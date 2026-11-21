"""Generate a synthetic test job (drawn cars + masks) for pipeline testing.

    python scripts/make_test_job.py jobs/test-sports sports
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

out = Path(sys.argv[1] if len(sys.argv) > 1 else "jobs/test-sports")
vtype = sys.argv[2] if len(sys.argv) > 2 else "sports"
out.mkdir(parents=True, exist_ok=True)

SCENES = [
    ((20, 24, 40), (90, 60, 80), (200, 20, 20)),
    ((10, 30, 50), (40, 80, 110), (240, 240, 245)),
    ((40, 20, 10), (150, 90, 50), (20, 20, 25)),
    ((5, 5, 15), (30, 30, 60), (255, 160, 0)),
    ((30, 40, 50), (120, 130, 140), (0, 120, 255)),
]


def car(draw: ImageDraw.ImageDraw, W, H, col, s=1.0, ox=0.0):
    m = isinstance(col, int)
    C = (lambda c: 255) if m else (lambda c: c)
    cx, base = W * (0.5 + ox), H * 0.72
    L = W * 0.7 * s
    x0, x1 = cx - L / 2, cx + L / 2
    hgt = L * 0.17
    body = [(x0, base - hgt * 0.35), (x0 + L * 0.04, base - hgt * 0.9), (x0 + L * 0.3, base - hgt * 1.05),
            (x0 + L * 0.42, base - hgt * 1.75), (x0 + L * 0.68, base - hgt * 1.78), (x0 + L * 0.82, base - hgt * 1.1),
            (x1 - L * 0.02, base - hgt * 0.95), (x1, base - hgt * 0.4), (x1 - L * 0.02, base), (x0 + L * 0.02, base)]
    draw.polygon(body, fill=col)
    glass = [(x0 + L * 0.45, base - hgt * 1.62), (x0 + L * 0.66, base - hgt * 1.65), (x0 + L * 0.77, base - hgt * 1.12),
             (x0 + L * 0.36, base - hgt * 1.1)]
    draw.polygon(glass, fill=C((25, 30, 40)))
    draw.line([(x0 + L * 0.05, base - hgt * 0.8), (x1 - L * 0.05, base - hgt * 0.85)], fill=C((255, 255, 255)), width=int(4 * s * W / 1000))
    for wx in (x0 + L * 0.2, x0 + L * 0.8):
        r = hgt * 0.62
        draw.ellipse([wx - r, base - r, wx + r, base + r], fill=C((15, 15, 15)))
        draw.ellipse([wx - r * 0.6, base - r * 0.6, wx + r * 0.6, base + r * 0.6], fill=C((170, 170, 180)))
        draw.ellipse([wx - r * 0.2, base - r * 0.2, wx + r * 0.2, base + r * 0.2], fill=C((60, 60, 60)))
    draw.ellipse([x1 - L * 0.06, base - hgt * 0.9, x1 - L * 0.01, base - hgt * 0.65], fill=C((255, 250, 220)))


images = []
for i, (sky, ground, col) in enumerate(SCENES):
    W, H = (2400, 1600) if i != 3 else (1600, 2000)
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        c = tuple(int(sky[k] * (1 - t) + ground[k] * t) for k in range(3)) if t < 0.62 else tuple(int(ground[k] * 0.6) for k in range(3))
        d.line([(0, y), (W, y)], fill=c)
    for k in range(14):  # background "buildings"
        bx = (k * 197) % W
        d.rectangle([bx, H * 0.35 + (k * 53) % 200, bx + 120, H * 0.62], fill=tuple(min(255, v + 25) for v in sky))
    im = im.filter(ImageFilter.GaussianBlur(3))
    d = ImageDraw.Draw(im)
    s, ox = (1.0, 0.0) if i != 2 else (1.25, 0.1)
    car(d, W, H, col, s, ox)
    mask = Image.new("L", (W, H), 0)
    car(ImageDraw.Draw(mask), W, H, 255, s, ox)
    im.save(out / f"{i + 1:02d}.jpg", quality=90)
    mask.save(out / f"{i + 1:02d}.mask.png")
    images.append({"file": f"{i + 1:02d}.jpg", "caption": ["", "LED matrix headlights", "Carbon aero kit", "", "21\" forged wheels"][i]})

job = {
    "version": 1,
    "title": "2025 Velocita GT Turbo S",
    "vehicleType": vtype,
    "price": "$189,900",
    "priceLabel": "Starting at",
    "specs": [{"label": "Horsepower", "value": "640 HP"}, {"label": "0-60 mph", "value": "2.6 s"},
              {"label": "Top speed", "value": "205 mph"}, {"label": "Torque", "value": "590 lb-ft"}],
    "dealer": "Prime Motors",
    "contact": "+1 555 0100  ·  primemotors.com",
    "cta": "Book a test drive",
    "formats": ["9:16"],
    "voice": {"enabled": True, "voice": "am_michael"},
    "images": images,
    "heroIndex": 0,
}
(out / "job.json").write_text(json.dumps(job, indent=2), encoding="utf-8")
print("wrote", out)
