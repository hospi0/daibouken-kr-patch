# -*- coding: utf-8 -*-
r"""타이틀 부제 TLOGO_2.DG2(192×16, «セントエルモスの奇跡») → 한글(2026-11-15)

  DG2 = «PP» + u16 폭 + u16 높이 (BE) + 팔레트 256×RGB555 BE(512 B) + 화소 8비트(폭×높이). 팔레트는 그대로 둔다.
  글자마다 따로 그려 원본 잉크 가로 범위를 글자 간격으로 채운다(원본도 글자 사이를 벌려 192 px 를 채움).
    TTF  = 8배로 그려 줄인 덮임 비율 → 원본 팔레트 노랑 단계 중 가장 가까운 색
    BDF  = 갈무리 화소 그대로(보간 없음) → 잉크 = 원본 최대 노랑, 오른쪽·아래 1 px 그림자 = 어두운 노랑

  python tools/title_sub.py --preview            # work/title/부제_미리보기_<글꼴>.png (원본|한글, 실제 색 4배)
  python tools/title_sub.py --font <이름> --write # work/build/files/TLOGO_2.DG2
"""
import os
import struct
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(r'C:\claude\project\anearth-kr-patch\tools')
SRC = os.path.join(ROOT, 'work', 'disc0', 'TLOGO_2.DG2')
TEXT = '세인트 엘모스의 기적'
GAL = r'C:\claude\utils\font\Galmuri-v2.40.3'
FONTS = {
    '갈무리14': ('bdf', GAL + r'\Galmuri14.bdf'),
    '갈무리11굵게': ('bdf', GAL + r'\Galmuri11-Bold.bdf'),
    '나눔고딕EB': ('ttf', r'C:\claude\utils\font\nanum-gothic\NanumGothicExtraBold.ttf'),
    '주아': ('ttf', r'C:\claude\utils\font\jua\Jua-Regular.ttf'),
}
S = 8


def load():
    d = open(SRC, 'rb').read()
    w, h = struct.unpack_from('>HH', d, 2)
    pal = [struct.unpack_from('>H', d, 6 + 2 * i)[0] for i in range(256)]
    return d, w, h, pal, bytearray(d[518:518 + w * h])


def rgb(v):
    return ((v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3)


def glyphs_ttf(path, H):
    """글자별 덮임 비율 2차원 목록(높이 H)"""
    size = H * S
    f = ImageFont.truetype(path, size)
    # 한글 대표 글자 높이를 H 에 맞춤
    while True:
        bb = f.getbbox('엘')
        if bb[3] - bb[1] <= H * S: break
        size -= 2; f = ImageFont.truetype(path, size)
    ref = f.getbbox('엘')
    out = []
    for ch in TEXT:
        if ch == ' ': out.append(None); continue
        bb = f.getbbox(ch)
        cw = bb[2] - bb[0]
        im = Image.new('L', (cw + S, H * S), 0)
        ImageDraw.Draw(im).text((-bb[0], -ref[1]), ch, font=f, fill=255)
        wpx = (cw + S - 1) // S
        sm = im.crop((0, 0, wpx * S, H * S)).resize((wpx, H), Image.BOX)
        out.append([[sm.getpixel((x, y)) / 255 for x in range(wpx)] for y in range(H)])
    return out


def glyphs_bdf(path):
    from bdf import Font
    f = Font(path)
    out = []
    for ch in TEXT:
        if ch == ' ': out.append(None); continue
        pts, _ = f.draw(ch)
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        x0 = min(xs); w = max(xs) - x0 + 1
        out.append({(x - x0, y): 1 for x, y in pts})
    return out, f


def main():
    d, w, h, pal, px = load()
    bg = max(set(px), key=px.count)
    used = sorted(set(px))
    ramp = [i for i in used if rgb(pal[i])[0] == rgb(pal[i])[1] and rgb(pal[i])[2] <= 64 and rgb(pal[i])[0] >= 96]
    full = max(ramp, key=lambda i: rgb(pal[i])[0])
    dark = min(ramp, key=lambda i: abs(rgb(pal[i])[0] - 136))
    cols = [x for x in range(w) if any(px[y * w + x] != bg for y in range(h))]
    L, R = min(cols), max(cols) + 1                    # 원본 잉크 가로 범위
    rows = [y for y in range(h) if any(px[y * w + x] != bg for x in range(w))]
    T, B = min(rows), max(rows) + 1

    def build(name):
        kind, path = FONTS[name]
        out = bytearray([bg]) * (w * h)
        if kind == 'ttf':
            gl = glyphs_ttf(path, B - T)
            widths = [len(g[0]) if g else 0 for g in gl]
        else:
            gl, f = glyphs_bdf(path)
            ys = [y for g in gl if g for (_, y) in g]
            y0 = min(ys); gh = max(ys) - y0 + 1
            widths = [max(x for x, _ in g) + 1 if g else 0 for g in gl]
        nch = sum(1 for g in gl if g)
        nsp = sum(1 for g in gl if g is None)
        gaps = len(gl) - 1 + nsp                        # 빈칸 = 간격 2개 몫
        free = (R - L) - sum(widths)
        gap = free / gaps
        x = L
        for g, cw in zip(gl, widths):
            if g is None:
                x += gap; continue
            xi = int(round(x))
            if kind == 'ttf':
                for yy in range(B - T):
                    for xx in range(cw):
                        a = g[yy][xx]
                        if a < 0.12 or not (0 <= xi + xx < w): continue
                        want = tuple(c * a for c in (248, 248, 0))
                        out[(T + yy) * w + xi + xx] = min(ramp + [bg], key=lambda i: sum((p - q) ** 2 for p, q in zip(rgb(pal[i]), want)))
            else:
                yo = T + ((B - T) - gh) // 2 - y0
                for (xx, yy) in g:                      # 그림자 먼저
                    for dx, dy in ((1, 1),):
                        X, Y = xi + xx + dx, yo + yy + dy
                        if 0 <= X < w and 0 <= Y < h and (xx + dx, yy + dy) not in g: out[Y * w + X] = dark
                for (xx, yy) in g:
                    out[(yo + yy) * w + xi + xx] = full
            x += cw + gap
        return out

    os.makedirs(os.path.join(ROOT, 'work', 'title'), exist_ok=True)
    if '--preview' in sys.argv:
        def img(p):
            im = Image.new('RGB', (w, h)); im.putdata([rgb(pal[c]) for c in p]); return im
        for name in FONTS:
            o = build(name)
            sheet = Image.new('RGB', (w, h * 2 + 4), (60, 60, 60))
            sheet.paste(img(px), (0, 0)); sheet.paste(img(o), (0, h + 4))
            p = os.path.join(ROOT, 'work', 'title', '부제_미리보기_%s.png' % name)
            sheet.resize((w * 4, (h * 2 + 4) * 4), Image.NEAREST).save(p)
            print(p)
    if '--write' in sys.argv:
        name = sys.argv[sys.argv.index('--font') + 1]
        o = build(name)
        od = os.path.join(ROOT, 'work', 'build', 'files'); os.makedirs(od, exist_ok=True)
        open(os.path.join(od, 'TLOGO_2.DG2'), 'wb').write(d[:518] + bytes(o) + d[518 + w * h:])
        print('쓰기 OK TLOGO_2.DG2 (%s)' % name)


if __name__ == '__main__':
    main()
