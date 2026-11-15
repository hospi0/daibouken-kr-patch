# -*- coding: utf-8 -*-
r"""빌드본 0.BIN 에 «번역 안 된 일본어 문구»가 남았는지 전수 검사(2026-11-15, 하스피 «다 뽑았다며» 이후)

  python tools/find_left_jp.py      (먼저 tools/build.py)

세 갈래로 찾는다 — 한 갈래만 쓰면 계속 샌다:
  ① 포인터 대상: 0.BIN 안 BE32 값이 가리키는 자리마다 문자열을 읽음(앞이 포인터 바이트여도 잡힘: 出　航·木)
  ② 0 다음 시작: «0 + 글자들 + 0»(짧은 메뉴 «  装  備  »)
  ③ 붙은 문자열: 앞 문자열 바로 뒤(資材)
남은 것 = 번역 행·추가 표가 덮지 않았고 빌드본에서도 바이트가 그대로인 곳. 잡음(코드 바이트)은 «일본어 글자 2개 이상 + 깨진 글자 없음»으로 거름.
"""
import glob
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build  # noqa: E402

B = 0x6004000
o = open(os.path.join(ROOT, 'work', 'disc0', '0.BIN'), 'rb').read()
n = open(os.path.join(ROOT, 'work', 'build', 'files', '0.BIN'), 'rb').read()
KEEP = [(0x3B600, 0x3BB90)]                      # 엔딩 제작진 명단(허락 없이 손대지 않음)
JP = re.compile(r'[ぁ-んァ-ヶ一-龯々]')


def read(a):
    """a 에서 0 까지 시프트JIS 로 읽기 → (끝, 글) 또는 None"""
    j, s = a, ''
    while j < len(o) and o[j] != 0 and j - a < 80:
        c = o[j]
        if (0x81 <= c <= 0x9f or 0xe0 <= c <= 0xea) and j + 1 < len(o) and 0x40 <= o[j + 1] <= 0xfc and o[j + 1] != 0x7f:
            ch = o[j:j + 2].decode('cp932', 'replace')
            if ch == '�': return None
            s += ch; j += 2
        elif 0x20 <= c < 0x7f or 0xa1 <= c <= 0xdf:
            s += o[j:j + 1].decode('cp932', 'replace'); j += 1
        else:
            return None
    if j >= len(o) or o[j] != 0 or not s: return None
    return j, s


def main():
    cov = []
    for f in glob.glob(os.path.join(ROOT, 'work', 'text', 'kr', '*.tsv')):
        for l in open(f, encoding='utf-8-sig').read().split('\n')[1:]:
            p = l.split('\t')
            if len(p) >= 6 and p[2].startswith('0.BIN@') and p[5] and p[5] != p[4]:
                a = int(p[2].split('@')[1], 16); cov.append((a, a + len(p[4].encode('cp932', 'replace'))))
    for k, (a, bud, jp, ko) in build.EXTRA_EXE.items(): cov.append((a, a + bud))
    for k, a in build.OFFSET_FIX.items(): cov.append((a, o.index(0, a)))
    cand = set()
    for i in range(0, len(o) - 3, 2):                       # ① 포인터 대상
        v = struct.unpack_from('>I', o, i)[0]
        if B <= v < B + len(o): cand.add(v - B)
    for i in range(1, len(o)):                               # ② 0 다음 시작
        if o[i - 1] == 0 and o[i]: cand.add(i)
    # ④ 앞이 수치 바이트인 표 항목(鋼鉄 — 0·포인터·붙은 문자열 어느 것도 아님): 가나·JIS 1수준 한자 2자 이상 + 0
    def lvl1(c, t):
        code = (c << 8) | t
        return 0x829F <= code <= 0x82F1 or 0x8340 <= code <= 0x8396 or 0x889F <= code <= 0x9872 or code in (0x8140, 0x815B)
    ends = {}
    for a in range(0, len(o) - 6):
        j = a; k = 0
        while j + 1 < len(o) and lvl1(o[j], o[j + 1]): j += 2; k += 1
        if k >= 2 and j < len(o) and o[j] == 0 and j not in ends: ends[j] = a
    cand |= set(ends.values())
    out = {}
    for a in sorted(cand):
        r = read(a)
        if not r: continue
        e, s = r
        cand.add(e + 1)                                      # ③ 붙은 문자열(바로 뒤 시작)
        if len(JP.findall(s)) < 1 or len(re.sub(r'[\s　]', '', s)) < 1: continue
        if any(x < e and a < y for x, y in cov) or any(x <= a < y for x, y in KEEP): continue
        if n[a:e] != o[a:e]: continue
        # 잡음: 일본어 글자 1개뿐인데 반각·영숫자 섞임
        if len(JP.findall(s)) == 1 and re.search(r'[ｦ-ﾟA-Za-z@?/`]', s): continue
        out[a] = s
    for a, s in sorted(out.items()):
        print('%X\t%d\t%s' % (a, o.index(0, a) - a, s))
    print('남은 후보 %d' % len(out))


if __name__ == '__main__':
    main()
