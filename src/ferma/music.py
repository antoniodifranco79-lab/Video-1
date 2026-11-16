# Colonna sonora + sound design procedurali per "E se la Terra smettesse di girare?".
# Legge timeline.json e narration.wav dalla cartella dello script, scrive audio.wav (48 kHz stereo, già mixato).
import json, numpy as np, wave, os
from scipy import signal
os.chdir(os.path.dirname(os.path.abspath(__file__)))
SR = 48000
TL = json.load(open('timeline.json')); S = {s['id']: s for s in TL['sentences']}
def wt(sid, prefix, k=0):
    ws = [w for w in S[sid]['words'] if w['w'].startswith(prefix)]
    return ws[k]
T = dict(SPEED=S['speed']['start'], WINDS=S['winds']['start'], WAVES=S['waves']['start'], BULGE=S['bulge']['start'], DAY=S['day']['start'],
         ZONE=S['zone']['start'], OUTRO=S['outro']['start'], CTA=S['cta']['start'], END=TL['total'])
T['TITLE'] = S['hook']['words'][0]['s']
T['STOP'] = wt('hook', 'ferma')['s']; T['TUNO'] = wt('hook', 'Tu')['s'] - 0.08
T['FRENA'] = wt('speed', 'Se')['s'] - 0.1; T['COLPO'] = wt('speed', 'colpo')['s']; T['TUTTO'] = wt('speed', 'tutto')['s'] - 0.1
T['VENTI'] = wt('winds', 'venti')['s'] - 0.1; T['WINDB'] = wt('winds', 'spazzano')['s']
T['TSU'] = wt('waves', 'Tsunami')['s'] - 0.1; T['COSTE'] = wt('waves', 'penetrano')['s'] - 0.1; T['LAND'] = T['TSU'] + (-212 + 610) / 165
T['SENZA'] = wt('bulge', 'Senza')['s'] - 0.1; T['MIGR'] = wt('bulge', 'gli')['s'] - 0.1
T['LUCE'] = wt('day', 'sei')['s'] - 0.1; T['NOTTE'] = wt('day', 'sei', 1)['s'] - 0.05
T['TRAM'] = wt('zone', 'in')['s'] - 0.1; T['MONDO'] = wt('outro', 'Il')['s'] - 0.1; T['BH'] = wt('cta', 'un')['s'] - 0.05
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
def screech(dur=0.6, g=0.4):
    n = int(dur * SR); t = tt(n); x = np.zeros(n)
    for k, f0 in enumerate([2400, 3100, 3900]):
        f = f0 * (1 - 0.35 * t / dur); ph = 2 * np.pi * np.cumsum(f) / SR
        x += np.sin(ph + 3 * np.sin(2 * np.pi * 47 * t)) * (0.6 / (k + 1))
    x += bp(noise(n), 2000, 6000) * 0.5
    return x * env(n, 0.01, 0.1, 0.9, 0.25) * g
def glass(g=0.3):
    n = int(0.9 * SR); t = tt(n); x = hp(noise(n), 4000) * np.exp(-t * 9) * 0.7
    for f in rng.uniform(3000, 9000, 7): x += np.sin(2 * np.pi * f * t) * np.exp(-t * (8 + rng.random() * 10)) * 0.12
    return x * g
def clank(g=0.3):
    n = int(0.5 * SR); t = tt(n); x = np.zeros(n)
    for f in rng.uniform(250, 1400, 4): x += np.sin(2 * np.pi * f * t) * np.exp(-t * (10 + rng.random() * 15))
    return (x * 0.4 + lp(noise(n), 1500) * np.exp(-t * 30)) * g
def collapse(dur=3.0, g=0.8):
    n = int(dur * SR); t = tt(n); x = lp(noise(n), 180) * 2.5 * np.exp(-t * 0.9) + lp(noise(n), 900) * np.exp(-t * 2.5) * 0.8
    for k in range(10):
        s0 = int(rng.random() * n * 0.7); m = min(n - s0, int(0.25 * SR)); x[s0:s0 + m] += lp(noise(m), 600 + rng.random() * 1500) * np.exp(-tt(m) * 18) * 0.9
    return x * env(n, 0.05, 0.3, 1, 0.8) * g
def swoosh(dur=1.2, g=0.3, rise=True):
    n = int(dur * SR); t = tt(n); p = t / dur; nz = noise(n)
    a = lp(nz, 800); b = hp(lp(nz, 5000), 600); w = p if rise else 1 - p
    return (a * (1 - w) + b * w) * np.sin(np.pi * p) ** 2 * g
