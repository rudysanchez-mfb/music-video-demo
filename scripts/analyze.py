#!/usr/bin/env python3
"""analyze.py <music-video> [out.json] - per-second audio RMS + video motion + luma.

Prints a 10 s table and the heaviest windows so intro/outro/chapter cards can be
placed where the song (and the band) hit hardest.

Requirements: ffmpeg on PATH and numpy (`pip install numpy`).
"""
import sys, json, subprocess, wave, tempfile, os
import numpy as np

src = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    os.environ.get('MUSIC_DEMO_DIR', '.'), 'analysis.json')

tmp = tempfile.mkdtemp()
wav = os.path.join(tmp, 'mono.wav')
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-vn', '-ac', '1',
                '-ar', '16000', wav], check=True)

w = wave.open(wav)
sr = w.getframerate()
a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
rms = [float(np.sqrt(np.mean(a[i * sr:(i + 1) * sr] ** 2))) for i in range(len(a) // sr)]

W, H, F = 80, 60, 6
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-vf',
                      f'fps={F},scale={W}:{H},format=gray', '-f', 'rawvideo', '-'],
                     capture_output=True).stdout
fr = np.frombuffer(raw, dtype=np.uint8).reshape(-1, H, W).astype(np.float32)
d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))
motion = [float(d[i * F:(i + 1) * F].mean()) for i in range(len(d) // F)]
lum = [float(fr[i * F:(i + 1) * F].mean()) for i in range(len(fr) // F)]

n = min(len(rms), len(motion))
json.dump({'src': src, 'seconds': n, 'rms': rms[:n], 'motion': motion[:n],
           'lum': lum[:n]}, open(out, 'w'))
print(f"{src}\n{n}s   t   dB    motion  luma")
for t in range(0, n, 10):
    r = np.mean(rms[t:t + 10]); m = np.mean(motion[t:t + 10]); l = np.mean(lum[t:t + 10])
    print(f"{t:4d} {20 * np.log10(r + 1e-9):6.1f} {m:6.1f} {l:5.1f} {'#' * int(m)}")

m = np.array(motion[:n]); r = np.array(rms[:n]); rdb = 20 * np.log10(r + 1e-9)
loud = np.where(rdb > np.percentile(rdb, 60))[0]
print(f"\nloud section (top 40% by RMS) starts ~{int(loud.min()) if len(loud) else 0}s; "
      f"quiet intro ~0-{int(loud.min()) if len(loud) else 0}s")

win = 8
c = sorted(((m[t:t + win].mean(), t) for t in range(0, n - win)), reverse=True)
picked = []
for s, t in c:
    if all(abs(t - p) >= win for _, p in picked):
        picked.append((s, t))
    if len(picked) >= 10:
        break
print("heaviest 8s windows (motion):",
      ', '.join(f"{t}-{t + win}s ({s:.0f})" for s, t in sorted(picked, key=lambda x: x[1])))
print(f"wrote {out}")
