# What If · serie 3D verticale

| Episodio | Video | Sorgenti |
|---|---|---|
| E se la Luna cadesse sulla Terra? | [`output/what_if_luna.mp4`](output/what_if_luna.mp4) | `src/` |
| E se il Sole si spegnesse? | [`output/what_if_sole.mp4`](output/what_if_sole.mp4) | `src/sole/` |

Ogni episodio ha la stessa pipeline: `script.json` (testo), `build_timeline.py` (voce Piper + tempi parola per parola), `scene.html` (scena Three.js), `music.py` (colonna sonora e mix), `src/render.mjs` (rendering fotogramma per fotogramma).

## Episodio "Il Sole"

Tre mondi 3D nello stesso video: lo spazio (Sole con granulazione e corona, fronte dell'ultima luce che impiega 8 minuti e 20 secondi, pozzo gravitazionale, ghiaccio che avanza dai poli, spaccato della Terra con nucleo e oceano liquido), un paesaggio a livello del suolo (giorno che diventa buio istantaneo, alberi che muoiono, lago che gela, alba finale) e un diorama di una colonia sotterranea con geotermia, reattore e serre.

```bash
cd src/sole && python3 build_timeline.py && python3 music.py && cd ../..
SCENE=src/sole/scene.html OUT=frames_sole node src/render.mjs full 0 1656 1
ffmpeg -framerate 30 -i frames_sole/f%05d.jpg -i src/sole/audio.wav -c:v libx264 -preset slow -crf 21 -pix_fmt yuv420p \
  -movflags +faststart -c:a aac -b:a 192k -shortest output/what_if_sole.mp4
```

## Episodio "La Luna"


Video verticale 9:16 (1080×1920, 30 fps, ~58 s) in stile "What If" 3D per TikTok / Reels / Shorts.
Il video finale è in [`output/what_if_luna.mp4`](output/what_if_luna.mp4).

Tutto è generato da codice, senza software di editing:

| Fase | Strumento | File |
|---|---|---|
| Voce narrante italiana | [Piper TTS](https://github.com/rhasspy/piper), voce `it_IT-paola-medium` | `src/script.json`, `src/build_timeline.py` |
| Timeline e sottotitoli parola per parola | Python | `src/timeline.json` |
| Scena 3D (Terra 4K, marea oceanica che sommerge i continenti, Luna fratturata in celle di Voronoi con interno incandescente, anello di detriti, pioggia di meteoriti con onde d'urto, oscillazione dell'asse) | Three.js r170 + bloom + color grading | `src/scene.html` |
| Rendering fotogramma per fotogramma | Playwright + Chromium headless | `src/render.mjs` |
| Colonna sonora (pad, sub, arpeggi, batteria, braam) e sound design (riser, crepe, esplosione, meteore) | NumPy + SciPy | `src/music.py` |
| Luna 4K con crateri procedurali | Pillow + NumPy | `src/moontex.py` |
| Montaggio e codifica | ffmpeg | vedi sotto |

## Struttura del video

1. **Hook** – "E se la Luna cadesse sulla Terra? Spoiler: non riuscirebbe nemmeno a toccarla."
2. **Avvicinamento** – contatore della distanza Terra-Luna da 384.400 km in giù
3. **Maree** – rigonfiamento mareale fisicamente corretto (due bulge), gli oceani sommergono le coste
4. **Limite di Roche** – le crepe seguono le fratture reali: la Luna si spacca in 120 frammenti con interno incandescente
5. **Anello** – i frammenti formano un anello come Saturno
6. **Pioggia di detriti** – meteore, impatti, superficie di lava
7. **Asse instabile** – senza Luna l'asse terrestre oscilla
8. **Outro + CTA** – teaser del prossimo episodio

## Riprodurre il rendering

```bash
npm install                                   # three.js
pip install piper-tts numpy scipy pillow     # TTS, audio, texture
mkdir -p voices && cd voices && \
  curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/paola/medium/it_IT-paola-medium.onnx && \
  curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/paola/medium/it_IT-paola-medium.onnx.json && cd ..

python3 src/build_timeline.py                 # voce + src/timeline.json + src/narration.wav
python3 src/moontex.py                        # texture Luna 4K (già incluse in assets/)
python3 src/music.py                          # src/audio.wav (voce + musica + effetti, già mixato)
node src/render.mjs test 1.6 22.6 27 40       # fotogrammi di prova in test/
node src/render.mjs full 0 1725 1             # tutti i fotogrammi in frames/ (si può parallelizzare: start/step)

ffmpeg -framerate 30 -i frames/f%05d.jpg -i src/audio.wav -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p \
  -movflags +faststart -c:a aac -b:a 192k -shortest output/what_if_luna.mp4
```

Richiede Node 22, Python 3, ffmpeg e un Chromium utilizzabile da Playwright (`npx playwright install chromium` se non presente).

## Cambiare argomento

Il testo della narrazione è in `src/script.json`: ogni frase corrisponde a una scena e la timeline 3D si adatta automaticamente alle durate dell'audio. Le inquadrature sono nell'array `shots` di `src/scene.html`, le etichette tecniche nell'array `callouts`.

Texture: Terra 4K da `three-globe` (NASA Blue Marble), nuvole e Luna base dagli esempi di three.js.
