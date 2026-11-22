"""Prepare a job folder for rendering.

    python pipeline/prep.py jobs/<job-id> --out video/public/job [--no-ai]

Reads jobs/<job-id>/job.json + images, runs the AI steps (background removal,
depth, vehicle classification, TTS), builds the beat-locked timeline, renders
the soundtrack, and writes one Remotion props file per output format.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

sys.path.insert(0, str(Path(__file__).parent))
import ai  # noqa: E402
import audio  # noqa: E402
import longform  # noqa: E402
import timeline  # noqa: E402

FPS = 30
FORMATS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}
VOICES = set(ai.EDGE_VOICES)
PRESETS = json.loads((Path(__file__).parent / "presets.json").read_text(encoding="utf-8"))


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60] or "car"


def default_lines(job: dict, preset: dict) -> dict:
    title = job.get("title", "").strip() or "your next car"
    specs = [s for s in job.get("specs", []) if s.get("value")]
    lines = {
        "hero": preset["heroLine"].format(title=title),
        "specs": " ".join(f"{s.get('label', '').strip()}, {s['value'].strip()}." for s in specs[:4]),
        "price": f"{job.get('priceLabel') or 'Starting at'} {job['price']}." if job.get("price") else "",
        "outro": f"{job.get('cta') or 'Book your test drive'}" + (f" at {job['dealer']}." if job.get("dealer") else " today."),
    }
    return lines


def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job_dir", type=Path)
    ap.add_argument("--out", type=Path, default=Path("video/public/job"))
    ap.add_argument("--no-ai", action="store_true", help="skip models (fast local test)")
    ap.add_argument("--mode", choices=["short", "long"], help="override job.mode")
    args = ap.parse_args()

    job_dir: Path = args.job_dir
    job = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    mode = args.mode or job.get("mode", "short")
    out: Path = args.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    rel = out.name  # path prefix inside Remotion's public/ folder

    # ------------------------------------------------------------------ images
    entries = job.get("images") or [{"file": p.name} for p in sorted(job_dir.iterdir())
                                     if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    if not entries:
        sys.exit("No images in job")
    hero = int(job.get("heroIndex", 0)) if 0 <= int(job.get("heroIndex", 0)) < len(entries) else 0

    raw = []
    for e in entries:
        im = ImageOps.exif_transpose(Image.open(job_dir / e["file"])).convert("RGB")
        im.thumbnail((2560, 2560), Image.LANCZOS)
        raw.append(im)

    # ------------------------------------------------------------------ preset (AI picks if "auto")
    vtype = (job.get("vehicleType") or "auto").lower()
    if vtype not in PRESETS:
        vtype = (None if args.no_ai else ai.classify(raw[hero])) or "sports"
    preset = PRESETS[vtype]
    grade = preset["theme"]["grade"]
    log(f"preset: {vtype}")

    images = []
    for i, e in enumerate(entries):
        log(f"image {i + 1}/{len(entries)}: {e['file']}")
        img = ImageEnhance.Contrast(raw[i]).enhance(grade["contrast"])
        img = ImageEnhance.Color(img).enhance(grade["saturate"])
        img = ImageEnhance.Brightness(img).enhance(grade["brightness"])
        img.save(out / f"img_{i}.jpg", quality=92)
        bg = img.resize((360, max(1, int(360 * img.height / img.width))), Image.BILINEAR)
        bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(9))).enhance(0.55)
        bg.save(out / f"bg_{i}.jpg", quality=85)

        mask = None
        override = job_dir / (Path(e["file"]).stem + ".mask.png")
        if override.exists():
            mask = Image.open(override).convert("L").resize(img.size)
        elif not args.no_ai:
            mask = ai.cutout(img)
        valid, box = ai.mask_stats(mask)
        cat = (e.get("category") or "auto").lower()
        if cat not in ai.CATEGORIES:
            cat = (ai.categorize(raw[i]) if (mode == "long" and not args.no_ai) else None) or "exterior"
        cut_name = None
        if valid:
            rgba = img.copy()
            rgba.putalpha(mask)
            rgba.save(out / f"cut_{i}.png", optimize=False, compress_level=3)
            cut_name = f"{rel}/cut_{i}.png"

        d = None if args.no_ai else ai.depth(img)
        if d is None:
            d = ai.synthetic_depth(img.size, mask if valid else None)
        d = ai.finish_depth(d, img.size)
        d.save(out / f"depth_{i}.png")
        darr = np.asarray(d, dtype=np.float32) / 255.0
        h, w = darr.shape
        x0, y0, x1, y1 = box
        region = darr[int(y0 * h): max(int(y0 * h) + 1, int(y1 * h)), int(x0 * w): max(int(x0 * w) + 1, int(x1 * w))]
        images.append({
            "src": f"{rel}/img_{i}.jpg",
            "bg": f"{rel}/bg_{i}.jpg",
            "cutout": cut_name,
            "depth": f"{rel}/depth_{i}.png",
            "w": img.width,
            "h": img.height,
            "box": [round(v, 4) for v in box],
            "carDepth": round(float(np.median(region)), 3),
            "caption": (e.get("caption") or "").strip(),
            "category": cat,
        })

    # ------------------------------------------------------------------ shared assets
    logo = None
    if job.get("logo") and (job_dir / job["logo"]).exists():
        li = Image.open(job_dir / job["logo"]).convert("RGBA")
        li.thumbnail((800, 800))
        li.save(out / "logo.png")
        logo = f"{rel}/logo.png"

    rng = np.random.default_rng(3)
    g = rng.integers(0, 2, (256, 256)).astype(np.uint8) * 255
    alpha = rng.integers(0, 70, (256, 256)).astype(np.uint8)
    Image.fromarray(np.stack([g, g, g, alpha], axis=-1), "RGBA").save(out / "grain.png")

    theme = json.loads(json.dumps(preset["theme"]))
    theme["name"] = vtype
    specs = [s for s in job.get("specs", []) if s.get("value")][:4]
    car = {
        "title": job.get("title", "").strip(),
        "tagline": (job.get("tagline") or preset["tagline"]).strip(),
        "price": (job.get("price") or "").strip(),
        "priceLabel": (job.get("priceLabel") or "Starting at").strip(),
        "specs": specs,
        "dealer": (job.get("dealer") or "").strip(),
        "contact": (job.get("contact") or "").strip(),
        "cta": (job.get("cta") or "Book a test drive").strip(),
        "logo": logo,
    }
    music_file = None
    if job.get("music"):
        mf = job_dir / job["music"]
        music_file = mf if mf.exists() else None
    name = slug(job.get("title") or job_dir.name)
    common = {"theme": theme, "car": car, "images": images, "audio": f"{rel}/mix.wav", "grain": f"{rel}/grain.png", "fps": FPS}

    if mode == "long":
        run_long(job, job_dir, preset, images, common, out, rel, name, music_file, args)
    else:
        run_short(job, preset, images, hero, common, out, name, music_file, args)


def run_long(job, job_dir, preset, images, common, out, rel, name, music_file, args):
    script_path = job_dir / "script.md"
    if not script_path.exists():
        sys.exit("Long mode needs jobs/<id>/script.md (generate it with pipeline/script_gen.py or the upload page).")
    vo_cfg = job.get("voice") or {}
    voice = vo_cfg.get("voice") if vo_cfg.get("voice") in VOICES else "am_michael"
    # Any Microsoft Edge neural voice can narrate the whole script, e.g. "ja-JP-KeitaNeural" for Japanese.
    edge_voice = (vo_cfg.get("edgeVoice") or "").strip()

    def norm(x: str) -> str:
        return re.sub(r"[^a-z0-9\u3040-\u30ff\u4e00-\u9fff]+", " ", x.lower()).strip()

    overrides = [o for o in (job.get("ttsOverrides") or []) if o.get("match") and o.get("text")]

    def tts_fn(text, speed):
        if args.no_ai:
            return None
        # A sentence can be spoken differently from how it's captioned, e.g. Roman Urdu shown on screen
        # but voiced from Urdu script by an Urdu neural voice.
        for o in overrides:
            if norm(o["match"]) in norm(text):
                clip = ai.edge_tts(o["text"], o.get("edgeVoice", "ur-PK-AsadNeural"), float(o.get("speed", 1.0)))
                if clip is not None:
                    return clip
                break
        if edge_voice:
            clip = ai.edge_tts(text, edge_voice, speed)
            if clip is None:  # don't let the English Kokoro voice read e.g. Japanese text
                sys.exit(f"edge-tts voice {edge_voice} failed for: {text[:60]!r}")
            return clip
        return ai.tts(text, voice, speed)

    job = dict(job)
    if music_file:
        job["_music_path"] = str(music_file)
    plan = longform.build(job, images, preset, script_path.read_text(encoding="utf-8"), tts_fn, out, rel, log)
    theme = common["theme"]
    theme["fx"]["grain"] = min(theme["fx"]["grain"], 0.025)  # grain kills compression on long videos
    words = (job.get("thumbnailText") or "").strip()
    props = {**common, **plan, "mode": "long", "width": 1920, "height": 1080, "format": "16:9",
             "burnCaptions": bool(job.get("burnCaptions", True)),
             "decor": job.get("decor") or None,
             "thumbnail": {"text": words or job.get("title", ""), "badge": (job.get("thumbnailBadge") or "FULL REVIEW").strip()}}
    (out / "props-long.json").write_text(json.dumps(props), encoding="utf-8")
    renders = [{"format": "16:9", "props": "props-long.json", "output": f"{name}-youtube.mp4", "poster": f"{name}-thumbnail.jpg",
                "long": True, "durationInFrames": plan["durationInFrames"]}]
    (out / "renders.json").write_text(json.dumps(renders, indent=1), encoding="utf-8")
    (out / "voiceover.txt").write_text(f"Long-form video, script: script.md ({plan['durationInFrames'] / FPS / 60:.1f} min)", encoding="utf-8")
    log("ready: long 16:9")


def run_short(job, preset, images, hero, common, out, name, music_file, args):
    vo_cfg = job.get("voice") or {}
    lines = default_lines(job, preset)
    lines.update({k: v for k, v in (vo_cfg.get("lines") or {}).items() if isinstance(v, str)})
    vo_clips, vo_secs = {}, {}
    if vo_cfg.get("enabled", True):
        voice = vo_cfg.get("voice") if vo_cfg.get("voice") in VOICES else "am_michael"
        speed = float(preset.get("voiceSpeed", 1.0)) * float(vo_cfg.get("speed", 1.0))
        for k in ("hero", "specs", "price", "outro"):
            if lines.get(k, "").strip():
                log(f"tts {k}: {lines[k]!r}")
                clip = ai.tts(lines[k], voice, speed) if not args.no_ai else None
                if clip is not None:
                    vo_clips[k] = clip
                    vo_secs[k] = len(clip) / audio.SR

    tl = timeline.build(len(images), hero, preset, vo_secs, FPS, len(common["car"]["specs"]))
    log(f"timeline: {tl['durationInFrames'] / FPS:.1f}s, {len(tl['scenes'])} scenes")
    clips = [(tl["voStarts"][k] / FPS, v) for k, v in vo_clips.items()]
    audio.build_mix(tl, preset["music"], clips, out / "mix.wav", music_file)
    log("audio mixed")

    formats = [f for f in (job.get("formats") or ["9:16"]) if f in FORMATS] or ["9:16"]
    if job.get("mode") == "long":
        formats = ["9:16"]  # bonus Short for a long-form job
        name += "-short"
    renders = []
    for f in formats:
        w, h = FORMATS[f]
        props = {**common, **tl, "mode": "short", "width": w, "height": h, "format": f}
        pf = out / f"props-{f.replace(':', 'x')}.json"
        pf.write_text(json.dumps(props, indent=1), encoding="utf-8")
        renders.append({"format": f, "props": pf.name, "output": f"{name}-{f.replace(':', 'x')}.mp4",
                        "poster": f"{name}-{f.replace(':', 'x')}.jpg",
                        "posterFrame": tl["scenes"][1]["from"] + tl["beatFrames"] * 3})
    (out / "renders.json").write_text(json.dumps(renders, indent=1), encoding="utf-8")
    (out / "voiceover.txt").write_text("\n".join(f"{k}: {v}" for k, v in lines.items()), encoding="utf-8")
    log(f"ready: {', '.join(formats)}")

if __name__ == "__main__":
    main()
