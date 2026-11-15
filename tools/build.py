# -*- coding: utf-8 -*-
r"""대모험 한글 빌더 + 검사기(2026-11-15)
  번역 입력: work/text/kr/*.tsv (= my files/번역 병합 사본) (extract.py 의 dbk_NNN.tsv 꼴 — id·종류·위치·예산·JP·KO, KO 빈칸 = 원문 그대로)
  python tools/build.py --check   → 검사만(work/text/check.tsv + 요약), 아무것도 안 씀
  python tools/build.py           → work/build/files/ 에 TALKS.DAT·JPNZN12X.FNT·이름 DAT·0.BIN (디스크는 discbuild.py)

  ★TALKS 규칙(게임이 메시지를 «절대 줄 번호»로 찾음, 0.BIN 곳곳에 숫자로 박힘):
    · 메시지 줄 수 ≤ 원문 줄 수, 남는 줄은 #E «뒤» 빈 줄 → 모든 메시지 시작 줄 번호 = 원문
    · 제어 줄 {#?} {#Y} {#N} {#:} {#P} 은 원문과 같은 순서·개수
    · 줄 폭 ≤ 44칸(반각 1·전각/한글 2) · 파일 ≤ 0xEBF0 B(적재 버퍼 고정) · 전체 줄 수 = 원문
  · 이름·exe = 제자리, 바이트 ≤ 원래(남는 자리 0, item 은 반각 공백)
  · 조판: 부호 뒤 공백 지움 · «……»·«...»·«・・・» → 한국식 말줄임 «…» 한 칸 · 반각 ? ! → 전각
  · 글꼴: 한글 = 갈무리11, 한자 칸에 덮어씀(남는 일본어·스태프 롤·이름 입력판이 쓰는 한자는 피함). 글자 없으면 빌드 실패"""
import collections, glob, os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import extract                                    # 이 프로젝트 것(anearth tools 보다 먼저)
sys.path.append(r'C:\claude\project\anearth-kr-patch\tools')
D = os.path.join(ROOT, 'work', 'disc0')
OUT = os.path.join(ROOT, 'work', 'build', 'files')
TALK_W = extract.TALK_W
TALK_MAX = 0xEBF0
GAL = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.bdf'
PUNCT_SP = re.compile(r'([,.!?…、。，．！？：；:;～~・])[ 　]+')
FULL = {'?': '？', '!': '！', '~': '～', '(': '（', ')': '）', ',': '，', ':': '：'}


def width(s):
    return extract.width(s)


# ---------- 제자리 칸 보정(2026-11-15 칸 조사) ----------
EXE_BASE = 0x06004000                 # 0.BIN 적재 주소(IP.BIN 1st read, 크기 칸 0 = 파일 통째)
# ★2026-11-15 정정: 0.BIN 끝(0x60BFF98) 뒤 빈 RAM 은 107 B 뿐 — 처음에 덧붙였다가 실행 중 덮여 백업 RAM 화면이 깨짐.
#   (덤프 위치 0xBBF98 을 주소로 착각.) 옮길 자리 = 0.BIN «안» 0 구간 0x60B9430~0x60BF930(파일 0xB5430~, 25,856 B:
#   파일·스테이트 34장 전부 0, 이 구간 가리키는 리터럴 0). 앞 변수 자리(0x60B9410대)와 떨어뜨려 0x60BC000~0x60BF800.
RELOC_START = 0x060BC000 - EXE_BASE
RELOC_MAX = 0x060BF800 - 0x060BC000
# 추출에서 빠진 0.BIN 문구(이름 입력판 버튼) — 칸 보호도 안 돼 «決» 칸에 한글이 덮였음
def load_extra_exe():
    """work/text/extra_exe.tsv — 추출에서 빠진 짧은 0.BIN 문구(메뉴 2~4자·표 이름, 2026-11-15 실기 지적)"""
    out = {}
    for l in open(os.path.join(ROOT, 'work', 'text', 'extra_exe.tsv'), encoding='utf-8').read().split('\n')[1:]:
        q = l.split('\t')
        if len(q) >= 5 and q[0]: out[q[0]] = (int(q[1], 16), int(q[2]), q[3], q[4])
    return out


