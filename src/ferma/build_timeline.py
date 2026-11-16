# Voce neurale Kokoro (it, if_sara) + allineamento parola per parola con Whisper -> timeline.json, narration.wav
import json, os, re, difflib, unicodedata, numpy as np, soundfile as sf
from scipy import signal
HERE=os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
MODELS=os.environ.get('KOKORO_DIR',os.path.join(HERE,'..','..','models'))
VOICE=os.environ.get('VOICE','if_sara'); SPEED=float(os.environ.get('SPEED','1.08'))
FPS=30; LEAD=0.45; SR=24000
display={'cta':'Seguimi: nel prossimo What_If, un buco nero attraversa il Sistema Solare.',
 'speed':"All'equatore il suolo corre verso est a 1.670 chilometri orari. Se la Terra frena di colpo, tutto quello che non è ancorato alla roccia continua a volare."}
items=json.load(open('script.json')); os.makedirs('narr',exist_ok=True)
from kokoro_onnx import Kokoro
from faster_whisper import WhisperModel
kok=None; asr=WhisperModel('small',device='cpu',compute_type='int8')
def norm(w):
    w=unicodedata.normalize('NFKD',w.lower()); w=''.join(c for c in w if not unicodedata.combining(c)); return re.sub(r"[^a-z0-9']","",w)
t=LEAD; sentences=[]; track=[]
for it in items:
    f=f"narr/{it['id']}.wav"
    if not os.path.exists(f):
        kok=kok or Kokoro(os.path.join(MODELS,'kokoro-v1.0.onnx'),os.path.join(MODELS,'voices-v1.0.bin'))
        a,sr=kok.create(it['text'],voice=VOICE,speed=SPEED,lang='it'); sf.write(f,a,sr)
    a,sr=sf.read(f,dtype='float32'); assert sr==SR
    env=np.abs(a); nz=np.where(env>0.01)[0]; s0=max(0,nz[0]-int(0.03*SR)); e0=min(len(a),nz[-1]+int(0.12*SR)); a=a[s0:e0]
    segs,_=asr.transcribe(signal.resample_poly(a,16000,SR).astype(np.float32),language='it',word_timestamps=True)
    W=[(w.word.strip(),w.start,w.end) for s in segs for w in s.words]
    text=display.get(it['id'],it['text']); D=text.split()
    nd=[norm(x.replace('_',' ')) for x in D]; nw=[norm(x[0]) for x in W]
    times=[None]*len(D)
    for op,i1,i2,j1,j2 in difflib.SequenceMatcher(None,nd,nw,autojunk=False).get_opcodes():
        if op=='equal':
            for k in range(i2-i1): times[i1+k]=(W[j1+k][1],W[j1+k][2])
        elif op=='replace':
            ws,we=W[j1][1],W[j2-1][2]; L=[max(1,len(nd[k])) for k in range(i1,i2)]; tot=sum(L); c=ws
            for k,l in zip(range(i1,i2),L): d=(we-ws)*l/tot; times[k]=(c,c+d); c+=d
    # interpolate missing
    for k in range(len(D)):
        if times[k] is None:
            prev=next((times[j][1] for j in range(k-1,-1,-1) if times[j]),0.0)
            nxt=next((times[j][0] for j in range(k+1,len(D)) if times[j]),len(a)/SR)
            times[k]=(prev,max(prev+0.05,min(nxt,prev+0.35)))
    wl=[{'w':D[k],'s':round(t+times[k][0],3),'e':round(t+times[k][1],3)} for k in range(len(D))]
    chunks=[]; c=[]
    for k,x in enumerate(wl):
        c.append(x)
        if it['id']=='hook' and len(chunks)==0:
            if x['w'].endswith('?'): chunks.append(c); c=[]
            continue
        nxt=wl[k+1]['w'] if k+1<len(wl) else ''
        chars=sum(len(y['w']) for y in c)+len(c)-1
        absorb=nxt!='' and nxt[-1] in ',.;:?!' and chars+1+len(nxt)<=27 and len(c)<5
        if x['w'][-1] in ',.;:?!' or ((len(c)>=4 or chars+1+len(nxt)>22) and not absorb): chunks.append(c); c=[]
    if c: chunks.append(c)
    dur=len(a)/SR
    sentences.append({'id':it['id'],'text':text,'start':round(t,3),'end':round(t+dur,3),'words':wl,'chunks':[{'s':ch[0]['s'],'e':ch[-1]['e'],'words':ch} for ch in chunks],'asr':' '.join(x[0] for x in W)})
    track.append((int(t*SR),a)); t+=dur+it['pauseAfter']
total=t+0.4; n=int(total*SR)+1; mix=np.zeros(n,dtype=np.float32)
for off,a in track: mix[off:off+len(a)]+=a
mix=np.clip(mix/max(1e-6,np.abs(mix).max())*0.95,-1,1); sf.write('narration.wav',mix,SR,subtype='PCM_16')
json.dump({'fps':FPS,'total':round(total,3),'sentences':sentences},open('timeline.json','w'),indent=1,ensure_ascii=False)
for s in sentences: print(f"{s['id']:7s} {s['start']:6.2f}->{s['end']:6.2f} | {s['asr']}")
print('total',round(total,2),'frames',int(total*FPS))
