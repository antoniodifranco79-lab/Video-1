#!/usr/bin/env python3
"""BOT 1 - SCRITTORE e BOT 2 - VERIFICATORE.

Lo Scrittore inventa nuovi video (5 curiosità ciascuno) usando Claude.
Il Verificatore ricontrolla ogni fatto con una seconda chiamata indipendente
e scarta i video con anche un solo fatto dubbio. Poi controlli automatici su
lunghezze, colori, doppioni. I video approvati finiscono in contenuti.json.

Uso:  python scrittore.py            (riempie la coda fino a OBIETTIVO_CODA)
      python scrittore.py --quanti 5 (ne scrive esattamente 5, se approvati)
Serve la variabile d'ambiente ANTHROPIC_API_KEY.
"""
import argparse
import re
import sys
from collections import defaultdict

from pydantic import BaseModel

import comune as c

MODELLO = "claude-opus-5-5"
OBIETTIVO_CODA = 14     # video pronti da tenere sempre in coda (2 settimane)
MAX_PER_GIRO = 10

# ------------------------------------------------------------ formati di risposta
class Video(BaseModel):
    id: str
    titolo: str
    intro: str
    colori: list[str]
    tag: list[str]
    fatti: list[str]


class Lotto(BaseModel):
    video: list[Video]


class ControlloFatto(BaseModel):
    numero: int
    corretto: bool
    nota: str


class ControlloVideo(BaseModel):
    id: str
    fatti: list[ControlloFatto]


class Verifica(BaseModel):
    video: list[ControlloVideo]


# ------------------------------------------------------------ prompt
ISTRUZIONI_SCRITTORE = """Scrivi i testi per un canale YouTube Shorts italiano chiamato "Curiosità al Minuto".
Ogni video presenta 5 curiosità su un unico argomento, lette da una voce sintetica.

Regole per ogni video:
- id: breve, minuscolo, parole separate da trattini, senza accenti (es. "vulcani", "antico-egitto").
- titolo: massimo 60 caratteri, accattivante, con la parola chiave in MAIUSCOLO (es. "5 segreti dei VULCANI che non conosci").
- intro: una frase da leggere ad alta voce che riprende il titolo, senza maiuscole enfatiche (es. "Cinque segreti dei vulcani che non conosci.").
- colori: due colori esadecimali #RRGGBB scuri o saturi adatti all'argomento; il testo sopra è bianco, quindi niente colori chiari.
- tag: 5 parole chiave in minuscolo; il primo tag è la categoria generale (es. "animali", "spazio", "storia", "corpo umano", "cibo", "natura", "tecnologia", "geografia").
- fatti: esattamente 5 frasi, ognuna di massimo 25 parole, scritte per essere ascoltate.

Regole sui fatti, le più importanti:
- Solo fatti veri, ben documentati e verificabili su fonti affidabili. Se hai il minimo dubbio, scegli un altro fatto.
- Niente leggende popolari presentate come vere, niente miti sfatati, niente numeri inventati o troppo precisi.
- Se un dato è una stima, dillo ("circa", "si stima").
- Niente politica, religione, consigli medici, persone viventi, tragedie recenti o argomenti per adulti.
- Contenuti adatti a tutti e scritti in un italiano corretto e naturale.
- Ogni video deve essere originale: non ripetere argomenti già usati."""

ISTRUZIONI_VERIFICATORE = """Sei un fact-checker severo. Controlli i testi di un canale di curiosità prima della pubblicazione.
Per ogni fatto decidi se è corretto così com'è scritto: vero, non fuorviante, non esagerato, con numeri giusti.
Segna corretto=false se il fatto è falso, dubbio, controverso, una leggenda, oppure se i numeri sono imprecisi
o presentati come certi quando sono stime. Nel dubbio, segna false. Nella nota spiega in breve il motivo."""


