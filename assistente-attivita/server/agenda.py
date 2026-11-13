"""Regole dell'agenda: orari di apertura, posti liberi, controlli sulle prenotazioni."""
import re
from datetime import date, datetime, timedelta

GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
        "settembre", "ottobre", "novembre", "dicembre"]
PASSO = 15          # minuti tra un orario proposto e l'altro
ANTICIPO_MIN = 60   # non si prenota per meno di un'ora da adesso
GIORNI_MAX = 60     # non si prenota oltre due mesi

RE_ORA = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def minuti(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def hhmm(n):
    return f"{n // 60:02d}:{n % 60:02d}"


def nome_giorno(d):
    return f"{GIORNI[d.weekday()]} {d.day} {MESI[d.month - 1]}"


def turni(orari, d):
    """Fasce di apertura di un giorno, in minuti: [(inizio, fine), ...]."""
    return [(minuti(a), minuti(b)) for a, b in orari.get(str(d.weekday()), [])]


def testo_orari(orari):
    righe = []
    for g, nome in enumerate(GIORNI):
        fasce = orari.get(str(g), [])
        righe.append(f"{nome.capitalize()}: " + (", ".join(f"{a}-{b}" for a, b in fasce) if fasce else "chiuso"))
    return "\n".join(righe)


def leggi_orari_testo(testo_per_giorno):
    """Da {"0": "09:00-13:00, 15:00-19:00" | "chiuso"} al formato interno. Solleva ValueError se non valido."""
    orari = {}
    for g in range(7):
        t = (testo_per_giorno.get(str(g)) or "").strip().lower()
        fasce = []
        if t and t != "chiuso":
            for parte in t.split(","):
                pezzi = [x.strip().replace(".", ":") for x in parte.split("-")]
                if len(pezzi) != 2 or not all(RE_ORA.match(x) for x in pezzi):
                    raise ValueError(f"{GIORNI[g].capitalize()}: scrivi gli orari così: 09:00-13:00, 15:00-19:00")
                a, b = (hhmm(minuti(x)) for x in pezzi)
                if minuti(b) <= minuti(a):
                    raise ValueError(f"{GIORNI[g].capitalize()}: l'orario di chiusura deve venire dopo l'apertura")
                fasce.append([a, b])
            fasce.sort()
            for (_, fine), (inizio, _) in zip(fasce, fasce[1:]):
                if minuti(inizio) < minuti(fine):
                    raise ValueError(f"{GIORNI[g].capitalize()}: le fasce orarie si sovrappongono")
        orari[str(g)] = fasce
    return orari


def _sovrapposti(inizio, durata, prenotazioni):
    fine = inizio + durata
    return sum(1 for p in prenotazioni if inizio < minuti(p["ora"]) + p["minuti"] and minuti(p["ora"]) < fine)


def problema(salone, d, ora, durata, prenotazioni, adesso):
    """None se la prenotazione va bene, altrimenti il motivo (in italiano, da girare al cliente)."""
    if not RE_ORA.match(ora or ""):
        return "orario non valido: usa il formato HH:MM"
    inizio = minuti(ora)
    quando = datetime(d.year, d.month, d.day, inizio // 60, inizio % 60, tzinfo=adesso.tzinfo)
    if quando < adesso + timedelta(minutes=ANTICIPO_MIN):
        return "l'orario è già passato o è troppo vicino: serve almeno un'ora di anticipo"
    if d > adesso.date() + timedelta(days=GIORNI_MAX):
        return f"si può prenotare al massimo {GIORNI_MAX} giorni in anticipo"
    fasce = turni(salone["orari"], d)
    if not fasce:
        return f"{nome_giorno(d)} il salone è chiuso"
    if not any(a <= inizio and inizio + durata <= b for a, b in fasce):
        return "l'appuntamento deve iniziare e finire dentro l'orario di apertura (" + \
               ", ".join(f"{hhmm(a)}-{hhmm(b)}" for a, b in fasce) + ")"
    if _sovrapposti(inizio, durata, prenotazioni) >= max(1, int(salone["posti"])):
        return "a quell'ora non c'è posto"
    return None


def orari_liberi(salone, d, durata, prenotazioni, adesso):
    out = []
    for a, b in turni(salone["orari"], d):
        t = a
        while t + durata <= b:
            if problema(salone, d, hhmm(t), durata, prenotazioni, adesso) is None:
                out.append(hhmm(t))
            t += PASSO
    return out


def trova_servizio(salone, nome):
    n = (nome or "").strip().lower()
    for s in salone["servizi"]:
        if s["nome"].lower() == n:
            return s
    candidati = [s for s in salone["servizi"] if n and (n in s["nome"].lower() or s["nome"].lower() in n)]
    return candidati[0] if len(candidati) == 1 else None


def data_valida(testo):
    try:
        return date.fromisoformat(testo)
    except (TypeError, ValueError):
        return None
