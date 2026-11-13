"""Messaggi che partono da soli: promemoria il giorno prima e richiesta di recensione dopo la visita."""
import logging
import os
from datetime import datetime, timedelta

import agenda
import db

log = logging.getLogger("promemoria")

ORA_PROMEMORIA = "10:00"      # il giorno prima dell'appuntamento
ORA_RECENSIONE = "20:00"      # la sera della visita
MARGINE_ORE = 2               # niente promemoria se mancano meno di 2 ore


def _quando(data_iso, hhmm):
    d = agenda.data_valida(data_iso)
    m = agenda.minuti(hhmm)
    return datetime(d.year, d.month, d.day, m // 60, m % 60, tzinfo=db.FUSO)


def esegui(mittente, adesso=None):
    """Invia ciò che è dovuto. Restituisce quanti messaggi sono partiti."""
    adesso = adesso or db.adesso()
    nome_prom = os.environ.get("MODELLO_PROMEMORIA", "promemoria_appuntamento")
    nome_rec = os.environ.get("MODELLO_RECENSIONE", "richiesta_recensione")
    oggi = adesso.date()
    inviati = 0
    for p in db.prenotazioni_da_avvisare((oggi - timedelta(days=1)).isoformat(), (oggi + timedelta(days=1)).isoformat()):
        appuntamento = _quando(p["data"], p["ora"])
        try:
            if not p["promemoria_inviato"]:
                momento = _quando((appuntamento.date() - timedelta(days=1)).isoformat(), ORA_PROMEMORIA)
                creata = datetime.fromisoformat(p["creata"])
                if creata >= momento:
                    db.segna(p["id"], "promemoria_inviato")          # prenotato all'ultimo: non serve
                elif momento <= adesso < appuntamento - timedelta(hours=MARGINE_ORE):
                    giorno = "oggi" if appuntamento.date() == oggi else "domani"
                    mittente.modello(p["phone_number_id"], p["cliente_wa"], nome_prom,
                                     [p["nome"], giorno, p["ora"], p["salone_nome"]])
                    db.segna(p["id"], "promemoria_inviato")
                    inviati += 1
            if (not p["recensione_inviata"] and p["piano"] == "completo" and p["link_recensioni"]
                    and _quando(p["data"], ORA_RECENSIONE) <= adesso < _quando(p["data"], ORA_RECENSIONE) + timedelta(hours=16)):
                mittente.modello(p["phone_number_id"], p["cliente_wa"], nome_rec,
                                 [p["nome"], p["salone_nome"], p["link_recensioni"]])
                db.segna(p["id"], "recensione_inviata")
                inviati += 1
        except Exception:  # un errore su un cliente non deve fermare gli altri
            log.exception("Invio non riuscito per la prenotazione %s", p["id"])
    return inviati
