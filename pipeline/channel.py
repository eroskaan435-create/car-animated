"""Reference-channel automation (driven by .github/workflows/channel.yml and docs/index.html).

    python pipeline/channel.py sync          # list the reference channel, schedule, reschedule, pick the next video
    python pipeline/channel.py make <id>     # build jobs/yt-<id>/ (photos + Japanese script) for a queued video

State lives in the repo:
  channel/config.json   reference channel URL, my channel name, defaults (time slot, voice, decor...)
  channel/queue.json    every reference video, oldest first: status, publishAt (editable on the page), intro, links
  channel/intros/<id>.* optional intro clip (video -> put in front, audio -> played before the narration)

Only the reference video's title/description are used, to work out which car it is about. The script is written
fresh from general knowledge and the photos come from Wikimedia Commons (free licences, credited in the description).
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
import photos  # noqa: E402
import youtube  # noqa: E402

CFG = Path("channel/config.json")
QUEUE = Path("channel/queue.json")
INTROS = Path("channel/intros")
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
UA = "car-animated/1.0 (https://github.com/zaars59208/car-animated)"

DEFAULTS = {
    "reference": {"url": ""},
    "mine": {},
    "language": "ja",
    "voice": "ja-JP-KeitaNeural",
    "voiceSpeed": 1.08,
    "timezone": "Asia/Tokyo",
    "publishTime": "18:00",
    "everyDays": 1,
    "leadHours": 48,
    "decor": {"frame": True, "stickers": True, "stickerEvery": 60, "maxStickers": 1},
    "transitionSfx": 0.35,
}


def now() -> datetime:
    return datetime.now(timezone.utc)


def load_cfg() -> dict:
    cfg = json.loads(CFG.read_text(encoding="utf-8")) if CFG.exists() else {}
    return {**DEFAULTS, **cfg}


def load_queue() -> dict:
    return json.loads(QUEUE.read_text(encoding="utf-8")) if QUEUE.exists() else {"items": []}


def save_queue(q: dict):
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    q["updated"] = now().isoformat(timespec="seconds")
    QUEUE.write_text(json.dumps(q, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def parse_t(s: str | None) -> datetime | None:
    if not s:
        return None
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def ytdlp(*args) -> dict:
    out = subprocess.run(["yt-dlp", "--no-warnings", "-J", *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout
    return json.loads(out)


def log(m):
    print(m, flush=True)


# --------------------------------------------------------------------------- sync
def next_slot(after: datetime, cfg: dict) -> datetime:
    tz = ZoneInfo(cfg["timezone"])
    hh, mm = (int(x) for x in cfg["publishTime"].split(":"))
    local = after.astimezone(tz)
    slot = local.replace(hour=hh, minute=mm, second=0, microsecond=0)
    while slot <= local:
        slot += timedelta(days=1)
    return slot.astimezone(timezone.utc)


def sync() -> str:
    cfg = load_cfg()
    q = load_queue()
    items = q.setdefault("items", [])
    by_id = {it["id"]: it for it in items}
    url = (cfg.get("reference") or {}).get("url", "").strip()

    # 1) reference channel -> queue (oldest first)
    if url:
        base = re.sub(r"/(videos|shorts|streams|featured)/?$", "", url.rstrip("/"))
        d = ytdlp("--flat-playlist", base + "/videos")
        entries = [e for e in (d.get("entries") or []) if e.get("id")]
        entries.reverse()  # YouTube lists newest first
        q["reference"] = {"url": base, "name": d.get("channel") or d.get("uploader") or d.get("title"), "count": len(entries)}
        order = max([it.get("order", 0) for it in items] + [0])
        added = 0
        for e in entries:
            if e["id"] in by_id:
                continue
            order += 1
            it = {"id": e["id"], "order": order, "title": e.get("title") or "", "url": f"https://www.youtube.com/watch?v={e['id']}",
                  "durationSec": e.get("duration"), "status": "queued", "publishAt": None}
            items.append(it)
            by_id[it["id"]] = it
            added += 1
        log(f"reference: {q['reference']['name']} ({len(entries)} videos, {added} new)")

    # videos already made by hand (job.json "sourceVideo")
    for jp in Path("jobs").glob("*/job.json"):
        try:
            src = json.loads(jp.read_text(encoding="utf-8")).get("sourceVideo")
        except Exception:
            continue
        it = by_id.get(src)
        if it and it["status"] == "queued":
            it.update(status="made", job=jp.parent.name, note="made by hand")

    # 2) intros present in channel/intros (and forget removed ones)
    for it in items:
        if it.get("intro") and not (Path("channel") / it["intro"]).exists():
            it.pop("intro", None)
            it.pop("introType", None)
    for f in INTROS.glob("*.*") if INTROS.exists() else []:
        it = by_id.get(f.stem)
        if it:
            it["intro"] = f"{INTROS.name}/{f.name}"
            it["introType"] = "video" if f.suffix.lower() in VIDEO_EXT else "audio"

    # 3) default publish slots for queued videos without one (editable on the page)
    last = max([parse_t(it.get("publishAt")) for it in items if it.get("publishAt")] + [now() + timedelta(hours=cfg["leadHours"] / 2)])
    for it in sorted(items, key=lambda x: x.get("order", 0)):
        if it["status"] in ("queued", "requested") and not it.get("publishAt"):
            last = next_slot(last + timedelta(days=max(0, cfg["everyDays"] - 1)), cfg)
            it["publishAt"] = last.isoformat().replace("+00:00", "Z")

    # 4) status housekeeping + reschedules on my channel
    for it in items:
        t = parse_t(it.get("publishAt"))
        if it["status"] == "scheduled" and t and t <= now():
            it["status"] = "published"
        if it["status"] == "making" and parse_t(it.get("startedAt")) and now() - parse_t(it["startedAt"]) > timedelta(hours=5):
            it.update(status="failed", note="render did not finish (see Actions)")
        if it["status"] == "scheduled" and it.get("myVideoId") and it.get("publishAt") != it.get("uploadedPublishAt"):
            if youtube.configured():
                youtube.reschedule(it["myVideoId"], it.get("publishAt"))
                it["uploadedPublishAt"] = it.get("publishAt")

    if youtube.configured():
        try:
            me = youtube.my_channel()
            if me.get("id"):
                q["mine"] = me
        except SystemExit as e:
            log(f"my channel: {e}")

    # 5) what to make next: a requested video, else the next queued one due within leadHours
    nxt = ""
    if not any(it["status"] == "making" for it in items):
        req = [it for it in items if it["status"] == "requested"]
        due = [it for it in sorted(items, key=lambda x: x.get("order", 0)) if it["status"] == "queued"]
        if req:
            nxt = sorted(req, key=lambda x: x.get("order", 0))[0]["id"]
        elif due and parse_t(due[0]["publishAt"]) - now() <= timedelta(hours=cfg["leadHours"]):
            nxt = due[0]["id"]
    save_queue(q)
    log(f"next: {nxt or '-'}")
    return nxt


# --------------------------------------------------------------------------- LLM (Ollama, free)
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")


def ollama(prompt: str, system: str, max_tokens: int, fmt: str | None = None, temp=0.7) -> str:
    body = {"model": MODEL, "system": system, "prompt": prompt, "stream": False,
            "options": {"temperature": temp, "top_p": 0.9, "repeat_penalty": 1.1, "num_ctx": 4096, "num_predict": max_tokens}}
    if fmt:
        body["format"] = fmt
    req = urllib.request.Request(f"{OLLAMA}/api/generate", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.loads(r.read())["response"]


def identify(title: str, desc: str) -> dict:
    system = "You extract structured data about cars from YouTube video titles and descriptions. Answer with JSON only."
    prompt = (
        "Which car is this video about?\n"
        f"TITLE: {title}\nDESCRIPTION: {desc[:1500]}\n\n"
        'Return JSON: {"make": "manufacturer in English", "model": "model name in English", '
        '"name_ja": "manufacturer + model in Japanese as Japanese people write it, e.g. ホンダ N-BOX", '
        '"year": "model year from the title or empty", '
        '"type": "one of sedan, suv, truck, sports, luxury, electric", '
        '"youtube_title": "a NEW catchy Japanese YouTube title (max 60 characters) for a review of this car; do not copy the original title", '
        '"tags": ["5 to 8 short Japanese or English hashtags without #"]}'
    )
    d = json.loads(ollama(prompt, system, 400, fmt="json", temp=0.2))
    d["type"] = d.get("type") if d.get("type") in ("sedan", "suv", "truck", "sports", "luxury", "electric") else "sedan"
    return d


JA_SYSTEM = (
    "あなたはプロの自動車系YouTubeチャンネルの台本ライターです。ナレーターがそのまま読み上げる日本語の本文だけを書きます。"
    "見出し、箇条書き、記号、絵文字、英語の文章、ト書き、効果音の指示は書きません。です・ます調で、短めの文を中心に、テンポよく親しみやすく書きます。"
    "価格、馬力、トルク、燃費、寸法、発売日などの具体的な数値は、確実に正しいと分かっているもの以外は書かず、定性的に説明してください。"
    "存在しない装備やグレードを作らないでください。「このセクションでは」のような言い方はしません。"
)

JA_CHAPTERS = [
    ("Hook", 130, "冒頭の掴み。このクルマの一番の魅力を短く伝え、最後まで見たくなるようにする。挨拶はしない。"),
    ("エクステリア", 380, "外観デザイン。フロント、サイド、リア、ライト、ホイール、ボディカラーの印象。"),
    ("インテリア", 380, "内装。デザイン、素材の質感、シート、運転席まわり、メーターや画面。"),
    ("室内空間と使い勝手", 340, "室内の広さ、後席、荷室、収納、乗り降りのしやすさ、日常での使いやすさ。"),
    ("エンジンと走り", 380, "パワートレインの特徴と、街中や高速での走り、乗り心地、静かさ。"),
    ("安全装備", 300, "先進安全装備や運転支援を、確実な範囲で一般的に説明。"),
    ("燃費と維持費", 300, "燃費性能や税金などの維持費を、確実な範囲で定性的に説明。"),
    ("価格とライバル", 330, "価格帯の考え方と、主なライバル車との違いを定性的に比較。"),
    ("まとめ", 280, "長所と短所をまとめ、どんな人におすすめかを伝え、最後にチャンネル登録と高評価をお願いして締める。"),
]

CJK = re.compile(r"[぀-ヿ一-鿿]")


def clean_ja(text: str) -> str:
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            out.append("")
            continue
        if s.startswith("#") or len(CJK.findall(s)) < len(s) * 0.3:
            continue  # headings / English chatter
        s = re.sub(r"[\[【(（][^\]】)）]*(音楽|BGM|効果音|ナレーション|映像)[^\]】)）]*[\]】)）]", "", s)
        # English fragments the model sometimes mixes in: "futurism（未来主義）" / "アルcantaro（アルカンタラ）" -> the Japanese
        s = re.sub(r"[゠-ヿA-Za-z\-]*[A-Za-z]{2,}[゠-ヿA-Za-z\-]*\s*[（(]([^）)]+)[）)]", r"\1", s)
        s = re.sub(r"[*_`#>]+", "", s)
        s = re.sub(r"^\s*[-•・]\s*", "", s)
        s = re.sub(r"^(ナレーション|ナレーター)\s*[:：]\s*", "", s)
        out.append(s.strip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def write_script_ja(car: dict, job_dir: Path):
    name = car.get("name_ja") or f"{car.get('make', '')} {car.get('model', '')}".strip()
    about = f"{name}（{car.get('make', '')} {car.get('model', '')}{' ' + car['year'] if car.get('year') else ''}）"
    heads = "、".join(h for h, _, _ in JA_CHAPTERS)
    parts = []
    for head, chars, goal in JA_CHAPTERS:
        prev = parts[-1][1][-300:] if parts else ""
        prompt = (f"対象のクルマ: {about}\n動画: このクルマを紹介する日本語のYouTubeレビュー動画。構成: {heads}。\n"
                  + (f"直前のセクションの終わり（繰り返さず自然に続ける）:「…{prev}」\n" if prev else "")
                  + f"今から「{head}」のセクションだけを書いてください。\n内容: {goal}\n長さ: 約{chars}文字、段落は{max(1, round(chars / 130))}つ程度。")
        text = ""
        for _ in range(2):
            text = clean_ja(ollama(prompt, JA_SYSTEM, int(chars * 1.6)))
            if len(text) >= chars * 0.5:
                break
        log(f"[{head}] {len(text)} chars")
        parts.append((head, text))
    md = [f"<!-- Generated by {MODEL} for {about}. Check facts before rendering. -->", ""]
    for head, text in parts:
        md += [f"## {head}", "", text, ""]
    (job_dir / "script.md").write_text("\n".join(md), encoding="utf-8")
    return sum(len(t) for _, t in parts)


# --------------------------------------------------------------------------- make
def make(vid: str):
    cfg = load_cfg()
    q = load_queue()
    it = next(x for x in q["items"] if x["id"] == vid)
    job_name = f"yt-{vid}"
    job_dir = Path("jobs") / job_name
    if job_dir.exists():
        shutil.rmtree(job_dir)
    job_dir.mkdir(parents=True)

    try:
        meta = ytdlp(it["url"])
    except subprocess.CalledProcessError as e:  # e.g. YouTube's bot check on CI IPs: the queued title is enough
        log(f"yt-dlp metadata failed ({(e.stderr or '').strip()[:200]}); using the queued title")
        meta = {}
    title, desc = meta.get("title") or it.get("title", ""), meta.get("description") or ""
    it["refPublished"] = meta.get("upload_date")
    car = identify(title, desc)
    log(f"car: {car}")

    picked = photos.gather(car, target=int(cfg.get("photos", 60)))
    if len(picked) < 8:
        raise SystemExit(f"only {len(picked)} free photos of {car.get('make')} {car.get('model')} found")
    # photos are downloaded at render time (render.yml -> photos.py fetch), only URLs + credits are committed
    images, remote = [], []
    for i, ph in enumerate(picked, 1):
        f = f"{i:02d}.jpg"
        images.append({"file": f, "caption": "", "category": ph["cat"]})
        remote.append({"file": f, "url": ph["url"], "fallback": ph["fallback"]})
    short, full = photos.credits(picked)
    (job_dir / "credits.txt").write_text("\n".join(full) + "\n", encoding="utf-8")
    repo = os.environ.get("GITHUB_REPOSITORY", "zaars59208/car-animated")
    credits = short + [f"全写真クレジット: https://github.com/{repo}/blob/main/jobs/{job_name}/credits.txt"]
    log(f"photos: {len(images)}")

    chars = write_script_ja(car, job_dir)
    log(f"script: {chars} chars")

    name_ja = car.get("name_ja") or f"{car.get('make', '')} {car.get('model', '')}"
    yt_title = (car.get("youtube_title") or f"{name_ja}徹底解説！魅力と注意点をまるごとチェック")[:100]
    mine = (q.get("mine") or {}).get("name") or (cfg.get("mine") or {}).get("name") or ""
    tags = []
    for t in [name_ja, car.get("model", ""), f"{car.get('make', '')}{car.get('model', '')}", car.get("make", ""), "新型車", "車レビュー", "自動車"]:
        t = re.sub(r"[\s・\-]+", "", t or "")
        if t and t.lower() not in [x.lower() for x in tags]:
            tags.append(t)
    mine_tag = re.sub(r"\s+", "", mine)
    job = {
        "version": 1, "title": name_ja, "tagline": "", "vehicleType": car["type"], "mode": "long", "stage": "render",
        "pace": "fast", "language": cfg["language"], "burnCaptions": True, "alsoShort": False,
        "thumbnailText": name_ja, "thumbnailBadge": "徹底解説", "price": "", "priceLabel": "", "dealer": "", "contact": "",
        "cta": "チャンネル登録お願いします", "specs": [],
        "voice": {"enabled": True, "voice": "am_michael", "edgeVoice": cfg["voice"], "speed": cfg["voiceSpeed"]},
        "images": images, "remoteImages": remote, "heroIndex": 0, "facts": {}, "pros": "", "cons": "",
        "descriptionTitle": yt_title + (f" | {mine}" if mine else ""),
        "hashtags": [f"#{t}" for t in tags] + ([f"#{mine_tag}"] if mine else []),
        "credits": credits, "decor": cfg["decor"], "transitionSfx": cfg["transitionSfx"],
        "sourceVideo": vid,
        "youtube": {"queueId": vid, "title": yt_title, "tags": tags, "categoryId": "2", "publishAt": it.get("publishAt")},
    }
    if it.get("intro") and (Path("channel") / it["intro"]).exists():
        src = Path("channel") / it["intro"]
        dst = f"intro{src.suffix.lower()}"
        shutil.copy(src, job_dir / dst)
        job["introVideo" if it.get("introType") == "video" else "introAudio"] = dst
    (job_dir / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    it.update(status="making", job=job_name, startedAt=now().isoformat(timespec="seconds"), car=f"{car.get('make', '')} {car.get('model', '')}".strip(),
              myTitle=yt_title, note="")
    save_queue(q)
    log(f"job ready: {job_dir}")


if __name__ == "__main__":
    if sys.argv[1] == "sync":
        n = sync()
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"next={n}\n")
    elif sys.argv[1] == "make":
        try:
            make(sys.argv[2])
        except BaseException as e:  # show why on the page (queue note) instead of only in the Actions log
            import traceback
            traceback.print_exc()
            shutil.rmtree(Path("jobs") / f"yt-{sys.argv[2]}", ignore_errors=True)
            q = load_queue()
            for it in q.get("items", []):
                if it["id"] == sys.argv[2] and it.get("status") != "failed":
                    it.update(status="failed", note=f"{type(e).__name__}: {e}"[:300])
            save_queue(q)
            sys.exit(1)
