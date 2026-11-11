import json, numpy as np, wave, os
# Sound design procedurale per "E se il Sole diventasse una gigante rossa?"; scrive src/sfx.wav
os.chdir(os.path.dirname(os.path.abspath(__file__)))
SR=48000
TL=json.load(open('timeline.json')); S={s['id']:s for s in TL['sentences']}
T=dict(HOOK=0.0,FUEL=S['fuel']['start'],SWELL=S['swell']['start'],INNER=S['inner']['start'],
       EARTH=S['earth']['start'],ENGULF=S['engulf']['start'],NEBULA=S['nebula']['start'],
       DWARF=S['dwarf']['start'],CTA=S['cta']['start'],END=TL['total'])

# replica della curva del raggio solare per sincronizzare gli impatti di inghiottimento
def clamp(x,a,b): return max(a,min(b,x))
def lerp(a,b,t): return a+(b-a)*t
def easeIn(t): t=clamp(t,0,1); return t*t*t
def easeInOut(t):
    t=clamp(t,0,1); return 4*t*t*t if t<.5 else 1-((-2*t+2)**3)/2
def u01(t,a,b): return clamp((t-a)/(b-a),0,1)
def sunR(t):
    if t<T['SWELL']: return 1.0
    if t<T['INNER']: return lerp(1.0,2.6,easeIn(u01(t,T['SWELL'],T['INNER'])))
    if t<T['EARTH']: return lerp(2.6,5.4,easeInOut(u01(t,T['INNER'],T['EARTH'])))
    if t<T['ENGULF']: return lerp(5.4,6.5,easeInOut(u01(t,T['EARTH'],T['ENGULF'])))
    if t<T['NEBULA']: return lerp(6.5,7.9,easeInOut(u01(t,T['ENGULF'],T['NEBULA'])))
    return 7.9
PLANETS=[('mercury',3.35,0.11),('venus',4.95,0.20),('earth',7.05,0.24)]
engulf={}
for nm,r,sz in PLANETS:
    tt=T['NEBULA']
    t=0.0
    while t<=T['NEBULA']:
        if sunR(t)>=r-sz*0.6: tt=t; break
        t+=0.01
    engulf[nm]=tt

N=int((T['END']+1.0)*SR); t=np.arange(N)/SR
rng=np.random.default_rng(11)
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

# --- 1. drone spaziale (tutto il video)
def drone(dur,f0,gain):
    n=int(dur*SR); tt=np.arange(n)/SR; sig=np.zeros(n)
    for k,(mult,det) in enumerate([(1,0),(1,0.4),(2,-0.3),(3,0.2),(0.5,0.1)]):
        sig+=np.sin(2*np.pi*(f0*mult+det)*tt+0.3*np.sin(2*np.pi*0.07*tt+k))/(1+k)
    lfo=0.75+0.25*np.sin(2*np.pi*0.05*tt); return smooth(sig*lfo,600)*gain
d1=drone(T['END']+1,52,0.24); d1*=env_ad(len(d1),2.0,2.5); add(d1,0,0,1)
d2=drone(T['END']+1,78,0.11); d2*=env_ad(len(d2),4.0,2.5); add(d2,0,0.3,1)

# --- 2. hook: colpo profondo + whoosh
n=int(2.5*SR); tt=np.arange(n)/SR
hit=np.sin(2*np.pi*(60*np.exp(-tt*4)+32)*tt)*np.exp(-tt*2.2)*0.8+smooth(rng.standard_normal(n),1500)*np.exp(-tt*7)*0.5
add(hit,0.95,0,0.7)
n=int(1.0*SR); tt=np.arange(n)/SR; add(smooth(rng.standard_normal(n),2500)*(tt/1.0)**2*0.5,0.0,0,0.5)

# --- 3. riser di dilatazione (SWELL -> ENGULF): rumore e seno ascendenti, calore crescente
n=int((T['ENGULF']-T['SWELL'])*SR); tt=np.arange(n)/SR; p=tt/tt[-1]
nz=rng.standard_normal(n)
riser=(smooth(nz,220)*(1-p)+smooth(nz,2600)*p)*(0.02+0.30*p**3)
riser+=np.sin(2*np.pi*(38+70*p**2)*tt)*(0.05+0.28*p**2)
add(riser*env_ad(n,1.2,0.1),T['SWELL'])
# letto di fusione: rumore filtrato "ribollente" durante EARTH
n=int((T['NEBULA']-T['EARTH'])*SR); bed=smooth(rng.standard_normal(n),140)*env_ad(n,1.0,1.0)*1.1; add(bed,T['EARTH'],0,1)

