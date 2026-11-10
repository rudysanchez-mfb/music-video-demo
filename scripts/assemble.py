#!/usr/bin/env python3
"""assemble.py <timeline.json> - score a product demo to a music video.

Cards ride over semi-transparent footage cut at the SONG's own offset; bodies
carry burned lower-third captions; one continuous song plays underneath at a
measured static gain.

timeline.json keys:
  out, song_video, [music (wav; extracted from song_video if absent)],
  [song_offset=0], [card_alpha=0.42], [theme],
  segments: [{type:card, card, seconds} |
             {type:body, take, in, out, captions:[[a,b,KICKER,text],...]}]

Invariants:
  * footage for a card = song_video at (song_offset + card start), so the band
    plays what you hear;
  * audio = volume + limiter + aresample=48000. NEVER loudnorm: it upsamples to
    96/192 kHz and players mangle the AAC.
"""
import json, subprocess, sys, os, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cards import caption, THEMES

T = json.load(open(sys.argv[1]))
WORK = os.environ.get('MUSIC_DEMO_DIR', '.')
build = os.path.join(WORK, 'build')
cards_dir = os.path.join(WORK, 'cards')
os.makedirs(build, exist_ok=True)
os.makedirs(cards_dir, exist_ok=True)

th = THEMES.get(T.get('theme', 'cockpit'), THEMES['cockpit'])
FADE = 0.5
OFF = float(T.get('song_offset', 0))


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-3000:]); sys.exit(1)


def dur(p):
    return float(subprocess.check_output(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'csv=p=0', p]).decode().strip())


music = T.get('music')
if not music:
    music = os.path.join(build, 'song.wav')
    run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i',
         T['song_video'], '-vn', '-ac', '2', '-ar', '48000', music])

ENC = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt',
       'yuv420p', '-r', '30', '-an']
parts = []
cursor = 0.0

for i, s in enumerate(T['segments']):
    out = os.path.join(build, f'seg{i:02d}.mp4')
    if s['type'] == 'card':
        D = s['seconds']; a = T.get('card_alpha', 0.42)
        fc = (f"color=c=black:s=1920x1080:d={D}:r=30[bg];"
              f"[0:v]scale=1920:-2,crop=1920:1080,hue=s=0.15,"
              f"eq=contrast=1.12:brightness=-0.04,fps=30,trim=0:{D},"
              f"setpts=PTS-STARTPTS,format=rgba,colorchannelmixer=aa={a}[fg];"
              f"[bg][fg]overlay=shortest=1[v1];[v1][1:v]overlay=format=auto[v2];"
              f"[v2]fade=t=in:st=0:d={FADE},fade=t=out:st={D - FADE}:d={FADE},"
              f"format=yuv420p[v]")
        run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
             '-ss', f'{OFF + cursor:.3f}', '-t', str(D + 0.5), '-i', T['song_video'],
             '-loop', '1', '-i', os.path.join(cards_dir, f"{s['card']}.png"),
             '-filter_complex', fc, '-map', '[v]', '-t', str(D), *ENC, out])
        print(f"  card {s['card']} footage from song t={OFF + cursor:.1f}s")
    else:
        D = s['out'] - s['in']
        inputs = ['-ss', str(s['in']), '-t', str(D), '-i', s['take']]
        chain = "[0:v]scale=1920:1080,setpts=PTS-STARTPTS,fps=30[v0]"
        last = 'v0'
        for j, (a, b, kick, text) in enumerate(s.get('captions', [])):
            png = os.path.join(cards_dir, f"cap-{i:02d}-{j:02d}.png")
            caption(text, png, kick, th)
            inputs += ['-loop', '1', '-i', png]
            chain += (f";[{last}][{j + 1}:v]overlay=format=auto:"
                      f"enable='between(t,{a},{b})'[v{j + 1}]")
            last = f'v{j + 1}'
        chain += (f";[{last}]fade=t=in:st=0:d=0.4,"
                  f"fade=t=out:st={D - 0.4}:d=0.4,format=yuv420p[v]")
        run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *inputs,
             '-filter_complex', chain, '-map', '[v]', '-t', str(D), *ENC, out])
    d = dur(out); parts.append((out, d)); cursor += d
    print(f"seg{i:02d} {s['type']:5s} {d:6.2f}s  {s.get('card') or s.get('take')}")

total = sum(d for _, d in parts)
print(f"total video {total:.1f}s (song {OFF:.0f}s -> {OFF + total:.0f}s)")

concat = os.path.join(build, 'concat.txt')
with open(concat, 'w') as f:
    for p, _ in parts:
        f.write(f"file '{os.path.abspath(p)}'\n")
video = os.path.join(build, 'video.mp4')
run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat',
     '-safe', '0', '-i', concat, '-c', 'copy', video])

meas = subprocess.run(
    ['ffmpeg', '-hide_banner', '-i', music, '-af',
     f'atrim={OFF}:{OFF + total},ebur128=peak=true', '-f', 'null', '-'],
    capture_output=True, text=True).stderr
I = float(re.search(r'I:\s*(-?[\d.]+) LUFS', meas.split('Summary:')[-1]).group(1))
gain = float(T.get('target_lufs', -14.0)) - I
print(f"song measured {I:.1f} LUFS over the cut -> gain {gain:+.1f} dB")

af = (f"atrim={OFF}:{OFF + total},asetpts=PTS-STARTPTS,volume={gain:.2f}dB,"
      f"alimiter=limit=0.89:level=false,"
      f"afade=t=in:st=0:d=0.8,afade=t=out:st={total - 4}:d=4,aresample=48000")
run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', video, '-i', music,
     '-filter_complex', f"[1:a]{af}[a]", '-map', '0:v', '-map', '[a]',
     '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest',
     '-movflags', '+faststart', T['out']])
print('wrote', T['out'], f"{dur(T['out']):.1f}s", os.path.getsize(T['out']) // 1024, 'KB')
