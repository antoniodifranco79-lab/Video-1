"""Test del servizio (nessuna chiamata vera a WhatsApp o a Claude).

Esegui:  python -m pytest -q test_server.py
"""
import hashlib
import hmac
import json
import types
from datetime import date, datetime, timedelta

import pytest

import agenda
import assistente
import db
import promemoria
import whatsapp

LUN = datetime(2026, 11, 16, 9, 0, tzinfo=db.FUSO)   # lunedì: il salone tipo è chiuso
MAR = date(2026, 11, 17)


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("PROMEMORIA_ATTIVI", "0")
    db.inizializza()


@pytest.fixture
def salone():
    sid = db.crea_salone("Salone Aurora", "PNID1", indirizzo="Via Roma 12", telefono="0123",
                         link_recensioni="https://g.page/r/test")
    return db.salone(sid)


# ================================================================== agenda
def test_orari_testo_andata_e_ritorno():
    o = agenda.leggi_orari_testo({"0": "chiuso", "1": "9.00-13:00, 15:00-19:30", "5": "09:00-18:00"})
    assert o["0"] == [] and o["1"] == [["09:00", "13:00"], ["15:00", "19:30"]] and o["6"] == []
    for sbagliato in ("9-13", "13:00-09:00", "09:00-13:00, 12:00-15:00", "25:00-26:00"):
        with pytest.raises(ValueError):
            agenda.leggi_orari_testo({"1": sbagliato})


@pytest.mark.parametrize("giorno,ora,durata,atteso", [
    (MAR, "09:00", 45, None),
    (MAR, "12:30", 45, "dentro l'orario"),        # finisce dopo le 13 (pausa pranzo)
    (MAR, "13:30", 30, "dentro l'orario"),
    (MAR, "18:45", 45, None),                      # finisce alle 19:30 esatte
    (date(2026, 11, 22), "10:00", 30, "chiuso"),   # domenica
    (date(2026, 11, 16), "08:00", 30, "già passato"),
    (MAR + timedelta(days=90), "10:00", 30, "al massimo"),
    (MAR, "9:5", 30, "formato"),
])
def test_problema(salone, giorno, ora, durata, atteso):
    esito = agenda.problema(salone, giorno, ora, durata, [], LUN)
    assert esito is None if atteso is None else atteso in esito


def test_posti_e_sovrapposizioni(salone):
    occupato = [{"ora": "10:00", "minuti": 60}]
    assert "non c'è posto" in agenda.problema(salone, MAR, "10:30", 30, occupato, LUN)
    assert agenda.problema(salone, MAR, "11:00", 30, occupato, LUN) is None   # subito dopo: libero
    assert agenda.problema(salone, MAR, "09:30", 30, occupato, LUN) is None   # finisce alle 10: libero
    salone["posti"] = 2
    assert agenda.problema(salone, MAR, "10:30", 30, occupato, LUN) is None


def test_orari_liberi(salone):
    liberi = agenda.orari_liberi(salone, MAR, 45, [{"ora": "09:00", "minuti": 60}], LUN)
    assert "09:00" not in liberi and "10:00" in liberi and "12:15" in liberi and "12:30" not in liberi
    assert liberi[-1] == "18:45"
    assert agenda.orari_liberi(salone, date(2026, 11, 22), 30, [], LUN) == []


def test_trova_servizio(salone):
    assert agenda.trova_servizio(salone, "piega")["nome"] == "Piega"
    assert agenda.trova_servizio(salone, "Taglio") is None          # ambiguo: donna o uomo
    assert agenda.trova_servizio(salone, "taglio uomo")["prezzo"] == 18


# ================================================================== whatsapp
def firma(corpo, segreto="segreto"):
    return "sha256=" + hmac.new(segreto.encode(), corpo, hashlib.sha256).hexdigest()


def test_firma():
    assert whatsapp.firma_valida("segreto", b"abc", firma(b"abc"))
    assert not whatsapp.firma_valida("segreto", b"abc", firma(b"abcd"))
    assert not whatsapp.firma_valida("", b"abc", firma(b"abc", ""))
    assert not whatsapp.firma_valida("segreto", b"abc", None)


