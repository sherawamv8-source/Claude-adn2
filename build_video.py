#!/usr/bin/env python3
"""WC26 promo video renderer.

Composites the 93s vertical (1080x1920 @30fps) promo described in SCRIPT.md:
PIL-generated frames piped straight into ffmpeg/libx264. Player stills and
flags come from assets/, background-removed cutouts from assets/cutouts/,
and real match footage is sampled from assets/clips/ (frame sequences are
pre-extracted to /tmp/cf by build_all.sh).
"""
import math
import os
import random
import subprocess
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
DUR = 93.0
N_FRAMES = int(DUR * FPS)
ROOT = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(ROOT, "assets")
CUT = os.path.join(A, "cutouts")
CF = "/tmp/cf"

GOLD = (255, 200, 40)
NEON_GREEN = (57, 255, 120)
NEON_BLUE = (80, 180, 255)
RED = (255, 60, 50)
SILVER = (228, 230, 238)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def lerp(a, b, t):
    return a + (b - a) * t


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in(t):
    t = clamp(t)
    return t ** 3


def ease_io(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- fonts/text
@lru_cache(maxsize=None)
def font(size, name="anton"):
    path = {
        "anton": "fonts/Anton-Regular.ttf",
        "arch": "fonts/ArchivoBlack-Regular.ttf",
        "osw": "fonts/Oswald.ttf",
    }[name]
    return ImageFont.truetype(os.path.join(ROOT, path), size)


@lru_cache(maxsize=None)
def _text(text, size, fill, stroke, stroke_fill, glow, glow_r, fname, align, spacing):
    f = font(size, fname)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    bbox = probe.multiline_textbbox((0, 0), text, font=f, stroke_width=stroke,
                                    spacing=spacing, align=align)
    pad = glow_r * 2 + 12
    w = int(bbox[2] - bbox[0] + pad * 2)
    h = int(bbox[3] - bbox[1] + pad * 2)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    org = (pad - bbox[0], pad - bbox[1])
    if glow:
        g = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(g).multiline_text(
            org, text, font=f, fill=glow, spacing=spacing, align=align,
            stroke_width=max(2, stroke // 2), stroke_fill=glow)
        g = g.filter(ImageFilter.GaussianBlur(glow_r))
        img.alpha_composite(g)
        img.alpha_composite(g)
    ImageDraw.Draw(img).multiline_text(
        org, text, font=f, fill=fill, spacing=spacing, align=align,
        stroke_width=stroke, stroke_fill=stroke_fill)
    return img


def T(text, size, fill=(255, 255, 255), stroke=None, stroke_fill=(8, 8, 12),
      glow=None, glow_r=26, fname="anton", align="center", spacing=8):
    if stroke is None:
        stroke = max(3, size // 14)
    return _text(text, size, fill, stroke, stroke_fill, glow, glow_r,
                 fname, align, spacing)


def paste(base, img, cx, cy, scale=1.0, alpha=1.0, angle=0.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    im = img
    if angle:
        im = im.rotate(angle, expand=True, resample=Image.BILINEAR)
    if abs(scale - 1.0) > 1e-3:
        im = im.resize((max(1, int(im.width * scale)),
                        max(1, int(im.height * scale))), Image.BILINEAR)
    if alpha < 1.0:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    base.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def cover(img, w=W, h=H, cx=0.5, cy=0.5, zoom=1.0):
    iw, ih = img.size
    s = max(w / iw, h / ih) * zoom
    cw, ch = w / s, h / s
    x0 = clamp(cx * iw - cw / 2, 0, iw - cw)
    y0 = clamp(cy * ih - ch / 2, 0, ih - ch)
    return img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize(
        (w, h), Image.BILINEAR)


def shake(fi, amp):
    if amp <= 0:
        return 0, 0
    r = random.Random(fi * 977 + 13)
    return int(r.uniform(-amp, amp)), int(r.uniform(-amp, amp))


def fshake(img, dx, dy):
    if not dx and not dy:
        return img
    c = Image.new("RGBA", (W, H), (5, 5, 8, 255))
    c.alpha_composite(img, (dx, dy))
    return c


def glitch(img, amt, seed):
    if amt <= 0:
        return img
    r = random.Random(seed)
    arr = np.asarray(img.convert("RGB")).copy()
    for _ in range(int(3 + amt * 12)):
        y = r.randint(0, H - 90)
        hgt = r.randint(10, 80)
        sh = int(r.uniform(-1, 1) * amt * 130)
        arr[y:y + hgt] = np.roll(arr[y:y + hgt], sh, axis=1)
    ch = int(amt * 14)
    if ch:
        arr[..., 0] = np.roll(arr[..., 0], ch, axis=1)
        arr[..., 2] = np.roll(arr[..., 2], -ch, axis=1)
    return Image.fromarray(arr).convert("RGBA")


# ---------------------------------------------------------------- materials
def make_vignette(strength=160):
    s = 4
    y, x = np.mgrid[0:H // s, 0:W // s]
    d = np.sqrt(((x - W / s / 2) / (W / s / 2)) ** 2 +
                ((y - H / s / 2) / (H / s / 2)) ** 2)
    a = np.clip((d - 0.55) / 0.85, 0, 1) ** 1.5 * strength
    v = np.zeros((H // s, W // s, 4), np.uint8)
    v[..., 3] = a.astype(np.uint8)
    return Image.fromarray(v).resize((W, H), Image.BILINEAR)


def make_grad(top, bottom):
    g = Image.new("RGBA", (1, 256))
    for i in range(256):
        t = i / 255
        g.putpixel((0, i), tuple(int(lerp(top[j], bottom[j], t)) for j in range(4)))
    return g.resize((W, H), Image.BILINEAR)


def radial_bg(inner=(40, 40, 50), outer=(8, 8, 12)):
    s = 4
    y, x = np.mgrid[0:H // s, 0:W // s]
    d = np.clip(np.sqrt(((x - W / s / 2)) ** 2 + ((y - H / s / 2)) ** 2) /
                (H / s / 1.6), 0, 1)
    arr = np.zeros((H // s, W // s, 3), np.uint8)
    for c in range(3):
        arr[..., c] = (inner[c] + (outer[c] - inner[c]) * d).astype(np.uint8)
    return Image.fromarray(arr).resize((W, H), Image.BILINEAR).convert("RGBA")


def make_grain():
    out = []
    rs = np.random.RandomState(3)
    for _ in range(6):
        n = rs.randint(0, 255, (H // 3, W // 3), np.uint8)
        g = np.zeros((H // 3, W // 3, 4), np.uint8)
        g[..., 0] = g[..., 1] = g[..., 2] = n
        g[..., 3] = 14
        out.append(Image.fromarray(g).resize((W, H), Image.NEAREST))
    return out


# flags ----------------------------------------------------------------
def _flag(draw_fn, w=900, h=600):
    img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    draw_fn(ImageDraw.Draw(img), w, h, img)
    return img


def flag_brazil():
    def d(dr, w, h, img):
        dr.rectangle([0, 0, w, h], fill=(0, 151, 57))
        dr.polygon([(w / 2, 60), (w - 90, h / 2), (w / 2, h - 60), (90, h / 2)],
                   fill=(254, 221, 0))
        dr.ellipse([w / 2 - 130, h / 2 - 130, w / 2 + 130, h / 2 + 130],
                   fill=(0, 39, 118))
    return _flag(d)


def flag_germany():
    def d(dr, w, h, img):
        dr.rectangle([0, 0, w, h / 3], fill=(0, 0, 0))
        dr.rectangle([0, h / 3, w, 2 * h / 3], fill=(221, 0, 0))
        dr.rectangle([0, 2 * h / 3, w, h], fill=(255, 206, 0))
    return _flag(d)


def flag_argentina():
    def d(dr, w, h, img):
        dr.rectangle([0, 0, w, h / 3], fill=(108, 172, 228))
        dr.rectangle([0, h / 3, w, 2 * h / 3], fill=(255, 255, 255))
        dr.rectangle([0, 2 * h / 3, w, h], fill=(108, 172, 228))
        dr.ellipse([w / 2 - 55, h / 2 - 55, w / 2 + 55, h / 2 + 55],
                   fill=(244, 180, 50))
    return _flag(d)


def flag_italy():
    def d(dr, w, h, img):
        dr.rectangle([0, 0, w / 3, h], fill=(0, 140, 69))
        dr.rectangle([w / 3, 0, 2 * w / 3, h], fill=(244, 245, 240))
        dr.rectangle([2 * w / 3, 0, w, h], fill=(205, 33, 42))
    return _flag(d)


def flag_france():
    def d(dr, w, h, img):
        dr.rectangle([0, 0, w / 3, h], fill=(0, 35, 149))
        dr.rectangle([w / 3, 0, 2 * w / 3, h], fill=(255, 255, 255))
        dr.rectangle([2 * w / 3, 0, w, h], fill=(237, 41, 57))
    return _flag(d)


def flag_uruguay():
    def d(dr, w, h, img):
        for i in range(9):
            dr.rectangle([0, i * h / 9, w, (i + 1) * h / 9],
                         fill=(255, 255, 255) if i % 2 == 0 else (0, 56, 168))
        dr.rectangle([0, 0, w * 0.4, h * 5 / 9], fill=(255, 255, 255))
        dr.ellipse([w * 0.2 - 70, h * 0.28 - 70, w * 0.2 + 70, h * 0.28 + 70],
                   fill=(252, 209, 22))
    return _flag(d)


def flag_england():
    def d(dr, w, h, img):
        dr.rectangle([0, 0, w, h], fill=(255, 255, 255))
        dr.rectangle([w / 2 - 60, 0, w / 2 + 60, h], fill=(206, 17, 38))
        dr.rectangle([0, h / 2 - 60, w, h / 2 + 60], fill=(206, 17, 38))
    return _flag(d)


def flag_spain():
    def d(dr, w, h, img):
        dr.rectangle([0, 0, w, h / 4], fill=(170, 21, 27))
        dr.rectangle([0, h / 4, w, 3 * h / 4], fill=(241, 191, 0))
        dr.rectangle([0, 3 * h / 4, w, h], fill=(170, 21, 27))
    return _flag(d)


def flag_ecuador():
    def d(dr, w, h, img):
        dr.rectangle([0, 0, w, h / 2], fill=(255, 221, 0))
        dr.rectangle([0, h / 2, w, 3 * h / 4], fill=(0, 56, 147))
        dr.rectangle([0, 3 * h / 4, w, h], fill=(237, 28, 36))
        dr.ellipse([w / 2 - 90, h / 2 - 90, w / 2 + 90, h / 2 + 90],
                   fill=(180, 140, 60))
        dr.ellipse([w / 2 - 70, h / 2 - 70, w / 2 + 70, h / 2 + 70],
                   fill=(70, 110, 160))
    return _flag(d)


def chip(flag_img, w=240, h=160):
    c = Image.new("RGBA", (w + 28, h + 28), (0, 0, 0, 0))
    d = ImageDraw.Draw(c)
    d.rounded_rectangle([8, 12, w + 16, h + 20], radius=26, fill=(0, 0, 0, 120))
    d.rounded_rectangle([10, 10, w + 18, h + 18], radius=24,
                        fill=(255, 255, 255, 255))
    fl = cover(flag_img.convert("RGBA"), w - 8, h - 8)
    mask = Image.new("L", fl.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, fl.width - 1, fl.height - 1],
                                           radius=18, fill=255)
    c.paste(fl, (14, 14), mask)
    return c


# ---------------------------------------------------------------- assets
print("loading assets...")
IMG = {n: Image.open(os.path.join(A, f)).convert("RGBA") for n, f in {
    "flag_jp": "flag_jp.png", "flag_ma": "flag_ma.png",
    "flag_co": "flag_co.png", "flag_nl": "flag_nl.png",
    "james_fist": "james_fist.jpg", "james_cel": "james_celebration.jpg",
    "bounou": "bounou.jpg", "ueda_japan": "ueda_japan.jpg",
    "kubo_sociedad_src": "kubo_sociedad.jpg", "hakimi_src": "hakimi.jpg",
    "vandijk_src": "vandijk.jpg", "trophy_src": "trophy.jpg",
    "mitoma_src": "mitoma_brighton.jpg",
}.items()}
CUTS = {n: Image.open(os.path.join(CUT, f)).convert("RGBA") for n, f in {
    "trophy": "trophy.png", "vandijk": "vandijk.png", "hakimi": "hakimi.png",
    "bounou": "bounou.png", "kubo": "kubo_sociedad.png", "ueda": "ueda.png",
    "endo": "endo_captain.png", "lorenzo": "lorenzo.png", "james": "james.png",
    "mitoma": "mitoma.png",
}.items()}
# trim glass reflection under the trophy base
tr = CUTS["trophy"]
CUTS["trophy"] = tr.crop((0, 0, tr.width, int(tr.height * 0.952)))

FLAG_EC = flag_ecuador()
CHAMPS = [("BRAZIL", flag_brazil()), ("GERMANY", flag_germany()),
          ("ITALY", flag_italy()), ("ARGENTINA", flag_argentina()),
          ("FRANCE", flag_france()), ("URUGUAY", flag_uruguay()),
          ("ENGLAND", flag_england()), ("SPAIN", flag_spain())]
CHIPS = {"ec": chip(FLAG_EC), "jp": chip(IMG["flag_jp"]),
         "ma": chip(IMG["flag_ma"]), "co": chip(IMG["flag_co"]),
         "nl": chip(IMG["flag_nl"])}

VIGNETTE = make_vignette()
GRAIN = make_grain()
DARK_RADIAL = radial_bg()
GRADES = {
    "ec": make_grad((0, 20, 70, 80), (255, 205, 0, 45)),
    "jp": make_grad((10, 30, 90, 70), (0, 8, 40, 90)),
    "ma": make_grad((120, 10, 25, 70), (0, 60, 35, 80)),
    "co": make_grad((255, 190, 0, 35), (20, 10, 0, 110)),
    "nl": make_grad((255, 110, 10, 50), (25, 25, 28, 110)),
}


class Clip:
    def __init__(self, name):
        d = os.path.join(CF, name)
        self.files = [os.path.join(d, f) for f in sorted(os.listdir(d))]
        self.n = len(self.files)

    def frame(self, tl, speed=1.0, pingpong=True):
        i = int(max(0.0, tl) * FPS * speed)
        if pingpong and self.n > 1:
            cyc = i % (2 * self.n - 2)
            i = cyc if cyc < self.n else 2 * self.n - 2 - cyc
        else:
            i = min(i, self.n - 1)
        return Image.open(self.files[i]).convert("RGBA")


CLIPS = {n: Clip(n) for n in ["ecuador_action", "pacho", "hincapie", "caicedo",
                              "japan_press", "ouahbi", "james_action",
                              "diaz_action"]}


def make_logo(target_h=900):
    img = Image.new("RGBA", (760, 1060), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([70, 50, 430, 410], radius=72, fill=(14, 14, 17, 255),
                        outline=(212, 175, 55, 200), width=4)
    d.rounded_rectangle([330, 440, 690, 800], radius=72, fill=(14, 14, 17, 255),
                        outline=(212, 175, 55, 200), width=4)
    f = font(280, "arch")
    d.text((250, 235), "2", font=f, fill=(245, 245, 245, 255), anchor="mm")
    d.text((510, 625), "6", font=f, fill=(245, 245, 245, 255), anchor="mm")
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([230, 180, 530, 760], fill=(255, 200, 60, 130))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(60)))
    trophy = CUTS["trophy"].resize(
        (int(CUTS["trophy"].width * 620 / CUTS["trophy"].height), 620),
        Image.LANCZOS)
    img.alpha_composite(trophy, (380 - trophy.width // 2, 150))
    ft = font(64, "arch")
    d = ImageDraw.Draw(img)
    d.text((380, 880), "FIFA WORLD CUP", font=ft,
           fill=(255, 255, 255, 255), anchor="mm",
           stroke_width=3, stroke_fill=(0, 0, 0, 255))
    d.text((380, 970), "26", font=font(90, "arch"), fill=GOLD + (255,),
           anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0, 255))
    s = target_h / img.height
    return img.resize((int(img.width * s), target_h), Image.LANCZOS)


LOGO = make_logo()


def brick_overlay():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bw, bh = 180, 84
    for row in range(H // bh + 1):
        off = (row % 2) * bw // 2 - bw
        for col in range(W // bw + 2):
            x, y = col * bw + off, row * bh
            d.rectangle([x + 5, y + 5, x + bw - 5, y + bh - 5],
                        outline=(255, 210, 90, 255), width=6)
    return img


BRICKS = brick_overlay()


def light_rays():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = random.Random(5)
    for _ in range(9):
        x = r.randint(-200, W + 200)
        wbase = r.randint(90, 260)
        d.polygon([(x, -50), (x + 60, -50),
                   (x + wbase + 300, H), (x - wbase, H)],
                  fill=(255, 215, 120, r.randint(28, 50)))
    return img.filter(ImageFilter.GaussianBlur(22))


RAYS = light_rays()

HORSE_PTS = [(0.46, 0.04), (0.52, 0.10), (0.55, 0.05), (0.58, 0.12),
             (0.66, 0.18), (0.74, 0.28), (0.80, 0.42), (0.81, 0.52),
             (0.76, 0.55), (0.66, 0.50), (0.58, 0.44), (0.54, 0.45),
             (0.58, 0.56), (0.64, 0.68), (0.67, 0.84), (0.66, 0.96),
             (0.30, 0.96), (0.31, 0.82), (0.35, 0.66), (0.40, 0.52),
             (0.37, 0.42), (0.28, 0.34), (0.25, 0.26), (0.32, 0.20),
             (0.40, 0.14)]


def horse_sil(hh=900, color=(255, 220, 0)):
    w = int(hh * 0.78)
    img = Image.new("RGBA", (w, hh), (0, 0, 0, 0))
    pts = [(p[0] * w, p[1] * hh) for p in HORSE_PTS]
    glow = Image.new("RGBA", (w, hh), (0, 0, 0, 0))
    ImageDraw.Draw(glow).polygon(pts, fill=color + (160,))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(24)))
    d = ImageDraw.Draw(img)
    d.polygon(pts, fill=(12, 12, 14, 255), outline=color + (255,))
    d.line(pts + [pts[0]], fill=color + (255,), width=8, joint="curve")
    return img


HORSE = horse_sil()


def bolt(p0, p1, seed, color=(255, 230, 60), width=10, glow_r=14):
    r = random.Random(seed)
    pts = [p0]
    n = 7
    for i in range(1, n):
        t = i / n
        x = lerp(p0[0], p1[0], t) + r.uniform(-70, 70)
        y = lerp(p0[1], p1[1], t) + r.uniform(-30, 30)
        pts.append((x, y))
    pts.append(p1)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.line(pts, fill=color + (255,), width=width, joint="curve")
    layer = layer.filter(ImageFilter.GaussianBlur(glow_r))
    d = ImageDraw.Draw(layer)
    d.line(pts, fill=(255, 255, 255, 255), width=max(2, width // 3),
           joint="curve")
    return layer


# precomputed shards for the trophy glass shatter
def make_shards():
    r = random.Random(11)
    shards = []
    for _ in range(26):
        ang = r.uniform(0, 2 * math.pi)
        spd = r.uniform(500, 1600)
        size = r.uniform(28, 110)
        rot = r.uniform(-400, 400)
        tri = [(r.uniform(-size, size), r.uniform(-size, size)) for _ in range(3)]
        shards.append((ang, spd, tri, rot))
    return shards


SHARDS = make_shards()


def draw_shards(canvas, t_since, cx=540, cy=900):
    d = ImageDraw.Draw(canvas)
    for ang, spd, tri, rot in SHARDS:
        x = cx + math.cos(ang) * spd * t_since
        y = cy + math.sin(ang) * spd * t_since + 700 * t_since ** 2
        a = int(220 * clamp(1 - t_since / 1.0))
        if a <= 0:
            continue
        th = math.radians(rot * t_since)
        pts = [(x + px * math.cos(th) - py * math.sin(th),
                y + px * math.sin(th) + py * math.cos(th)) for px, py in tri]
        d.polygon(pts, fill=(225, 240, 255, a), outline=(255, 255, 255, a))


def crack_lines(seed=21):
    r = random.Random(seed)
    lines = []
    for _ in range(14):
        ang = r.uniform(0, 2 * math.pi)
        pts = [(540, 900)]
        x, y = 540, 900
        for seg in range(6):
            ln = r.uniform(60, 190)
            ang += r.uniform(-0.5, 0.5)
            x += math.cos(ang) * ln
            y += math.sin(ang) * ln
            pts.append((x, y))
        lines.append(pts)
    return lines


CRACKS = crack_lines()

EMBERS = [(random.Random(31 + i).uniform(0, W),
           random.Random(57 + i).uniform(0.35, 1.0),
           random.Random(91 + i).uniform(0, 6.28),
           random.Random(17 + i).uniform(3, 9)) for i in range(70)]


def draw_embers(canvas, t, intensity=1.0):
    d = ImageDraw.Draw(canvas)
    for x0, spd, ph, sz in EMBERS:
        prog = ((t * spd * 0.25 + ph / 6.28) % 1.0)
        y = H + 60 - prog * (H + 300)
        x = x0 + math.sin(t * 2 + ph) * 40
        a = int(200 * intensity * (1 - prog) * clamp(prog * 8))
        if a <= 0:
            continue
        col = (255, int(120 + 100 * (1 - prog)), 30, a)
        d.ellipse([x - sz, y - sz, x + sz, y + sz], fill=col)


def player_sil(w=460, h=560):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([w / 2 - 85, 40, w / 2 + 85, 210], fill=(60, 70, 100, 255))
    d.rounded_rectangle([w / 2 - 170, 230, w / 2 + 170, h - 20], radius=80,
                        fill=(60, 70, 100, 255))
    return img


SIL = player_sil()


def red_x(size=560):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = size * 0.12
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for dr_ in (gd, d):
        wdt = 64 if dr_ is gd else 44
        col = (255, 30, 30, 180) if dr_ is gd else (235, 20, 25, 255)
        dr_.line([(m, m), (size - m, size - m)], fill=col, width=wdt)
        dr_.line([(size - m, m), (m, size - m)], fill=col, width=wdt)
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(18)))
    d = ImageDraw.Draw(img)
    d.line([(m, m), (size - m, size - m)], fill=(255, 60, 55, 255), width=40)
    d.line([(size - m, m), (m, size - m)], fill=(255, 60, 55, 255), width=40)
    return img


REDX = red_x()


def padlock(hh=520):
    w = int(hh * 0.82)
    img = Image.new("RGBA", (w, hh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bw = int(w * 0.9)
    bx = (w - bw) // 2
    by = int(hh * 0.42)
    d.arc([bx + bw // 6, 10, bx + bw - bw // 6, int(hh * 0.62)],
          180, 360, fill=(200, 205, 215, 255), width=46)
    d.rounded_rectangle([bx, by, bx + bw, hh - 8], radius=60,
                        fill=(72, 76, 88, 255), outline=(180, 185, 200, 255),
                        width=8)
    d.ellipse([w / 2 - 42, by + 90, w / 2 + 42, by + 174],
              fill=(28, 30, 36, 255))
    d.rectangle([w / 2 - 18, by + 150, w / 2 + 18, by + 250],
                fill=(28, 30, 36, 255))
    return img


PADLOCK = padlock()


def chain_row(y, link=70, alpha=230):
    img = Image.new("RGBA", (W, 130), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = -20
    i = 0
    while x < W + 40:
        box = [x, 28, x + link, 102]
        d.ellipse(box, outline=(170, 175, 188, alpha), width=16)
        x += link - 18
        i += 1
    return img


CHAIN = chain_row(0)


def field_mesh(t):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    vy = 640
    for i in range(-6, 8):
        x_b = 540 + i * 220
        d.line([(540 + i * 36, vy), (x_b, H)], fill=(40, 255, 160, 70), width=3)
    off = (t * 480) % 160
    yy = vy + 10
    k = 0
    while yy < H:
        a = int(90 * (yy - vy) / (H - vy))
        d.line([(0, yy), (W, yy)], fill=(40, 255, 160, 30 + a), width=2)
        step = 14 + (yy - vy) * 0.22
        yy += step
        k += 1
    for side in (-1, 1):
        for j in range(5):
            prog = ((t * 0.9 + j * 0.2) % 1.0)
            yy = lerp(H - 80, vy + 60, prog)
            sc = lerp(1.0, 0.25, prog)
            cx = 540 + side * lerp(430, 90, prog)
            s = 70 * sc
            a = int(255 * (1 - prog * 0.6))
            d.line([(cx - s, yy + s), (cx, yy - s), (cx + s, yy + s)],
                   fill=(80, 255, 180, a), width=max(3, int(14 * sc)))
    return img


def tactical_board(t):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    col = (255, 255, 255, 60)
    d.rectangle([120, 280, 960, 1640], outline=col, width=4)
    d.line([(120, 960), (960, 960)], fill=col, width=4)
    d.ellipse([420, 840, 660, 1080], outline=col, width=4)
    d.rectangle([330, 280, 750, 520], outline=col, width=4)
    d.rectangle([330, 1400, 750, 1640], outline=col, width=4)
    r = random.Random(9)
    for i in range(8):
        x0, y0 = r.uniform(200, 880), r.uniform(400, 1500)
        x1, y1 = r.uniform(200, 880), r.uniform(400, 1500)
        p = (t * 0.45 + i * 0.13) % 1.0
        x, y = lerp(x0, x1, p), lerp(y0, y1, p)
        c = (255, 90, 90, 200) if i % 2 else (90, 180, 255, 200)
        d.ellipse([x - 16, y - 16, x + 16, y + 16], fill=c)
        d.line([(x, y), (x1, y1)], fill=c[:3] + (90,), width=3)
    return img


def radar_overlay(t, cx, cy):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    col = (60, 255, 140)
    for rr in (150, 270, 390):
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                  outline=col + (160,), width=4)
    d.line([(cx - 420, cy), (cx + 420, cy)], fill=col + (90,), width=2)
    d.line([(cx, cy - 420), (cx, cy + 420)], fill=col + (90,), width=2)
    ang = (t * 220) % 360
    d.pieslice([cx - 390, cy - 390, cx + 390, cy + 390], ang - 38, ang,
               fill=col + (60,))
    th = math.radians(ang)
    d.line([(cx, cy), (cx + 390 * math.cos(th), cy + 390 * math.sin(th))],
           fill=col + (230,), width=5)
    r = random.Random(4)
    for i in range(5):
        bx = cx + r.uniform(-330, 330)
        by = cy + r.uniform(-330, 330)
        blink = (math.sin(t * 5 + i * 1.7) + 1) / 2
        d.ellipse([bx - 10, by - 10, bx + 10, by + 10],
                  fill=(255, 80, 70, int(120 + 130 * blink)))
    return img


def slash_layer(p, seed=33):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = random.Random(seed)
    for i in range(3):
        off = i * 130 - 130
        x0 = lerp(-500, W + 200, p) + off
        d.line([(x0, -100), (x0 - 520, H + 100)],
               fill=(40, 220, 130, 230), width=26 - i * 6)
    return img.filter(ImageFilter.GaussianBlur(3))


def ui_mock():
    img = Image.new("RGBA", (W, 460), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([70, 20, W - 70, 150], radius=64,
                        fill=(255, 255, 255, 240))
    d.ellipse([95, 42, 180, 127], fill=(200, 60, 60, 255))
    d.text((137, 84), "26", font=font(40, "arch"), fill=(255, 255, 255, 255),
           anchor="mm")
    d.text((210, 84), "Drop your champion...", font=font(46, "osw"),
           fill=(110, 110, 115, 255), anchor="lm")
    return img


UI = ui_mock()
SUB_BTN = None


def sub_button():
    img = Image.new("RGBA", (560, 170), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([6, 10, 554, 160], radius=42, fill=(20, 20, 20, 160))
    d.rounded_rectangle([0, 0, 548, 150], radius=42, fill=(230, 33, 23, 255))
    d.text((274, 75), "SUBSCRIBE", font=font(64, "arch"),
           fill=(255, 255, 255, 255), anchor="mm")
    return img


SUB_BTN = sub_button()


def down_arrow(hh=240, color=GOLD):
    img = Image.new("RGBA", (220, hh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([80, 10, 140, hh - 100], fill=color + (255,))
    d.polygon([(20, hh - 110), (200, hh - 110), (110, hh - 10)],
              fill=color + (255,))
    return img


ARROW = down_arrow()


def goal_scene(tl):
    """tl is local time of the 'ball hits the post' beat (0..2.2)."""
    img = DARK_RADIAL.copy()
    d = ImageDraw.Draw(img)
    d.rectangle([0, 1450, W, H], fill=(12, 40, 22, 255))
    d.line([(0, 1450), (W, 1450)], fill=(255, 255, 255, 90), width=4)
    # goal frame
    for x in (190, 890):
        d.rectangle([x - 22, 540, x + 22, 1450], fill=(240, 240, 245, 255))
    d.rectangle([168, 498, 912, 542], fill=(240, 240, 245, 255))
    for gx in range(210, 890, 52):
        d.line([(gx, 545), (gx + 30, 1445)], fill=(255, 255, 255, 50), width=2)
    for gy in range(590, 1450, 60):
        d.line([(192, gy), (888, gy)], fill=(255, 255, 255, 40), width=2)
    # ball path: flies in, smacks the left post at tl=0.6, rebounds
    hit = 0.6
    if tl < hit:
        p = tl / hit
        bx = lerp(-80, 190, p)
        by = lerp(1500, 980, ease_out(p))
    else:
        p = clamp((tl - hit) / 0.9)
        bx = lerp(190, -160, p)
        by = lerp(980, 1500, ease_in(p))
    r = 62
    d.ellipse([bx - r, by - r, bx + r, by + r], fill=(245, 245, 245, 255),
              outline=(30, 30, 30, 255), width=6)
    d.ellipse([bx - 24, by - 24, bx + 24, by + 24], fill=(25, 25, 28, 255))
    if abs(tl - hit) < 0.12:
        fl = Image.new("RGBA", (W, H), (255, 255, 255,
                                        int(200 * (1 - abs(tl - hit) / 0.12))))
        img.alpha_composite(fl)
    return img


# ============================================================== sections
def sec_intro_logo(c, t, tl, p):
    c.alpha_composite(DARK_RADIAL)
    sc = lerp(0.55, 1.0, ease_out(tl / 2.0)) if tl < 2.0 else lerp(1.0, 1.06, (tl - 2) / 1.0)
    dx, dy = shake(int(t * FPS), 10 if 2.2 < tl < 2.9 else 0)
    paste(c, LOGO, 540 + dx, 1150 + dy, scale=sc)
    if 0.35 < tl < 2.15:
        pop = ease_out((tl - 0.35) / 0.3)
        cap = T("THE WORLD CUP\nIS HERE", 150, glow=(255, 255, 255), glow_r=22)
        paste(c, cap, 540, 470, scale=lerp(0.6, 1.0, pop), alpha=pop)
    elif tl >= 2.15:
        sx, sy = shake(int(t * FPS), 14 * clamp(1 - (tl - 2.15) / 0.5))
        cap = T("HISTORY\nREWRITTEN", 165, fill=(220, 255, 230),
                glow=NEON_GREEN, glow_r=30)
        paste(c, cap, 540 + sx, 470 + sy,
              scale=lerp(1.25, 1.0, ease_out((tl - 2.15) / 0.25)))


def sec_glitch_stadium(c, t, tl, p):
    fr = CLIPS["james_action"].frame(tl + 0.2)
    amt = lerp(1.0, 0.35, p)
    fr = glitch(fr, amt, int(t * FPS))
    c.alpha_composite(fr)
    c.alpha_composite(GRADES["co"])
    sx, sy = shake(int(t * FPS), 8)
    cap = T("HISTORY\nREWRITTEN", 165, fill=(220, 255, 230),
            glow=NEON_GREEN, glow_r=30)
    paste(c, cap, 540 + sx, 470 + sy)
    if tl < 0.12:
        c.alpha_composite(Image.new("RGBA", (W, H),
                                    (255, 255, 255, int(230 * (1 - tl / 0.12)))))


def sec_flags8(c, t, tl, p):
    c.alpha_composite(DARK_RADIAL)
    idx = min(int(tl / 0.3), 7)
    name, fl = CHAMPS[idx]
    seg_p = (tl - idx * 0.3) / 0.3
    g = fl.convert("L").convert("RGBA")
    paste(c, g, 540, 1000, scale=lerp(1.3, 1.22, seg_p) * 1080 / 900)
    bar = Image.new("RGBA", (W, 130), (0, 0, 0, 160))
    c.alpha_composite(bar, (0, 1320))
    paste(c, T(name, 86, fill=(220, 220, 220)), 540, 1385)
    paste(c, T("ONLY 8 NATIONS\nHAVE EVER WON IT", 110,
               glow=(255, 255, 255), glow_r=18), 540, 420)
    if seg_p < 0.18:
        c.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 60)))


def sec_shatter(c, t, tl, p):
    c.alpha_composite(DARK_RADIAL)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ga = int(120 + 100 * min(tl / 0.5, 1))
    ImageDraw.Draw(glow).ellipse([240, 480, 840, 1380],
                                 fill=(255, 190, 60, ga))
    c.alpha_composite(glow.filter(ImageFilter.GaussianBlur(90)))
    sx, sy = shake(int(t * FPS), 10 if tl > 0.5 else 3)
    tro = CUTS["trophy"].resize((int(CUTS["trophy"].width * 980 /
                                     CUTS["trophy"].height), 980),
                                Image.BILINEAR)
    paste(c, tro, 540 + sx, 900 + sy)
    if tl < 0.5:
        reveal = tl / 0.5
        d = ImageDraw.Draw(c)
        for pts in CRACKS:
            n = max(2, int(len(pts) * reveal))
            d.line(pts[:n], fill=(235, 245, 255, 200), width=5)
    else:
        draw_shards(c, tl - 0.5)
        if tl < 0.62:
            c.alpha_composite(Image.new(
                "RGBA", (W, H), (255, 255, 255, int(240 * (1 - (tl - 0.5) / 0.12)))))
    sx2, sy2 = shake(int(t * FPS) + 7, 9)
    paste(c, T("THE CURSE\nIS BREAKING", 140, fill=(255, 235, 235),
               glow=RED, glow_r=28), 540 + sx2, 380 + sy2)


TEASES = [("ECUADOR", "ec", None), ("JAPAN", "jp", "ueda_japan"),
          ("MOROCCO", "ma", "hakimi_src"), ("COLOMBIA", "co", "james_fist"),
          ("NETHERLANDS", "nl", "vandijk_src")]


def sec_teases(c, t, tl, p):
    if tl < 5.0:
        i = int(tl / 0.5)
        team, key, imkey = TEASES[i % 5]
        seg_p = (tl - i * 0.5) / 0.5
        slide = (1 - ease_out(seg_p / 0.45)) * W * (1 if i % 2 else -1)
        fl = FLAG_EC if key == "ec" else IMG[f"flag_{key}"]
        left = cover(fl.convert("RGBA"), W // 2, H, zoom=1.0)
        if imkey is None:
            right = cover(CLIPS["ecuador_action"].frame(1.4), W // 2, H, zoom=1.4)
        else:
            right = cover(IMG[imkey], W // 2, H, zoom=1.05)
        c.paste(left, (int(slide), 0))
        c.paste(right, (int(W // 2 - slide if i % 2 else W // 2 + slide), 0))
        d = ImageDraw.Draw(c)
        d.rectangle([W // 2 - 7, 0, W // 2 + 7, H], fill=(255, 255, 255, 255))
        bar = Image.new("RGBA", (W, 150), (0, 0, 0, 170))
        c.alpha_composite(bar, (0, 1280))
        paste(c, T(team, 100, glow=GOLD, glow_r=16), 540, 1357)
        cap = (T("5 RISING EMPIRES", 105, glow=(255, 255, 255), glow_r=18)
               if tl < 3.5 else
               T("FIRST GOLDEN CROWN", 96, fill=GOLD, glow=(255, 170, 0),
                 glow_r=24))
        paste(c, cap, 540, 330)
        c.alpha_composite(GRADES["co"])
    else:
        c.alpha_composite(DARK_RADIAL)
        zp = (tl - 5.0) / 2.0
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([270, 430, 810, 1330],
                                     fill=(255, 190, 60, 170))
        c.alpha_composite(glow.filter(ImageFilter.GaussianBlur(90)))
        tro = CUTS["trophy"].resize((int(CUTS["trophy"].width * 1050 /
                                         CUTS["trophy"].height), 1050),
                                    Image.BILINEAR)
        paste(c, tro, 540, 850, scale=lerp(1.25, 1.0, ease_io(zp)))
        for i, k in enumerate(["ec", "jp", "ma", "co", "nl"]):
            x = 130 + i * 205
            yo = ease_out(clamp((tl - 5.2 - i * 0.1) / 0.35))
            paste(c, CHIPS[k], x, int(1560 + 120 * (1 - yo)), scale=0.8,
                  alpha=yo)
        paste(c, T("FIRST GOLDEN CROWN", 96, fill=GOLD, glow=(255, 170, 0),
                   glow_r=24), 540, 330)
        paste(c, T("HERE'S WHO TO WATCH", 64, fill=(235, 235, 235)), 540, 1740)


def header(c, key, title):
    paste(c, CHIPS[key], 170, 170, scale=0.9)
    paste(c, T(title, 92, glow=(255, 255, 255), glow_r=12), 620, 170)


def sec_ecuador_wall(c, t, tl, p):
    c.alpha_composite(cover(CLIPS["ecuador_action"].frame(tl), W, H, zoom=1.05))
    c.alpha_composite(GRADES["ec"])
    header(c, "ec", "ECUADOR")
    if tl < 2.6:
        n = int(19 * ease_out(tl / 2.4))
        paste(c, T(str(n), 360, fill=GOLD, glow=(255, 170, 0), glow_r=30),
              540, 800)
        paste(c, T("MATCHES UNBEATEN", 86, glow=(255, 255, 255), glow_r=12),
              540, 1110)
    else:
        paste(c, T("19", 250, fill=GOLD, glow=(255, 170, 0), glow_r=26),
              540, 720, scale=1.0)
        paste(c, T("MATCHES UNBEATEN", 80, glow=(255, 255, 255), glow_r=12),
              540, 950)
    if 2.9 < tl < 3.05 or 3.4 < tl < 3.55:
        paste(c, BRICKS, 540, 960, alpha=0.55)
    if tl >= 3.55:
        paste(c, BRICKS, 540, 960, alpha=0.16)
        sx, sy = shake(int(t * FPS), 6 * clamp(1 - (tl - 3.55)))
        paste(c, T("A BRICK WALL", 150, fill=(255, 225, 120),
                   glow=(255, 180, 0), glow_r=24), 540 + sx, 1430 + sy,
              scale=lerp(1.3, 1.0, ease_out((tl - 3.55) / 0.3)))


def sec_ecuador_duo(c, t, tl, p):
    c.alpha_composite(make_grad((6, 16, 50, 255), (2, 6, 20, 255)))
    lx = (1 - ease_out((tl - 0.15) / 0.4)) * -560
    rx = (1 - ease_out((tl - 2.45) / 0.4)) * 560
    left = cover(CLIPS["pacho"].frame(tl, speed=0.7), 534, H)
    c.paste(left, (int(lx), 0))
    if tl > 2.45:
        right = cover(CLIPS["hincapie"].frame(tl - 2.45, speed=0.7), 534, H)
        c.paste(right, (int(546 + rx), 0))
    else:
        d = ImageDraw.Draw(c)
        d.rectangle([546, 0, W, H], fill=(8, 14, 36, 255))
        paste(c, T("?", 300, fill=(40, 60, 110)), 813, 900)
    d = ImageDraw.Draw(c)
    d.rectangle([534, 0, 546, H], fill=GOLD + (255,))
    c.alpha_composite(GRADES["ec"])
    header(c, "ec", "ECUADOR")
    if tl > 0.6:
        paste(c, T("PACHO", 95, glow=NEON_BLUE, glow_r=16), 270, 1460)
        paste(c, T("PSG · UCL WINNER", 44, fname="osw"), 270, 1560)
    if tl > 2.9:
        paste(c, T("HINCAPIÉ", 95, glow=RED, glow_r=16), 810, 1460)
        paste(c, T("ARSENAL", 44, fname="osw"), 810, 1560)


def sec_caicedo(c, t, tl, p):
    if tl < 3.8:
        zoom = lerp(1.0, 1.25, ease_io(tl / 3.8))
        c.alpha_composite(cover(CLIPS["caicedo"].frame(tl), W, H, zoom=zoom,
                                cy=0.42))
        c.alpha_composite(GRADES["ec"])
        header(c, "ec", "ECUADOR")
        paste(c, T("CAICEDO", 100, glow=NEON_BLUE, glow_r=18), 540, 1450)
        paste(c, T("CHELSEA · THE SHIELD", 46, fname="osw"), 540, 1555)
        if tl < 1.5:
            paste(c, T("SHIELDED", 130, glow=(255, 255, 255), glow_r=20),
                  540, 420, alpha=ease_out(tl / 0.3))
        else:
            paste(c, T("TOUGH TO BREAK", 110, glow=(255, 255, 255),
                       glow_r=20), 540, 420)
    else:
        tg = tl - 3.8
        c.alpha_composite(goal_scene(tg))
        c.alpha_composite(GRADES["ec"])
        header(c, "ec", "ECUADOR")
        if tg > 0.6:
            sx, sy = shake(int(t * FPS), 12 * clamp(1 - (tg - 0.6) / 0.8))
            paste(c, T("BIGGEST HURDLE:\nFINISHING", 120, fill=(255, 220, 220),
                       glow=RED, glow_r=26), 540 + sx, 450 + sy,
                  scale=lerp(1.35, 1.0, ease_out((tg - 0.6) / 0.3)))


def sec_japan_injuries(c, t, tl, p):
    if tl < 0.7:
        c.alpha_composite(cover(IMG["flag_jp"].convert("RGBA"), W, H,
                                zoom=lerp(1.35, 1.0, ease_out(tl / 0.7))))
        paste(c, T("JAPAN", 200, fill=(200, 20, 40),
                   stroke_fill=(255, 255, 255), glow=(255, 255, 255),
                   glow_r=26), 540, 960,
              scale=lerp(1.4, 1.0, ease_out(tl / 0.5)))
        return
    bg = cover(IMG["flag_jp"].convert("RGBA"), W, H, zoom=1.0)
    bg = bg.filter(ImageFilter.GaussianBlur(14))
    c.alpha_composite(bg)
    c.alpha_composite(Image.new("RGBA", (W, H), (10, 10, 30, 190)))
    header(c, "jp", "JAPAN")
    paste(c, T("INJURED SUPERSTARS", 84, fill=(255, 210, 210), glow=RED,
               glow_r=20), 540, 400)
    for side, (label, sub) in enumerate(
            [("MITOMA", "BRIGHTON"), ("MINAMINO", "MONACO")]):
        cx = 285 + side * 510
        card = Image.new("RGBA", (470, 680), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle([0, 0, 469, 679], radius=36, fill=(16, 22, 60, 235),
                             outline=(120, 140, 220, 200), width=5)
        c.alpha_composite(card, (cx - 235, 560))
        if side == 0:
            mi = CUTS["mitoma"]
            mi = mi.resize((int(mi.width * 600 / mi.height), 600),
                           Image.BILINEAR)
            region = c.crop((cx - 235, 560, cx + 235, 1240))
            region.alpha_composite(mi, (235 - mi.width // 2, 80))
            c.paste(region, (cx - 235, 560))
        else:
            paste(c, SIL, cx, 880)
        paste(c, T(label, 72, glow=(255, 255, 255), glow_r=10), cx, 1310)
        paste(c, T(sub, 40, fname="osw"), cx, 1390)
        x_t0 = 0.95 + side * 0.55
        if tl > x_t0:
            xs = lerp(2.0, 1.0, ease_out((tl - x_t0) / 0.22))
            sx, sy = shake(int(t * FPS) + side, 8 * clamp(1 - (tl - x_t0)))
            paste(c, REDX, cx + sx, 890 + sy, scale=xs * 0.95)


def sec_japan_press(c, t, tl, p):
    pw = W // 3
    for i in range(3):
        fr = cover(CLIPS["japan_press"].frame(tl * 1.1 + i * 0.18), pw, H,
                   zoom=1.35, cx=0.3 + 0.2 * i)
        c.paste(fr, (i * pw, 0))
        d = ImageDraw.Draw(c)
        if i:
            d.rectangle([i * pw - 4, 0, i * pw + 4, H], fill=(120, 200, 255, 255))
    c.alpha_composite(GRADES["jp"])
    r = random.Random(int(t * FPS))
    d = ImageDraw.Draw(c)
    for _ in range(14):
        y = r.randint(0, H)
        x = r.randint(0, W - 300)
        ln = r.randint(120, 380)
        d.line([(x, y), (x + ln, y)], fill=(140, 220, 255, 90), width=3)
    header(c, "jp", "JAPAN")
    sx, sy = shake(int(t * FPS), 5)
    paste(c, T("HIGH-INTENSITY\nPRESS", 130, fill=(210, 240, 255),
               glow=NEON_BLUE, glow_r=26), 540 + sx, 1450 + sy)


def sec_endo_kubo(c, t, tl, p):
    c.alpha_composite(make_grad((6, 14, 60, 255), (2, 4, 24, 255)))
    d = ImageDraw.Draw(c)
    for gx in range(0, W, 90):
        d.line([(gx, 0), (gx, H)], fill=(60, 120, 255, 26), width=2)
    for gy in range(0, H, 90):
        d.line([(0, gy), (W, gy)], fill=(60, 120, 255, 26), width=2)
    lx = (1 - ease_out(tl / 0.4)) * -600
    en = CUTS["endo"]
    en = en.resize((int(en.width * 1050 / en.height), 1050), Image.LANCZOS)
    glowL = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glowL).ellipse([40, 560, 500, 1500], fill=(40, 120, 255, 120))
    c.alpha_composite(glowL.filter(ImageFilter.GaussianBlur(70)))
    paste(c, en, int(280 + lx), 1080)
    if tl > 1.6:
        ku = CUTS["kubo"]
        kus = lerp(0.78, 0.95, ease_io((tl - 1.6) / 3.4)) * 1250
        ku = ku.resize((int(ku.width * kus / ku.height), int(kus)),
                       Image.BILINEAR)
        rx = (1 - ease_out((tl - 1.6) / 0.4)) * 620
        glowR = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(glowR).ellipse([600, 500, 1060, 1500],
                                      fill=(120, 60, 255, 120))
        c.alpha_composite(glowR.filter(ImageFilter.GaussianBlur(70)))
        paste(c, ku, int(800 + rx), 1020)
    if tl > 2.0 and int(t * FPS) % 3 != 0:
        for k in range(2):
            c.alpha_composite(bolt((430, 800 + k * 260), (700, 740 + k * 300),
                                   seed=int(t * FPS) * 3 + k,
                                   color=(90, 180, 255), width=7, glow_r=10))
    paste(c, T("ENDO", 86, glow=NEON_BLUE, glow_r=16), 250, 1620)
    paste(c, T("THE ANCHOR", 44, fname="osw"), 250, 1710)
    if tl > 2.2:
        paste(c, T("KUBO", 86, glow=(180, 120, 255), glow_r=16), 830, 1620)
        paste(c, T("THE GENIUS", 44, fname="osw"), 830, 1710)
    header(c, "jp", "JAPAN")


def sec_ueda(c, t, tl, p):
    c.alpha_composite(make_grad((4, 10, 40, 255), (2, 4, 18, 255)))
    c.alpha_composite(tactical_board(t))
    ue = CUTS["ueda"]
    ue = ue.resize((int(ue.width * 760 / ue.height), 760), Image.BILINEAR)
    rise = ease_out(tl / 0.5)
    paste(c, ue, 540, int(1050 + 250 * (1 - rise)))
    c.alpha_composite(radar_overlay(t, 540, 870))
    header(c, "jp", "JAPAN")
    paste(c, T("UEDA · TOP SCORER", 74, glow=NEON_GREEN, glow_r=14), 540, 1540)
    if tl > 2.2:
        r = random.Random(int(t * FPS))
        gx, gy = r.randint(-7, 7), r.randint(-5, 5)
        paste(c, T("TACTICAL\nNIGHTMARE", 130, fill=(220, 255, 230),
                   glow=NEON_GREEN, glow_r=24), 540 + gx, 420 + gy,
              scale=lerp(1.3, 1.0, ease_out((tl - 2.2) / 0.3)))
    else:
        paste(c, T("DISCIPLINED. DEADLY.", 80, glow=(255, 255, 255),
                   glow_r=14), 540, 430)


def sec_morocco_coach(c, t, tl, p):
    c.alpha_composite(cover(IMG["flag_ma"].convert("RGBA"), W, H, zoom=1.05))
    c.alpha_composite(GRADES["ma"])
    c.alpha_composite(Image.new("RGBA", (W, H), (20, 5, 8, 110)))
    card_w, card_h = 740, 1060
    fr = cover(CLIPS["ouahbi"].frame(max(0, tl - 0.3), speed=0.9),
               card_w, card_h, cy=0.4)
    card = Image.new("RGBA", (card_w + 24, card_h + 24), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle(
        [0, 0, card_w + 23, card_h + 23], radius=40,
        fill=(245, 215, 130, 255))
    mask = Image.new("L", (card_w, card_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, card_w - 1, card_h - 1],
                                           radius=34, fill=255)
    card.paste(fr, (12, 12), mask)
    pop = ease_out(tl / 0.45)
    paste(c, card, 540, 940, scale=lerp(0.8, 1.0, pop), alpha=pop)
    if 0.9 < tl < 1.5:
        c.alpha_composite(slash_layer((tl - 0.9) / 0.6))
    header(c, "ma", "MOROCCO")
    paste(c, T("OUAHBI · HEAD COACH", 60, fname="osw",
               glow=(255, 255, 255), glow_r=10), 540, 1560)
    if tl > 1.3:
        paste(c, T("THE ATLAS LIONS", 100, fill=(120, 255, 170),
                   glow=(0, 200, 90), glow_r=22), 540, 350,
              scale=lerp(1.25, 1.0, ease_out((tl - 1.3) / 0.3)))
    if tl > 3.1:
        sx, sy = shake(int(t * FPS), 7 * clamp(1 - (tl - 3.1)))
        paste(c, T("TRANSFORMED", 118, fill=(255, 245, 230),
                   glow=(255, 120, 40), glow_r=24), 540 + sx, 1720 + sy)


def sec_hakimi_bounou(c, t, tl, p):
    c.alpha_composite(make_grad((70, 8, 18, 255), (10, 30, 22, 255)))
    d = ImageDraw.Draw(c)
    for i in range(-3, 16):
        d.line([(i * 110, 0), (i * 110 - 500, H)], fill=(0, 120, 70, 60),
               width=14)
    if tl < 3.2:
        hk = CUTS["hakimi"]
        hk = hk.resize((int(hk.width * 1150 / hk.height), 1150), Image.LANCZOS)
        sl = (1 - ease_out(tl / 0.45)) * -700
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([150, 420, 930, 1620],
                                     fill=(0, 230, 110, 110))
        c.alpha_composite(glow.filter(ImageFilter.GaussianBlur(80)))
        paste(c, hk, int(540 + sl), 1010)
        paste(c, T("HAKIMI", 130, glow=NEON_GREEN, glow_r=22), 540, 1620,
              alpha=ease_out((tl - 0.4) / 0.3))
        paste(c, T("THE NEW WAVE ARRIVES", 60, fname="osw"), 540, 1740,
              alpha=ease_out((tl - 0.6) / 0.3))
    elif tl < 5.8:
        ts = tl - 3.2
        bn = CUTS["bounou"]
        bn = bn.resize((int(bn.width * 900 / bn.height), 900), Image.BILINEAR)
        ang = lerp(-10, 0, ease_out(ts / 0.5))
        yy = int(lerp(1500, 1010, ease_out(ts / 0.45)))
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([100, 500, 980, 1500],
                                     fill=(255, 200, 60, 100))
        c.alpha_composite(glow.filter(ImageFilter.GaussianBlur(80)))
        paste(c, bn, 540, yy, angle=ang)
        paste(c, T("BONO", 130, fill=GOLD, glow=(255, 170, 0), glow_r=22),
              540, 1620, alpha=ease_out((ts - 0.4) / 0.3))
        paste(c, T("THE WALL OF MOROCCO", 60, fname="osw"), 540, 1740,
              alpha=ease_out((ts - 0.5) / 0.3))
    else:
        ts = tl - 5.8
        c.alpha_composite(field_mesh(t))
        sx, sy = shake(int(t * FPS), 9 * clamp(1 - ts / 1.0))
        paste(c, T("STUN THE WORLD\nAGAIN", 130, fill=(255, 250, 240),
                   glow=(255, 80, 40), glow_r=28), 540 + sx, 760 + sy,
              scale=lerp(1.4, 1.0, ease_out(ts / 0.35)))
        if ts < 0.15:
            c.alpha_composite(Image.new("RGBA", (W, H),
                                        (255, 255, 255, int(180 * (1 - ts / 0.15)))))
    header(c, "ma", "MOROCCO")


def sec_colombia_horse(c, t, tl, p):
    c.alpha_composite(make_grad((8, 6, 2, 255), (40, 16, 0, 255)))
    draw_embers(c, t, intensity=0.7 if tl < 2.2 else 1.0)
    if tl < 2.2:
        pop = ease_out(tl / 0.5)
        paste(c, HORSE, 540, 950, scale=lerp(0.7, 1.0, pop), alpha=pop)
        paste(c, T("THE ULTIMATE\nDARK HORSE", 130, fill=(255, 225, 90),
                   glow=(255, 180, 0), glow_r=26), 540, 380,
              alpha=ease_out((tl - 0.3) / 0.3))
    else:
        ts = tl - 2.2
        lo = CUTS["lorenzo"]
        lo = lo.resize((int(lo.width * 760 / lo.height), 760), Image.LANCZOS)
        fire = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(fire).ellipse([100, 700, 980, 1700],
                                     fill=(255, 110, 10, 120))
        c.alpha_composite(fire.filter(ImageFilter.GaussianBlur(100)))
        paste(c, lo, 540, int(lerp(1150, 980, ease_out(ts / 0.4))), alpha=ease_out(ts / 0.3))
        paste(c, T("LORENZO", 120, fill=(255, 230, 120), glow=(255, 140, 0),
                   glow_r=24), 540, 1500, alpha=ease_out((ts - 0.3) / 0.3))
        paste(c, T("HEAD COACH · UNBEATEN RUN", 54, fname="osw"), 540, 1620,
              alpha=ease_out((ts - 0.4) / 0.3))
        paste(c, T("A LEGENDARY RUN", 92, glow=(255, 255, 255), glow_r=16),
              540, 350)
    header(c, "co", "COLOMBIA")


def sec_james_diaz(c, t, tl, p):
    c.alpha_composite(make_grad((30, 22, 0, 255), (8, 6, 2, 255)))
    em_l = 1.0 if tl < 2.8 else 0.45
    em_r = 0.45 if tl < 2.8 else 1.0
    # left: James cutout on gold card
    lw = 534
    lcard = Image.new("RGBA", (lw, H), (0, 0, 0, 255))
    lg = make_grad((255, 190, 0, 255), (120, 70, 0, 255)).resize((lw, H))
    lcard.alpha_composite(lg)
    jm = CUTS["james"]
    js = lerp(1.0, 1.12, ease_io(clamp(tl / 8.0)))
    jm = jm.resize((int(jm.width * 1.05 * js), int(jm.height * 1.05 * js)),
                   Image.BILINEAR)
    lcard.alpha_composite(jm, (lw // 2 - jm.width // 2 + 10,
                               H // 2 - jm.height // 2 - 60))
    if em_l < 1.0:
        lcard.alpha_composite(Image.new("RGBA", (lw, H), (0, 0, 0, 130)))
    sl = (1 - ease_out(tl / 0.4)) * -560
    c.alpha_composite(lcard, (int(sl), 0))
    # right: Diaz footage
    if tl > 0.9:
        rfr = cover(CLIPS["diaz_action"].frame(tl - 0.9, speed=0.85), 534, H,
                    zoom=1.1)
        if em_r < 1.0:
            rfr = Image.alpha_composite(
                rfr, Image.new("RGBA", (534, H), (0, 0, 0, 130)))
        rs = (1 - ease_out((tl - 0.9) / 0.4)) * 560
        c.alpha_composite(rfr, (int(546 + rs), 0))
    else:
        ImageDraw.Draw(c).rectangle([546, 0, W, H], fill=(20, 14, 2, 255))
    # divider lightning
    seedband = int(t * FPS) // 2
    c.alpha_composite(bolt((540, -40), (540, H + 40), seed=seedband,
                           color=(255, 220, 50), width=8, glow_r=12))
    if 3.4 < tl < 6.4 and int(t * FPS) % 4 < 2:
        c.alpha_composite(bolt((700, 1100), (980, 1650),
                               seed=int(t * FPS) * 7, color=(255, 230, 80),
                               width=9, glow_r=14))
    header(c, "co", "COLOMBIA")
    if tl > 0.7:
        paste(c, T("JAMES", 92, glow=GOLD, glow_r=18), 270, 1500)
        paste(c, T("THE GENIUS", 46, fname="osw"), 270, 1600)
    if tl > 3.2:
        paste(c, T("DÍAZ", 92, fill=(255, 240, 120), glow=(255, 220, 0),
                   glow_r=20), 810, 1500)
        paste(c, T("ELECTRIC PACE", 46, fname="osw"), 810, 1600)
    if 2.8 < tl < 2.95:
        c.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 220, 90)))


def sec_nl_curse(c, t, tl, p):
    c.alpha_composite(cover(IMG["flag_nl"].convert("RGBA"), W, H, zoom=1.0))
    c.alpha_composite(Image.new("RGBA", (W, H), (30, 30, 34, 150)))
    c.alpha_composite(GRADES["nl"])
    header(c, "nl", "NETHERLANDS")
    broken = tl > 5.3  # padlock has shattered
    paste(c, T("3-TIME RUNNERS-UP", 92, glow=(255, 160, 40), glow_r=20),
          540, 380, alpha=ease_out((tl - 0.4) / 0.3) * (0.0 if broken else 1.0))
    years = [("1974", 1.2, 700), ("1978", 1.9, 950), ("2010", 2.6, 1200)]
    for label, t0, yy in years:
        if tl > t0 and not broken:
            pp = ease_out((tl - t0) / 0.25)
            sx, sy = shake(int(t * FPS) + yy, 6 * clamp(1 - (tl - t0) / 0.5))
            paste(c, T(label, 170, fill=SILVER, stroke_fill=(30, 30, 36),
                       glow=(255, 255, 255), glow_r=14),
                  540 + sx, yy + sy, scale=lerp(1.9, 1.0, pp), alpha=pp)
    if 3.6 < tl:
        ts = tl - 3.6
        if ts < 1.7:
            ya = ease_out(ts / 0.35)
            c.alpha_composite(CHAIN, (0, 760))
            c.alpha_composite(CHAIN, (0, 1160))
            paste(c, PADLOCK, 540, int(1000 - 200 * (1 - ya)), alpha=ya)
        else:
            tb = ts - 1.7
            if tb < 0.13:
                c.alpha_composite(Image.new(
                    "RGBA", (W, H), (255, 255, 255, int(220 * (1 - tb / 0.13)))))
            draw_shards(c, tb, cx=540, cy=1000)
            sx, sy = shake(int(t * FPS), 11 * clamp(1 - tb / 0.9))
            r = random.Random(int(t * FPS) // 2)
            jx, jy = r.randint(-4, 4), r.randint(-3, 3)
            paste(c, T("BREAK\nTHE CURSE", 165, fill=(255, 245, 235),
                       glow=(255, 120, 30), glow_r=28),
                  540 + sx + jx, 980 + sy + jy,
                  scale=lerp(1.4, 1.0, ease_out(tb / 0.3)))


def sec_vandijk(c, t, tl, p):
    c.alpha_composite(make_grad((44, 42, 46, 255), (14, 13, 15, 255)))
    ray_a = clamp((tl - 3.5) / 1.5)
    if ray_a > 0:
        paste(c, RAYS, 540, 960, alpha=ray_a)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([140, 300, 940, 1300],
                                 fill=(255, 180, 60, int(40 + 90 * ray_a)))
    c.alpha_composite(glow.filter(ImageFilter.GaussianBlur(110)))
    vd = CUTS["vandijk"]
    sc = lerp(1.45, 1.78, ease_io(tl / 8.0))
    vd2 = vd.resize((int(vd.width * sc * 0.62), int(vd.height * sc * 0.62)),
                    Image.BILINEAR)
    paste(c, vd2, 540, int(lerp(1250, 1130, ease_io(tl / 8.0))))
    c.alpha_composite(GRADES["nl"])
    header(c, "nl", "NETHERLANDS")
    if tl > 0.6 and tl < 4.6:
        paste(c, T("TOWERING\nVAN DIJK", 130, glow=(255, 255, 255),
                   glow_r=20), 540, 460,
              alpha=ease_out((tl - 0.6) / 0.3))
    if tl >= 4.6:
        txt = T("ETERNAL GLORY", 116, fill=(255, 230, 140),
                glow=(255, 190, 40), glow_r=30)
        shp = ((tl - 4.6) * 0.55) % 1.2
        txt2 = txt.copy()
        band = Image.new("RGBA", txt.size, (0, 0, 0, 0))
        bx = int(lerp(-200, txt.width + 200, clamp(shp)))
        ImageDraw.Draw(band).polygon(
            [(bx, 0), (bx + 110, 0), (bx + 30, txt.height),
             (bx - 80, txt.height)], fill=(255, 255, 250, 170))
        band = band.filter(ImageFilter.GaussianBlur(10))
        txt2.alpha_composite(Image.composite(
            band, Image.new("RGBA", band.size, (0, 0, 0, 0)),
            txt.getchannel("A")))
        paste(c, txt2, 540, 460,
              scale=lerp(1.25, 1.0, ease_out((tl - 4.6) / 0.3)))
        paste(c, T("THE FINAL SHOT", 60, fname="osw"), 540, 640)
    paste(c, T("THE CAPTAIN", 54, fname="osw", glow=(255, 255, 255),
               glow_r=8), 540, 1700)


def sec_outro(c, t, tl, p):
    c.alpha_composite(DARK_RADIAL)
    pop = ease_out(tl / 0.4)
    paste(c, LOGO, 540, 930, scale=0.78 * lerp(0.7, 1.0, pop), alpha=pop)
    for i, k in enumerate(["ec", "jp", "ma", "co", "nl"]):
        ang = t * 2.4 + i * 2 * math.pi / 5
        x = 540 + math.cos(ang) * 430
        y = 930 + math.sin(ang) * 300
        depth = (math.sin(ang) + 1) / 2
        paste(c, CHIPS[k], x, y, scale=lerp(0.62, 0.95, depth),
              alpha=lerp(0.75, 1.0, depth))
    paste(c, T("WHO WINS IT?", 130, fill=GOLD, glow=(255, 180, 0), glow_r=26),
          540, 360, alpha=ease_out((tl - 0.3) / 0.3))
    if tl > 1.6:
        a = ease_out((tl - 1.6) / 0.35)
        bounce = abs(math.sin(t * 4.5)) * 40
        paste(c, ARROW, 540, int(1240 - bounce), scale=0.85, alpha=a)
        c.alpha_composite(UI, (0, 1380))
        pulse = 1 + 0.045 * math.sin(t * 7)
        paste(c, SUB_BTN, 540, 1660, scale=pulse, alpha=a)
        paste(c, T("COMMENT YOUR CHAMPION", 56, glow=NEON_GREEN, glow_r=14),
              540, 1810, alpha=a)
    if tl > 4.5:
        c.alpha_composite(Image.new("RGBA", (W, H),
                                    (0, 0, 0, int(255 * (tl - 4.5) / 0.5))))


SECTIONS = [
    (0.0, 3.0, sec_intro_logo),
    (3.0, 4.0, sec_glitch_stadium),
    (4.0, 6.4, sec_flags8),
    (6.4, 8.0, sec_shatter),
    (8.0, 15.0, sec_teases),
    (15.0, 21.0, sec_ecuador_wall),
    (21.0, 26.0, sec_ecuador_duo),
    (26.0, 32.0, sec_caicedo),
    (32.0, 35.0, sec_japan_injuries),
    (35.0, 37.0, sec_japan_press),
    (37.0, 42.0, sec_endo_kubo),
    (42.0, 47.0, sec_ueda),
    (47.0, 52.0, sec_morocco_coach),
    (52.0, 60.0, sec_hakimi_bounou),
    (60.0, 65.0, sec_colombia_horse),
    (65.0, 73.0, sec_james_diaz),
    (73.0, 80.0, sec_nl_curse),
    (80.0, 88.0, sec_vandijk),
    (88.0, 93.0, sec_outro),
]


def render_frame(fi):
    t = fi / FPS
    c = Image.new("RGBA", (W, H), (5, 5, 8, 255))
    for t0, t1, fn in SECTIONS:
        if t0 <= t < t1:
            fn(c, t, t - t0, (t - t0) / (t1 - t0))
            break
    c.alpha_composite(VIGNETTE)
    c.alpha_composite(GRAIN[fi % len(GRAIN)])
    return c.convert("RGB")


def main():
    out = os.path.join(ROOT, "output", "video_silent.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "medium", "-crf", "19",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    import time
    t0 = time.time()
    for fi in range(N_FRAMES):
        proc.stdin.write(render_frame(fi).tobytes())
        if fi % 150 == 0:
            el = time.time() - t0
            print(f"frame {fi}/{N_FRAMES}  {el:.0f}s elapsed", flush=True)
    proc.stdin.close()
    proc.wait()
    print("done:", out)


if __name__ == "__main__":
    main()
