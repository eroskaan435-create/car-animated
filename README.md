# 🏎️ Car Promo Video Studio

Upload car photos and get a fast-paced, beat-synced promo video with an AI voice-over.
All rendering runs on **GitHub Actions**, so your own computer does no heavy work.

```
docs/index.html (upload page)
      │  commits photos + job.json via GitHub API
      ▼
jobs/<name>/           ──►  GitHub Actions  (.github/workflows/render.yml)
                              1. pipeline/prep.py  (Python + AI)
                                 • background removal (rembg / BiRefNet)
                                 • depth maps for 3D parallax (Depth-Anything-V2)
                                 • vehicle-type detection (CLIP) → style preset
                                 • voice-over (Kokoro TTS, fallback edge-tts)
                                 • beat-locked timeline + synthesized music & SFX
                              2. video/ (Remotion + Three.js) → MP4 via ffmpeg
                              3. MP4 + poster published as a GitHub Release
```

## Effects
Whip pans with motion blur, punch-in zooms on the beat, Ken Burns push/pull, 3D depth parallax (Three.js shader),
title text behind the car, light sweeps across the paint, flash cuts, RGB glitch, camera shake on impacts,
speed lines, sparks/bokeh/dust particles, counting spec cards, a price slam with a shockwave, and an animated CTA.

Each **vehicle style** has its own look, fonts, edit pace and music genre:

| Style | Music | Pace | Look |
|---|---|---|---|
| Sports | trap, 129 BPM | 3-beat shots | red/orange, sparks, glitch |
| Luxury | ambient, 90 BPM | slow glides | gold, Cinzel serif, bokeh |
| SUV | rock, 112 BPM | heavy zooms | amber, dust |
| Truck | rock, 120 BPM | hard shake | yellow/black, sparks |
| Electric | synthwave, 120 BPM | 3-beat shots | cyan neon, glitch |
| Sedan | EDM, 112 BPM | balanced | blue, bokeh |

The music is generated fresh for every video, so it's royalty-free, and every cut, whoosh and impact lands exactly on the beat.

## One-time setup (about 5 minutes)

1. **Create a public repo** on GitHub (e.g. `car-animated`). Public repos get unlimited free Actions minutes.
2. **Push this folder:**
   ```bash
   git init -b main
   git add .
   git commit -m "Car promo video studio"
   git remote add origin https://github.com/<you>/car-animated.git
   git push -u origin main
   ```
3. **Turn on the upload page:** repo → *Settings → Pages → Deploy from a branch → `main` / `/docs`* → Save.
   It goes live at `https://<you>.github.io/car-animated/` after about 1 minute.
4. **Create a token** at <https://github.com/settings/personal-access-tokens/new> (fine-grained):
   - Repository access: *Only select repositories →* your repo
   - Permissions: **Contents: Read and write**, **Actions: Read-only**
5. Open the page, expand **GitHub connection**, enter owner, repo and token, then click **Test connection**.
   The token is kept only in your browser.

