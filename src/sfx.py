import json, numpy as np, wave, os
# Sound design per "E se gli oceani sparissero?"; scrive src/sfx.wav
os.chdir(os.path.dirname(os.path.abspath(__file__)))
SR=48000
TL=json.load(open('timeline.json')); S={s['id']:s for s in TL['sentences']}
T=dict(HOOK=0.0,COVER=S['cover']['start'],DRAIN=S['drain']['start'],REVEAL=S['reveal']['start'],
       CLIMATE=S['climate']['start'],LIFE=S['life']['start'],DESERT=S['desert']['start'],
       OUTRO=S['outro']['start'],CTA=S['cta']['start'],END=TL['total'])
def clamp(x,a,b): return max(a,min(b,x))
def lerp(a,b,t): return a+(b-a)*t
def easeInOut(t):
    t=clamp(t,0,1); return 4*t*t*t if t<.5 else 1-((-2*t+2)**3)/2
def u01(t,a,b): return clamp((t-a)/(b-a),0,1)
def drain(t):
    if t<T['DRAIN']: return 0.0
    if t<T['REVEAL']: return lerp(0,0.5,easeInOut(u01(t,T['DRAIN'],T['REVEAL'])))
    if t<T['CLIMATE']: return lerp(0.5,0.76,easeInOut(u01(t,T['REVEAL'],T['CLIMATE'])))
    if t<T['LIFE']: return lerp(0.76,0.88,u01(t,T['CLIMATE'],T['LIFE']))
    if t<T['DESERT']: return lerp(0.88,0.95,u01(t,T['LIFE'],T['DESERT']))
    if t<T['OUTRO']: return lerp(0.95,1.0,u01(t,T['DESERT'],T['OUTRO']))
    return lerp(1.0,0.0,easeInOut(u01(t,T['OUTRO'],T['OUTRO']+3.2)))

N=int((T['END']+1.0)*SR); t=np.arange(N)/SR
rng=np.random.default_rng(23)
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
def smooth(x,fc):
    X=np.fft.rfft(x); f=np.fft.rfftfreq(len(x),1/SR); X*=1/np.sqrt(1+(f/fc)**4); return np.fft.irfft(X,len(x))
def bandpass(x,flo,fhi):
    X=np.fft.rfft(x); f=np.fft.rfftfreq(len(x),1/SR)
    X*= (1/np.sqrt(1+(flo/np.maximum(f,1e-6))**4)) * (1/np.sqrt(1+(f/fhi)**4))
    return np.fft.irfft(X,len(x))

# --- drone spaziale
def drone(dur,f0,gain):
    n=int(dur*SR); tt=np.arange(n)/SR; sig=np.zeros(n)
    for k,(mult,det) in enumerate([(1,0),(1,0.4),(2,-0.3),(3,0.2),(0.5,0.1)]):
        sig+=np.sin(2*np.pi*(f0*mult+det)*tt+0.3*np.sin(2*np.pi*0.07*tt+k))/(1+k)
    lfo=0.75+0.25*np.sin(2*np.pi*0.05*tt); return smooth(sig*lfo,600)*gain
d1=drone(T['END']+1,54,0.22); d1*=env_ad(len(d1),2.0,2.5); add(d1,0,0,1)
d2=drone(T['END']+1,80,0.10); d2*=env_ad(len(d2),4.0,2.5); add(d2,0,0.3,1)

# --- ambiente oceanico (risacca) modulato dalla presenza d'acqua = 1-drain
water=np.array([1.0-drain(tt) for tt in np.arange(0,N/SR,0.02)])
water_i=np.interp(t, np.arange(len(water))*0.02, water)
sea=smooth(rng.standard_normal(N),380)
waves=0.6+0.4*np.sin(2*np.pi*0.12*t+0.8*np.sin(2*np.pi*0.05*t))  # moto ondoso lento
sea=sea*waves*water_i*0.5
out[:,0]+=sea; out[:,1]+=np.roll(sea,1500)

# --- hook: colpo profondo + whoosh
n=int(2.4*SR); tt=np.arange(n)/SR
hit=np.sin(2*np.pi*(58*np.exp(-tt*4)+30)*tt)*np.exp(-tt*2.2)*0.8+smooth(rng.standard_normal(n),1400)*np.exp(-tt*7)*0.45
add(hit,0.95,0,0.65)
n=int(1.0*SR); tt=np.arange(n)/SR; add(smooth(rng.standard_normal(n),2400)*(tt/1.0)**2*0.45,0.0,0,0.45)

