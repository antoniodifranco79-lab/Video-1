# What If · Serie di video "E se…?" in 3D

Video verticali 9:16 (1080×1920, 30 fps, ~50 s) in stile "What If" 3D per TikTok / Reels / Shorts.
Tutto è generato da codice, senza software di editing.

## Episodi

| # | Titolo | Video |
|---|---|---|
| 01 | E se la Luna cadesse sulla Terra? | [`output/what_if_luna.mp4`](output/what_if_luna.mp4) |
| 02 | E se il Sole diventasse una gigante rossa? | [`output/what_if_sole.mp4`](output/what_if_sole.mp4) |

## Pipeline

| Fase | Strumento | File |
|---|---|---|
| Voce narrante italiana | [Piper TTS](https://github.com/rhasspy/piper), voce `it_IT-paola-medium` | `src/script.json`, `src/build_timeline.py` |
| Timeline e sottotitoli parola per parola | Python | `src/timeline.json` |
| Scena 3D | Three.js r170 + bloom (Chromium headless) | `src/scene.html` |
| Rendering fotogramma per fotogramma | Playwright + Chromium | `src/render.mjs` |
| Sound design procedurale | NumPy | `src/sfx.py` |
| Montaggio e codifica | ffmpeg | vedi sotto |

## Episodio 02 — "E se il Sole diventasse una gigante rossa?"

Struttura delle scene (ogni frase di `src/script.json` è una scena; la timeline 3D si adatta alle durate dell'audio):

1. **Hook** – titolo "E se il Sole diventasse una gigante rossa?"
2. **Combustibile** – tra ~5 miliardi di anni il Sole esaurisce l'idrogeno nel nucleo
3. **Dilatazione** – il nucleo collassa, gli strati esterni si gonfiano, il Sole si arrossa
4. **Pianeti interni** – inghiotte Mercurio e poi Venere
5. **Terra** – oceani in ebollizione, atmosfera strappata, superficie di lava (shader riusato dall'ep. 01)
6. **Engulf** – il Sole raggiunge ~1 UA (100× il raggio attuale) e divora la Terra
7. **Nebulosa** – espelle gli strati esterni formando una nebulosa planetaria
8. **Nana bianca** – resta solo il nucleo nudo, che si raffredda nel buio
9. **Outro + CTA**

Elementi 3D: Sole con shader di granulazione al plasma (simplex noise + fbm) e colore/raggio animati, corona additiva, pianeti in orbita (Mercurio, Venere, Terra completa, Marte), inghiottimento sincronizzato con gli impatti audio, nebulosa planetaria a particelle colorate e nana bianca.

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
node src/render.mjs test 6.5 26 33 40         # fotogrammi di prova in test/
node src/render.mjs full 0 1527 1             # tutti i fotogrammi in frames/ (parallelizzabile: start/step)

ffmpeg -i src/narration.wav -i src/sfx.wav -filter_complex \
  "[0:a]aresample=48000,highpass=f=80,acompressor=threshold=-18dB:ratio=3:attack=10:release=120:makeup=4[n];[1:a]volume=0.55[s];[n][s]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95,atrim=0:51.0[a]" \
  -map "[a]" -ac 2 -ar 48000 audio.wav
ffmpeg -framerate 30 -i frames/f%05d.jpg -i audio.wav -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p \
  -movflags +faststart -c:a aac -b:a 192k -shortest output/what_if_sole.mp4
```

Richiede Node 22, Python 3, ffmpeg e un Chromium utilizzabile da Playwright.

## Cambiare argomento

Il testo della narrazione è in `src/script.json`: ogni frase corrisponde a una scena e la timeline 3D si adatta automaticamente alle durate dell'audio. Le inquadrature sono nell'array `shots` di `src/scene.html`, le etichette tecniche nell'array `callouts`.
