"""Find 50+ free-licence photos of a car (exterior, interior, engine, details) and download them at render time.

Sources (all allow commercial use with attribution: CC0, public domain, CC BY, CC BY-SA):
  * Wikimedia Commons: the model's category tree (via Wikidata P373), its Wikipedia articles, and a file search
  * Openverse (api.openverse.org): CC search engine over Flickr, Wikimedia and others, with targeted queries
    ("<model> interior", "... dashboard", "... engine", ...)

    python pipeline/photos.py fetch jobs/<id>      # download job["remoteImages"] (done in render.yml before prep)

Photos are not committed to the repo (50+ per video would bloat it); the job keeps their URLs and credits.
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

UA = "car-animated/1.0 (https://github.com/zaars59208/car-animated)"
FREE = re.compile(r"^(cc0|public domain|pd|pdm|cc by(-sa)? \d(\.\d)?( [a-z]+)?|by(-sa)?|cc-by(-sa)?-\d.*)$", re.I)
EXCLUDE = re.compile(r"\b(toy|tomica|miniature|scale model|model car|diecast|die-cast|lego|brochure|catalog(ue)?|poster|sketch|"
                     r"drawing|logo|plamo|plastic model|mini 4wd|choro ?q|rendering|map|diagram|chart|crash test|accident)\b", re.I)
HINTS = [
    ("engine", re.compile(r"engine|motor ?room|engine ?bay|under ?the ?hood|エンジン", re.I)),
    ("interior", re.compile(r"interior|dashboard|cockpit|cabin|inside|\bseats?\b|\bseating\b|steering|console|instrument|\bmeter|trunk|cargo|luggage|"
                            r"boot|内装|インテリア|室内|運転席|荷室|シート", re.I)),
    ("detail", re.compile(r"wheel|rim\b|headlight|headlamp|tail ?light|tail ?lamp|rear ?lamp|badge|emblem|grille|mirror|"
                          r"\blamp\b|\bdetail|ホイール|ライト", re.I)),
    ("exterior", re.compile(r"front|rear|side|view|profile|exterior|left|right|外観", re.I)),
]
QUOTA = {"interior": 16, "engine": 5, "detail": 10}


def log(m):
    print(m, flush=True)


def get_json(url: str, tries=3) -> dict:
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < tries - 1:
                time.sleep(20 * (i + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if i == tries - 1:
                raise
            time.sleep(3)
    return {}


def api(host: str, params: dict) -> dict:
    return get_json(f"https://{host}/w/api.php?" + urllib.parse.urlencode({**params, "format": "json"}))


def commons(params: dict) -> dict:
    return api("commons.wikimedia.org", params)


def norm(s: str) -> str:
    s = re.sub(r"^(file|ファイル):", "", s, flags=re.I)
    s = re.sub(r"\.(jpe?g|png|webp|tiff?)$", "", s, flags=re.I)
    return re.sub(r"[^a-z0-9]", "", s.lower())


def hint(text: str) -> str:
    for cat, rx in HINTS:
        if rx.search(text):
            return cat
    return "auto"


def wiki_articles(car: dict) -> list[tuple[str, str]]:
    """The car's Japanese Wikipedia article (robust to katakana) and its English counterpart."""
    out = []
    for q in [car.get("name_ja"), f"{car.get('make', '')} {car.get('model', '')}"]:
        if not q or not q.strip():
            continue
        hits = api("ja.wikipedia.org", {"action": "query", "list": "search", "srsearch": q, "srlimit": 1}).get("query", {}).get("search", [])
        if hits:
            ja = hits[0]["title"]
            out.append(("ja", ja))
            pages = api("ja.wikipedia.org", {"action": "query", "titles": ja, "prop": "langlinks", "lllang": "en", "redirects": 1})["query"]["pages"]
            ll = next(iter(pages.values())).get("langlinks") or []
            if ll:
                out.append(("en", ll[0]["*"]))
            break
    return out


