# Colonna sonora + sound design procedurali per "E se il Sole si spegnesse?".
# Legge timeline.json e narration.wav dalla cartella dello script, scrive audio.wav (48 kHz stereo, già mixato).
import json, numpy as np, wave, os
from scipy import signal
os.chdir(os.path.dirname(os.path.abspath(__file__)))
SR = 48000
TL = json.load(open('timeline.json')); S = {s['id']: s for s in TL['sentences']}
def wt(sid, prefix, k=0):
    ws = [w for w in S[sid]['words'] if w['w'].startswith(prefix)]
    return ws[k]
T = dict(LIGHT=S['light']['start'], ORBIT=S['orbit']['start'], COLD=S['cold']['start'], PLANTS=S['plants']['start'],
         DEEP=S['deep']['start'], HUMANS=S['humans']['start'], OUTRO=S['outro']['start'], CTA=S['cta']['start'], END=TL['total'])
T['TITLE'] = S['hook']['words'][0]['s']
T['OFF'] = wt('hook', "all'improvviso")['e'] + 0.12
T['CUTG'] = wt('light', 'Poi')['s'] - 0.15
T['DARK'] = wt('light', 'colpo')['s'] + 0.12
T['ORBIT2'] = wt('orbit', 'Il')['s'] - 0.1
T['WEEK'] = wt('cold', 'zero')['e'] + 0.1
T['COLDB'] = wt('cold', 'oceani')['s'] - 0.4
T['GELANO'] = wt('cold', 'gelano')['s']
T['PLANTB'] = wt('plants', 'e')['s'] - 0.06
T['WEDGE'] = T['DEEP'] + 0.9
T['DEEPB'] = wt('deep', 'Il')['s'] - 0.1
T['HUMB'] = wt('humans', 'piccole')['s'] - 0.1
T['REIGN'] = wt('outro', 'fortuna')['s'] + 0.05
T['OUTROB'] = wt('outro', 'Ma')['s'] - 0.1
N = int((T['END'] + 1.0) * SR)
rng = np.random.default_rng(23)
music = np.zeros((N, 2)); sfx = np.zeros((N, 2))

def env(n, a, d, s, r):
    e = np.zeros(n); na, nd, nr = max(1, int(a * SR)), int(d * SR), int(r * SR)
    e[:min(na, n)] = np.linspace(0, 1, na)[:min(na, n)]
    if nd > 0 and na < n: m = min(nd, n - na); e[na:na + m] = np.linspace(1, s, nd)[:m]
    if na + nd < n: e[na + nd:] = s
    if 0 < nr < n: e[-nr:] *= np.linspace(1, 0, nr)
    return e
def lp(x, fc, o=2): return signal.sosfilt(signal.butter(o, min(fc, SR * 0.45) / (SR / 2), 'low', output='sos'), x)
def hp(x, fc, o=2): return signal.sosfilt(signal.butter(o, fc / (SR / 2), 'high', output='sos'), x)
def bp(x, f1, f2, o=2): return signal.sosfilt(signal.butter(o, [f1 / (SR / 2), f2 / (SR / 2)], 'band', output='sos'), x)
def add(bus, sig, start, pan=0.0, gain=1.0):
    i = int(start * SR)
    if i < 0: sig = sig[-i:]; i = 0
    n = min(len(sig), N - i)
    if n <= 0: return
    l, r = np.sqrt(0.5 * (1 - pan)), np.sqrt(0.5 * (1 + pan))
    bus[i:i + n, 0] += sig[:n] * gain * l; bus[i:i + n, 1] += sig[:n] * gain * r
def tt(n): return np.arange(n) / SR
def saw(f, n, det=0.0): return 2 * ((tt(n) * (f + det)) % 1.0) - 1
def noise(n): return rng.standard_normal(n)

# ---------------- instruments
def pad(freqs, dur, gain=0.08, cut=900, a=1.2, r=1.5):
    n = int(dur * SR); out = np.zeros(n)
    for f in freqs:
        for det in (-0.6, 0, 0.7): out += saw(f, n, det * f / 440)
    return lp(out, cut, 2) * env(n, a, 0.3, 0.9, r) * gain / len(freqs)