EXTRA_EXE = load_extra_exe()
# 추출기가 앞 포인터 꼬리 2 B 를 글자로 읽었거나 첫 반각 글자를 놓친 행 → 진짜 시작
OFFSET_FIX = {'X0006': 0x12FE, 'X0013': 0x513C, 'X0222': 0x229C4, 'X0233': 0x23CB0, 'X0393': 0x3CDB8,
              'X0598': 0x60F0F, 'X0600': 0x60F42,
              # 배·대포 표: 추출기가 앞 가격 바이트(00 뒤)부터 잡아 번역이 가격을 덮던 행(2026-11-15)
              'X0484': 0x60364, 'X0486': 0x6039C, 'X0496': 0x604A4}
# 원문 유지: 세이브 파일 설명(DAIBOKEN_0 앞 ﾀﾞｲﾎﾞｰｹﾝ — 본체 메모리 관리 화면에 그대로 나옴) · 개발용 오류문
KEEP_IDS = {'X0401', 'X0473'}
NAMETAB = (0x60EBA, 0x61023, 17)      # 해적·반지 이름 표: 17 B 간격, 이름 16 B + 0
GOODSTAB = (0x6053C, 0x60866, 18)     # 교역품 표 45개: 18 B 간격, 이름 12 B(ダイヤモンド 가 꽉 참) + 값 4 B(윗 2 B 늘 0) + 2 B


def slot_fix(fn, k, off, bud, kd, b):
    """(오프셋, 예산, 모드) — 모드 'table' = 고정 칸(옮기지 않음), 'keep' = 원문 유지"""
    if k in KEEP_IDS:
        return off, bud, 'keep'
    if k in OFFSET_FIX:
        off = OFFSET_FIX[k]
        bud = b.index(0, off) - off
    if fn == 'HUMAN.DAT' or (fn == '0.BIN' and off in (0x12E0, 0x12FE)):
        # 인물 레코드 30 B: 이름 + 0, 0x11 = 플래그(0 이면 이름 17 B 까지), 0x12~ 능력치
        return off, (17 if b[off + 17] == 0 else 16), 'table'
    if fn == '0.BIN' and NAMETAB[0] <= off < NAMETAB[1] and (off - NAMETAB[0]) % NAMETAB[2] == 0:
        return off, 16, 'table'
    if fn == '0.BIN' and GOODSTAB[0] <= off < GOODSTAB[1] and (off - GOODSTAB[0]) % GOODSTAB[2] == 0:
        return off, 12, 'table'
    if fn == 'ITEM.DAT':
        return off, 16, 'table'       # 레코드 32 B: 글 16 B(무기는 «이름 + 빈칸 + +n» 16 B), 0x19~ 수치
    return off, bud, 'normal'


# 숫자·값 앞 머리말: 게임이 «원문 길이 위치»에 숫자를 써 넣음 → 정확히 원문 길이(짧으면 공백 채움, 길면 안 됨)
#   (2026-11-15 «전원G가» — 全員で 를 4 B 로 줄였더니 숫자가 0 뒤로 가서 안 보임)
EXACT_LEN = {'X0157', 'X0199', 'X0200', 'X0211', 'X0036', 'X0290'}
# 반각 괄호를 그대로 둘 칸(전각으로 바꾸면 뒤 글자 찍는 위치가 어긋남): 전투 «作戦(» + 약자 한 글자 + «)»
NO_NORM = {'XE106'}
NAME_CUT = 8      # 전투 화면 오른쪽 위 이름 칸은 앞 8 B 만 찍음(트레비르=8 B 멀쩡, «리온 아벤추라»는 8번째에서 «벤»이 반 토막)