# HOOK: spinning planet, epic build, hard brake
prog_pad(0.0, T['STOP'] + 0.3, [Dm, Dm, F, Cc], 0.07, 1300)
prog_sub(0.3, T['STOP'], [Dm, Dm, F, Cc], 0.4, 2)
prog_arp(0.3, T['STOP'], [Dm, Dm, F, Cc], 0.11, 2, 4, 2400)
k = 0.0
while k < T['STOP'] - 0.3: add(sfx, swoosh(1.1, 0.25), k, -0.4 + 0.8 * ((k / 1.1) % 2)); k += 1.1
for i, s0 in enumerate(np.arange(T['TITLE'], T['STOP'] - 0.2, beat)): add(music, kick(0.55 + 0.1 * (i % 2)), s0)
add(sfx, boom(0.8, 70, 30, 2.0), T['TITLE'] - 0.03)
add(sfx, screech(0.55, 0.45), T['STOP'] - 0.3, 0.2)
add(sfx, boom(1.3, 110, 24, 5.0), T['STOP'] - 0.02)
add(music, crash(0.5), T['STOP'])
# TU NO: wind blast + debris
add(sfx, wind(T['WINDS'] - T['TUNO'] + 0.5, 0.35, 250, 900), T['TUNO'] - 0.05)
add(sfx, swoosh(0.9, 0.7, True), T['TUNO'] - 0.2)
for k in range(8): add(sfx, clank(0.3), T['TUNO'] + 0.1 + rng.random() * 0.9, rng.random() * 1.6 - 0.8)
for k in range(3): add(sfx, glass(0.25), T['TUNO'] + 0.2 + rng.random() * 0.8, rng.random() * 1.2 - 0.6)
# SPEED: tense pulse
prog_pad(T['SPEED'], T['WINDS'], [Dm, Am, F, Em], 0.07, 1000)
prog_sub(T['SPEED'], T['TUTTO'], [Dm, Am, F, Em], 0.38, 4)
prog_arp(T['SPEED'], T['TUTTO'], [Dm, Am, F, Em], 0.12, 4, 4, 3000)
add(sfx, swoosh(1.0, 0.35), T['SPEED'] + 0.1)
add(sfx, boom(0.9, 90, 28, 3.0), T['COLPO']); add(music, crash(0.35), T['COLPO'])
# TUTTO: debris, cars, glass
drums(T['TUTTO'], T['WINDS'] - 0.2, 0.85, 0.55, 0.25)
for k in range(22): add(sfx, clank(0.32), T['TUTTO'] + rng.random() * (T['WINDS'] - T['TUTTO']), rng.random() * 1.6 - 0.8)
for k in range(6): add(sfx, glass(0.22), T['TUTTO'] + rng.random() * (T['WINDS'] - T['TUTTO']), rng.random() * 1.6 - 0.8)
# WINDS: global storm, wall of debris, collapses
add(sfx, riser(T['VENTI'] - T['WINDS'] + 0.2, 0.4), T['WINDS'])
add(sfx, wind(T['WAVES'] - T['VENTI'] + 0.6, 0.6, 180, 1400), T['VENTI'] - 0.1)
add(sfx, boom(1.0, 80, 26, 4.0), T['VENTI'])
prog_pad(T['VENTI'], T['WAVES'], [Dm, F, Cc, Am], 0.08, 1500)
drums(T['VENTI'], T['WAVES'] - 0.3, 1.0, 0.75, 0.28)
prog_sub(T['VENTI'], T['WAVES'] - 0.3, [Dm, F, Cc, Am], 0.45, 2)
for k in range(8): add(sfx, collapse(2.6, 0.55), T['WINDB'] + 0.25 + k * 0.32, (k % 3 - 1) * 0.5)
for k in range(10): add(sfx, glass(0.25), T['VENTI'] + rng.random() * (T['WAVES'] - T['VENTI']), rng.random() * 1.6 - 0.8)
# WAVES: ocean surge, tsunami roar, landfall crash
n = int((T['BULGE'] - T['WAVES'] + 0.5) * SR); t = tt(n); p = np.clip((t - (T['TSU'] - T['WAVES'])) / (T['LAND'] - T['TSU']), 0, 1)
roar = lp(noise(n), 140) * 2.4 * (0.4 + 0.6 * np.sin(2 * np.pi * 0.25 * t) ** 2) + bp(noise(n), 300, 1800) * (0.15 + 0.9 * p ** 2)
add(sfx, roar * env(n, 0.8, 0.1, 1, 0.8), T['WAVES'], 0, 0.7)
add(sfx, riser(T['LAND'] - T['TSU'], 0.45), T['TSU'])
add(sfx, boom(1.4, 70, 22, 6.0), T['LAND']); add(music, crash(0.5), T['LAND'])
n = int((T['BULGE'] - T['LAND']) * SR); add(sfx, bp(noise(n), 200, 2500) * env(n, 0.05, 0.3, 0.8, 1.0) * 0.8, T['LAND'])
for k in range(10): add(sfx, clank(0.3), T['LAND'] + rng.random() * (T['BULGE'] - T['LAND']), rng.random() * 1.6 - 0.8)
prog_pad(T['WAVES'], T['BULGE'], [Dm, Am, F, Am], 0.075, 900)
prog_sub(T['TSU'], T['BULGE'] - 0.3, [Dm, Am, F, Am], 0.4, 2)
drums(T['TSU'], T['BULGE'] - 0.3, 0.9, 0.6, 0.22, half=True)
# BULGE / MIGRATION: awe
add(sfx, swoosh(1.6, 0.4, False), T['BULGE'] - 0.4)
add(sfx, boom(0.6, 60, 28, 3.0), T['BULGE'])
prog_pad(T['BULGE'], T['DAY'], [F, Cc, G, Am], 0.08, 2200)
prog_arp(T['SENZA'], T['DAY'], [F, Cc, G, Am], 0.1, 4, 2, 2600)
add(sfx, swoosh(2.4, 0.3, True), T['SENZA'] + 0.2)
n = int((T['DAY'] - T['MIGR']) * SR); t = tt(n); add(sfx, lp(noise(n), 400) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.3 * t)) * env(n, 1.0, 0.1, 1, 0.8) * 0.6, T['MIGR'])
for k, f in enumerate([1046.5, 1318.5, 1568, 2093]): add(music, bell(f, 2.5, 0.06), T['MIGR'] + 0.2 + k * 0.5, (k - 1.5) * 0.3)
# DAY: a year in seconds
tk = T['DAY'] + 0.25; i = 0
while tk < T['LUCE'] - 0.15: add(sfx, tick(i % 2 == 0, 0.18), tk, 0.25 if i % 2 else -0.25); i += 1; tk += 0.12
prog_pad(T['DAY'], T['ZONE'], [Am, Em, F, Cc], 0.07, 1400)
n = int((T['NOTTE'] - T['LUCE']) * SR); t = tt(n)
heat = (np.sin(2 * np.pi * 3520 * t) * np.sin(2 * np.pi * 3527 * t) * 0.02 + bp(noise(n), 2500, 7000) * 0.05 * (np.sin(2 * np.pi * 9 * t) > 0.7)) * env(n, 0.2, 0.1, 1, 0.3)
add(sfx, heat, T['LUCE'])
add(sfx, wind(T['ZONE'] - T['NOTTE'] + 0.5, 0.25, 400, 800), T['NOTTE'])
for k in range(5): add(sfx, clank(0.18), T['NOTTE'] + rng.random() * (T['ZONE'] - T['NOTTE']), rng.random() * 1.4 - 0.7)
# ZONE + eternal sunset: hope
prog_pad(T['ZONE'], T['OUTRO'], [F, Cc, Am, G], 0.08, 1800)
for s0, f in zip(np.arange(T['ZONE'] + 0.1, T['OUTRO'] - 0.4, 0.75), [523.25, 659.26, 783.99, 659.26, 587.33, 523.25, 659.26, 880, 783.99, 659.26, 587.33, 523.25]):
    add(music, piano(f, 2.5, 0.12), s0, 0.1); add(music, piano(f / 2, 2.5, 0.06), s0, -0.1)
