# Colonna sonora + sound design procedurali, sincronizzati alla timeline. Scrive audio.wav (48 kHz stereo) già mixato con la voce.
import json, numpy as np, wave, os
from scipy import signal
os.chdir(os.path.dirname(os.path.abspath(__file__)))
SR=48000
TL=json.load(open('timeline.json')); S={s['id']:s for s in TL['sentences']}
T=dict(HOOK=0,DRIFT=S['drift']['start'],TIDES=S['tides']['start'],ROCHE=S['roche']['start'],RING=S['ring']['start'],RAIN=S['rain']['start'],WOBBLE=S['wobble']['start'],OUTRO=S['outro']['start'],CTA=S['cta']['start'],END=TL['total'],TITLE=S['hook']['start'])
T['BREAK']=T['ROCHE']+(T['RING']-T['ROCHE'])*0.72
N=int((T['END']+1.0)*SR)
rng=np.random.default_rng(11)
music=np.zeros((N,2)); sfx=np.zeros((N,2))
def env_adsr(n,a,d,s,r):
    e=np.zeros(n); na,nd,nr=int(a*SR),int(d*SR),int(r*SR); na=max(na,1)
    e[:na]=np.linspace(0,1,na); 
    if nd>0: e[na:na+nd]=np.linspace(1,s,min(nd,max(0,n-na)))
    e[na+nd:]=s
    if nr>0 and nr<n: e[-nr:]*=np.linspace(1,0,nr)
    return e
def lp(x,fc,order=2):
    fc=min(fc,SR*0.45); sos=signal.butter(order,fc/(SR/2),'low',output='sos'); return signal.sosfilt(sos,x)
def hp(x,fc,order=2):
    sos=signal.butter(order,fc/(SR/2),'high',output='sos'); return signal.sosfilt(sos,x)
def add(bus,sig,start,pan=0.0,gain=1.0):
    i=int(start*SR); 
    if i<0: sig=sig[-i:]; i=0
    n=min(len(sig),N-i)
    if n<=0: return
    l=np.sqrt(0.5*(1-pan)); r=np.sqrt(0.5*(1+pan))
    bus[i:i+n,0]+=sig[:n]*gain*l; bus[i:i+n,1]+=sig[:n]*gain*r
def saw(f,n,det=0.0):
    t=np.arange(n)/SR; ph=(t*(f+det))%1.0; return 2*ph-1
def sine(f,n,ph0=0): return np.sin(2*np.pi*f*np.arange(n)/SR+ph0)
# ---------------- instruments
def pad(freqs,dur,gain=0.08,cut=900,a=1.2,r=1.5):
    n=int(dur*SR); out=np.zeros(n)
    for f in freqs:
        for det in (-0.6,0,0.7): out+=saw(f,n,det*f/440)
    out=lp(out,cut,2)*env_adsr(n,a,0.3,0.9,r)
    return out*gain/len(freqs)
def pluck(f,dur=0.5,gain=0.25,bright=2600):
    n=int(dur*SR); t=np.arange(n)/SR
    x=np.sin(2*np.pi*f*t)+0.45*np.sin(2*np.pi*2*f*t)*np.exp(-t*9)+0.2*np.sin(2*np.pi*3*f*t)*np.exp(-t*14)
    x=lp(x,bright,1)*np.exp(-t*7)*gain; return x
def sparkle(f,dur=1.6,gain=0.12):
    n=int(dur*SR); t=np.arange(n)/SR
    return (np.sin(2*np.pi*f*t)+0.3*np.sin(2*np.pi*f*2.01*t))*np.exp(-t*2.6)*gain
def sub(f,dur,gain=0.5):
    n=int(dur*SR); t=np.arange(n)/SR
    return np.sin(2*np.pi*f*t)*env_adsr(n,0.01,0.1,0.8,0.12)*gain
def bass_saw(f,dur,gain=0.3,cut=420):
    n=int(dur*SR); x=saw(f,n)+saw(f,n,0.8)+0.6*saw(f/2,n); x=lp(x,cut,2); x=np.tanh(x*2.2)
    return x*env_adsr(n,0.008,0.1,0.75,0.08)*gain
def kick(gain=1.0):
    n=int(0.45*SR); t=np.arange(n)/SR
    x=np.sin(2*np.pi*(150*np.exp(-t*22)+42)*t)*np.exp(-t*7)+0.4*lp(rng.standard_normal(n),900)*np.exp(-t*60)
    return np.tanh(x*1.8)*gain
def snare(gain=0.8):
    n=int(0.32*SR); t=np.arange(n)/SR
    x=hp(rng.standard_normal(n),1500)*np.exp(-t*16)+0.5*np.sin(2*np.pi*190*t)*np.exp(-t*25)
    return x*gain
