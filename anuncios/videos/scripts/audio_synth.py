"""Gera trilhas e efeitos sonoros originais (100% sintetizados, sem direitos de terceiros).

Uso: python3 scripts/audio_synth.py
Saída: assets/audio/music/*.wav e assets/audio/sfx/*.wav (44.1 kHz, estéreo)
"""
import os
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

SR = 44100
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSIC = os.path.join(ROOT, "assets/audio/music")
SFX = os.path.join(ROOT, "assets/audio/sfx")
rng = np.random.default_rng(7)


def t_axis(sec):
    return np.arange(int(sec * SR)) / SR


def lp(x, f, order=2):
    return sosfilt(butter(order, f, "low", fs=SR, output="sos"), x)


def hp(x, f, order=2):
    return sosfilt(butter(order, f, "high", fs=SR, output="sos"), x)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], "band", fs=SR, output="sos"), x)


def env_adsr(n, a=0.005, d=0.1, s=0.0, r=0.05, hold=None):
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    hold_n = max(0, n - a_n - d_n - r_n) if hold is None else int(hold * SR)
    e = np.concatenate([
        np.linspace(0, 1, max(a_n, 1)),
        np.linspace(1, s, max(d_n, 1)),
        np.full(hold_n, s),
        np.linspace(s, 0, max(r_n, 1)),
    ])
    if len(e) < n:
        e = np.concatenate([e, np.zeros(n - len(e))])
    return e[:n]


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


# ---------- instrumentos ----------

def kick(punch=1.0):
    t = t_axis(0.45)
    f = 45 + 120 * np.exp(-t * 28) * punch
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * np.exp(-t * 7)
    click = hp(rng.standard_normal(len(t)), 2000) * np.exp(-t * 400) * 0.3
    return np.tanh((x + click) * 1.6) * 0.9


def snare():
    t = t_axis(0.3)
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25) * 0.5
    noise = bp(rng.standard_normal(len(t)), 1500, 9000) * np.exp(-t * 16)
    return (tone + noise * 0.8) * 0.6


def clap():
    t = t_axis(0.35)
    n = bp(rng.standard_normal(len(t)), 900, 6000)
    e = np.zeros(len(t))
    for off in (0, 0.011, 0.022):
        e += np.where(t >= off, np.exp(-(t - off) * 60), 0)
    e += np.exp(-t * 12) * 0.5
    return n * e * 0.45


def hat(open_=False):
    t = t_axis(0.25 if open_ else 0.06)
    n = hp(rng.standard_normal(len(t)), 7000, 4)
    return n * np.exp(-t * (14 if open_ else 70)) * (0.22 if open_ else 0.18)


def bass_note(freq, dur, kind="saw"):
    t = t_axis(dur)
    if kind == "808":
        f = freq * (1 + 0.6 * np.exp(-t * 40))
        ph = 2 * np.pi * np.cumsum(f) / SR
        x = np.tanh(np.sin(ph) * 2.2) * env_adsr(len(t), 0.003, dur * 0.9, 0.0, 0.05)
        return x * 0.55
    saw = 2 * ((t * freq) % 1) - 1
    sq = np.sign(np.sin(2 * np.pi * freq / 2 * t)) * 0.4
    raw = saw + sq
    e = np.exp(-t * 8)
    x = lp(raw, 900) * e + lp(raw, 500) * (1 - e)
    return x * env_adsr(len(t), 0.004, 0.15, 0.6, 0.04) * 0.45


def pluck(freq, dur):
    t = t_axis(dur)
    x = sum(np.sin(2 * np.pi * freq * k * t + k) / k for k in (1, 2, 3, 4))
    x += (2 * ((t * freq * 1.003) % 1) - 1) * 0.3
    e = np.exp(-t * 6)
    x = lp(x, 2900) * e + lp(x, 450) * (1 - e)
    return x * np.exp(-t * 6) * 0.16


def pad(freqs, dur):
    t = t_axis(dur)
    x = np.zeros(len(t))
    for f in freqs:
        for det in (-0.12, 0.0, 0.11):
            fd = f * 2 ** (det / 12)
            x += 2 * ((t * fd + rng.random()) % 1) - 1
    x = lp(x / (len(freqs) * 3), 1400)
    return x * env_adsr(len(t), 0.25, 0.2, 0.8, 0.4) * 0.22


