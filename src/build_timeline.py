import json, wave, numpy as np, re, os, subprocess
# Genera la narrazione con Piper (voce it_IT-paola-medium) e costruisce src/timeline.json con i tempi parola per parola.
HERE=os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
VOICE=os.path.join(HERE,'..','voices','it_IT-paola-medium.onnx')
os.makedirs('narr',exist_ok=True)
items=json.load(open('script.json'))
for it in items:
    out=f"narr/{it['id']}.wav"
    if not os.path.exists(out):
        subprocess.run(['python3','-m','piper','-m',VOICE,'--length-scale','0.93','--sentence-silence','0.25','-f',out],input=it['text'].encode(),check=True)
FPS=30; LEAD=1.0; SR=22050
display={'cta':'Seguimi per il prossimo What If.'}
t=LEAD; sentences=[]; track=[]
for it in items:
    w=wave.open(f"narr/{it['id']}.wav"); a=np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16).astype(np.float32)/32768
    env=np.abs(a); nz=np.where(env>0.02)[0]; vs=nz[0]/SR; ve=nz[-1]/SR
    # trim trailing silence beyond voiced end + 0.12s
    cut=int(min(len(a),(ve+0.12)*SR)); a=a[:cut]
    dur=len(a)/SR
    text=display.get(it['id'],it['text'])
    words=text.split()
    wts=[]
    for wd in words:
        core=re.sub(r"[^\w']","",wd)
        wt=len(core)+0.6
        if wd[-1] in ',;:': wt+=2.2
        if wd[-1] in '.?!': wt+=1.0
        wts.append(wt)
    tot=sum(wts); cur=t+vs; span=(ve-vs)
    wl=[]
    for wd,wt in zip(words,wts):
        d=span*wt/tot
        wl.append({'w':wd,'s':round(cur,3),'e':round(cur+d,3)})
        cur+=d
    # chunks of max 3 words, break at punctuation
    chunks=[]; c=[]
    for x in wl:
        c.append(x)
        if len(c)>=3 or x['w'][-1] in ',.;:?!':
            chunks.append(c); c=[]
    if c: chunks.append(c)
    sentences.append({'id':it['id'],'text':text,'start':round(t,3),'end':round(t+dur,3),'words':wl,
                      'chunks':[{'s':ch[0]['s'],'e':ch[-1]['e'],'words':ch} for ch in chunks]})
    track.append((int(t*SR),a))
    t+=dur+it['pauseAfter']
total=t+0.4
n=int(total*SR)+1; mix=np.zeros(n,dtype=np.float32)
for off,a in track: mix[off:off+len(a)]+=a
mix=np.clip(mix/max(1e-6,np.abs(mix).max())*0.95,-1,1)
w=wave.open('narration.wav','wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix*32767).astype(np.int16).tobytes()); w.close()
tl={'fps':FPS,'total':round(total,3),'sentences':sentences}
json.dump(tl,open('timeline.json','w'),indent=1,ensure_ascii=False)
for s in sentences: print(f"{s['id']:7s} {s['start']:6.2f} -> {s['end']:6.2f}")
print('total',round(total,2),'frames',int(total*FPS))