def webhook(testo="Ciao", msg_id="wamid.1", tipo="text", numero="PNID1", da="393331112222"):
    m = {"from": da, "id": msg_id, "type": tipo}
    if tipo == "text":
        m["text"] = {"body": testo}
    return {"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": numero},
                                              "contacts": [{"wa_id": da, "profile": {"name": "Giulia"}}],
                                              "messages": [m]}}]}]}


def test_lettura_webhook():
    msgs = whatsapp.messaggi_in_arrivo(webhook("Buongiorno"))
    assert msgs == [{"phone_number_id": "PNID1", "da": "393331112222", "nome": "Giulia", "id": "wamid.1",
                     "tipo": "text", "testo": "Buongiorno"}]
    assert whatsapp.messaggi_in_arrivo({"entry": [{"changes": [{"value": {"statuses": [{}]}}]}]}) == []
    assert whatsapp.messaggi_in_arrivo({}) == []


# ================================================================== assistente (Claude finto)
def blocco_testo(t):
    return types.SimpleNamespace(type="text", text=t)


def blocco_strumento(nome, dati, bid="tu_1"):
    return types.SimpleNamespace(type="tool_use", id=bid, name=nome, input=dati)


class ClaudeFinto:
    def __init__(self, *risposte):
        self.risposte = list(risposte)
        self.chiamate = []
        self.beta = types.SimpleNamespace(messages=types.SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.chiamate.append(json.loads(json.dumps(kw, default=lambda o: o.__dict__)))
        stop, contenuto = self.risposte.pop(0)
        return types.SimpleNamespace(stop_reason=stop, content=contenuto)


def test_assistente_prenota_con_strumenti(salone):
    db.salva_messaggio(salone["id"], "39333", "cliente", "Vorrei una piega martedì alle 10, sono Giulia")
    claude = ClaudeFinto(
        ("tool_use", [blocco_strumento("orari_liberi", {"data": "2026-11-17", "servizio": "Piega"})]),
        ("tool_use", [blocco_strumento("prenota", {"servizio": "piega", "data": "2026-11-17", "ora": "10.00",
                                                   "nome": "Giulia"}, "tu_2")]),
        ("end_turn", [blocco_testo("Fatto Giulia! Piega martedì 17 alle 10:00.")]),
    )
    testo = assistente.rispondi(salone, "39333", "Giulia", adesso=LUN, client=claude)
    assert testo.startswith("Fatto Giulia")
    pren = db.prenotazioni_giorno(salone["id"], "2026-11-17")
    assert [(p["ora"], p["servizio"], p["origine"], p["cliente_wa"]) for p in pren] == [("10:00", "Piega", "bot", "39333")]
    prima = claude.chiamate[0]
    assert prima["model"] == "claude-opus-5-5" and prima["fallbacks"] == "default"
    assert prima["messages"][0]["role"] == "user" and "Giulia" in prima["messages"][0]["content"]
    assert "Orari liberi" in claude.chiamate[1]["messages"][-1]["content"][0]["content"]


def test_assistente_non_prenota_orario_occupato(salone):
    db.inserisci_prenotazione(salone["id"], cliente_wa="", nome="X", servizio="Piega", minuti=30, prezzo=20,
                              data="2026-11-17", ora="10:00", origine="salone")
    s = assistente.Strumenti(salone, "39333", "Giulia", LUN)
    assert s.esegui("prenota", {"servizio": "Piega", "data": "2026-11-17", "ora": "10:15", "nome": "Giulia"}).startswith("Non prenotato")
    assert s.esegui("prenota", {"servizio": "Massaggio", "data": "2026-11-17", "ora": "11:00", "nome": "G"}).startswith("Servizio non trovato")
    assert s.esegui("inventato", {}) == "Strumento sconosciuto."
    assert s.esegui("prenota", {"servizio": "Piega"}) == "Dati mancanti o non validi per questo strumento."


def test_assistente_annulla_solo_le_proprie(salone):
    mia = db.inserisci_prenotazione(salone["id"], cliente_wa="39333", nome="G", servizio="Piega", minuti=30, prezzo=20,
                                    data="2026-11-17", ora="10:00", origine="bot")
    altrui = db.inserisci_prenotazione(salone["id"], cliente_wa="39444", nome="H", servizio="Piega", minuti=30, prezzo=20,
                                       data="2026-11-17", ora="11:00", origine="bot")
    s = assistente.Strumenti(salone, "39333", "G", LUN)
    assert f"n.{mia}" in s.esegui("mie_prenotazioni", {})
    assert "non risulta" in s.esegui("annulla", {"numero": altrui})
    assert "annullata" in s.esegui("annulla", {"numero": mia})
    assert [p["id"] for p in db.prenotazioni_giorno(salone["id"], "2026-11-17")] == [altrui]


def test_assistente_rifiuto_passa_al_salone(salone):
    db.salva_messaggio(salone["id"], "39333", "cliente", "...")
    testo = assistente.rispondi(salone, "39333", "G", adesso=LUN, client=ClaudeFinto(("refusal", [])))
    assert testo == assistente.RISPOSTA_DI_RISERVA
    assert len(db.lista_da_gestire(salone["id"])) == 1


def test_storia_alternata(salone):
    for ruolo, t in [("bot", "vecchio"), ("cliente", "a"), ("cliente", "b"), ("bot", "c"), ("cliente", "d")]:
        db.salva_messaggio(salone["id"], "39333", ruolo, t)
    claude = ClaudeFinto(("end_turn", [blocco_testo("ok")]))
    assistente.rispondi(salone, "39333", "", adesso=LUN, client=claude)
    msgs = claude.chiamate[0]["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[0]["content"] == "a\nb"


# ================================================================== server web
@pytest.fixture
def web(monkeypatch):
    from fastapi.testclient import TestClient
    import app as modulo
    monkeypatch.setenv("WA_APP_SECRET", "segreto")
    monkeypatch.setenv("WA_VERIFY_TOKEN", "verifica")
    monkeypatch.setenv("ADMIN_PASSWORD", "password-lunga-1")
    inviati = []
    modulo.mittente = types.SimpleNamespace(testo=lambda pn, a, t: inviati.append((pn, a, t)),
                                            modello=lambda *a, **k: inviati.append(("modello", a)))
    modulo._risposto_fino.clear()
    with TestClient(modulo.app) as c:
        c.inviati = inviati
        c.modulo = modulo
        yield c


def posta(web, payload):
    corpo = json.dumps(payload).encode()
    return web.post("/webhook", content=corpo, headers={"x-hub-signature-256": firma(corpo), "content-type": "application/json"})


def test_verifica_webhook(web):
    r = web.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verifica", "hub.challenge": "42"})
    assert r.status_code == 200 and r.text == "42"
    assert web.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "no", "hub.challenge": "42"}).status_code == 403


