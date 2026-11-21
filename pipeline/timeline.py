"""Beat-locked edit decision list shared by the audio synth and the Remotion renderer."""
from __future__ import annotations

import math


def _beats_for(frames_needed: float, B: int, minimum: int, multiple: int = 1) -> int:
    beats = max(minimum, math.ceil(frames_needed / B))
    return int(math.ceil(beats / multiple) * multiple)


def build(n_images: int, hero: int, preset: dict, vo_secs: dict, fps: int, n_specs: int) -> dict:
    B = int(preset["beatFrames"])
    moves = preset["moves"]
    transitions = preset["transitions"]
    scenes: list[dict] = []
    events: list[dict] = []
    t = 0

    def add(kind: str, beats: int, **kw) -> dict:
        nonlocal t
        s = {"type": kind, "from": t, "duration": beats * B, **kw}
        scenes.append(s)
        t += beats * B
        return s

    others = [i for i in range(n_images) if i != hero] or [hero]
    order = list(others)
    k = 0
    pool = list(range(n_images))
    while len(order) < 3:  # always at least 3 montage shots
        cand = pool[k % len(pool)]
        if cand != order[-1] or n_images == 1:
            order.append(cand)
        k += 1
    order = order[:12]

    # ---- intro
    ib = int(preset["introBeats"])
    teasers = [{"frame": b * B, "image": order[(b - ib // 2) % len(order)]} for b in range(ib // 2, ib)]
    intro = add("intro", ib, cues={"tagline": 0, "title": (ib // 4) * B, "teasers": teasers})
    events.append({"type": "riser", "frame": 0, "duration": intro["duration"], "strength": 0.9})
    for tz in teasers:
        events.append({"type": "pop", "frame": tz["frame"], "strength": 0.6})

    # ---- hero (title slam on the drop)
    vo_hero_start = round(B * 0.75)
    hb = _beats_for(vo_hero_start + (vo_secs.get("hero", 0) + 0.6) * fps, B, 8 if B <= 16 else 6, 2)
    hero_s = add("hero", hb, image=hero, transitionIn="impact", cues={"title": 0, "subtitle": B * 2, "vo": vo_hero_start})
    events.append({"type": "impact", "frame": hero_s["from"], "strength": 1.0})

    # ---- montage
    sb = int(preset["shotBeats"])
    for i, img in enumerate(order):
        tr = transitions[i % len(transitions)]
        s = add("shot", sb, image=img, move=moves[i % len(moves)], transitionIn=tr)
        events.append({"type": "whoosh", "frame": s["from"], "strength": 1.0 if tr in ("whip", "zoom") else 0.6})

    # ---- specs
    n_specs = max(0, min(4, n_specs))
    vo_specs_start = round(B * 0.5)
    spb = _beats_for(vo_specs_start + (vo_secs.get("specs", 0) + 0.6) * fps, B, max(6, n_specs + 4), 2)
    spec_cues = [B * (1 + j) for j in range(n_specs)]
    specs = add("specs", spb, image=hero, transitionIn="whip", cues={"cards": spec_cues, "vo": vo_specs_start})
    events.append({"type": "whoosh", "frame": specs["from"], "strength": 1.0})
    events.append({"type": "impact", "frame": specs["from"], "strength": 0.45})
    for c in spec_cues:
        events.append({"type": "pop", "frame": specs["from"] + c, "strength": 1.0})

    # ---- price (slams on the second drop)
    vo_price_start = 4
    pb = _beats_for(vo_price_start + (vo_secs.get("price", 0) + 0.5) * fps, B, 4, 2)
    price = add("price", pb, image=order[len(order) // 2], transitionIn="impact", cues={"slam": 0, "vo": vo_price_start})
    build_start = max(hero_s["from"] + B, price["from"] - 4 * B)
    events.append({"type": "riser", "frame": build_start, "duration": price["from"] - build_start, "strength": 0.8})
    events.append({"type": "impact", "frame": price["from"], "strength": 1.0})

    # ---- outro / CTA
    vo_outro_start = round(B * 0.5)
    ob = _beats_for(vo_outro_start + (vo_secs.get("outro", 0) + 1.6) * fps, B, 8 if B <= 16 else 6, 2)
    outro_from = t
    total = outro_from + ob * B
    final_hit = max(outro_from + B, total - 3 * B)
    outro = add("outro", ob, image=hero, transitionIn="flash",
                cues={"vo": vo_outro_start, "cta": B * 2, "final": final_hit - outro_from})
    events.append({"type": "whoosh", "frame": outro["from"], "strength": 0.7})
    events.append({"type": "impact", "frame": outro["from"], "strength": 0.5})
    events.append({"type": "impact", "frame": final_hit, "strength": 0.9})

    # transitionOut = the next scene's transitionIn
    for a, b in zip(scenes, scenes[1:]):
        a["transitionOut"] = b.get("transitionIn")

    vo_starts = {
        "hero": hero_s["from"] + vo_hero_start,
        "specs": specs["from"] + vo_specs_start,
        "price": price["from"] + vo_price_start,
        "outro": outro["from"] + vo_outro_start,
    }
    return {
        "fps": fps,
        "beatFrames": B,
        "durationInFrames": total,
        "finalHit": final_hit,
        "scenes": scenes,
        "events": sorted(events, key=lambda e: e["frame"]),
        "voStarts": vo_starts,
    }
