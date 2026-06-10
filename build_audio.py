#!/usr/bin/env python3
"""
Synthesize the ambience bed: deep stadium crowd rumble + rhythmic sub-bass that
pulses on the beat, with accent 'drops' on each segment change so the visual
cuts land on the low end. Writes assets/ambience.wav (stereo, 44.1k).
"""
import numpy as np, wave, struct, os

ROOT = os.path.dirname(os.path.abspath(__file__))
SR   = 44100
DUR  = 92.92
N    = int(SR*DUR)
t    = np.arange(N)/SR
rng  = np.random.default_rng(7)

# ---- deep crowd rumble: lowpassed noise with a slow swell -------------------
def onepole_lp(x, a):
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):           # vectorised-ish via lfilter would be faster
        acc += a*(x[i]-acc); y[i] = acc
    return y

noise = rng.standard_normal(N).astype(np.float32)
# cascade a cheap lowpass using cumulative IIR via scipy-free lfilter
from numpy import convolve
# simple moving-average lowpass cascades -> heavy rumble
def smooth(x, k):
    c = np.ones(k)/k
    return np.convolve(x, c, mode="same")
rumble = smooth(smooth(noise, 220), 90)
rumble /= np.max(np.abs(rumble))+1e-9
swell  = 0.6 + 0.4*np.sin(2*np.pi*t/14.0)          # slow breathing swell
crowd  = rumble * swell * 0.16

# faint mid 'crowd texture' (bandpassed-ish) very low
tex = smooth(rng.standard_normal(N).astype(np.float32), 12)
tex -= smooth(tex, 200)
tex /= np.max(np.abs(tex))+1e-9
crowd += tex * 0.025

# ---- rhythmic sub-bass ------------------------------------------------------
BPM  = 84.0
beat = 60.0/BPM
subf = 50.0                      # sub frequency (Hz)
sub  = np.zeros(N, dtype=np.float32)

# segment-start times (seconds) -> bigger accent drops there
seg_starts = [0.0, 16.5, 32.9, 46.4, 59.2, 71.1, 84.0]

nbeats = int(DUR/beat)+1
for b in range(nbeats):
    bt = b*beat
    i0 = int(bt*SR)
    if i0 >= N: break
    accent = 1.0
    if any(abs(bt-s) < 0.18 for s in seg_starts): accent = 1.9   # drop on cut
    length = int(0.45*SR)
    idx = np.arange(length)
    env = np.exp(-idx/(0.16*SR))             # decay
    env[:int(0.008*SR)] *= np.linspace(0,1,int(0.008*SR))  # soft attack
    local = t[i0:i0+length] if i0+length<=N else t[i0:N]
    L = len(local)
    wave_seg = np.sin(2*np.pi*subf*(local-bt)).astype(np.float32)
    # add 2nd harmonic for warmth
    wave_seg += 0.25*np.sin(2*np.pi*2*subf*(local-bt)).astype(np.float32)
    sub[i0:i0+L] += (wave_seg*env[:L]*0.42*accent).astype(np.float32)

# big cinematic sub drop at the very start (and tail for the loop)
def drop(at):
    i0 = int(at*SR); length = int(1.2*SR)
    idx = np.arange(length); L = min(length, N-i0)
    if L <= 0: return
    f = np.linspace(70, 38, L)
    ph = 2*np.pi*np.cumsum(f)/SR
    env = np.exp(-idx[:L]/(0.5*SR))
    sub[i0:i0+L] += (np.sin(ph)*env*0.6).astype(np.float32)
drop(0.0)
drop(84.0)

bed = crowd + sub
# gentle soft-clip / limit
bed = np.tanh(bed*1.4)/1.4
bed *= 0.5                       # keep well under the voiceover
# tiny stereo widening
left  = bed
right = np.concatenate([bed[3:], bed[:3]]) * 0.98
stereo = np.stack([left, right], axis=1)
stereo = np.clip(stereo, -1, 1)

out = os.path.join(ROOT, "assets", "ambience.wav")
with wave.open(out, "w") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((stereo*32767).astype("<i2").tobytes())
print("wrote", out, f"{DUR:.2f}s")
