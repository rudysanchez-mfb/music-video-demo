#!/usr/bin/env python3
"""cards.py <cards.json> [outdir=cards] - 1920x1080 card overlays + lower-third captions (PIL).

cards.json: {"theme": "metal", "cards": [...], "captions": [...]}
Themes pick fonts + accent per genre; every theme is white type on a dark scrim so
it reads over footage. Text is ASCII-safe by design: the mono font has no
arrows/emoji.

Fonts are resolved by path (fc-match is unreliable). Point MUSIC_DEMO_FONTS at a
directory of TTFs (Anton, Bebas Neue, Oswald, Inter) or rely on the distro
Ubuntu/DejaVu/Liberation families.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import json, sys, os

W, H = 1920, 1080
WHITE = (247, 250, 255, 255); DIM = (190, 198, 210, 255); FAINT = (150, 158, 170, 255)

# First existing path wins. MUSIC_DEMO_FONTS overrides the search root.
GF = (os.environ.get('MUSIC_DEMO_FONTS') or
      os.path.expanduser('~/.local/share/fonts/media-skills/')).rstrip('/') + '/'
SYS = '/usr/share/fonts/truetype/'


def pick(*cands):
    for c in cands:
        if c and os.path.exists(c):
            return c
    return cands[-1]


IMPACT = pick(GF + 'Anton-Regular.ttf',
              SYS + 'liberation/LiberationSansNarrow-Bold.ttf',
              SYS + 'dejavu/DejaVuSans-Bold.ttf')
DISPLAY = pick(GF + 'BebasNeue-Regular.ttf', GF + 'Anton-Regular.ttf',
               SYS + 'ubuntu/Ubuntu-B.ttf')
SANS_B = pick(SYS + 'ubuntu/Ubuntu-B.ttf',
              SYS + 'liberation/LiberationSans-Bold.ttf',
              SYS + 'dejavu/DejaVuSans-Bold.ttf')
SANS_R = pick(SYS + 'ubuntu/Ubuntu-R.ttf',
              SYS + 'liberation/LiberationSans-Regular.ttf',
              SYS + 'dejavu/DejaVuSans.ttf')
MONO = pick(SYS + 'ubuntu/UbuntuMono-R.ttf', SYS + 'dejavu/DejaVuSansMono.ttf',
            SYS + 'noto/NotoSansMono-Regular.ttf')
HN = SANS_B

THEMES = {  # accent, title font (big), kicker/mono font
    'metal':      {'accent': (255, 160, 0, 255),  'title': IMPACT,  'mono': MONO},
    'hiphop':     {'accent': (255, 200, 40, 255), 'title': IMPACT,  'mono': MONO},
    'synth':      {'accent': (255, 64, 200, 255), 'title': SANS_B,  'mono': MONO},
    'rock':       {'accent': (232, 89, 12, 255),  'title': IMPACT,  'mono': MONO},
    'country':    {'accent': (222, 168, 84, 255), 'title': DISPLAY, 'mono': MONO},
    'electronic': {'accent': (86, 216, 231, 255), 'title': SANS_B,  'mono': MONO},
    'cockpit':    {'accent': (255, 160, 0, 255),  'title': SANS_B,  'mono': MONO},
}

DEFAULT_FOOT = os.environ.get('MUSIC_DEMO_FOOT', 'music-video-demo')


def hn(size, bold=False, path=None):
    return ImageFont.truetype(path or (SANS_B if bold else SANS_R), size)


def load(path, size, index=None):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return hn(size, True)


def wrap(d, text, font, maxw):
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=font) <= maxw:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def card(spec, th, out):
    ACC = th['accent']
    T = lambda s: load(th['title'], s, th.get('title_index'))
    M = lambda s: load(th['mono'], s)
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 14, H], fill=ACC)                       # left rail (house mark)
    x, y = 150, 150
    if spec.get('kind') == 'title':
        d.text((x, y), spec['kicker'], font=M(30), fill=ACC); y += 70
        size = spec.get('size', 220); big = T(size)
        for line in spec['title']:
            d.text((x - 6, y), line, font=big, fill=WHITE); y += int(size * 1.0)
        y += 40
        if spec.get('sub'):
            d.text((x, y), spec['sub'], font=M(36), fill=DIM)
        if spec.get('foot'):
            d.text((x, H - 110), spec['foot'], font=M(26), fill=FAINT)
    else:
        if spec.get('num'):
            d.text((x, y), spec['num'], font=T(120), fill=ACC)
            d.text((x + 190, y + 78), spec['kicker'], font=M(32), fill=ACC); y += 160
        else:
            d.text((x, y), spec['kicker'], font=M(32), fill=ACC); y += 70
        big = T(120)
        for line in wrap(d, spec['title'], big, 1500):
            d.text((x - 4, y), line, font=big, fill=WHITE); y += 128
        y += 40; body = hn(44)
        for b in spec.get('bullets', []):
            d.ellipse([x + 6, y + 18, x + 22, y + 34], fill=ACC)
            for line in wrap(d, b, body, 1450):
                d.text((x + 50, y), line, font=body, fill=DIM); y += 58
            y += 16
        if spec.get('verdict'):
            y += 20; d.text((x, y), spec['verdict'], font=hn(48, True), fill=ACC)
        d.text((x, H - 110), spec.get('foot', DEFAULT_FOOT), font=M(26), fill=FAINT)
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sh.putalpha(im.split()[3].filter(ImageFilter.GaussianBlur(14)))
    base = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    base.alpha_composite(sh); base.alpha_composite(im); base.save(out)


def caption(text, out, kicker=None, th=None):
    th = th or THEMES['cockpit']; ACC = th['accent']
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    font = hn(40, True); kf = load(th['mono'], 24)
    lines = wrap(d, text, font, 1500); pad = 34
    tw = max(d.textlength(l, font=font) for l in lines)
    kw = d.textlength(kicker, font=kf) if kicker else 0
    w = int(max(tw, kw) + pad * 2); h = 22 + 52 * len(lines) + (34 if kicker else 0)
    x0 = (W - w) // 2; y0 = H - 92 - h
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=14, fill=(8, 10, 14, 215))
    d.rectangle([x0, y0 + 12, x0 + 6, y0 + h - 12], fill=ACC)
    yy = y0 + 14
    if kicker:
        d.text((x0 + pad, yy), kicker, font=kf, fill=ACC); yy += 32
    for l in lines:
        d.text((x0 + pad, yy), l, font=font, fill=WHITE); yy += 52
    im.save(out)


if __name__ == '__main__':
    spec = json.load(open(sys.argv[1]))
    outdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.environ.get('MUSIC_DEMO_DIR', '.'), 'cards')
    os.makedirs(outdir, exist_ok=True)
    th = THEMES.get(spec.get('theme', 'cockpit'), THEMES['cockpit'])
    for c in spec['cards']:
        card(c, th, f"{outdir}/{c['id']}.png"); print('card', c['id'])
