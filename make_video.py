#!/usr/bin/env python3
"""
Generate 10-scene World Cup 2026 Vox-style video using Pillow + ffmpeg.
Each scene = 10 frames at different animation stages → smooth fade-in via ffmpeg.
"""

import os, subprocess, shutil, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1920, 1080
FPS = 30
SCENE_SEC = 5
FRAMES_PER_SCENE = FPS * SCENE_SEC   # 150 frames

FRAMES_DIR = "/home/user/Claude-adn2/frames"
os.makedirs(FRAMES_DIR, exist_ok=True)

FONT_BOLD   = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
FONT_REG    = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
EMOJI_FONT  = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

IMG_DIR = "/home/user/Claude-adn2"

# --- colour palette ---
C_DARK    = (10, 10, 15)
C_VOX_Y   = (255, 222, 0)
C_WHITE   = (255, 255, 255)
C_DIM     = (120, 120, 130)
C_SPAIN_R = (198, 11, 30)
C_SPAIN_Y = (255, 196, 0)
C_CAPE_B  = (0, 56, 147)
C_CAPE_Y  = (247, 209, 22)

def font(size, bold=True):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)

def efont(size):
    return ImageFont.truetype(EMOJI_FONT, size)

def ease_in_out(t):
    """Smooth easing: 0→1"""
    return t * t * (3 - 2 * t)

def lerp(a, b, t):
    return a + (b - a) * t

def alpha_color(color, alpha):
    return (*color[:3], int(alpha * 255))

def draw_text_centered(draw, text, y, fnt, color, img_w=W):
    bbox = draw.textbbox((0, 0), text, font=fnt)
    tw = bbox[2] - bbox[0]
    x = (img_w - tw) // 2
    draw.text((x, y), text, font=fnt, fill=color)

def draw_text_left(draw, text, x, y, fnt, color):
    draw.text((x, y), text, font=fnt, fill=color)

def draw_rect_alpha(img, x1, y1, x2, y2, color, alpha):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rectangle([x1, y1, x2, y2], fill=(*color, int(alpha * 255)))
    return Image.alpha_composite(img.convert("RGBA"), overlay)