def place(buf, sig, start, gain=1.0, pan=0.0):
    i = int(start * SR)
    if i >= buf.shape[0]:
        return
    n = min(len(sig), buf.shape[0] - i)
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    buf[i:i + n, 0] += sig[:n] * gain * l * 1.41
    buf[i:i + n, 1] += sig[:n] * gain * r * 1.41


def master(buf, target_peak=0.89):
    buf = np.tanh(buf * 1.2)
    buf = buf / (np.max(np.abs(buf)) + 1e-9) * target_peak
    return buf.astype(np.float32)


# ---------- trilhas ----------

def track(name, bpm, prog, scale_root, style, bars=40):
    beat = 60 / bpm
    bar = beat * 4
    total = bars * bar + 2
    buf = np.zeros((int(total * SR), 2))
    side = np.ones(buf.shape[0])  # sidechain envelope
    k = kick(1.2 if style == "tension" else 1.0)
    for b in range(bars):
        t0 = b * bar
        chord = prog[b % len(prog)]
        root = scale_root + chord[0]
        intro = b < 1
        # drums
        if style == "tension":  # half-time trap-ish
            for kb in (0, 1.5, 2.75) if not intro else (0,):
                place(buf, k, t0 + kb * beat, 0.95)
                si = int((t0 + kb * beat) * SR)
                side[si:si + int(0.18 * SR)] = np.minimum(side[si:si + int(0.18 * SR)], np.linspace(0.35, 1, int(0.18 * SR))[:len(side[si:si + int(0.18 * SR)])])
            if not intro:
                place(buf, clap(), t0 + 2 * beat, 0.9)
                steps = 16 if b % 4 != 3 else 24
                for s in range(steps):
                    place(buf, hat(), t0 + s * (bar / steps), 0.8 if s % 2 == 0 else 0.5, pan=0.25)
            place(buf, bass_note(midi(root - 12), bar * 0.95, "808"), t0, 0.95)
        else:  # four on the floor
            for q in range(4):
                place(buf, k, t0 + q * beat, 0.9)
                si = int((t0 + q * beat) * SR)
                seg = side[si:si + int(0.2 * SR)]
                side[si:si + len(seg)] = np.minimum(seg, np.linspace(0.3, 1, int(0.2 * SR))[:len(seg)])
                if not intro:
                    place(buf, hat(True), t0 + (q + 0.5) * beat, 0.6, pan=0.3)
                    place(buf, hat(), t0 + (q + 0.25) * beat, 0.4, pan=-0.3)
                    place(buf, hat(), t0 + (q + 0.75) * beat, 0.4, pan=-0.3)
            if not intro:
                place(buf, clap(), t0 + beat, 0.8)
                place(buf, clap(), t0 + 3 * beat, 0.8)
            for e in range(8):  # offbeat bass
                if e % 2 == 1 or style == "bright":
                    place(buf, bass_note(midi(root - 12), beat * 0.45), t0 + e * beat / 2, 0.9 if e % 2 else 0.5)
        # harmony
        chord_f = [midi(root + iv + 12) for iv in chord[1]]
        place(buf, pad(chord_f, bar), t0, 0.9 if style != "tension" else 0.7)
        if style != "tension" and not intro:
            pattern = [0, 1, 2, 1, 2, 0, 1, 2]
            for s in range(8):
                f = chord_f[pattern[s] % len(chord_f)] * 2
                place(buf, pluck(f, beat * 0.5), t0 + s * beat / 2, 0.9, pan=(-0.4 if s % 2 else 0.4))
        if style == "tension" and not intro and b % 2 == 1:
            for s in range(4):
                place(buf, pluck(chord_f[s % len(chord_f)] * 2, beat * 0.9), t0 + s * beat, 0.7, pan=0.3 if s % 2 else -0.3)
    # apply sidechain to everything but the kick: approximate by ducking all, then re-add kicks
    buf *= side[:, None] ** 0.8
    sf.write(os.path.join(MUSIC, f"{name}.wav"), master(buf), SR)
    print("music", name, round(total, 1), "s")


