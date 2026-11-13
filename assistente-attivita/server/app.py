"""Server web: webhook di WhatsApp, pannello dei saloni, pannello amministratore."""
import asyncio
import logging
import os
import re
import secrets
import threading
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

import agenda
import assistente
import db
import promemoria
import whatsapp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")

QUI = Path(__file__).resolve().parent
modelli_html = Jinja2Templates(directory=str(QUI / "templates"))
modelli_html.env.globals["nome_giorno"] = lambda s: agenda.nome_giorno(agenda.data_valida(s))

mittente = whatsapp.Mittente()
_lucchetti, _risposto_fino, _lock_globale = {}, {}, threading.Lock()


async def _ciclo_promemoria():
    while True:
        try:
            await asyncio.to_thread(promemoria.esegui, mittente)
        except Exception:
            log.exception("Errore nel ciclo dei promemoria")
        await asyncio.sleep(60)


@asynccontextmanager
async def avvio(app):
    db.inizializza()
    compito = None
    if os.environ.get("PROMEMORIA_ATTIVI", "1") == "1":
        compito = asyncio.create_task(_ciclo_promemoria())
    yield
    if compito:
        compito.cancel()


app = FastAPI(title="Assistente saloni", lifespan=avvio, docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/salute", response_class=PlainTextResponse)
def salute():
    return "ok"


# ================================================================== WhatsApp
@app.get("/webhook", response_class=PlainTextResponse)
def verifica_webhook(request: Request):
    q = request.query_params
    atteso = os.environ.get("WA_VERIFY_TOKEN", "")
    if q.get("hub.mode") == "subscribe" and atteso and secrets.compare_digest(q.get("hub.verify_token", ""), atteso):
        return q.get("hub.challenge", "")
    raise HTTPException(403, "Token di verifica non valido")


@app.post("/webhook")
async def ricevi_webhook(request: Request, background: BackgroundTasks):
    corpo = await request.body()
    if not whatsapp.firma_valida(os.environ.get("WA_APP_SECRET", ""), corpo, request.headers.get("x-hub-signature-256", "")):
        raise HTTPException(403, "Firma non valida")
    try:
        payload = await request.json()
    except ValueError:
        return {"ok": True}
    for m in whatsapp.messaggi_in_arrivo(payload):
        background.add_task(gestisci_messaggio, m)
    return {"ok": True}


def _lucchetto(chiave):
    with _lock_globale:
        return _lucchetti.setdefault(chiave, threading.Lock())


def gestisci_messaggio(m, client=None):
    if not m["id"] or not m["da"] or db.gia_processato(m["id"]):
        return
    s = db.salone_da_numero(m["phone_number_id"])
    if not s:
        log.warning("Messaggio per un numero non collegato a nessun salone: %s", m["phone_number_id"])
        return
    leggibile = m["tipo"] in ("text", "button", "interactive") and m["testo"]
    testo = m["testo"] if leggibile else f"[{m['tipo'] or 'messaggio'} non leggibile]"
    msg_id = db.salva_messaggio(s["id"], m["da"], "cliente", testo[:2000])
    if not s["bot_attivo"]:
        return
    chiave = (s["id"], m["da"])
    with _lucchetto(chiave):
        if _risposto_fino.get(chiave, 0) >= msg_id:
            return  # già coperto da una risposta data mentre questo messaggio aspettava
        incluso = db.ultimo_id_cliente(s["id"], m["da"])  # i messaggi fin qui finiscono nella risposta
        if not leggibile:
            db.apri_da_gestire(s["id"], m["da"], m["nome"], f"Ha mandato un {m['tipo'] or 'messaggio'} che il bot non sa leggere")
            risposta = "Posso leggere solo i messaggi scritti: scrivimi pure qui! Ho comunque avvisato il salone."
        else:
            try:
                risposta = assistente.rispondi(s, m["da"], m["nome"], client=client)
            except Exception:
                log.exception("Errore dell'assistente (salone %s)", s["id"])
                db.apri_da_gestire(s["id"], m["da"], m["nome"], "L'assistente ha avuto un errore: rispondi tu")
                risposta = assistente.RISPOSTA_DI_RISERVA
        if not risposta:
            return
        try:
            mittente.testo(s["phone_number_id"], m["da"], risposta)
        except Exception:
            log.exception("Invio su WhatsApp non riuscito (salone %s)", s["id"])
            db.apri_da_gestire(s["id"], m["da"], m["nome"], "Risposta non inviata per un errore di WhatsApp")
            return
        db.salva_messaggio(s["id"], m["da"], "bot", risposta)
        _risposto_fino[chiave] = max(_risposto_fino.get(chiave, 0), incluso)


# ================================================================== pannello del salone
def _salone_o_404(token):
    s = db.salone_da_token(token)
    if not s:
        raise HTTPException(404, "Pagina non trovata")
    return s


def _torna(url, ok=None, errore=None):
    if ok:
        url += "?ok=" + quote(ok)
    elif errore:
        url += "?errore=" + quote(errore)
    return RedirectResponse(url, status_code=303)


def numero_whatsapp(testo):
    cifre = re.sub(r"\D", "", testo or "")
    if not cifre:
        return ""
    if cifre.startswith("00"):
        cifre = cifre[2:]
    if len(cifre) == 10 and cifre.startswith("3"):
        cifre = "39" + cifre
    return cifre if 8 <= len(cifre) <= 15 else None


@app.get("/s/{token}", response_class=HTMLResponse)
def pannello(request: Request, token: str):
    s = _salone_o_404(token)
    oggi = db.adesso().date()
    pren = db.prenotazioni_periodo(s["id"], oggi.isoformat(), (oggi + timedelta(days=13)).isoformat())
    giorni = []
    for i in range(14):
        d = oggi + timedelta(days=i)
        lista = [p for p in pren if p["data"] == d.isoformat()]
        if lista or agenda.turni(s["orari"], d):
            giorni.append({"data": d.isoformat(), "nome": agenda.nome_giorno(d), "pren": lista,
                           "chiuso": not agenda.turni(s["orari"], d)})
    dal = (db.adesso() - timedelta(days=30)).isoformat(timespec="seconds")
    stat = {"messaggi": db.conta_messaggi(s["id"], dal),
            "prenotazioni_bot": db.conta_prenotazioni_bot(s["id"], dal),
            "da_gestire": len(db.lista_da_gestire(s["id"]))}
    return modelli_html.TemplateResponse(request, "pannello.html", {
        "s": s, "giorni": giorni, "da_gestire": db.lista_da_gestire(s["id"]), "stat": stat,
        "oggi": oggi.isoformat(), "ok": request.query_params.get("ok"), "errore": request.query_params.get("errore")})


@app.post("/s/{token}/prenota")
def pannello_prenota(token: str, data: str = Form(...), ora: str = Form(...), servizio: str = Form(...),
                     nome: str = Form(...), telefono: str = Form(""), minuti: int = Form(30), forza: str = Form("")):
    s = _salone_o_404(token)
    base = f"/s/{token}"
    d = agenda.data_valida(data)
    if not d:
        return _torna(base, errore="Data non valida")
    if servizio == "__blocco__":
        serv = {"nome": "Orario bloccato", "minuti": max(15, min(600, minuti)), "prezzo": 0}
    else:
        serv = agenda.trova_servizio(s, servizio)
        if not serv:
            return _torna(base, errore="Servizio non trovato")
    wa = numero_whatsapp(telefono)
    if wa is None:
        return _torna(base, errore="Numero di telefono non valido")
    ora = ora.strip()
    if not agenda.RE_ORA.match(ora):
        return _torna(base, errore="Orario non valido")
    motivo = agenda.problema(s, d, ora, serv["minuti"], db.prenotazioni_giorno(s["id"], d.isoformat()), db.adesso() - timedelta(days=1))
    if motivo and not forza:
        return _torna(base, errore=f"Non inserito: {motivo}. Spunta «Inserisci comunque» se vuoi forzare.")
    db.inserisci_prenotazione(s["id"], cliente_wa=wa, nome=" ".join(nome.split())[:60] or "Cliente", servizio=serv["nome"],
                              minuti=serv["minuti"], prezzo=serv["prezzo"], data=d.isoformat(), ora=ora, origine="salone")
    return _torna(base, ok="Appuntamento inserito")


@app.post("/s/{token}/annulla/{pren_id}")
def pannello_annulla(token: str, pren_id: int):
    s = _salone_o_404(token)
    db.annulla_prenotazione(s["id"], pren_id)
    return _torna(f"/s/{token}", ok="Appuntamento annullato")


@app.post("/s/{token}/gestito/{item_id}")
def pannello_gestito(token: str, item_id: int):
    s = _salone_o_404(token)
    db.chiudi_da_gestire(s["id"], item_id)
    return _torna(f"/s/{token}", ok="Segnato come fatto")


@app.post("/s/{token}/bot")
def pannello_bot(token: str, attivo: str = Form("0")):
    s = _salone_o_404(token)
    db.aggiorna_salone(s["id"], bot_attivo=1 if attivo == "1" else 0)
    return _torna(f"/s/{token}", ok="Assistente acceso" if attivo == "1" else "Assistente spento: rispondete voi")


@app.get("/s/{token}/impostazioni", response_class=HTMLResponse)
def impostazioni(request: Request, token: str):
    s = _salone_o_404(token)
    orari_testo = {str(g): ", ".join(f"{a}-{b}" for a, b in s["orari"].get(str(g), [])) or "chiuso" for g in range(7)}
    servizi_testo = "\n".join(f"{x['nome']}; {x['prezzo']:g}; {x['minuti']}" for x in s["servizi"])
    return modelli_html.TemplateResponse(request, "impostazioni.html", {
        "s": s, "orari_testo": orari_testo, "servizi_testo": servizi_testo, "giorni": agenda.GIORNI,
        "ok": request.query_params.get("ok"), "errore": request.query_params.get("errore")})


def leggi_servizi(testo):
    servizi = []
    for n, riga in enumerate((testo or "").splitlines(), 1):
        if not riga.strip():
            continue
        pezzi = [p.strip() for p in riga.split(";")]
        try:
            nome, prezzo, durata = pezzi[0], float(pezzi[1].replace(",", ".").replace("€", "")), int(pezzi[2])
        except (IndexError, ValueError):
            raise ValueError(f"Servizi, riga {n}: scrivi «Nome; prezzo; minuti», per esempio «Piega; 20; 30»")
        if not nome or prezzo < 0 or not 5 <= durata <= 600:
            raise ValueError(f"Servizi, riga {n}: controlla nome, prezzo e minuti (tra 5 e 600)")
        servizi.append({"nome": nome[:60], "prezzo": prezzo, "minuti": durata})
    if not servizi:
        raise ValueError("Serve almeno un servizio")
    return servizi


@app.post("/s/{token}/impostazioni")
async def salva_impostazioni(request: Request, token: str):
    s = _salone_o_404(token)
    f = await request.form()
    base = f"/s/{token}/impostazioni"
    try:
        orari = agenda.leggi_orari_testo({str(g): f.get(f"orari_{g}", "") for g in range(7)})
        servizi = leggi_servizi(f.get("servizi", ""))
        posti = int(f.get("posti", "1"))
        if not 1 <= posti <= 30:
            raise ValueError("Postazioni: un numero tra 1 e 30")
    except ValueError as e:
        return _torna(base, errore=str(e))
    link = (f.get("link_recensioni") or "").strip()
    if link and not link.startswith("https://"):
        return _torna(base, errore="Il link per le recensioni deve iniziare con https://")
    db.aggiorna_salone(s["id"], nome=(f.get("nome") or s["nome"]).strip()[:80], indirizzo=(f.get("indirizzo") or "").strip()[:120],
                       telefono=(f.get("telefono") or "").strip()[:30], orari=orari, servizi=servizi, posti=posti,
                       link_recensioni=link[:300], note=(f.get("note") or "").strip()[:1500])
    return _torna(base, ok="Impostazioni salvate")


# ================================================================== amministratore
sicurezza = HTTPBasic()


def admin(credenziali: HTTPBasicCredentials = Depends(sicurezza)):
    password = os.environ.get("ADMIN_PASSWORD", "")
    if len(password) < 10:
        raise HTTPException(503, "Imposta ADMIN_PASSWORD (almeno 10 caratteri) nelle variabili del server")
    if not (secrets.compare_digest(credenziali.username, "admin") and secrets.compare_digest(credenziali.password, password)):
        raise HTTPException(401, "Accesso negato", headers={"WWW-Authenticate": "Basic"})
    return True


@app.get("/admin", response_class=HTMLResponse)
def pagina_admin(request: Request, _=Depends(admin)):
    dal = (db.adesso() - timedelta(days=30)).isoformat(timespec="seconds")
    saloni = [dict(s, messaggi=db.conta_messaggi(s["id"], dal), prenotazioni_bot=db.conta_prenotazioni_bot(s["id"], dal),
                   da_gestire=len(db.lista_da_gestire(s["id"]))) for s in db.tutti_i_saloni()]
    canone = {"base": 49, "completo": 89}
    return modelli_html.TemplateResponse(request, "admin.html", {
        "saloni": saloni, "base_url": str(request.base_url).rstrip("/"),
        "totale": sum(canone.get(s["piano"], 0) for s in saloni if s["phone_number_id"]),
        "ok": request.query_params.get("ok"), "errore": request.query_params.get("errore")})


@app.post("/admin/saloni")
def admin_nuovo(nome: str = Form(...), phone_number_id: str = Form(""), piano: str = Form("completo"), _=Depends(admin)):
    if piano not in ("base", "completo") or not nome.strip():
        return _torna("/admin", errore="Dati non validi")
    if phone_number_id.strip() and db.salone_da_numero(phone_number_id.strip()):
        return _torna("/admin", errore="Questo numero è già collegato a un altro salone")
    db.crea_salone(nome.strip()[:80], phone_number_id.strip() or None, piano=piano)
    return _torna("/admin", ok=f"Salone «{nome.strip()}» creato")


@app.post("/admin/saloni/{salone_id}")
def admin_modifica(salone_id: int, phone_number_id: str = Form(""), piano: str = Form("completo"), _=Depends(admin)):
    s = db.salone(salone_id)
    if not s or piano not in ("base", "completo"):
        return _torna("/admin", errore="Dati non validi")
    altro = db.salone_da_numero(phone_number_id.strip()) if phone_number_id.strip() else None
    if altro and altro["id"] != salone_id:
        return _torna("/admin", errore="Questo numero è già collegato a un altro salone")
    db.aggiorna_salone(salone_id, phone_number_id=phone_number_id.strip() or None, piano=piano)
    return _torna("/admin", ok=f"«{s['nome']}» aggiornato")
