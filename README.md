# WC26 Promo Video — "5 Rising Empires"

A fully scripted, programmatically rendered 93-second vertical promo
(1080x1920 @ 30fps) for the 2026 FIFA World Cup, covering five first-time
title contenders: **Ecuador, Japan, Morocco, Colombia and the Netherlands**.

The final deliverable is `output/wc26_promo.mp4`.

## How it's built

| Stage | Tool | Output |
|---|---|---|
| Asset prep | `rembg` (u2net) background removal on player/trophy stills | `assets/cutouts/*.png` |
| Footage harvest | ffmpeg center-crops of the previous draft render (removes its burned-in captions) | `assets/clips/*.mp4` |
| Frame renderer | `build_video.py` — pure PIL/numpy compositing piped into ffmpeg/libx264 | `output/video_silent.mp4` |
| SFX bed | `build_sfx.py` — every cue synthesized with numpy/scipy (booms, risers, glass shatter, clang, radar pings, gong, choir pad…) | `output/sfx.wav` |
| Mux | ffmpeg amix of voiceover + SFX | `output/wc26_promo.mp4` |

Run everything with:

```bash
./build_all.sh
```

(Requires: ffmpeg, Python 3 with `pillow`, `numpy`, `scipy`; fonts are bundled
in `fonts/`. The clip frame cache is extracted to `/tmp/cf` automatically.)

## Edit plan

The full timed shot list (voiceover, visual direction, on-screen text and SFX
per beat) lives in [`SCRIPT.md`](SCRIPT.md). Highlights:

- **Intro (0:00–0:15)** — WC26 logo 3D zoom on black, glitch cut to a roaring
  stadium, the 8 historical champions' flags flashed in grayscale, the trophy
  shattering a glass overlay, then rapid split-screen teases of all 5 teams.
- **Ecuador (0:15–0:32)** — ticking "19 MATCHES UNBEATEN" counter, brick-wall
  texture flashes, Pacho/Hincapié split screen, Caicedo zoom, ball-off-the-post
  "biggest hurdle" beat.
- **Japan (0:32–0:47)** — red X cards over the injured Mitoma/Minamino,
  triple-panel high-intensity press, Endo/Kubo with electric arcs, and a radar
  sweep over top scorer Ueda on a moving tactical board.
- **Morocco (0:47–1:00)** — coach Ouahbi framed on the flag with claw-slash
  streaks, Hakimi swipe-in, Bounou's leaping entrance, neon wing-attack mesh.
- **Colombia (1:00–1:13)** — neon dark-horse silhouette, Lorenzo over fire
  embers, James/Díaz split screen divided by a live lightning bolt.
- **Netherlands (1:13–1:28)** — silver 1974/1978/2010 slams, a chained padlock
  that shatters on "break the curse", towering low-angle Van Dijk bathed in
  golden god rays with a shine-sweep "ETERNAL GLORY".
- **Outro (1:28–1:33)** — logo with the 5 flags orbiting, bouncing arrow onto a
  comment-box mockup and a pulsing SUBSCRIBE button.

## Repo layout

```
assets/          source stills, flags, voiceover
assets/cutouts/  background-removed PNGs (rembg)
assets/clips/    caption-free footage crops from the previous draft
fonts/           Anton, Archivo Black, Oswald (OFL)
build_video.py   frame renderer (all graphics drawn in code)
build_sfx.py     synthesized sound-design bed
build_all.sh     one-shot pipeline
output/          rendered deliverables
```
