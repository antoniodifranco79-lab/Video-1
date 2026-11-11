# What If · E se la Luna cadesse sulla Terra?

Video verticale 9:16 (1080×1920, 30 fps, ~52 s) in stile "What If" 3D per TikTok / Reels / Shorts.
Il video finale è in [`output/what_if_luna.mp4`](output/what_if_luna.mp4).

Tutto è generato da codice, senza software di editing:

| Fase | Strumento | File |
|---|---|---|
| Voce narrante italiana | [Piper TTS](https://github.com/rhasspy/piper), voce `it_IT-paola-medium` | `src/script.json`, `src/build_timeline.py` |
| Timeline e sottotitoli parola per parola | Python | `src/timeline.json` |
| Scena 3D (Terra, Luna, limite di Roche, anello di detriti, pioggia di meteoriti, oscillazione dell'asse) | Three.js r170 + bloom | `src/scene.html` |
| Rendering fotogramma per fotogramma | Playwright + Chromium headless | `src/render.mjs` |
| Sound design (drone, riser, esplosione, meteore, pad) | NumPy | `src/sfx.py` |
| Montaggio e codifica | ffmpeg | vedi sotto |

## Struttura del video

1. **Hook** – titolo "E se la Luna cadesse sulla Terra?"
2. **Avvicinamento** – la Luna oggi si allontana di 3,8 cm/anno; immaginiamo che si avvicini
3. **Maree** – rigonfiamento mareale della Terra, onde di centinaia di metri
4. **Limite di Roche** – a 18.000 km la Luna si crepa e si frantuma
5. **Anello** – i frammenti formano un anello come Saturno
6. **Pioggia di detriti** – meteore, impatti, superficie di lava
7. **Asse instabile** – senza Luna l'asse terrestre oscilla
8. **Outro + CTA**

## Riprodurre il rendering

```bash
npm install                                   # three.js
pip install piper-tts numpy                   # TTS e sound design
mkdir -p voices && cd voices && \
  curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/paola/medium/it_IT-paola-medium.onnx && \
  curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/paola/medium/it_IT-paola-medium.onnx.json && cd ..

python3 src/build_timeline.py                 # voce + src/timeline.json + src/narration.wav
python3 src/sfx.py                            # src/sfx.wav
node src/render.mjs test 1.6 22.6 27 40       # fotogrammi di prova in test/
node src/render.mjs full 0 1541 1             # tutti i fotogrammi in frames/ (si può parallelizzare: start/step)

ffmpeg -i src/narration.wav -i src/sfx.wav -filter_complex \
  "[0:a]aresample=48000,highpass=f=80,acompressor=threshold=-18dB:ratio=3:attack=10:release=120:makeup=4[n];[1:a]volume=0.55[s];[n][s]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95,atrim=0:52.4[a]" \
  -map "[a]" -ac 2 -ar 48000 audio.wav
ffmpeg -framerate 30 -i frames/f%05d.jpg -i audio.wav -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p \
  -movflags +faststart -c:a aac -b:a 192k -shortest output/what_if_luna.mp4
```

Richiede Node 22, Python 3, ffmpeg e un Chromium utilizzabile da Playwright (`npx playwright install chromium` se non presente).

## Cambiare argomento

Il testo della narrazione è in `src/script.json`: ogni frase corrisponde a una scena e la timeline 3D si adatta automaticamente alle durate dell'audio. Le inquadrature sono nell'array `shots` di `src/scene.html`, le etichette tecniche nell'array `callouts`.

Texture dei pianeti: esempi di three.js (`examples/textures/planets`).