# ------------------------------------------------------------ controlli automatici
RE_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
RE_COLORE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def luminanza(hex_colore):
    r, g, b = (int(hex_colore[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lin = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def problemi_formali(v, id_usati, titoli_usati):
    """Restituisce l'elenco dei problemi (vuoto = va bene)."""
    p = []
    if not RE_ID.match(v.id) or len(v.id) > 40:
        p.append("id non valido")
    if v.id in id_usati:
        p.append("id già usato")
    if not v.titolo.strip() or len(v.titolo) > 70:
        p.append("titolo vuoto o troppo lungo")
    if v.titolo.strip().lower() in titoli_usati:
        p.append("titolo già usato")
    if not v.intro.strip() or len(v.intro) > 140:
        p.append("intro vuota o troppo lunga")
    if len(v.colori) != 2 or not all(RE_COLORE.match(x) for x in v.colori):
        p.append("colori non validi")
    elif max(luminanza(x) for x in v.colori) > 0.5:
        p.append("colori troppo chiari per il testo bianco")
    if not 3 <= len(v.tag) <= 8 or any(not t.strip() or len(t) > 30 for t in v.tag):
        p.append("tag non validi")
    if len(v.fatti) != 5:
        p.append("servono esattamente 5 fatti")
    for i, f in enumerate(v.fatti, 1):
        if len(f.strip()) < 20 or len(f.split()) > 30 or len(f) > 190:
            p.append(f"fatto {i} troppo corto o troppo lungo")
    return p


# ------------------------------------------------------------ chiamate a Claude
def chiedi(client, istruzioni, testo, formato, effort):
    risposta = client.beta.messages.parse(
        model=MODELLO,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": effort},
        system=istruzioni,
        messages=[{"role": "user", "content": testo}],
        output_format=formato,
    )
    if risposta.stop_reason == "refusal":
        c.avviso("Claude ha rifiutato la richiesta: riprovo al prossimo giro.")
        return None
    if risposta.stop_reason == "max_tokens" or risposta.parsed_output is None:
        c.avviso(f"Risposta incompleta da Claude ({risposta.stop_reason}).")
        return None
    return risposta.parsed_output


def preferenze(statistiche, pubblicati):
    """Media delle visualizzazioni per categoria, dalla migliore alla peggiore."""
    per_cat = defaultdict(list)
    for vid, info in pubblicati.items():
        s = statistiche.get("video", {}).get(vid)
        if s:
            per_cat[info.get("categoria", "altro")].append(s.get("visualizzazioni", 0))
    medie = {k: sum(v) / len(v) for k, v in per_cat.items()}
    return sorted(medie.items(), key=lambda x: -x[1])


def scrivi_video(client, quanti, contenuti, pubblicati, statistiche):
    gia = [f"- {v['id']}: {v['titolo']}" for v in contenuti["video"]]
    classifica = preferenze(statistiche, pubblicati)
    suggerimento = ""
    if len(classifica) >= 2:
        migliori = ", ".join(k for k, _ in classifica[:3])
        peggiori = ", ".join(k for k, _ in classifica[-2:])
        suggerimento = (f"\nI dati del canale dicono che le categorie più viste sono: {migliori}. "
                        f"Quelle meno viste: {peggiori}. Scrivi più video nelle categorie più viste, "
                        "ma tieni un po' di varietà.")
    richiesta = (f"Scrivi {quanti} nuovi video, tutti su argomenti diversi tra loro.{suggerimento}\n\n"
                 "Argomenti già usati (non ripeterli e non fare varianti troppo simili):\n" + "\n".join(gia))
    lotto = chiedi(client, ISTRUZIONI_SCRITTORE, richiesta, Lotto, "medium")
    return lotto.video if lotto else []


def verifica(client, candidati):
    testo = "\n\n".join(
        f"VIDEO id={v.id} - {v.titolo}\n" + "\n".join(f"{i}. {f}" for i, f in enumerate(v.fatti, 1))
        for v in candidati)
    esito = chiedi(client, ISTRUZIONI_VERIFICATORE, "Controlla questi fatti:\n\n" + testo, Verifica, "high")
    if esito is None:
        return set()
    approvati = set()
    for cv in esito.video:
        if len(cv.fatti) == 5 and all(f.corretto for f in cv.fatti):
            approvati.add(cv.id)
        else:
            dubbi = "; ".join(f"{f.numero}: {f.nota}" for f in cv.fatti if not f.corretto)
            print(f"  Scartato '{cv.id}' dal Verificatore: {dubbi or 'controllo incompleto'}")
    return approvati


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quanti", type=int, help="quanti video scrivere (default: riempie la coda)")
    a = ap.parse_args()

    contenuti = c.leggi(c.CONTENUTI, {"video": []})
    pubblicati = c.leggi(c.PUBBLICATI, {})
    statistiche = c.leggi(c.STATISTICHE, {})
    in_coda = len(c.da_pubblicare(contenuti, pubblicati))
    quanti = a.quanti if a.quanti else min(MAX_PER_GIRO, OBIETTIVO_CODA - in_coda)
    print(f"Video in coda: {in_coda}. Da scrivere: {max(quanti, 0)}.")
    if quanti <= 0:
        return

    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        c.avviso("Manca il Secret ANTHROPIC_API_KEY: lo Scrittore non può scrivere nuovi video.")
        sys.exit(1)
    import anthropic
    client = anthropic.Anthropic()  # legge ANTHROPIC_API_KEY

    id_usati = {v["id"] for v in contenuti["video"]}
    titoli_usati = {v["titolo"].strip().lower() for v in contenuti["video"]}
    candidati = []
    for v in scrivi_video(client, quanti, contenuti, pubblicati, statistiche):
        prob = problemi_formali(v, id_usati, titoli_usati)
        if prob:
            print(f"  Scartato '{v.id}': {', '.join(prob)}")
            continue
        id_usati.add(v.id)
        titoli_usati.add(v.titolo.strip().lower())
        candidati.append(v)
    if not candidati:
        c.avviso("Nessun video nuovo approvato in questo giro.")
        return

    approvati_id = verifica(client, candidati)
    nuovi = [v for v in candidati if v.id in approvati_id]
    for v in nuovi:
        contenuti["video"].append({
            "id": v.id, "titolo": v.titolo.strip(), "intro": v.intro.strip(),
            "colori": [x.upper() for x in v.colori], "tag": [t.strip().lower() for t in v.tag],
            "fatti": [f.strip() for f in v.fatti],
        })
        print(f"  Approvato: {v.id} - {v.titolo}")
    c.scrivi(c.CONTENUTI, contenuti)
    print(f"Aggiunti {len(nuovi)} video. Ora in coda: {in_coda + len(nuovi)}.")
    if in_coda + len(nuovi) < 3:
        c.avviso("La coda è quasi vuota: controlla la chiave ANTHROPIC_API_KEY e il credito.")
        sys.exit(1)


if __name__ == "__main__":
    main()