def test_webhook_risponde_una_volta(web, salone, monkeypatch):
    monkeypatch.setattr(assistente, "rispondi", lambda s, wa, nome, client=None: f"Ciao {nome}!")
    assert web.post("/webhook", content=b"{}", headers={"x-hub-signature-256": "sha256=000"}).status_code == 403
    assert posta(web, webhook("Ciao")).status_code == 200
    assert posta(web, webhook("Ciao")).status_code == 200        # stesso id: WhatsApp lo ha reinviato
    assert web.inviati == [("PNID1", "393331112222", "Ciao Giulia!")]
    assert [m["ruolo"] for m in db.storia(salone["id"], "393331112222")] == ["cliente", "bot"]


def test_webhook_numero_sconosciuto_e_vocali(web, salone, monkeypatch):
    monkeypatch.setattr(assistente, "rispondi", lambda *a, **k: pytest.fail("non deve rispondere"))
    posta(web, webhook("Ciao", "wamid.x", numero="ALTRO"))
    assert web.inviati == []
    posta(web, webhook(msg_id="wamid.audio", tipo="audio"))
    assert "solo i messaggi scritti" in web.inviati[0][2]
    assert "audio" in db.lista_da_gestire(salone["id"])[0]["motivo"]


def test_webhook_bot_spento_ed_errori(web, salone, monkeypatch):
    db.aggiorna_salone(salone["id"], bot_attivo=0)
    monkeypatch.setattr(assistente, "rispondi", lambda *a, **k: pytest.fail("bot spento"))
    posta(web, webhook("Ciao", "wamid.2"))
    assert web.inviati == []
    db.aggiorna_salone(salone["id"], bot_attivo=1)

    def guasto(*a, **k):
        raise RuntimeError("API giù")
    monkeypatch.setattr(assistente, "rispondi", guasto)
    posta(web, webhook("Ciao", "wamid.3"))
    assert web.inviati[-1][2] == assistente.RISPOSTA_DI_RISERVA
    assert db.lista_da_gestire(salone["id"])


