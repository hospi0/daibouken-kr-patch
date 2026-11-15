# -*- coding: utf-8 -*-
r"""대모험 번역 추출(2026-11-15) → work/text/jp.tsv(전체) + my files/tsv/dbk_NNN.tsv(18 KB 단위, 하스피 규칙)
  열: id · 종류 · 위치 · 예산 · JP · KO(빈칸)
  · talk  = TALKS.DAT 메시지(시작 줄 ~ #E 앞). JP 는 줄을 «／» 로 이음, 제어 줄(#? #Y #N #: #P 등)은 {#?} 꼴 토큰.
            예산 «L줄·W칸» = 원문 줄 수(제어 줄 포함, 넘기면 안 됨 — 게임이 메시지를 «줄 번호»로 찾음) · 줄 폭(반각 칸, 한글 1자 = 2칸)
  · name  = CITY·MONSNAME(시프트JIS 0 끝) — 예산 = 원래 바이트 수
  · human / item = HUMAN·ITEM 고정 칸 이름(반각 가타카나) — 예산 = 칸 바이트 수(한글 1자 2 B)
  · exe   = 0.BIN 문자열(제자리, 예산 = 원래 바이트 수) — 후보 걸러냄(가나·한자 2자 이상)
  python tools/extract.py"""
import os, re, struct
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
D = os.path.join(ROOT, 'work', 'disc0')
TALK_W = 44          # 대사 줄 폭(반각 칸) — 원문 최대 44(분포 끝), 창 안쪽 약 24자
SPLIT = 18 * 1024
# 0.BIN 에서 번역 TSV 에 넣지 않는 구역: 엔딩 스태프 롤(50 B 레코드, ⛔허락 없이 손대지 않음) · 이름 입력 글자판(따로 설계)
EXE_SKIP = [(0x3B600, 0x3BB90), (0x3C430, 0x3C6A0)]


def width(s):
    return sum(1 if (ord(c) < 0x80 or 0xFF61 <= ord(c) <= 0xFF9F) else 2 for c in s)


def talks():
    t = open(os.path.join(D, 'TALKS.DAT'), 'rb').read().decode('cp932')
    lines = t.split('\r\n')
    out, sec, cur, start, n = [], '', [], None, 0
    for i, l in enumerate(lines):
        if l.startswith('//'):
            sec = l.strip('/- '); continue
        if start is None:
            start = i
        if l == '#E':
            body = '／'.join(('{%s}' % x) if x.startswith('#') else x for x in cur)
            n += 1
            out.append(('T%04d' % n, 'talk', '%s@%d' % (sec, start), '%d줄·%d칸' % (len(cur), TALK_W), body))
            cur, start = [], None
        else:
            cur.append(l)
    assert cur in ([], ['']), ('끝 #E 없음', cur)   # 파일 끝 0x1A(EOF 표시) 한 줄은 그대로
    return out


def zstrings(fn, kind, pre):
    b = open(os.path.join(D, fn), 'rb').read()
    out = []
    for m in re.finditer(rb'(?:[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc]|[\x20-\x7e\xa1-\xdf])+', b):
        s = m.group()
        try: u = s.decode('cp932')
        except UnicodeDecodeError: continue
        if sum(1 for c in u if ord(c) > 0x3000 or 0xFF61 <= ord(c) <= 0xFF9F) < 2: continue
        out.append(('%s%04d' % (pre, len(out) + 1), kind, '%s@0x%X' % (fn, m.start()), '%dB' % len(s), u.rstrip()))
    return out


def exe():
    b = open(os.path.join(D, '0.BIN'), 'rb').read()
    out = []
    for m in re.finditer(rb'(?:[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc]|[\x20-\x7e\xa1-\xdf])+\x00', b):
        s = m.group()[:-1]
        st = m.start()
        if any(a <= st < b_ for a, b_ in EXE_SKIP): continue
        # 앞 1~3 B 가 반각·ASCII 찌꺼기이고 그 뒤가 4 B 정렬 전각이면 잘라냄(코드 바이트가 붙은 것)
        k = (-st) & 3
        if k and len(s) > k + 2 and all(x < 0x80 or 0xA1 <= x <= 0xDF for x in s[:k]) and 0x81 <= s[k] <= 0xEF:
            s = s[k:]; st += k
        try: u = s.decode('cp932')
        except UnicodeDecodeError: continue
        jp = [c for c in u if 0x3040 <= ord(c) <= 0x30FF or 0x4E00 <= ord(c) <= 0x9FFF or 0xFF61 <= ord(c) <= 0xFF9F or 0xFF10 <= ord(c) <= 0xFF5A]
        kana = [c for c in u if 0x3040 <= ord(c) <= 0x30FF or 0xFF66 <= ord(c) <= 0xFF9D]
        full = [c for c in u if ord(c) > 0x3000 and not 0xFF61 <= ord(c) <= 0xFF9F]
        if len(jp) < 2 or (not kana and len(jp) < 3): continue
        if not full and len(u) < 5: continue                   # 반각 2~4자 = 대부분 코드 바이트
        if st & 1 and len(u) < 4: continue
        if '#E' in u or u.startswith('#'): continue          # 0.BIN 안 별도 대본 조각은 따로 조사
        out.append(('X%04d' % (len(out) + 1), 'exe', '0.BIN@0x%X' % st, '%dB' % len(s), u))
    return out


def write_split(rows):
    od = os.path.join(ROOT, 'my files', 'tsv'); os.makedirs(od, exist_ok=True)
    head = 'id\t종류\t위치\t예산\tJP\tKO\n'
    chunks, cur = [], head
    for r in rows:
        line = '\t'.join(r) + '\t\n'
        if len((cur + line).encode('utf-8')) > SPLIT and cur != head:
            chunks.append(cur); cur = head
        cur += line
    chunks.append(cur)
    if len(chunks) > 1 and len((chunks[-2] + chunks[-1][len(head):]).encode('utf-8')) <= SPLIT:
        last = chunks.pop(); chunks[-1] += last[len(head):]
    for f in os.listdir(od):
        if f.startswith('dbk_') and f.endswith('.tsv'): os.remove(os.path.join(od, f))
    for k, c in enumerate(chunks, 1):
        open(os.path.join(od, 'dbk_%03d.tsv' % k), 'w', encoding='utf-8', newline='\n').write(c)
    return len(chunks)


def main():
    rows = talks() + zstrings('CITY.DAT', 'name', 'C') + zstrings('MONSNAME.DAT', 'name', 'M') \
        + zstrings('HUMAN.DAT', 'human', 'H') + zstrings('ITEM.DAT', 'item', 'I') + exe()
    os.makedirs(os.path.join(ROOT, 'work', 'text'), exist_ok=True)
    with open(os.path.join(ROOT, 'work', 'text', 'jp.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('id\t종류\t위치\t예산\tJP\n')
        for r in rows: f.write('\t'.join(r) + '\n')
    import collections
    c = collections.Counter(r[1] for r in rows)
    chars = collections.Counter()
    for r in rows: chars[r[1]] += len(re.sub(r'\{[^}]*\}|／', '', r[4]))
    n = write_split(rows)
    print('행', len(rows), dict(c), '글자', dict(chars), '· TSV %d개 → my files/tsv/' % n)


if __name__ == '__main__':
    main()