# --- 4. impatti di inghiottimento (Mercurio, Venere, Terra)
def swallow(dur,f,decay,ng):
    n=int(dur*SR); tt=np.arange(n)/SR
    s=np.sin(2*np.pi*(f*np.exp(-tt*decay*0.6)+f*0.4)*tt)*np.exp(-tt*decay)
    s+=smooth(rng.standard_normal(n),ng)*np.exp(-tt*decay*1.4)*0.6
    return s
add(swallow(1.6,74,3.0,2200),engulf['mercury']-0.05,-0.4,0.42)
add(swallow(2.0,62,2.4,1800),engulf['venus']-0.05,0.4,0.55)
# Terra: grande boato all'inghiottimento
n=int(5.0*SR); tt=np.arange(n)/SR
boom=np.sin(2*np.pi*(88*np.exp(-tt*3)+26)*tt)*np.exp(-tt*1.5)
burst=smooth(rng.standard_normal(n),5200)*np.exp(-tt*4.2)*0.9+smooth(rng.standard_normal(n),300)*np.exp(-tt*0.9)*0.6
add((boom+burst*0.8)*env_ad(n,0.004,1.0),engulf['earth']-0.02,0,0.95)

# --- 5. nebulosa (NEBULA): espulsione soffiata + pad cristallino in espansione
n=int(3.2*SR); tt=np.arange(n)/SR; p=tt/3.2
whoosh=smooth(rng.standard_normal(n),2000)*np.sin(np.pi*p)**1.3*0.5
add(whoosh,T['NEBULA']-0.15,0,0.5)
n=int((T['END']-T['NEBULA']+1.0)*SR); tt=np.arange(n)/SR
pad=np.zeros(n)
for f,amp in [(329.6,1),(392,0.8),(493.9,0.7),(659.3,0.5),(783.9,0.35),(246.9,0.8)]:
    pad+=np.sin(2*np.pi*f*tt+0.5*np.sin(2*np.pi*0.3*tt))*amp*(0.6+0.4*np.sin(2*np.pi*(0.1+f/5000)*tt))
pad=smooth(pad,3000)*env_ad(n,2.2,2.5)*0.03; add(pad,T['NEBULA'],0,1)

# --- 6. nana bianca (DWARF): accordo caldo e lontano + chime
n=int((T['END']-T['DWARF']+1)*SR); tt=np.arange(n)/SR
ch=np.zeros(n)
for f,amp in [(130.8,1),(196,0.7),(261.6,0.6),(329.6,0.4),(392,0.3)]:
    ch+=np.sin(2*np.pi*f*tt)*amp*(0.8+0.2*np.sin(2*np.pi*0.2*tt+f))
ch=smooth(ch,1100)*env_ad(n,2.2,2.6)*0.045; add(ch,T['DWARF'],0,1)
n=int(1.8*SR); tt=np.arange(n)/SR
chime=(np.sin(2*np.pi*1046.5*tt)+0.5*np.sin(2*np.pi*2093*tt))*np.exp(-tt*3)*0.11; add(chime,T['CTA'],0.2)

# --- 7. ducking sotto la narrazione
w=wave.open('narration.wav'); nar=np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16).astype(np.float64)/32768; nsr=w.getframerate()
env=np.abs(nar); env=np.convolve(env,np.ones(int(0.08*nsr))/int(0.08*nsr),mode='same')
env_i=np.interp(np.arange(N)/SR, np.arange(len(env))/nsr, env, right=0)
out*=(1-0.45*np.clip(env_i/0.15,0,1))[:,None]
peak=np.abs(out).max(); out=out/peak*0.9
out=np.tanh(out*1.3)/np.tanh(1.3)
ww=wave.open('sfx.wav','wb'); ww.setnchannels(2); ww.setsampwidth(2); ww.setframerate(SR); ww.writeframes((out*32767).astype(np.int16).tobytes()); ww.close()
print('sfx ok', round(N/SR,2),'s | engulf:', {k:round(v,2) for k,v in engulf.items()})
