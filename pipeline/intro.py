"""Put an intro clip in front of a finished long video and shift captions + chapter times to match.

    python pipeline/intro.py <video.mp4> <intro clip> <dir with captions.srt / chapters.txt / description.txt>

The intro is scaled/padded to the video's size and frame rate (any format ffmpeg reads; a clip without
sound gets silence). Chapter 1 stays at 0:00 so the YouTube chapter list stays valid.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


def probe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration",
                          "-of", "json", str(path)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def shift_srt(text: str, d: float) -> str:
    def f(m):
        h, mi, s, ms = (int(x) for x in m.groups())
        t = max(0, round((h * 3600 + mi * 60 + s) * 1000 + ms + d * 1000))
        h, t = divmod(t, 3600000)
        mi, t = divmod(t, 60000)
        s, ms = divmod(t, 1000)
        return f"{h:02d}:{mi:02d}:{s:02d},{ms:03d}"
    return re.sub(r"(\d\d):(\d\d):(\d\d),(\d\d\d)", f, text)


def shift_chapters(text: str, d: float) -> str:
    """Shift every 'm:ss Title' / 'h:mm:ss Title' line except the one at 0:00."""
    def f(m):
        parts = [int(x) for x in m.group(1).split(":")]
        sec = parts[-1] + 60 * parts[-2] + (3600 * parts[0] if len(parts) == 3 else 0)
        if sec == 0:
            return m.group(0)
        sec = int(sec + d)
        stamp = f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"
        return stamp + m.group(2)
    return re.sub(r"(?m)^(\d+:\d\d(?::\d\d)?)( .+)$", f, text)


def main():
    video, intro, extras = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    v = probe(video)
    vs = next(s for s in v["streams"] if s["codec_type"] == "video")
    W, H = vs["width"], vs["height"]
    fps = vs["r_frame_rate"]
    i = probe(intro)
    has_audio = any(s["codec_type"] == "audio" for s in i["streams"])
    d = float(i["format"]["duration"])
    print(f"intro {intro.name}: {d:.2f}s, audio={has_audio}")

    tmp = video.with_suffix(".with-intro.mp4")
    norm = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={fps},format=yuv420p"
    inputs = ["-i", str(intro), "-i", str(video)]
    if not has_audio:
        inputs += ["-f", "lavfi", "-t", f"{d:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    ia = "[0:a]" if has_audio else "[2:a]"
    fc = (f"[0:v]{norm}[iv];{ia}aresample=48000,aformat=channel_layouts=stereo[ia];"
          f"[1:v]setsar=1,format=yuv420p[mv];[1:a]aresample=48000,aformat=channel_layouts=stereo[ma];"
          f"[iv][ia][mv][ma]concat=n=2:v=1:a=1[v][a]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-c:a", "aac", "-b:a", "256k",
                    "-movflags", "+faststart", str(tmp)], check=True)
    tmp.replace(video)

    for name, fn in (("captions.srt", shift_srt), ("chapters.txt", shift_chapters), ("description.txt", shift_chapters)):
        p = extras / name
        if p.exists():
            p.write_text(fn(p.read_text(encoding="utf-8"), d), encoding="utf-8")
    print("intro added; captions and chapters shifted by", round(d, 2), "s")


if __name__ == "__main__":
    main()
