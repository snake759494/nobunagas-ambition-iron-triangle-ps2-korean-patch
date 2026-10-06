# -*- coding: utf-8 -*-
"""F11N 그림 묶음(혁신판).
0x00 'F11N' u32 텍스처수 A, u32 스프라이트수 B, u32 C
0x10 스프라이트[B] 16B
텍스처: 'T11N' u32 블록크기, u32 w, u32 h, u32 저장w, u32 저장h, u32 bpp(4 | 9=8bpp, 상위 플래그 가능), 0x99999999,
  팔레트(4bpp 16색, 8bpp 256색 RGBA, 8bpp 는 CSM1 배열), 픽셀(저장w x 저장h, 4bpp 하위 니블 왼쪽)"""
import struct
import numpy as np

def unswizzle(p):
    p = p.copy()
    for b in range(0, 256, 32):
        a = p[b+8:b+16].copy(); p[b+8:b+16] = p[b+16:b+24]; p[b+16:b+24] = a
    return p

def parse(d):
    assert d[:4] == b'F11N'
    A, B, C = struct.unpack_from('<III', d, 4)
    off = 0x10 + B * 16
    texs = []
    for t in range(A):
        assert d[off:off+4] == b'T11N', (t, hex(off))
        size, w, h, sw, sh, bpp, pad = struct.unpack_from('<7I', d, off + 4)
        b = bpp & 0xFF
        ncol = 16 if b == 4 else 256
        po = off + 32
        pal = np.frombuffer(d, np.uint8, ncol * 4, po).reshape(ncol, 4)
        if ncol == 256: pal = unswizzle(pal)
        xo = po + ncol * 4
        if b == 4:
            raw = np.frombuffer(d, np.uint8, sw * sh // 2, xo)
            idx = np.stack([raw & 15, raw >> 4], 1).reshape(sh, sw)
        else:
            idx = np.frombuffer(d, np.uint8, sw * sh, xo).reshape(sh, sw)
        texs.append(dict(off=off, size=size, w=w, h=h, sw=sw, sh=sh, bpp=b, flag=bpp >> 8, pal=pal,
                         idx=idx, pal_off=po, pix_off=xo))
        off += size
    return texs

def to_rgba(t):
    pal = t['pal'].astype(np.int32).copy()
    pal[:, 3] = np.minimum(pal[:, 3] * 2, 255)
    return pal[t['idx'][:t['h'], :t['w']]].astype(np.uint8)