def hat(gain=0.25,dur=0.07):
    n=int(dur*SR); t=np.arange(n)/SR
    return hp(rng.standard_normal(n),7000,4)*np.exp(-t*(2.5/dur))*gain
def crash(gain=0.5):
    n=int(3.0*SR); t=np.arange(n)/SR
    return hp(rng.standard_normal(n),3500,2)*np.exp(-t*1.6)*gain
def braam(f,dur,gain=0.7):
    n=int(dur*SR); t=np.arange(n)/SR
    x=np.zeros(n)
    for det in (-1.5,-0.7,0,0.6,1.4): x+=saw(f,n,det)+0.5*saw(f*2,n,det*2)
    cut=120+1800*np.exp(-t*1.3)
    # time-varying filter approximated by 3 bands crossfade
    lo,mid,hi=lp(x,180),lp(x,700),lp(x,2400)
    w=np.clip((cut-180)/520,0,1); w2=np.clip((cut-700)/1700,0,1)
    y=lo*(1-w)+mid*w*(1-w2)+hi*w2
    return np.tanh(y*1.5)*env_adsr(n,0.12,0.6,0.7,2.0)*gain
# ---------------- harmony
BPM=100; beat=60/BPM; bar=4*beat
chords=[('Am',[110,220,261.63,329.63]),('F',[87.31,174.61,220,261.63]),('C',[130.81,261.63,329.63,392]),('G',[98,196,246.94,293.66])]
def chord_at(k): return chords[k%4]
# ---------------- arrangement
def section_pad(t0,t1,gain,cut,octave=1):
    k=0; t=t0
    while t<t1:
        name,fr=chord_at(k); dur=min(bar,t1-t)+1.2
        add(music,pad([f*octave for f in fr[1:]],dur,gain,cut),t,0.0)
        t+=bar; k+=1
