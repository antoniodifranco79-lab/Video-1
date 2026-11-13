#!/usr/bin/env python3
"""BOT 4 - PUBBLICATORE: crea il prossimo video e lo carica su YouTube.

Gira ogni giorno (GitHub Actions). Tiene traccia dei video in pubblicati.json.
"""
import datetime as dt
import json
import os
import sys

import comune as c
import genera_video as gv


def main():
    contenuti = c.leggi(c.CONTENUTI, {"video": []})
    pubblicati = c.leggi(c.PUBBLICATI, {})
    coda = c.da_pubblicare(contenuti, pubblicati)
    if not coda:
        sys.exit("Nessun testo da pubblicare: lo Scrittore deve prepararne di nuovi.")
    v = coda[0]
    yt = c.youtube()  # controlla le credenziali prima di creare il video

    gv.USCITA.mkdir(exist_ok=True)
    mp4, meta_file = gv.USCITA / f"{v['id']}.mp4", gv.USCITA / f"{v['id']}.json"
    print(f"Creo {mp4.name} ...", flush=True)
    gv.crea_video(v, contenuti, mp4)
    gv.scrivi_dati(v, contenuti, meta_file)
    meta = json.loads(meta_file.read_text(encoding="utf-8"))

    from googleapiclient.http import MediaFileUpload
    corpo = {
        "snippet": {"title": meta["titolo"], "description": meta["descrizione"], "tags": meta["tag"],
                    "categoryId": "27", "defaultLanguage": "it", "defaultAudioLanguage": "it"},
        "status": {"privacyStatus": os.environ.get("YT_VISIBILITA") or "public",
                   "selfDeclaredMadeForKids": False},
    }
    print("Carico su YouTube ...", flush=True)
    req = yt.videos().insert(part="snippet,status", body=corpo,
                             media_body=MediaFileUpload(str(mp4), mimetype="video/mp4", resumable=True))
    risposta = None
    while risposta is None:
        _, risposta = req.next_chunk()

    visibilita = risposta.get("status", {}).get("privacyStatus")
    pubblicati[v["id"]] = {"youtube_id": risposta["id"], "data": dt.date.today().isoformat(),
                           "visibilita": visibilita, "categoria": v["tag"][0]}
    c.scrivi(c.PUBBLICATI, pubblicati)
    print(f"Pubblicato: https://youtube.com/shorts/{risposta['id']} (visibilità: {visibilita})")
    if visibilita != corpo["status"]["privacyStatus"]:
        c.avviso(f"YouTube ha impostato il video come '{visibilita}': probabilmente Google non ha "
                 "ancora approvato l'app (vedi LEGGIMI.md, Passo 6).")
    print(f"Testi ancora in coda: {len(coda) - 1}")


if __name__ == "__main__":
    main()
