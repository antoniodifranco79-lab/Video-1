#!/usr/bin/env python3
"""Genera video verticali (YouTube Shorts / TikTok / Reels) da contenuti.json.

Uso:
    python genera_video.py --id squali      # un video
    python genera_video.py --tutti          # tutti i video non ancora creati
    python genera_video.py --prossimo       # solo il primo video non ancora creato
"""
import argparse
import json
import math
import subprocess
import sys
import tempfile
import wave
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

QUI = Path(__file__).resolve().parent
VOCE = QUI / "voices" / "it_IT-paola-medium.onnx"
FONT = QUI / "font" / "Montserrat.ttf"
USCITA = QUI / "uscita"

W, H, FPS = 1080, 1920, 30
SR = 22050                 # frequenza della voce Piper
PAUSA = 0.45               # secondi di silenzio dopo ogni frase
VELOCITA_VOCE = 0.9        # <1 = parla più veloce
GIALLO = (255, 212, 0)
BIANCO = (255, 255, 255)


# ---------------------------------------------------------------- utilità
def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def font(size, peso="ExtraBold"):
    f = ImageFont.truetype(str(FONT), size)
    f.set_variation_by_name(peso)
    return f


# ---------------------------------------------------------------- audio
def sintetizza(testo, dest):
    subprocess.run(
        [sys.executable, "-m", "piper", "-m", str(VOCE), "-f", str(dest),
         "--length-scale", str(VELOCITA_VOCE)],
        input=testo.encode("utf-8"), check=True, capture_output=True)
    with wave.open(str(dest)) as w:
        if w.getframerate() != SR or w.getnchannels() != 1:
            raise RuntimeError(f"Voce con formato inatteso: {w.getframerate()} Hz, {w.getnchannels()} canali")
        dati = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return dati.astype(np.float32) / 32768.0


def musica(durata):
    """Sottofondo ambient sintetizzato (nessun problema di copyright)."""
    t = np.arange(int(durata * SR)) / SR
    accordi = [[220.0, 277.18, 329.63], [196.0, 246.94, 293.66],
               [174.61, 220.0, 261.63], [196.0, 246.94, 329.63]]
    durata_accordo = 4.0
    out = np.zeros_like(t)
    for i, acc in enumerate(accordi * int(durata // (durata_accordo * 4) + 1)):
        inizio = i * durata_accordo
        if inizio > durata:
            break
        m = (t >= inizio - 1) & (t < inizio + durata_accordo + 1)
        tt = t[m] - inizio
        inv = np.clip(np.minimum(tt + 1, durata_accordo + 1 - tt), 0, 1)  # dissolvenza
        for f in acc:
            out[m] += inv * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2 * tt))
    out *= 0.5 + 0.5 * np.sin(2 * np.pi * 0.1 * t)  # respiro lento
    out /= np.max(np.abs(out)) + 1e-9
    fade = np.clip(np.minimum(t, durata - t) / 1.5, 0, 1)
    return out * fade * 0.06


# ---------------------------------------------------------------- grafica
def sfondo(c1, c2, seed):
    """Sfondo alto il doppio dello schermo, scorre in loop verticale."""
    rng = np.random.default_rng(seed)
    hh = H * 2
    y = np.linspace(0, 4 * np.pi, hh, endpoint=False)[:, None]  # periodo = H, loop senza salti
    k = (0.5 - 0.5 * np.cos(y))  # c1 -> c2 -> c1, periodico
    a, b = np.array(c1, np.float32), np.array(c2, np.float32)
    img = (a * (1 - k) + b * k)[:, None, :].repeat(W, axis=1)
    base = Image.fromarray(img.astype(np.uint8))
    # bolle sfumate
    bolle = Image.new("RGBA", (W, hh), (0, 0, 0, 0))
    d = ImageDraw.Draw(bolle)
    for _ in range(14):
        r = int(rng.uniform(90, 260))
        x, yy = rng.uniform(0, W), rng.uniform(0, H)
        alpha = int(rng.uniform(25, 60))
        for off in (0, H):  # ripetute per il loop
            d.ellipse([x - r, yy + off - r, x + r, yy + off + r], fill=(255, 255, 255, alpha))
    bolle = bolle.filter(ImageFilter.GaussianBlur(40))
    base.paste(bolle, (0, 0), bolle)
    # leggera vignettatura
    arr = np.asarray(base).astype(np.float32)
    xs = np.linspace(-1, 1, W)[None, :]
    vign = 1 - 0.35 * np.clip(np.abs(xs) ** 2, 0, 1)
    return (arr * vign[..., None]).astype(np.uint8)