def test_messaggio_gia_coperto_non_riceve_doppia_risposta(web, salone, monkeypatch):
    chiamate = []
    monkeypatch.setattr(assistente, "rispondi", lambda *a, **k: chiamate.append(1) or "ok")
    gestisci = web.modulo.gestisci_messaggio
    # due messaggi arrivati insieme: il primo viene risposto includendo anche il secondo
    db.gia_processato("pre")  # nessun effetto: solo per avere il db pronto
    m1 = whatsapp.messaggi_in_arrivo(webhook("Ciao", "wamid.a"))[0]
    m2 = whatsapp.messaggi_in_arrivo(webhook("vorrei prenotare", "wamid.b"))[0]
    db.salva_messaggio(salone["id"], m2["da"], "cliente", "arrivato mentre il primo aspettava")
    gestisci(m1)
    web.modulo._risposto_fino[(salone["id"], m2["da"])] = 10 ** 9   # come se la risposta avesse coperto tutto
    gestisci(m2)
    assert len(chiamate) == 1


def test_pannello(web, salone):
    assert web.get("/s/sbagliato").status_code == 404
    r = web.get(f"/s/{salone['token']}")
    assert r.status_code == 200 and "Salone Aurora" in r.text
    giorno = (db.adesso().date() + timedelta(days=1))
    while not agenda.turni(salone["orari"], giorno):
        giorno += timedelta(days=1)
    r = web.post(f"/s/{salone['token']}/prenota", data={"data": giorno.isoformat(), "ora": "10:00", "servizio": "Piega",
                                                        "nome": "Mario <b>", "telefono": "333 444 5555"},
                 follow_redirects=False)
    assert r.status_code == 303 and "ok=" in r.headers["location"]
    pren = db.prenotazioni_giorno(salone["id"], giorno.isoformat())
    assert pren[0]["cliente_wa"] == "393334445555" and pren[0]["origine"] == "salone"
    html = web.get(f"/s/{salone['token']}").text
    assert "Mario &lt;b&gt;" in html and "Mario <b>" not in html            # niente HTML iniettato
    r = web.post(f"/s/{salone['token']}/prenota", data={"data": giorno.isoformat(), "ora": "10:00", "servizio": "Piega",
                                                        "nome": "Anna"}, follow_redirects=False)
    assert "errore=" in r.headers["location"]                                # orario occupato
    r = web.post(f"/s/{salone['token']}/prenota", data={"data": giorno.isoformat(), "ora": "10:00", "servizio": "Piega",
                                                        "nome": "Anna", "forza": "1"}, follow_redirects=False)
    assert "ok=" in r.headers["location"]
    web.post(f"/s/{salone['token']}/annulla/{pren[0]['id']}")
    assert len(db.prenotazioni_giorno(salone["id"], giorno.isoformat())) == 1
    web.post(f"/s/{salone['token']}/bot", data={"attivo": "0"})
    assert db.salone(salone["id"])["bot_attivo"] == 0


def test_impostazioni(web, salone):
    url = f"/s/{salone['token']}/impostazioni"
    assert web.get(url).status_code == 200
    dati = {"nome": "Aurora Hair", "posti": "2", "servizi": "Taglio; 25,50; 45\nPiega; 20; 30",
            **{f"orari_{g}": "09:00-13:00" for g in range(7)}, "link_recensioni": "https://g.page/r/x"}
    r = web.post(url, data=dati, follow_redirects=False)
    assert "ok=" in r.headers["location"]
    s = db.salone(salone["id"])
    assert s["nome"] == "Aurora Hair" and s["posti"] == 2 and s["servizi"][0] == {"nome": "Taglio", "prezzo": 25.5, "minuti": 45}
    for campo, valore in [("servizi", "Taglio 25"), ("orari_1", "9-13"), ("posti", "99"), ("link_recensioni", "javascript:x")]:
        r = web.post(url, data={**dati, campo: valore}, follow_redirects=False)
        assert "errore=" in r.headers["location"], campo