def name_align(k, s, bud, errs, src):
    """이름이 NAME_CUT 바이트 경계에서 2 B 글자를 반으로 자르면, 첫 반각 공백을 전각으로(모든 글자 2 B 단위 정렬)."""
    def cuts(t):
        p = 0
        for c in t:
            w = 1 if ord(c) < 0x80 else 2
            if p < NAME_CUT < p + w: return True
            p += w
        return False
    # ★인물 이름: 전투 동료 정보에는 앞 8 B 만 복사됨(RAM 0x607E730, «리온 아백ｳ 공격») → 성 앞을 공백으로 채워
    #   성이 9번째 바이트부터 시작하게 = 전투에선 이름만(«리온»), 전체 이름 화면에선 «리온　　아벤추라»
    if ' ' in s and k.startswith(('H', 'X0005', 'X0006')):
        first, rest = s.split(' ', 1)
        fb = sum(1 if ord(c) < 0x80 else 2 for c in first)
        if fb < NAME_CUT:
            pad = NAME_CUT - fb
            t = first + '　' * (pad // 2) + ' ' * (pad % 2) + rest
            if sum(1 if ord(c) < 0x80 else 2 for c in t) <= bud: return t
    if not cuts(s): return s
    t = s.replace(' ', '　', 1)
    nb = sum(1 if ord(c) < 0x80 else 2 for c in t)
    if ' ' in s and nb <= bud and not cuts(t): return t
    errs.append((k, src, '이름이 %d B 경계에서 글자를 자름(전투 화면 이름 칸): %s' % (NAME_CUT, s)))
    return s


def item_layout(k, s, orig, errs, src):
    """무기·방어구 = 이름 + 빈칸 + 원래 «+n» 3 B 를 16 B 에(+ 는 13번째 바이트). 그 밖 = 그대로."""
    if orig[13:14] != b'+':
        return s
    name = re.sub(r'[\s　]*[+＋][\s　]*\d+[\s　]*$', '', s).rstrip(' 　')
    nb = sum(1 if ord(c) < 0x80 else 2 for c in name)
    if nb > 12:
        errs.append((k, src, '무기 이름 %d B > 12 B(+n 앞 칸): %s' % (nb, name)))
        return None
    return name + ' ' * (13 - nb) + orig[13:16].decode('ascii')


def norm(s):
    """번역 조판(쓰는 순간): 말줄임 → … 한 칸, 부호 뒤 공백 삭제, 반각 부호 → 전각"""
    # ★{#?} 같은 제어 토큰 안은 손대지 않는다(전각 «#？» 로 바뀌면 제어 줄이 깨짐, 2026-11-15)
    parts = re.split(r'(\{[^}]*\})', s)
    for i in range(0, len(parts), 2):
        t = parts[i].replace('……', '…').replace('...', '…').replace('・・・', '…')
        t = re.sub(r'．{2,}', '…', t)            # 0.BIN 전투 문구의 «．．．» 도 한국식 말줄임 한 칸
        t = re.sub(r'…+', '…', t)
        t = ''.join(FULL.get(c, c) for c in t)
        parts[i] = PUNCT_SP.sub(r'\1', t)
    return ''.join(parts)


def load_ko():
    ko = {}
    kodir = sys.argv[sys.argv.index('--ko') + 1] if '--ko' in sys.argv else os.path.join(ROOT, 'work', 'text', 'kr')   # my files/번역 병합 사본(하스피 원본은 읽기만)
    for f in sorted(glob.glob(os.path.join(kodir, '*.tsv'))):
        for ln, line in enumerate(open(f, encoding='utf-8-sig'), 1):
            p = line.rstrip('\r\n').split('\t')
            if ln == 1 and p[0] == 'id': continue
            if len(p) >= 6 and p[5].strip() and p[5] != p[4]:   # KO = JP 그대로 = 미번역(잡음 행 포함)
                ko[p[0]] = (p[5], '%s:%d' % (os.path.basename(f), ln))
    return ko


def talk_messages():
    """원문 TALKS → [(id, 시작 줄, 내용 줄들)] + 전체 줄"""
    t = open(os.path.join(D, 'TALKS.DAT'), 'rb').read().decode('cp932')
    lines = t.split('\r\n')
    msgs, cur, start, n = [], [], None, 0
    for i, l in enumerate(lines):
        if l.startswith('//'): continue
        if start is None: start = i
        if l == '#E':
            n += 1; msgs.append(('T%04d' % n, start, cur)); cur, start = [], None
        else:
            cur.append(l)
    return lines, msgs


def main():
    check = '--check' in sys.argv
    ko = load_ko()
    rows = {r[0]: r for r in (l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'work', 'text', 'jp.tsv'), encoding='utf-8')) if r[0] != 'id'}
    errs = []
    _b0 = open(os.path.join(D, '0.BIN'), 'rb').read()
    for k, (off, bud, jp, kr) in EXTRA_EXE.items():
        assert _b0[off:off + bud].decode('cp932') == jp, (k, hex(off), _b0[off:off + bud])
        rows[k] = [k, 'exe', '0.BIN@0x%X' % off, '%dB' % bud, jp, '']
        ko.setdefault(k, (kr, 'build.py:EXTRA_EXE'))
    unknown = [k for k in ko if k not in rows]
    for k in unknown: errs.append((k, ko[k][1], '원문표에 없는 id'))

    # ---------- TALKS ----------
    lines, msgs = talk_messages()
    new_lines = list(lines)
    for mid, start, body in msgs:
        if mid not in ko: continue
        txt, src = ko[mid]
        segs = [norm(x) for x in txt.split('／')]
        new = []
        for s in segs:
            m = re.fullmatch(r'\{(#[^}]*)\}', s.strip())   # {#?} 뿐 아니라 {#G-53}·{#P・・・・}·{#E //..//} 도 제어 줄
            new.append(m.group(1) if m else s)
        otok = [x for x in body if x.startswith('#')]; ntok = [x for x in new if x.startswith('#')]
        bad = []
        if otok != ntok: bad.append('제어 줄 다름 %s → %s' % (otok, ntok))
        if any(re.search(r'\{#|#[A-Z?:]', x) for x in new if not x.startswith('#')): bad.append('줄 안에 제어 토큰')
        if len(new) > len(body): bad.append('줄 수 %d > 원문 %d' % (len(new), len(body)))
        for x in new:
            if not x.startswith('#') and width(x) > TALK_W: bad.append('줄 폭 %d > %d: %s' % (width(x), TALK_W, x))
        if bad:
            for b in bad: errs.append((mid, src, b))
            continue
        # 메시지 자리: start ~ start+len(body) 내용, 그 다음 줄 #E → 내용 new + #E + 빈 줄(남는 만큼)
        assert new_lines[start + len(body)] == '#E'
        blk = new + ['#E'] + [''] * (len(body) - len(new))
        new_lines[start:start + len(body) + 1] = blk
    assert len(new_lines) == len(lines)

    # ---------- 이름·exe(제자리) ----------
    inplace = collections.defaultdict(list)          # 파일 → [(오프셋, 예산, 새 텍스트, kind, id, src)]
    for k, (txt, src) in ko.items():
        r = rows.get(k)
        if not r or r[1] == 'talk': continue
        fn, off = r[2].split('@'); off = int(off, 16); bud = int(r[3].rstrip('B'))
        s = txt if k in NO_NORM else norm(txt)
        if '／' in s: errs.append((k, src, '줄바꿈(／) 불가 칸')); continue
        inplace[fn].append((off, bud, s, r[1], k, src))

    # ---------- 글자 ----------
    used = set()
    for x in new_lines:
        used |= set(x)
    for fn, lst in inplace.items():
        for o, b, s, kd, k, src in lst: used |= set(s)
    hang = sorted(c for c in used if '가' <= c <= '힣')
    fb = bytearray(open(os.path.join(D, 'JPNZN12X.FNT'), 'rb').read())
    nb = fb[17]; blocks = [struct.unpack_from('<HH', fb, 18 + 4 * i) for i in range(nb)]; gbase = 18 + 4 * nb

    def gidx(code):
        n = 0
        for s_, e in blocks:
            if s_ <= code <= e: return n + code - s_
            n += e - s_ + 1
        return None
    # 피해야 할 한자 = 번역 후에도 남는 일본어(번역 안 된 줄·스태프 롤·이름 입력판·exe 전체 원문 중 미번역)가 쓰는 글자
    keep = set()
    for x in new_lines: keep |= {c for c in x if ord(c) > 0x3000}
    bin0 = open(os.path.join(D, '0.BIN'), 'rb').read()
    for a, b in extract.EXE_SKIP:
        keep |= set(bin0[a:b].decode('cp932', 'ignore'))
    for k, r in rows.items():
        if r[1] != 'talk' and k not in ko: keep |= set(r[4])
    keepcodes = set()
    for c in keep:
        try:
            e = c.encode('cp932')
            if len(e) == 2: keepcodes.add(struct.unpack('>H', e)[0])
        except UnicodeEncodeError: pass
    free = []
    c = 0x889F
    while len(free) < len(hang) and c <= 0x9FFC:
        lo = c & 0xFF
        if 0x40 <= lo <= 0xFC and lo != 0x7F and c not in keepcodes and gidx(c) is not None: free.append(c)
        c += 1
    if len(free) < len(hang): errs.append(('-', '-', '한자 칸 모자람 %d < %d' % (len(free), len(hang))))
    enc = dict(zip(hang, free))

    def sj(s, where):
        o = bytearray()
        for ch in s:
            if ch in enc: o += struct.pack('>H', enc[ch])
            else:
                try: o += ch.encode('cp932')
                except UnicodeEncodeError:
                    errs.append((where[0], where[1], '글자 없음 %r' % ch)); o += b'?'
        return bytes(o)

    # 인코딩·바이트 예산 검사
    tb = bytearray()
    srcmap = {start: (mid, ko[mid][1]) for mid, start, body in msgs if mid in ko}
    for i, x in enumerate(new_lines):
        w = srcmap.get(i, ('TALKS', '줄 %d' % i))
        tb += (b'\x1a' if x == '\x1a' else sj(x, w))
        if i < len(new_lines) - 1: tb += b'\r\n'
    if len(tb) > TALK_MAX: errs.append(('TALKS', '-', '파일 %d B > 적재 버퍼 %d B' % (len(tb), TALK_MAX)))
    files = {}
    reloc_n = 0
    for fn, lst in inplace.items():
        b = bytearray(open(os.path.join(D, fn), 'rb').read())
        ptrs = None
        if fn == '0.BIN':
            ptrs = collections.defaultdict(list)          # 4 B 정렬 BE32 = 포인터(리터럴 풀·자료 표)
            for i in range(0, len(b) - 3, 4):
                v = struct.unpack_from('>I', b, i)[0]
                if EXE_BASE <= v < EXE_BASE + len(b): ptrs[v].append(i)
            tail = bytearray()                              # 0.BIN 안 빈 구간(RELOC_START~)에 쓸 옮긴 문자열
        for off, bud, s, kd, k, src in lst:
            off, bud, mode = slot_fix(fn, k, off, bud, kd, b)
            if mode == 'keep':
                continue                                     # 원문 유지(세이브 설명·개발용 문구)
            if kd == 'human' or (fn == '0.BIN' and (off in (0x12E0, 0x12FE) or (NAMETAB[0] <= off < NAMETAB[1] and (off - NAMETAB[0]) % NAMETAB[2] == 0))):
                s = name_align(k, s, bud, errs, src)
            if kd == 'item':
                s = item_layout(k, s, b[off:off + 16], errs, src)
                if s is None: continue
            e = sj(s, (k, src))
            if len(e) > bud:
                refs = ptrs.get(EXE_BASE + off, []) if ptrs is not None else []
                if refs and mode != 'table':
                    # ★0.BIN 안 빈 구간(RELOC_START~)으로 옮기고 포인터 교체
                    while len(tail) % 4: tail += b'\0'
                    na = EXE_BASE + RELOC_START + len(tail)
                    tail += e + b'\0'
                    for r in refs: struct.pack_into('>I', b, r, na)
                    reloc_n += 1
                    continue
                errs.append((k, src, '%d B > 예산 %d B: %s' % (len(e), bud, s))); continue
            # 원문이 공백으로 끝을 채운 칸(배·대포 이름 «ケッチ　　», 메뉴 «戦闘　　»)은 원문 글 길이까지 반각 공백으로 채움
            #   — 뒤에 이어 찍는 값(가격) 열이 원문처럼 맞는다. 그 밖은 0(무기 이름은 item_layout 이 16 B 꽉 채움)
            ob = bytes(b[off:off + bud]).split(b'\0')[0]
            if kd == 'exe' and (ob.endswith((b' ', b'\x81\x40')) or 0x60340 <= off < 0x60520 or k in EXACT_LEN) and len(e) < len(ob):
                e = e + b' ' * (len(ob) - len(e))
            b[off:off + bud] = e + b'\0' * (bud - len(e))
        if fn == '0.BIN':
            if len(tail) > RELOC_MAX: errs.append(('0.BIN', '-', '옮긴 문자열 %d B > 빈 RAM %d B' % (len(tail), RELOC_MAX)))
            else:
                assert not any(b[RELOC_START:RELOC_START + len(tail)])
                b[RELOC_START:RELOC_START + len(tail)] = tail
        files[fn] = bytes(b)
    if reloc_n: print('   0.BIN 문구 %d개(%d B)를 0x%X~ 빈 구간으로 옮김(포인터 교체)' % (reloc_n, len(tail), EXE_BASE + RELOC_START))

    # ---------- 보고 ----------
    os.makedirs(os.path.join(ROOT, 'work', 'text'), exist_ok=True)
    with open(os.path.join(ROOT, 'work', 'text', 'check.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('id\t파일:줄\t문제\n')
        for e in errs: f.write('\t'.join(e) + '\n')
    nt = sum(1 for mid, _, _ in msgs if mid in ko)
    print('번역 %d행(대사 %d/%d) · 한글 %d자(칸 %d) · TALKS %d/%d B · 문제 %d건 → work/text/check.tsv'
          % (len(ko), nt, len(msgs), len(hang), len(free), len(tb), TALK_MAX, len(errs)))
    for e in errs[:15]: print('  ', *e)
    if check: return
    if errs: sys.exit('⛔문제가 있어 빌드 안 함')

    # ---------- 쓰기 ----------
    from bdf import Font
    sys.path.insert(0, HERE)
    import poc
    f = Font(GAL)
    for ch, code in enc.items():
        i = gidx(code); fb[gbase + 24 * i:gbase + 24 * i + 24] = poc.glyph(f, ch)
    # 한국식 말줄임: 0x8163 «…» 칸 = 바닥선 점 셋
    i = gidx(0x8163); rows12 = [0] * 12
    for x in (1, 5, 9): rows12[10] |= 1 << (15 - x)
    fb[gbase + 24 * i:gbase + 24 * i + 24] = b''.join(struct.pack('>H', r) for r in rows12)
    os.makedirs(OUT, exist_ok=True)
    for f_ in os.listdir(OUT): os.remove(os.path.join(OUT, f_))
    open(os.path.join(OUT, 'TALKS.DAT'), 'wb').write(bytes(tb))
    open(os.path.join(OUT, 'JPNZN12X.FNT'), 'wb').write(fb)
    for fn, b in files.items(): open(os.path.join(OUT, fn), 'wb').write(b)
    # 타이틀 부제 그림 «세인트 엘모스의 기적»(하스피 글꼴 결정 = 주아, 2026-11-15)
    import subprocess
    subprocess.run([sys.executable, os.path.join(HERE, 'title_sub.py'), '--font', '주아', '--write'], check=True)
    orig = open(os.path.join(D, 'TALKS.DAT'), 'rb').read()
    print('쓰기 OK %s · TALKS 원본과 %s' % (sorted(['TALKS.DAT', 'JPNZN12X.FNT'] + list(files)), '같음' if bytes(tb) == orig else '다름'))


if __name__ == '__main__':
    main()