def section_sub(t0,t1,gain,div=2):
    k=0; t=t0; step=beat/div; i=0
    while t<t1:
        kb=int((t-t0)//bar); name,fr=chord_at(kb)
        add(music,sub(fr[0]/2,step*0.9,gain*(1.0 if i%div==0 else 0.7)),t); t+=step; i+=1
def section_bass(t0,t1,gain):
    t=t0; i=0
    while t<t1:
        kb=int((t-t0)//bar); name,fr=chord_at(kb); step=beat/2
        f=fr[0]*(2 if i%4==3 else 1)
        add(music,bass_saw(f,step*0.95,gain),t); t+=step; i+=1
def section_arp(t0,t1,gain,octave=2,div=4,bright=2600,pan_w=0.5):
    t=t0; i=0; pat=[0,1,2,3,2,1,3,0]
    while t<t1:
        kb=int((t-t0)//bar); name,fr=chord_at(kb); f=fr[1+pat[i%8]%3]*octave*(2 if (i%16)>=12 else 1)
        add(music,pluck(f,0.45,gain,bright),t,np.sin(i*0.7)*pan_w); t+=beat/div; i+=1
def section_sparkle(t0,t1,gain):
    t=t0; i=0; notes=[659.26,783.99,880,1046.5,987.77,783.99]
    while t<t1:
        if rng.random()<0.8: add(music,sparkle(notes[i%6]*(2 if rng.random()<0.3 else 1),1.8,gain),t,rng.random()*1.4-0.7)
        t+=beat/2*(1 if rng.random()<0.6 else 2); i+=1
def section_drums(t0,t1,kg=0.9,sg=0.6,hg=0.2,half=False):
    t=t0; i=0
    while t<t1:
        b=i%8  # eighth notes index in bar
        if half:
            if b==0: add(music,kick(kg),t)
            if b==4: add(music,snare(sg),t)
            if b%2==0: add(music,hat(hg*0.8),t,0.3)
        else:
            if b in (0,4) or (b==6 and (i//8)%2==1): add(music,kick(kg),t)
            if b in (2,6): add(music,snare(sg),t)
            add(music,hat(hg*(1 if b%2==0 else 0.6)),t,0.3)
        t+=beat/2; i+=1
# intro
add(music,pad([220,261.63,329.63],T['DRIFT']-T['HOOK']+2,0.05,700,1),0.0)
add(music,sub(55,2.5,0.5)*env_adsr(int(2.5*SR),0.005,0.5,0.3,1.0),T['TITLE']-0.02)
# build: drift -> roche
section_pad(T['DRIFT'],T['ROCHE'],0.07,900)
section_sub(T['DRIFT']+bar,T['ROCHE'],0.42,2)
section_arp(T['DRIFT']+bar*2,T['TIDES'],0.10,2,4,1800)
section_arp(T['TIDES'],T['ROCHE'],0.16,2,4,2600)
section_drums(T['TIDES'],T['ROCHE'],0.55,0.0,0.14,half=True)
# tension: roche -> break
section_pad(T['ROCHE'],T['BREAK'],0.09,1500)
section_sub(T['ROCHE'],T['BREAK']-0.35,0.5,4)
section_arp(T['ROCHE'],T['BREAK']-0.35,0.2,4,4,3200)
section_drums(T['ROCHE'],T['BREAK']-0.35,1.0,0.7,0.26)
n=int(2.6*SR); t=np.arange(n)/SR; p=t/2.6
add(music,np.sin(2*np.pi*(220*2**(p*p*1.0))*t)*(0.05+0.25*p**2),T['BREAK']-2.6)
# break
add(music,braam(55,6.0,0.8),T['BREAK']-0.03)
add(music,crash(0.45),T['BREAK'])
add(music,kick(1.2),T['BREAK'])
# ring: beauty
section_pad(T['RING']-0.5,T['RAIN'],0.09,2200,2)
section_sparkle(T['RING'],T['RAIN'],0.10)
section_sub(T['RING'],T['RAIN'],0.25,1)
# rain: heavy
section_pad(T['RAIN'],T['WOBBLE'],0.08,1200)
section_bass(T['RAIN'],T['WOBBLE'],0.28)
section_drums(T['RAIN'],T['WOBBLE'],1.0,0.75,0.28)
section_arp(T['RAIN'],T['WOBBLE'],0.16,4,4,3400)
# wobble: ominous half-time
section_pad(T['WOBBLE'],T['OUTRO'],0.1,800)
section_drums(T['WOBBLE'],T['OUTRO']-0.5,0.9,0.7,0.2,half=True)
section_sub(T['WOBBLE'],T['OUTRO']-0.5,0.4,1)
n=int((T['OUTRO']-T['WOBBLE'])*SR); t=np.arange(n)/SR
add(music,np.sin(2*np.pi*(65+5*np.sin(2*np.pi*0.45*t))*t)*env_adsr(n,1.0,0.5,0.9,1.0)*0.12,T['WOBBLE'])
# outro: resolve (C major -> Am add9), gentle plucks
add(music,pad([261.63,329.63,392,523.25],T['CTA']-T['OUTRO']+0.5,0.075,1400,1),T['OUTRO'])
add(music,pad([220,329.63,493.88,523.25],T['END']-T['CTA']+1.5,0.07,1400,1),T['CTA']-0.2)
for i,(f,dt) in enumerate([(659.26,0),(523.25,0.6),(440,1.2),(493.88,1.8),(523.25,2.6),(659.26,3.3)]):
    add(music,pluck(f,1.2,0.16,2200),T['OUTRO']+0.4+dt,(i%2-0.5)*0.6)
add(music,sparkle(1046.5,2.5,0.14),T['CTA']+0.1,0.3); add(music,sparkle(1318.5,2.5,0.1),T['CTA']+0.35,-0.3)
# ---------------- SFX
def smooth(x,fc): return lp(x,fc,2)
# riser noise TIDES->BREAK
n=int((T['BREAK']-T['TIDES'])*SR); t=np.arange(n)/SR; p=t/t[-1]; nz=rng.standard_normal(n)
add(sfx,(smooth(nz,250)*(1-p)+hp(smooth(nz,4000),400)*p)*(0.02+0.4*p**3)*env_adsr(n,1,0.1,1,0.02),T['TIDES'])
# ocean roar during tides
n=int((T['ROCHE']-T['TIDES']+1)*SR); t=np.arange(n)/SR
add(sfx,smooth(rng.standard_normal(n),320)*(0.5+0.5*np.sin(2*np.pi*0.35*t))*env_adsr(n,1.5,0.2,1,1.0)*0.5,T['TIDES'])
# crack sounds roche
for k in range(34):
    st=T['ROCHE']+0.3+rng.random()*(T['BREAK']-T['ROCHE']-0.5); n=int(0.3*SR); t=np.arange(n)/SR
    add(sfx,smooth(rng.standard_normal(n),900+rng.random()*3500)*np.exp(-t*22)*(0.3+rng.random()*0.6)+0.3*np.sin(2*np.pi*(80+rng.random()*60)*t)*np.exp(-t*30),st,rng.random()*1.4-0.7,0.35*(0.4+0.6*(st-T['ROCHE'])/(T['BREAK']-T['ROCHE'])))
# break explosion
n=int(6.0*SR); t=np.arange(n)/SR
boom=np.sin(2*np.pi*(95*np.exp(-t*3)+26)*t)*np.exp(-t*1.4)
burst=smooth(rng.standard_normal(n),6000)*np.exp(-t*4.0)*0.9+smooth(rng.standard_normal(n),250)*np.exp(-t*0.8)*0.7
add(sfx,(boom*1.1+burst*0.9)*env_adsr(n,0.004,0.5,1,1.0),T['BREAK']-0.02,0,1.0)
# meteor whooshes + impacts
nw=int((T['WOBBLE']+3.0-T['RAIN'])/0.3)
for k in range(nw):
    st=T['RAIN']-0.3+k*0.3+rng.random()*0.2; dur=0.35+rng.random()*0.5; n=int(dur*SR); t=np.arange(n)/SR; p=t/dur
    wh=hp(smooth(rng.standard_normal(n),3200),300)*np.sin(np.pi*p)**1.5*(0.25+0.5*rng.random())
    add(sfx,wh,st,rng.random()*1.6-0.8,0.26)
    if rng.random()<0.6:
        n2=int(0.7*SR); t2=np.arange(n2)/SR
        imp=np.sin(2*np.pi*(75*np.exp(-t2*8)+32)*t2)*np.exp(-t2*5)+smooth(rng.standard_normal(n2),900)*np.exp(-t2*12)*0.5
        add(sfx,imp,st+dur*0.9,rng.random()*1.2-0.6,0.3)
n=int((T['OUTRO']-T['RAIN'])*SR); add(sfx,smooth(rng.standard_normal(n),90)*env_adsr(n,1.5,0.2,1,1.2)*1.5,T['RAIN'])
# hook: whoosh in + title hit
n=int(1.0*SR); t=np.arange(n)/SR; add(sfx,hp(smooth(rng.standard_normal(n),2500),200)*(t/1.0)**2*0.5,0.0,0,0.6)
n=int(2.5*SR); t=np.arange(n)/SR
add(sfx,np.sin(2*np.pi*(60*np.exp(-t*4)+32)*t)*np.exp(-t*2.2)*0.9+smooth(rng.standard_normal(n),1500)*np.exp(-t*7)*0.5,T['TITLE']-0.03,0,0.8)
# scene-cut whooshes (subtle) at each sentence start
for sid in ('drift','tides','ring','rain','wobble','outro'):
    st=S[sid]['start']-0.25; n=int(0.5*SR); t=np.arange(n)/SR; p=t/0.5
    add(sfx,hp(smooth(rng.standard_normal(n),2000),250)*np.sin(np.pi*p)**2*0.5,st,0,0.3)
# outro / cta: soft chime already in music
# ---------------- reverb (synthetic IR)
def reverb(x,wet,dec=1.6):
    n=int(dec*SR); ir=rng.standard_normal(n)*np.exp(-np.arange(n)/SR*(6.9/dec)); ir=lp(ir,5000,1); ir/=np.sqrt(np.sum(ir**2))*6
    y=np.empty_like(x)
    for c in range(x.shape[1]): y[:,c]=signal.fftconvolve(x[:,c],ir)[:len(x)]
    return x*(1-wet*0.3)+y*wet
music=reverb(music,0.35,1.8)
sfx=reverb(sfx,0.18,1.2)
# ---------------- narration
w=wave.open('narration.wav'); nar=np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16).astype(np.float64)/32768; nsr=w.getframerate()
nar=signal.resample_poly(nar,SR,nsr); nar=hp(nar,85,2)
# presence boost
sos=signal.butter(2,[1800/(SR/2),5200/(SR/2)],'band',output='sos'); nar=nar+0.35*signal.sosfilt(sos,nar)
# simple compressor
envn=np.abs(signal.sosfilt(signal.butter(1,30/(SR/2),'low',output='sos'),np.abs(nar)))*2.2
gain=np.where(envn>0.25,(0.25/np.maximum(envn,1e-6))**0.6,1.0)
nar=nar*gain; nar=nar/np.max(np.abs(nar))*0.92
narS=np.stack([nar,nar],1); narS=np.pad(narS,((0,max(0,N-len(narS))),(0,0)))[:N]
narS=reverb(narS,0.07,0.9)
# ducking
envd=signal.sosfilt(signal.butter(1,12/(SR/2),'low',output='sos'),np.abs(narS[:,0]))*3.0
duck=1-0.5*np.clip(envd/0.12,0,1)
# ---------------- mix
music=music/np.max(np.abs(music)); sfx=sfx/np.max(np.abs(sfx))
mix=narS*1.0+(music*0.42+sfx*0.5)*duck[:,None]
mix=np.tanh(mix*0.9)/np.tanh(0.9); mix=mix/np.max(np.abs(mix))*0.95
ww=wave.open('audio.wav','wb'); ww.setnchannels(2); ww.setsampwidth(2); ww.setframerate(SR); ww.writeframes((mix*32767).astype(np.int16).tobytes()); ww.close()
print('audio ok',N/SR)
