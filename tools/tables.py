# 시나리오 데이터 테이블: 레코드 크기 자동 판정 + 문자열 필드 추정
import struct, re, collections
def recsize(d):
    for R in range(8, 4000):
        n = len(d) // R
        if n < 2 or len(d) % R: continue
        if all(struct.unpack_from('<I', d, k*R)[0] == k for k in range(min(n, 6))):
            return R, n
    return None
ASC = re.compile(rb'[A-Za-z0-9\xc0-\xcb][\x20-\x7e\xc0-\xcb]*')
SJ = re.compile(rb'(?:[\x81-\x9f\xe0-\xef][\x40-\xfc])+')
def fields(d, R, n):
    a = collections.Counter(); s = collections.Counter(); ext = collections.defaultdict(int)
    for k in range(n):
        r = d[k*R:(k+1)*R]
        for m in ASC.finditer(r, 4):
            if m.start() > 0 and r[m.start()-1] != 0: continue
            if len(m.group()) >= 2 and re.search(rb'[A-Za-z]', m.group()):
                a[m.start()] += 1; ext[m.start()] = max(ext[m.start()], m.end())
        for m in SJ.finditer(r, 4):
            if r[m.start()-1] == 0: s[m.start()] += 1
    return a, s, ext

GROUP0, NGROUP, GSIZE = 53, 26, 22
def layout(t, gr='work/GR'):
    """테이블 종류 t(0..21)의 문자열 필드 [(start,width,'asc'|'sj')] — 26개 묶음 전체 통계."""
    A = collections.Counter(); S = collections.Counter(); N = 0; R = None
    for g in range(NGROUP):
        i = GROUP0 + g*GSIZE + t
        d = open(f'{gr}/{i:04d}.bin', 'rb').read()
        r = recsize(d)
        if not r: return None, []
        R, n = r; a, s, _ = fields(d, R, n); A.update(a); S.update(s); N += n
    th = max(2, N // 40)
    starts = sorted(set([(o, 'asc') for o, c in A.items() if c >= th] + [(o, 'sj') for o, c in S.items() if c >= th and o < R-3]))
    out = []
    for k, (o, kind) in enumerate(starts):
        nxt = starts[k+1][0] if k+1 < len(starts) else R - 3
        out.append((o, nxt - o, kind))
    return R, out

# 테이블 종류별 (시작, 폭, 종류, 요미위치) — 폭은 NUL 포함 필드 크기
SPEC = {
 0: [(4, 16, 'base', 20)],
 1: [(4, 12, 'fam', 40), (16, 12, 'giv', 49)],
 2: [(4, 12, 'region', 16)],
 3: [(4, 12, 'terrain', None)],
 5: [(4, 20, 'unit', 24), (69, 80, 'desc', None)],
 6: [(4, 20, 'province', 24)],
 7: [(4, 16, 'basetype', 20), (46, 80, 'desc', None)],
 8: [(4, 28, 'item', 32)],
 9: [(16, 12, 'fam', 40), (28, 12, 'giv', 49)],
 10: [(4, 28, 'title', 32)],
 11: [(4, 24, 'castle', 28)],
 12: [(4, 8, 'basekind', 12)],
 13: [(4, 20, 'clan', 24)],
 16: [(4, 12, 'tactic', 16), (110, 80, 'desc', None)],
 17: [(4, 28, 'facility', 32), (105, 80, 'desc', None)],
 19: [(4, 24, 'tech', 28), (162, 80, 'desc', None)],
 20: [(4, 28, 'rank', 32)],
}
def cstr(b):
    return b.split(b'\0')[0]
def sj(b):
    b = cstr(b)
    out = b''
    i = 0
    while i + 1 < len(b) and 0x81 <= b[i] <= 0x9f or (i + 1 < len(b) and 0xe0 <= b[i] <= 0xef):
        out += b[i:i+2]; i += 2
    try: return out.decode('cp932')
    except: return ''
def iter_fields(gr='work/GR'):
    """(파일번호, 레코드, 필드시작절대, 폭, 종류, 영문bytes, 요미str)"""
    for g in range(NGROUP):
        for t, spec in SPEC.items():
            i = GROUP0 + g*GSIZE + t
            d = open(f'{gr}/{i:04d}.bin', 'rb').read()
            R, n = recsize(d)
            for k in range(n):
                for o, w, kind, yo in spec:
                    s = cstr(d[k*R+o:k*R+o+w])
                    y = sj(d[k*R+yo:k*R+yo+14]) if yo is not None else ''
                    yield i, k, k*R+o, w, kind, s, y
