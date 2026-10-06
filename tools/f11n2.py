# -*- coding: utf-8 -*-
"""F11N(혁신판) 전체 파서: 팔레트 전용 변형(플래그 0x10000, 픽셀 없음)은 직전 픽셀을 공유."""
import struct, numpy as np
from f11n import unswizzle
def parse(d):
    A, B, C = struct.unpack_from('<III', d, 4)
    spr = [struct.unpack_from('<IHHII', d, 0x10 + i*16) for i in range(B)]
    off = 0x10 + B*16; tx = []; lastpix = None
    for t in range(A):
        size, w, h, sw, sh, bpp, pad = struct.unpack_from('<7I', d, off + 4)
        b = bpp & 0xFF; nc = 16 if b == 4 else 256
        po = off + 32; xo = po + nc*4
        has = size > 32 + nc*4
        tex = dict(i=t, off=off, size=size, w=w, h=h, sw=sw, sh=sh, bpp=b, pal_off=po, pix_off=xo if has else None)
        pal = np.frombuffer(d, np.uint8, nc*4, po).reshape(nc, 4)
        tex['pal'] = unswizzle(pal) if nc == 256 else pal.copy()
        if has:
            if b == 4:
                r = np.frombuffer(d, np.uint8, sw*sh//2, xo); idx = np.stack([r & 15, r >> 4], 1).reshape(sh, sw)
            else:
                idx = np.frombuffer(d, np.uint8, sw*sh, xo).reshape(sh, sw)
            lastpix = (t, idx)
        tex['idx'] = lastpix[1] if lastpix else None
        tex['pixsrc'] = lastpix[0] if lastpix else None
        tx.append(tex); off += size
    return spr, tx
def rgba(tex, idx=None):
    p = tex['pal'].astype(int); p[:, 3] = np.minimum(p[:, 3]*2, 255)
    i = tex['idx'] if idx is None else idx
    return p[i].astype(np.uint8)
def sxy(s):
    xy, w, h, t, c = s
    return xy & 0xFFFF, xy >> 16, w, h, t, c