## Making a video
1. Drop in 3–10 photos. The first one is the hero shot; drag to reorder and add optional captions.
2. Fill in the title, price, specs, dealer and CTA. Choose a style or leave it on *Auto-detect*.
3. Check the voice-over lines (they're auto-written, so edit them freely), then pick a voice and formats.
4. Click **CREATE VIDEO**. The page follows the render and shows the video when it's done (about 8–20 min).
   Every video is also listed under the repo's **Releases**.

**Without the page:** create `jobs/<any-name>/` with the photos and a `job.json`
(use *Download job.json* on the page, or copy one from `scripts/make_test_job.py`), then push.
You can also re-run a job from *Actions → Render car video → Run workflow*.

## 🎬 YouTube long videos (13–15 min, 16:9)
Switch the page to the **YouTube long video** tab.

1. Add **30–60 photos** (exterior, interior, engine, details). The AI sorts them by type, or you can set it per photo.
2. Fill in the facts (engine, gearbox, features, pros/cons, rivals…). The script writer only uses these facts.
3. Click **Generate script (free AI)**. GitHub runs **Qwen 2.5 7B** through Ollama (free, ~10–25 min) and writes
   about 2,100 words across 11 chapters into `jobs/<id>/script.md`. It appears in the page's script box.
4. **Read and fix the script.** The meter shows words and estimated minutes. You can also paste your own script
   (each `## Heading` starts a chapter).
5. Click **Render YouTube video**. GitHub Actions then:
   - voices every sentence (Kokoro TTS) and fits the video into **13:00–15:00**. If it's short, it adds pauses and
     music galleries; if it's long, it speeds the voice up slightly (max 1.15×). A script that's far too long is rejected with a message.
   - builds a cold open, then chapter title cards, then narrated photo shots with crossfades, spec callouts, a chapter progress bar,
     burned-in captions, a pros/cons board and a YouTube end screen (with space for end-screen elements)
   - renders the video on **12 runners in parallel**, joins the slices and adds the soundtrack
   - publishes `…-youtube.mp4`, `…-thumbnail.jpg` (1280×720), `captions.srt`, `chapters.txt` and `description.txt`
     (chapter timestamps are already inside), plus an optional 9:16 Short

### Fast, beat-synced long videos (`"pace": "fast"`)
Add `"pace": "fast"` to a long job's `job.json` for an energetic edit instead of a calm review
(see `jobs/suzuki-mehran/`):
- The length follows the narration, with no 13–15 min padding, so any script of 60+ words works.
- The music keeps its full groove the whole way through and ducks under the voice.
- Shots cut every 2–4 beats with the preset's whip/flash/zoom transitions. Chapter cards are one bar long
  and every chapter starts on a bar line.
- `"shotScale": 2` doubles every shot length if the cuts feel too fast.
- `"descriptionTitle"` and `"descriptionIntro"` replace the first two lines of `description.txt`
  (default: "<title> — Full Review" and the first sentences of the script). These two fields work in any long job.
- `"ttsOverrides"` lets a line be spoken differently from how it's captioned. For example, Roman Urdu on
  screen can be voiced from Urdu script by `ur-PK-AsadNeural` (any edge-tts voice works).

### Japanese (and other non-English) long videos
See `jobs/honda-n-box/`:
- `"language": "ja"`: the script is split into sentences on 。！？ and captions break after 、. Chapter titles can be Japanese
  (まとめ/結論 gets the pros/cons board), and the description headings are in Japanese.
- `"voice": {"edgeVoice": "ja-JP-KeitaNeural"}` narrates the whole script with any edge-tts voice. If that voice fails,
  the job stops instead of falling back to an English voice.
- `"hashtags"` and `"credits"` (photo attributions, e.g. for CC BY-SA images) are added to `description.txt`.
- The render runners install `fonts-noto-cjk` so Japanese text renders.

### Sizzling frame + kawaii car stickers
Add `"decor": {"frame": true, "stickers": true, "stickerEvery": 60, "maxStickers": 3}` to a long job
(see `jobs/honda-n-box-preview/`):
- `frame`: the picture is inset inside an animated frame with an asphalt band, a moving road line, checkered-flag corners,
  a flickering neon edge, two headlight "comets" racing around it, sparks and electric crackles.
- `stickers`: a cute car sticker pops in (with a pop sound) every `stickerEvery` seconds and stays on screen. At most
  `maxStickers` show at once, and the end screen is kept clear. There are 8 original SVG designs in `video/src/fx/decor.tsx`,
  alternating modern and classic: kei box car, retro round car, sports car, '50s fin convertible, EV, camper van, kei truck, taxi.
- The music is synthesized fresh for every video, so it's always royalty-free.

Expect about 30–60 minutes per long video. The first run takes longer because it downloads the models (~6 GB, cached after that).

## Tips for best results
- Use landscape photos where the whole car is visible on a clean background. These give the best cutouts for
  the "text behind car" and studio spec shots.
- Mix in close-ups (wheels, lights, interior) for the punch-zoom shots.
- Keep the title short (≤ 25 characters) so it renders large.
- To override a bad cutout, add `<photo-name>.mask.png` (white = car) next to the photo.

## Local preview (optional, needs Node 20+ and Python 3.11)
```bash
python scripts/make_test_job.py jobs/test-sports sports
python pipeline/prep.py jobs/test-sports --out video/public/job --no-ai   # --no-ai skips the models
cd video && npm ci && npm run studio      # live preview in the browser
```

## Notes
- **Public repo = public files.** Photos in `jobs/` and the rendered videos can be seen by anyone.
- Remotion is free for individuals and companies with up to 3 people. Larger companies need a
  [company license](https://www.remotion.dev/license).
- The first workflow run downloads the AI models (~1.5 GB, plus ~4.7 GB for the script writer) and caches them.
- The AI script can still get things wrong. Always read it before rendering.