def pluck(f, dur=0.6, gain=0.25, bright=2600, dec=6.0):
    n = int(dur * SR); t = tt(n)
    x = np.sin(2 * np.pi * f * t) + 0.45 * np.sin(4 * np.pi * f * t) * np.exp(-t * 9) + 0.2 * np.sin(6 * np.pi * f * t) * np.exp(-t * 14)
    return lp(x, bright, 1) * np.exp(-t * dec) * gain
def piano(f, dur=2.5, gain=0.2):
    n = int(dur * SR); t = tt(n); x = np.zeros(n)
    for k, a in enumerate([1, 0.5, 0.28, 0.16, 0.08]):
        x += a * np.sin(2 * np.pi * f * (k + 1) * t * (1 + 0.0004 * k)) * np.exp(-t * (1.6 + k * 1.1))
    return x * env(n, 0.004, 0.05, 1, 0.3) * gain
def bell(f, dur=2.0, gain=0.12): t = tt(int(dur * SR)); return (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 3) + 0.2 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 6)) * np.exp(-t * 2.2) * gain
def sub(f, dur, gain=0.5): n = int(dur * SR); return np.sin(2 * np.pi * f * tt(n)) * env(n, 0.01, 0.1, 0.8, 0.12) * gain
def kick(g=1.0):
    n = int(0.45 * SR); t = tt(n)
    x = np.sin(2 * np.pi * (150 * np.exp(-t * 22) + 42) * t) * np.exp(-t * 7) + 0.4 * lp(noise(n), 900) * np.exp(-t * 60)
    return np.tanh(x * 1.8) * g
def snare(g=0.8): n = int(0.32 * SR); t = tt(n); return (hp(noise(n), 1500) * np.exp(-t * 16) + 0.5 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25)) * g
def hat(g=0.25, d=0.07): n = int(d * SR); return hp(noise(n), 7000, 4) * np.exp(-tt(n) * (2.5 / d)) * g
def crash(g=0.5): n = int(3.0 * SR); return hp(noise(n), 3500) * np.exp(-tt(n) * 1.6) * g
def boom(g=1.0, f0=95, f1=26, dur=5.0):
    n = int(dur * SR); t = tt(n)
    x = np.sin(2 * np.pi * (f0 * np.exp(-t * 3) + f1) * t) * np.exp(-t * 1.3) + lp(noise(n), 6000) * np.exp(-t * 4.0) * 0.7 + lp(noise(n), 250) * np.exp(-t * 0.8) * 0.6
    return x * env(n, 0.004, 0.5, 1, 1.0) * g
def braam(f, dur, gain=0.7, major=False):
    n = int(dur * SR); t = tt(n); x = np.zeros(n)
    for det in (-1.5, -0.7, 0, 0.6, 1.4):
        x += saw(f, n, det) + 0.5 * saw(f * 2, n, det * 2) + 0.35 * saw(f * (2.52 if major else 2.38), n, det)
    cut = 120 + 2000 * np.exp(-t * 1.1)
    lo, mid, hi = lp(x, 180), lp(x, 700), lp(x, 2400)
    w = np.clip((cut - 180) / 520, 0, 1); w2 = np.clip((cut - 700) / 1700, 0, 1)
    return np.tanh((lo * (1 - w) + mid * w * (1 - w2) + hi * w2) * 1.4) * env(n, 0.12, 0.6, 0.7, 2.0) * gain
def riser(dur, g=0.4):
    n = int(dur * SR); t = tt(n); p = t / dur; nz = noise(n)
    x = lp(nz, 300) * (1 - p) + hp(lp(nz, 5000), 500) * p
    x += np.sin(2 * np.pi * (60 + 240 * p ** 2) * t) * 0.4
    return x * (0.02 + p ** 2.5) * g
def wind(dur, g=0.3, base=350, spread=500):
    n = int(dur * SR); t = tt(n); nz = noise(n)
    a = bp(nz, base, base + spread); b = bp(nz, base * 2.2, base * 2.2 + spread)
    m = 0.55 + 0.45 * np.sin(2 * np.pi * 0.13 * t + 1.0) * np.sin(2 * np.pi * 0.07 * t)
    return (a * m + b * (1 - m) * 0.6) * env(n, 1.5, 0.2, 1, 1.5) * g
