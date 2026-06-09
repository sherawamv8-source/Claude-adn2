#!/usr/bin/env python3
"""Build a muted ranking edit from 5 football clips (PIL text + ffmpeg overlay)."""

import subprocess
import os
from PIL import Image, ImageDraw, ImageFont

FFMPEG = "/usr/local/lib/python3.11/dist-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
CLIPS_DIR = "/root/.claude/uploads/11a90f4e-6d19-5996-9518-7ea2eb8b4415"
OUTPUT = "/home/user/Claude-adn2/ranking_edit.mp4"
FONT_PATH = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
TMP = "/tmp/ranking_parts"
os.makedirs(TMP, exist_ok=True)

# Ranking: (rank, clip_prefix, label_line1, label_line2)
RANKING = [
    (5, "d0714e1a", "PASSION FROM",        "PIERO HINCAPIE"),
    (4, "d84728f7", "WHAT A TACKLE",       "PACHO / PSG"),
    (3, "5eba6f8f", "LUIS DIAZ",           "NUTMEG KING"),
    (2, "59616c29", "JAPAN FANS",          "TOP OF GROUP E"),
    (1, "f31b49c2", "STOPPAGE TIME",       "WINNER"),
]

W, H = 1080, 1920
GOLD  = (255, 215,   0, 255)
WHITE = (255, 255, 255, 255)
BLACK = (  0,   0,   0, 255)
DARK  = ( 17,  17,  17, 255)

def load_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()

def centered_text(draw, text, y, font, color, shadow=True):
    """Draw text centered at y with optional drop shadow."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    if shadow:
        draw.text((x + 4, y + 4), text, font=font, fill=(0, 0, 0, 200))
    draw.text((x, y), text, font=font, fill=color)

def make_rank_card_png(rank, line1, line2, out_path):
    img = Image.new("RGBA", (W, H), DARK)
    draw = ImageDraw.Draw(img)

    # Decorative horizontal bars
    draw.rectangle([80, 550, W - 80, 558], fill=(255, 215, 0, 200))
    draw.rectangle([80, 920, W - 80, 928], fill=(255, 215, 0, 200))

    # Big rank number
    font_rank = load_font(300)
    centered_text(draw, f"#{rank}", 580, font_rank, WHITE)

    # Label lines
    font_label = load_font(85)
    centered_text(draw, line1, 940,  font_label, GOLD)
    centered_text(draw, line2, 1040, font_label, GOLD)

    img.convert("RGB").save(out_path)
    print(f"  Card #{rank} PNG created.")

def make_card_video(png_path, out_path, duration=2.2):
    """Loop a PNG image into a short video."""
    run([
        FFMPEG, "-y",
        "-loop", "1", "-framerate", "30",
        "-i", png_path,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-an",
        out_path
    ])

def make_badge_png(rank, out_path, badge_w=260, badge_h=155):
    """Small '#N' badge for top-left corner of the clip."""
    img = Image.new("RGBA", (badge_w, badge_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Semi-transparent dark background
    draw.rounded_rectangle([0, 0, badge_w - 1, badge_h - 1],
                            radius=20, fill=(0, 0, 0, 175))
    font = load_font(110)
    bbox = draw.textbbox((0, 0), f"#{rank}", font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (badge_w - tw) // 2
    y = (badge_h - th) // 2 - 8
    draw.text((x + 3, y + 3), f"#{rank}", font=font, fill=(0, 0, 0, 200))
    draw.text((x, y), f"#{rank}", font=font, fill=WHITE)
    img.save(out_path)

def process_clip(clip_path, rank, out_path):
    """Mute clip + overlay rank badge at top-left."""
    badge_png = os.path.join(TMP, f"badge_{rank}.png")
    make_badge_png(rank, badge_png)
    run([
        FFMPEG, "-y",
        "-i", clip_path,
        "-i", badge_png,
        "-filter_complex",
        "[0:v]scale=1080:1920,fps=30[base];[1:v]scale=260:155[badge];[base][badge]overlay=40:40",
        "-an",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        out_path
    ])
    print(f"  Clip #{rank} processed.")

def find_clip(prefix):
    for f in os.listdir(CLIPS_DIR):
        if f.startswith(prefix) and f.endswith(".mp4"):
            return os.path.join(CLIPS_DIR, f)
    raise FileNotFoundError(f"No clip with prefix {prefix}")

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("STDERR:", r.stderr[-800:])
        raise RuntimeError(f"ffmpeg failed on: {os.path.basename(cmd[-1])}")

# ── Main ─────────────────────────────────────────────────────────────────────
parts = []
print("Building ranking edit parts...")
for rank, prefix, line1, line2 in RANKING:
    card_png  = os.path.join(TMP, f"card_{rank}.png")
    card_vid  = os.path.join(TMP, f"card_{rank}.mp4")
    clip_out  = os.path.join(TMP, f"clip_{rank}.mp4")

    make_rank_card_png(rank, line1, line2, card_png)
    make_card_video(card_png, card_vid)
    process_clip(find_clip(prefix), rank, clip_out)

    parts.append(card_vid)
    parts.append(clip_out)

print("Concatenating all segments...")
concat_list = os.path.join(TMP, "concat.txt")
with open(concat_list, "w") as f:
    for p in parts:
        f.write(f"file '{p}'\n")

run([
    FFMPEG, "-y",
    "-f", "concat", "-safe", "0",
    "-i", concat_list,
    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
    "-pix_fmt", "yuv420p",
    "-an",
    OUTPUT
])
print(f"\nDone! Output: {OUTPUT}")
size_mb = os.path.getsize(OUTPUT) / 1e6
print(f"File size: {size_mb:.1f} MB")
