# 5 New Empires — 2026 World Cup short (vertical, 1080×1920)

A cinematic, beat-driven vertical edit (~93s) profiling five nations chasing
their first World Cup: **Ecuador, Japan, Morocco, Colombia, Netherlands**.
Built deterministically from the supplied voiceover and photos with Pillow +
ffmpeg — no AI-generated footage, so every real face stays correctly labelled.

## Output
`output/world_cup_empires.mp4` — H.264 / AAC, 1080×1920, 30 fps, 92.92 s
(matches the voiceover exactly).

## How it's built (3 steps)
```bash
python3 build_audio.py     # -> assets/ambience.wav  (crowd rumble + sub-bass)
python3 render_scenes.py   # -> scenes/*.png         (25 framed still scenes)
python3 build_video.py     # -> output/world_cup_empires.mp4
```

## Art direction
- **Layout** — every hero photo is placed sharp and centred inside a rounded
  frame over a blurred fill of itself, so faces are never cropped and there are
  no black bars. Cinematic grade (slight desaturation, contrast, vignette, fine
  grain). Team-colour accents.
- **Typography** — heavy condensed headers (*Anton* / *Bebas Neue*, uppercase,
  outlined) + a sleek lower-third subtitle (*Montserrat*) on a soft pill. All
  text is centred and kept inside safe margins; the Ken-Burns zoom is capped at
  1.045 so nothing drifts off-screen.
- **Sound** — synthesized deep stadium crowd hum + a rhythmic 50 Hz sub-bass
  that accents each segment change, mixed under the voiceover. The opening and
  closing low-end "drops" are aligned so the clip loops seamlessly.
- **Cuts** — xfade transitions (fade / fade-through-black / slide) chosen per
  scene; offsets computed so segment changes land on the narration.

## A note on missing faces (network-restricted build)
This environment's network policy only reaches GitHub/PyPI (Wikipedia/Wikimedia
were blocked), so a few named players/coaches that weren't uploaded —
**Willian Pacho, Piero Hincapié, Moisés Caicedo, Luis Díaz, Mohamed Ouahbi** —
could not be downloaded. Rather than show broken or mislabelled images, they are
rendered as clean **typographic nameplates in national colours** (name, role,
club). Drop matching photos into `assets/photos/`, swap the relevant
`s_namecard(...)` call for `s_single(...)` in `render_scenes.py`, and re-run the
three build steps to slot real photos in.

## Assets used
Real photos: James Rodríguez, Luis Díaz (nameplate), Néstor Lorenzo, Achraf
Hakimi, Yassine Bounou, Wataru Endo, Takefusa Kubo, Ayase Ueda, Kaoru Mitoma,
Virgil van Dijk, the World Cup trophy, the 2026 emblem, and the five national
flags.

Fonts are OFL-licensed (Anton, Bebas Neue, Oswald, Montserrat).
