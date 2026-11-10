#!/usr/bin/env bash
# qa.sh <final.mp4> <song_video> <body_start_1,body_start_2,...> [card_time_1,card_time_2]
# Writes build/qa-*.png: a contact sheet, the first frame of every body (no
# spinner/white allowed), and card-vs-source frame pairs at the same song offset
# (they must match). Prints the audio stream (must be 48000 Hz).
set -eu

V="$1"; SONG="$2"; BODIES="$3"; CARDS="${4:-}"
BUILD="${MUSIC_DEMO_DIR:-.}/build"
mkdir -p "$BUILD"

ffprobe -v error -select_streams a \
  -show_entries stream=codec_name,sample_rate,channels -of default=nw=1 "$V"

ffmpeg -hide_banner -loglevel error -y -i "$V" \
  -vf "fps=1/5,scale=320:-1,tile=8x6:padding=3:color=0x222222" \
  -frames:v 1 "$BUILD/qa-sheet.png"

i=0
for t in ${BODIES//,/ }; do
  ffmpeg -hide_banner -loglevel error -y -ss "$t" -i "$V" -frames:v 1 \
    -vf scale=480:-1 "$BUILD/qa-body-$i.png"
  i=$((i+1))
done

if [ -n "$CARDS" ]; then
  i=0
  for t in ${CARDS//,/ }; do
    ffmpeg -hide_banner -loglevel error -y -ss "$t" -i "$V" -frames:v 1 \
      -vf scale=480:-1 "$BUILD/qa-card-out-$i.png"
    ffmpeg -hide_banner -loglevel error -y -ss "$t" -i "$SONG" -frames:v 1 \
      -vf "scale=1920:-2,crop=1920:1080,scale=480:-1" "$BUILD/qa-card-src-$i.png"
    i=$((i+1))
  done
fi

echo "QA frames in $BUILD/qa-*.png - READ them before reporting."
