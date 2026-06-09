#!/usr/bin/env python3
"""
30-second World Cup 2022 reel — paper-cut motion graphics
Argentina — FIFA World Cup Champions, Qatar 2022
"""
import os, math, numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import VideoClip

W, H, FPS = 1080, 1920, 30

# ── palette ─────────────────────────────────────────────────────────────────
CREAM        = (252, 248, 240)
ARG_BLUE     = (117, 170, 219)
ARG_BLUE_DEP = (43,  103, 161)
LIGHT_BLUE   = (116, 185, 255)
DARK_BLUE    = (10,   40,  80)
WHITE        = (255, 255, 255)
GOLD         = (255, 215,   0)
GOLD_DARK    = (184, 134,  11)
CONFETTI_CLR = [(255,80,80),(80,220,80),(80,80,255),(255,210,40),(255,80,200),(80,230,230)]

# ── helpers ──────────────────────────────────────────────────────────────────
def ei(t):          return t*t*(3-2*t)           # ease-in-out
def lp(a,b,t):      return a+(b-a)*t             # lerp

def paper_bg(w, h, color=CREAM):
    arr = np.full((h,w,3), color, dtype=np.uint8)
    noise = np.random.normal(0, 4, arr.shape).astype(np.int16)
    return Image.fromarray(np.clip(arr.astype(np.int16)+noise, 0, 255).astype(np.uint8))

def torn_edge(draw, y, width, color, up=False):
    pts = [(0, y)]
    x = 0
    rng = np.random.RandomState(int(y) % 9999)
    while x < width:
        x += rng.randint(20, 55)
        pts.append((min(x, width), y + rng.randint(-18, 18)))
    pts.append((width, y))
    oy = -50 if up else 50
    pts += [(width, y+oy), (0, y+oy)]
    draw.polygon(pts, fill=color)

