import json, numpy as np, wave, os
# Sound design procedurale (drone, riser, esplosione, meteore, pad) sincronizzato alla timeline; scrive src/sfx.wav
os.chdir(os.path.dirname(os.path.abspath(__file__)))
SR=48000
TL=json.load(open('timeline.json')); S={s['id']:s for s in TL['sentences']}
T=dict(DRIFT=S['drift']['start'],TIDES=S['tides']['start'],ROCHE=S['roche']['start'],RING=S['ring']['start'],RAIN=S['rain']['start'],WOBBLE=S['wobble']['start'],OUTRO=S['outro']['start'],CTA=S['cta']['start'],END=TL['total'])
T['BREAK']=T['ROCHE']+(T['RING']-T['ROCHE'])*0.72
N=int(T['END']*SR)+SR; t=np.arange(N)/SR
rng=np.random.default_rng(7)
out=np.zeros((N,2),dtype=np.float64)
def env_ad(n,a,d):
    e=np.ones(n); na=int(a*SR); nd=int(d*SR)
    if na>0: e[:na]=np.linspace(0,1,na)
    if nd>0: e[-nd:]*=np.linspace(1,0,nd)
    return e
def add(sig,start,pan=0.0,gain=1.0):
    i=int(start*SR); n=min(len(sig),N-i)
    if n<=0: return
    l=np.sqrt(0.5*(1-pan)); r=np.sqrt(0.5*(1+pan))
    out[i:i+n,0]+=sig[:n]*gain*l; out[i:i+n,1]+=sig[:n]*gain*r
def lowpass(x,fc):
    a=np.exp(-2*np.pi*fc/SR); y=np.empty_like(x); acc=0.0
    # vectorized IIR via scipy-free loop is slow; use lfilter-like recursion with numpy trick
    from itertools import accumulate
    b=1-a
    y=np.array(list(accumulate(x*b, lambda acc,v: acc*a+v)))
    return y
def smooth(x,fc):  # cheap one-pole via FFT-based approximation
    X=np.fft.rfft(x); f=np.fft.rfftfreq(len(x),1/SR); X*=1/np.sqrt(1+(f/fc)**4); return np.fft.irfft(X,len(x))
# --- 1. space drone (whole video): detuned low saws through soft filter, slow swell
def drone(dur,f0,gain):
    n=int(dur*SR); tt=np.arange(n)/SR
    sig=np.zeros(n)
    for k,(mult,det) in enumerate([(1,0),(1,0.4),(2,-0.3),(3,0.2),(0.5,0.1)]):
        ph=2*np.pi*(f0*mult+det)*tt
        sig+=np.sin(ph+0.3*np.sin(2*np.pi*0.07*tt+k))/(1+k)
    lfo=0.75+0.25*np.sin(2*np.pi*0.05*tt)
    return smooth(sig*lfo,600)*gain
d1=drone(T['END']+1,55,0.25); d1*=env_ad(len(d1),2.0,2.5); add(d1,0,0,1)
d2=drone(T['END']+1,82.4,0.12); d2*=env_ad(len(d2),4.0,2.5); add(d2,0,0.3,1)
# tension riser: rising noise + rising sine from TIDES to BREAK
n=int((T['BREAK']-T['TIDES'])*SR); tt=np.arange(n)/SR; p=tt/tt[-1]
nz=rng.standard_normal(n); riser=(smooth(nz,250)*(1-p)+smooth(nz,2800)*p)*(0.02+0.35*p**3)
riser+=np.sin(2*np.pi*(40+60*p**2)*tt)*(0.05+0.3*p**2)
add(riser*env_ad(n,1.0,0.05),T['TIDES'])
# heartbeat-like pulse during ROCHE
for k in range(int((T['BREAK']-T['ROCHE'])/0.75)):
    st=T['ROCHE']+k*0.75; n=int(0.35*SR); tt=np.arange(n)/SR
    thump=np.sin(2*np.pi*(55*np.exp(-tt*6)+38)*tt)*np.exp(-tt*9)
    add(thump,st,0,0.35*(0.5+0.5*k/8))
# crack sounds during roche (random crackles)
for k in range(28):
    st=T['ROCHE']+0.5+rng.random()*(T['BREAK']-T['ROCHE']-0.6); n=int(0.25*SR); tt=np.arange(n)/SR
    cr=smooth(rng.standard_normal(n),800+rng.random()*3000)*np.exp(-tt*25)*(0.3+rng.random()*0.5)
    add(cr,st,rng.random()*1.2-0.6,0.25)