def chirp(g=0.12):
    n = int((0.06 + rng.random() * 0.1) * SR); t = tt(n); p = t / t[-1]
    f0 = 2800 + rng.random() * 2500; f = f0 * (1 + 0.35 * np.sin(np.pi * p) * (1 if rng.random() < .5 else -1))
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.sin(np.pi * p) ** 2 * (0.6 + 0.4 * np.sin(2 * np.pi * 38 * t)) * g
def tick(hi=True, g=0.25):
    n = int(0.05 * SR); t = tt(n)
    return (hp(noise(n), 2500) * np.exp(-t * 250) * 0.6 + np.sin(2 * np.pi * (2400 if hi else 1800) * t) * np.exp(-t * 120)) * g
def crack(g=0.4):
    n = int(0.5 * SR); t = tt(n)
    x = hp(noise(n), 1200) * np.exp(-t * 40) * 0.8
    for k in range(3): x += np.sin(2 * np.pi * (420 - 260 * t * 2 + k * 170) * t) * np.exp(-t * (14 + k * 6)) * 0.35
    return x * g
def creak(g=0.2):
    n = int(1.2 * SR); t = tt(n); f = 140 + 60 * np.sin(2 * np.pi * 0.8 * t) + 30 * t
    ph = 2 * np.pi * np.cumsum(f) / SR; x = signal.sawtooth(ph) * (0.5 + 0.5 * np.sin(2 * np.pi * 23 * t))
    return lp(x, 900) * env(n, 0.05, 0.2, 0.8, 0.5) * g

Am = [110, 220, 261.63, 329.63]; F = [87.31, 174.61, 220, 261.63]; Cc = [130.81, 261.63, 329.63, 392]; G = [98, 196, 246.94, 293.66]; Dm = [73.42, 146.83, 174.61, 220]; Em = [82.41, 164.81, 196, 246.94]
BPM = 96; beat = 60 / BPM; bar = 4 * beat
def prog_pad(t0, t1, chords, gain, cut, oct=1):
    t = t0; k = 0
    while t < t1:
        fr = chords[k % len(chords)]; add(music, pad([f * oct for f in fr[1:]], min(bar, t1 - t) + 1.2, gain, cut), t); t += bar; k += 1