def confetti(draw, w, h, frame, total, seed=42):
    rng = np.random.RandomState(seed)
    for i in range(70):
        col = CONFETTI_CLR[i % len(CONFETTI_CLR)]
        sx  = rng.randint(0, w)
        sy  = -rng.randint(0, h//2)
        spd = rng.uniform(0.7, 1.6)
        wob = rng.uniform(-35, 35)
        prog = (frame / max(total,1)) * spd
        cx_ = sx + wob * math.sin(prog * math.pi * 2)
        cy_ = sy + prog * h * 1.6
        if 0 <= cy_ <= h:
            sz = rng.randint(9, 22)
            draw.rectangle([cx_-sz//2, cy_-sz//4, cx_+sz//2, cy_+sz//4], fill=col)

def star(draw, cx, cy, r, color):
    pts = []
    for i in range(10):
        ang = math.pi/2 + i*math.pi/5
        rad = r if i%2==0 else r/2.5
        pts.append((cx+rad*math.cos(ang), cy+rad*math.sin(ang)))
    draw.polygon(pts, fill=color)

def font(size, bold=True):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def shadow_text(draw, xy, text, fnt, fill, shadow=(0,0,0), off=4, anchor="mm"):
    draw.text((xy[0]+off, xy[1]+off), text, font=fnt, fill=shadow, anchor=anchor)
    draw.text(xy, text, font=fnt, fill=fill, anchor=anchor)

def safe_rect(draw, coords, **kw):
    x0,y0,x1,y1 = coords
    if x1 > x0 and y1 > y0:
        draw.rectangle([x0,y0,x1,y1], **kw)

def safe_ellipse(draw, coords, **kw):
    x0,y0,x1,y1 = coords
    if x1 > x0 and y1 > y0:
        draw.ellipse([x0,y0,x1,y1], **kw)

def label_box(draw, cx, y, w2, h2, bg=ARG_BLUE_DEP, border=ARG_BLUE):
    safe_rect(draw, [cx-w2-5, y-h2-5, cx+w2+5, y+h2+5], fill=(20,40,80))
    safe_rect(draw, [cx-w2, y-h2, cx+w2, y+h2], fill=bg)
    safe_rect(draw, [cx-w2+8, y-h2+8, cx+w2-8, y+h2-8], fill=border)

# ── Scene 1 · Opening title  (0–6 s) ────────────────────────────────────────
def scene1(t, dur=6.0):
    p = t/dur
    img = paper_bg(W, H, CREAM)
    d   = ImageDraw.Draw(img)

    # layered paper sweeping up from bottom
    layers_col = [DARK_BLUE, ARG_BLUE_DEP, ARG_BLUE, LIGHT_BLUE, (215,235,255)]
    for i, col in enumerate(layers_col):
        lp_ = ei(min(1, max(0, p*5 - i*0.7)))
        if lp_ > 0:
            y0 = int(H*(1-lp_))
            d.rectangle([0, y0, W, H], fill=col)
            torn_edge(d, y0, W, col, up=True)

    # Argentine sun rays fan-out behind title
    sun_p = ei(min(1, max(0, p*2-0.5)))
    if sun_p > 0:
        cx, cy = W//2, H//2 - 60
        for ang_d in range(0, 360, 18):
            ang = math.radians(ang_d)
            r_out = int(lp(0, 340, sun_p))
            r_in  = int(lp(0,  50, sun_p))
            x1 = cx + r_in*math.cos(ang); y1 = cy + r_in*math.sin(ang)
            x2 = cx + r_out*math.cos(ang); y2 = cy + r_out*math.sin(ang)
            d.line([x1,y1,x2,y2], fill=(252,191,73), width=6)
        safe_ellipse(d, [cx-int(50*sun_p), cy-int(50*sun_p), cx+int(50*sun_p), cy+int(50*sun_p)],
                     fill=(252,200,80))

    # title box
    box_p = ei(min(1, max(0, p*2-0.1)))
    box_w = int(lp(0, 460, box_p))
    if box_w > 20:
        bx = W//2
        by = H//2 - 60
        d.rectangle([bx-box_w-6, by-76, bx+box_w+6, by+76], fill=(20,50,110))
        d.rectangle([bx-box_w,   by-70, bx+box_w,   by+70], fill=WHITE)
        if box_w > 80:
            shadow_text(d, (W//2, H//2-60), "ARGENTINA",
                        font(108), ARG_BLUE_DEP, shadow=ARG_BLUE, off=4)

    # subtitle slide-up
    sub_p = ei(min(1, max(0, p*3-1.2)))
    sub_y = int(lp(H//2+220, H//2+120, sub_p))
    if sub_p > 0.05:
        shadow_text(d, (W//2, sub_y),      "FIFA WORLD CUP 2022", font(52), WHITE, off=3)
        shadow_text(d, (W//2, sub_y+70),   "CHAMPIONS",           font(68), GOLD,  off=3)

    # 3 stars
    st_p = ei(min(1, max(0, p*3-0.8)))
    if st_p > 0:
        for i,sx in enumerate([-130, 0, 130]):
            star(d, W//2+sx, H//2-175, int(28*st_p), GOLD)

    if p > 0.55:
        confetti(d, W, H, int((p-0.55)/0.45*30), 30, seed=42)
    return np.array(img)

# ── Scene 2 · Trophy reveal  (6–12 s) ───────────────────────────────────────
def scene2(t, dur=6.0):
    p = t/dur
    img = paper_bg(W, H, (242,236,220))
    d   = ImageDraw.Draw(img)

    # background gradient layers
    for i, col in enumerate([ARG_BLUE_DEP, ARG_BLUE, LIGHT_BLUE]):
        lp_ = ei(min(1, max(0, p*3 - i*0.6)))
        if lp_ > 0:
            y0 = int(H*(1-lp_))
            d.rectangle([0,y0,W,H], fill=col)

    # trophy built layer-by-layer
    tr_p = ei(min(1, max(0, p*2-0.1)))
    cx   = W//2
    base_y = H//2 + 300

    if tr_p > 0:
        # base
        bw = int(220*tr_p); bh = int(55*tr_p)
        by = base_y - bh
        safe_rect(d, [cx-bw//2+10,by+10,cx+bw//2+10,by+bh+10], fill=(70,50,10))
        safe_rect(d, [cx-bw//2, by, cx+bw//2, by+bh], fill=GOLD_DARK)
        safe_rect(d, [cx-bw//2+10, by+8, cx+bw//2-10, by+bh-8], fill=GOLD)
        # mid plate
        pw = int(160*tr_p); ph = int(30*tr_p)
        py = by - ph
        safe_rect(d, [cx-pw//2+8,py+8,cx+pw//2+8,py+ph+8], fill=(70,50,10))
        safe_rect(d, [cx-pw//2,py,cx+pw//2,py+ph], fill=GOLD_DARK)
        # stem
        sw = int(52*tr_p); sh = int(180*tr_p)
        sy = py - sh
        safe_rect(d, [cx-sw//2+6,sy+6,cx+sw//2+6,py+6], fill=(70,50,10))
        safe_rect(d, [cx-sw//2,sy,cx+sw//2,py], fill=GOLD_DARK)
        safe_rect(d, [cx-sw//2+7,sy+7,cx+sw//2-7,py-7], fill=GOLD)
        # bowl
        bow_w = int(300*tr_p); bow_h = int(210*tr_p)
        bow_y = sy - bow_h + int(bow_h*0.25)
        safe_ellipse(d, [cx-bow_w//2+12,bow_y+12,cx+bow_w//2+12,bow_y+bow_h+12], fill=(70,50,10))
        safe_ellipse(d, [cx-bow_w//2, bow_y, cx+bow_w//2, bow_y+bow_h], fill=GOLD_DARK)
        safe_ellipse(d, [cx-bow_w//2+14,bow_y+14,cx+bow_w//2-14,bow_y+bow_h-14], fill=GOLD)
        safe_ellipse(d, [cx-bow_w//2+28,bow_y+22,cx-bow_w//4,bow_y+bow_h//3], fill=(255,245,160))
        # globe top
        glob_r = int(65*tr_p)
        glob_y = bow_y - glob_r*2
        safe_ellipse(d, [cx-glob_r,glob_y,cx+glob_r,glob_y+glob_r*2], fill=(30,90,195))
        safe_ellipse(d, [cx-glob_r+8,glob_y+8,cx+glob_r-8,glob_y+glob_r*2-8], fill=(60,130,230))
        safe_ellipse(d, [cx-glob_r+15,glob_y+15,cx-glob_r//2,glob_y+glob_r//2], fill=(100,170,255))

    # text labels
    txt_p = ei(min(1, max(0, p-0.55)*4))
    if txt_p > 0.05:
        ty = H//2 + 370 + int(lp(80,0,txt_p))
        label_box(d, W//2, ty, 420, 52)
        shadow_text(d, (W//2, ty), "THE GOLDEN TROPHY", font(48), GOLD, shadow=DARK_BLUE, off=3)
        label_box(d, W//2, ty+130, 380, 45)
        shadow_text(d, (W//2, ty+130), "QATAR 2022  ·  LUSAIL", font(40), WHITE, shadow=DARK_BLUE, off=3)

    confetti(d, W, H, int(p*30), 30, seed=111)
    return np.array(img)

# ── Scene 3 · Flag unfurl  (12–18 s) ────────────────────────────────────────
def scene3(t, dur=6.0):
    p = t/dur
    img = paper_bg(W, H, (232,242,255))
    d   = ImageDraw.Draw(img)

    d.rectangle([0,0,W,H], fill=(220,235,255))

    # flag paper layers unfurling left→right
    fl_p = ei(min(1, p*1.8))
    fw = W - 120; fh = int(fw*0.62)
    fx = 60; fy = H//2 - fh//2
    cw = int(fw*fl_p)

    if cw > 10:
        # shadow
        d.rectangle([fx+16,fy+16,fx+fw+16,fy+fh+16], fill=(160,170,200))
        sh = fh//3
        # top white stripe
        d.rectangle([fx,fy, fx+cw, fy+sh], fill=(248,248,252))
        # mid blue stripe
        d.rectangle([fx,fy+sh, fx+cw, fy+sh*2], fill=ARG_BLUE)
        # bottom white stripe
        d.rectangle([fx,fy+sh*2, fx+cw, fy+fh], fill=(248,248,252))
        # border
        d.rectangle([fx,fy,fx+cw,fy+fh], outline=ARG_BLUE_DEP, width=5)
        # horizontal stripe dividers
        d.line([fx,fy+sh,fx+cw,fy+sh], fill=(200,200,220), width=3)
        d.line([fx,fy+sh*2,fx+cw,fy+sh*2], fill=(200,200,220), width=3)

        # Sol de Mayo
        if fl_p > 0.65:
            sp = (fl_p-0.65)/0.35
            scx = fx + fw//2; scy = fy + sh + sh//2
            sr = int(58*sp)
            for ang_d in range(0,360,24):
                ang = math.radians(ang_d)
                rlen = 32 if ang_d%48==0 else 20
                x1=scx+(sr+4)*math.cos(ang); y1=scy+(sr+4)*math.sin(ang)
                x2=scx+(sr+rlen)*math.cos(ang); y2=scy+(sr+rlen)*math.sin(ang)
                d.line([x1,y1,x2,y2], fill=(252,191,73), width=6)
            safe_ellipse(d, [scx-sr,scy-sr,scx+sr,scy+sr], fill=(252,191,73))
            safe_ellipse(d, [scx-sr+9,scy-sr+9,scx+sr-9,scy+sr-9], fill=(255,205,85))
            # face
            if sp > 0.6:
                ey_y=scy-sr//4
                safe_ellipse(d, [scx-sr//3-6,ey_y-5,scx-sr//3+6,ey_y+5], fill=GOLD_DARK)
                safe_ellipse(d, [scx+sr//3-6,ey_y-5,scx+sr//3+6,ey_y+5], fill=GOLD_DARK)
                if scx+sr//4 > scx-sr//4 and scy+sr//4 > scy-sr//8:
                    d.arc([scx-sr//4,scy-sr//8,scx+sr//4,scy+sr//4], 20, 160, fill=GOLD_DARK, width=5)

    # "LA ALBICELESTE" header banner
    bx_p = ei(min(1, max(0, p-0.4)*3))
    if bx_p > 0.05:
        by1 = fy - 140
        label_box(d, W//2, by1+50, 440, 55, ARG_BLUE_DEP, ARG_BLUE)
        shadow_text(d, (W//2, by1+50), "⭐  LA ALBICELESTE  ⭐", font(42), GOLD, DARK_BLUE, 3)

        by2 = fy + fh + 80
        label_box(d, W//2, by2+50, 450, 55, DARK_BLUE, ARG_BLUE_DEP)
        shadow_text(d, (W//2, by2+50), "CAMPEONES DEL MUNDO", font(42), WHITE, DARK_BLUE, 3)

    confetti(d, W, H, int(p*30), 30, seed=222)
    return np.array(img)

# ── Scene 4 · Celebration  (18–24 s) ────────────────────────────────────────
def scene4(t, dur=6.0):
    p = t/dur
    img = paper_bg(W, H, (238,230,212))
    d   = ImageDraw.Draw(img)

    # stadium layers
    for i, col in enumerate([DARK_BLUE, ARG_BLUE_DEP, ARG_BLUE, (180,215,255)]):
        lp_ = ei(min(1, max(0, p*4-i*0.6)))
        if lp_ > 0:
            y0 = int(H*(1-lp_))
            d.rectangle([0,y0,W,H], fill=col)

    # player silhouettes (5 players)
    positions = [(W//2,H//2+20),(W//2-255,H//2+100),(W//2+255,H//2+100),
                 (W//2-150,H//2+230),(W//2+150,H//2+230)]
    for i,(px,py) in enumerate(positions):
        pp = ei(min(1, max(0, p*5 - i*0.5)))
        if pp > 0.02:
            jmp = int(math.sin(p*math.pi*3 + i*1.2)*38*pp)
            bw = int(68*pp); bh = int(175*pp); hr = int(34*pp)
            ay = py - jmp
            safe_ellipse(d, [px-bw, ay+bh-8, px+bw, ay+bh+8], fill=(40,60,110))
            # shirt
            safe_rect(d, [px-bw//2, ay-hr, px+bw//2, ay+bh-hr], fill=WHITE)
            sw = max(1, bw//4)
            safe_rect(d, [px-sw//2, ay-hr, px+sw//2, ay+bh-hr], fill=ARG_BLUE)
            # head
            safe_ellipse(d, [px-hr, ay-hr*3, px+hr, ay-hr], fill=(215,175,130))
            # arms raised (main player only)
            if i == 0:
                arm_len = int(100*pp)
                d.line([px, ay, px-arm_len, ay-arm_len//2], fill=WHITE, width=int(18*pp))
                d.line([px, ay, px+arm_len, ay-arm_len//2], fill=WHITE, width=int(18*pp))

    # centre player holds trophy
    tp = ei(min(1, max(0, p*2-0.1)))
    if tp > 0.1:
        tcx = W//2; tcy = H//2 - 230 - int(60*tp)
        ts = int(35*tp)
        safe_rect(d, [tcx-ts//3,tcy-ts*2,tcx+ts//3,tcy], fill=GOLD)
        safe_ellipse(d, [tcx-ts,tcy-ts*3,tcx+ts,tcy-ts*2], fill=GOLD)
        safe_rect(d, [tcx-ts//2,tcy,tcx+ts//2,tcy+ts//2], fill=GOLD_DARK)

    # CAMPEONES burst
    cbp = ei(min(1, max(0, p-0.45)*4))
    if cbp > 0.05:
        br = int(420*cbp)
        d.ellipse([W//2-br,H//8-br//2,W//2+br,H//8+br//2], fill=GOLD)
        shadow_text(d, (W//2, H//8),      "CAMPEONES!", font(96), WHITE,       DARK_BLUE,    off=4)
        shadow_text(d, (W//2, H//8+110),  "LIONEL MESSI", font(52), ARG_BLUE_DEP, GOLD,     off=3)
        shadow_text(d, (W//2, H//8+175),  "AND LA ALBICELESTE", font(36), DARK_BLUE, WHITE, off=2)

    confetti(d, W, H, int(p*30), 30, seed=333)
    return np.array(img)

# ── Scene 5 · Final card  (24–30 s) ─────────────────────────────────────────
def scene5(t, dur=6.0):
    p = t/dur
    img = paper_bg(W, H, DARK_BLUE)
    d   = ImageDraw.Draw(img)

    # dark-to-light background reveal
    for i,(col,delay) in enumerate([(DARK_BLUE,0),(ARG_BLUE_DEP,0.15),(ARG_BLUE,0.35)]):
        lp_ = ei(min(1, max(0, p-delay)*3))
        if lp_ > 0:
            y0 = int(H*(1-lp_))
            d.rectangle([0,y0,W,H], fill=col)

    # starfield
    rng = np.random.RandomState(888)
    st_p = ei(min(1, max(0, p-0.1)*3))
    if st_p > 0:
        for _ in range(90):
            sx=rng.randint(0,W); sy=rng.randint(0,H//2); ss=rng.randint(2,6)
            d.ellipse([sx-ss,sy-ss,sx+ss,sy+ss], fill=WHITE)

    # large trophy
    tr_p = ei(min(1, max(0, p-0.05)*2.5))
    if tr_p > 0.03:
        cx  = W//2; by  = H//2 + 320
        bw=int(240*tr_p); bh=int(55*tr_p)
        sw=int(55*tr_p);  sh=int(160*tr_p)
        bww=int(290*tr_p);bwh=int(200*tr_p)
        by_= by-bh
        # glow
        for g in range(4):
            gw=bw+g*18
            safe_rect(d, [cx-gw//2,by_-sh-bwh-g*12,cx+gw//2,by+bh], fill=(100+g*10,80,10))
        # base
        safe_rect(d, [cx-bw//2,by_,cx+bw//2,by], fill=GOLD_DARK)
        safe_rect(d, [cx-bw//2+10,by_+9,cx+bw//2-10,by-9], fill=GOLD)
        # stem
        safe_rect(d, [cx-sw//2,by_-sh,cx+sw//2,by_], fill=GOLD_DARK)
        safe_rect(d, [cx-sw//2+7,by_-sh+7,cx+sw//2-7,by_-7], fill=GOLD)
        # bowl
        bow_y=by_-sh-bwh+bwh//4
        safe_ellipse(d, [cx-bww//2+12,bow_y+12,cx+bww//2+12,bow_y+bwh+12], fill=(80,55,5))
        safe_ellipse(d, [cx-bww//2,bow_y,cx+bww//2,bow_y+bwh], fill=GOLD_DARK)
        safe_ellipse(d, [cx-bww//2+14,bow_y+14,cx+bww//2-14,bow_y+bwh-14], fill=GOLD)
        safe_ellipse(d, [cx-bww//2+28,bow_y+22,cx-bww//4,bow_y+bwh//3], fill=(255,248,170))
        # globe
        gr=int(65*tr_p); gy=bow_y-gr*2
        safe_ellipse(d, [cx-gr,gy,cx+gr,gy+gr*2], fill=(30,90,200))
        safe_ellipse(d, [cx-gr+8,gy+8,cx+gr-8,gy+gr*2-8], fill=(60,130,230))
        safe_ellipse(d, [cx-gr+14,gy+14,cx-gr//2,gy+gr//2], fill=(100,170,255))

    # text
    tx_p = ei(min(1, max(0, p-0.38)*4))
    if tx_p > 0.05:
        off = int(lp(90, 0, tx_p))

        # top banner
        ty = 150 + off
        label_box(d, W//2, ty+70, 460, 60)
        shadow_text(d, (W//2, ty+70), "FIFA WORLD CUP", font(56), GOLD, DARK_BLUE, 4)
        label_box(d, W//2, ty+170, 440, 55)
        shadow_text(d, (W//2, ty+170), "2022  ·  QATAR", font(52), WHITE, DARK_BLUE, 3)

        # 3 gold stars above title
        for si,sx in enumerate([-130,0,130]):
            star(d, W//2+sx, ty-30, int(30*tx_p), GOLD)

        # bottom banner
        by_t = H - 370 + off
        label_box(d, W//2, by_t+60, 480, 62, DARK_BLUE, ARG_BLUE_DEP)
        shadow_text(d, (W//2, by_t+60), "ARGENTINA", font(96), WHITE, ARG_BLUE, 4)
        label_box(d, W//2, by_t+170, 420, 52, ARG_BLUE_DEP, ARG_BLUE)
        shadow_text(d, (W//2, by_t+170), "WORLD CHAMPIONS", font(46), GOLD, DARK_BLUE, 3)

    confetti(d, W, H, int(p*30), 30, seed=555)
    return np.array(img)

# ── dispatcher ───────────────────────────────────────────────────────────────
SCENE_DUR = 6.0

def make_frame(t):
    if   t < SCENE_DUR*1: return scene1(t,                SCENE_DUR)
    elif t < SCENE_DUR*2: return scene2(t - SCENE_DUR,    SCENE_DUR)
    elif t < SCENE_DUR*3: return scene3(t - SCENE_DUR*2,  SCENE_DUR)
    elif t < SCENE_DUR*4: return scene4(t - SCENE_DUR*3,  SCENE_DUR)
    else:                  return scene5(t - SCENE_DUR*4,  SCENE_DUR)

# ── render ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    out = "/home/user/Claude-adn2/world_cup_2022_reel.mp4"
    print("Rendering 30-second World Cup 2022 paper-cut reel …")
    clip = VideoClip(make_frame, duration=30)
    clip.write_videofile(
        out, fps=FPS, codec="libx264", audio=False,
        logger="bar", preset="medium",
        ffmpeg_params=["-crf","18","-pix_fmt","yuv420p"]
    )
    print(f"\nDone → {out}")