def pill_text(img, text, cx, cy, fnt, bg, fg, pad_x=30, pad_y=14):
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), text, font=fnt)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x1 = cx - tw//2 - pad_x
    y1 = cy - th//2 - pad_y
    x2 = cx + tw//2 + pad_x
    y2 = cy + th//2 + pad_y
    draw.rounded_rectangle([x1, y1, x2, y2], radius=30, fill=bg)
    draw.text((cx - tw//2, cy - th//2), text, font=fnt, fill=fg)

def load_photo(name, size=(W, H), crop=True):
    path = os.path.join(IMG_DIR, name)
    img = Image.open(path).convert("RGB")
    if crop:
        # Cover crop
        iw, ih = img.size
        scale = max(size[0]/iw, size[1]/ih)
        nw, nh = int(iw*scale), int(ih*scale)
        img = img.resize((nw, nh), Image.LANCZOS)
        left = (nw - size[0]) // 2
        top = (nh - size[1]) // 2
        img = img.crop((left, top, left+size[0], top+size[1]))
    return img

def gradient_bg(colors_stops, size=(W, H)):
    """Vertical gradient from list of (y_frac, color) tuples."""
    img = Image.new("RGB", size, colors_stops[0][1])
    draw = ImageDraw.Draw(img)
    for y in range(size[1]):
        t = y / size[1]
        for i in range(len(colors_stops) - 1):
            t0, c0 = colors_stops[i]
            t1, c1 = colors_stops[i+1]
            if t0 <= t <= t1:
                f = (t - t0) / (t1 - t0)
                r = int(lerp(c0[0], c1[0], f))
                g = int(lerp(c0[1], c1[1], f))
                b = int(lerp(c0[2], c1[2], f))
                draw.line([(0, y), (size[0], y)], fill=(r, g, b))
                break
    return img

def draw_bar(draw, x, y, w, h, fill_frac, bg_color, fill_color):
    draw.rounded_rectangle([x, y, x+w, y+h], radius=h//2, fill=bg_color)
    fw = max(int(w * fill_frac), h)
    draw.rounded_rectangle([x, y, x+fw, y+h], radius=h//2, fill=fill_color)

def vignette(img):
    vig = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(vig)
    for i in range(60):
        alpha = int(180 * (i / 60))
        d.rectangle([i, i, W-i, H-i], outline=alpha)
    vig = vig.filter(ImageFilter.GaussianBlur(40))
    black = Image.new("RGB", img.size, (0, 0, 0))
    img = img.convert("RGB")
    img.paste(black, mask=vig)
    return img

# =========================================================
# SCENE RENDERERS — each returns a PIL Image for frame `f`
# f goes 0 → FRAMES_PER_SCENE-1
# =========================================================

def t(f, delay_sec=0.0):
    """Normalised time 0→1 with optional delay, eased."""
    raw = max(0, f / FPS - delay_sec) / (SCENE_SEC - delay_sec)
    return ease_in_out(min(raw, 1.0))

def slide_y(f, delay_sec=0.0, dist=60):
    """Returns y-offset: starts at +dist, ends at 0."""
    return int(dist * (1 - t(f, delay_sec)))

def fade(f, delay_sec=0.0):
    return t(f, delay_sec)

# ---------- scene 1: Title ----------
def scene1(f):
    img = gradient_bg([(0, (5,5,10)), (0.5,(20,0,40)), (1,(5,5,10))])
    draw = ImageDraw.Draw(img)

    # grid
    for x in range(0, W, 60):
        draw.line([(x,0),(x,H)], fill=(255,222,0,10), width=1)
    for y in range(0, H, 60):
        draw.line([(0,y),(W,y)], fill=(255,222,0,10), width=1)

    # trophy emoji
    a1 = fade(f, 0.0)
    trophy_y = H//2 - 240 + slide_y(f, 0.0)
    eim = Image.new("RGBA", (200,200), (0,0,0,0))
    ed = ImageDraw.Draw(eim)
    try:
        ef = efont(120)
        ed.text((20, 20), "🏆", font=ef, embedded_color=True)
    except:
        ed.text((20, 60), "WC", font=font(80), fill=C_VOX_Y)
    eim.putalpha(Image.fromarray(__import__('numpy').full((200,200), int(a1*255), dtype='uint8')) if False else eim.getchannel('A').point(lambda x: int(x * a1)))
    img.paste(eim, (W//2-100, trophy_y), eim)

    # eyebrow
    a2 = fade(f, 0.8)
    ey = int(lerp(H//2-130, H//2-110, t(f, 0.8)))
    eyebrow = "THE STORY OF THE WORLD CUP"
    eb_font = font(22)
    bbox = draw.textbbox((0,0), eyebrow, font=eb_font)
    ex = (W - (bbox[2]-bbox[0])) // 2
    draw.text((ex, ey), eyebrow, font=eb_font, fill=(*C_VOX_Y, int(a2*255)))

    # WORLD CUP 2026
    a3 = fade(f, 1.0)
    scale = lerp(0.7, 1.0, t(f, 1.0))
    title_lines = [("WORLD", 120), ("CUP", 120), ("2026", 120)]
    base_y = H//2 - 60
    for i,(txt,sz) in enumerate(title_lines):
        tf = font(sz)
        bbox = draw.textbbox((0,0), txt, font=tf)
        tw = bbox[2]-bbox[0]
        tx = (W - tw) // 2
        color = C_VOX_Y if txt=="CUP" else C_WHITE
        draw.text((tx, base_y + i*130), txt, font=tf, fill=(*color, int(a3*255)))

    # subtitle
    a4 = fade(f, 1.4)
    sub = "When giants faced an island nation"
    sf = font(28, bold=False)
    bbox = draw.textbbox((0,0), sub, font=sf)
    sx = (W - (bbox[2]-bbox[0])) // 2
    draw.text((sx, H//2+330), sub, font=sf, fill=(*C_DIM, int(a4*255)))

    # FIFA 2026 badge top right
    a5 = fade(f, 1.8)
    badge = "FIFA 2026"
    bf = font(20)
    draw.rounded_rectangle([W-160, 20, W-20, 60], radius=4, outline=(*C_VOX_Y, int(a5*255)), width=2)
    bbox = draw.textbbox((0,0), badge, font=bf)
    draw.text((W-90-(bbox[2]-bbox[0])//2, 30), badge, font=bf, fill=(*C_VOX_Y, int(a5*255)))

    return img

# ---------- scene 2: Matchup ----------
def scene2(f):
    img = gradient_bg([(0,(13,13,13)),(1,(26,10,0))])
    draw = ImageDraw.Draw(img)

    # label
    a0 = fade(f, 1.3)
    label = "GROUP STAGE   ·   WORLD CUP 2026"
    lf = font(20)
    bbox = draw.textbbox((0,0), label, font=lf)
    draw.text(((W-(bbox[2]-bbox[0]))//2, 50), label, font=lf, fill=(*C_DIM, int(a0*255)))

    # Spain side
    a_l = fade(f, 0.3)
    ox = int((1-a_l)*(-150))
    # flag
    try:
        eim = Image.new("RGBA",(240,180),(0,0,0,0))
        ed=ImageDraw.Draw(eim)
        ef=efont(130)
        ed.text((20,10), "🇪🇸", font=ef, embedded_color=True)
        eim.putalpha(eim.getchannel('A').point(lambda x: int(x*a_l)))
        img.paste(eim, (W//2-500+ox, H//2-200), eim)
    except:
        draw.text((W//2-520+ox, H//2-200), "ESP", font=font(120), fill=(*C_SPAIN_R, int(a_l*255)))
    # SPAIN
    a_ln = fade(f, 0.6)
    ox2 = int((1-a_ln)*(-100))
    tf = font(72)
    draw.text((W//2-480+ox2, H//2+0), "SPAIN", font=tf, fill=(*C_WHITE, int(a_ln*255)))
    # tag
    a_lt = fade(f, 1.0)
    draw.text((W//2-430, H//2+90), "THE FAVORITES", font=font(22), fill=(*C_SPAIN_Y, int(a_lt*255)))

    # VS
    a_vs = fade(f, 0.8)
    scale_vs = lerp(0.6, 1.0, t(f, 0.8))
    tf_vs = font(100)
    bbox = draw.textbbox((0,0),"VS",font=tf_vs)
    vx = (W - (bbox[2]-bbox[0]))//2
    draw.text((vx, H//2-60), "VS", font=tf_vs, fill=(*C_VOX_Y, int(a_vs*255)))

    # Cape Verde side
    a_r = fade(f, 0.3)
    ox3 = int((1-a_r)*150)
    try:
        eim = Image.new("RGBA",(240,180),(0,0,0,0))
        ed=ImageDraw.Draw(eim)
        ef=efont(130)
        ed.text((20,10), "🇨🇻", font=ef, embedded_color=True)
        eim.putalpha(eim.getchannel('A').point(lambda x: int(x*a_r)))
        img.paste(eim, (W//2+220+ox3, H//2-200), eim)
    except:
        draw.text((W//2+220+ox3, H//2-200), "CPV", font=font(120), fill=(*C_CAPE_B, int(a_r*255)))
    # CAPE VERDE
    a_rn = fade(f, 0.6)
    ox4 = int((1-a_rn)*100)
    draw.text((W//2+200+ox4, H//2+0), "CAPE VERDE", font=font(48), fill=(*C_WHITE, int(a_rn*255)))
    # tag
    a_rt = fade(f, 1.0)
    draw.text((W//2+210, H//2+90), "THE UNDERDOGS", font=font(22), fill=(*C_CAPE_Y, int(a_rt*255)))

    # bottom line
    a_b = fade(f, 1.5)
    msg = "Nobody saw what was coming."
    mf = font(28, bold=False)
    bbox = draw.textbbox((0,0),msg,font=mf)
    draw.text(((W-(bbox[2]-bbox[0]))//2, H-120), msg, font=mf, fill=(*C_DIM, int(a_b*255)))

    return img

# ---------- scene 3: Spain Badge ----------
def scene3(f):
    img = gradient_bg([(0,(100,0,0)),(0.5,(40,0,0)),(1,(10,0,5))])
    draw = ImageDraw.Draw(img)

    # title
    a0 = fade(f, 0.2)
    sy0 = slide_y(f, 0.2)
    tf = font(52)
    draw.text((W//2-240, 80+sy0), "THE  ", font=tf, fill=(*C_WHITE, int(a0*255)))
    draw.text((W//2-90, 80+sy0), "POWERHOUSE", font=tf, fill=(*C_SPAIN_Y, int(a0*255)))

    # badge photo
    a1 = fade(f, 0.4)
    badge = load_photo("spain_badge.jpg", size=(380,380))
    # zoom effect
    zoom = lerp(0.9, 1.0, t(f, 0.4))
    bw = int(380*zoom)
    badge_z = badge.resize((bw, bw), Image.LANCZOS)
    bx = (bw-380)//2
    badge_z = badge_z.crop((bx, bx, bx+380, bx+380))
    # glow
    glow = Image.new("RGB", (400, 400), (255,196,0))
    img.paste(glow, (W//2-200, H//2-220))
    img.paste(badge_z, (W//2-190, H//2-210))

    # Overlay alpha
    overlay = Image.new("RGBA", img.size, (0,0,0,0))
    od = ImageDraw.Draw(overlay)
    od.rectangle([W//2-200, H//2-220, W//2+200, H//2+180], fill=(0,0,0,int((1-a1)*255)))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # stats
    stats = [("1","World Cup Title"), ("#2","FIFA Ranking"),("117","Years of Football")]
    sx_offsets = [W//2-580, W//2-100, W//2+380]
    for i,(num,lbl) in enumerate(stats):
        a_s = fade(f, 0.8 + i*0.2)
        sy = slide_y(f, 0.8 + i*0.2, 40)
        x = sx_offsets[i]
        draw.text((x, H//2+220+sy), num, font=font(86), fill=(*C_SPAIN_Y, int(a_s*255)))
        draw.text((x, H//2+320+sy), lbl.upper(), font=font(18, bold=False), fill=(*C_DIM, int(a_s*255)))

    return img

# ---------- scene 4: Cape Verde ----------
def scene4(f):
    img = gradient_bg([(0,(0,20,70)),(0.6,(0,10,40)),(1,(0,5,20))])
    draw = ImageDraw.Draw(img)

    # big flag
    a0 = fade(f, 0.2)
    try:
        eim = Image.new("RGBA",(280,220),(0,0,0,0))
        ed=ImageDraw.Draw(eim)
        ef=efont(160)
        ed.text((20,10), "🇨🇻", font=ef, embedded_color=True)
        eim.putalpha(eim.getchannel('A').point(lambda x: int(x*a0)))
        img.paste(eim, (W//2-140, 80), eim)
    except:
        draw.text((W//2-80, 80), "CPV", font=font(140), fill=(*C_CAPE_B, int(a0*255)))

    # CAPE VERDE
    a1 = fade(f, 0.5)
    ox = int((1-a1)*(-80))
    draw.text((W//2-560+ox, 300), "CAPE VERDE", font=font(120), fill=(*C_WHITE, int(a1*255)))

    # underdog line
    a2 = fade(f, 1.0)
    sy2 = slide_y(f, 1.0, 30)
    draw.text((W//2-340, 440+sy2), "THE TINY ISLAND NATION", font=font(36), fill=(*C_CAPE_Y, int(a2*255)))

    # fact pills
    pills = ["🌊 Atlantic Ocean Islands","👥 Pop. 600,000","⚽ FIFA Rank: #40","💪 Zero Pressure"]
    a3 = fade(f, 1.3)
    pill_y = 560
    pf = font(26)
    pill_colors = [(0,30,90),(0,40,110),(10,50,130),(20,60,150)]
    positions = [W//2-760, W//2-360, W//2+40, W//2+380]

    for i, (ptxt, pc) in enumerate(zip(pills, pill_colors)):
        # Draw pill background + text
        ef_small = font(22)
        bbox = draw.textbbox((0,0), ptxt, font=ef_small)
        pw = bbox[2]-bbox[0]+40
        ph = 50
        px = positions[i]
        draw.rounded_rectangle([px, pill_y, px+pw, pill_y+ph], radius=25,
                                fill=(*pc, int(a3*200)), outline=(*C_WHITE, int(a3*60)), width=1)
        draw.text((px+20, pill_y+10), ptxt, font=ef_small, fill=(*C_WHITE, int(a3*220)))

    return img

# ---------- scene 5: The Stage ----------
def scene5(f):
    img = Image.new("RGB", (W, H), (2, 13, 5))
    draw = ImageDraw.Draw(img)

    # pitch arc
    for i in range(5, 0, -1):
        alpha = int(30 - i*4)
        draw.arc([W//2-600-(i*10), H-300-(i*5), W//2+600+(i*10), H+300+(i*5)],
                 180, 360, fill=(255,255,255,alpha), width=2)

    # pitch lines
    draw.arc([W//2-580, H-290, W//2+580, H+290], 180, 360, fill=(255,255,255,20), width=2)
    draw.line([(W//2, H-290),(W//2, H)], fill=(255,255,255,20), width=2)

    # stadium icon
    a0 = fade(f, 0.2)
    try:
        eim = Image.new("RGBA",(200,180),(0,0,0,0))
        ed=ImageDraw.Draw(eim)
        ed.text((0,0), "🏟️", font=efont(120), embedded_color=True)
        eim.putalpha(eim.getchannel('A').point(lambda x: int(x*a0)))
        img.paste(eim, (W//2-100, 100), eim)
    except:
        pass

    # LOCATION
    a1 = fade(f, 0.5)
    loc = "UNITED STATES   ·   2026"
    lf = font(24)
    bbox = draw.textbbox((0,0),loc,font=lf)
    draw.text(((W-(bbox[2]-bbox[0]))//2, 290), loc, font=lf, fill=(50,200,50,int(a1*200)))

    # THE STAGE IS SET
    a2 = fade(f, 0.7)
    sy2 = slide_y(f, 0.7, 50)
    lines = [("THE", 100), ("STAGE", 140), ("IS SET", 100)]
    base_y = 340
    for i,(ln,sz) in enumerate(lines):
        lnf = font(sz)
        bbox = draw.textbbox((0,0),ln,font=lnf)
        lx = (W-(bbox[2]-bbox[0]))//2
        color = (50,200,50) if ln=="STAGE" else C_WHITE
        draw.text((lx, base_y+i*150+sy2), ln, font=lnf, fill=(*color, int(a2*255)))

    # date
    a3 = fade(f, 1.2)
    dt = "GROUP STAGE  ·  90 MINUTES"
    df = font(26, bold=False)
    bbox = draw.textbbox((0,0),dt,font=df)
    draw.text(((W-(bbox[2]-bbox[0]))//2, H-140), dt, font=df, fill=(*C_DIM, int(a3*255)))

    # crowd dots
    a4 = fade(f, 1.5)
    import random; random.seed(42)
    for i in range(80):
        dx = random.randint(W//2-350, W//2+350)
        dy = random.randint(H-100, H-30)
        dot_a = int(a4 * 255 * (0.3 + 0.7*random.random()))
        col = C_VOX_Y if i%2==0 else C_WHITE
        draw.ellipse([dx-4, dy-4, dx+4, dy+4], fill=(*col, dot_a))

    return img

# ---------- scene 6: Spain Attacks ----------
def scene6(f):
    photo = load_photo("match_action.jpg")
    # Ken Burns: slight zoom in
    zoom = lerp(1.0, 1.08, f/FRAMES_PER_SCENE)
    zw = int(W*zoom)
    zh = int(H*zoom)
    photo_z = photo.resize((zw, zh), Image.LANCZOS)
    ox = (zw-W)//2; oy = (zh-H)//2
    photo_z = photo_z.crop((ox, oy, ox+W, oy+H))
    # darken
    dark = Image.new("RGB", (W,H), (0,0,0))
    img = Image.blend(photo_z, dark, 0.72).convert("RGBA")

    overlay = Image.new("RGBA",(W,H),(0,0,0,0))
    draw = ImageDraw.Draw(overlay)

    # gradient bottom overlay
    for y in range(H//2, H):
        t_grad = (y - H//2) / (H//2)
        draw.line([(0,y),(W,y)], fill=(10,10,10,int(t_grad*220)))

    img = Image.alpha_composite(img, overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # KICKOFF label
    a0 = fade(f, 0.2)
    k = "⚽ KICKOFF"
    kf = font(26)
    bbox = draw.textbbox((0,0),k,font=kf)
    draw.text(((W-(bbox[2]-bbox[0]))//2, 220), k, font=kf, fill=(*C_VOX_Y, int(a0*255)))

    # SPAIN ATTACKS. & ATTACKS.
    lines = [("SPAIN", C_WHITE), ("ATTACKS.", C_VOX_Y), ("& ATTACKS.", C_WHITE)]
    base_y = 290
    for i,(ln,col) in enumerate(lines):
        a = fade(f, 0.5+i*0.25)
        sy = slide_y(f, 0.5+i*0.25, 40)
        tf = font(120 if i<2 else 90)
        bbox = draw.textbbox((0,0),ln,font=tf)
        tx = (W-(bbox[2]-bbox[0]))//2
        draw.text((tx, base_y+i*140+sy), ln, font=tf, fill=(*col, int(a*255)))

    # stat pill
    a3 = fade(f, 1.0)
    stat_txt = "70%+ BALL POSSESSION"
    sf = font(28)
    bbox = draw.textbbox((0,0),stat_txt,font=sf)
    sw = bbox[2]-bbox[0]+40
    sx = (W-sw)//2
    draw.rounded_rectangle([sx, H-200, sx+sw, H-145], radius=6, fill=(*C_SPAIN_R, int(a3*220)))
    draw.text((sx+20, H-198), stat_txt, font=sf, fill=(*C_WHITE, int(a3*255)))

    # sub text
    a4 = fade(f, 1.2)
    draw.text((W//2-380, H-130), "The pressure was relentless. But Cape Verde held.", font=font(26,bold=False), fill=(*C_DIM, int(a4*255)))

    return img

# ---------- scene 7: Vozinha Intro ----------
def scene7(f):
    img = Image.new("RGB",(W,H),(8,8,15))
    draw = ImageDraw.Draw(img)

    # gradient overlay left side
    for x in range(W):
        t_grad = x/W
        alpha = int(lerp(200, 0, t_grad))
        draw.line([(x,0),(x,H)], fill=(0,30,90,alpha))

    # photo — slide from left
    a0 = fade(f, 0.3)
    photo = load_photo("vozinha_portrait.jpg", size=(500,700))
    # border glow
    border = Image.new("RGB",(510,710),(0,56,147))
    img.paste(border, (70, H//2-365))
    img_rgba = img.convert("RGBA")
    photo_rgba = photo.convert("RGBA")
    photo_mask = Image.new("L", (500,700), int(a0*255))
    ox_slide = int((1-a0)*(-200))
    img_rgba.paste(photo_rgba, (75+ox_slide, H//2-360), photo_mask)
    img = img_rgba.convert("RGB")
    draw = ImageDraw.Draw(img)

    # rating badge
    a_r = fade(f, 1.2)
    draw.rounded_rectangle([490, H//2+240, 640, H//2+320], radius=14,
                            fill=(26,26,26), outline=(*C_VOX_Y, int(a_r*255)), width=2)
    draw.text((510, H//2+248), "7.5", font=font(48), fill=(*C_VOX_Y, int(a_r*255)))
    draw.text((510, H//2+298), "MATCH RATING", font=font(16, bold=False), fill=(*C_DIM, int(a_r*255)))

    # info right side
    px = 700
    # "1" ghost number
    a_ghost = fade(f, 0.2)
    draw.text((W-240, 80), "1", font=font(280), fill=(*C_WHITE, int(a_ghost*20)))

    # position tag
    a1 = fade(f, 0.5)
    draw.text((px, 200), "🧤 GOALKEEPER  ·  CAPE VERDE", font=font(26), fill=(*C_CAPE_Y, int(a1*255)))

    # VOZINHA
    a2 = fade(f, 0.7)
    ox2 = int((1-a2)*120)
    draw.text((px+ox2, 260), "VOZINHA", font=font(140), fill=(*C_WHITE, int(a2*255)))

    # full name
    a3 = fade(f, 1.0)
    draw.text((px, 410), "Josimar Vozinha   ·   #1", font=font(28, bold=False), fill=(*C_DIM, int(a3*255)))

    # attr bars
    attrs = [("Reflexes", 0.95, 95), ("Aerial",   0.88, 88), ("Presence", 0.91, 91)]
    bar_y = 480
    for i,(lbl, frac, val) in enumerate(attrs):
        a_b = fade(f, 1.1+i*0.2)
        sy_b = slide_y(f, 1.1+i*0.2, 20)
        # label
        draw.text((px, bar_y+i*80+sy_b), lbl.upper(), font=font(18,bold=False), fill=(*C_DIM, int(a_b*255)))
        # bar
        bar_w = 400
        draw_bar(draw, px, bar_y+i*80+32+sy_b, bar_w, 10,
                 frac*a_b, (40,40,50), C_VOX_Y)
        # value
        draw.text((px+bar_w+18, bar_y+i*80+20+sy_b), str(val), font=font(28), fill=(*C_WHITE, int(a_b*255)))

    return img

# ---------- scene 8: The Saves ----------
def scene8(f):
    photo = load_photo("vozinha_save.jpg")
    zoom = lerp(1.0, 1.07, f/FRAMES_PER_SCENE)
    zw = int(W*zoom); zh = int(H*zoom)
    photo_z = photo.resize((zw, zh), Image.LANCZOS)
    ox = (zw-W)//2; oy = (zh-H)//2
    photo_z = photo_z.crop((ox, oy, ox+W, oy+H))
    dark = Image.new("RGB",(W,H),(0,0,0))
    img = Image.blend(photo_z, dark, 0.75)
    draw = ImageDraw.Draw(img)

    # left gradient
    for x in range(800):
        alpha = int(lerp(240, 0, x/800))
        draw.line([(x,0),(x,H)], fill=(6,12,16,alpha))

    # section label
    a0 = fade(f, 0.2)
    draw.text((80, 160), "🧤 MAN OF THE MATCH", font=font(28), fill=(*C_VOX_Y, int(a0*255)))

    # SAVE AFTER SAVE.
    lines = [("SAVE", C_WHITE), ("AFTER", C_WHITE), ("SAVE.", C_VOX_Y)]
    base_y = 220
    for i,(ln,col) in enumerate(lines):
        a = fade(f, 0.4+i*0.2)
        ox_s = int((1-a)*(-60))
        draw.text((80+ox_s, base_y+i*150), ln, font=font(130), fill=(*col, int(a*255)))

    # stat cards
    stats = [("8+","Saves Made"),("0","Goals Conceded"),("3","Big Stops"),("7.5","Player Rating")]
    cols2 = 2
    card_w, card_h = 260, 130
    start_x, start_y = 80, 700
    for i,(num,lbl) in enumerate(stats):
        a_c = fade(f, 0.8+i*0.2)
        sy_c = slide_y(f, 0.8+i*0.2, 30)
        cx = start_x + (i%cols2)*(card_w+20)
        cy = start_y + (i//cols2)*(card_h+16) + sy_c
        draw.rounded_rectangle([cx, cy, cx+card_w, cy+card_h], radius=12,
                                fill=(255,255,255,int(a_c*18)), outline=(255,255,255,int(a_c*40)), width=1)
        draw.text((cx+20, cy+14), num, font=font(62), fill=(*C_VOX_Y, int(a_c*255)))
        draw.text((cx+20, cy+88), lbl.upper(), font=font(18,bold=False), fill=(*C_DIM, int(a_c*255)))

    return img

# ---------- scene 9: Full Time ----------
def scene9(f):
    img = Image.new("RGB",(W,H),(5,5,5))
    draw = ImageDraw.Draw(img)

    # diagonal color split
    overlay = Image.new("RGBA",(W,H),(0,0,0,0))
    od = ImageDraw.Draw(overlay)
    # Spain left slash
    od.polygon([(0,0),(W//2-80,0),(W//2+80,H),(0,H)], fill=(*C_SPAIN_R, 38))
    # Cape Verde right slash
    od.polygon([(W//2-80,0),(W,0),(W,H),(W//2+80,H)], fill=(*C_CAPE_B, 38))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # FULL TIME label
    a0 = fade(f, 0.2)
    ft = "FULL TIME  ·  WORLD CUP 2026"
    ff = font(26)
    bbox = draw.textbbox((0,0),ft,font=ff)
    draw.text(((W-(bbox[2]-bbox[0]))//2, 60), ft, font=ff, fill=(*C_DIM, int(a0*255)))

    # Flags
    flag_y = H//2 - 160
    for emoji, slide_dir, x_pos, a_start in [("🇪🇸",-1, W//2-640, 0.5),("🇨🇻",1, W//2+400, 0.5)]:
        a = fade(f, a_start)
        ox = int((1-a)*slide_dir*150)
        try:
            eim = Image.new("RGBA",(200,160),(0,0,0,0))
            ed=ImageDraw.Draw(eim)
            ed.text((10,0), emoji, font=efont(120), embedded_color=True)
            eim.putalpha(eim.getchannel('A').point(lambda x: int(x*a)))
            img.paste(eim, (x_pos+ox, flag_y), eim)
        except:
            pass

    # 0 — 0 score
    a1 = fade(f, 0.8)
    scale1 = lerp(0.5, 1.0, t(f, 0.8))
    score = "0"
    dash = "—"
    score_zero = "0"
    sf = font(280)
    df_small = font(160)
    bbox_s = draw.textbbox((0,0),score,font=sf)
    sw = bbox_s[2]-bbox_s[0]
    bbox_d = draw.textbbox((0,0),dash,font=df_small)
    dw = bbox_d[2]-bbox_d[0]
    total_w = sw*2 + dw + 60
    base_x = (W-total_w)//2
    base_y = H//2 - 160
    draw.text((base_x, base_y), "0", font=sf, fill=(*C_WHITE, int(a1*255)))
    draw.text((base_x + sw + 20, base_y+60), "—", font=df_small, fill=(*C_DIM, int(a1*200)))
    draw.text((base_x + sw + dw + 60, base_y), "0", font=sf, fill=(*C_WHITE, int(a1*255)))

    # team names
    a2 = fade(f, 1.3)
    nf = font(28)
    draw.text((W//2-560, H//2+170), "SPAIN", font=nf, fill=(*C_DIM, int(a2*255)))
    draw.text((W//2+340, H//2+170), "CAPE VERDE", font=nf, fill=(*C_DIM, int(a2*255)))

    # shock line
    a3 = fade(f, 1.6)
    scale3 = lerp(0.7, 1.0, t(f, 1.6))
    shock = "🌍 THE WORLD STOOD STILL."
    shf = font(44)
    bbox = draw.textbbox((0,0),shock,font=shf)
    sx = (W-(bbox[2]-bbox[0]))//2
    draw.text((sx, H//2+240), shock, font=shf, fill=(*C_VOX_Y, int(a3*255)))

    return img

# ---------- scene 10: Legend ----------
def scene10(f):
    img = gradient_bg([(0,(20,14,0)),(0.5,(14,10,0)),(1,(6,4,0))])
    draw = ImageDraw.Draw(img)

    # pulsing rings
    ring_alpha = int(abs(math.sin(f/FPS * math.pi))*60 + 20)
    for r in [350, 480, 610]:
        draw.ellipse([W//2-r, H//2-r, W//2+r, H//2+r],
                     outline=(*C_VOX_Y, ring_alpha), width=1)

    # stars
    a0 = fade(f, 0.3)
    stars = "★  ★  ★"
    sf = font(50)
    bbox = draw.textbbox((0,0),stars,font=sf)
    draw.text(((W-(bbox[2]-bbox[0]))//2, 80), stars, font=sf, fill=(*C_VOX_Y, int(a0*255)))

    # THE WALL OF THE ATLANTIC
    a1 = fade(f, 0.5)
    sy1 = slide_y(f, 0.5, 30)
    legend = "THE WALL OF THE ATLANTIC"
    lf = font(34)
    bbox = draw.textbbox((0,0),legend,font=lf)
    draw.text(((W-(bbox[2]-bbox[0]))//2, 180+sy1), legend, font=lf, fill=(*C_VOX_Y, int(a1*255)))

    # VOZ / INHA
    a2 = fade(f, 0.8)
    scale2 = lerp(0.6, 1.0, t(f, 0.8))
    name1 = "VOZ"
    name2 = "INHA"
    nf = font(220)
    bbox1 = draw.textbbox((0,0),name1,font=nf)
    bbox2 = draw.textbbox((0,0),name2,font=nf)
    total = (bbox1[2]-bbox1[0]) + (bbox2[2]-bbox2[0])
    nx = (W-total)//2
    draw.text((nx, 230), name1, font=nf, fill=(*C_WHITE, int(a2*255)))
    draw.text((nx + bbox1[2]-bbox1[0], 230), name2, font=nf, fill=(*C_VOX_Y, int(a2*255)))

    # tagline
    a3 = fade(f, 1.3)
    sy3 = slide_y(f, 1.3, 25)
    tagline = "He held the line.  He made history."
    tf = font(34, bold=False)
    bbox = draw.textbbox((0,0),tagline,font=tf)
    draw.text(((W-(bbox[2]-bbox[0]))//2, 530+sy3), tagline, font=tf, fill=(*C_DIM, int(a3*255)))

    # recap badge
    a4 = fade(f, 1.6)
    rx1 = W//2-280; rx2 = W//2+280; ry1 = 600; ry2 = 680
    draw.rounded_rectangle([rx1,ry1,rx2,ry2], radius=40,
                            fill=(255,255,255,int(a4*15)), outline=(255,255,255,int(a4*50)), width=1)
    try:
        eim1 = Image.new("RGBA",(90,70),(0,0,0,0))
        ImageDraw.Draw(eim1).text((0,0), "🇪🇸", font=efont(60), embedded_color=True)
        eim1.putalpha(eim1.getchannel('A').point(lambda x: int(x*a4)))
        img.paste(eim1, (rx1+30, ry1+5), eim1)
        eim2 = Image.new("RGBA",(90,70),(0,0,0,0))
        ImageDraw.Draw(eim2).text((0,0), "🇨🇻", font=efont(60), embedded_color=True)
        eim2.putalpha(eim2.getchannel('A').point(lambda x: int(x*a4)))
        img.paste(eim2, (rx2-110, ry1+5), eim2)
    except:
        pass
    recap_score = "0  —  0"
    rsf = font(52)
    bbox = draw.textbbox((0,0),recap_score,font=rsf)
    draw.text(((W-(bbox[2]-bbox[0]))//2, ry1+15), recap_score, font=rsf, fill=(*C_VOX_Y, int(a4*255)))

    # final tag
    a5 = fade(f, 2.0)
    ft = "WORLD CUP 2026  ·  THE GIANT KILLER"
    ftf = font(22, bold=False)
    bbox = draw.textbbox((0,0),ft,font=ftf)
    draw.text(((W-(bbox[2]-bbox[0]))//2, 720), ft, font=ftf, fill=(*C_DIM, int(a5*180)))

    return img

SCENES = [scene1, scene2, scene3, scene4, scene5,
          scene6, scene7, scene8, scene9, scene10]

print(f"Generating {len(SCENES)*FRAMES_PER_SCENE} frames at {W}x{H}...")
frame_idx = 0

# fade between scenes: last 15 frames dark → first 15 frames dark
FADE_FRAMES = 15

for s_idx, scene_fn in enumerate(SCENES):
    print(f"  Scene {s_idx+1}/10 ...", flush=True)
    for f in range(FRAMES_PER_SCENE):
        img = scene_fn(f)
        img = vignette(img)

        # fade out last FADE_FRAMES of each scene (except last)
        if s_idx < len(SCENES)-1 and f >= FRAMES_PER_SCENE - FADE_FRAMES:
            dark_alpha = (f - (FRAMES_PER_SCENE - FADE_FRAMES)) / FADE_FRAMES
            dark = Image.new("RGB",(W,H),(0,0,0))
            img = Image.blend(img, dark, dark_alpha)

        # fade in first FADE_FRAMES of each scene (except first)
        if s_idx > 0 and f < FADE_FRAMES:
            dark_alpha = 1.0 - f/FADE_FRAMES
            dark = Image.new("RGB",(W,H),(0,0,0))
            img = Image.blend(img, dark, dark_alpha)

        img.save(f"{FRAMES_DIR}/frame_{frame_idx:05d}.png")
        frame_idx += 1

print(f"Done! {frame_idx} frames saved to {FRAMES_DIR}/")
