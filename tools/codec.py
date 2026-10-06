# -*- coding: utf-8 -*-
"""게임 바이트 <-> 편집용 텍스트.
ASCII 그대로, 0xC0 Ō 0xC1 ō 0xC2 Ū 0xC3 ū, 그 밖의 1바이트 0x80~0xFF 는 {XX},
SJIS 2바이트(0x81-0x9F,0xE0-0xEF 선행)는 cp932 문자로. 한글은 encode 시 글꼴 cmap(SJIS 칸)으로."""
import re, json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAC = {0xC0: 'Ō', 0xC1: 'ō', 0xC2: 'Ū', 0xC3: 'ū'}
RMAC = {v: k for k, v in MAC.items()}
def lead(b): return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xEF
def decode(b):
    out = []; i = 0
    while i < len(b):
        c = b[i]
        if c < 0x80: out.append(chr(c)); i += 1; continue
        if lead(c) and i + 1 < len(b):
            try:
                out.append(b[i:i+2].decode('cp932')); i += 2; continue
            except UnicodeDecodeError:
                pass
        out.append(MAC.get(c) or '{%02X}' % c); i += 1
    return ''.join(out)
_cmap = None
def cmap():
    global _cmap
    if _cmap is None:
        _cmap = {k: v for k, v in json.load(open(os.path.join(ROOT, 'translation/charmap.json'), encoding='utf-8')).items()}
    return _cmap
TOK = re.compile(r'\{([0-9A-F]{2})\}')
class EncodeError(Exception): pass
def encode(s):
    cm = cmap(); out = bytearray(); i = 0
    while i < len(s):
        m = TOK.match(s, i)
        if m: out.append(int(m.group(1), 16)); i = m.end(); continue
        ch = s[i]
        ch = {'·': '・', '“': '"', '”': '"', '‘': "'", '’': "'"}.get(ch, ch)
        if ord(ch) < 0x80: out.append(ord(ch))
        elif ch in RMAC: out.append(RMAC[ch])
        elif ch in cm: c = cm[ch]; out += bytes([c >> 8, c & 255])
        else:
            try:
                b = ch.encode('cp932')
            except UnicodeEncodeError:
                raise EncodeError('encode: %r in %r' % (ch, s))
            if '가' <= ch <= '힣': raise EncodeError('hangul not in font: %r' % ch)
            out += b
        i += 1
    return bytes(out)