def prog_sub(t0, t1, chords, gain, div=2):
    t = t0; i = 0
    while t < t1:
        fr = chords[int((t - t0) // bar) % len(chords)]; add(music, sub(fr[0] / 2, beat / div * 0.9, gain * (1 if i % div == 0 else 0.7)), t); t += beat / div; i += 1
def prog_arp(t0, t1, chords, gain, oct=2, div=4, bright=2600):
    t = t0; i = 0; pat = [0, 1, 2, 1, 2, 0, 1, 2]
    while t < t1:
        fr = chords[int((t - t0) // bar) % len(chords)]; f = fr[1 + pat[i % 8]] * oct
        add(music, pluck(f, 0.5, gain, bright), t, np.sin(i * 0.7) * 0.5); t += beat / div; i += 1
def drums(t0, t1, kg=0.9, sg=0.6, hg=0.2, half=False):
    t = t0; i = 0
    while t < t1:
        b = i % 8
        if half:
            if b == 0: add(music, kick(kg), t)
            if b == 4 and sg > 0: add(music, snare(sg), t)
            if b % 2 == 0: add(music, hat(hg * 0.8), t, 0.3)
        else:
            if b in (0, 4) or (b == 6 and (i // 8) % 2 == 1): add(music, kick(kg), t)
            if b in (2, 6) and sg > 0: add(music, snare(sg), t)
            add(music, hat(hg * (1 if b % 2 == 0 else 0.6)), t, 0.3)
        t += beat / 2; i += 1

# ================= ARRANGEMENT =================
# HOOK: solar rumble + tension pad, title hit
n = int(T['OFF'] * SR) + SR // 4; t = tt(n)
rumble = lp(noise(n), 160) * 2.2 + 0.35 * np.sin(2 * np.pi * 38 * t) + bp(noise(n), 700, 2400) * 0.25 * (0.5 + 0.5 * np.sin(2 * np.pi * 3.1 * t))
add(sfx, rumble * env(n, 0.25, 0.1, 1, 0.12), 0.0, 0, 0.7)
add(music, pad(Am[1:], T['OFF'] + 0.6, 0.06, 1100, 0.3, 0.4), 0.0)
add(sfx, boom(0.9, 70, 30, 2.5), T['TITLE'] - 0.03)
# OFF: power-down
n = int(1.6 * SR); t = tt(n); f = 180 * np.exp(-t * 2.2) + 22; ph = 2 * np.pi * np.cumsum(f) / SR
xs = signal.sawtooth(ph) + 0.6 * signal.sawtooth(ph * 1.5); wv = np.exp(-t * 1.5)
pdown = (lp(xs, 1200) * wv + lp(xs, 110) * (1 - wv)) * env(n, 0.005, 0.2, 0.9, 0.6)
add(sfx, pdown, T['OFF'] - 0.05, 0, 0.55)
add(sfx, sub(40, 1.2, 0.6) * np.exp(-tt(int(1.2 * SR)) * 2), T['OFF'])
n = int(0.4 * SR); add(sfx, hp(lp(noise(n), 4000), 300) * np.linspace(1, 0, n) ** 2 * 0.4, T['OFF'])
# eerie drone after the Sun dies
add(music, pad([73.42, 110, 146.83], T['CUTG'] - T['OFF'] + 0.6, 0.05, 500, 1.0, 0.3), T['OFF'] + 0.2)
n = int((T['CUTG'] - T['OFF']) * SR); t = tt(n); add(music, np.sin(2 * np.pi * 1318.5 * t) * 0.012 * env(n, 1.5, 0.1, 1, 0.1), T['OFF'] + 0.3, 0.4)
# timer ticks (clock running) + heartbeat + riser
tk = T['OFF'] + 0.6; i = 0
while tk < T['CUTG'] - 0.05:
    add(sfx, tick(i % 2 == 0, 0.22), tk, 0.25 if i % 2 else -0.25); i += 1
    tk += 0.5 * (1 - 0.35 * (tk - T['OFF']) / (T['CUTG'] - T['OFF']))
hb = T['LIGHT']
while hb < T['CUTG'] - 0.3: add(music, kick(0.45), hb); add(music, kick(0.3), hb + 0.22); hb += beat * 2
add(sfx, riser(T['CUTG'] - T['LIGHT'], 0.35), T['LIGHT'])
# DAY: birds + soft wind, then lights out
add(sfx, wind(T['DARK'] - T['CUTG'] + 0.2, 0.08, 300, 400), T['CUTG'] - 0.05)
for k in range(9): add(sfx, chirp(0.1), T['CUTG'] + 0.05 + rng.random() * (T['DARK'] - T['CUTG'] - 0.1), rng.random() * 1.4 - 0.7)
add(sfx, boom(1.0, 60, 24, 4.0), T['DARK'] - 0.02)
n = int(0.03 * SR); add(sfx, hp(noise(n), 2000) * 0.5, T['DARK'] - 0.03)   # electric click
n = int(3.5 * SR); t = tt(n); add(sfx, np.sin(2 * np.pi * 3100 * t) * np.exp(-t * 0.9) * 0.02, T['DARK'] + 0.1, 0.2)  # ringing silence
add(sfx, wind(T['ORBIT'] - T['DARK'] + 1.0, 0.1, 200, 300), T['DARK'] + 0.3)
# ORBIT: minor pad, slow arp, gravity swells
prog_pad(T['ORBIT'], T['COLD'], [Dm, Am, F, Em], 0.075, 900)
prog_arp(T['ORBIT'] + bar * 0.5, T['COLD'], [Dm, Am, F, Em], 0.10, 2, 2, 1800)
sw = T['ORBIT']
while sw < T['ORBIT2']:
    n = int(1.6 * SR); t = tt(n); add(music, np.sin(2 * np.pi * 36.7 * t) * np.sin(np.pi * t / 1.6) ** 2 * 0.5, sw); sw += bar / 2
# crystallize shimmer at "il vero problema è il freddo"
for k, f in enumerate([1760, 2093, 2637, 3136, 3520]): add(music, bell(f, 2.5, 0.05), T['ORBIT2'] + 0.12 * k, (k - 2) * 0.3)
n = int(1.2 * SR); add(sfx, hp(noise(n), 4000) * np.linspace(0, 1, n) ** 2 * np.linspace(1, 0, n) * 0.25, T['ORBIT2'])
# COLD: icy wind, cracks, glass pad, pulses
add(sfx, wind(T['DEEP'] - T['ORBIT2'] + 1.5, 0.22, 380, 700), T['ORBIT2'])
prog_pad(T['COLD'], T['PLANTS'], [Am, F, Am, Em], 0.07, 1200)
prog_sub(T['COLD'], T['PLANTS'], [Am, F, Am, Em], 0.32, 2)
drums(T['COLD'] + bar, T['PLANTS'] - 0.2, 0.6, 0.0, 0.1, half=True)
n = int((T['PLANTS'] - T['COLD']) * SR); t = tt(n)
glass = sum(np.sin(2 * np.pi * f * t) * (0.5 + 0.5 * np.sin(2 * np.pi * (0.3 + k * 0.17) * t)) for k, f in enumerate([880, 1318.5, 1760, 2349]))
add(music, glass * env(n, 1.5, 0.1, 1, 1.0) * 0.012, T['COLD'])
for k in range(10): add(sfx, crack(0.35), T['COLD'] + 0.5 + rng.random() * (T['PLANTS'] - T['COLD'] - 0.8), rng.random() * 1.4 - 0.7)
for k in range(5): add(sfx, crack(0.5), T['GELANO'] - 0.1 + k * 0.17, (k - 2) * 0.35)
add(sfx, creak(0.18), T['COLDB'] + 0.3, -0.3); add(sfx, creak(0.15), T['WEEK'], 0.4)
# PLANTS: sad piano, rustle
melody = [(T['PLANTS'] + 0.05, 220.0), (T['PLANTS'] + 0.65, 261.63), (T['PLANTS'] + 1.25, 246.94), (T['PLANTS'] + 1.85, 196.0), (T['PLANTS'] + 2.45, 174.61), (T['PLANTS'] + 3.3, 164.81), (T['PLANTS'] + 4.1, 220.0)]
for s0, f in melody: add(music, piano(f, 3.0, 0.16), s0, -0.1); add(music, piano(f / 2, 3.0, 0.08), s0, 0.1)
add(music, pad([110, 130.81, 164.81], T['DEEP'] - T['PLANTS'] + 0.8, 0.05, 700), T['PLANTS'])
for k in range(14):
    n = int(0.35 * SR); t = tt(n); add(sfx, bp(noise(n), 1800, 6000) * np.sin(np.pi * t / t[-1]) * 0.12, T['PLANTS'] + rng.random() * (T['DEEP'] - T['PLANTS']), rng.random() * 1.6 - 0.8)
# DEEP: magma rumble, reveal swell, hope (major)
n = int((T['HUMANS'] - T['DEEP'] + 0.5) * SR); t = tt(n)
magma = lp(noise(n), 110) * 2.5 * (0.6 + 0.4 * np.sin(2 * np.pi * 0.4 * t)) + lp(noise(n), 600) * 0.25 * (np.sin(2 * np.pi * 1.7 * t) > 0.6)
add(sfx, magma * env(n, 1.0, 0.1, 1, 0.6), T['DEEP'], 0, 0.55)
add(sfx, riser(T['WEDGE'] + 0.4 - T['DEEP'], 0.25), T['DEEP'])
add(sfx, boom(0.6, 80, 30, 3.0), T['WEDGE'] + 0.4)
prog_pad(T['DEEP'], T['HUMANS'], [F, Cc, Am, G], 0.075, 1400)
prog_sub(T['DEEPB'], T['HUMANS'], [F, Cc, Am, G], 0.3, 1)
prog_arp(T['DEEPB'], T['HUMANS'], [F, Cc, Am, G], 0.11, 2, 2, 2200)
# HUMANS: hopeful build + reactor hum
prog_pad(T['HUMANS'], T['OUTRO'], [F, Cc, G, Am], 0.08, 1800)
prog_sub(T['HUMANS'], T['OUTRO'] - 0.3, [F, Cc, G, Am], 0.38, 2)
prog_arp(T['HUMANS'], T['OUTRO'] - 0.3, [F, Cc, G, Am], 0.15, 4, 4, 3000)
drums(T['HUMANS'] + bar * 0.5, T['OUTRO'] - 0.4, 0.85, 0.55, 0.22)
n = int((T['OUTRO'] - T['HUMANS']) * SR); t = tt(n)
add(sfx, (np.sin(2 * np.pi * 60 * t) + 0.5 * np.sin(2 * np.pi * 120 * t) + 0.2 * np.sin(2 * np.pi * 180 * t)) * env(n, 1.0, 0.1, 1, 0.5) * 0.05, T['HUMANS'])
add(sfx, riser(T['REIGN'] - (T['OUTRO'] - 1.2), 0.5), T['OUTRO'] - 1.2)
# OUTRO: re-ignition + sunrise
add(sfx, boom(1.2, 110, 30, 6.0), T['REIGN'] - 0.03)
add(music, braam(65.41, 5.5, 0.75, major=True), T['REIGN'])
add(music, crash(0.45), T['REIGN'])
prog_pad(T['REIGN'] + 0.5, T['END'] + 0.5, [Cc, G, Am, F], 0.08, 2600, 1)
for i, (f, dt) in enumerate([(659.26, 0), (783.99, 0.55), (880, 1.1), (783.99, 1.65), (659.26, 2.3), (587.33, 2.9), (523.25, 3.6), (659.26, 4.4), (783.99, 5.0)]):
    add(music, pluck(f, 1.4, 0.15, 2600, 3.5), T['OUTROB'] + 0.2 + dt, (i % 2 - 0.5) * 0.6)
for k in range(10): add(sfx, chirp(0.09), T['OUTROB'] + 1.0 + rng.random() * (T['END'] - T['OUTROB'] - 1.5), rng.random() * 1.4 - 0.7)
add(sfx, wind(T['END'] - T['OUTROB'] + 0.5, 0.05, 300, 400), T['OUTROB'])
add(music, bell(1046.5, 2.5, 0.12), T['CTA'] + 0.05, 0.3); add(music, bell(1318.5, 2.5, 0.09), T['CTA'] + 0.3, -0.3)
# transition whooshes at cuts
for c in [T['WIDE'] if 'WIDE' in T else T['OFF'] + 1.3, T['LIGHT'], T['ORBIT'], T['COLD'], T['COLDB'], T['PLANTS'], T['PLANTB'], T['DEEP'], T['DEEPB'], T['HUMANS'], T['HUMB'], T['OUTROB']]:
    n = int(0.5 * SR); t = tt(n); add(sfx, hp(lp(noise(n), 2200), 250) * np.sin(np.pi * t / 0.5) ** 2 * 0.45, c - 0.25, 0, 0.35)

# ---------------- reverb
def reverb(x, wet, dec=1.6):
    n = int(dec * SR); ir = noise(n) * np.exp(-tt(n) * (6.9 / dec)); ir = lp(ir, 5000, 1); ir /= np.sqrt(np.sum(ir ** 2)) * 6
    y = np.empty_like(x)
    for c in range(2): y[:, c] = signal.fftconvolve(x[:, c], ir)[:len(x)]
    return x * (1 - wet * 0.3) + y * wet
music = reverb(music, 0.38, 2.0); sfx = reverb(sfx, 0.18, 1.2)
# ---------------- narration
w = wave.open('narration.wav'); nar = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768; nsr = w.getframerate()
nar = signal.resample_poly(nar, SR, nsr); nar = hp(nar, 85, 2)
nar = nar + 0.35 * bp(nar, 1800, 5200)
envn = np.abs(signal.sosfilt(signal.butter(1, 30 / (SR / 2), 'low', output='sos'), np.abs(nar))) * 2.2
nar = nar * np.where(envn > 0.25, (0.25 / np.maximum(envn, 1e-6)) ** 0.6, 1.0); nar = nar / np.max(np.abs(nar)) * 0.92
narS = np.stack([nar, nar], 1); narS = np.pad(narS, ((0, max(0, N - len(narS))), (0, 0)))[:N]
narS = reverb(narS, 0.07, 0.9)
envd = signal.sosfilt(signal.butter(1, 12 / (SR / 2), 'low', output='sos'), np.abs(narS[:, 0])) * 3.0
duck = 1 - 0.5 * np.clip(envd / 0.12, 0, 1)
music = music / np.max(np.abs(music)); sfx = sfx / np.max(np.abs(sfx))
mix = narS + (music * 0.42 + sfx * 0.5) * duck[:, None]
mix = np.tanh(mix * 0.9) / np.tanh(0.9); mix = mix / np.max(np.abs(mix)) * 0.95
ww = wave.open('audio.wav', 'wb'); ww.setnchannels(2); ww.setsampwidth(2); ww.setframerate(SR); ww.writeframes((mix * 32767).astype(np.int16).tobytes()); ww.close()
print('audio ok', round(N / SR, 2), {k: round(v, 2) for k, v in T.items()})
