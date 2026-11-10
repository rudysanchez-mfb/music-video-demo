# music-video-demo

**Score, card, and caption software product demos to the tempo of music videos.**

Take any music video, keep the song as the spine, and cut a product showcase
around it: the video's own footage rides semi-transparent under intro, chapter,
and outro cards, while live 1080p takes of your app play between them with
burned-in captions. The band on screen plays the bar you hear; the product does
the talking; nothing on screen is a mock.

This repository is the pipeline and the conventions, not the media. It ships
**no audio, no video, and no copyrighted material** — only scripts, example
card/timeline JSON, and documentation.

---

## What it produces

```
intro card (song footage, dimmed)
  -> chapter 1 card (song footage, dimmed)
  -> body take 1  (live app recording + lower-third captions)
  -> chapter 2 card
  -> body take 2
  -> ...
  -> wrap card
  -> outro card
one continuous song underneath, static gain, fades in/out
```

Every card's background is cut from the song video **at that card's own timeline
offset**, so the picture matches the bar you hear. Audio is measured once with
`ebur128` and normalized to -14 LUFS with `volume` + `alimiter` (never `loudnorm`,
which resamples to 96/192 kHz and mangles the AAC in players).

---

## Requirements

| tool | used for |
|---|---|
| `python3` + `PIL` (Pillow) + `numpy` | card rendering, song analysis |
| `ffmpeg` / `ffprobe` | audio extraction, encoding, QA frames |
| Node.js + [Playwright](https://playwright.dev/) (Chrome channel) | recording live app takes |
| `yt-dlp` | optional — pulling tracks for the rotation (`add-demo-track`) |
| `whisper` | optional — transcribing takes to time captions |

No `drawtext` is required: all type is rendered as PIL PNG overlays, so a
minimal ffmpeg build works.

### Fonts

`cards.py` resolves fonts by path, not `fc-match` (whose cache can be stale and
return icon fonts). Point `MUSIC_DEMO_FONTS` at a directory containing
`Anton-Regular.ttf`, `BebasNeue-Regular.ttf`, `Oswald-*.ttf`, `Inter-*.ttf`;
otherwise it falls back to the distro Ubuntu / Liberation / DejaVu families.

---

## Install

```bash
git clone https://github.com/rudysanchez-mfb/music-video-demo.git
cd music-video-demo
python3 -m pip install --user pillow numpy
# Playwright (in your own project dir is fine):
npm init -y && npm i -D playwright && npx playwright install chrome
```

The scripts also accept a pre-existing Playwright install via
`MUSIC_DEMO_PLAYWRIGHT=/path/to/node_modules/playwright/index.mjs`.

---

## Configuration

Everything that used to be a hardcoded personal path is an environment variable.

| variable | default | meaning |
|---|---|---|
| `MUSIC_DEMO_DIR` | `.` | working dir for `takes/`, `cards/`, `build/` |
| `MUSIC_DEMO_OUT` | `.` | where the finished mp4 is delivered |
| `MUSIC_DEMO_STATE` | `~/.config/music-video-demo/state.json` | Playwright `storageState` jar |
| `MUSIC_DEMO_FONTS` | `~/.local/share/fonts/media-skills/` | display TTF directory |
| `MUSIC_DEMO_PLAYWRIGHT` | bare `playwright` | path to `playwright/index.mjs` |
| `MUSIC_DEMO_FOOT` | `music-video-demo` | default footer on chapter cards |
| `MUSIC_DEMO_LIBRARY` | *(unset)* | root of your track rotation (`add-demo-track`) |

Set them once per session:

```bash
export MUSIC_DEMO_DIR="$HOME/scratch/my-demo"
export MUSIC_DEMO_OUT="$HOME/Documents/demos/$(date +%F)-my-demo"
mkdir -p "$MUSIC_DEMO_DIR" "$MUSIC_DEMO_OUT"
```

---

## The pipeline

### 1. Analyze the song

```bash
python3 scripts/analyze.py song.webm "$MUSIC_DEMO_DIR/analysis.json"
```

Prints a 10-second table of RMS, motion, and luma, plus the heaviest 8-second
windows. Use it to place the intro card on the song's opening and the wrap/outro
cards on the heaviest stretch — a mismatch is heard instantly.

### 2. Auth and probe

If the app needs a login, create a Playwright `storageState` jar once, headed,
with a human at the keyboard:

```js
// save-state.mjs
const context = await browser.newContext();
// ...log in...
await context.storageState({ path: process.env.MUSIC_DEMO_STATE });
```

Then probe every route headless with the jar (screenshot, inputs, placeholders,
seed buttons) **before** writing a scene. Selectors must come from the app's own
`data-testid` / `data-playwright` attributes or stable classnames — never
guessed. `scripts/bridge-state.mjs` is the legacy lane for harvesting an
already-open CDP Chrome on `:9222`.

### 3. Record

```bash
cp scripts/record.template.mjs "$MUSIC_DEMO_DIR/record.mjs"
# rewrite the SEGMENTS block, then:
cd "$MUSIC_DEMO_DIR" && nohup node record.mjs > record.log 2>&1 &
```

Scene rules that matter:

- seed a populated screen before demonstrating;
- wait for async work to **settle**, not merely to start;
- hold 4–7 s on every payoff;
- end every scene on a full, readable screen — never an empty state.

Each scene writes beat marks to `takes/marks.json`; captions are timed off those.
Inspect takes with a contact sheet (`fps=1/2.5, tile=5x4`) and actually read it.
Retake one scene with `ONLY=<name> node record.mjs`.

### 4. Cards

```bash
python3 scripts/cards.py cards.json "$MUSIC_DEMO_DIR/cards"
```

Two card shapes (`cards.example.json`):

```jsonc
// title card
{"id": "intro", "kind": "title", "kicker": "...", "title": ["LINE ONE", "LINE TWO"],
 "size": 220, "sub": "...", "foot": "soundtrack: artist - title"}

// chapter card
{"id": "ch1", "num": "01", "kicker": "SEARCH", "title": "Ask in plain words.",
 "bullets": ["three bullets max"], "verdict": "one line max", "foot": "optional"}
```

Copy rules: put numbers on a card only if a probe screenshot showed them. Three
bullets, one verdict line. ASCII only (the mono font has no arrows or emoji).
Credit the track in the intro/outro `foot` as `artist - title`. No lyrics on a
card, ever.

Themes pick a display font and accent colour per genre:

| genre | theme | look |
|---|---|---|
| metal / hard rock | `metal` | Anton, orange `#ffa000` |
| hip-hop / trap | `hiphop` | Anton, gold |
| synthwave / retro | `synth` | Ubuntu Bold, magenta |
| classic rock / punk | `rock` | Anton, ember `#e8590c` |
| country / folk / americana | `country` | Bebas Neue, brass |
| house / techno / EDM | `electronic` | Ubuntu Bold, cyan |
| anything else | `cockpit` | house look |

### 5. Timeline and assemble

`timeline.json` (see `examples/timeline.example.json`) lists `song_video`,
`theme`, optional `song_offset`, `card_alpha` (0.42 reads well), and `segments`.
Card segments alternate with body segments; body `captions` are
`[from, to, KICKER, text]` in body-relative seconds (marks minus `in`).

```bash
MUSIC_DEMO_DIR="$MUSIC_DEMO_DIR" python3 scripts/assemble.py timeline.json
```

### 6. QA before you say anything

```bash
MUSIC_DEMO_DIR="$MUSIC_DEMO_DIR" bash scripts/qa.sh \
  build/demo.mp4 song.webm 9.0,17.0,25.0 0,9,17
```

Read every `build/qa-*.png`:

- audio sample rate is 48000;
- no body opens on a spinner or white;
- each card frame matches the source frame at the same song time;
- captions sit clear of the thing they describe.

Fix, rebuild, re-read. Then copy the mp4 plus a `pipeline/` copy of every script
and JSON used to `MUSIC_DEMO_OUT`.

---

## Adding tracks (companion skill)

The `add-demo-track` skill lives in
[`skills/add-demo-track/SKILL.md`](skills/add-demo-track/SKILL.md). It documents
how to grow the local rotation (`hype`, `drive`, `chill`) from a URL or file:
download with `yt-dlp`, detect tempo, normalize to -14 LUFS, name to the
library's convention, rebuild the manifest.

> The ingest engine and seed audio are intentionally **not** bundled. This repo
> ships no copyrighted tracks. Only add music you have the rights to use, and
> record the source and licence with the file.

If you drive the pipeline directly from a music video (as `music-video-demo`
does), you do not need the rotation at all — the timeline names the song video.

---

## Project layout

```
README.md
LICENSE                     Apache-2.0
NOTICE
.gitignore
SKILL.md                    agent-facing walkthrough
scripts/
  analyze.py                per-second RMS / motion / luma
  cards.py                  card + lower-third PNG renderer (PIL)
  assemble.py               timeline -> scored, captioned mp4
  qa.sh                     contact sheet + frame/sample-rate checks
  bridge-state.mjs          CDP -> Playwright storageState (legacy)
  record.template.mjs       headless 1080p take recorder (template)
examples/
  cards.example.json
  timeline.example.json
skills/
  add-demo-track/SKILL.md   companion: grow the track rotation
```

---

## Design invariants (do not "simplify" these)

1. Card footage is cut from the song video at the card's own timeline offset.
   Never pick footage by motion score.
2. Audio is `volume` + `alimiter` + `aresample=48000`, targeting -14 LUFS from
   an `ebur128` measurement. **Never** `loudnorm`.
3. Every segment fades 0.4–0.5 s in/out; the song fades in over 0.8 s and out
   over the last 4 s.
4. Captions narrate the product; they never quote lyrics.

---

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

Copyright 2026 Rudy Sanchez.
