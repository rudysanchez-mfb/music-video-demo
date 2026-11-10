---
name: music-video-demo
description: >-
  Turn a music video (any genre) into a scored, captioned product demo: the song
  is the spine, the video's own footage rides semi-transparent under
  intro/outro/chapter cards, and live 1080p takes of the app play between them
  with burned-in captions. Use when you have a music video file and want to make
  a demo/showcase out of it, "score the demo with this song", or show off an app
  (local or hosted) to a track. One song per video, never a medley.
---

# music-video-demo

Song in, showcase out. The band on screen plays the bar you hear; the product
does the talking through captions; nothing on screen is a mock.

All paths are configurable. Set these before you start (see README):

| variable | meaning |
|---|---|
| `MUSIC_DEMO_DIR` | scratch/working dir for `takes/`, `cards/`, `build/` (default `.`) |
| `MUSIC_DEMO_OUT` | deliverable dir for the final mp4 (default `.`) |
| `MUSIC_DEMO_STATE` | Playwright storageState jar (default `~/.config/music-video-demo/state.json`) |
| `MUSIC_DEMO_FONTS` | dir of display TTFs (Anton, Bebas Neue, Oswald, Inter) |
| `MUSIC_DEMO_PLAYWRIGHT` | path to `playwright/index.mjs` (default bare `playwright`) |

`$SKILL` = this repository's root. Scripts live in `$SKILL/scripts/`.

Requirements: `python3` with PIL + numpy, `ffmpeg`/`ffprobe` on PATH, Node with
Playwright (and a Chrome channel), and `whisper`/`yt-dlp` only if you add tracks
(see the `add-demo-track` companion skill). Fonts are resolved by path, not
`fc-match` (whose cache can be stale and return icon fonts). If your system
ffmpeg lacks `drawtext`, that is fine: all type here is PIL PNG overlays.

## Inputs to settle from the ask (do not ask, read it)

- The music video file (copy it into `MUSIC_DEMO_DIR`).
- The surfaces to show, in order.
- Captions: on by default (they are the narration). No voice-over unless asked.
- One song per video. Never a medley.

## Step 1 - Analyze the song

```bash
python3 "$SKILL/scripts/analyze.py" song.webm "$MUSIC_DEMO_DIR/analysis.json"
```

Read the table: where the quiet intro ends, where the heaviest windows are.
This decides placement (Step 5): the intro card sits on the song's own opening,
the wrap/outro cards sit on the heaviest stretch. A mismatch is heard instantly.

## Step 2 - Auth and probe

If the app needs a login, create a storageState jar once, headed, with a human at
the keyboard. The jar is a standard Playwright `storageState` file:

```js
// save-state.mjs (your own helper) - run headed, log in, then:
await context.storageState({ path: process.env.MUSIC_DEMO_STATE });
```

Never open a visible browser from the agent without the user present. A stale jar
means log in again. `scripts/bridge-state.mjs` is the legacy lane for harvesting
an already-open CDP Chrome on `:9222`.

Then probe every route headless with the jar (screenshot + inputs + placeholders
+ seed buttons) before writing a scene. Selectors come from the repo's own
classname dictionaries and `data-testid` / `data-playwright` attributes, never
guessed. The `SEGMENTS` block in `record.template.mjs` is an example; rewrite it
for the app at hand.

## Step 3 - Record

Copy `$SKILL/scripts/record.template.mjs` into `MUSIC_DEMO_DIR` as `record.mjs`,
rewrite the `SEGMENTS` block (one async scene per route), run it in the
background:

```bash
cd "$MUSIC_DEMO_DIR" && nohup node record.mjs > record.log 2>&1 &
```

Scene rules: seed a populated screen before demonstrating; wait for the search
to SETTLE (not merely for rows to exist); hold 4-7 s on every payoff; end every
scene on a full readable screen, never on an empty state. Each scene logs beat
marks to `takes/marks.json`; captions are timed off those.

Inspect every take with a contact sheet (`fps=1/2.5, tile=5x4`) and READ it.
Takes open on white/spinner for 2-9 s: that is what `in` trims in Step 5.
Retake a single scene with `ONLY=<name>`.

## Step 4 - Cards

`cards.json` = `{"theme": <genre>, "cards": [...]}`; render with:

```bash
python3 "$SKILL/scripts/cards.py" cards.json "$MUSIC_DEMO_DIR/cards"
```

Shapes:

- title card: `{"id","kind":"title","kicker","title":[lines],"size","sub","foot"}`
- chapter card: `{"id","num":"01","kicker","title","bullets":[3],"verdict"?,"foot"?}`

Copy rules: numbers only if a probe screenshot showed them (post counts, ms).
Three bullets, one verdict line max. ASCII only (the mono font has no arrows or
emoji). Credit the track in the intro/outro `foot` as `artist - title`. No lyrics
anywhere on a card.

| genre heard | theme | look |
|---|---|---|
| metal, hard rock | `metal` | Anton, orange `#ffa000` |
| hip-hop, trap | `hiphop` | Anton, gold |
| synthwave, retro | `synth` | Ubuntu Bold, magenta |
| classic rock, punk | `rock` | Anton, ember `#e8590c` |
| country, folk, americana | `country` | Bebas Neue, brass |
| house, techno, EDM | `electronic` | Ubuntu Bold, cyan |
| anything else / unsure | `cockpit` | house look |

Preview one card composited over a footage frame before rendering them all.

## Step 5 - Timeline and assemble

`timeline.json` (see `examples/timeline.example.json`): `song_video`, `theme`,
optional `song_offset` (start the song later if the demo is short and the heavy
part must land on the close), `card_alpha` (0.42 reads well), and `segments` -
`card` (`seconds` 8 for chapters, 9 intro, 12-13 outro) alternating with `body`
(`take`, `in`, `out`, `captions: [[from, to, KICKER, text], ...]` in body-relative
seconds, derived from marks minus `in`).

```bash
MUSIC_DEMO_DIR="$MUSIC_DEMO_DIR" python3 "$SKILL/scripts/assemble.py" timeline.json
```

Invariants the script enforces; do not "simplify" them away:

1. **Card footage is cut from the song video at the card's own timeline offset.**
   Never pick footage by motion score - "it doesn't match the head banging".
2. **Audio is `volume` + `alimiter` + `aresample=48000`, target -14 LUFS from an
   `ebur128` measurement.** Never `loudnorm`: it upsamples to 96/192 kHz and the
   AAC comes out mangled in players.
3. Every segment fades 0.4-0.5 s in/out; the song fades in 0.8 s and out over
   the last 4 s.

## Step 6 - QA before you say anything

```bash
MUSIC_DEMO_DIR="$MUSIC_DEMO_DIR" bash "$SKILL/scripts/qa.sh" \
  build/demo.mp4 song.webm <body starts,comma> <card times,comma>
```

Read every `build/qa-*.png`: sample rate 48000; no body opens on a spinner or
white; each card frame matches the source frame at the same song time; captions
sit clear of what they describe. Fix, rebuild, re-read. Then copy the mp4 plus a
`pipeline/` copy of every script and JSON used to `MUSIC_DEMO_OUT`.

## Report

Lead with the path and runtime. Say what was verified by frame (tense 1) and
that the full cut was not listened to end to end unless it was. Two or three
sentences on the song-to-picture mapping. No menus.
