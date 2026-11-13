"""Database SQLite: saloni, prenotazioni, messaggi, cose da gestire."""
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("Europe/Rome")

SCHEMA = """
CREATE TABLE IF NOT EXISTS saloni (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    indirizzo TEXT NOT NULL DEFAULT '',
    telefono TEXT NOT NULL DEFAULT '',
    phone_number_id TEXT UNIQUE,              -- id del numero WhatsApp su Meta
    token TEXT NOT NULL UNIQUE,               -- link segreto del pannello del titolare
    orari TEXT NOT NULL,                      -- JSON {"0": [["09:00","13:00"], ...], ...} 0 = lunedì
    servizi TEXT NOT NULL,                    -- JSON [{"nome","prezzo","minuti"}]
    posti INTEGER NOT NULL DEFAULT 1,         -- appuntamenti contemporanei possibili
    piano TEXT NOT NULL DEFAULT 'completo',   -- 'base' | 'completo'
    link_recensioni TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',            -- altre informazioni per l'assistente
    bot_attivo INTEGER NOT NULL DEFAULT 1,
    creato TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prenotazioni (
    id INTEGER PRIMARY KEY,
    salone_id INTEGER NOT NULL REFERENCES saloni(id),
    cliente_wa TEXT NOT NULL DEFAULT '',
    nome TEXT NOT NULL,
    servizio TEXT NOT NULL,
    minuti INTEGER NOT NULL,
    prezzo REAL NOT NULL DEFAULT 0,
    data TEXT NOT NULL,                       -- AAAA-MM-GG
    ora TEXT NOT NULL,                        -- HH:MM
    origine TEXT NOT NULL,                    -- 'bot' | 'salone'
    stato TEXT NOT NULL DEFAULT 'confermata', -- 'confermata' | 'annullata'
    promemoria_inviato INTEGER NOT NULL DEFAULT 0,
    recensione_inviata INTEGER NOT NULL DEFAULT 0,
    creata TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pren_giorno ON prenotazioni(salone_id, data);
CREATE TABLE IF NOT EXISTS messaggi (
    id INTEGER PRIMARY KEY,
    salone_id INTEGER NOT NULL,
    cliente_wa TEXT NOT NULL,
    ruolo TEXT NOT NULL,                      -- 'cliente' | 'bot'
    testo TEXT NOT NULL,
    quando TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_msg_cliente ON messaggi(salone_id, cliente_wa, id);
CREATE TABLE IF NOT EXISTS processati (
    msg_id TEXT PRIMARY KEY,
    quando TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS da_gestire (
    id INTEGER PRIMARY KEY,
    salone_id INTEGER NOT NULL,
    cliente_wa TEXT NOT NULL,
    nome_cliente TEXT NOT NULL DEFAULT '',
    motivo TEXT NOT NULL,
    stato TEXT NOT NULL DEFAULT 'aperto',
    quando TEXT NOT NULL
);
"""

ORARI_TIPO = {str(g): [["09:00", "13:00"], ["15:00", "19:30"]] for g in range(1, 5)}
ORARI_TIPO.update({"0": [], "5": [["09:00", "18:00"]], "6": []})
SERVIZI_TIPO = [
    {"nome": "Taglio donna", "prezzo": 28, "minuti": 45},
    {"nome": "Taglio uomo", "prezzo": 18, "minuti": 30},
    {"nome": "Piega", "prezzo": 20, "minuti": 30},
    {"nome": "Colore", "prezzo": 45, "minuti": 90},
]


def percorso():
    return os.environ.get("DB_PATH", "dati.sqlite3")


def adesso():
    return datetime.now(FUSO)


def ora_iso():
    return adesso().isoformat(timespec="seconds")


@contextmanager
def con():
    c = sqlite3.connect(percorso(), timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    try:
        yield c
        c.commit()
    finally:
        c.close()


def inizializza():
    with con() as c:
        c.execute("PRAGMA journal_mode = WAL")
        c.executescript(SCHEMA)


# ------------------------------------------------------------------ saloni
def _salone(riga):
    if riga is None:
        return None
    s = dict(riga)
    s["orari"] = json.loads(s["orari"])
    s["servizi"] = json.loads(s["servizi"])
    return s


def crea_salone(nome, phone_number_id=None, **campi):
    dati = {"indirizzo": "", "telefono": "", "orari": ORARI_TIPO, "servizi": SERVIZI_TIPO, "posti": 1,
            "piano": "completo", "link_recensioni": "", "note": ""}
    dati.update(campi)
    with con() as c:
        cur = c.execute(
            "INSERT INTO saloni (nome, indirizzo, telefono, phone_number_id, token, orari, servizi, posti, piano,"
            " link_recensioni, note, creato) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (nome, dati["indirizzo"], dati["telefono"], phone_number_id or None, secrets.token_urlsafe(24),
             json.dumps(dati["orari"]), json.dumps(dati["servizi"], ensure_ascii=False), int(dati["posti"]),
             dati["piano"], dati["link_recensioni"], dati["note"], ora_iso()))
        return cur.lastrowid


def aggiorna_salone(salone_id, **campi):
    ammessi = {"nome", "indirizzo", "telefono", "phone_number_id", "orari", "servizi", "posti", "piano",
               "link_recensioni", "note", "bot_attivo"}
    sets, valori = [], []
    for k, v in campi.items():
        if k not in ammessi:
            raise ValueError(k)
        if k in ("orari", "servizi"):
            v = json.dumps(v, ensure_ascii=False)
        if k == "phone_number_id":
            v = v or None
        sets.append(f"{k} = ?")
        valori.append(v)
    if sets:
        with con() as c:
            c.execute(f"UPDATE saloni SET {', '.join(sets)} WHERE id = ?", (*valori, salone_id))


