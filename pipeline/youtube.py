"""Minimal YouTube Data API v3 client (stdlib only) for scheduled uploads to "my channel".

Credentials come from GitHub Actions secrets (set by the "Connect my channel" button on docs/index.html):
YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.

    python pipeline/youtube.py upload <job dir> <output dir>   # upload the rendered video, update channel/queue.json

Videos are uploaded as private with `publishAt` (at least 30 minutes from now), so YouTube publishes them then.
Note: uploads from an unverified Google Cloud project stay private until the project passes YouTube's audit.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://www.googleapis.com/youtube/v3"
MIN_LEAD = timedelta(minutes=30)  # never schedule closer than this to "now"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3"


def configured() -> bool:
    return all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))


_token: dict = {}


def token() -> str:
    if _token.get("exp", 0) > time.time() + 60:
        return _token["access"]
    body = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token",
    }).encode()
    with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=body), timeout=60) as r:
        d = json.loads(r.read())
    _token.update(access=d["access_token"], exp=time.time() + int(d.get("expires_in", 3600)))
    return _token["access"]


def call(method: str, url: str, body: dict | None = None, data: bytes | None = None, headers: dict | None = None):
    h = {"Authorization": f"Bearer {token()}", **(headers or {})}
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json; charset=UTF-8"
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}, r.headers
    except urllib.error.HTTPError as e:
        raise SystemExit(f"YouTube API {method} {url.split('?')[0]} -> {e.code}: {e.read().decode(errors='replace')[:800]}")


def iso(dt: str | None) -> str:
    """The publish time to give YouTube (RFC 3339 UTC): the wanted time, but at least MIN_LEAD from now."""
    floor = datetime.now(timezone.utc) + MIN_LEAD
    t = None
    if dt:
        t = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
    if t is None or t < floor:
        t = floor
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def status_body(publish_at: str | None) -> dict:
    s = {"selfDeclaredMadeForKids": False, "embeddable": True, "license": "youtube"}
    if publish_at:
        s.update(privacyStatus="private", publishAt=publish_at)
    else:
        s.update(privacyStatus="public")
    return s


def upload_video(path: Path, meta: dict, publish_at: str | None) -> str:
    size = path.stat().st_size
    body = {"snippet": meta, "status": status_body(publish_at)}
    _, hdr = call("POST", f"{UPLOAD}/videos?uploadType=resumable&part=snippet,status", body=body,
                  headers={"X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)})
    loc = hdr["Location"]
    chunk = 64 * 1024 * 1024
    with path.open("rb") as f:
        pos = 0
        while pos < size:
            part = f.read(chunk)
            end = pos + len(part) - 1
            for attempt in range(5):
                req = urllib.request.Request(loc, data=part, method="PUT", headers={
                    "Authorization": f"Bearer {token()}", "Content-Length": str(len(part)),
                    "Content-Range": f"bytes {pos}-{end}/{size}"})
                try:
                    with urllib.request.urlopen(req, timeout=900) as r:
                        res = json.loads(r.read())
                        print(f"uploaded {size / 1e6:.0f} MB -> https://youtu.be/{res['id']}")
                        return res["id"]
                except urllib.error.HTTPError as e:
                    if e.code == 308:  # chunk accepted, continue
                        break
                    if e.code >= 500 and attempt < 4:
                        time.sleep(5 * (attempt + 1))
                        continue
                    raise SystemExit(f"upload failed {e.code}: {e.read().decode(errors='replace')[:500]}")
                except (urllib.error.URLError, TimeoutError):
                    if attempt == 4:
                        raise
                    time.sleep(5 * (attempt + 1))
            pos = end + 1
            print(f"  {pos / size * 100:.0f}%", flush=True)
    raise SystemExit("upload did not complete")


def set_thumbnail(video_id: str, jpg: Path):
    try:
        call("POST", f"{UPLOAD}/thumbnails/set?videoId={video_id}", data=jpg.read_bytes(), headers={"Content-Type": "image/jpeg"})
        print("thumbnail set")
    except SystemExit as e:  # custom thumbnails need a verified channel; the video itself is fine
        print(f"thumbnail not set: {e}")


def reschedule(video_id: str, publish_at: str | None) -> str:
    """Schedule an existing private video; returns the time actually set."""
    t = iso(publish_at)
    call("PUT", f"{API}/videos?part=status", body={"id": video_id, "status": status_body(t)})
    print(f"rescheduled {video_id} -> {t}")
    return t


def my_videos(limit: int = 500) -> list[dict]:
    """Every video on my channel (private and scheduled ones too, since we are the owner)."""
    d, _ = call("GET", f"{API}/channels?part=contentDetails&mine=true")
    ch = d.get("items") or []
    if not ch:
        return []
    pl = ch[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, page = [], ""
    while len(ids) < limit:
        d, _ = call("GET", f"{API}/playlistItems?part=contentDetails&maxResults=50&playlistId={pl}" + (f"&pageToken={page}" if page else ""))
        ids += [x["contentDetails"]["videoId"] for x in d.get("items", [])]
        page = d.get("nextPageToken")
        if not page:
            break
    out = []
    for i in range(0, len(ids), 50):
        d, _ = call("GET", f"{API}/videos?part=snippet,status&id={','.join(ids[i:i + 50])}")
        for v in d.get("items", []):
            out.append({"id": v["id"], "title": v["snippet"].get("title", ""), "privacy": v["status"].get("privacyStatus"),
                        "publishAt": v["status"].get("publishAt"), "publishedAt": v["snippet"].get("publishedAt")})
    return out


def my_channel() -> dict:
    d, _ = call("GET", f"{API}/channels?part=snippet&mine=true")
    it = (d.get("items") or [{}])[0]
    return {"id": it.get("id"), "name": it.get("snippet", {}).get("title")}


# --------------------------------------------------------------------------- CLI
def update_queue(item_id: str, **fields):
    p = Path("channel/queue.json")
    if not p.exists():
        return
    q = json.loads(p.read_text(encoding="utf-8"))
    for it in q.get("items", []):
        if it["id"] == item_id:
            it.update(fields)
    p.write_text(json.dumps(q, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cmd_upload(job_dir: Path, out: Path, qid: str | None = None):
    job = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    yt = job.get("youtube") or {}
    qid = qid or yt.get("queueId")
    release = os.environ.get("RELEASE_URL", "")
    if not configured():
        print("My channel isn't connected (no YT_* secrets): video stays in Releases only.")
        if qid:
            update_queue(qid, status="made", release=release, madeAt=datetime.now(timezone.utc).isoformat())
        return
    # the queue is the source of truth: the owner may have changed the time on the page after the job was built
    q = json.loads(Path("channel/queue.json").read_text(encoding="utf-8")) if Path("channel/queue.json").exists() else {}
    item = next((it for it in q.get("items", []) if it["id"] == qid), {}) if qid else {}
    try:
        mp4 = next(out.glob("*-youtube.mp4"), None) or max(
            (f for f in out.glob("*.mp4") if "short" not in f.name.lower()), key=lambda f: f.stat().st_size, default=None)
        if not mp4:
            raise SystemExit(f"no rendered .mp4 in {out}")
        desc = (out / "description.txt").read_text(encoding="utf-8") if (out / "description.txt").exists() else ""
        meta = {
            "title": (item.get("myTitle") or yt.get("title") or job.get("descriptionTitle") or job.get("title", ""))[:100],
            "description": desc[:4900],
            "tags": [t.lstrip("#") for t in (yt.get("tags") or job.get("hashtags") or [])][:30],
            "categoryId": str(yt.get("categoryId", "2")),  # Autos & Vehicles
        }
        lang = job.get("language")
        if lang:
            meta.update(defaultLanguage=lang, defaultAudioLanguage=lang)
        publish_at = iso(item.get("publishAt") or yt.get("publishAt"))  # >= 30 min from now
        vid = upload_video(mp4, meta, publish_at)
    except BaseException as e:  # show why on the page; the sync retries after an hour
        if qid:
            update_queue(qid, note=f"YouTube upload failed: {e}"[:300], uploadTriedAt=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        raise
    thumb = next(out.glob("*-thumbnail.jpg"), None)
    if thumb:
        set_thumbnail(vid, thumb)
    if qid:
        fields = dict(status="scheduled", myVideoId=vid, publishAt=publish_at, uploadedPublishAt=publish_at,
                      madeAt=item.get("madeAt") or datetime.now(timezone.utc).isoformat(), note="")
        if release:
            fields["release"] = release
        update_queue(qid, **fields)


if __name__ == "__main__":
    if sys.argv[1] == "upload":  # upload <job dir> <output dir> [queue id]
        cmd_upload(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4] if len(sys.argv) > 4 else None)
    elif sys.argv[1] == "note":  # note <queue id> <text>
        update_queue(sys.argv[2], note=sys.argv[3], uploadTriedAt=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    elif sys.argv[1] == "whoami":
        print(my_channel())
