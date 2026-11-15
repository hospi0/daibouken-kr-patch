# -*- coding: utf-8 -*-
"""0.BIN 문장 조각 정리(2026-11-15 하스피 «그냥 지금 줄여» «은(는) 없애는 방향으로 늘 그랬듯»)
  · 이름·숫자 사이에 끼는 조각을 원문 바이트 길이 안으로(작은 버퍼 넘침 예방)
  · 이름 뒤 조사 쌍 은(는)·을(를)·이(가)·와(과) 없앰 — 조사가 필요 없는 문장으로
  python tools/fix_frag_20261115.py [--apply]
"""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW = {
    # 이름 뒤 조각(조사 쌍 없앰)
    'X0009': ' 침몰했다!',            # が沈没した！ 12
    'X0043': ' 침몰했다!',
    'X0011': ' 기적적으로 생존',       # は奇跡的に助かった 18
    'X0200': ' 보상 판매로 ',          # を下取りして 12
    'X0244': ' 잔여 ',                # はあと 6
    'X0245': '회',                    # 回使える 8
    'X0246': '의ＨＰ가',               # はＨＰが 8
    'X0254': '：편성에서 못 뺍니다',    # をはずすことはできません 24
    'X0315': ' 출현!!!',              # が現れた！！！ 14
    'X0322': ' 기절했다…',            # は気絶した．．． 17
    'X0323': ' 대미지를 받았다',       # のダメージをうけた 19
    'X0325': ' 방어 중',              # は防御している 15
    'X0329': ' 자세를 잡았다',         # は身構えている 15
    'X0330': ' 사용',                 # をつかった 11
    'X0335': ' 부활했다!',            # は復活した！ 13
    'X0336': ' 멀쩡한 듯하다…',        # は元気なようだ．．． 21
    'X0341': ' 격파!',                # をたおした 10
    'X0344': ' 레벨 업!',             # はレベルがあがった！ 21
    'X0346': ' 달성!!',               # になった！！ 13
    'X0348': ' 습득!',                # をおぼえた！ 12
    'X0388': ' 보물을 갖고 있었다!!',   # は宝物を持っていた！！ 23
    'X0389': ' 획득!!!',              # を手に入れた！！！ 19
    'X0390': '획득!!!',               # 手に入れた！！！ 16
    # 그 밖 조각 원문 길이로
    'X0251': '개 사용',               # 個使った 8
    'X0320': '의 공격',               # の攻撃！ 8
    'X0326': '의 공격',               #  の攻撃 7
    'X0332': '의 ＨＰ가 ',            #  のＨＰが  10
    'X0343': ' Ｇ 획득',              #  Ｇ を得た 10
    'X0026': '기함 공격',             # 旗艦を狙え 10
    'X0027': '직접 지휘',             # 命令させろ 10
    'X0211': '전원',                  # 全員で 6
    'X0402': ' 뒤　로',               #  戻　る 7
    'X0412': '카트리지',              # ｶｰﾄﾘｯｼﾞ  8
}
EXTRA = {
    'XE045': ' ： ',                  #  は  4 → «리온 ： 12 대미지를 받았다»
    'XE046': ' ： ',                  #  を  4 → «A 및 B ： 획득!!!»
    'XE107': ' 및 ',                  #  と  4
}


def main():
    apply = '--apply' in sys.argv
    n = 0
    for f in sorted(glob.glob(os.path.join(ROOT, 'work', 'text', 'kr', '*.tsv'))):
        L = open(f, encoding='utf-8-sig').read().split('\n'); ch = False
        for i, l in enumerate(L):
            p = l.split('\t')
            if len(p) >= 6 and p[0] in NEW and p[5] != NEW[p[0]]:
                print('%s  %r → %r' % (p[0], p[5], NEW[p[0]])); p[5] = NEW[p[0]]; L[i] = '\t'.join(p); ch = True; n += 1
        if ch and apply:
            open(f, 'w', encoding='utf-8', newline='').write('\n'.join(L))
    f = os.path.join(ROOT, 'work', 'text', 'extra_exe.tsv')
    L = open(f, encoding='utf-8').read().split('\n'); ch = False
    for i, l in enumerate(L):
        q = l.split('\t')
        if len(q) >= 5 and q[0] in EXTRA and q[4] != EXTRA[q[0]]:
            print('%s  %r → %r' % (q[0], q[4], EXTRA[q[0]])); q[4] = EXTRA[q[0]]; L[i] = '\t'.join(q); ch = True; n += 1
    if ch and apply:
        open(f, 'w', encoding='utf-8', newline='').write('\n'.join(L))
    print('%d행 %s' % (n, '반영' if apply else '미리보기'))


if __name__ == '__main__':
    main()
