#!/usr/bin/env python3
"""Statistics Slide animation → MP4"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Wedge, Circle
import imageio
import imageio_ffmpeg
import io, os

# ── Video settings ─────────────────────────────────────────────────────────────
FPS       = 60
DURATION  = 4.5          # seconds
N_FRAMES  = int(FPS * DURATION)
W, H      = 1280, 720
DPI       = 96
OUT       = '/home/user/Claude-adn2/statistics_animation.mp4'

# ── Design tokens ──────────────────────────────────────────────────────────────
TEAL     = '#177E89'
ORANGE   = '#E8A020'
GRAY_TR  = '#E0E0E0'
WHITE    = '#FFFFFF'
DARK     = '#111111'
MID      = '#777777'

charts = [
    {'pct': 75,  'color': TEAL},
    {'pct': 60,  'color': TEAL},
    {'pct': 95,  'color': ORANGE},
    {'pct': 25,  'color': TEAL},
]

DESC = ('Curabitur iaculis risus erat,\n'
        'sit amet placerat nunc\n'
        'elementum non. Integer id\n'
        'aliquam nulla.')

# ── Chart geometry ─────────────────────────────────────────────────────────────
R_OUT   = 98          # outer radius  (px in data-space)
R_IN    = 64          # inner radius
R_MID   = (R_OUT + R_IN) / 2
R_CAP   = (R_OUT - R_IN) / 2   # half-width → cap dot radius

CX_LIST = [160, 480, 800, 1120]   # x-centres of the four rings
CY      = 390                      # y-centre (matplotlib: 0=bottom)

# ── Easing ─────────────────────────────────────────────────────────────────────
def ease_out_cubic(t):
    t = float(np.clip(t, 0, 1))
    return 1 - (1 - t) ** 3

def ease_in_out(t):
    t = float(np.clip(t, 0, 1))
    return t * t * (3 - 2 * t)

def lerp_norm(t, start, end):
    """Return 0→1 progress for t within [start, end]."""
    if t <= start:  return 0.0
    if t >= end:    return 1.0
    return (t - start) / (end - start)

# ── Per-frame renderer ─────────────────────────────────────────────────────────
def render_frame(t: float) -> np.ndarray:
    """t ∈ [0,1]. Returns H×W×3 uint8 array."""
    fig, ax = plt.subplots(figsize=(W / DPI, H / DPI), dpi=DPI)
    fig.patch.set_facecolor(WHITE)
    ax.set_facecolor(WHITE)
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect('equal')
    ax.axis('off')

    # ── Title ──────────────────────────────────────────────────────────────────
    ta = ease_out_cubic(lerp_norm(t, 0.0, 0.18))
    ty_offset = (1 - ta) * 20          # slides down 20px
    ax.text(W / 2, 638 - ty_offset, 'Statistics Slide',
            ha='center', va='center',
            fontsize=34, fontweight='bold',
            color=DARK, alpha=ta)

    # ── Rings & text ───────────────────────────────────────────────────────────
    for i, (cx, ch) in enumerate(zip(CX_LIST, charts)):
        delay   = 0.15 + i * 0.09
        ring_end = delay + 0.58

        ring_t  = ease_out_cubic(lerp_norm(t, delay, ring_end))
        cur_pct = ch['pct'] * ring_t
        ring_alpha = min(1.0, lerp_norm(t, delay, delay + 0.12) * 4)

        # Background full ring
        bg = Wedge((cx, CY), R_OUT, 0, 360,
                   width=R_OUT - R_IN,
                   facecolor=GRAY_TR, edgecolor='none',
                   alpha=ring_alpha, zorder=1)
        ax.add_patch(bg)

        if cur_pct >= 0.3:
            angle   = cur_pct / 100 * 360
            theta2  = 90              # start angle (top, CCW-positive)
            theta1  = 90 - angle      # end angle (clockwise travel)

            # Coloured arc
            arc = Wedge((cx, CY), R_OUT, theta1, theta2,
                        width=R_OUT - R_IN,
                        facecolor=ch['color'], edgecolor='none',
                        alpha=ring_alpha, zorder=2)
            ax.add_patch(arc)

            # Rounded cap at START (top, fixed)
            sx = cx + R_MID * np.cos(np.radians(90))
            sy = CY + R_MID * np.sin(np.radians(90))
            ax.add_patch(Circle((sx, sy), R_CAP,
                                facecolor=ch['color'], edgecolor='none',
                                alpha=ring_alpha, zorder=3))

            # Rounded cap at END (moving)
            ex = cx + R_MID * np.cos(np.radians(theta1))
            ey = CY + R_MID * np.sin(np.radians(theta1))
            ax.add_patch(Circle((ex, ey), R_CAP,
                                facecolor=ch['color'], edgecolor='none',
                                alpha=ring_alpha, zorder=3))

        # Percentage counter
        pct_alpha = ease_out_cubic(lerp_norm(t, delay + 0.05, delay + 0.3))
        ax.text(cx, CY, f'{int(cur_pct)}%',
                ha='center', va='center',
                fontsize=28, fontweight='bold',
                color=DARK, alpha=pct_alpha, zorder=4)

        # Headline
        txt_start = ring_end - 0.05
        txt_a = ease_out_cubic(lerp_norm(t, txt_start, txt_start + 0.25))
        ax.text(cx, CY - R_OUT - 28, 'Enter Headline',
                ha='center', va='top',
                fontsize=13, fontweight='bold',
                color=DARK, alpha=txt_a, zorder=4)

        # Description body
        ax.text(cx, CY - R_OUT - 53, DESC,
                ha='center', va='top',
                fontsize=9.5, color=MID,
                alpha=txt_a, linespacing=1.65, zorder=4)

    # ── Capture frame ─────────────────────────────────────────────────────────
    buf = io.BytesIO()
    fig.savefig(buf, format='raw', dpi=DPI)
    plt.close(fig)
    buf.seek(0)
    frame = np.frombuffer(buf.read(), dtype=np.uint8)
    frame = frame.reshape((H, W, 4))
    return frame[:, :, :3]   # drop alpha → RGB


# ── Render & write ─────────────────────────────────────────────────────────────
ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

print(f"Rendering {N_FRAMES} frames at {FPS} fps …")
writer = imageio.get_writer(
    OUT, fps=FPS,
    codec='libx264',
    ffmpeg_log_level='error',
    ffmpeg_params=['-pix_fmt', 'yuv420p', '-crf', '18'],
    macro_block_size=None,
)

for f in range(N_FRAMES):
    t = f / (N_FRAMES - 1)
    frame = render_frame(t)
    writer.append_data(frame)
    if f % 30 == 0:
        print(f"  frame {f}/{N_FRAMES} ({100*t:.0f}%)", flush=True)

writer.close()
size_mb = os.path.getsize(OUT) / 1e6
print(f"\nDone → {OUT}  ({size_mb:.1f} MB)")