def dividi_righe(parole, f, larghezza):
    righe, cur = [], []
    for i, p in enumerate(parole):
        prova = " ".join(parole[j] for j in cur + [i])
        if cur and f.getlength(prova) > larghezza:
            righe.append(cur)
            cur = [i]
        else:
            cur.append(i)
    if cur:
        righe.append(cur)
    return righe


def strato_testo(testo, evidenzia, dim, etichetta=None):
    """Immagine RGBA con il testo centrato; la parola `evidenzia` è gialla."""
    parole = testo.split()
    for size in range(dim, 40, -4):
        f = font(size)
        righe = dividi_righe(parole, f, W - 160)
        if len(righe) <= 7:
            break
    interl = int(size * 1.22)
    alt_testo = interl * len(righe)
    spazio_etichetta = 170 if etichetta else 0
    img = Image.new("RGBA", (W, alt_testo + spazio_etichetta + 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if etichetta:
        fe = font(70, "Black")
        r = 72
        cx, cy = W // 2, r + 10
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GIALLO + (255,))
        d.text((cx, cy), etichetta, font=fe, fill=(20, 20, 20), anchor="mm")
    spazio = f.getlength(" ")
    y = spazio_etichetta + 20
    for riga in righe:
        lw = sum(f.getlength(parole[i]) for i in riga) + spazio * (len(riga) - 1)
        x = (W - lw) / 2
        for i in riga:
            col = GIALLO if i == evidenzia else BIANCO
            d.text((x, y), parole[i], font=f, fill=col,
                   stroke_width=max(6, size // 10), stroke_fill=(0, 0, 0))
            x += f.getlength(parole[i]) + spazio
        y += interl
    # ombra morbida per staccare dallo sfondo
    ombra = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ombra.putalpha(img.getchannel("A").point(lambda v: v * 0.5).filter(ImageFilter.GaussianBlur(14)))
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.alpha_composite(ombra, (0, 8))
    out.alpha_composite(img)
    return out


def intestazione(testo):
    f = font(46, "Black")
    img = Image.new("RGBA", (W, 120), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lw = f.getlength(testo)
    d.rounded_rectangle([(W - lw) / 2 - 36, 20, (W + lw) / 2 + 36, 100], radius=40,
                        fill=(0, 0, 0, 150))
    d.text((W / 2, 60), testo, font=f, fill=BIANCO, anchor="mm")
    return img


class Strato:
    """Strato RGBA pre-calcolato per una fusione veloce con numpy."""

    def __init__(self, img):
        a = np.asarray(img).astype(np.uint16)
        self.rgb = a[..., :3]
        self.a = a[..., 3:4]
        self.h, self.w = a.shape[:2]

    def disegna(self, frame, x, y, opac=1.0):
        h = min(self.h, H - y)
        if h <= 0:
            return
        a = self.a[:h] if opac >= 1 else (self.a[:h] * opac).astype(np.uint16)
        reg = frame[y:y + h, x:x + self.w].astype(np.uint16)
        frame[y:y + h, x:x + self.w] = ((self.rgb[:h] * a + reg * (255 - a)) // 255).astype(np.uint8)


# ---------------------------------------------------------------- video
def tempi_parole(testo, durata):
    """Stima quando viene detta ogni parola (proporzionale alla lunghezza)."""
    parole = testo.split()
    pesi = np.array([len(p) + 2 for p in parole], np.float32)
    fine = np.cumsum(pesi) / pesi.sum() * durata
    return np.concatenate([[0], fine[:-1]])


def crea_video(v, cfg, dest):
    c1, c2 = hex_rgb(v["colori"][0]), hex_rgb(v["colori"][1])
    segmenti = [{"testo": v["titolo"], "voce": v["intro"], "tipo": "intro"}]
    for i, f in enumerate(v["fatti"], 1):
        segmenti.append({"testo": f, "voce": f, "tipo": "fatto", "n": i})
    segmenti.append({"testo": cfg["chiusura"], "voce": cfg["chiusura"], "tipo": "fine"})

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # 1) voce
        audio, t = [], 0.0
        for i, s in enumerate(segmenti):
            a = sintetizza(s["voce"], tmp / f"s{i}.wav")
            s["inizio"], s["durata_voce"] = t, len(a) / SR
            audio += [a, np.zeros(int(PAUSA * SR), np.float32)]
            t += len(a) / SR + PAUSA
            s["fine"] = t
        voce = np.concatenate(audio)
        durata = len(voce) / SR
        mix = voce * 0.95 + musica(durata)
        mix = np.clip(mix, -1, 1)
        with wave.open(str(tmp / "audio.wav"), "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(SR)
            w.writeframes((mix * 32767).astype(np.int16).tobytes())

        # 2) immagini
        bg = sfondo(c1, c2, zlib.crc32(v["id"].encode()))
        testata = Strato(intestazione(cfg["canale"].upper()))
        n_frame = int(math.ceil(durata * FPS))
        cmd = ["ffmpeg", "-y", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
               "-i", str(tmp / "audio.wav"),
               "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(dest)]
        ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)

        cache = {}
        for fr in range(n_frame):
            t = fr / FPS
            seg = next((s for s in segmenti if t < s["fine"]), segmenti[-1])
            off = int(t * 60) % H
            frame = bg[off:off + H].copy()
            testata.disegna(frame, 0, 150)

            # parola evidenziata
            locale = t - seg["inizio"]
            tp = tempi_parole(seg["testo"], seg["durata_voce"])
            idx = int(np.searchsorted(tp, locale, side="right") - 1)
            if locale > seg["durata_voce"]:
                idx = -1
            dim = {"intro": 104, "fatto": 82, "fine": 72}[seg["tipo"]]
            etich = f"#{seg['n']}" if seg["tipo"] == "fatto" else None
            chiave = (id(seg), idx)
            if chiave not in cache:
                cache.clear() if len(cache) > 60 else None
                im = strato_testo(seg["testo"], idx, dim, etich)
                cache[chiave] = (im, Strato(im))
            img, st = cache[chiave]

            # animazione di entrata (zoom + dissolvenza)
            p = min(1.0, locale / 0.25)
            ease = 1 - (1 - p) ** 3
            scala = 0.82 + 0.18 * ease
            if scala < 0.999:
                st = Strato(img.resize((int(img.width * scala), int(img.height * scala)), Image.BILINEAR))
            y = int(H * 0.47 - st.h / 2)
            st.disegna(frame, (W - st.w) // 2, max(300, y), ease)

            # barra di avanzamento
            prog = int(W * t / durata)
            frame[H - 360:H - 348, :] = (frame[H - 360:H - 348, :] * 0.5).astype(np.uint8)
            frame[H - 360:H - 348, :prog] = GIALLO

            ff.stdin.write(frame.tobytes())
        ff.stdin.close()
        if ff.wait() != 0:
            raise RuntimeError("ffmpeg non è riuscito a creare il video")
    return durata


def scrivi_dati(v, cfg, dest):
    hashtag = " ".join("#" + t.replace(" ", "") for t in v["tag"])
    descr = (f"{v['intro']}\n\n"
             + "\n".join(f"{i}. {f}" for i, f in enumerate(v["fatti"], 1))
             + f"\n\nIscriviti a {cfg['canale']} per una curiosità al giorno!\n\n{hashtag} #shorts")
    dati = {"titolo": f"{v['titolo']} #shorts"[:100], "descrizione": descr,
            "tag": list(dict.fromkeys(v["tag"] + ["shorts", "curiosità"])), "file": f"{v['id']}.mp4"}
    dest.write_text(json.dumps(dati, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--id")
    g.add_argument("--tutti", action="store_true")
    g.add_argument("--prossimo", action="store_true")
    args = ap.parse_args()

    cfg = json.loads((QUI / "contenuti.json").read_text(encoding="utf-8"))
    USCITA.mkdir(exist_ok=True)
    da_fare = [v for v in cfg["video"] if not (USCITA / f"{v['id']}.mp4").exists()]
    if args.id:
        da_fare = [v for v in cfg["video"] if v["id"] == args.id]
        if not da_fare:
            sys.exit(f"Nessun video con id '{args.id}'")
    elif args.prossimo:
        da_fare = da_fare[:1]
    if not da_fare:
        print("Tutti i video sono già stati creati. Aggiungi nuovi testi in contenuti.json.")
        return
    for v in da_fare:
        dest = USCITA / f"{v['id']}.mp4"
        print(f"Creo {dest.name} ...", flush=True)
        durata = crea_video(v, cfg, dest)
        scrivi_dati(v, cfg, USCITA / f"{v['id']}.json")
        print(f"  fatto: {durata:.1f} secondi", flush=True)


if __name__ == "__main__":
    main()
