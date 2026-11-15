# -*- coding: utf-8 -*-
r"""대모험 PoC(2026-11-15 하스피 «ㄱ») — 오프닝 이벤트 첫 두 대사를 한글로
  · 글꼴 JPNZN12X.FNT(FONTX2 12×12, 행 2 B 빅엔디언, 왼쪽 = MSB) 의 한자 칸 0x889F~ 를 한글(갈무리11)로 덮음
  · TALKS.DAT: «これは ひどい» → 세 줄 한글(파일 크기 늘림 시험 겸), «もしかして…» 세 줄 → 한글
  python tools/poc.py → work/build/files/{TALKS.DAT, JPNZN12X.FNT} (+ 글자판 work/look/poc_font.png)"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, r'C:\claude\project\anearth-kr-patch\tools')
from bdf import Font
GAL = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.bdf'

OLD1 = 'これは ひどい'
NEW1 = ['이건 너무 심하다', '배가 완전히 부서졌어', '대체 무슨 일이 있었던 거지?']
OLD2 = 'もしかして\r\nこれはファルさんの 船じゃないのか？\r\nあの帆のマークはそうに違いない！'
NEW2 = ['혹시', '이건 팔 아저씨의 배 아니야?', '저 돛의 마크는 틀림없어!']


def fontx(b):
    nb = b[17]
    blocks = [struct.unpack_from('<HH', b, 18 + 4 * i) for i in range(nb)]
    return blocks, 18 + 4 * nb


def index(blocks, code):
    n = 0
    for s, e in blocks:
        if s <= code <= e: return n + code - s
        n += e - s + 1
    raise KeyError(hex(code))


def codes(blocks, start, count):
    out, c = [], start
    while len(out) < count:
        lo = c & 0xFF
        if 0x40 <= lo <= 0xFC and lo != 0x7F:
            try: index(blocks, c); out.append(c)
            except KeyError: pass
        c += 1
    return out


def glyph(f, ch):
    pts, _ = f.draw(ch)
    ref, _ = f.draw('가'); top = min(y for _, y in ref)
    rows = [0] * 12
    xs = [x for x, _ in pts]; x0 = min(xs) if xs else 0
    w = (max(xs) - x0 + 1) if xs else 0
    dx = max(0, (11 - w) // 2)
    for x, y in pts:
        yy = y - top + 1; xx = x - x0 + dx
        if 0 <= yy < 12 and 0 <= xx < 12: rows[yy] |= 1 << (15 - xx)
    return b''.join(struct.pack('>H', r) for r in rows)


def main():
    fb = bytearray(open(os.path.join(ROOT, 'work', 'disc0', 'JPNZN12X.FNT'), 'rb').read())
    blocks, base = fontx(fb)
    chars = sorted(set(''.join(NEW1 + NEW2)) - set(' ?!'))
    cs = codes(blocks, 0x889F, len(chars))
    f = Font(GAL)
    enc = {}
    for ch, c in zip(chars, cs):
        i = index(blocks, c); fb[base + 24 * i:base + 24 * i + 24] = glyph(f, ch); enc[ch] = c

    def sj(s):
        o = bytearray()
        for ch in s:
            if ch in enc: o += struct.pack('>H', enc[ch])
            elif ch == ' ': o += b' '
            elif ch == '?': o += '？'.encode('cp932')
            elif ch == '!': o += '！'.encode('cp932')
            else: raise SystemExit('⛔글자 없음 %r' % ch)
        return bytes(o)

    t = open(os.path.join(ROOT, 'work', 'disc0', 'TALKS.DAT'), 'rb').read()
    o1, o2 = OLD1.encode('cp932'), OLD2.encode('cp932')
    sec = t.index('オープニングイベント'.encode('cp932'))          # 오프닝 장 안의 첫 것만
    i1 = t.index(o1, sec); i2 = t.index(o2, sec); assert i1 < i2
    t2 = (t[:i1] + b'\r\n'.join(sj(x) for x in NEW1) + t[i1 + len(o1):i2] + b'\r\n'.join(sj(x) for x in NEW2)
          + t[i2 + len(o2):])
    od = os.path.join(ROOT, 'work', 'build', 'files'); os.makedirs(od, exist_ok=True)
    open(os.path.join(od, 'TALKS.DAT'), 'wb').write(t2)
    open(os.path.join(od, 'JPNZN12X.FNT'), 'wb').write(fb)
    print('한글 %d자 → 0x%X~0x%X · TALKS %d → %d B' % (len(chars), cs[0], cs[-1], len(t), len(t2)))
    # 글자판
    from PIL import Image
    im = Image.new('L', (13 * len(chars), 12), 0)
    for k, ch in enumerate(chars):
        g = fb[base + 24 * index(blocks, enc[ch]):][:24]
        for r in range(12):
            v = struct.unpack_from('>H', g, 2 * r)[0]
            for x in range(12):
                if v >> (15 - x) & 1: im.putpixel((13 * k + x, r), 255)
    os.makedirs(os.path.join(ROOT, 'work', 'look'), exist_ok=True)
    im.resize((im.size[0] * 4, 48), Image.NEAREST).save(os.path.join(ROOT, 'work', 'look', 'poc_font.png'))


if __name__ == '__main__':
    main()
