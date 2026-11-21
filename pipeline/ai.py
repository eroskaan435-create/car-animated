"""AI helpers. Every function degrades gracefully: if a model is missing or fails,
it returns None and the pipeline falls back to a non-AI effect."""
from __future__ import annotations

import asyncio
import re
import subprocess
import tempfile
import traceback
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

SR_OUT = 44100


def _warn(what: str):
    print(f"  ! {what} failed, using fallback:")
    traceback.print_exc(limit=1)


# --------------------------------------------------------------------------- background removal
_rembg_session = None


def cutout(img: Image.Image) -> Image.Image | None:
    """Return an 'L' alpha mask of the main vehicle, or None."""
    global _rembg_session
    try:
        from rembg import new_session, remove

        if _rembg_session is None:
            try:
                _rembg_session = new_session("birefnet-general-lite")
            except Exception:
                _rembg_session = new_session("isnet-general-use")
        small = img.copy()
        small.thumbnail((1280, 1280), Image.LANCZOS)
        mask = remove(small, session=_rembg_session, only_mask=True, post_process_mask=True)
        return mask.convert("L").resize(img.size, Image.LANCZOS)
    except Exception:
        _warn("background removal")
        return None


def mask_stats(mask: Image.Image | None):
    """Return (valid, bbox[x0,y0,x1,y1] normalized)."""
    if mask is None:
        return False, [0.08, 0.2, 0.92, 0.85]
    a = np.asarray(mask, dtype=np.float32) / 255.0
    cov = float((a > 0.5).mean())
    ys, xs = np.where(a > 0.5)
    if len(xs) < 50:
        return False, [0.08, 0.2, 0.92, 0.85]
    h, w = a.shape
    x0, x1 = np.percentile(xs, [0.5, 99.5]) / w
    y0, y1 = np.percentile(ys, [0.5, 99.5]) / h
    box = [float(x0), float(y0), float(x1), float(y1)]
    valid = 0.05 < cov < 0.85 and (x1 - x0) > 0.25
    return valid, box


# --------------------------------------------------------------------------- depth
_depth_pipe = None


def depth(img: Image.Image) -> Image.Image | None:
    """Return a normalized 'L' depth map (white = near), or None."""
    global _depth_pipe
    try:
        if _depth_pipe is None:
            from transformers import pipeline

            _depth_pipe = pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device="cpu")
        small = img.copy()
        small.thumbnail((768, 768), Image.LANCZOS)
        d = _depth_pipe(small)["depth"].convert("F")
        arr = np.asarray(d, dtype=np.float32)
        lo, hi = np.percentile(arr, [2, 98])
        arr = np.clip((arr - lo) / max(1e-6, hi - lo), 0, 1)
        return Image.fromarray((arr * 255).astype(np.uint8), "L")
    except Exception:
        _warn("depth estimation")
        return None


def synthetic_depth(size, mask: Image.Image | None) -> Image.Image:
    """Fallback: ground-plane gradient + vehicle mask pushed forward."""
    w, h = 512, max(1, int(512 * size[1] / size[0]))
    y = np.linspace(0, 1, h)[:, None] * np.ones((1, w))
    d = 0.15 + 0.55 * y ** 1.5
    if mask is not None:
        m = np.asarray(mask.resize((w, h)), dtype=np.float32) / 255.0
        d = np.maximum(d, 0.55 + 0.35 * m) * (m > 0.05) + d * (m <= 0.05)
    return Image.fromarray((np.clip(d, 0, 1) * 255).astype(np.uint8), "L")


def finish_depth(d: Image.Image, size) -> Image.Image:
    """Smooth + dilate near regions so parallax stretches background, not the car."""
    w = 768
    h = max(1, int(w * size[1] / size[0]))
    d = d.resize((w, h), Image.BILINEAR)
    d = d.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(4))
    return d


# --------------------------------------------------------------------------- vehicle type
LABELS = {
    "sports": "a photo of a sports car or supercar",
    "luxury": "a photo of a luxury limousine or premium car",
    "suv": "a photo of an SUV or off-road 4x4",
    "truck": "a photo of a pickup truck",
    "ev": "a photo of a modern electric car",
    "sedan": "a photo of a family sedan or hatchback",
}


_clip_pipe = None


