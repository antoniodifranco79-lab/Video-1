#!/usr/bin/env python3
"""BOT 6 - SEGRETARIO: scrive il riepilogo settimanale in report.md.

GitHub Actions lo pubblica come "Issue" nel repository: GitHub ti avvisa
via email, così lo leggi senza aprire nulla.
"""
import datetime as dt
from collections import defaultdict

import comune as c

REPORT = c.QUI / "report.md"
SOGLIA_ISCRITTI = 1000


def numero(n):
    return f"{n:,}".replace(",", ".") if isinstance(n, int) else "?"


def componi(contenuti, pubblicati, stat):
    righe = [f"# Riepilogo settimanale - {dt.date.today():%d/%m/%Y}", ""]
    video = stat.get("video", {})
    storico = stat.get("storico", [])
    iscritti = stat.get("iscritti")
    totale = sum(v.get("visualizzazioni", 0) for v in video.values())
    coda = len(c.da_pubblicare(contenuti, pubblicati))

    crescita = ""
    if len(storico) >= 2:
        diff = storico[-1].get("visualizzazioni_totali", 0) - storico[-2].get("visualizzazioni_totali", 0)
        crescita = f" ({'+' if diff >= 0 else ''}{numero(diff)} rispetto alla volta scorsa)"

    righe += ["## Numeri", "",
              "| | |", "|---|---|",
              f"| Video pubblicati | {len(pubblicati)} |",
              f"| Visualizzazioni totali | {numero(totale)}{crescita} |",
              f"| Iscritti | {numero(iscritti)} |",
              f"| Video pronti in coda | {coda} |", ""]
    if isinstance(iscritti, int):
        perc = min(100, iscritti * 100 // SOGLIA_ISCRITTI)
        righe += [f"Strada verso il guadagno: **{perc}%** dei {SOGLIA_ISCRITTI} iscritti richiesti da YouTube.", ""]

    if video:
        top = sorted(video.items(), key=lambda x: -x[1].get("visualizzazioni", 0))[:3]
        righe += ["## I 3 video più visti", ""]
        for vid, s in top:
            righe.append(f"- [{vid}](https://youtube.com/shorts/{s['youtube_id']}): "
                         f"{numero(s.get('visualizzazioni'))} visualizzazioni, {numero(s.get('mi_piace'))} mi piace")
        righe.append("")
        per_cat = defaultdict(list)
        for vid, info in pubblicati.items():
            if vid in video:
                per_cat[info.get("categoria", "altro")].append(video[vid].get("visualizzazioni", 0))
        if per_cat:
            righe += ["## Categorie (media visualizzazioni)", ""]
            for cat, vals in sorted(per_cat.items(), key=lambda x: -sum(x[1]) / len(x[1])):
                righe.append(f"- {cat}: {numero(sum(vals) // len(vals))}")
            righe.append("")

    problemi = []
    privati = [vid for vid, s in video.items() if s.get("visibilita") == "private"]
    privati += [vid for vid, info in pubblicati.items()
                if vid not in video and info.get("visibilita") == "private"]
    if privati:
        problemi.append(f"{len(privati)} video sono **privati**: Google non ha ancora approvato l'app. "
                        "Rendili pubblici da YouTube Studio oppure completa il Passo 6 di LEGGIMI.md.")
    if coda < 3:
        problemi.append("La coda dei testi è quasi vuota: controlla che lo Scrittore funzioni "
                        "(chiave ANTHROPIC_API_KEY e credito).")
    if not stat:
        problemi.append("Nessuna statistica disponibile: l'Analista non ha ancora letto i dati da YouTube.")
    righe += ["## Cosa devi fare", ""]
    righe += [f"- ⚠️ {p}" for p in problemi] if problemi else ["- Niente: va tutto bene. ✅"]
    righe += ["", "_Scritto in automatico dal bot Segretario._"]
    return "\n".join(righe) + "\n"


def main():
    testo = componi(c.leggi(c.CONTENUTI, {"video": []}), c.leggi(c.PUBBLICATI, {}),
                    c.leggi(c.STATISTICHE, {}))
    REPORT.write_text(testo, encoding="utf-8")
    print(testo)


if __name__ == "__main__":
    main()