# --- 2. BREAK: big impact: sub boom + noise burst + long tail
n=int(5.0*SR); tt=np.arange(n)/SR
boom=np.sin(2*np.pi*(90*np.exp(-tt*3)+28)*tt)*np.exp(-tt*1.6)
burst=smooth(rng.standard_normal(n),6000)*np.exp(-tt*4.5)*0.9+smooth(rng.standard_normal(n),300)*np.exp(-tt*0.9)*0.6
add((boom*1.0+burst*0.8)*env_ad(n,0.004,1.0),T['BREAK']-0.02,0,0.9)
# sub silence dip just before break (duck drone): emulate by negative drone? skip
# --- 3. ring: shimmering high pad
n=int((T['RAIN']-T['RING']+1.5)*SR); tt=np.arange(n)/SR
pad=np.zeros(n)
for f,amp in [(329.6,1),(392,0.8),(493.9,0.7),(659.3,0.4),(246.9,0.9)]:
    pad+=np.sin(2*np.pi*f*tt+0.5*np.sin(2*np.pi*0.3*tt))*amp*(0.6+0.4*np.sin(2*np.pi*(0.11+f/5000)*tt))
pad=smooth(pad,2500)*env_ad(n,2.5,2.0)*0.035
add(pad,T['RING']-0.5,0,1)
# --- 4. rain: whooshes + impacts
nw=int((T['WOBBLE']+3.0-T['RAIN'])/0.32)
for k in range(nw):
    st=T['RAIN']-0.3+k*0.32+rng.random()*0.2; dur=0.35+rng.random()*0.5; n=int(dur*SR); tt=np.arange(n)/SR; p=tt/dur
    fc=400+3500*np.sin(np.pi*p)**2
    wh=smooth(rng.standard_normal(n),3000)*np.sin(np.pi*p)**1.5*(0.25+0.5*rng.random())
    add(wh,st,rng.random()*1.6-0.8,0.22)
    if rng.random()<0.6:
        n2=int(0.6*SR); t2=np.arange(n2)/SR
        imp=np.sin(2*np.pi*(70*np.exp(-t2*8)+35)*t2)*np.exp(-t2*6)+smooth(rng.standard_normal(n2),900)*np.exp(-t2*14)*0.5
        add(imp,st+dur*0.9,rng.random()*1.2-0.6,0.28)
# rumble bed during rain/wobble
n=int((T['OUTRO']-T['RAIN'])*SR); rum=smooth(rng.standard_normal(n),90)*env_ad(n,1.5,1.2)*1.4; add(rum,T['RAIN'],0,1)
# wobble: slow detuned wobble tone
n=int((T['OUTRO']-T['WOBBLE'])*SR); tt=np.arange(n)/SR
wob=np.sin(2*np.pi*(65+6*np.sin(2*np.pi*0.45*tt))*tt)*env_ad(n,1.5,1.0)*0.18; add(wob,T['WOBBLE'])
# --- 5. outro: warm calm chord + soft chime at CTA
n=int((T['END']-T['OUTRO']+1)*SR); tt=np.arange(n)/SR
ch=np.zeros(n)
for f,amp in [(130.8,1),(196,0.7),(261.6,0.6),(329.6,0.4),(392,0.3)]:
    ch+=np.sin(2*np.pi*f*tt)*amp*(0.8+0.2*np.sin(2*np.pi*0.2*tt+f))
ch=smooth(ch,1200)*env_ad(n,2.0,2.5)*0.05; add(ch,T['OUTRO'])
n=int(1.8*SR); tt=np.arange(n)/SR
chime=(np.sin(2*np.pi*1046.5*tt)+0.5*np.sin(2*np.pi*2093*tt))*np.exp(-tt*3)*0.12; add(chime,T['CTA'],0.2)
# --- 6. hook: deep hit at t=1.0 (title) and whoosh in
n=int(2.5*SR); tt=np.arange(n)/SR
hit=np.sin(2*np.pi*(60*np.exp(-tt*4)+32)*tt)*np.exp(-tt*2.2)*0.8+smooth(rng.standard_normal(n),1500)*np.exp(-tt*7)*0.5
add(hit,0.95,0,0.7)
n=int(1.0*SR); tt=np.arange(n)/SR; p=tt/1.0
wh=smooth(rng.standard_normal(n),2500)*p**2*0.5; add(wh,0.0,0,0.5)
# duck under narration a bit (sidechain-ish): compute narration envelope
w=wave.open('narration.wav'); nar=np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16).astype(np.float64)/32768; nsr=w.getframerate()
env=np.abs(nar); env=np.convolve(env,np.ones(int(0.08*nsr))/int(0.08*nsr),mode='same')
env_i=np.interp(np.arange(N)/SR, np.arange(len(env))/nsr, env, right=0)
duck=1-0.45*np.clip(env_i/0.15,0,1)
out*=duck[:,None]
# soft clip / normalize
peak=np.abs(out).max(); out=out/peak*0.9
out=np.tanh(out*1.3)/np.tanh(1.3)
ww=wave.open('sfx.wav','wb'); ww.setnchannels(2); ww.setsampwidth(2); ww.setframerate(SR); ww.writeframes((out*32767).astype(np.int16).tobytes()); ww.close()
print('sfx ok', N/SR)
