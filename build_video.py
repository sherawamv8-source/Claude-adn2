#!/usr/bin/env python3
"""
Assemble the final vertical (1080x1920, 30fps) video.
Pass 1: each scene PNG -> a gentle centered Ken-Burns clip (text stays in frame).
Pass 2: xfade-chain the clips with their per-scene transitions, then mux the
        voiceover over the synthesized stadium/sub-bass ambience.
Output: output/world_cup_empires.mp4
"""
import os, json, subprocess, shlex

ROOT = os.path.dirname(os.path.abspath(__file__))
SC   = os.path.join(ROOT, "scenes")
TMP  = os.path.join(ROOT, "tmp_clips")
OUT  = os.path.join(ROOT, "output")
os.makedirs(TMP, exist_ok=True); os.makedirs(OUT, exist_ok=True)

FPS   = 30
T     = 0.45                     # transition (xfade) duration
ZMAX  = 1.045                    # gentle zoom ceiling (keeps text on-screen)
VO    = os.path.join(ROOT, "assets", "voiceover.mp3")
AMB   = os.path.join(ROOT, "assets", "ambience.wav")
FINAL = os.path.join(OUT, "world_cup_empires.mp4")

man = json.load(open(os.path.join(SC, "manifest.json")))
scenes = man["scenes"]
N = len(scenes)

def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode != 0:
        print(p.stdout.decode()[-3000:]); raise SystemExit(f"FAILED: {cmd[:3]}")

# ---- clip lengths: non-last get +T so xfade overlap preserves total ---------
durs = [s["dur"] for s in scenes]
L = [durs[i] + (T if i < N-1 else 0.0) for i in range(N)]

# ---- PASS 1 : Ken Burns clips ----------------------------------------------
clips = []
for i, s in enumerate(scenes):
    png = os.path.join(SC, s["file"])
    out = os.path.join(TMP, f"clip_{i:02d}.mp4")
    Lf  = max(2, round(L[i]*FPS))
    zr  = (ZMAX - 1.0) / Lf
    direction = 1 if i % 2 == 0 else -1   # subtle alternating vertical drift
    ypan = (f"ih/2-(ih/zoom/2)+{direction}*on*0.10")
    vf = (
        "scale=1620:2880:force_original_aspect_ratio=increase,crop=1620:2880,"
        f"zoompan=z='min(zoom+{zr:.6f},{ZMAX})':d={Lf}:"
        "x='iw/2-(iw/zoom/2)':"
        f"y='{ypan}':s=1080x1920:fps={FPS},setsar=1,format=yuv420p"
    )
    run(["ffmpeg","-y","-loop","1","-i",png,"-vf",vf,"-t",f"{L[i]:.3f}",
         "-c:v","libx264","-preset","medium","-crf","18",
         "-pix_fmt","yuv420p","-r",str(FPS),out])
    clips.append(out)
    print(f"  pass1 clip {i:02d} {s['id']:18s} {L[i]:.2f}s ({Lf}f)")

# ---- PASS 2 : xfade chain + audio ------------------------------------------
inputs = []
for c in clips: inputs += ["-i", c]
inputs += ["-i", VO, "-i", AMB]
vo_idx, amb_idx = N, N+1

fc = []
prev = "0:v"
acc = L[0]
for k in range(1, N):
    trans = scenes[k]["trans"]
    offset = acc - T
    label = f"x{k}"
    fc.append(f"[{prev}][{k}:v]xfade=transition={trans}:duration={T}:"
              f"offset={offset:.3f}[{label}]")
    prev = label
    acc = acc + L[k] - T
vlast = prev

# audio: voiceover over ambience, no normalisation pumping, soft limit
fc.append(f"[{vo_idx}:a]aresample=44100,aformat=channel_layouts=stereo[vo]")
fc.append(f"[{amb_idx}:a]aresample=44100[amb]")
fc.append("[vo][amb]amix=inputs=2:duration=first:weights='1.00 0.85':"
          "normalize=0[mx]")
fc.append("[mx]alimiter=limit=0.96,aresample=44100[aout]")

filtergraph = ";".join(fc)
cmd = ["ffmpeg","-y"] + inputs + [
    "-filter_complex", filtergraph,
    "-map", f"[{vlast}]", "-map", "[aout]",
    "-r", str(FPS), "-c:v","libx264","-preset","medium","-crf","19",
    "-pix_fmt","yuv420p","-c:a","aac","-b:a","192k",
    "-t", "92.92", "-movflags","+faststart", FINAL]
run(cmd)
print("WROTE", FINAL)
