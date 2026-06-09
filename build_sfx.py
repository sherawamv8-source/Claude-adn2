#!/usr/bin/env python3
"""Synthesizes the SFX bed for the WC26 promo (output/sfx.wav).

Every cue is generated from scratch with numpy/scipy (no sample packs):
sub-bass drops, noise-sweep whooshes/risers, a glass shatter, counter ticks,
a goalpost clang, electric buzz, sonar pings, chain clanks, a church-bell
gong, an airy choir pad and the outro pop chime.
"""
import numpy as np
from scipy import signal
import wave
import os

SR = 44100
DUR = 93.0
N = int(SR * DUR)
mix = np.zeros(N)
rng = np.random.RandomState(42)


def add(t0, snd, gain=1.0):
    i0 = int(t0 * SR)
    i1 = min(N, i0 + len(snd))
    if i1 > i0:
        mix[i0:i1] += snd[:i1 - i0] * gain


def env(n, attack=0.01, release=None, shape=2.0):
    t = np.linspace(0, 1, n)
    a = int(attack * n) if attack < 1 else int(attack * SR)
    e = np.ones(n)
    if a > 0:
        e[:a] = np.linspace(0, 1, a)
    e *= (1 - t) ** shape
    return e


def lowpass(x, fc, order=4):
    b, a = signal.butter(order, fc / (SR / 2), "low")
    return signal.lfilter(b, a, x)


def highpass(x, fc, order=4):
    b, a = signal.butter(order, fc / (SR / 2), "high")
    return signal.lfilter(b, a, x)


def bandpass(x, f0, f1, order=3):
    b, a = signal.butter(order, [f0 / (SR / 2), f1 / (SR / 2)], "band")
    return signal.lfilter(b, a, x)


def boom(dur=0.9, f0=130, f1=38):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = np.geomspace(f0, f1, n)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + 0.4 * np.sin(2 * ph)
    x += lowpass(rng.randn(n), 160) * 0.5
    return np.tanh(x * 2.2) * env(n, 0.004, shape=2.4)


def whoosh(dur=0.5, up=True, bright=2600):
    n = int(dur * SR)
    x = rng.randn(n)
    f = np.geomspace(300, bright, n) if up else np.geomspace(bright, 300, n)
    out = np.zeros(n)
    seg = 1024
    for i in range(0, n, seg):
        fc = f[min(i, n - 1)]
        lo, hi = fc * 0.6, min(fc * 1.6, SR / 2 - 200)
        out[i:i + seg] = bandpass(x[i:i + seg], lo, hi)
    w = out * np.hanning(n)
    return w / (np.abs(w).max() + 1e-9)


