# -*- coding: utf-8 -*-
"""한글(2바이트) 글자 표시 폭/소형 모드 패치.
- 원본: 2바이트 글자는 항상 20x20 으로 그리고 폭 20 으로 진행. 영문 '소형 2줄 모드'(t3==1, 10x10)에서도
  2바이트만 20x20 이라 두 줄이 겹친다.
- 패치: 폭 W(기본 18), 소형 모드에서는 WS(12) x HS(10).
코드 동굴: MPEG 미지원 기능 에러 문자열 자리(파일 0x533298~, VA 0x633218), 게임 영상에서 쓰이지 않음."""
import struct

W = 18
WS = 12   # 소형 모드의 한글 진행폭
HS = 10   # 원본 10px 줄 간격을 넘기지 않도록 높이는 별도 지정
CAVE_OFF = 0x533298
def va(o): return o - 0x80 + 0x100000
def off(v): return v - 0x100000 + 0x80
def J(t): return 0x08000000 | ((t >> 2) & 0x3ffffff)
def JAL(t): return 0x0C000000 | ((t >> 2) & 0x3ffffff)
def ADDIU(rt, rs, imm): return (9 << 26) | (rs << 21) | (rt << 16) | (imm & 0xffff)
def ADDU(rd, rs, rt): return (rs << 21) | (rt << 16) | (rd << 11) | 0x21
def LW(rt, o, base): return (0x23 << 26) | (base << 21) | (rt << 16) | (o & 0xffff)
def SW(rt, o, base): return (0x2b << 26) | (base << 21) | (rt << 16) | (o & 0xffff)
def BNE(rs, rt, n): return (5 << 26) | (rs << 21) | (rt << 16) | (n & 0xffff)
JR_RA = 0x03e00008; NOP = 0
zero, at, v0, v1, a0, a1, a2, a3 = 0, 1, 2, 3, 4, 5, 6, 7
t0, t1, t2, t3, t4, t5, t6 = 8, 9, 10, 11, 12, 13, 14
s1, s4, s5, sp, ra = 17, 20, 21, 29, 31
SLOT = 0x120   # 0x199db0 프레임의 미사용 칸

def apply(elf, warn):
    elf = bytearray(elf)
    def put(va_, old, new):
        o = off(va_)
        cur = struct.unpack_from('<I', elf, o)[0]
        if cur != old: warn('FONTPATCH mismatch', hex(va_), hex(cur)); return False
        struct.pack_into('<I', elf, o, new); return True
    cave = []
    base = va(CAVE_OFF)
    def here(): return base + 4 * len(cave)
    # C1: 0x199db0 진입 - t3(소형 플래그) 저장
    c1 = here()
    cave += [0x0140882d, SW(t3, SLOT, sp), JR_RA, NOP]
    # C2: 2바이트 그리기 사각형 크기 -> t5(폭), a1 = s4 + 높이
    c2 = here()
    cave += [LW(t4, SLOT, sp), ADDIU(t5, zero, W), ADDIU(t6, zero, 20), ADDIU(at, zero, 1),
             BNE(t4, at, 3), NOP, ADDIU(t5, zero, WS), ADDIU(t6, zero, HS),
             JR_RA, ADDU(a1, s4, t6)]
    # C3: 폭 함수 0x19a930 2바이트 분기 -> v0 = (a1==1 ? W/2 : W), 0x19aa88 로
    c3 = here()
    cave += [ADDIU(v0, zero, W), ADDIU(at, zero, 1), BNE(a1, at, 2), NOP, ADDIU(v0, zero, WS),
             J(0x19aa88), NOP]
    # C4: 폭 함수 0x199550 2바이트 분기 -> 0x1995e4 로
    c4 = here()
    cave += [ADDIU(v0, zero, W), ADDIU(at, zero, 1), BNE(a1, at, 2), NOP, ADDIU(v0, zero, WS),
             J(0x1995e4), NOP]
    # C5: 소형 렌더 루프(0x199b68) 2바이트 진행폭
    c5 = here()
    s2 = 18
    cave += [BNE(s4, at, 2), ADDIU(s2, s2, W), ADDIU(s2, s2, WS - W), J(0x199ba0), NOP]
    cave += [0, 0]
    blob = struct.pack('<%dI' % len(cave), *cave)
    assert len(blob) <= 0xE0
    elf[CAVE_OFF:CAVE_OFF + len(blob)] = blob
    ok = all([
        put(0x199dec, ADDU(s1, t2, zero) if False else 0x0140882d, JAL(c1)),
        put(0x19a260, ADDIU(a1, s4, 0x14), JAL(c2)),
        put(0x19a26c, ADDIU(v1, s5, 0x14), ADDU(v1, s5, t5)),
        put(0x19a9b8, 0x10000033, J(c3)),
        put(0x1995c4, 0x10000007, J(c4)),
        put(0x199b6c, 0x1000000c, J(c5)),
        put(0x199b70, ADDIU(18, 18, 0x14), ADDIU(at, zero, 1)),
        put(0x1992b8, ADDIU(t0, zero, 0x14), ADDIU(t0, zero, W)),
        # 두 줄 이름("%s<LF>%s": 이름, 성) -> 한 줄 "%s %s": 성, 이름
        put(0x1ee464, 0x24a53a00, 0x24a53a08),
        put(0x1ee468, 0x26260010, 0x26260004),
        put(0x1ee470, 0x26270004, 0x26270010),
    ])
    # 13바이트 고정 표(0x5413c8~): Yes/No/N/A/None
    from codec import encode
    for o, k in ((0x5413d5, '예'), (0x5413e2, '아니요'), (0x5413ef, '없음'), (0x5413fc, '없음')):
        b = encode(k); elf[o:o+13] = b + bytes(13 - len(b))
    return bytes(elf)