add(sfx, wind(T['OUTRO'] - T['TRAM'] + 0.3, 0.06, 300, 300), T['TRAM'])
for k in range(7): add(sfx, chirp(0.06), T['TRAM'] + 0.3 + rng.random() * (T['OUTRO'] - T['TRAM'] - 0.6), rng.random() * 1.4 - 0.7)
# OUTRO: the world spins again
n = int(1.8 * SR); t = tt(n); f = 60 + 200 * (t / 1.8) ** 2; ph = 2 * np.pi * np.cumsum(f) / SR
add(sfx, lp(signal.sawtooth(ph), 1500) * env(n, 0.3, 0.1, 1, 0.4) * 0.2 + swoosh(1.8, 0.35, True), T['OUTRO'])
prog_pad(T['OUTRO'], T['BH'] + 0.3, [Cc, G, Am, F], 0.08, 2600)
prog_sub(T['OUTRO'] + 1.0, T['BH'] - 0.2, [Cc, G, Am, F], 0.32, 1)
prog_arp(T['OUTRO'] + 1.0, T['BH'] - 0.2, [Cc, G, Am, F], 0.12, 4, 4, 3000)
drums(T['OUTRO'] + 1.6, T['BH'] - 0.3, 0.75, 0.45, 0.2)
add(music, bell(1046.5, 2.5, 0.12), T['MONDO'] + 0.2, 0.3); add(music, bell(1568, 2.5, 0.08), T['MONDO'] + 0.45, -0.3)
# BLACK HOLE teaser
add(sfx, boom(1.3, 55, 20, 5.0), T['BH']); add(music, braam(36.71, T['END'] - T['BH'] + 0.5, 0.6), T['BH'])
n = int((T['END'] - T['BH']) * SR); t = tt(n); p = t / t[-1]
add(sfx, (lp(noise(n), 90) * 2.5 + bp(noise(n), 600, 3000) * 0.3 * p ** 2) * env(n, 0.3, 0.1, 1, 0.5) * 0.6, T['BH'])
hb = T['BH'] + 0.6
while hb < T['END'] - 0.5: add(music, kick(0.5), hb); add(music, kick(0.32), hb + 0.24); hb += 0.95

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