def commons_category(lang: str, article: str) -> str | None:
    pages = api(f"{lang}.wikipedia.org", {"action": "query", "titles": article, "prop": "pageprops", "redirects": 1})["query"]["pages"]
    qid = next(iter(pages.values())).get("pageprops", {}).get("wikibase_item")
    if not qid:
        return None
    d = get_json(f"https://www.wikidata.org/w/api.php?action=wbgetclaims&entity={qid}&property=P373&format=json")
    claims = d.get("claims", {}).get("P373") or []
    return claims[0]["mainsnak"]["datavalue"]["value"] if claims else None


def commons_tree(cat: str, max_files=500, max_cats=80, depth=3) -> dict[str, str]:
    """File title -> category path, walking subcategories ('Interior of ...', 'Engines', '(AH40)' ...)."""
    files: dict[str, str] = {}
    seen, todo = set(), [(cat, 0, cat)]
    while todo and len(files) < max_files and len(seen) < max_cats:
        c, d, path = todo.pop(0)
        if c in seen:
            continue
        seen.add(c)
        cont: dict = {}
        while True:
            r = commons({"action": "query", "list": "categorymembers", "cmtitle": "Category:" + c, "cmtype": "file|subcat",
                         "cmlimit": 500, **cont})
            for m in r.get("query", {}).get("categorymembers", []):
                if m["ns"] == 14 and d < depth:
                    sub = m["title"].split(":", 1)[1]
                    if not re.search(r"\b(by (country|city|year|colou?r)|in (art|advertising)|toys?|models?|scale)\b", sub, re.I):
                        todo.append((sub, d + 1, f"{path} / {sub}"))
                elif m["ns"] == 6 and re.search(r"\.(jpe?g|png)$", m["title"], re.I):
                    files.setdefault(m["title"], path)
            if "continue" in r and len(files) < max_files:
                cont = r["continue"]
            else:
                break
    log(f"commons category '{cat}': {len(files)} files in {len(seen)} categories")
    return files


