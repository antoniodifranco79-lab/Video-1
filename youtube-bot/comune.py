"""Funzioni e percorsi condivisi da tutti i bot."""
import json
import os
import sys
from pathlib import Path

QUI = Path(__file__).resolve().parent
CONTENUTI = QUI / "contenuti.json"        # testi dei video (Scrittore)
PUBBLICATI = QUI / "pubblicati.json"      # video già su YouTube (Pubblicatore)
STATISTICHE = QUI / "statistiche.json"    # visualizzazioni ecc. (Analista)


def leggi(percorso, default):
    try:
        return json.loads(Path(percorso).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def scrivi(percorso, dati):
    tmp = Path(str(percorso) + ".tmp")
    tmp.write_text(json.dumps(dati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(percorso)


def avviso(testo):
    """Messaggio evidenziato nel riepilogo di GitHub Actions."""
    print(f"::warning::{testo}", flush=True)


def da_pubblicare(contenuti, pubblicati):
    return [v for v in contenuti["video"] if v["id"] not in pubblicati]


def youtube():
    """Client YouTube autenticato con il refresh token salvato nei Secrets."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    chiavi = ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")
    mancano = [k for k in chiavi if not os.environ.get(k)]
    if mancano:
        sys.exit("Mancano i Secrets su GitHub: " + ", ".join(mancano))
    cred = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
    )
    return build("youtube", "v3", credentials=cred, cache_discovery=False)
