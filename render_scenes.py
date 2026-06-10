#!/usr/bin/env python3
"""
Render every still scene (1080x1920) for the "5 New Empires" World Cup edit.
Clean, cinematic, centered. Hero photos sit sharp inside a rounded frame over a
blurred fill of themselves (no black bars, faces never cropped). Missing faces
become styled nameplates in national colours.
Output: scenes/NN_id.png  +  scenes/manifest.json (order, durations, transitions)
"""
import os, json, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps

ROOT = os.path.dirname(os.path.abspath(__file__))
A    = os.path.join(ROOT, "assets")
PH   = os.path.join(A, "photos")
FL   = os.path.join(A, "flags")
OUT  = os.path.join(ROOT, "scenes")
os.makedirs(OUT, exist_ok=True)

W, H = 1080, 1920
BG   = (10, 13, 18)

# ---- palette ---------------------------------------------------------------
GOLD   = (235, 187, 75)
GOLD2  = (244, 210, 122)
WHITE  = (244, 246, 248)
GREY   = (150, 156, 165)
RED_HL = (220, 60, 60)
NAT = {
    "ecuador":     {"a": (255,206,0),  "b": (3,78,162),   "c": (237,28,36)},
    "japan":       {"a": (188,0,45),   "b": (235,235,235),"c": (188,0,45)},
    "morocco":     {"a": (193,39,45),  "b": (0,98,51),    "c": (193,39,45)},
    "colombia":    {"a": (252,209,22), "b": (0,56,147),   "c": (206,17,38)},
    "netherlands": {"a": (255,107,0),  "b": (33,70,139),  "c": (174,28,40)},
}

# ---- fonts -----------------------------------------------------------------
F = os.path.join(A, "fonts")
def font(name, size): return ImageFont.truetype(os.path.join(F, name), size)
def _vf(name, size, wght):
    fo = ImageFont.truetype(os.path.join(F, name), size)
    fo.set_variation_by_axes([wght])
    return fo
def anton(s):  return font("Anton-Regular.ttf", s)       # heavy condensed header
def bebas(s):  return font("BebasNeue-Regular.ttf", s)
def mont(s):   return _vf("Montserrat-VF.ttf", s, 600)   # sleek subtitle
def osw(s):    return _vf("Oswald-VF.ttf", s, 500)
def oswb(s):   return _vf("Oswald-VF.ttf", s, 700)

# ---- image helpers ---------------------------------------------------------
def load(path):
    return Image.open(path).convert("RGB")

def grade(img, color=0.86, contrast=1.06, bright=1.0):
    img = ImageEnhance.Color(img).enhance(color)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    if bright != 1.0:
        img = ImageEnhance.Brightness(img).enhance(bright)
    return img

def cover(img, w, h, fx=0.5, fy=0.42):
    """Resize+crop to exactly w x h, biased to focal point (fy upper for faces)."""
    iw, ih = img.size
    s = max(w/iw, h/ih)
    nw, nh = int(math.ceil(iw*s)), int(math.ceil(ih*s))
    img = img.resize((nw, nh), Image.LANCZOS)
    x = int((nw-w)*fx); y = int((nh-h)*fy)
    x = max(0, min(x, nw-w)); y = max(0, min(y, nh-h))
    return img.crop((x, y, x+w, y+h))

def contain(img, w, h):
    iw, ih = img.size
    s = min(w/iw, h/ih)
    return img.resize((max(1,int(iw*s)), max(1,int(ih*s))), Image.LANCZOS)

def rounded_mask(w, h, r):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0,0,w-1,h-1], radius=r, fill=255)
    return m

def vgrad(w, h, top_a, bot_a, color=(0,0,0)):
    """Vertical alpha gradient overlay (top_a..bot_a alpha 0-255)."""
    g = Image.new("L", (1, h))
    for y in range(h):
        t = y/(h-1)
        g.putpixel((0,y), int(top_a+(bot_a-top_a)*t))
    g = g.resize((w, h))
    ov = Image.new("RGBA", (w, h), color+(0,))
    ov.putalpha(g)
    return ov

