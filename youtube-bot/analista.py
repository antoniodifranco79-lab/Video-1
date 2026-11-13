#!/usr/bin/env python3
"""BOT 5 - ANALISTA: legge da YouTube visualizzazioni, like, commenti e iscritti.

Salva tutto in statistiche.json, che lo Scrittore usa per scegliere gli
argomenti e il Segretario per il riepilogo settimanale.
"""
import datetime as dt

import comune as c


def main():
    pubblicati = c.leggi(c.PUBBLICATI, {})
    stat = c.leggi(c.STATISTICHE, {})
    if not pubblicati:
        print("Nessun video pubblicato ancora: niente da analizzare.")
        return

    from googleapiclient.errors import HttpError
    yt = c.youtube()
    per_youtube_id = {info["youtube_id"]: vid for vid, info in pubblicati.items() if info.get("youtube_id")}
    risultati = {}
    try:
        ids = list(per_youtube_id)
        for i in range(0, len(ids), 50):
            r = yt.videos().list(part="statistics,status", id=",".join(ids[i:i + 50])).execute()
            for item in r.get("items", []):
                s = item.get("statistics", {})
                risultati[per_youtube_id[item["id"]]] = {
                    "youtube_id": item["id"],
                    "visualizzazioni": int(s.get("viewCount", 0)),
                    "mi_piace": int(s.get("likeCount", 0)),
                    "commenti": int(s.get("commentCount", 0)),
                    "visibilita": item.get("status", {}).get("privacyStatus"),
                }
        canale = yt.channels().list(part="statistics", mine=True).execute().get("items", [])
        iscritti = int(canale[0]["statistics"].get("subscriberCount", 0)) if canale else None
    except HttpError as e:
        if e.resp.status in (401, 403):
            c.avviso("L'Analista non ha il permesso di leggere le statistiche: rifai il Passo 4 di "
                     "LEGGIMI.md includendo anche lo scope youtube.readonly.")
            return
        raise

    mancanti = set(pubblicati) - set(risultati)
    for vid in mancanti:
        print(f"  Video '{vid}' non trovato su YouTube (eliminato?).")

    oggi = dt.date.today().isoformat()
    totale = sum(x["visualizzazioni"] for x in risultati.values())
    storico = [s for s in stat.get("storico", []) if s.get("data") != oggi]
    storico.append({"data": oggi, "visualizzazioni_totali": totale, "iscritti": iscritti})
    c.scrivi(c.STATISTICHE, {"aggiornato": oggi, "iscritti": iscritti, "video": risultati,
                             "storico": storico[-104:]})
    print(f"Statistiche aggiornate: {len(risultati)} video, {totale} visualizzazioni, "
          f"{iscritti if iscritti is not None else '?'} iscritti.")


if __name__ == "__main__":
    main()
