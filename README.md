# What If · Serie di video "E se…?" in 3D

Video verticali 9:16 (1080×1920, 30 fps, ~49 s) in stile "What If" 3D per TikTok / Reels / Shorts.
Tutto è generato da codice, senza software di editing.

## Episodi

| # | Titolo | Video |
|---|---|---|
| 01 | E se la Luna cadesse sulla Terra? | [`output/what_if_luna.mp4`](output/what_if_luna.mp4) |
| 02 | E se gli oceani sparissero? | [`output/what_if_oceani.mp4`](output/what_if_oceani.mp4) |

> Nella storia del repository è presente anche un concept alternativo per
> l'episodio 02 ("E se il Sole diventasse una gigante rossa?", commit precedente),
> sostituito su richiesta da quello sugli oceani.

## Pipeline

| Fase | Strumento | File |
|---|---|---|
| Voce narrante italiana | [Piper TTS](https://github.com/rhasspy/piper), voce `it_IT-paola-medium` | `src/script.json`, `src/build_timeline.py` |
| Timeline e sottotitoli parola per parola | Python | `src/timeline.json` |
| Scena 3D | Three.js r170 + bloom (Chromium headless) | `src/scene.html` |
| Rendering fotogramma per fotogramma | Playwright + Chromium | `src/render.mjs` |
| Sound design procedurale | NumPy | `src/sfx.py` |
| Montaggio e codifica | ffmpeg | vedi sotto |

## Episodio 02 — "E se gli oceani sparissero?"

Struttura delle scene (ogni frase di `src/script.json` è una scena; la timeline 3D si adatta alle durate dell'audio):

1. **Hook** – titolo "E se tutti gli oceani della Terra sparissero?"
2. **Gli oceani** – coprono il 71% del pianeta, 1,3 miliardi di km³ d'acqua
3. **Prosciugamento** – l'acqua evapora, il livello del mare crolla, le coste si ritirano
4. **Fondali** – affiorano dorsali, pianure abissali e fosse profonde 11 km
5. **Clima** – senza evaporazione spariscono nuvole e piogge, il clima collassa
6. **Vita** – la vita marina si spegne e la catena alimentare crolla
7. **Deserto** – la Terra diventa un deserto rovente con tempeste di polvere
8. **Outro** – per fortuna non accadrà, ma gli oceani vanno protetti
9. **CTA**

Tecnica: Terra in Three.js con shader di prosciugamento che usa la mappa speculare come maschera degli oceani e una mappa di rumore come profondità dei bacini. Al crescere di `uDrain` l'acqua si ritira dai bassi fondali verso le fosse, rivelando il fondale (da fango scuro a sabbia secca); le terre emerse si inaridiscono, le luci delle città si spengono, le nuvole svaniscono, l'atmosfera vira dal blu al marrone polveroso. Particelle di vapore in risalita durante l'evaporazione, foschia di polvere nella fase deserto, e ritorno degli oceani nell'outro.

## Riprodurre il rendering

```bash
npm install                                   # three.js
pip install piper-tts numpy                   # TTS e sound design
# voce italiana (mirror sherpa-onnx; huggingface può essere irraggiungibile):
mkdir -p voices && cd voices && \
  curl -L -o v.tar.bz2 https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-it_IT-paola-medium.tar.bz2 && \
  tar xjf v.tar.bz2 && mv vits-piper-it_IT-paola-medium/it_IT-paola-medium.onnx* . && cd ..

python3 src/build_timeline.py                 # voce + src/timeline.json + src/narration.wav
python3 src/sfx.py                            # src/sfx.wav
node src/render.mjs test 6.5 14.5 19 37.5     # fotogrammi di prova in test/
node src/render.mjs full 0 1471 1             # tutti i fotogrammi in frames/ (parallelizzabile: start/step)

ffmpeg -i src/narration.wav -i src/sfx.wav -filter_complex \
  "[0:a]aresample=48000,highpass=f=80,acompressor=threshold=-18dB:ratio=3:attack=10:release=120:makeup=4[n];[1:a]volume=0.6[s];[n][s]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95,atrim=0:49.1[a]" \
  -map "[a]" -ac 2 -ar 48000 audio.wav
ffmpeg -framerate 30 -i frames/f%05d.jpg -i audio.wav -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p \
  -movflags +faststart -c:a aac -b:a 192k -shortest output/what_if_oceani.mp4
```

Richiede Node 22, Python 3, ffmpeg e un Chromium utilizzabile da Playwright.

## Cambiare argomento

Il testo della narrazione è in `src/script.json`: ogni frase corrisponde a una scena e la timeline 3D si adatta automaticamente alle durate dell'audio. Le inquadrature sono nell'array `shots` di `src/scene.html`, le etichette tecniche nell'array `callouts`.