# ---------- efeitos ----------

def sfx_all():
    out = {}
    t = t_axis(0.55)
    n = rng.standard_normal(len(t))
    sweep = np.zeros(len(t))
    fc = np.linspace(300, 6000, len(t))
    for i in range(0, len(t), 512):  # coarse time-varying band
        seg = n[i:i + 1024]
        f = fc[i]
        sweep[i:i + len(seg)] += bp(seg, max(f * 0.6, 60), min(f * 1.4, 20000))[:len(seg)] * np.hanning(len(seg))
    out["whoosh"] = sweep * np.sin(np.pi * t / t[-1]) ** 2 * 0.9

    t = t_axis(1.2)
    f = 30 + 90 * np.exp(-t * 9)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.2)
    crack = lp(rng.standard_normal(len(t)), 3000) * np.exp(-t * 18) * 0.6
    out["impact"] = np.tanh((boom + crack) * 1.8) * 0.9

    t = t_axis(0.12)
    out["pop"] = np.sin(2 * np.pi * (500 + 900 * np.exp(-t * 40)) * t) * np.exp(-t * 35) * 0.6

    t = t_axis(0.05)
    out["click"] = hp(rng.standard_normal(len(t)), 2500) * np.exp(-t * 160) * 0.5

    t = t_axis(1.0)
    ding = np.zeros(len(t))
    for f0, st in ((1318.5, 0), (1760, 0.11)):
        tt = np.clip(t - st, 0, None)
        ding += np.where(t >= st, np.sin(2 * np.pi * f0 * tt) * np.exp(-tt * 6) + 0.3 * np.sin(2 * np.pi * f0 * 2.01 * tt) * np.exp(-tt * 9), 0)
    out["ding"] = ding * 0.35

    t = t_axis(0.5)
    g = rng.standard_normal(len(t))
    g = np.round(g * 3) / 3
    gate = (np.sin(2 * np.pi * 23 * t) > 0).astype(float)
    out["glitch"] = bp(g, 300, 5000) * gate * np.exp(-t * 4) * 0.5

    t = t_axis(2.0)
    rf = 200 * 2 ** (t * 2.2)
    out["riser"] = (np.sin(2 * np.pi * np.cumsum(rf) / SR) * 0.3 + hp(rng.standard_normal(len(t)), 3000) * 0.25) * (t / t[-1]) ** 2

    t = t_axis(0.6)
    out["buzz"] = np.sign(np.sin(2 * np.pi * 110 * t)) * lp(np.ones(len(t)), 50) * np.exp(-t * 3) * 0.25 + np.sin(2 * np.pi * 116 * t) * 0.2 * np.exp(-t * 3)

    t = t_axis(0.35)
    out["cash"] = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * d) for f, d in ((2093, 9), (2637, 11), (3136, 13))) * 0.18

    for name, sig in out.items():
        st = np.stack([sig, sig], 1).astype(np.float32)
        st /= np.max(np.abs(st)) + 1e-9
        sf.write(os.path.join(SFX, f"{name}.wav"), st * 0.9, SR)
    print("sfx", ", ".join(out))


if __name__ == "__main__":
    os.makedirs(MUSIC, exist_ok=True)
    os.makedirs(SFX, exist_ok=True)
    # progressões: (offset do acorde em semitons, intervalos)
    minor = (0, (0, 3, 7))
    track("tension", 96, [(0, (0, 3, 7)), (-4, (0, 4, 7)), (-2, (0, 4, 7)), (-5, (0, 3, 7))], 45, "tension", bars=26)
    track("drive", 124, [(0, (0, 3, 7, 10)), (-4, (0, 4, 7, 11)), (3, (0, 4, 7)), (-2, (0, 4, 7))], 45, "drive", bars=34)
    track("bright", 118, [(0, (0, 4, 7, 11)), (7, (0, 4, 7)), (9, (0, 3, 7)), (5, (0, 4, 7, 11))], 48, "bright", bars=32)
    sfx_all()
