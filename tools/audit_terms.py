# -*- coding: utf-8 -*-
"""번역 분석(읽기만) — 인물·용어·토큰·명사 일관성.

  python tools/audit_terms.py [번역 폴더] > work/text/audit.txt

A 토큰: {#..} 제어, [화자], ／ 줄 수, %d 류, Ｇ 단위 — 원문과 개수·순서 비교
B 인물: HUMAN(이름표) 번역 = 기준. 대사·화자 태그·exe 에서 그 이름이 다르게 적힌 곳
C 용어: CITY·MONSNAME·ITEM 이름 번역 = 기준. 대사에서 다르게 적힌 곳
D 명사: 원문 가타카나·한자 낱말별로 번역 표기가 갈린 것
"""
import glob
import re
import sys
import unicodedata
from collections import Counter, defaultdict

DIR = sys.argv[1] if len(sys.argv) > 1 else 'my files/번역'
rows = []
for f in sorted(glob.glob(DIR + '/*.tsv')):
    L = open(f, encoding='utf-8-sig').read().split('\n')
    for i, l in enumerate(L[1:], 2):
        p = l.split('\t')
        if len(p) >= 6:
            rows.append(dict(id=p[0], kind=p[1], where=p[2], jp=p[4], ko=p[5], src='%s:%d' % (f[-11:], i)))


def nf(s):
    return unicodedata.normalize('NFKC', s)


def out(s=''):
    print(s)


# ---------- A 토큰 ----------
TOKS = [('제어', r'\{[^}]*\}'), ('화자', r'\[[^\]]*\]'), ('서식', r'%[0-9]*[a-zA-Z]'), ('Ｇ', r'[ＧG](?![a-zA-Z])')]
out('=' * 70 + '\nA 토큰 차이')
na = 0
for r in rows:
    if not r['ko'].strip() or r['ko'] == r['jp']:
        continue
    for name, pat in TOKS:
        a = re.findall(pat, nf(r['jp'])) if name != '화자' else re.findall(pat, r['jp'])
        b = re.findall(pat, nf(r['ko'])) if name != '화자' else re.findall(pat, r['ko'])
        if name == '화자':
            a, b = len(a), len(b)
        elif name == '제어':
            a, b = [nf(x) for x in a], [nf(x) for x in b]
        if a != b:
            na += 1
            out('  %s %s [%s] %s → %s\n     %s\n   → %s' % (r['id'], r['src'], name, a, b, r['jp'][:80], r['ko'][:80]))
out('  계 %d' % na)

# ---------- 이름 사전 ----------
def kata_words(s):
    return re.findall(r'[ァ-ヺー]{2,}', nf(s).replace('･', '・'))


names = {}   # JP(전각) → KO
for r in rows:
    if r['kind'] in ('human',) and r['ko'].strip():
        jp = nf(r['jp']).replace('･', '・').strip()
        ko = r['ko'].strip()
        jparts = [p for p in re.split(r'[・\s]+', jp) if p]
        kparts = [p for p in re.split(r'[・\s]+', ko) if p]
        if len(jparts) == len(kparts):
            for a, b in zip(jparts, kparts):
                if len(a) >= 2:
                    names.setdefault(a, Counter())[b] += 1
terms = {}
for r in rows:
    if r['kind'] in ('name', 'item') and r['ko'].strip():
        jp = re.sub(r'[　\s]*[+＋]\s*\d+\s*$', '', nf(r['jp'])).strip('　 ')
        ko = re.sub(r'[　\s]*[+＋]\s*\d+\s*$', '', r['ko']).strip('　 ')
        if len(jp) >= 2 and re.search(r'[ァ-ヺ一-龯]', jp):
            terms.setdefault(jp, Counter())[ko] += 1

out('\n' + '=' * 70 + '\n이름표 자체가 갈린 것(같은 JP 이름 조각 → 여러 KO)')
for d in (names, terms):
    for k, c in sorted(d.items()):
        if len(c) > 1:
            out('  %s → %s' % (k, dict(c)))


HAN = re.compile(r'[가-힣]+')


