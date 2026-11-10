---
name: add-demo-track
description: >-
  Add a song to the demo-video music rotation from a URL or a local file.
  Downloads with yt-dlp, detects tempo, normalises loudness to match the existing
  library, names it to the library's convention, files it under a mood folder,
  and rebuilds the manifest. Use when you give a YouTube/other URL and say to add
  it to the demo music, put it in rotation, or convert a track for the demo
  videos.
---

# add-demo-track

This is the companion skill to `music-video-demo`. It documents how to grow the
local track library that the demo pipeline draws from.

> The ingest engine (`ingest.py`) and the seeded tracks are **not** bundled with
> this repository. Point `MUSIC_DEMO_LIBRARY` at your own library root and use
> the ingest command your environment provides. What follows is the workflow and
> the conventions to follow; nothing here ships copyrighted audio.

Set `MUSIC_DEMO_LIBRARY` to your library root. The layout the rotation expects:

```
$MUSIC_DEMO_LIBRARY/
  hype/      # triumphant, celebratory, anthemic
  drive/     # relentless, propulsive, dark
  chill/     # low-key, warm, background
  _removed/  # retired tracks
  manifest.json
```

One command adds a track:

```bash
python3 "$MUSIC_DEMO_LIBRARY/ingest.py" <url-or-file> \
  --mood <hype|drive|chill> --tags "words describing it"
```

## Licensing

Only add tracks you may use. Seed libraries are often CC-BY (for example Kevin
MacLeod, incompetech.com, CC BY 4.0). Write the source and licence into the
description/tag so the provenance travels with the file. This repository ships
**no** audio.

## Picking the mood

Only `hype`, `drive` and `chill` are scanned; a track filed under any other
folder name is silently invisible. Retire a track by moving it to `_removed/`
and rebuilding the manifest - don't delete it, or its index gets handed to
something else later.

| mood | used for | feel |
|---|---|---|
| `hype` | feature wins, ship energy | triumphant, celebratory, anthemic |
| `drive` | fixes, urgency, "watch this break then get fixed" | relentless, propulsive, dark |
| `chill` | refactor, chore, docs | low-key, warm, background |

## Tags

The manifest derives each track's searchable tags from its filename: strip the
leading `NN_` and extension, turn underscores into spaces. Discovery counts how
many words of a hint appear in that string, so tags are the whole mechanism.
Pick words a hint would plausibly contain (`rock`, `driving`, `celebration`,
`dark`), not just the artist. `--tags` usually takes the first four words; omit
it and the title gets slugified instead, which is usually worse.

## Tempo detection is octave-ambiguous

BPM is measured with a spectral-flux onset envelope plus autocorrelation (numpy
only). It cannot resolve genuine ambiguity: a stomp-clap pattern has real energy
at both the beat and the half-beat, so a track that is 81 BPM can measure 161.
When the script prints `! tempo is octave-ambiguous`, check it and pass `--bpm`.
BPM is cosmetic metadata in the filename; a wrong one misleads a human but does
not break selection.

## Other flags

- `--bpm N` - override detection.
- `--start S` - trim S seconds off the head. Default auto-detects leading silence
  at -40 dB, so a demo doesn't open on dead air. Auto-detection only finds
  *silence*; a track opening with talking or a slow fade needs `--start` by hand.
- `--desc "..."` - plain-English description. Pass it whenever you know what the
  track is; otherwise the description is derived from `--tags` and says so.
- `--comment "..."` - seed the COMMENT tag. Optional.
- `--dest DIR` - target a different library root (used for testing).
- `--no-reindex` - skip rebuilding `manifest.json`.

## Custom tags

If your library writes a generated provenance tag, treat it as regenerated on
every ingest: never rely on hand edits there. The COMMENT frame is the one to
hand-edit - nothing in the pipeline reads or writes it after the optional
`--comment` seed. Tag editors (Kid3, MusicBrainz Picard) both surface it as a
first-class field. Editing tags later changes file checksums, so if your library
uses an immutability guard, unlock, edit, then re-lock.

## What good output looks like

Every library track is 256 kbps / 44.1 kHz / stereo, normalised to -14 LUFS via
two-pass `loudnorm` (a track louder than its neighbours jumps out of rotation).
Indices are never reused: the next number is the max across `hype`, `drive`,
`chill` and `_removed`, plus one.
