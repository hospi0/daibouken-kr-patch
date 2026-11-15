# -*- coding: utf-8 -*-
"""work/text/kr 대사의 줄 폭(44칸) 넘침을 «낱말 단위 다시 나누기»로 푼다(글자·띄어쓰기는 안 바꿈).

  python tools/rewrap_kr.py          # 미리보기
  python tools/rewrap_kr.py --apply

한 문단(제어 줄 사이 연속 줄) 안에서만 다시 나눈다. 줄 수는 그 메시지의 원문 줄 수를 넘기지 않는다.
들여쓰기 줄은 앞 공백만 줄여서 들어가면 그렇게 한다(가운데 정렬 대사).
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build  # noqa: E402

W = build.TALK_W
APPLY = '--apply' in sys.argv
KR = os.path.join(os.path.dirname(HERE), 'work', 'text', 'kr')


def w(s):
    return build.width(build.norm(s))


def is_ctrl(s):
    return re.fullmatch(r'\{#[^}]*\}', s.strip()) is not None


def best_split(words, k):
    """words 를 k 줄 이하로, 가장 긴 줄이 최소가 되게(모두 ≤ W). 없으면 None."""
    n = len(words)
    from functools import lru_cache

    @lru_cache(None)
    def go(i, left):
        if i == n:
            return (0, ())
        if left == 0:
            return None
        best = None
        for j in range(i + 1, n + 1):
            line = ' '.join(words[i:j])
            if w(line) > W:
                break
            r = go(j, left - 1)
            if r is None:
                continue
            cand = (max(w(line), r[0]), (line,) + r[1])
            if best is None or cand[0] < best[0]:
                best = cand
        return best
    r = go(0, k)
    return list(r[1]) if r else None


def fix_row(jp, ko):
    segs = ko.split('／')
    olines = len(jp.split('／'))
    if not any(not is_ctrl(s) and w(s) > W for s in segs):
        return ko, None
    out = list(segs)
    # ① 들여쓰기만 줄이면 되는 줄
    for i, s in enumerate(out):
        if not is_ctrl(s) and w(s) > W and s != s.lstrip(' 　'):
            t = s
            while w(t) > W and t[:1] in (' ', '　'):
                t = t[1:]
            if w(t) <= W:
                out[i] = t
    # ② 문단 다시 나누기
    i = 0
    res = []
    while i < len(out):
        if is_ctrl(out[i]) or out[i].strip() == '':
            res.append(out[i]); i += 1; continue
        j = i
        while j < len(out) and not is_ctrl(out[j]) and out[j].strip() != '':
            j += 1
        para = out[i:j]
        if any(w(s) > W for s in para):
            # 넘치는 첫 줄 앞까지는 그대로 두고, 그 줄부터 «앞에서 채우기»(낱말 단위). 줄이 모자라면 균형 나누기.
            f0 = next(t for t, s in enumerate(para) if w(s) > W)
            head, tail = para[:f0], para[f0:]
            words = ' '.join(s.strip() for s in tail).split()
            spare = olines - len(out)       # 메시지 전체 줄 여유
            new = None
            for k in range(len(tail), len(tail) + max(0, spare) + 1):
                g, cur = [], ''
                for wd in words:
                    t = (cur + ' ' + wd) if cur else wd
                    if w(t) <= W:
                        cur = t
                    else:
                        g.append(cur); cur = wd
                g.append(cur)
                if len(g) <= k and all(w(x) <= W for x in g):
                    new = head + g
                    break
                b = best_split(tuple(words), k)
                if b:
                    new = head + b
                    break
            if new is None:                 # 앞줄까지 포함해 문단 전체 다시 나누기
                allw = ' '.join(s.strip() for s in para).split()
                for k in range(len(para), len(para) + max(0, spare) + 1):
                    new = best_split(tuple(allw), k)
                    if new:
                        break
            if new is None:
                return ko, '못 풂'
            res.extend(new)
            out_len_delta = len(new) - len(para)
            olines -= 0
        else:
            res.extend(para)
        i = j
    if len(res) > len(jp.split('／')):
        return ko, '줄 수 초과'
    return '／'.join(res), None


def main():
    n = 0
    for f in sorted(glob.glob(KR + '/*.tsv')):
        L = open(f, encoding='utf-8-sig').read().split('\n')
        ch = False
        for i, l in enumerate(L):
            p = l.split('\t')
            if len(p) < 6 or p[1] != 'talk' or not p[5].strip():
                continue
            new, err = fix_row(p[4], p[5])
            if err:
                print('✖ %s %s' % (p[0], err))
            elif new != p[5]:
                n += 1
                print('● %s\n   %s\n → %s' % (p[0], p[5], new))
                p[5] = new; L[i] = '\t'.join(p); ch = True
        if ch and APPLY:
            open(f, 'w', encoding='utf-8', newline='').write('\n'.join(L))
    print('다시 나눈 행 %d%s' % (n, ' (반영)' if APPLY else ' (미리보기)'))


if __name__ == '__main__':
    main()
