# -*- coding: utf-8 -*-
"""GRAPHRES 31번 = 게임 2바이트 글꼴.
글리프 3487개 x 224B: [GIF 태그 16B][20x20 4bpp 200B][패딩 8B], 하위 니블이 왼쪽 픽셀.
원본 값 14(0xE)=투명. 북미 렌더러는 0~15를 알파로 사용하므로
한글뿐 아니라 남겨 쓰는 원본 기호도 14 -> 0 변환해야 한다.
ELF 0x535580 u16 조회표: SJIS 칸 k=(상위-0x81 또는 -0xC1)*256+하위 -> 글리프 번호.
한글: KS X 1001 2350자를 SJIS 0x889F 이후 유효 칸(조회표 값 있음)에 순서대로 배정."""
import struct, json, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLE_OFF = 0x535580
TABLE_N = 11136
GB = 224
TRANS = 14

def k_of(c):
    hi, lo = c >> 8, c & 255
    return (hi - 0x81 if hi < 0xA0 else hi - 0xC1) * 256 + lo

def read_table(elf):
    return struct.unpack_from('<%dH' % TABLE_N, elf, TABLE_OFF)

def hangul2350():
    return [bytes([h, l]).decode('euc-kr') for h in range(0xB0, 0xC9) for l in range(0xA1, 0xFF)]

def slots(elf, n):
    tab = read_table(elf)
    out = []
    for hi in list(range(0x88, 0xA0)) + list(range(0xE0, 0xF0)):
        for lo in list(range(0x40, 0x7F)) + list(range(0x80, 0xFD)):
            c = hi << 8 | lo
            if c < 0x889F or lo == 0x5C: continue   # 0x5C('\') 둘째 바이트는 제어문자 해석과 충돌 우려
            k = k_of(c)
            if k >= TABLE_N or tab[k] == 0xFFFF: continue
            out.append((c, tab[k]))
            if len(out) == n: return out
    raise ValueError('slots')

def decode(font, i):
    b = np.frombuffer(font[i*GB+16:i*GB+216], np.uint8)
    return np.stack([b & 15, b >> 4], 1).reshape(20, 20)

def encode(g):
    g = np.asarray(g, np.uint8).reshape(-1)
    return (g[0::2] | (g[1::2] << 4)).astype(np.uint8).tobytes()

def render(ch, fnt, size, dy=0):
    # Native-size FreeType coverage only: no resampling, gamma, stroke or shadow.
    im = Image.new('L', (20, 20), 0)
    f = ImageFont.truetype(fnt, size)
    ImageDraw.Draw(im).text((10, 10 + dy), ch, 255, font=f, anchor='mm')
    return np.asarray(im, np.float32) / 255

def to_glyph(cov):
    # 영문판 팔레트: 0=투명 ~ 15=글자색(알파 단계). 외곽선 없이 덮임 정도만.
    v = np.clip(np.rint(cov * 15), 0, 15).astype(np.uint8)
    return v

def build(elf, font_bytes, chars, fnt, size, dy=0):
    font = bytearray(font_bytes)
    # Original Japanese punctuation otherwise appears as an opaque white box.
    # Preserve packet tags and glyph geometry; only convert the transparency key.
    for gi in range(len(font_bytes) // GB):
        g = decode(font_bytes, gi).copy()
        g[g == TRANS] = 0
        font[gi*GB+16:gi*GB+216] = encode(g)
    sl = slots(elf, len(chars))
    cmap = {}
    for ch, (code, gi) in zip(chars, sl):
        g = to_glyph(render(ch, fnt, size, dy))
        font[gi*GB+16:gi*GB+216] = encode(g)
        cmap[ch] = code
    return bytes(font), cmap