def vignette(im, strength=120):
    w, h = im.size
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse([-w*0.30, -h*0.18, w*1.30, h*1.18], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(220))
    dark = Image.new("RGB", (w, h), (0,0,0))
    inv = ImageOps.invert(mask).point(lambda p: int(p*strength/255))
    im.paste(dark, (0,0), inv)
    return im

_grain = None
def grain(im, amt=10):
    global _grain
    if _grain is None:
        import random
        random.seed(7)
        g = Image.new("L", (W//2, H//2))
        g.putdata([random.randint(0,255) for _ in range((W//2)*(H//2))])
        _grain = g.resize((W, H)).filter(ImageFilter.GaussianBlur(0.4))
    noise = _grain.point(lambda p: int((p-128)*amt/128))
    base = im.convert("RGB")
    overlay = Image.merge("RGB", (noise, noise, noise))
    return ImageChops_add(base, overlay)

def ImageChops_add(a, b):
    from PIL import ImageChops
    return ImageChops.add(a, b, scale=1.0, offset=0)

def base_canvas():
    return Image.new("RGB", (W, H), BG)

# ---- text helpers ----------------------------------------------------------
def wrap(draw, text, fnt, maxw):
    words = text.split()
    lines, cur = [], ""
    for wd in words:
        t = (cur+" "+wd).strip()
        if draw.textlength(t, font=fnt) <= maxw:
            cur = t
        else:
            if cur: lines.append(cur)
            cur = wd
    if cur: lines.append(cur)
    return lines

def draw_center(img, text, fnt, y, fill=WHITE, stroke=0, stroke_fill=(0,0,0),
                tracking=0):
    d = ImageDraw.Draw(img)
    if tracking == 0:
        w = d.textlength(text, font=fnt)
        x = (W - w)//2
        d.text((x, y), text, font=fnt, fill=fill, stroke_width=stroke,
               stroke_fill=stroke_fill)
        return
    # letter tracking
    widths = [d.textlength(ch, font=fnt) for ch in text]
    total = sum(widths) + tracking*(len(text)-1)
    x = (W-total)/2
    for ch, wch in zip(text, widths):
        d.text((x, y), ch, font=fnt, fill=fill, stroke_width=stroke,
               stroke_fill=stroke_fill)
        x += wch + tracking

def subtitle(img, text, y=1530, maxw=900):
    """Sleek lower-third subtitle on a soft translucent pill, centered."""
    if not text: return
    d = ImageDraw.Draw(img)
    fnt = mont(42)
    lines = wrap(d, text, fnt, maxw)
    lh = 56
    block_h = lh*len(lines)
    pad = 26
    box_w = max(d.textlength(l, font=fnt) for l in lines) + pad*2
    box_h = block_h + pad*1.2
    bx0 = (W-box_w)/2; by0 = y - pad*0.6
    pill = Image.new("RGBA", (int(box_w), int(box_h)), (0,0,0,0))
    ImageDraw.Draw(pill).rounded_rectangle([0,0,int(box_w)-1,int(box_h)-1],
                    radius=26, fill=(8,10,14,150))
    img.paste(pill, (int(bx0), int(by0)), pill)
    yy = y
    for l in lines:
        draw_center(img, l, fnt, yy, fill=WHITE)
        yy += lh

def tag(img, text, color, y=120):
    """Small uppercase nation/role tag with an accent bar, centered."""
    d = ImageDraw.Draw(img)
    fnt = oswb(38)
    tw = d.textlength(text.upper(), font=fnt)
    bar = 8
    total = tw + 40
    x0 = (W-total)/2
    d.rounded_rectangle([x0, y+6, x0+bar, y+44], radius=4, fill=color)
    d.text((x0+24, y), text.upper(), font=fnt, fill=WHITE)

def header(img, text, y, color=WHITE, size=118, stroke=5, sub=None, sub_color=None):
    draw_center(img, text.upper(), anton(size), y, fill=color,
                stroke=stroke, stroke_fill=(0,0,0), tracking=2)
    if sub:
        draw_center(img, sub.upper(), oswb(44), y+size+14,
                    fill=sub_color or GOLD, tracking=8)

def accent_ticks(img, color):
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=color)
    d.rectangle([0, H-10, W, H], fill=color)

# ---- framed hero (sharp photo on blurred self-fill) ------------------------
def hero(photo, frame_w=940, frame_h=1180, top=300, fx=0.5, fy=0.40):
    img = base_canvas()
    src = grade(load(photo))
    # blurred background fill
    bgf = cover(src, W, H, 0.5, 0.42).filter(ImageFilter.GaussianBlur(34))
    bgf = ImageEnhance.Brightness(bgf).enhance(0.45)
    img.paste(bgf, (0,0))
    img.paste(vgrad(W, H, 120, 220), (0,0), vgrad(W, H, 120, 220))
    # sharp framed subject
    card = cover(src, frame_w, frame_h, fx, fy)
    r = 30
    mask = rounded_mask(frame_w, frame_h, r)
    # drop shadow
    sh = Image.new("RGBA", (W, H), (0,0,0,0))
    shm = Image.new("L", (frame_w, frame_h), 0)
    ImageDraw.Draw(shm).rounded_rectangle([0,0,frame_w-1,frame_h-1], radius=r, fill=210)
    cx = (W-frame_w)//2
    sh.paste((0,0,0,255), (cx, top), shm)
    sh = sh.filter(ImageFilter.GaussianBlur(34))
    img.paste(sh, (0, 26), sh)
    img.paste(card, (cx, top), mask)
    # thin border stroke
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([cx, top, cx+frame_w-1, top+frame_h-1], radius=r,
                        outline=(255,255,255), width=3)
    # inner bottom gradient inside the card for text legibility
    gin = vgrad(frame_w, 360, 0, 200)
    img.paste(gin, (cx, top+frame_h-360), gin)
    return img

def finish(img, color=None):
    """Apply vignette + grain + accent ticks; return final RGB."""
    if color: accent_ticks(img, color)
    img = vignette(img, 110)
    img = grain(img, 8)
    return img

# ---- flag helpers ----------------------------------------------------------
def flag_panel(name, w, h):
    f = load(os.path.join(FL, name+".png"))
    return cover(f, w, h, 0.5, 0.5)

# ---------------------------------------------------------------------------
#  SCENE BUILDERS
# ---------------------------------------------------------------------------
def s_title_trophy(sub):
    img = base_canvas()
    src = grade(load(os.path.join(PH, "trophy.jpg")), color=0.9)
    bgf = cover(src, W, H, 0.5, 0.35).filter(ImageFilter.GaussianBlur(8))
    bgf = ImageEnhance.Brightness(bgf).enhance(0.62)
    img.paste(bgf, (0,0))
    img.paste(vgrad(W, H, 150, 230), (0,0), vgrad(W, H, 150, 230))
    # gold emblem at bottom
    em = load(os.path.join(A, "emblem2026.png")).convert("RGBA")
    em = em.resize((int(em.width*220/em.height), 220))
    img.paste(em, ((W-em.width)//2, 250), em)
    header(img, "History", 760, color=GOLD2, size=150, stroke=6)
    header(img, "Rewritten", 920, color=WHITE, size=150, stroke=6)
    subtitle(img, sub)
    return finish(img, GOLD)

def s_eight_winners(sub):
    img = base_canvas()
    img.paste(vgrad(W, H, 40, 120, color=(20,22,26)), (0,0),
              vgrad(W, H, 40, 120, color=(20,22,26)))
    tag(img, "Football's closed club", GREY, y=210)
    header(img, "The 8 Winners", 300, color=(150,156,165), size=96, stroke=4)
    teams = ["BRAZIL","GERMANY","ITALY","ARGENTINA",
             "FRANCE","URUGUAY","SPAIN","ENGLAND"]
    d = ImageDraw.Draw(img)
    fnt = bebas(74); y = 520
    for t in teams:
        draw_center(img, t, fnt, y, fill=(120,126,135), tracking=6)
        y += 118
    subtitle(img, sub)
    return finish(img, (90,94,100))

def _strip_panel(src_img, x, y, w, h, label, color, fx=0.5, fy=0.32):
    panel = cover(src_img, w, h, fx, fy)
    return panel

def s_grid5(sub, head, head_color, title_tag):
    """5 horizontal bands: each nation's star (or flag) + label."""
    img = base_canvas()
    rows = [
        ("Ecuador",     None,                 "ecuador",     "ECUADOR"),
        ("Japan",       "kubo.jpg",           "japan",       "JAPAN"),
        ("Morocco",     "hakimi.jpg",         "morocco",     "MOROCCO"),
        ("Colombia",    "james_celebrate.jpg","colombia",    "COLOMBIA"),
        ("Netherlands", "vandijk.jpg",        "netherlands", "NETHERLANDS"),
    ]
    top = 232; band_h = 236; gap = 6
    d = ImageDraw.Draw(img)
    for i,(nat, photo, flag, lbl) in enumerate(rows):
        y = top + i*(band_h+gap)
        if photo:
            src = grade(load(os.path.join(PH, photo)))
            band = cover(src, W, band_h, 0.5, 0.28)
        else:
            band = flag_panel(flag, W, band_h)
        img.paste(band, (0, y))
        # darken left side for label legibility
        ov = vgrad(W, band_h, 150, 150, color=(0,0,0))
        img.paste(ov, (0,y), ov)
        d.rectangle([0, y, 12, y+band_h], fill=NAT[flag]["a"])
        d.text((44, y+band_h//2-40), lbl, font=anton(58), fill=WHITE,
               stroke_width=4, stroke_fill=(0,0,0))
    bands_bottom = top + 5*(band_h+gap)
    # solid dark footer so the subtitle sits in clear space
    d.rectangle([0, bands_bottom, W, H], fill=BG)
    header(img, head, 66, color=head_color, size=92, stroke=4)
    subtitle(img, sub, y=1560)
    return finish(img, GOLD)

def s_single(photo, tagtxt, natkey, head, head_color, sub, fy=0.34,
             headsize=104, sub_label=None, sub_label_color=None):
    img = hero(os.path.join(PH, photo), fy=fy)
    if tagtxt: tag(img, tagtxt, NAT[natkey]["a"], y=120)
    header(img, head, 196, color=head_color, size=headsize, stroke=5,
           sub=sub_label, sub_color=sub_label_color)
    subtitle(img, sub)
    return finish(img, NAT[natkey]["a"])

def s_namecard(name, role, natkey, sub, club=None):
    """Styled nameplate for a player without a photo (national colours)."""
    img = base_canvas()
    c = NAT[natkey]
    # diagonal colour blocks
    big = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(big, "RGBA")
    d.polygon([(0,H),(0,H-560),(W,H-980),(W,H)], fill=c["a"]+(38,))
    d.polygon([(0,H),(0,H-300),(W,H-640),(W,H)], fill=c["b"]+(34,))
    img = Image.blend(img, big, 1.0)
    # flag chip top
    chip = flag_panel(natkey, 150, 100)
    cm = rounded_mask(150,100,12)
    img.paste(chip, ((W-150)//2, 360), cm)
    ImageDraw.Draw(img).rounded_rectangle([(W-150)//2,360,(W-150)//2+149,460],
                    radius=12, outline=WHITE, width=2)
    # big name
    parts = name.upper().split()
    if len(parts) >= 2:
        header(img, parts[0], 640, color=WHITE, size=120, stroke=5)
        header(img, " ".join(parts[1:]), 790, color=c["a"], size=140, stroke=5)
    else:
        header(img, name, 720, color=c["a"], size=150, stroke=5)
    draw_center(img, role.upper(), oswb(46), 1000, fill=GOLD, tracking=8)
    if club:
        draw_center(img, club.upper(), osw(38), 1064, fill=GREY, tracking=6)
    subtitle(img, sub)
    return finish(img, c["a"])

def s_split3(items, head, natkey, sub):
    """Three vertical columns (Endo | Kubo | Ueda)."""
    img = base_canvas()
    colw = (W - 2*6)//3
    xs = [0, colw+6, 2*(colw+6)]
    d = ImageDraw.Draw(img)
    for x,(photo,label) in zip(xs, items):
        src = grade(load(os.path.join(PH, photo)))
        col = cover(src, colw, H, 0.5, 0.30)
        img.paste(col, (x, 0))
    # readability gradients top+bottom
    img.paste(vgrad(W, 360, 220, 0), (0,0), vgrad(W, 360, 220, 0))
    img.paste(vgrad(W, 520, 0, 230), (0,H-520), vgrad(W, 520, 0, 230))
    for x,(photo,label) in zip(xs, items):
        d.text((x+colw//2 - d.textlength(label, font=anton(58))//2, H-300),
               label, font=anton(58), fill=WHITE, stroke_width=4,
               stroke_fill=(0,0,0))
    header(img, head, 110, color=WHITE, size=92, stroke=5)
    subtitle(img, sub)
    return finish(img, NAT[natkey]["a"])

def s_two_up(left, right, head, natkey, sub):
    """Two stacked hero photos (e.g. Bounou save + Hakimi wing)."""
    img = base_canvas()
    h2 = (H-6)//2
    for i,(photo, label, fy) in enumerate([left, right]):
        src = grade(load(os.path.join(PH, photo)))
        band = cover(src, W, h2, 0.5, fy)
        y = i*(h2+6)
        img.paste(band, (0, y))
        img.paste(vgrad(W, 260, 0, 200), (0, y+h2-260), vgrad(W,260,0,200))
        d = ImageDraw.Draw(img)
        d.text((50, y+h2-120), label, font=anton(56), fill=WHITE,
               stroke_width=4, stroke_fill=(0,0,0))
        d.rectangle([0, y, 12, y+h2], fill=NAT[natkey]["a"])
    header(img, head, 60, color=WHITE, size=84, stroke=4)
    subtitle(img, sub)
    return finish(img, NAT[natkey]["a"])

def s_outro_grid(sub):
    img = s_grid5(sub, "Who Makes History?", GOLD2, None)
    return img

def s_outro_cta(sub):
    img = base_canvas()
    src = grade(load(os.path.join(PH, "trophy.jpg")), color=0.9)
    bgf = cover(src, W, H, 0.5, 0.35).filter(ImageFilter.GaussianBlur(26))
    bgf = ImageEnhance.Brightness(bgf).enhance(0.4)
    img.paste(bgf, (0,0))
    img.paste(vgrad(W, H, 160, 220), (0,0), vgrad(W, H, 160, 220))
    d = ImageDraw.Draw(img)
    # subscribe button
    bw, bh = 560, 150
    bx, by = (W-bw)//2, 760
    d.rounded_rectangle([bx,by,bx+bw,by+bh], radius=30, fill=RED_HL)
    sw = d.textlength("SUBSCRIBE", font=anton(76))
    d.text((bx+(bw-sw)//2, by+26), "SUBSCRIBE", font=anton(76), fill=WHITE)
    # comment bubble
    cbw, cbh = 560, 150
    cx2, cy2 = (W-cbw)//2, 980
    d.rounded_rectangle([cx2,cy2,cx2+cbw,cy2+cbh], radius=30, outline=WHITE, width=5)
    cw = d.textlength("COMMENT", font=anton(70))
    d.text((cx2+(cbw-cw)//2, cy2+34), "COMMENT", font=anton(70), fill=WHITE)
    header(img, "Comment &", 470, color=WHITE, size=92, stroke=5)
    header(img, "Subscribe", 590, color=GOLD2, size=92, stroke=5)
    subtitle(img, sub)
    return finish(img, GOLD)

# ---------------------------------------------------------------------------
#  SCENE LIST  (durations sum ~= 92.92s; transition = xfade INTO this scene)
# ---------------------------------------------------------------------------
SCENES = [
 # --- SEG 1 : HOOK (16.5s) ---
 ("01_title",   3.8, "fade",      lambda: s_title_trophy(
    "The World Cup is here. Football history is about to be rewritten.")),
 ("02_winners", 4.6, "fadeblack", lambda: s_eight_winners(
    "Only eight nations have ever won the trophy. This year, the curse breaks.")),
 ("03_empires", 4.2, "slideleft", lambda: s_grid5(
    "Five rising empires are ready to storm the stage.",
    "5 New Empires", RED_HL, None)),
 ("04_watch",   3.9, "fade",      lambda: s_grid5(
    "Chasing their first-ever golden crown. Here is who to watch.",
    "5 New Empires", RED_HL, None)),
 # --- SEG 2 : ECUADOR (16.4s) ---
 ("05_ecu_flag",3.9, "slideleft", lambda: s_single_flag("ecuador",
    "Ecuador", "19-Game Unbeaten",
    "First, Ecuador — riding a remarkable nineteen-match unbeaten run.")),
 ("06_pacho",   3.4, "slideleft", lambda: s_namecard("Willian Pacho",
    "Champions League Winner", "ecuador",
    "A solid brick wall, led by Champions League winner Willian Pacho.",
    club="Paris Saint-Germain")),
 ("07_hincapie",3.3, "slideright",lambda: s_namecard("Piero Hincapie",
    "The Shield", "ecuador",
    "Alongside Arsenal's Piero Hincapie — tough, aggressive, relentless.",
    club="Arsenal")),
 ("08_caicedo", 3.4, "fade",      lambda: s_namecard("Moises Caicedo",
    "The Engine", "ecuador",
    "Shielded by Chelsea's Moises Caicedo, they are hard to break down.",
    club="Chelsea")),
 ("09_finish",  2.4, "fadeblack", lambda: s_textcard(
    "Finishing Hurdle", GREY, "ecuador",
    "Their one hurdle: clinical finishing in the final third.")),
 # --- SEG 3 : JAPAN (13.5s) ---
 ("10_jpn_press",4.0,"slideleft", lambda: s_single("kubo.jpg",
    "Japan", "japan", "Deadly High-Press", WHITE,
    "Next, Japan. Even without Mitoma and Minamino, their press stays deadly.",
    fy=0.30, headsize=100)),
 ("11_mitoma",  2.4, "fade",      lambda: s_single("mitoma.jpg",
    "Injured Star", "japan", "Mitoma Out", GREY,
    "Superstar Kaoru Mitoma misses out through injury.", fy=0.20, headsize=92)),
 ("12_jpn_trio",4.4, "slideleft", lambda: s_split3(
    [("endo.webp","ENDO"),("kubo.jpg","KUBO"),("ueda_portrait.jpg","UEDA")],
    "Endo · Kubo · Ueda", "japan",
    "Powered by Endo, creator Takefusa Kubo and top scorer Ayase Ueda.")),
 ("13_jpn_tac", 2.7, "fade",      lambda: s_single("ueda_action.jpg",
    "Japan", "japan", "A Tactical Nightmare", WHITE,
    "A disciplined squad that is a tactical nightmare for anyone.",
    fy=0.18, headsize=92)),
 # --- SEG 4 : MOROCCO (12.8s) ---
 ("14_mar_flag",3.4,"slideleft",  lambda: s_single_flag("morocco",
    "Morocco", "The Atlas Lions",
    "Third, Morocco. The Atlas Lions have been completely transformed.")),
 ("15_ouahbi",  3.2, "fade",      lambda: s_namecard("Mohamed Ouahbi",
    "U-20 World Champion", "morocco",
    "Under youth-champion coach Mohamed Ouahbi, a new era begins.",
    club="Head Coach")),
 ("16_morocco_keepers",3.6,"slideleft", lambda: s_two_up(
    ("bounou.jpg","BOUNOU", 0.30), ("hakimi.jpg","HAKIMI", 0.30),
    "Bounou & Hakimi", "morocco",
    "Yassine Bounou in goal, Achraf Hakimi flying down the right.")),
 ("17_morocco_attack",2.6,"fade", lambda: s_single("hakimi.jpg",
    "Wing Attack", "morocco", "Progressive Attack", (90,200,120),
    "A progressive wing attack ready to stun the world again.",
    fy=0.28, headsize=96)),
 # --- SEG 5 : COLOMBIA (11.9s) ---
 ("18_lorenzo", 3.5, "slideleft", lambda: s_single("lorenzo.webp",
    "Colombia", "colombia", "The Dark Horse", GOLD2,
    "Fourth, Colombia — the dark horse, on a legendary run under Nestor Lorenzo.",
    fy=0.30, headsize=104)),
 ("19_james",   4.4, "fade",      lambda: s_single("james_celebrate.jpg",
    "No. 10", "colombia", "James Rodriguez", WHITE,
    "The creative genius of James Rodriguez pulls every string.",
    fy=0.22, headsize=104)),
 ("20_diaz",    4.0, "slideright",lambda: s_namecard("Luis Diaz",
    "Electric Pace", "colombia",
    "And the electric pace of Luis Diaz brings elite momentum to North America.",
    club="Forward")),
 # --- SEG 6 : NETHERLANDS (12.9s) ---
 ("21_ned_curse",3.6,"fadeblack", lambda: s_single("vandijk.jpg",
    "Netherlands", "netherlands", "Break The Curse", (255,150,70),
    "Finally, the Netherlands — three-time runners-up, desperate to break the curse.",
    fy=0.16, headsize=96)),
 ("22_vandijk", 4.6, "fade",      lambda: s_single("vandijk.jpg",
    "The Captain", "netherlands", "Van Dijk", (255,140,40),
    "Captained by the towering Virgil van Dijk, the Oranje stand tall.",
    fy=0.14, headsize=120, sub_label="The Captain", sub_label_color=(255,150,70))),
 ("23_ned_quality",4.7,"slideleft", lambda: s_single_flag("netherlands",
    "Quality In Depth", "Eternal Glory",
    "A pragmatic side packed with quality, chasing their final shot at glory.")),
 # --- SEG 7 : OUTRO (8.9s) ---
 ("24_outro_grid",4.4,"fadeblack", lambda: s_outro_grid(
    "Only one question remains: who will make history?")),
 ("25_outro_cta", 4.5,"fade",      lambda: s_outro_cta(
    "Drop your champion in the comments and subscribe for daily coverage!")),
]

# ---- extra builders referenced above --------------------------------------
def s_single_flag(natkey, tagtxt, head, sub, head_color=None):
    """Hero built from a national flag (no player photo available)."""
    img = base_canvas()
    src = flag_panel(natkey, W, H)
    bgf = src.filter(ImageFilter.GaussianBlur(40))
    bgf = ImageEnhance.Brightness(bgf).enhance(0.5)
    img.paste(bgf, (0,0))
    img.paste(vgrad(W, H, 120, 210), (0,0), vgrad(W, H, 120, 210))
    # framed sharp flag
    fw, fh = 940, 620; top = 470
    card = cover(src, fw, fh, 0.5, 0.5)
    cx = (W-fw)//2
    img.paste(card, (cx, top), rounded_mask(fw, fh, 28))
    ImageDraw.Draw(img).rounded_rectangle([cx,top,cx+fw-1,top+fh-1],
                    radius=28, outline=WHITE, width=3)
    tag(img, tagtxt, NAT[natkey]["a"], y=170)
    header(img, head, 1180, color=head_color or NAT[natkey]["a"], size=104, stroke=5)
    subtitle(img, sub)
    return finish(img, NAT[natkey]["a"])

def s_textcard(head, head_color, natkey, sub):
    """Minimal grey statement card (e.g. 'Finishing Hurdle')."""
    img = base_canvas()
    c = NAT[natkey]
    img.paste(vgrad(W, H, 30, 110, color=(18,20,24)), (0,0),
              vgrad(W, H, 30, 110, color=(18,20,24)))
    d = ImageDraw.Draw(img, "RGBA")
    d.polygon([(0,H),(0,H-360),(W,H-700),(W,H)], fill=c["a"]+(26,))
    header(img, head, 820, color=head_color, size=128, stroke=5)
    draw_center(img, "THE ONLY QUESTION MARK", oswb(40), 990, fill=GREY, tracking=8)
    subtitle(img, sub)
    return finish(img, (90,94,100))

# ---------------------------------------------------------------------------
#  MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    manifest = []
    for idx, (sid, dur, trans, builder) in enumerate(SCENES):
        img = builder()
        assert img.size == (W, H), f"{sid} wrong size {img.size}"
        path = os.path.join(OUT, f"{sid}.png")
        img.save(path)
        manifest.append({"id": sid, "file": f"{sid}.png", "dur": dur,
                         "trans": trans})
        print(f"  rendered {sid:18s} {dur:4.1f}s  trans={trans}")
    total = sum(s["dur"] for s in manifest)
    json.dump({"scenes": manifest, "total": total},
              open(os.path.join(OUT, "manifest.json"), "w"), indent=2)
    print(f"TOTAL scene time: {total:.2f}s  ({len(manifest)} scenes)")