def _clip():
    global _clip_pipe
    if _clip_pipe is None:
        from transformers import pipeline

        _clip_pipe = pipeline("zero-shot-image-classification", model="openai/clip-vit-base-patch32", device="cpu")
    return _clip_pipe


def _zero_shot(img: Image.Image, labels: dict) -> tuple[str, float]:
    small = img.copy()
    small.thumbnail((512, 512))
    res = _clip()(small, candidate_labels=list(labels.values()))
    kind = next(k for k, v in labels.items() if v == res[0]["label"])
    return kind, float(res[0]["score"])


def classify(img: Image.Image) -> str | None:
    try:
        kind, score = _zero_shot(img, LABELS)
        print(f"  vehicle type (CLIP): {kind} ({score:.2f})")
        return kind
    except Exception:
        _warn("vehicle classification")
        return None


CATEGORIES = {
    "exterior": "a photo of the outside of a whole car",
    "interior": "a photo of a car interior with dashboard, steering wheel or seats",
    "engine": "a photo of a car engine bay under the hood",
    "detail": "a close-up photo of a car wheel, headlight, taillight or badge",
}


def categorize(img: Image.Image) -> str | None:
    try:
        return _zero_shot(img, CATEGORIES)[0]
    except Exception:
        _warn("photo categorization")
        return None


# --------------------------------------------------------------------------- text to speech
EDGE_VOICES = {
    "am_michael": "en-US-GuyNeural", "am_adam": "en-US-ChristopherNeural", "am_fenrir": "en-US-EricNeural",
    "af_heart": "en-US-AriaNeural", "af_bella": "en-US-JennyNeural", "af_nicole": "en-US-MichelleNeural",
    "bm_george": "en-GB-RyanNeural", "bm_lewis": "en-GB-ThomasNeural",
    "bf_emma": "en-GB-SoniaNeural", "bf_isabella": "en-GB-LibbyNeural",
}

_kokoro = {}


def _trim(x: np.ndarray) -> np.ndarray:
    if len(x) == 0:
        return x
    thr = 0.02 * np.max(np.abs(x))
    idx = np.where(np.abs(x) > thr)[0]
    if len(idx) == 0:
        return x
    pad = int(0.03 * SR_OUT)
    return x[max(0, idx[0] - pad): idx[-1] + pad]


def _resample(x: np.ndarray, sr: int) -> np.ndarray:
    from math import gcd

    from scipy.signal import resample_poly

    g = gcd(sr, SR_OUT)
    return resample_poly(x, SR_OUT // g, sr // g)


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("0-60", "zero to sixty").replace("0-100", "zero to one hundred")
    return text


def tts(text: str, voice: str, speed: float) -> np.ndarray | None:
    """Return mono float audio at 44.1kHz."""
    text = _clean_text(text)
    if not text:
        return None
    try:
        from kokoro import KPipeline

        lang = voice[0] if voice[:1] in ("a", "b") else "a"
        if lang not in _kokoro:
            _kokoro[lang] = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M")
        chunks = []
        for _, _, audio in _kokoro[lang](text, voice=voice, speed=speed):
            if audio is not None:
                chunks.append(np.asarray(audio, dtype=np.float32).reshape(-1))
        if chunks:
            return _trim(_resample(np.concatenate(chunks), 24000))
    except Exception:
        _warn("Kokoro TTS")
    return edge_tts(text, EDGE_VOICES.get(voice, "en-US-GuyNeural"), speed)


def edge_tts(text: str, edge_voice: str, speed: float = 1.0) -> np.ndarray | None:
    """Microsoft Edge neural voice by its full name (e.g. 'ur-PK-AsadNeural'). Mono float at 44.1kHz."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    for attempt in range(3):
        try:
            import edge_tts as et

            with tempfile.TemporaryDirectory() as td:
                mp3 = Path(td) / "vo.mp3"
                rate = f"{int(round((speed - 1) * 100)):+d}%"
                asyncio.run(et.Communicate(text, edge_voice, rate=rate).save(str(mp3)))
                raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp3), "-f", "f32le", "-ac", "1", "-ar", str(SR_OUT), "-"],
                                     check=True, capture_output=True).stdout
                return _trim(np.frombuffer(raw, dtype=np.float32).astype(np.float64))
        except Exception:
            if attempt == 2:
                _warn(f"edge-tts ({edge_voice})")
    return None