def riser(dur=2.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = np.geomspace(70, 880, n)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * 0.5
    nz = highpass(rng.randn(n), 800) * np.linspace(0.05, 1.0, n) ** 2
    x += nz * 0.7
    return x * np.linspace(0.1, 1.0, n) ** 1.5


def shatter():
    n = int(1.1 * SR)
    x = highpass(rng.randn(n), 2800) * env(n, 0.002, shape=3.2) * 1.4
    for _ in range(22):
        f = rng.uniform(2800, 9500)
        st = int(rng.uniform(0, 0.45) * SR)
        m = int(rng.uniform(0.04, 0.22) * SR)
        ping = np.sin(2 * np.pi * f * np.arange(m) / SR) * env(m, 0.002, shape=4)
        x[st:st + m] += ping * rng.uniform(0.1, 0.3)
    return x


def tick():
    n = int(0.045 * SR)
    return bandpass(rng.randn(n), 1500, 3200) * env(n, 0.002, shape=5) * 1.6


def clang():
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for f, g in [(178, 1.0), (271, 0.7), (412, 0.55), (628, 0.4), (957, 0.3),
                 (1459, 0.2)]:
        x += np.sin(2 * np.pi * f * t) * g * np.exp(-t * (2.5 + f / 300))
    x += highpass(rng.randn(n), 1200) * np.exp(-t * 18) * 0.8
    return np.tanh(x * 1.6)


def buzz(dur=4.0):
    n = int(dur * SR)
    x = bandpass(rng.randn(n), 1800, 6400)
    gate = (rng.rand(n // 700 + 1) > 0.45).repeat(700)[:n]
    flick = lowpass(rng.randn(n), 30)
    flick = (flick - flick.min()) / (np.ptp(flick) + 1e-9)
    return x * gate * flick * np.hanning(n)


def ping():
    n = int(1.0 * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * 1180 * t) * np.exp(-t * 7)
    x += np.roll(x, int(0.23 * SR)) * 0.4
    return x


def rumble(dur=2.4):
    n = int(dur * SR)
    return lowpass(rng.randn(n), 70) * np.hanning(n) * 2.0


def chains():
    n = int(1.0 * SR)
    x = np.zeros(n)
    for _ in range(9):
        st = int(rng.uniform(0, 0.7) * SR)
        m = int(0.12 * SR)
        t = np.arange(m) / SR
        c = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * 38)
                for f in rng.uniform(900, 4200, 4))
        x[st:st + m] += c * 0.3
    return x


def gong():
    n = int(3.4 * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for f, g in [(98, 1.0), (147, 0.6), (196, 0.5), (247, 0.35), (392, 0.2)]:
        x += np.sin(2 * np.pi * f * t + 0.3 * np.sin(2 * np.pi * f * 2.01 * t)) \
            * g * np.exp(-t * 1.4)
    return np.tanh(x) * 0.9


def pad(dur=5.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for f in [110, 165, 220, 277, 330]:
        det = 1 + rng.uniform(-0.002, 0.002)
        x += np.sin(2 * np.pi * f * det * t) / 5
    e = np.minimum(np.linspace(0, 2.5, n), 1.0) * np.hanning(n) ** 0.4
    return lowpass(x, 900) * e


def chime():
    n = int(0.7 * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for i, f in enumerate([880, 1320, 1760]):
        st = int(i * 0.07 * SR)
        m = n - st
        x[st:] += np.sin(2 * np.pi * f * np.arange(m) / SR) * \
            np.exp(-np.arange(m) / SR * 6) * 0.5
    return x


def thud():
    return boom(0.4, 90, 45)


# ------------------------------------------------------------- timeline
add(0.10, boom(), 0.9)                       # logo slam
add(2.15, boom(0.6, 100, 45), 0.7)           # "rewritten"
add(2.95, whoosh(0.35), 0.6)
add(3.02, boom(0.5, 120, 50), 0.8)           # glitch hit
for i in range(8):                            # champion flag flashes
    add(4.0 + i * 0.3, tick(), 0.8)
add(4.2, riser(2.6), 0.55)                   # build into shatter
add(6.90, shatter(), 0.9)
add(6.90, boom(0.8, 110, 40), 0.9)
for i in range(10):                           # tease cards
    add(8.0 + i * 0.5, whoosh(0.32, up=(i % 2 == 0)), 0.5)
add(13.0, whoosh(0.7, up=False, bright=3400), 0.6)
add(15.0, boom(0.7, 100, 42), 0.85)          # Ecuador
for i in range(20):                           # counter ticks
    add(15.6 + i * 0.115, tick(), 0.55)
add(17.9, thud(), 0.8)
add(18.4, thud(), 0.8)
add(18.55, boom(0.6, 80, 38), 0.8)           # brick wall
add(21.15, whoosh(0.4), 0.6)                 # Pacho slide
add(23.45, whoosh(0.4, up=False), 0.6)       # Hincapié slide
add(26.0, whoosh(0.45), 0.55)
add(30.4, clang(), 0.9)                      # ball off the post
add(32.0, whoosh(0.5, bright=4000), 0.7)     # Japan slash
add(32.95, boom(0.5, 130, 60), 0.6)          # X stamp 1
add(33.50, boom(0.5, 130, 60), 0.6)          # X stamp 2
add(35.0, whoosh(0.4), 0.6)
add(37.0, whoosh(0.45), 0.6)
add(37.3, buzz(4.4), 0.30)                   # electric arcs
add(42.0, whoosh(0.45, up=False), 0.6)
add(43.0, ping(), 0.5)                       # radar
add(45.0, ping(), 0.45)
add(44.2, boom(0.5, 110, 50), 0.6)           # tactical nightmare
add(47.0, rumble(2.6), 0.7)                  # lion rumble
add(47.0, whoosh(0.5, up=False, bright=2000), 0.6)
add(47.9, whoosh(0.35, bright=5000), 0.5)    # claw slash
add(50.1, boom(0.6, 100, 45), 0.7)
add(52.05, whoosh(0.45), 0.65)               # Hakimi
add(55.2, whoosh(0.45, up=False), 0.65)      # Bono
add(57.8, boom(0.7, 110, 40), 0.85)          # stun the world
add(57.8, shatter(), 0.4)
add(60.1, thud(), 0.9)                       # horse stomp
add(60.55, thud(), 0.7)
add(62.2, whoosh(0.5), 0.6)                  # Lorenzo + fire
add(65.05, whoosh(0.4), 0.6)                 # James in
add(66.0, buzz(1.2), 0.22)
add(67.8, buzz(2.8), 0.35)                   # Diaz lightning
add(67.8, whoosh(0.35, bright=5200), 0.6)
add(73.0, boom(0.7, 100, 40), 0.8)           # NL
add(74.2, boom(0.45, 140, 70), 0.65)         # 1974
add(74.9, boom(0.45, 140, 70), 0.65)         # 1978
add(75.6, boom(0.45, 140, 70), 0.65)         # 2010
add(76.6, chains(), 0.8)                     # padlock
add(77.4, chains(), 0.6)
add(78.30, shatter(), 0.85)                  # curse breaks
add(78.30, boom(0.8, 100, 36), 0.9)
add(80.2, gong(), 0.75)                      # van Dijk
add(83.6, pad(6.5), 0.5)                     # angelic pad
add(84.6, gong(), 0.4)
add(88.0, whoosh(0.5), 0.6)                  # outro
add(88.15, boom(0.5, 110, 50), 0.6)
add(89.7, chime(), 0.7)                      # UI pop
add(90.6, chime(), 0.5)

# gentle limiter & headroom
mix = np.tanh(mix * 0.9) * 0.85
pcm = (mix * 32767 * 0.6).astype(np.int16)

os.makedirs("output", exist_ok=True)
with wave.open("output/sfx.wav", "wb") as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(SR)
    f.writeframes(pcm.tobytes())
print("wrote output/sfx.wav")
