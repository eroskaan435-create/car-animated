"""Write a ~2,100-word YouTube review script with a free local LLM (Ollama).

    python pipeline/script_gen.py jobs/<id>            # writes jobs/<id>/script.md

Env: OLLAMA_MODEL (default qwen2.5:7b), OLLAMA_URL (default http://127.0.0.1:11434)
The model is only given the facts from job.json and told not to invent numbers,
so the script stays accurate; review it on the upload page before rendering.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")

# (heading, target words, goal)
CHAPTERS = [
    ("Hook", 70, "A gripping 20-30 second cold open. Tease the most exciting thing about this car and what the viewer will learn. No greetings like 'hey guys'."),
    ("Overview", 210, "Introduce the car: what it is, who it is for, and where it sits in the market. Mention the price if given."),
    ("Exterior Design", 230, "Walk around the outside: stance, front, profile, rear, lights, wheels, paint. Describe how it looks and feels in person."),
    ("Interior and Comfort", 230, "Sit inside: materials, seats, driving position, space, quietness, quality impressions."),
    ("Technology and Features", 200, "Infotainment, screens, driver aids, connectivity and the listed features."),
    ("Engine and Performance", 230, "The powertrain, power figures from the facts, acceleration, gearbox, how the performance feels."),
    ("Driving Experience", 200, "Ride, handling, steering, comfort on the highway and in town, everyday usability."),
    ("Safety", 150, "Safety equipment and driver-assistance systems in general terms unless specific items are listed."),
    ("Practicality", 160, "Cargo space, storage, seating, running costs and ownership in general terms unless given."),
    ("Price and Rivals", 180, "Value for money, the price, and how it compares with the listed rivals (qualitatively, no invented figures)."),
    ("Verdict", 170, "Summarize strengths and weaknesses, who should buy it, and finish by inviting viewers to {cta}{dealer_part} and to like and subscribe."),
]

SYSTEM = (
    "You are a professional automotive YouTube scriptwriter. You write natural, engaging narration that will be read aloud "
    "by a voice-over artist. Output ONLY the narration for the requested section as plain paragraphs: no headings, no lists, "
    "no markdown, no emojis, no stage directions, no sound or music cues, no phrases like 'in this section' or 'in this chapter'. "
    "Never invent specific numbers, prices, dates, awards, ratings, trims or features that are not in the FACTS. If a detail is "
    "missing, talk about it in general, qualitative terms or skip it. Write numbers the way they should be spoken when it helps "
    "(for example '0-60' as 'zero to sixty'). Vary sentence length and keep it conversational and confident."
)


def facts_block(job: dict) -> str:
    f = job.get("facts") or {}
    rows = [
        ("Model", job.get("title")),
        ("Vehicle style", job.get("vehicleType") if job.get("vehicleType") not in (None, "auto") else None),
        ("Tagline", job.get("tagline")),
        ((job.get("priceLabel") or "Price"), job.get("price")),
    ]
    rows += [(s.get("label"), s.get("value")) for s in job.get("specs", []) if s.get("value")]
    for k in ("engine", "transmission", "drivetrain", "fuel", "seats", "cargo", "features", "rivals", "notes"):
        rows.append((k.title(), f.get(k)))
    rows += [("Pros", job.get("pros")), ("Cons", job.get("cons")), ("Presented by (dealer)", job.get("dealer")),
             ("Dealer contact", job.get("contact"))]
    def norm(v) -> str:
        parts = [x.strip(" -•\t") for x in re.split(r"[\r\n]+", str(v))]
        return "; ".join(re.sub(r"\s+", " ", x) for x in parts if x)

    return "\n".join(f"- {k}: {norm(v)}" for k, v in rows if k and v and str(v).strip())


def ollama(prompt: str, max_tokens: int) -> str:
    body = json.dumps({
        "model": MODEL, "system": SYSTEM, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.7, "top_p": 0.9, "repeat_penalty": 1.1, "num_ctx": 4096, "num_predict": max_tokens},
    }).encode()
    req = urllib.request.Request(f"{URL}/api/generate", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.loads(r.read())["response"]


def clean(text: str) -> str:
    lines = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            lines.append("")
            continue
        if s.startswith("#") or re.match(r"^(sure|here('s| is)|certainly|okay)\b", s, re.I) or re.match(r"^\*\*.*\*\*$", s):
            continue
        s = re.sub(r"\[[^\]]*\]", "", s)           # [music], [b-roll]
        s = re.sub(r"[*_`#]+", "", s)
        s = re.sub(r"^\s*[-•]\s+", "", s)
        s = re.sub(r"^(narrator|voice ?over|vo)\s*:\s*", "", s, flags=re.I)
        lines.append(s.strip())
    out = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return out.strip('"“” ')


def main():
    job_dir = Path(sys.argv[1])
    job = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    facts = facts_block(job)
    dealer_part = f" at {job['dealer']}" if job.get("dealer") else ""
    cta = (job.get("cta") or "book a test drive").strip().lower()
    titles = [c[0] for c in CHAPTERS]
    parts: list[tuple[str, str]] = []
    t_start = time.time()
    for name, words, goal in CHAPTERS:
        goal = goal.format(cta=cta, dealer_part=dealer_part)
        prev = parts[-1][1][-600:] if parts else ""
        paras = max(1, round(words / 75))
        prompt = (
            f"FACTS about the vehicle (the only facts you may use):\n{facts}\n\n"
            f"VIDEO: a 14-minute YouTube review of this car. Sections in order: {', '.join(titles)}.\n"
            + (f"END OF THE PREVIOUS SECTION (continue naturally, do not repeat it):\n\"...{prev}\"\n\n" if prev else "")
            + f"Now write ONLY the \"{name}\" section.\nGoal: {goal}\n"
            f"Length: about {words} words ({int(words * 0.85)}-{int(words * 1.15)}), in {paras} paragraph{'s' if paras > 1 else ''}."
        )
        t0 = time.time()
        text = clean(ollama(prompt, int(words * 2.2)))
        n = len(text.split())
        if n < words * 0.7:
            more = clean(ollama(prompt + f"\n\nYou already wrote:\n{text}\n\nContinue this section with about {words - n} more words. "
                                "Do not repeat anything; output only the continuation.", int((words - n) * 2.2)))
            text = (text + "\n\n" + more).strip()
            n = len(text.split())
        print(f"[{name}] {n} words in {time.time() - t0:.0f}s", flush=True)
        parts.append((name, text))

    total = sum(len(t.split()) for _, t in parts)
    md = [
        "<!-- Review and edit freely. Each '## ' heading starts a chapter. "
        f"About 2,000-2,300 words = 13-15 minutes. Generated by {MODEL}. Check every fact before rendering. -->",
        "",
    ]
    for name, text in parts:
        md += [f"## {name}", "", text, ""]
    (job_dir / "script.md").write_text("\n".join(md), encoding="utf-8")
    print(f"script.md: {total} words, {time.time() - t_start:.0f}s total")


if __name__ == "__main__":
    main()