# --- evaporazione: sibili di vapore ascendenti (DRAIN -> REVEAL)
k=0
while True:
    st=T['DRAIN']+0.3+k*0.55
    if st>T['REVEAL']+1.0: break
    dur=0.5+rng.random()*0.5; n=int(dur*SR); tt=np.arange(n)/SR; p=tt/dur
    hiss=bandpass(rng.standard_normal(n),1800,7000)*np.sin(np.pi*p)**1.4*(0.18+0.18*rng.random())
    hiss*= (0.4+0.6*np.sin(2*np.pi*(2+4*p)*tt)*0.5+0.5)
    add(hiss,st,rng.random()*1.4-0.7,0.5); k+=1

# --- reveal: pad di meraviglia
n=int((T['CLIMATE']-T['REVEAL']+1.2)*SR); tt=np.arange(n)/SR
pad=np.zeros(n)
for f,amp in [(130.8,1),(196,0.7),(261.6,0.7),(392,0.5),(523.3,0.3)]:
    pad+=np.sin(2*np.pi*f*tt+0.4*np.sin(2*np.pi*0.25*tt))*amp*(0.7+0.3*np.sin(2*np.pi*(0.1+f/6000)*tt))
pad=smooth(pad,1600)*env_ad(n,2.2,2.2)*0.035; add(pad,T['REVEAL']-0.3,0,1)

# --- climate: tensione in crescita (CLIMATE -> DESERT)
n=int((T['DESERT']-T['CLIMATE'])*SR); tt=np.arange(n)/SR; p=tt/tt[-1]
riser=bandpass(rng.standard_normal(n),300,2600)*(0.04+0.22*p**2)
riser+=np.sin(2*np.pi*(42+30*p**2)*tt)*(0.04+0.12*p**2)
add(riser*env_ad(n,1.0,0.2),T['CLIMATE'])

# --- desert: vento di polvere con sweep (DESERT -> OUTRO)
n=int((T['OUTRO']-T['DESERT']+0.8)*SR); tt=np.arange(n)/SR
lfo=0.5+0.5*np.sin(2*np.pi*0.18*tt+0.6*np.sin(2*np.pi*0.07*tt))
wind=bandpass(rng.standard_normal(n),300,2200)*(0.12+0.20*lfo)
wind+=bandpass(rng.standard_normal(n),600,1600)*0.08*np.sin(2*np.pi*0.11*tt)
add(wind*env_ad(n,1.2,1.4),T['DESERT'],0,1)

# --- outro: accordo caldo e speranzoso + chime al CTA
n=int((T['END']-T['OUTRO']+1)*SR); tt=np.arange(n)/SR
ch=np.zeros(n)
for f,amp in [(146.8,1),(220,0.7),(293.7,0.6),(369.99,0.45),(440,0.3)]:
    ch+=np.sin(2*np.pi*f*tt)*amp*(0.8+0.2*np.sin(2*np.pi*0.2*tt+f))
ch=smooth(ch,1300)*env_ad(n,2.2,2.6)*0.05; add(ch,T['OUTRO'],0,1)
n=int(1.8*SR); tt=np.arange(n)/SR
chime=(np.sin(2*np.pi*1046.5*tt)+0.5*np.sin(2*np.pi*1568*tt))*np.exp(-tt*3)*0.11; add(chime,T['CTA'],0.2)

# --- ducking sotto la narrazione
w=wave.open('narration.wav'); nar=np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16).astype(np.float64)/32768; nsr=w.getframerate()
env=np.abs(nar); env=np.convolve(env,np.ones(int(0.08*nsr))/int(0.08*nsr),mode='same')
env_i=np.interp(np.arange(N)/SR, np.arange(len(env))/nsr, env, right=0)
out*=(1-0.42*np.clip(env_i/0.15,0,1))[:,None]
peak=np.abs(out).max(); out=out/peak*0.9
out=np.tanh(out*1.25)/np.tanh(1.25)
ww=wave.open('sfx.wav','wb'); ww.setnchannels(2); ww.setsampwidth(2); ww.setframerate(SR); ww.writeframes((out*32767).astype(np.int16).tobytes()); ww.close()
print('sfx ok', round(N/SR,2),'s')
