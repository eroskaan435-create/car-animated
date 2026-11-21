"""Procedural, royalty-free soundtrack + SFX, locked to the video timeline.

Everything is synthesized with numpy/scipy, so cuts, impacts, whooshes and
risers land exactly on the frames the visuals use.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 44100
_rng = np.random.default_rng(1337)


# --------------------------------------------------------------------------- dsp helpers
def _n(sec: float) -> int:
    return max(1, int(round(sec * SR)))


def _t(n: int) -> np.ndarray:
    return np.arange(n) / SR


def mtof(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def noise(n: int) -> np.ndarray:
    return _rng.uniform(-1, 1, n)


def _sos(kind: str, fc, order=2):
    return signal.butter(order, fc, kind, fs=SR, output="sos")


def lp(x, fc, order=2):
    return signal.sosfilt(_sos("low", min(fc, SR / 2 - 100), order), x)


def hp(x, fc, order=2):
    return signal.sosfilt(_sos("high", fc, order), x)


def bp(x, lo, hi, order=2):
    return signal.sosfilt(_sos("band", [lo, min(hi, SR / 2 - 100)], order), x)


def saw(f: float, n: int, phase: float = 0.0) -> np.ndarray:
    ph = (np.arange(n) * f / SR + phase) % 1.0
    return 2.0 * ph - 1.0


def env_ar(n: int, a: float, r: float) -> np.ndarray:
    e = np.ones(n)
    na, nr = min(n, _n(a)), min(n, _n(r))
    e[:na] = np.linspace(0, 1, na)
    if nr > 0:
        e[n - nr:] *= np.linspace(1, 0, nr)
    return e


def place(buf: np.ndarray, x: np.ndarray, t_sec: float, gain: float = 1.0, pan: float = 0.0):
    """Add mono (n,) or stereo (n,2) clip x into stereo buf at t_sec."""
    start = int(round(t_sec * SR))
    if start >= len(buf) or len(x) == 0:
        return
    if start < 0:
        x = x[-start:]
        start = 0
    end = min(len(buf), start + len(x))
    x = x[: end - start]
    if x.ndim == 1:
        ang = (pan + 1) * np.pi / 4
        buf[start:end, 0] += x * gain * np.cos(ang) * 1.414
        buf[start:end, 1] += x * gain * np.sin(ang) * 1.414
    else:
        buf[start:end] += x * gain


def reverb(x: np.ndarray, seconds=1.6, decay=0.35, wet=0.15, tone=6000) -> np.ndarray:
    n = _n(seconds)
    t = _t(n)
    irs = []
    for _ in range(2):
        ir = lp(noise(n) * np.exp(-t / decay), tone)
        ir[: _n(0.012)] = 0  # pre-delay
        irs.append(ir / np.sqrt(np.sum(ir ** 2)))
    out = np.zeros_like(x)
    for c in range(2):
        w = signal.fftconvolve(x[:, c], irs[c])[: len(x)]
        out[:, c] = x[:, c] + wet * w
    return out


# --------------------------------------------------------------------------- instruments
def kick(punch=1.0, tail=0.28):
    n = _n(0.55)
    t = _t(n)
    f = 44 + 120 * punch * np.exp(-t / 0.032)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / tail)
    click = hp(noise(n), 2500) * np.exp(-t / 0.004) * 0.35
    return np.tanh(1.7 * (body + click))


def snare(tone=190, tail=0.13):
    n = _n(0.4)
    t = _t(n)
    body = np.sin(2 * np.pi * tone * t) * np.exp(-t / 0.045) * 0.7
    nz = bp(noise(n), 1200, 9000) * np.exp(-t / tail)
    return np.tanh(1.4 * (body + nz))


def clap():
    n = _n(0.35)
    t = _t(n)
    e = np.zeros(n)
    for ti in (0.0, 0.011, 0.023):
        m = t >= ti
        e[m] += np.exp(-(t[m] - ti) / 0.006)
    e += np.exp(-t / 0.09) * 0.55
    return bp(noise(n), 900, 3500) * e * 1.4


def hat(open_=False, soft=1.0):
    n = _n(0.4 if open_ else 0.08)
    t = _t(n)
    return hp(noise(n), 7500) * np.exp(-t / (0.16 if open_ else 0.028)) * soft


def rim():
    n = _n(0.08)
    t = _t(n)
    return (np.sin(2 * np.pi * 1700 * t) * np.exp(-t / 0.012) + bp(noise(n), 2000, 6000) * np.exp(-t / 0.01)) * 0.6


def crash():
    n = _n(2.0)
    t = _t(n)
    return hp(noise(n), 5000) * np.exp(-t / 0.6) * 0.5


def sub808(note, dur):
    n = _n(dur)
    t = _t(n)
    f = mtof(note) * (1 + 0.6 * np.exp(-t / 0.02))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.9)
    return np.tanh(2.2 * x) * env_ar(n, 0.002, 0.04)


def bass_saw(note, dur, cutoff=700):
    n = _n(dur)
    f = mtof(note)
    x = saw(f, n) + saw(f * 1.006, n, 0.3)
    x = lp(x, cutoff, 4)
    return x * env_ar(n, 0.004, 0.03) * np.exp(-_t(n) / max(dur, 0.12))


def pad(notes, dur, cutoff=1500):
    n = _n(dur)
    out = np.zeros((n, 2))
    for m in notes:
        f = mtof(m)
        out[:, 0] += saw(f * 0.996, n, _rng.random()) + saw(f * 1.004, n, _rng.random())
        out[:, 1] += saw(f * 1.003, n, _rng.random()) + saw(f * 0.997, n, _rng.random())
    e = env_ar(n, min(0.35, dur / 3), min(0.5, dur / 3))
    for c in range(2):
        out[:, c] = lp(out[:, c], cutoff, 2) * e
    return out / (len(notes) * 2)


def pluck(note, dur, bright=3200):
    n = _n(dur)
    f = mtof(note)
    x = lp(saw(f, n) + 0.5 * saw(f * 2.002, n), bright, 2)
    return x * np.exp(-_t(n) / 0.14) * env_ar(n, 0.002, 0.02)


def chug(root, dur):
    n = _n(dur)
    x = saw(mtof(root), n) + saw(mtof(root + 7), n, 0.2) + 0.6 * saw(mtof(root + 12), n, 0.5)
    x = np.tanh(5 * x)
    x = lp(x, 3200, 2) * np.exp(-_t(n) / 0.1) * env_ar(n, 0.002, 0.02)
    return x * 0.5


# --------------------------------------------------------------------------- sfx
def riser(dur):
    n = _n(dur)
    t = _t(n)
    p = t / dur
    nz = hp(noise(n), 1200) * p ** 2.4
    f = 180 * 7 ** p
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * p ** 2 * 0.35
    trem = 1 - 0.4 * (0.5 + 0.5 * np.sin(2 * np.pi * np.cumsum(4 + 20 * p) / SR)) * p
    x = (nz + tone) * trem
    st = np.stack([x, np.roll(x, 37)], axis=1)
    return st


def impact(size=1.0):
    n = _n(2.6)
    t = _t(n)
    f = 30 + 70 * np.exp(-t / 0.12)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / (0.7 * size))
    body = lp(noise(n), 2500) * np.exp(-t / 0.18) * 0.7
    crack = hp(noise(n), 3000) * np.exp(-t / 0.025) * 0.6
    x = np.tanh(1.5 * (boom * 1.2 + body + crack))
    st = np.stack([x, x], axis=1)
    return reverb(st, seconds=2.4, decay=0.6, wet=0.35, tone=4000)


def whoosh(dur=0.42):
    n = _n(dur)
    t = _t(n)
    p = t / dur
    e = np.sin(np.pi * np.clip(p, 0, 1) ** 1.7) ** 2
    x = bp(noise(n), 350, 5000) * e
    ang = p * np.pi / 2
    return np.stack([x * np.cos(ang), x * np.sin(ang)], axis=1) * 1.6


def pop():
    n = _n(0.09)
    t = _t(n)
    f = 1200 - 600 * t / 0.09
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.025) + hp(noise(n), 4000) * np.exp(-t / 0.003) * 0.3


def snare_roll(dur, beat):
    """Accelerating snare roll (8ths -> 16ths -> 32nds) with a crescendo."""
    hits, tt = [], 0.0
    while tt < dur - 1e-6:
        p = tt / dur
        step = beat / 2 if p < 0.4 else beat / 4 if p < 0.75 else beat / 8
        hits.append((tt, 0.25 + 0.75 * p))
        tt += step
    return hits


# --------------------------------------------------------------------------- music styles
PROGS = {
    "trap": [(33, [57, 60, 64]), (29, [53, 57, 60]), (31, [55, 59, 62]), (28, [52, 55, 59])],
    "edm": [(33, [57, 60, 64]), (29, [57, 60, 65]), (36, [55, 60, 64]), (31, [55, 59, 62])],
    "synthwave": [(33, [57, 60, 64]), (29, [57, 60, 65]), (36, [55, 60, 64]), (31, [55, 59, 62])],
    "rock": [(40, [52, 55, 59]), (40, [52, 55, 59]), (43, [55, 59, 62]), (45, [57, 60, 64])],
    "ambient": [(33, [57, 60, 64, 67]), (29, [53, 57, 60, 64]), (36, [55, 60, 64, 67]), (28, [52, 55, 59, 62])],
}


def render_bar(style, t0, bar_i, beat, stems, tr=0):
    """Synthesize one 4/4 bar starting at t0 seconds into the stem buffers (tr = transpose)."""
    st = beat / 4
    root, chord = PROGS[style][bar_i % 4]
    root, chord = root + tr, [c + tr for c in chord]
    D, B, M = stems["drums"], stems["bass"], stems["music"]
    kicks = []

    def K(step, g=1.0):
        place(D, kick(), t0 + step * st, g)
        kicks.append(t0 + step * st)

    if style == "trap":
        for s in (0, 6, 10):
            K(s)
        place(D, clap(), t0 + 8 * st, 0.8)
        place(D, snare(), t0 + 8 * st, 0.45)
        for s in range(0, 16, 2):
            place(D, hat(), t0 + s * st, 0.35, pan=0.2)
        if bar_i % 2 == 1:
            for k in range(8):
                place(D, hat(), t0 + (12 + k / 2) * st, 0.25 + 0.03 * k, pan=0.2)
        place(D, hat(True), t0 + 14 * st, 0.2, -0.2)
        for s, d in ((0, 6), (6, 4), (10, 6)):
            place(B, sub808(root + 12, d * st), t0 + s * st, 0.9)
        place(M, pad(chord, 4 * beat, 1100), t0, 0.5)
        for s, k in zip((0, 3, 6, 10, 12), (0, 1, 2, 1, 2)):
            place(M, pluck(chord[k] + 12, 2 * st, 2600), t0 + s * st, 0.22, pan=(-0.4 if k % 2 else 0.4))
    elif style in ("edm", "synthwave"):
        for s in (0, 4, 8, 12):
            K(s)
        if style == "edm":
            for s in (4, 12):
                place(D, clap(), t0 + s * st, 0.75)
        else:
            for s in (4, 12):
                place(D, snare(210, 0.18), t0 + s * st, 0.6)
        for s in range(16):
            place(D, hat(open_=(s % 4 == 2)), t0 + s * st, 0.32 if s % 4 == 2 else 0.14, pan=0.25)
        if style == "edm":
            for s in (2, 6, 10, 14):
                place(B, bass_saw(root + 12, 2 * st, 900), t0 + s * st, 0.7)
        else:
            for s in range(0, 16, 2):
                place(B, bass_saw(root + 12 + (12 if s % 4 == 2 else 0), 2 * st, 850), t0 + s * st, 0.6)
        place(M, pad(chord, 4 * beat, 1700), t0, 0.5)
        arp = chord + [chord[0] + 12]
        seq = arp + arp[::-1][1:-1]
        for s in range(16 if style == "synthwave" else 8):
            step = s if style == "synthwave" else s * 2
            place(M, pluck(seq[s % len(seq)] + 12, st * 1.5, 3000), t0 + step * st, 0.15, pan=(-0.5 if s % 2 else 0.5))
    elif style == "rock":
        for s in (0, 8, 10):
            K(s)
        for s in (4, 12):
            place(D, snare(180, 0.16), t0 + s * st, 0.9)
        for s in range(0, 16, 2):
            place(D, hat(soft=0.8), t0 + s * st, 0.3, pan=-0.2)
        if bar_i % 4 == 0:
            place(D, crash(), t0, 0.6, 0.3)
        for s in range(0, 16, 2):
            acc = 1.0 if s in (0, 6, 8) else 0.7
            place(B, chug(root, 2 * st), t0 + s * st, 0.75 * acc, pan=-0.35)
            place(B, chug(root, 2 * st), t0 + s * st + 0.012, 0.75 * acc, pan=0.35)
        place(B, bass_saw(root, 4 * beat, 500), t0, 0.5)
    elif style == "ambient":
        K(0, 0.8)
        K(10, 0.6)
        place(D, rim(), t0 + 8 * st, 0.6)
        for s in range(0, 16, 2):
            place(D, hat(soft=0.6), t0 + s * st, 0.18, pan=0.3)
        place(B, sub808(root + 12, 4 * beat), t0, 0.7)
        place(M, pad(chord, 4 * beat, 2000), t0, 0.7)
        seq = chord + [chord[1] + 12]
        for s in range(8):
            place(M, pluck(seq[s % len(seq)] + 12, st * 3, 2400), t0 + s * 2 * st, 0.2, pan=(-0.5 if s % 2 else 0.5))
    return kicks


# --------------------------------------------------------------------------- main entry
def _load_audio(path: Path) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
        check=True, capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(np.float64)


def _fade(x, sec_in, sec_out):
    n_in, n_out = min(len(x), _n(sec_in)), min(len(x), _n(sec_out))
    x[:n_in] *= np.linspace(0, 1, n_in)[:, None]
    x[len(x) - n_out:] *= np.linspace(1, 0, n_out)[:, None]
    return x


def _rms(x):
    return float(np.sqrt(np.mean(x ** 2)) + 1e-9)


def build_mix(timeline: dict, style: str, vo_clips: list, out_path: Path, user_music: Path | None = None):
    """timeline: output of timeline.build(); vo_clips: [(start_sec, np.ndarray mono @SR)]."""
    fps = timeline["fps"]
    beat = timeline["beatFrames"] / fps
    total = timeline["durationInFrames"] / fps
    N = _n(total + 0.05)
    sc = {s["type"]: s for s in timeline["scenes"] if s["type"] != "shot"}
    sec = lambda f: f / fps  # noqa: E731

    stems = {k: np.zeros((N, 2)) for k in ("drums", "bass", "music", "sfx")}
    kicks: list[float] = []

    drop = sec(sc["hero"]["from"])
    price = sec(sc["price"]["from"])
    build_start = max(drop + beat, price - 4 * beat)
    end_groove = sec(timeline["finalHit"])

    if user_music is None:
        # Intro: pad + sub pulses + accelerating snare roll in the last bar.
        intro_bars = max(1, int(round(drop / (4 * beat))))
        for b in range(intro_bars):
            root, chord = PROGS[style][b % 4]
            place(stems["music"], pad(chord, 4 * beat, 900 + 500 * b), b * 4 * beat, 0.55)
            place(stems["bass"], sub808(root + 12, 2 * beat), b * 4 * beat, 0.3)
        roll_len = min(drop, 4 * beat)
        for tt, g in snare_roll(roll_len, beat):
            place(stems["drums"], snare(200, 0.08), drop - roll_len + tt, 0.85 * g)

        # Two groove segments, each starting on a downbeat.
        for seg_start, seg_end in ((drop, build_start), (price, end_groove)):
            seg = {k: np.zeros((N, 2)) for k in ("drums", "bass", "music")}
            t0, bar_i = seg_start, 0
            while t0 < seg_end - 1e-6:
                kicks += [k for k in render_bar(style, t0, bar_i, beat, seg) if k < seg_end]
                t0 += 4 * beat
                bar_i += 1
            a, b = int(seg_start * SR), int(seg_end * SR)
            fade = _n(0.02)
            for k, buf in seg.items():
                buf[:a] = 0
                if k != "music":  # let pads ring through cuts
                    buf[b:] = 0
                    buf[max(a, b - fade):b] *= np.linspace(1, 0, b - max(a, b - fade))[:, None]
                else:
                    buf[b + _n(beat * 2):] = 0
                stems[k] += buf

        # Pre-price build: pad + roll.
        root, chord = PROGS[style][0]
        place(stems["music"], pad(chord, price - build_start, 1400), build_start, 0.85)
        for tt, g in snare_roll(price - build_start, beat):
            place(stems["drums"], snare(200, 0.08), build_start + tt, 0.85 * g)
        # Outro tail: a long chord after the final hit.
        place(stems["music"], pad(PROGS[style][0][1], total - end_groove + 0.5, 1600), end_groove, 0.6)
        place(stems["bass"], sub808(PROGS[style][0][0] + 12, total - end_groove), end_groove, 0.7)

        # Sidechain pump for the EDM-ish styles.
        if style in ("edm", "synthwave", "trap"):
            imp = np.zeros(N)
            for k in kicks:
                i = int(k * SR)
                if i < N:
                    imp[i] = 1.0
            env = signal.lfilter([1.0], [1.0, -np.exp(-1 / (0.13 * SR))], imp)
            pump = 1 - 0.55 * np.clip(env, 0, 1)
            for k in ("bass", "music"):
                stems[k] *= pump[:, None]

        music = stems["drums"] * 0.9 + stems["bass"] * 0.75 + stems["music"] * 0.45
        music = reverb(music, 1.4, 0.3, 0.1)
    else:
        m = _load_audio(user_music)
        reps = int(np.ceil(N / max(1, len(m))))
        music = np.tile(m, (reps, 1))[:N].copy()
        music = _fade(music, 0.3, 2.0)

    music *= 0.11 / _rms(music[_n(drop): _n(total)] if total > drop + 1 else music)

    # ------------------------------------------------------------------ SFX from timeline events
    sfx = stems["sfx"]
    for ev in timeline["events"]:
        t = sec(ev["frame"])
        g = ev.get("strength", 1.0)
        kind = ev["type"]
        if kind == "impact":
            place(sfx, impact(g), t, 0.5 * g)
        elif kind == "whoosh":
            w = whoosh(0.42)
            place(sfx, w, t - 0.42 * 0.72, 0.45 * g)
        elif kind == "pop":
            place(sfx, pop(), t, 0.3 * g)
        elif kind == "riser":
            d = sec(ev["duration"])
            place(sfx, riser(d), t, 0.5 * g)
    sfx_peak = np.max(np.abs(sfx)) + 1e-9
    if sfx_peak > 0.8:
        sfx *= 0.8 / sfx_peak

    # ------------------------------------------------------------------ voice-over + ducking
    vo = np.zeros((N, 2))
    active = np.zeros(N)
    for start, clip in vo_clips:
        if clip is None or len(clip) == 0:
            continue
        clip = clip * (0.13 / _rms(clip))
        place(vo, clip, start, 1.0)
        a = max(0, int((start - 0.12) * SR))
        b = min(N, int((start + len(clip) / SR + 0.25) * SR))
        active[a:b] = 1.0
    coef = np.exp(-1 / (0.07 * SR))
    smooth = signal.filtfilt([1 - coef], [1, -coef], active) if active.any() else active
    smooth = np.clip(smooth, 0, 1)
    duck = 1 - 0.55 * smooth

    mix = music * duck[:, None] + sfx * (1 - 0.25 * smooth[:, None]) + vo
    # master: soft clip + peak normalize
    pk = np.percentile(np.abs(mix), 99.7) + 1e-9
    mix = np.tanh(mix / pk * 1.3) / np.tanh(1.3)
    mix *= 0.95 / (np.max(np.abs(mix)) + 1e-9)
    mix = _fade(mix, 0.01, 0.6)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(str(out_path), SR, (mix * 32767).astype(np.int16))
    return out_path


# --------------------------------------------------------------------------- long-form beds
def _pump(stems, kicks, n):
    imp = np.zeros(n)
    for k in kicks:
        i = int(k * SR)
        if i < n:
            imp[i] = 1.0
    env = signal.lfilter([1.0], [1.0, -np.exp(-1 / (0.13 * SR))], imp)
    pump = 1 - 0.55 * np.clip(env, 0, 1)
    for k in ("bass", "music"):
        stems[k] *= pump[:, None]


def render_bed(style: str, dur: float, beat: float, tr: int = 0, bar_offset: int = 0, drums: float = 1.0) -> np.ndarray:
    """A looping background bed of `dur` seconds (float32 stereo), faded at both ends."""
    n = _n(dur + 2.5)
    stems = {k: np.zeros((n, 2)) for k in ("drums", "bass", "music")}
    kicks, t0, i = [], 0.0, 0
    while t0 < dur:
        kicks += render_bar(style, t0, i + bar_offset, beat, stems, tr)
        t0 += 4 * beat
        i += 1
    if style in ("edm", "synthwave", "trap"):
        _pump(stems, kicks, n)
    music = stems["drums"] * 0.9 * drums + stems["bass"] * 0.75 + stems["music"] * 0.45
    music = reverb(music, 1.4, 0.3, 0.12)[: _n(dur)]
    music = _fade(music, 0.25, min(1.0, dur / 4))
    return (music / (_rms(music) + 1e-9) * 0.11).astype(np.float32)


def render_open(style: str, drop: float, end: float, beat: float) -> np.ndarray:
    """Cold open: pad + snare-roll build up to `drop`, then full groove until `end`."""
    n = _n(end + 2.5)
    stems = {k: np.zeros((n, 2)) for k in ("drums", "bass", "music")}
    for b in range(max(1, int(round(drop / (4 * beat))))):
        root, chord = PROGS[style][b % 4]
        place(stems["music"], pad(chord, 4 * beat, 900 + 500 * b), b * 4 * beat, 0.55)
        place(stems["bass"], sub808(root + 12, 2 * beat), b * 4 * beat, 0.3)
    roll = min(drop, 4 * beat)
    for tt, g in snare_roll(roll, beat):
        place(stems["drums"], snare(200, 0.08), drop - roll + tt, 0.85 * g)
    kicks, t0, i = [], drop, 0
    while t0 < end:
        kicks += render_bar(style, t0, i, beat, stems)
        t0 += 4 * beat
        i += 1
    if style in ("edm", "synthwave", "trap"):
        _pump(stems, kicks, n)
    music = stems["drums"] * 0.9 + stems["bass"] * 0.75 + stems["music"] * 0.45
    music = reverb(music, 1.4, 0.3, 0.1)[: _n(end)]
    music = _fade(music, 0.01, 0.6)
    ref = music[_n(drop):] if end > drop + 1 else music
    return (music / (_rms(ref) + 1e-9) * 0.11).astype(np.float32)