def test_admin(web, salone, monkeypatch):
    assert web.get("/admin").status_code == 401
    assert web.get("/admin", auth=("admin", "sbagliata")).status_code == 401
    r = web.get("/admin", auth=("admin", "password-lunga-1"))
    assert r.status_code == 200 and "Salone Aurora" in r.text and "89 €" in r.text
    web.post("/admin/saloni", data={"nome": "Barber Luca", "phone_number_id": "PNID2", "piano": "base"},
             auth=("admin", "password-lunga-1"))
    assert db.salone_da_numero("PNID2")["piano"] == "base"
    r = web.post("/admin/saloni", data={"nome": "Doppio", "phone_number_id": "PNID2"}, auth=("admin", "password-lunga-1"),
                 follow_redirects=False)
    assert "errore=" in r.headers["location"]
    monkeypatch.setenv("ADMIN_PASSWORD", "corta")
    assert web.get("/admin", auth=("admin", "corta")).status_code == 503


# ================================================================== promemoria
def test_promemoria_e_recensioni(salone):
    inviati = []
    m = types.SimpleNamespace(modello=lambda pn, a, nome, par: inviati.append((nome, par)))
    pid = db.inserisci_prenotazione(salone["id"], cliente_wa="39333", nome="Giulia", servizio="Piega", minuti=30,
                                    prezzo=20, data="2026-11-18", ora="15:00", origine="bot")
    with db.con() as c:
        c.execute("UPDATE prenotazioni SET creata = ? WHERE id = ?", ("2026-11-10T12:00:00+01:00", pid))
    t = lambda g, h, mi=0: datetime(2026, 11, g, h, mi, tzinfo=db.FUSO)
    assert promemoria.esegui(m, t(17, 9, 59)) == 0                       # troppo presto
    assert promemoria.esegui(m, t(17, 10, 0)) == 1
    assert inviati[-1] == ("promemoria_appuntamento", ["Giulia", "domani", "15:00", "Salone Aurora"])
    assert promemoria.esegui(m, t(17, 11)) == 0                            # non due volte
    assert promemoria.esegui(m, t(18, 20, 0)) == 1
    assert inviati[-1] == ("richiesta_recensione", ["Giulia", "Salone Aurora", "https://g.page/r/test"])
    assert promemoria.esegui(m, t(18, 21)) == 0


def test_promemoria_casi_limite(salone):
    inviati = []
    m = types.SimpleNamespace(modello=lambda *a: inviati.append(a))
    # prenotata dopo le 10 del giorno prima: niente promemoria
    db.inserisci_prenotazione(salone["id"], cliente_wa="39333", nome="A", servizio="Piega", minuti=30, prezzo=20,
                              data="2026-11-18", ora="15:00", origine="bot")
    with db.con() as c:
        c.execute("UPDATE prenotazioni SET creata = '2026-11-17T18:00:00+01:00'")
    # senza numero: niente messaggi; piano base: niente recensione
    db.inserisci_prenotazione(salone["id"], cliente_wa="", nome="B", servizio="Piega", minuti=30, prezzo=20,
                              data="2026-11-18", ora="16:00", origine="salone")
    db.aggiorna_salone(salone["id"], piano="base")
    assert promemoria.esegui(m, datetime(2026, 11, 18, 9, tzinfo=db.FUSO)) == 0
    assert promemoria.esegui(m, datetime(2026, 11, 18, 20, 30, tzinfo=db.FUSO)) == 0
    # un errore di invio non blocca e non segna come inviato
    db.aggiorna_salone(salone["id"], piano="completo")
    rotto = types.SimpleNamespace(modello=lambda *a: (_ for _ in ()).throw(RuntimeError("giù")))
    assert promemoria.esegui(rotto, datetime(2026, 11, 18, 20, 30, tzinfo=db.FUSO)) == 0
    assert promemoria.esegui(m, datetime(2026, 11, 18, 20, 31, tzinfo=db.FUSO)) == 1
