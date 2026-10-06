# -*- coding: utf-8 -*-
"""ELF 문자열 교체(안전판).
문자열 사이 0 영역에는 전역 변수가 섞여 있으므로 절대 쓰지 않는다.
- 제자리: 원문 길이를 4바이트 정렬한 범위(room) 안이면 그 자리에.
- 넘치면: 다른 문자열이 줄어들어 생긴 '원래 문자열 바이트' 공간(pool)으로 옮기고
  데이터 포인터와 addiu 하위값을 고친다. 64 KiB 경계를 넘길 때는
  lui가 해당 addiu에서만 소비되는지 확인하고 상위값도 함께 고친다.
- 옮길 수 없으면 원문 유지."""
import struct
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from codec import encode

def va(o): return o - 0x80 + 0x100000
def off(v): return v - 0x100000 + 0x80
TEXT_END = 0x80 + 0x5d8380
REPORT = []

def exclusive_lui(elf, addiu):
    """Find an exclusively consumed high half, safe to relocate across 64 KiB.
    The low instruction must overwrite its own source. Reject every intervening
    read/write of that register and every control transfer, including delay slots.
    """
    w = struct.unpack_from('<I', elf, addiu)[0]
    reg = (w >> 21) & 31
    if w >> 26 != 9 or ((w >> 16) & 31) != reg or not reg: return None
    for p in range(addiu-4, max(0x7c, addiu-164), -4):
        v = struct.unpack_from('<I', elf, p)[0]
        op, rs, rt, rd = v >> 26, (v >> 21) & 31, (v >> 16) & 31, (v >> 11) & 31
        if op == 15 and rt == reg: return p
        if op in (1,2,3,4,5,6,7,20,21,22,23) or (op == 0 and (v & 63) in (8,9)): return None
        if rs == reg or rt == reg or (op in (0,28) and rd == reg): return None
    return None

def code_refs(elf, targets):
    """target VA 집합 -> [(addiu 파일오프셋, target)] (lui+addiu 쌍)"""
    out = []
    lui = {}
    for o in range(0x80, TEXT_END, 4):
        w = struct.unpack_from('<I', elf, o)[0]
        op = w >> 26; rt = (w >> 16) & 31; rs = (w >> 21) & 31; imm = w & 0xffff
        if op == 0x0f: lui[rt] = (imm << 16, o); continue
        if op == 0x09 and rs in lui:
            hi, lo = lui[rs]
            if o - lo > 160: continue
            a = (hi + (imm - 0x10000 if imm & 0x8000 else imm)) & 0xffffffff
            if a in targets: out.append((o, a))
    return out

def apply(elf, items, warn):
    """items: [(파일오프셋, 원문 bytes, 새 bytes)]"""
    elf = bytearray(elf)
    REPORT.clear()
    pool = []
    over = []
    for oo, ob, nb in items:
        n = len(ob)
        room = ((n + 1 + 3) & ~3) - 1
        if len(nb) <= room:
            end = oo + max(n, len(nb))
            elf[oo:oo+len(nb)] = nb
            for x in range(oo + len(nb), end + 1): elf[x] = 0
            if n - len(nb) >= 3: pool.append([oo + len(nb) + 1, n - len(nb)])   # 원래 문자열 바이트만
            REPORT.append(dict(source=oo, target=oo, length=len(nb), encoded=nb.hex(), code_refs=[], data_refs=[]))
        else:
            over.append((oo, ob, nb))
    if not over: return bytes(elf), 0
    tv = {va(oo): (oo, ob, nb) for oo, ob, nb in over}
    dp = {}
    for i in range(0x80, len(elf) - 4, 4):
        w = struct.unpack_from('<I', elf, i)[0]
        if w in tv: dp.setdefault(w, []).append(i)
    cr = {}
    for o, a in code_refs(bytes(elf), set(tv)):
        cr.setdefault(a, []).append(o)
    moved = 0
    for v, (oo, ob, nb) in sorted(tv.items(), key=lambda row: len(row[1][2]), reverse=True):
        need = len(nb) + 1
        codes = cr.get(v, [])
        high_refs = {c: exclusive_lui(elf, c) for c in codes}
        if not codes and not dp.get(v):
            warn('ELFKEEP unreferenced', hex(oo), ob, nb); continue
        hi = (v + 0x8000) >> 16
        slot = None
        for fr in sorted(pool, key=lambda region: region[1]):
            if fr[1] < need: continue
            nv = va(fr[0])
            if codes and ((nv + 0x8000) >> 16) != hi and any(p is None for p in high_refs.values()): continue
            slot = fr; break
        if slot is None:
            warn('ELFKEEP', hex(oo), ob, nb); continue
        at = slot[0]; slot[0] += need; slot[1] -= need
        elf[at:at+len(nb)] = nb; elf[at+len(nb)] = 0
        nv = va(at)
        for i in dp.get(v, []): struct.pack_into('<I', elf, i, nv)
        for o in codes:
            w = struct.unpack_from('<I', elf, o)[0]
            struct.pack_into('<I', elf, o, (w & 0xffff0000) | (nv & 0xffff))
            if ((nv + 0x8000) >> 16) != hi:
                p = high_refs[o]
                w = struct.unpack_from('<I', elf, p)[0]
                struct.pack_into('<I', elf, p, (w & 0xffff0000) | ((nv + 0x8000) >> 16))
        REPORT.append(dict(source=oo, target=at, length=len(nb), encoded=nb.hex(), code_refs=codes,
                           data_refs=dp.get(v, []), high_refs={str(k): p for k,p in high_refs.items()}))
        moved += 1
    return bytes(elf), moved
