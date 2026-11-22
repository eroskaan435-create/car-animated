"""Long-form (13-15 min) YouTube video planner.

Script (markdown, '## Chapter' headings) -> per-sentence TTS -> timeline with
chapter cards, narrated shots, spec callouts, captions, galleries and an end
screen -> soundtrack, SRT captions, YouTube chapters + description.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

import audio
from audio import SR

FPS = 30
MIN_SEC = 13 * 60 + 5
MAX_SEC = 15 * 60 - 5
IDEAL_SEC = 14 * 60
CARD = 90            # chapter title card (frames)
XF = 15              # crossfade overlap between narrated shots
END_SCREEN = 20 * FPS
CALM_MOVES = ["pushIn", "panLR", "depth", "pullOut", "panRL", "depth", "pushIn", "pullOut"]
TRANSPOSE = [0, 2, -2, 3, -3, 5, 0, 2, -2, 3, -3, 5]
WPS = 2.7            # placeholder speech rate (words/sec) when TTS is skipped
FAST_PATTERN = [4, 4, 2, 2, 4, 2, 2, 4]  # shot lengths in beats for pace="fast"
CJK = re.compile(r"[\u3000-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]")
CJK_PER_WORD = 2.0   # Japanese has no spaces: ~2 kana/kanji count as one "word" for length estimates


def units(s: str) -> float:
    """Word-equivalent length of a text: space-separated words, with CJK characters counted per CJK_PER_WORD."""
    n_cjk = len(CJK.findall(s))
    rest = CJK.sub(" ", s)
    return len(rest.split()) + n_cjk / CJK_PER_WORD


def is_cjk(s: str) -> bool:
    return len(CJK.findall(s)) > len(s) * 0.2


# --------------------------------------------------------------------------- script parsing
def parse_script(text: str) -> list[dict]:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    chapters: list[dict] = []
    cur = None
    para: list[str] = []

    def flush():
        if cur is not None and para:
            cur["paragraphs"].append(" ".join(para).strip())
        para.clear()

    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"^#{1,3}\s+(.+)$", line)
        if m:
            flush()
            cur = {"title": m.group(1).strip().strip("#").strip(), "paragraphs": []}
            chapters.append(cur)
            continue
        if not line:
            flush()
            continue
        if cur is None:
            cur = {"title": "Overview", "paragraphs": []}
            chapters.append(cur)
        line = re.sub(r"[*_`>]+", "", line)
        line = re.sub(r"^\s*[-•]\s+", "", line)
        if para and is_cjk(line) and is_cjk(para[-1]):
            para[-1] += line  # no spaces between Japanese lines
        else:
            para.append(line)
    flush()
    chapters = [c for c in chapters if c["paragraphs"]]
    for c in chapters:
        c["paragraphs"] = [[s for s in split_sentences(p)] for p in c["paragraphs"]]
    return chapters


def split_sentences_cjk(p: str) -> list[str]:
    parts = [x.strip() for x in re.split(r"(?<=[。！？!?])\s*", p.strip()) if x.strip()]
    out: list[str] = []
    for s in parts:
        if out and units(s) < 3:
            out[-1] += s
        else:
            out.append(s)
    final = []
    for s in out:  # very long sentences are split at 、 for TTS + captions
        if len(s) > 70:
            buf = ""
            for c in re.split(r"(?<=[、，,])", s):
                if len(buf + c) > 50 and buf:
                    final.append(buf)
                    buf = c
                else:
                    buf += c
            if buf:
                final.append(buf)
        else:
            final.append(s)
    return final


def split_sentences(p: str) -> list[str]:
    if is_cjk(p):
        return split_sentences_cjk(p)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“$£€(])", p.strip())
    out: list[str] = []
    for s in parts:
        s = s.strip()
        if not s:
            continue
        if out and len(s.split()) < 3:
            out[-1] += " " + s
        else:
            out.append(s)
    # very long sentences are split at commas/semicolons for TTS + captions
    final = []
    for s in out:
        if len(s.split()) > 38:
            chunks = re.split(r"(?<=[,;:])\s+", s)
            buf = ""
            for c in chunks:
                if len((buf + " " + c).split()) > 26 and buf:
                    final.append(buf.strip())
                    buf = c
                else:
                    buf = (buf + " " + c).strip()
            if buf:
                final.append(buf)
        else:
            final.append(s)
    return final


def is_hook(title: str) -> bool:
    return bool(re.match(r"^(hook|intro|introduction|cold open|フック|オープニング|導入)$", title.strip().lower()))


def word_count(chapters) -> int:
    return int(sum(units(s) for c in chapters for p in c["paragraphs"] for s in p))


# --------------------------------------------------------------------------- photos per chapter
def prefs_for(title: str) -> list[str]:
    t = title.lower()
    if any(k in t for k in ("interior", "comfort", "cabin", "seat", "内装", "インテリア", "室内", "シート", "快適")):
        return ["interior", "detail"]
    if any(k in t for k in ("tech", "infotainment", "connect", "screen", "テクノロジー", "ナビ", "画面", "装備")):
        return ["interior", "detail"]
    if any(k in t for k in ("engine", "performance", "power", "motor", "battery", "エンジン", "性能", "走り", "パワー")):
        return ["engine", "exterior", "detail"]
    if any(k in t for k in ("practical", "cargo", "space", "storage", "boot", "trunk", "荷室", "収納", "空間", "使い勝手")):
        return ["interior", "exterior"]
    return ["exterior", "detail"]


class Picker:
    """Least-recently-used photo picker so repeats are spread out."""

    def __init__(self, images):
        self.images = images
        self.uses = [0] * len(images)
        self.last = -1

    def pick(self, prefs: list[str]) -> int:
        pool = [i for p in prefs for i, im in enumerate(self.images) if im.get("category") == p]
        if len(pool) < 3:
            pool += [i for i, im in enumerate(self.images) if im.get("category") == "exterior" and i not in pool]
        if len(pool) < 3:
            pool = list(range(len(self.images)))
        cands = [i for i in pool if i != self.last] or pool
        best = min(cands, key=lambda i: (self.uses[i], pool.index(i)))
        self.uses[best] += 1
        self.last = best
        return best


# --------------------------------------------------------------------------- callouts
FACT_KEYS = {
    "engine": ["engine", "motor", "cylinder", "v6", "v8", "turbo"],
    "transmission": ["transmission", "gearbox", "automatic", "manual", "speed dual"],
    "drivetrain": ["all-wheel", "awd", "rear-wheel", "front-wheel", "four-wheel", "4x4", "drivetrain"],
    "fuel": ["mpg", "fuel economy", "economy", "range", "efficien", "consumption"],
    "seats": ["seats", "seating", "passengers"],
    "cargo": ["cargo", "trunk", "boot", "luggage"],
}


def callout_candidates(job: dict) -> list[dict]:
    out = []
    for s in job.get("specs", []) or []:
        if not s.get("value"):
            continue
        num = re.findall(r"\d[\d,]*\.?\d*", s["value"])
        keys = [s.get("label", "").lower()] + ([num[0]] if num else [])
        out.append({"label": s.get("label", ""), "value": s["value"], "keys": [k for k in keys if k], "used": 0})
    facts = job.get("facts") or {}
    for k, words in FACT_KEYS.items():
        v = (facts.get(k) or "").strip()
        if v and len(v) <= 40:
            out.append({"label": k.title(), "value": v, "keys": words, "used": 0})
    if job.get("price"):
        out.append({"label": job.get("priceLabel") or "Price", "value": job["price"], "keys": ["price", "costs", "msrp", "priced", "価格", "万円"], "used": 0})
    return out


def find_callout(sentence: str, cands: list[dict]):
    s = sentence.lower()
    for c in cands:
        if c["used"] >= 2:
            continue
        if any(k and k in s for k in c["keys"]):
            c["used"] += 1
            return c
    return None


# --------------------------------------------------------------------------- captions / text outputs
def cjk_groups(text: str, max_chars=30) -> list[str]:
    """Split a Japanese sentence into caption lines: break after 、 when possible, else after a particle."""
    if len(text) <= max_chars:
        return [text]
    n = math.ceil(len(text) / max_chars)
    cuts, start = [], 0
    for k in range(1, n):
        target = start + (len(text) - start) / (n - k + 1)
        lo, hi = int(start + (target - start) * 0.5), min(len(text) - 4, start + max_chars + 6)
        best = None
        for chars, tol in (("、，", 1.0), ("はがをでも", 0.3)):
            pos = [q + 1 for q in range(lo, hi) if text[q] in chars and text[q + 1] not in "、。！？」』）"]
            pos = [q for q in pos if abs(q - target) <= tol * (target - start)]
            if pos:
                best = min(pos, key=lambda q: abs(q - target))
                break
        if best is None:  # no clean break: keep it as one caption, the box wraps to two lines
            continue
        cuts.append(best)
        start = best
    bounds = [0, *cuts, len(text)]
    return [text[a:b] for a, b in zip(bounds, bounds[1:]) if text[a:b]]


def caption_chunks(text: str, f0: int, f1: int, max_words=9) -> list[dict]:
    if is_cjk(text):
        groups = cjk_groups(text)
        total = sum(len(g) for g in groups) or 1
        out, t = [], f0
        for g in groups:
            d = (f1 - f0) * len(g) / total
            out.append({"from": int(round(t)), "to": int(round(t + d)), "text": g})
            t += d
        return out
    words = text.split()
    n = max(1, math.ceil(len(words) / max_words))
    per = math.ceil(len(words) / n)
    groups = [" ".join(words[i:i + per]) for i in range(0, len(words), per)]
    total = sum(len(g) for g in groups) or 1
    out, t = [], f0
    for g in groups:
        d = (f1 - f0) * len(g) / total
        out.append({"from": int(round(t)), "to": int(round(t + d)), "text": g})
        t += d
    return out


def srt_time(frames: int) -> str:
    ms = int(round(frames / FPS * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def yt_time(frames: int) -> str:
    s = int(frames // FPS)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


# --------------------------------------------------------------------------- main planner
def build(job: dict, images: list[dict], preset: dict, script_text: str, tts_fn, out: Path, rel: str, log) -> dict:
    chapters = parse_script(script_text)
    if not chapters:
        raise SystemExit("Script is empty. Generate or paste a script first.")
    words = word_count(chapters)
    log(f"script: {len(chapters)} chapters, {words} words")
    fast = (job.get("pace") or "").lower() == "fast"
    ja = (job.get("language") or "").lower().startswith("ja")
    if fast and words < 60:
        raise SystemExit(f"Script too short ({words} words).")
    if not fast and words < 1300:
        raise SystemExit(f"Script too short ({words} words). A 13-15 min video needs about 1,900-2,300 words.")

    vo_cfg = job.get("voice") or {}
    base_speed = float(preset.get("voiceSpeed", 1.0)) * float(vo_cfg.get("speed", 1.0))
    voice_on = vo_cfg.get("enabled", True)

    def synth(speed: float):
        n_done = 0
        for c in chapters:
            c["clips"] = []
            for p in c["paragraphs"]:
                row = []
                for s in p:
                    clip = tts_fn(s, speed) if voice_on else None
                    if clip is None:
                        clip = np.zeros(int(units(s) / (WPS * speed) * SR))
                    row.append(clip)
                    n_done += 1
                    if n_done % 25 == 0:
                        log(f"  tts {n_done} sentences")
                c["clips"].append(row)

    speed = base_speed
    synth(speed)

    B = int(preset["beatFrames"])
    picker = Picker(images)

    BAR = 4 * B
    pattern = [max(1, int(round(b * float(job.get("shotScale", 1.0))))) for b in FAST_PATTERN]

    def bar_ceil(x: float) -> int:
        return int(math.ceil(x / BAR - 1e-6) * BAR)

    def beat_montage(t0: int, t1: int, prefs: list[str], scenes, events, k0: int, first_tr: str | None = None):
        """Cut t0..t1 (both on the beat grid) into short shots that start exactly on beats."""
        t, i = t0, 0
        tr_list = preset["transitions"]
        moves = preset["moves"]
        prefs = prefs + [c for c in ("exterior", "detail", "interior", "engine") if c not in prefs]  # rotate every photo
        while t < t1:
            d = pattern[(k0 + i) % len(pattern)] * B
            if t1 - (t + d) < 2 * B:  # never leave a sliver shorter than 2 beats
                d = t1 - t
            tr = first_tr if (i == 0 and first_tr) else tr_list[(k0 + i) % len(tr_list)]
            scenes.append({"type": "shot", "from": t, "duration": d, "image": picker.pick(prefs),
                           "move": moves[(k0 + i) % len(moves)], "transitionIn": tr})
            events.append({"type": "whoosh", "frame": t, "strength": 0.55 if i else 0.8})
            if d >= 4 * B and (k0 + i) % 2 == 0:
                events.append({"type": "pop", "frame": t + 2 * B, "strength": 0.35})
            t += d
            i += 1
        return i

    def layout(gap_s: float, gap_p: float, galleries: dict[int, int]) -> dict:
        picker.uses = [0] * len(images)
        picker.last = -1
        cands = callout_candidates(job)
        scenes, events, captions, callouts, chap_meta, segments, vo = [], [], [], [], [], [], []
        t = 0

        # ---- cold open: intro + hero title slam
        ib = int(preset["introBeats"])
        order = [i for i in range(len(images))]
        teasers = [{"frame": b * B, "image": order[(b + 1) % len(order)]} for b in range(ib // 2, ib)]
        scenes.append({"type": "intro", "from": 0, "duration": ib * B, "cues": {"tagline": 0, "title": (ib // 4) * B, "teasers": teasers}})
        events.append({"type": "riser", "frame": 0, "duration": ib * B, "strength": 0.9})
        t = ib * B
        hero_idx = int(job.get("heroIndex", 0)) if int(job.get("heroIndex", 0)) < len(images) else 0
        scenes.append({"type": "hero", "from": t, "duration": 8 * B, "image": hero_idx, "transitionIn": "impact",
                       "cues": {"title": 0, "subtitle": B * 2}})
        events.append({"type": "impact", "frame": t, "strength": 1.0})
        drop = t
        t += 8 * B
        chap_meta.append({"index": 0, "title": job.get("introLabel") or ("オープニング" if ja else "Intro"), "from": 0})

        # ---- hook narration over energetic shots
        hook = next((c for c in chapters if is_hook(c["title"])), None)
        cursor = t + 8
        if hook:
            for p, prow in zip(hook["paragraphs"], hook["clips"]):
                for s, clip in zip(p, prow):
                    f0 = int(cursor)
                    dur = len(clip) / SR * FPS
                    vo.append((f0 / FPS, clip))
                    captions.extend(caption_chunks(s, f0, int(f0 + dur)))
                    cursor += dur + gap_s * FPS
            hook_end = cursor + FPS * 0.6
        else:
            hook_end = t + 8 * B
        beats = max(8, math.ceil((hook_end - t) / B))
        shot_beats = int(preset["shotBeats"]) * 2
        n = 0 if fast else max(1, round(beats / shot_beats))
        tr_list = preset["transitions"]
        if fast:
            end = bar_ceil(max(hook_end, t + 8 * B))
            beat_montage(t, end, ["exterior", "detail"], scenes, events, 0)
            t = end
        for i in range(n):
            d = (beats // n + (1 if i < beats % n else 0)) * B
            img = picker.pick(["exterior", "detail"])
            tr = tr_list[i % len(tr_list)]
            scenes.append({"type": "shot", "from": t, "duration": d, "image": img, "move": preset["moves"][i % len(preset["moves"])],
                           "transitionIn": tr})
            events.append({"type": "whoosh", "frame": t, "strength": 0.8})
            t += d
        segments.append({"kind": "open", "t0": 0, "t1": t, "drop": drop})
        pulse_until = t

        # ---- chapters
        body = [c for c in chapters if not is_hook(c["title"])]
        card_len = BAR if fast else CARD
        shot_k = 0
        for ci, c in enumerate(body):
            card_from = t
            scenes.append({"type": "chapter", "from": t, "duration": card_len, "image": picker.pick(prefs_for(c["title"])),
                           "transitionIn": "zoom", "cues": {"index": ci + 1, "title": c["title"]}})
            events.append({"type": "whoosh", "frame": t, "strength": 0.9})
            events.append({"type": "impact", "frame": t, "strength": 0.35})
            chap_meta.append({"index": ci + 1, "title": c["title"], "from": t})
            t += card_len
            cursor = t + 10
            bounds = []
            for p, prow in zip(c["paragraphs"], c["clips"]):
                for s, clip in zip(p, prow):
                    f0 = int(cursor)
                    dur = len(clip) / SR * FPS
                    f1 = int(f0 + dur)
                    vo.append((f0 / FPS, clip))
                    captions.extend(caption_chunks(s, f0, f1))
                    co = find_callout(s, cands)
                    if co and (not callouts or callouts[-1]["to"] < f0):
                        callouts.append({"from": f0, "to": max(f0 + 120, f1), "label": co["label"], "value": co["value"]})
                    bounds.append(f0)
                    cursor += dur + gap_s * FPS
                cursor += (gap_p - gap_s) * FPS
            chap_end = bar_ceil(cursor + FPS * 0.4) if fast else int(cursor + FPS * 0.8)

            # pros / cons card at the start of the verdict
            seg_start = t
            title_l = c["title"].lower()
            pros = [x.strip(" -•") for x in re.split(r"[\n;]", job.get("pros", "") or "") if x.strip(" -•")][:5]
            cons = [x.strip(" -•") for x in re.split(r"[\n;]", job.get("cons", "") or "") if x.strip(" -•")][:5]
            if any(k in title_l for k in ("verdict", "conclusion", "final", "wrap", "まとめ", "結論", "総評")) and (pros or cons):
                d = min(int((chap_end - t) * 0.6), 90 + 50 * (len(pros) + len(cons)))
                scenes.append({"type": "proscons", "from": t, "duration": d, "image": picker.pick(["exterior"]),
                               "transitionIn": "zoom", "cues": {"pros": pros, "cons": cons}})
                for k in range(len(pros) + len(cons)):
                    events.append({"type": "pop", "frame": t + 30 + 50 * k, "strength": 0.6})
                seg_start = t + d

            if fast:
                seg_start = t + int(math.ceil((seg_start - t) / B)) * B  # back on the beat grid after a pros/cons card
                shot_k += beat_montage(seg_start, chap_end, prefs_for(c["title"]), scenes, events, shot_k,
                                       first_tr="zoom" if seg_start == t else None)
                segments.append({"kind": "drive", "t0": card_from, "t1": chap_end})
                t = chap_end
                continue

            # narrated shots, cut on sentence boundaries every ~6-10 s
            cuts = [seg_start]
            for b in bounds:
                if b - cuts[-1] >= 180:
                    cuts.append(b)
                while b - cuts[-1] > 330:
                    cuts.append(cuts[-1] + 240)
            while chap_end - cuts[-1] > 330:
                cuts.append(cuts[-1] + 240)
            if len(cuts) > 1 and chap_end - cuts[-1] < 100:
                cuts.pop()
            cuts.append(chap_end)
            for k in range(len(cuts) - 1):
                a, b = cuts[k], cuts[k + 1]
                first = k == 0
                scenes.append({"type": "shot", "calm": True, "from": a if first else a - XF, "duration": (b - a) + (0 if first else XF),
                               "image": picker.pick(prefs_for(c["title"])), "move": CALM_MOVES[(k + ci) % len(CALM_MOVES)],
                               "transitionIn": "zoom" if first and seg_start == t else "xfade"})
            segments.append({"kind": "calm", "t0": card_from, "t1": chap_end, "tr": TRANSPOSE[ci % len(TRANSPOSE)], "idx": ci})
            t = chap_end

            # optional music-only gallery to reach the target length
            g = galleries.get(ci, 0)
            if g:
                g_from = t
                sb = int(preset["shotBeats"]) + 1
                nb = max(sb, round(g / B))
                i = 0
                while nb > 0:
                    d = min(sb, nb) * B
                    tr = tr_list[i % len(tr_list)]
                    scenes.append({"type": "shot", "from": t, "duration": d, "image": picker.pick(["exterior", "detail"]),
                                   "move": preset["moves"][(i + ci) % len(preset["moves"])], "transitionIn": tr})
                    events.append({"type": "whoosh", "frame": t, "strength": 0.7})
                    t += d
                    nb -= d // B
                    i += 1
                segments.append({"kind": "gallery", "t0": g_from, "t1": t})

        # ---- end screen
        scenes.append({"type": "endscreen", "from": t, "duration": END_SCREEN, "image": hero_idx, "transitionIn": "flash"})
        events.append({"type": "impact", "frame": t, "strength": 0.6})
        chap_meta.append({"index": len(body) + 1, "title": "Outro", "from": t, "hidden": True})
        segments.append({"kind": "end", "t0": t, "t1": t + END_SCREEN})
        t += END_SCREEN

        for a, b in zip(scenes, scenes[1:]):
            if b.get("transitionIn") != "xfade":
                a["transitionOut"] = b.get("transitionIn")
        for i, cm in enumerate(chap_meta):
            cm["to"] = chap_meta[i + 1]["from"] if i + 1 < len(chap_meta) else t
        return {"scenes": scenes, "events": sorted(events, key=lambda e: e["frame"]), "captions": captions, "callouts": callouts,
                "chapters": chap_meta, "segments": segments, "vo": vo, "total": t, "pulseUntil": t - END_SCREEN if fast else pulse_until, "n_body": len(body)}

    # ---- fit the 13-15 minute window
    gap_s, gap_p = 0.35, 0.9
    plan = layout(gap_s, gap_p, {})
    sec = plan["total"] / FPS
    log(f"natural length: {sec / 60:.2f} min")
    if fast:
        log("pace=fast: length follows the narration (no 13-15 min fitting)")
    elif sec > MAX_SEC:
        plan = layout(0.22, 0.55, {})
        if plan["total"] / FPS > MAX_SEC:
            speech = sum(len(cl) for c in chapters for row in c["clips"] for cl in row) / SR
            excess = plan["total"] / FPS - (IDEAL_SEC + 30)
            factor = min(1.15, speech / max(1.0, speech - excess))
            log(f"too long; re-voicing at {factor:.3f}x speed")
            speed = base_speed * factor
            synth(speed)
            plan = layout(0.22, 0.55, {})
        if plan["total"] / FPS > MAX_SEC:
            raise SystemExit(f"Script too long ({words} words -> {plan['total'] / FPS / 60:.1f} min). Trim it to about 2,200 words.")
    elif sec < MIN_SEC:
        for gs, gp in ((0.45, 1.2), (0.6, 1.6)):
            plan = layout(gs, gp, {})
            if plan["total"] / FPS >= MIN_SEC:
                break
        deficit = (IDEAL_SEC - 20) - plan["total"] / FPS
        if deficit > 0:
            n_body = plan["n_body"]
            n_gal = min(n_body, max(1, math.ceil(deficit / 28)))
            if deficit / n_gal > 45:
                raise SystemExit(f"Script too short ({words} words -> {plan['total'] / FPS / 60:.1f} min). Add about {int(deficit * 2.6)} words.")
            step = n_body / n_gal
            idxs = sorted({max(0, min(n_body - 2, int(step * (k + 0.5)))) for k in range(n_gal)})
            per = int(deficit / len(idxs) * FPS)
            plan = layout(gs, gp, {i: per for i in idxs})
            log(f"added {len(idxs)} music galleries of {per / FPS:.0f}s")
    total = plan["total"]
    log(f"final length: {total / FPS / 60:.2f} min ({total} frames)")

    # ---- soundtrack
    build_long_mix(plan, preset, total, out / "mix.wav", job, B, log)

    # ---- text outputs
    caps = plan["captions"]
    (out / "captions.srt").write_text(
        "\n".join(f"{i + 1}\n{srt_time(c['from'])} --> {srt_time(c['to'])}\n{c['text']}\n" for i, c in enumerate(caps)), encoding="utf-8")
    chap_lines = [f"{yt_time(c['from'])} {c['title']}" for c in plan["chapters"] if not c.get("hidden")]
    (out / "chapters.txt").write_text("\n".join(chap_lines) + "\n", encoding="utf-8")
    (out / "description.txt").write_text(description(job, chapters, chap_lines), encoding="utf-8")

    return {
        "durationInFrames": total,
        "beatFrames": B,
        "finalHit": total - 3 * B,
        "scenes": plan["scenes"],
        "events": plan["events"],
        "captions": caps,
        "callouts": plan["callouts"],
        "chapters": plan["chapters"],
        "pulseUntil": plan["pulseUntil"],
    }


def description(job: dict, chapters, chap_lines) -> str:
    title = job.get("title", "").strip()
    first = next((p for c in chapters if not is_hook(c["title"]) for p in c["paragraphs"]), [])
    intro = (job.get("descriptionIntro") or "").strip() or ("" if ja else " ").join(first[:2])
    ja = (job.get("language") or "").lower().startswith("ja")
    heading = (job.get("descriptionTitle") or "").strip() or f"{title} — {'徹底レビュー' if ja else 'Full Review'}"
    lines = [heading + (f" | {job['dealer']}" if job.get("dealer") else ""), "", intro, "",
             "⏱️ チャプター" if ja else "⏱️ Chapters", *chap_lines, ""]
    specs = [s for s in job.get("specs", []) if s.get("value")]
    if specs:
        lines += ["📋 主なスペック" if ja else "📋 Key specs", *[f"• {s.get('label', '')}: {s['value']}" for s in specs], ""]
    if job.get("price"):
        lines.append(f"💰 {job.get('priceLabel') or 'Price'}: {job['price']}")
    if job.get("dealer") or job.get("contact"):
        lines.append(f"📍 {job.get('dealer', '')} {('— ' + job['contact']) if job.get('contact') else ''}".strip())
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9]+", title) if not w.isdigit()][:3]
    credits = [c for c in (job.get("credits") or []) if c]
    if credits:
        lines += ["", "📷 写真" if ja else "📷 Photos", *credits]
    tags = job.get("hashtags") or (["#cars", "#carreview"] + [f"#{w.lower()}" for w in words])
    lines += ["", " ".join(tags)]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- long soundtrack
def build_long_mix(plan: dict, preset: dict, total: int, out_path: Path, job: dict, B: int, log):
    beat = B / FPS
    N = int(total / FPS * SR) + SR
    music = np.zeros((N, 2), dtype=np.float32)
    style = preset["music"]

    def put(buf, x, t_sec, gain=1.0):
        a = int(t_sec * SR)
        b = min(len(buf), a + len(x))
        if b > a:
            buf[a:b] += (x[: b - a] * gain).astype(np.float32)

    user_music = None
    if job.get("_music_path"):
        user_music = audio._load_audio(Path(job["_music_path"])).astype(np.float32)
        user_music *= 0.11 / (audio._rms(user_music) + 1e-9)

    segs = []
    for seg in plan["segments"]:
        if seg["kind"] == "drive" and segs and segs[-1]["kind"] == "drive" and segs[-1]["t1"] == seg["t0"]:
            segs[-1] = {**segs[-1], "t1": seg["t1"]}
        else:
            segs.append(dict(seg))
    for seg in segs:
        t0, t1 = seg["t0"] / FPS, seg["t1"] / FPS
        dur = t1 - t0
        if user_music is not None:
            reps = int(np.ceil(dur * SR / len(user_music))) + 1
            start = int(t0 * SR) % len(user_music)
            x = np.tile(user_music, (reps + 1, 1))[start: start + int(dur * SR)]
            x = audio._fade(x.astype(np.float64), 0.3, 0.5).astype(np.float32)
            gain = 0.55 if seg["kind"] in ("calm", "end") else 1.0
        elif seg["kind"] == "open":
            x = audio.render_open(style, seg["drop"] / FPS, dur, beat)
            gain = 1.0
        elif seg["kind"] == "gallery":
            x = audio.render_bed(style, dur + 0.4, beat, tr=0, bar_offset=2)
            gain = 1.0
        elif seg["kind"] == "drive":
            x = audio.render_bed(style, dur + 0.4, beat, tr=0, bar_offset=int(round(seg["t0"] / (4 * B))))
            gain = 0.9
        else:  # calm / end
            x = audio.render_bed("ambient", dur + 0.6, beat, tr=seg.get("tr", 0), bar_offset=seg.get("idx", 0), drums=0.6)
            gain = 0.7
        put(music, x, t0, gain)
        log(f"  music {seg['kind']} {t0:6.1f}s -> {t1:6.1f}s")

    sfx = np.zeros((N, 2), dtype=np.float32)
    for ev in plan["events"]:
        t = ev["frame"] / FPS
        g = ev.get("strength", 1.0)
        if ev["type"] == "impact":
            put(sfx, audio.impact(g), t, 0.5 * g)
        elif ev["type"] == "whoosh":
            put(sfx, audio.whoosh(0.42), t - 0.3, 0.45 * g)
        elif ev["type"] == "pop":
            put(sfx, np.stack([audio.pop()] * 2, axis=1), t, 0.3 * g)
        elif ev["type"] == "riser":
            put(sfx, audio.riser(ev["duration"] / FPS), t, 0.5 * g)

    vo = np.zeros(N, dtype=np.float32)
    rate = 100  # envelope resolution (Hz)
    active = np.zeros(int(N / SR * rate) + 2)
    for start, clip in plan["vo"]:
        if clip is None or len(clip) == 0 or not np.any(clip):
            continue
        clip = clip * (0.13 / (audio._rms(clip) + 1e-9))
        a = int(start * SR)
        b = min(N, a + len(clip))
        vo[a:b] += clip[: b - a].astype(np.float32)
        active[max(0, int((start - 0.15) * rate)): int((start + len(clip) / SR + 0.3) * rate)] = 1
    coef = np.exp(-1 / (0.08 * rate))
    env = np.clip(signal.filtfilt([1 - coef], [1, -coef], active), 0, 1) if active.any() else active
    env_full = np.interp(np.arange(N) / SR * rate, np.arange(len(env)), env).astype(np.float32)

    mix = music * (1 - 0.6 * env_full)[:, None] + sfx * (1 - 0.3 * env_full)[:, None] + vo[:, None]
    del music, sfx
    pk = float(np.percentile(np.abs(mix[:: 7]), 99.8)) + 1e-9
    np.tanh(mix / pk * 1.2, out=mix)
    mix *= 0.95 / np.tanh(1.2)
    fade = int(2.0 * SR)
    mix[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None]
    mix = mix[: int(total / FPS * SR)]
    wavfile.write(str(out_path), SR, (np.clip(mix, -1, 1) * 32767).astype(np.int16))
    log("long soundtrack mixed")