def check_dict(title, d, kinds):
    out('\n' + '=' * 70 + '\n' + title)
    tot = 0
    for jp, c in sorted(d.items(), key=lambda x: -len(x[0])):
        std = c.most_common(1)[0][0]
        miss = []
        for r in rows:
            if r['kind'] not in kinds or not r['ko'].strip() or r['ko'] == r['jp']:
                continue
            j = nf(r['jp']).replace('･', '・')
            if jp in j and std not in r['ko'].replace(' ', '') and std.replace(' ', '') not in r['ko'].replace(' ', ''):
                miss.append(r)
        if miss:
            tot += len(miss)
            # 비슷한 표기 = 첫 글자 같은 한글 덩어리
            alt = Counter(w for r in miss for w in HAN.findall(r['ko']) if w[0] == std[0] and abs(len(w) - len(std)) <= 3)
            out('■ %s = 「%s」  다른 곳 %d · 비슷한 표기 %s' % (jp, std, len(miss), dict(alt.most_common(5))))
            for r in miss[:5]:
                out('    %s %s\n      %s\n    → %s' % (r['id'], r['src'], r['jp'][:70], r['ko'][:70]))
    out('  계 %d' % tot)


check_dict('B 인물 이름(HUMAN 표 기준) — 대사·exe 에서 다르게 적힌 곳', names, ('talk', 'exe'))
check_dict('C 용어(항구·몬스터·아이템 이름표 기준) — 대사·exe 에서 다르게 적힌 곳', terms, ('talk', 'exe'))

# 화자 태그
out('\n' + '=' * 70 + '\nB2 화자 태그 [..] 표기')
sp = defaultdict(Counter)
for r in rows:
    if r['kind'] != 'talk':
        continue
    a = re.findall(r'\[([^\]]*)\]', r['jp']); b = re.findall(r'\[([^\]]*)\]', r['ko'])
    if len(a) == len(b):
        for x, y in zip(a, b):
            sp[nf(x)][y] += 1
for k, c in sorted(sp.items()):
    std = names.get(k)
    flag = '' if len(c) == 1 else '  ★갈림'
    if std and std.most_common(1)[0][0] not in c:
        flag += '  ★이름표(%s)와 다름' % std.most_common(1)[0][0]
    out('  [%s] → %s%s' % (k, dict(c), flag))

# ---------- D 명사 ----------
out('\n' + '=' * 70 + '\nD 원문 낱말별 번역 표기 갈림(대사)')
JOSA = sorted('이 가 은 는 을 를 의 에 에서 에게 와 과 로 으로 도 만 이나 나 라 이라 야 이야 님 들 이여 여'.split(), key=len, reverse=True)


def stem(w):
    for j in JOSA:
        if len(w) > len(j) + 1 and w.endswith(j):
            return w[:-len(j)]
    return w


occ = defaultdict(list)
for r in rows:
    if r['kind'] != 'talk' or not r['ko'].strip():
        continue
    for k in set(re.findall(r'[ァ-ヺー]{3,}|[一-龯]{2,}', nf(r['jp']))):
        occ[k].append(r)
for k, lst in sorted(occ.items(), key=lambda x: -len(x[1])):
    if len(lst) < 3 or k in names or k in terms:
        continue
    df = Counter()
    for r in lst:
        df.update({stem(w) for w in HAN.findall(r['ko'])})
    top, c = df.most_common(1)[0]
    if c / len(lst) < 0.5:
        continue
    miss = [r for r in lst if top not in r['ko']]
    if not miss:
        continue
    alt = Counter(w for r in miss for w in {stem(x) for x in HAN.findall(r['ko'])} if w[0] == top[0] and w != top and abs(len(w) - len(top)) <= 2)
    out('■ %s → 「%s」 %d/%d · 빠진 %d · 다른 표기 %s' % (k, top, c, len(lst), len(miss), dict(alt.most_common(5)) or '-'))
    for r in miss[:3]:
        out('    %s %s → %s' % (r['id'], r['jp'][:50], r['ko'][:60]))