def commons_info(titles: list[str]) -> list[dict]:
    out = []
    for i in range(0, len(titles), 50):
        d = commons({"action": "query", "titles": "|".join(titles[i:i + 50]), "prop": "imageinfo",
                     "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1920})
        for p in d.get("query", {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [{}])[0]
            m = ii.get("extmetadata", {})
            lic = (m.get("LicenseShortName") or {}).get("value", "").strip()
            if ii.get("mime") not in ("image/jpeg", "image/png") or not FREE.match(lic):
                continue
            artist = html.unescape(re.sub(r"<[^>]+>", "", (m.get("Artist") or {}).get("value", ""))).strip() or "unknown"
            desc = html.unescape(re.sub(r"<[^>]+>", "", (m.get("ImageDescription") or {}).get("value", "")))[:300]
            out.append({"key": norm(p["title"]), "title": p["title"].split(":", 1)[1], "text": desc,
                        "url": ii.get("thumburl") or ii.get("url"), "fallback": ii.get("url"), "w": ii.get("width") or 0,
                        "h": ii.get("height") or 0, "lic": lic, "artist": artist, "source": "Wikimedia Commons",
                        "landing": ii.get("descriptionurl", ""), "date": (m.get("DateTimeOriginal") or {}).get("value", "")[:10]})
    return out


def openverse(q: str, pages=1) -> list[dict]:
    out = []
    for page in range(1, pages + 1):
        url = "https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(
            {"q": q, "license": "by,by-sa,cc0,pdm", "page_size": 20, "page": page, "mature": "false"})
        try:
            d = get_json(url)
        except Exception as e:  # rate limits etc. never stop the build
            log(f"openverse '{q}' p{page}: {e}")
            break
        for r in d.get("results", []):
            if (r.get("filetype") or "jpg").lower() not in ("jpg", "jpeg", "png"):
                continue
            lic = {"cc0": "CC0", "pdm": "Public domain"}.get(r["license"], f"CC {r['license'].upper()} {r.get('license_version') or ''}".strip())
            src = r.get("url") or ""
            thumb = src
            m = re.match(r"(https://upload\.wikimedia\.org/wikipedia/commons)/(\w)/(\w\w)/(.+)$", src)
            if m and (r.get("width") or 0) > 1920:  # Commons originals can be 30 MB: use a standard 1920px rendition
                thumb = f"{m.group(1)}/thumb/{m.group(2)}/{m.group(3)}/{m.group(4)}/1920px-{m.group(4)}"
            tags = " ".join(t.get("name", "") for t in (r.get("tags") or [])[:30])
            source = (r.get("source") or "").lower()
            source = "Wikimedia Commons" if source.startswith("wikimedia") else source.title()
            out.append({"key": norm(r.get("title") or src.rsplit("/", 1)[-1]), "title": r.get("title") or "", "text": tags, "query": q,
                        "url": thumb, "fallback": src, "w": r.get("width") or 0, "h": r.get("height") or 0, "lic": lic,
                        "artist": html.unescape(r.get("creator") or "unknown"), "source": source,
                        "landing": r.get("foreign_landing_url") or "", "date": ""})
        if page >= (d.get("page_count") or 1):
            break
    return out


def gather(car: dict, target=60) -> list[dict]:
    """Up to `target` photos with a category hint each, best first (index 0 = hero)."""
    make, model = car.get("make", "").strip(), car.get("model", "").strip()
    cands: dict[str, dict] = {}

    def add(items, trusted=False):
        for it in items:
            if it["key"] and it["key"] not in cands:
                it["trusted"] = trusted
                cands[it["key"]] = it

    # 1) Wikipedia: articles -> correct names, Commons category, article photos
    arts = []
    try:
        arts = wiki_articles(car)
    except Exception as e:
        log(f"wikipedia: {e}")
    log(f"wikipedia: {arts}")
    ja = next((a for lang, a in arts if lang == "ja"), "")
    en = next((a for lang, a in arts if lang == "en"), "")
    if ja:
        car["name_ja"] = re.sub(r"\s*[（(].*[）)]$", "", ja).replace("・", " ")
    if en:
        model = re.sub(rf"^{re.escape(make)}\s+", "", re.sub(r"\s*\(.*\)$", "", en), flags=re.I) or model
        car["model"] = model
    model_key, make_key = norm(model), norm(make)

    # 2) Commons category tree (best source of interior / engine shots)
    try:
        cat = commons_category("en", en) if en else None
        cat = cat or (commons_category("ja", ja) if ja else None)
        if cat:
            tree = commons_tree(cat)
            info = commons_info(list(tree))
            for it in info:
                it["text"] += " " + tree.get("File:" + it["title"], "")
            add(info, trusted=True)
    except Exception as e:
        log(f"commons category: {e}")

    # 3) article photos + Commons search
    try:
        titles = []
        for lang, art in arts:
            d = api(f"{lang}.wikipedia.org", {"action": "query", "titles": art, "prop": "images", "imlimit": 500, "redirects": 1})
            for p in d["query"]["pages"].values():
                titles += ["File:" + im["title"].split(":", 1)[1] for im in p.get("images", []) if re.search(r"\.jpe?g$", im["title"], re.I)]
        for q in [f"{make} {model}", f"{model} interior", f"{model} engine"]:
            d = commons({"action": "query", "list": "search", "srsearch": f"{q} filetype:bitmap", "srnamespace": 6, "srlimit": 50})
            titles += [x["title"] for x in d.get("query", {}).get("search", [])]
        titles = [t for t in dict.fromkeys(titles) if norm(t) not in cands]
        add(commons_info(titles))
    except Exception as e:
        log(f"commons search: {e}")

    # 4) Openverse (Flickr and more), targeted at the cabin and engine bay too
    base = f"{make} {model}".strip()
    for q, pages in [(base, 4), (f"{base} interior", 2), (f"{model} interior", 1), (f"{base} dashboard", 1), (f"{base} seats", 1),
                     (f"{base} engine", 1), (f"{base} rear", 1), (f"{base} wheel", 1)]:
        add(openverse(q, pages))
        if len(cands) > 600:
            break

    # filter: relevance, quality, no toys/brochures
    good = []
    for it in cands.values():
        text = f"{it['title']} {it['text']}"
        named = bool(model_key) and (model_key in norm(it["title"]) or model_key in norm(it["text"]))
        if not (it["trusted"] or named):
            continue
        # Openverse results must also mention the make ("Kissa Tanto interior" is a cafe, not a Daihatsu)
        if not it["trusted"] and make_key and make_key not in norm(text):
            continue
        if EXCLUDE.search(text) or max(it["w"], it["h"]) < 1000 or not FREE.match(it["lic"]):
            continue
        it["named"] = model_key in norm(it["title"])
        # the photo's own title/tags/category decide; the search query only breaks ties
        it["cat"] = hint(it["title"])
        if it["cat"] == "auto":
            it["cat"] = hint(it["text"])
        if it["cat"] == "auto" and it.get("query"):
            q_cat = hint(it["query"])
            it["cat"] = q_cat if q_cat in ("interior", "engine") else "auto"
        years = [int(y) for y in re.findall(r"(?<!\d)((?:19|20)\d\d)(?!\d)", it["title"])]
        it["recent"] = not years or max(years) >= datetime.now().year - 4
        good.append(it)

    def rank(it):
        return (it["named"], it["recent"], it["w"] >= it["h"], min(it["w"], 4000), it["date"])

    good.sort(key=rank, reverse=True)
    picked: list[dict] = []
    used = {k: 0 for k in QUOTA}
    for it in good:  # category quotas first so every chapter has fitting photos
        if it["cat"] in QUOTA and used[it["cat"]] < QUOTA[it["cat"]]:
            picked.append(it)
            used[it["cat"]] += 1
    for it in good:
        if len(picked) >= target:
            break
        if it not in picked and it["cat"] not in QUOTA:
            picked.append(it)
    for it in good:  # still short: take any remaining
        if len(picked) >= target:
            break
        if it not in picked:
            picked.append(it)
    picked = picked[:target]
    hero = next((it for it in picked if it["cat"] in ("exterior", "auto") and it["named"] and it["recent"] and it["w"] > it["h"]), None)
    if hero:
        picked.remove(hero)
        picked.insert(0, hero)
    from collections import Counter
    log(f"photos: {len(good)} usable, picked {len(picked)} {dict(Counter(p['cat'] for p in picked))}")
    return picked


def credits(picked: list[dict]) -> tuple[list[str], list[str]]:
    """(short grouped lines for the YouTube description, full per-photo lines for credits.txt)."""
    groups: dict[tuple[str, str], dict] = {}
    for p in picked:
        g = groups.setdefault((p["artist"][:60], p["source"]), {})
        g[p["lic"]] = g.get(p["lic"], 0) + 1
    short = [f"{a} ({s}): " + ", ".join(f"{lic}{f' ×{n}' if n > 1 else ''}" for lic, n in g.items()) for (a, s), g in groups.items()]
    full = [f"{i:02d}.jpg  \"{p['title']}\" by {p['artist']}, {p['lic']}, {p['source']} {p['landing']}".strip()
            for i, p in enumerate(picked, 1)]
    return short, full


# --------------------------------------------------------------------------- render-time download
def fetch(job_dir: Path, max_side=2560):
    from PIL import Image

    jp = job_dir / "job.json"
    job = json.loads(jp.read_text(encoding="utf-8"))
    remote = {r["file"]: r for r in job.get("remoteImages") or []}
    if not remote:
        return
    keep = []
    for e in job["images"]:
        f = job_dir / e["file"]
        r = remote.get(e["file"])
        if not f.exists() and r:
            for url in [r.get("url"), r.get("fallback")]:
                if not url:
                    continue
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": UA})
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        tmp = f.with_suffix(".dl")
                        tmp.write_bytes(resp.read())
                    im = Image.open(tmp).convert("RGB")
                    im.thumbnail((max_side, max_side))
                    im.save(f, "JPEG", quality=90)
                    tmp.unlink()
                    break
                except Exception as ex:
                    log(f"  {e['file']}: {url[:80]} -> {ex}")
                    time.sleep(1)
        if f.exists():
            keep.append(e)
    log(f"photos fetched: {len(keep)}/{len(job['images'])}")
    if len(keep) < 4:
        raise SystemExit("too few photos could be downloaded")
    job["images"] = keep
    if job.get("heroIndex", 0) >= len(keep):
        job["heroIndex"] = 0
    jp.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1] == "fetch":
        fetch(Path(sys.argv[2]))