def salone(salone_id):
    with con() as c:
        return _salone(c.execute("SELECT * FROM saloni WHERE id = ?", (salone_id,)).fetchone())


def salone_da_numero(phone_number_id):
    with con() as c:
        return _salone(c.execute("SELECT * FROM saloni WHERE phone_number_id = ?", (phone_number_id,)).fetchone())


def salone_da_token(token):
    with con() as c:
        return _salone(c.execute("SELECT * FROM saloni WHERE token = ?", (token,)).fetchone())


def tutti_i_saloni():
    with con() as c:
        return [_salone(r) for r in c.execute("SELECT * FROM saloni ORDER BY nome")]


# ------------------------------------------------------------------ prenotazioni
def prenotazioni_giorno(salone_id, data):
    with con() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM prenotazioni WHERE salone_id = ? AND data = ? AND stato = 'confermata' ORDER BY ora",
            (salone_id, data))]


def prenotazioni_periodo(salone_id, dal, al):
    with con() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM prenotazioni WHERE salone_id = ? AND data BETWEEN ? AND ? AND stato = 'confermata'"
            " ORDER BY data, ora", (salone_id, dal, al))]


def prenotazioni_cliente(salone_id, cliente_wa, dal):
    with con() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM prenotazioni WHERE salone_id = ? AND cliente_wa = ? AND data >= ? AND stato = 'confermata'"
            " ORDER BY data, ora", (salone_id, cliente_wa, dal))]


def inserisci_prenotazione(salone_id, *, cliente_wa, nome, servizio, minuti, prezzo, data, ora, origine):
    with con() as c:
        return c.execute(
            "INSERT INTO prenotazioni (salone_id, cliente_wa, nome, servizio, minuti, prezzo, data, ora, origine, creata)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (salone_id, cliente_wa, nome, servizio, minuti, prezzo, data, ora, origine, ora_iso())).lastrowid


def annulla_prenotazione(salone_id, pren_id):
    with con() as c:
        return c.execute("UPDATE prenotazioni SET stato = 'annullata' WHERE id = ? AND salone_id = ?",
                         (pren_id, salone_id)).rowcount == 1


def prenotazioni_da_avvisare(dal, al):
    """Prenotazioni confermate tra due date, con il salone, per promemoria e recensioni."""
    with con() as c:
        return [dict(r) for r in c.execute(
            "SELECT p.*, s.nome AS salone_nome, s.phone_number_id, s.piano, s.link_recensioni"
            " FROM prenotazioni p JOIN saloni s ON s.id = p.salone_id"
            " WHERE p.stato = 'confermata' AND p.cliente_wa != '' AND p.data BETWEEN ? AND ?"
            " AND s.phone_number_id IS NOT NULL", (dal, al))]


def segna(pren_id, campo):
    assert campo in ("promemoria_inviato", "recensione_inviata")
    with con() as c:
        c.execute(f"UPDATE prenotazioni SET {campo} = 1 WHERE id = ?", (pren_id,))


# ------------------------------------------------------------------ messaggi
def gia_processato(msg_id):
    """True se il messaggio era già stato gestito; altrimenti lo registra (WhatsApp può reinviarlo)."""
    with con() as c:
        try:
            c.execute("INSERT INTO processati (msg_id, quando) VALUES (?, ?)", (msg_id, ora_iso()))
            return False
        except sqlite3.IntegrityError:
            return True


def salva_messaggio(salone_id, cliente_wa, ruolo, testo):
    with con() as c:
        return c.execute("INSERT INTO messaggi (salone_id, cliente_wa, ruolo, testo, quando) VALUES (?,?,?,?,?)",
                         (salone_id, cliente_wa, ruolo, testo, ora_iso())).lastrowid


def storia(salone_id, cliente_wa, quanti=16):
    with con() as c:
        righe = c.execute("SELECT ruolo, testo, quando FROM messaggi WHERE salone_id = ? AND cliente_wa = ?"
                          " ORDER BY id DESC LIMIT ?", (salone_id, cliente_wa, quanti)).fetchall()
    return [dict(r) for r in reversed(righe)]


def ultimo_id_cliente(salone_id, cliente_wa):
    with con() as c:
        r = c.execute("SELECT MAX(id) FROM messaggi WHERE salone_id = ? AND cliente_wa = ? AND ruolo = 'cliente'",
                      (salone_id, cliente_wa)).fetchone()[0]
    return r or 0


def conta_prenotazioni_bot(salone_id, dal):
    with con() as c:
        return c.execute("SELECT COUNT(*) FROM prenotazioni WHERE salone_id = ? AND origine = 'bot' AND creata >= ?",
                         (salone_id, dal)).fetchone()[0]


def conta_messaggi(salone_id, dal):
    with con() as c:
        return c.execute("SELECT COUNT(*) FROM messaggi WHERE salone_id = ? AND ruolo = 'cliente' AND quando >= ?",
                         (salone_id, dal)).fetchone()[0]


# ------------------------------------------------------------------ da gestire
def apri_da_gestire(salone_id, cliente_wa, nome_cliente, motivo):
    with con() as c:
        c.execute("INSERT INTO da_gestire (salone_id, cliente_wa, nome_cliente, motivo, quando) VALUES (?,?,?,?,?)",
                  (salone_id, cliente_wa, nome_cliente, motivo, ora_iso()))


def lista_da_gestire(salone_id):
    with con() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM da_gestire WHERE salone_id = ? AND stato = 'aperto' ORDER BY id DESC", (salone_id,))]


def chiudi_da_gestire(salone_id, item_id):
    with con() as c:
        c.execute("UPDATE da_gestire SET stato = 'chiuso' WHERE id = ? AND salone_id = ?", (item_id, salone_id))
