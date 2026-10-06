# -*- coding: utf-8 -*-
"""노부나가의 야망 혁신(북미판) 한글패치 빌드.
python tools/build.py [--iso 출력경로] [--check]
입력: work/SLUS_218.68, work/GR/*.bin(원본 추출), translation/ko/*.tsv, translation/names.tsv
"""
import os, sys, struct, glob, re, json, shutil, collections, argparse
sys.path.insert(0, os.path.dirname(__file__))
from codec import decode, encode, EncodeError
from n12f import parse as n12f_parse, build as n12f_build
from extract import unesc
import tables, font

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISO_SRC = os.path.join(ROOT, "Nobunaga's Ambition - Iron Triangle (USA).iso")
ISO_OUT = os.path.join(ROOT, "Nobunagas_Ambition_Iron_Triangle_KO.iso")
GR_LBA, GR_SECT = 700000, 140217
NEW_GR_LBA = 4000
ELF_LBA = 283
WARN = []

def warn(*a):
    WARN.append(' '.join(map(str, a)))

# ---------------------------------------------------------------- 번역 읽기
GLOBAL_FIX = [('도토우미', '도토미'), ('진행 단계', '실행 단계'), ('작전 단계', '계획 단계'), ('활동 단계', '실행 단계')]
def load_ko():
    """{id: ko} — jobs 의 id 순서. 원문은 jobs 에서."""
    ko, en = {}, {}
    for p in sorted(glob.glob(os.path.join(ROOT, 'translation/jobs/*.tsv'))):
        if p.endswith('_names.tsv'): continue
        job = os.path.basename(p)[:-4]
        for l in open(p, encoding='utf-8'):
            t = l.rstrip('\n').split('\t')
            en[t[0]] = t[2]
        kp = os.path.join(ROOT, 'translation/ko', job + '.tsv')
        if os.path.exists(kp):
            for l in open(kp, encoding='utf-8'):
                l = l.rstrip('\n').rstrip('\r')
                if not l: continue
                t = l.split('\t', 1)
                if t[0] not in en: continue
                k = t[1] if len(t) == 2 else ''
                e = en[t[0]]
                # Write 도구가 지운 줄 끝 공백 복원(이름이 뒤에 끼는 조각)
                if e.endswith(' ') and k and not k.endswith(' ') and k[-1] not in '「『(\'"[“‘':
                    k += ' '
                for a, b in GLOBAL_FIX: k = k.replace(a, b)
                ko[t[0]] = k
    # 수동 교정(최우선)
    fp = os.path.join(ROOT, 'translation/fix.tsv')
    if os.path.exists(fp):
        for l in open(fp, encoding='utf-8'):
            t = l.rstrip('\n').split('\t')
            if len(t) >= 2 and not t[0].startswith('#'): ko[t[0]] = t[1]
    return ko, en

def load_names():
    nm = {}
    for l in list(open(os.path.join(ROOT, 'translation/names.tsv'), encoding='utf-8'))[1:]:
        kind, en, k, y, note = l.rstrip('\n').split('\t')
        nm[(kind, en)] = k
    return nm

def enc(s, ctx):
    try:
        return encode(s)
    except EncodeError as e:
        warn('ENC', ctx, e)
        return None

# ---------------------------------------------------------------- 글꼴
def build_font(elf, gr):
    chars = font.hangul2350()
    nf, cmap = font.build(elf, gr[31], chars, os.path.join(ROOT, 'NanumSquareNeo-cBd.ttf'), 19)
    json.dump(cmap, open(os.path.join(ROOT, 'translation/charmap.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    gr[31] = nf

# ---------------------------------------------------------------- N12F
def build_n12f(gr, ko, en):
    src = [l.rstrip('\n').split('\t', 3) for l in open(os.path.join(ROOT, 'translation/src/n12f.tsv'), encoding='utf-8')]
    bytext = {}   # 긴 중복 문장: 원문 -> 번역
    for f, k, m, t in src:
        i = '%s:%s' % (f, k)
        if i in ko and len(t) >= 25: bytext.setdefault(t, ko[i])
    files = collections.defaultdict(list)
    for f, k, m, t in src: files[int(f)].append((int(k), t))
    done = tot = 0
    for f, rows in files.items():
        d = gr[f]
        sec, base, strs, end = n12f_parse(d)
        new = []
        for k, t in rows:
            i = '%d:%d' % (f, k)
            tr = ko.get(i)
            if tr is None and len(t) >= 25: tr = bytext.get(t)
            tot += 1
            if tr is None or t in ('', 'Error'):
                new.append(strs[k]); continue
            b = enc(unesc(tr), i)
            if b is None: new.append(strs[k]); continue
            if t.count('\\n') != tr.count('\\n'): warn('NL', i)
            new.append(b); done += 1
        out = n12f_build(d, new)
        out += b'\0' * (-len(out) % 4)
        if len(out) > len(d): warn('GROW n12f', f, len(d), len(out))
        gr[f] = out
    print('N12F 번역 적용 %d/%d' % (done, tot))

# ---------------------------------------------------------------- 용어·이름 사전
def term_dict(ko, nm):
    """영문 -> 한글 (데이터 필드용). kind 별 + 공통."""
    by = {}
    for (kind, e), k in nm.items(): by[(kind, e)] = k
    for i, k in ko.items():
        if '|' in i and i.split('|')[0] in ('item', 'title', 'rank', 'tech', 'facility', 'tactic', 'unit',
                                              'basetype', 'terrain', 'basekind') or i.startswith('desc_'):
            kind, e = i.split('|', 1)
            by[(kind, e)] = k
    return by

def put(buf, off, width, ko, ctx):
    b = enc(ko, ctx)
    if b is None: return False
    if len(b) > width - 1:
        warn('LONG', ctx, ko, len(b), width - 1); return False
    buf[off:off+width] = b + b'\0' * (width - len(b))
    return True

def build_tables(gr, by):
    cnt = 0
    for g in range(tables.NGROUP):
        for t, spec in tables.SPEC.items():
            i = tables.GROUP0 + g * tables.GSIZE + t
            d = bytearray(gr[i]); R, n = tables.recsize(bytes(d))
            for k in range(n):
                last = None
                for o, w, kind, yo in spec:
                    s = tables.cstr(d[k*R+o:k*R+o+w])
                    if not s: continue
                    e = decode(s)
                    key = (('desc_' + last) if kind == 'desc' else kind, e)
                    if kind != 'desc': last = kind
                    if key in by and by[key] != e:
                        if put(d, k*R+o, w, by[key], 'tab%d.%d' % (i, k)): cnt += 1
            gr[i] = bytes(d)
        # 시나리오 제목/개요
        i = tables.GROUP0 + g * tables.GSIZE + 15
        gr[i] = scen_patch(gr[i], g)
    # 역사 영웅 625 (무장 레이아웃)
    d = bytearray(gr[625])
    for k in range(len(d) // 385):
        for o, kind in ((4, 'fam'), (16, 'giv')):
            e = decode(tables.cstr(d[k*385+o:k*385+o+12]))
            if (kind, e) in by: put(d, k*385+o, 12, by[(kind, e)], 'hero%d' % k)
    gr[625] = bytes(d)
    print('테이블 필드 교체', cnt)

SCEN = {}
def scen_patch(d, g):
    """68 계열: 제목 @8(48B), 개요 @84 ~ 다음 0 아닌 바이트 전."""
    d = bytearray(d)
    ti = SCEN.get('scen%d:title' % g); de = SCEN.get('scen%d:desc' % g)
    if ti: put(d, 8, 48, ti, 'scen%d title' % g)
    if de:
        p = 84; e = d.index(bytes(1), p)
        while e < len(d) - 3 and d[e] == 0: e += 1
        b = enc(unesc(de), 'scen%d' % g)
        if b and len(b) < e - p: d[p:e] = b + bytes(e - p - len(b))
        elif b: warn('LONG scen', g)
    return bytes(d)

def blob_patch(d, by, ctx, maxw=None):
    """null 경계 영문 문자열을 같은 바이트 범위 안에서 교체(뒤 0 패딩 활용, 폭 상한=kind 폭)."""
    d = bytearray(d)
    W = {'fam': 12, 'giv': 12, 'base': 16, 'castle': 24, 'clan': 20, 'province': 20, 'region': 12, 'terrain': 12,
         'unit': 20, 'basetype': 16, 'item': 28, 'title': 28, 'castle2': 24, 'basekind': 8, 'tactic': 12,
         'facility': 28, 'tech': 24, 'rank': 28}
    m = {}
    for (kind, e), k in by.items():
        if kind.startswith('desc_'): w = 80
        else: w = W.get(kind, 12)
        if e not in m or w < m[e][1]: m[e] = (k, w)
    pat = re.compile(rb'(?:^|(?<=[\x00-\x1f\x7f-\xbf\xc4-\xff]))[A-Z\xc0\xc2][\x20-\x7e\xc0-\xc3]+(?=\x00)')
    cnt = 0
    for mt in list(pat.finditer(bytes(d))):
        e = decode(mt.group())
        if e not in m: continue
        k, w = m[e]
        s, t = mt.start(), mt.end()
        z = t
        while z < len(d) and d[z] == 0 and z - s < w: z += 1
        avail = min(z - s, w) - 1
        b = enc(k, ctx)
        if b is None: continue
        if len(b) > avail:
            warn('BLOBLONG', ctx, e, k, len(b), avail); continue
        d[s:s+len(b)] = b; d[s+len(b):t] = b'\0' * max(0, t - s - len(b)); cnt += 1
    return bytes(d), cnt

def fix_checksum(gr):
    """SCENARIOVERSION 검사합: sum(b[i]*i), i=0.. over [0x4F4, len-4), 0x4F0 과 끝 4바이트에 저장(0x15E420)."""
    import numpy as np
    for i in range(680, 732):
        d = bytearray(gr[i])
        seg = np.frombuffer(bytes(d[0x4f4:len(d)-4]), np.uint8).astype(np.uint64)
        c = int((seg * np.arange(len(seg), dtype=np.uint64)).sum()) & 0xffffffff
        struct.pack_into('<I', d, 0x4f0, c); struct.pack_into('<I', d, len(d) - 4, c)
        gr[i] = bytes(d)

def scen_tail(gr, orig):
    """680~705 끝부분의 제목/개요 사본을 번역본(68 계열)으로 교체."""
    for g in range(26):
        i = 680 + g
        d = bytearray(gr[i]); o68 = orig[tables.GROUP0 + g * tables.GSIZE + 15]; n68 = gr[tables.GROUP0 + g * tables.GSIZE + 15]
        for a, b in ((o68[84:].split(bytes(1))[0], n68[84:].split(bytes(1))[0]), (o68[8:56].split(bytes(1))[0], n68[8:56].split(bytes(1))[0])):
            if a == b or len(a) < 4: continue
            p = d.find(a, 0x4f4)
            while p >= 0:
                z = p + len(a)
                while z < len(d) - 4 and d[z] == 0: z += 1
                if len(b) < z - p: d[p:z] = b + bytes(z - p - len(b))
                else: warn('scentail long', i)
                p = d.find(a, p + 1)
        gr[i] = bytes(d)

def build_blobs(gr, by):
    tot = 0
    for i in list(range(680, 732)) + [732]:
        gr[i], c = blob_patch(gr[i], by, 'blob%d' % i); tot += c
        if 680 <= i < 706:   # 헤더의 시나리오 개요(0x24~)
            pass
    print('시나리오 상태 데이터 교체', tot)

def scen_header(gr):
    """680~705 헤더: 개요 @28(다음 0 아닌 바이트 전), 제목 @0x3dc(48B) 를 68 계열 번역본으로."""
    for g in range(26):
        i = 680 + g
        d = bytearray(gr[i]); src = gr[tables.GROUP0 + g * tables.GSIZE + 15]
        de = src[84:].split(bytes(1))[0]
        q = 28; e = d.index(bytes(1), q); z = e
        while d[z] == 0 and z < 0x3d8: z += 1
        if len(de) < z - q: d[q:z] = de + bytes(z - q - len(de))
        else: warn('scenhdr long', i)
        if d[0x3dc:0x3dc+4] != bytes(4):
            ti = src[8:56].split(bytes(1))[0]
            d[0x3dc:0x3dc+48] = ti + bytes(48 - len(ti))
        else: warn('scenhdr title?', i)
        gr[i] = bytes(d)

# ---------------------------------------------------------------- ELF
def va2off(v): return v - 0x100000 + 0x80
def build_elf(elf, ko):
    import elfpatch
    items = []
    for l in open(os.path.join(ROOT, 'translation/src/elf.tsv'), encoding='utf-8'):
        o, cap, t = l.rstrip('\n').split('\t')
        oo = int(o, 16)
        tr = ELF_AUTO.get(oo) if ELF_A0 <= oo < ELF_A1 else ko.get(o)
        if tr is None or tr == t: continue
        if tr.count('\\n') == 1 and len(re.sub(r'\{..\}', '', tr)) <= 10 and not re.search('[A-Za-z]', tr):
            tr = tr.replace('\\n', '')   # 소형 2줄 겹침 방지: 짧은 2줄 라벨은 한 줄로
        b = enc(tr.replace('\\n', '\n'), 'elf' + o)
        if b is None: continue
        ob = elf[oo:elf.index(bytes(1), oo)]
        items.append((oo, ob, b))
    extra = os.path.join(ROOT, 'translation/elf_extra.tsv')
    if os.path.exists(extra):
        offsets = {o for o, _, _ in items}
        for line in open(extra, encoding='utf-8'):
            addr, original, translated = line.rstrip('\n').split('\t')
            oo = int(addr, 16)
            ob = elf[oo:elf.index(bytes(1), oo)]
            assert decode(ob).replace('\n', '\\n') == original, ('ELF source mismatch', addr)
            assert oo not in offsets, ('Duplicate ELF translation', addr)
            nb = enc(translated.replace('\\n', '\n'), 'extra:' + addr)
            if nb is not None: items.append((oo, ob, nb))
            offsets.add(oo)
    elf, moved = elfpatch.apply(elf, items, warn)
    import fontpatch
    elf = fontpatch.apply(elf, warn)
    elf = bytearray(elf)
    # 성명 순서: '이름 성' -> '성 이름'
    def patch(va, old, new):
        o = va2off(va)
        if struct.unpack_from('<I', elf, o)[0] != old: warn('ELFPATCH mismatch', hex(va)); return
        struct.pack_into('<I', elf, o, new)
    patch(0x1ee518, 0x26260010, 0x26260004)   # a2 = 성
    patch(0x1ee520, 0x26270004, 0x26270010)   # a3 = 이름
    patch(0x242f54, 0x0c090bc4, 0x0c090bc8)   # 첫 인자 = 성
    patch(0x242f60, 0x0c090bc8, 0x0c090bc4)   # 둘째 인자 = 이름
    print('ELF 문자열 교체', len(items), '재배치', moved)
    return bytes(elf)

ELF_AUTO = {}
ELF_A0, ELF_A1 = 0x544A80, 0x548400
def elf_auto_names():
    from romaji import ko as rko
    from make_jobs import NAME_A0, NAME_A1
    for l in open(os.path.join(ROOT, 'translation/src/elf.tsv'), encoding='utf-8'):
        o, cap, t = l.rstrip('\n').split('\t')
        oo = int(o, 16)
        if NAME_A0 <= oo < NAME_A1 and re.fullmatch(r"[A-ZŌŪ][a-zōū']+", t):
            r = rko(t)
            if r: ELF_AUTO[oo] = r

# ---------------------------------------------------------------- GRAPHRES / ISO
def read_gr():
    f = open(ISO_SRC, 'rb'); f.seek(GR_LBA * 2048); h = f.read(0x4000)
    cnt = struct.unpack_from('<I', h, 4)[0]
    ents = [struct.unpack_from('<II', h, 16 + i * 8) for i in range(cnt)]
    hdr_sect = ents[0][0]
    result = []
    for i, (sector, size) in enumerate(ents):
        data = open(os.path.join(ROOT, 'work/GR/%04d.bin' % i), 'rb').read()
        f.seek((GR_LBA + sector) * 2048)
        assert f.read(size) == data, ('Original extraction mismatch', i)
        result.append(data)
    f.close()
    return result, hdr_sect

def pack_gr(gr, hdr_sect):
    cnt = len(gr)
    out = bytearray(hdr_sect * 2048)
    struct.pack_into('<4sIII', out, 0, b'LINK', cnt, 0x800, 0)
    pos = hdr_sect
    body = []
    for i, d in enumerate(gr):
        struct.pack_into('<II', out, 16 + i * 8, pos, len(d))
        pad = d + b'\0' * (-len(d) % 2048)
        body.append(pad); pos += len(pad) // 2048
    return bytes(out) + b''.join(body)

def find_dirrec(iso_f, name):
    import pycdlib
    iso = pycdlib.PyCdlib(); iso.open_fp(iso_f)
    rec = iso.get_record(iso_path='/' + name)
    lba = rec.extent_location(); size = rec.get_data_length()
    iso.close()
    # 루트 디렉터리 섹터에서 레코드 찾기
    return lba, size

def write_iso(out_path, elf, grbin):
    final_path = out_path
    out_path = final_path + '.building'
    assert os.path.abspath(final_path) != os.path.abspath(ISO_SRC)
    shutil.copyfile(ISO_SRC, out_path)
    with open(out_path, 'r+b') as f:
        # ELF 같은 크기
        f.seek(ELF_LBA * 2048); old = f.read(len(elf))
        assert len(old) == len(elf)
        f.seek(ELF_LBA * 2048); f.write(elf)
        nsect = (len(grbin) + 2047) // 2048
        if nsect <= GR_SECT:
            lba = GR_LBA
        else:
            lba = NEW_GR_LBA
            assert lba + nsect <= GR_LBA, 'GRAPHRES 너무 큼'
            f.seek(lba * 2048)
            left = nsect * 2048
            while left:
                block = f.read(min(left, 4*1024*1024))
                assert block and not any(block), 'Relocation destination is not empty'
                left -= len(block)
        f.seek(lba * 2048); f.write(grbin + b'\0' * (-len(grbin) % 2048))
        if lba != GR_LBA:
            # 원래 자리 비우기(선택) — 그대로 두어도 무방하지만 혼동 방지로 0
            pass
        # 루트 디렉터리 레코드 수정
        f.seek(16 * 2048); pvd = f.read(2048)
        root_lba = struct.unpack_from('<I', pvd, 156 + 2)[0]
        root_len = struct.unpack_from('<I', pvd, 156 + 10)[0]
        f.seek(root_lba * 2048); dr = bytearray(f.read(root_len))
        p = 0; hit = False
        while p < len(dr):
            ln = dr[p]
            if ln == 0: p = (p // 2048 + 1) * 2048; continue
            nl = dr[p + 32]; nm = bytes(dr[p+33:p+33+nl])
            if nm == b'GRAPHRES.BIN;1':
                struct.pack_into('<I', dr, p + 2, lba); struct.pack_into('>I', dr, p + 6, lba)
                struct.pack_into('<I', dr, p + 10, len(grbin)); struct.pack_into('>I', dr, p + 14, len(grbin))
                hit = True
            p += ln
        assert hit
        f.seek(root_lba * 2048); f.write(dr)
        f.flush()
        f.seek(ELF_LBA * 2048); assert f.read(len(elf)) == elf
        f.seek(lba * 2048); assert f.read(len(grbin)) == grbin
    assert os.path.getsize(out_path) == os.path.getsize(ISO_SRC)
    os.replace(out_path, final_path)
    print('ISO:', final_path, 'GRAPHRES LBA', lba, 'size', len(grbin))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--iso', default=ISO_OUT)
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    forbidden = [k for k in os.environ if k.startswith('SKIP_') and k in
                 ('SKIP_N12F','SKIP_TABLES','SKIP_BLOBS','SKIP_HDR','SKIP_ELF')]
    assert not forbidden and not os.environ.get('TEST_ONE'), 'Partial/debug build flags are not allowed'
    WARN.clear()
    elf = open(os.path.join(ROOT, 'work/SLUS_218.68'), 'rb').read()
    with open(ISO_SRC, 'rb') as src:
        src.seek(ELF_LBA * 2048)
        assert src.read(len(elf)) == elf, 'Original ELF extraction mismatch'
    gr, hdr_sect = read_gr()
    global ORIG
    ORIG = list(gr)
    build_font(elf, gr)
    ko, en = load_ko()
    for k, v in ko.items():
        if k.startswith('scen'): SCEN[k] = v
    nm = load_names()
    by = term_dict(ko, nm)
    if not os.environ.get('SKIP_N12F'): build_n12f(gr, ko, en)
    if not os.environ.get('SKIP_TABLES'): build_tables(gr, by)
    if not os.environ.get('SKIP_BLOBS') and not os.environ.get('SKIP_HDR'): scen_header(gr)
    if not os.environ.get('SKIP_BLOBS'): build_blobs(gr, by)
    if not os.environ.get('SKIP_BLOBS'): scen_tail(gr, ORIG)
    fix_checksum(gr)
    if os.environ.get('TEST_ONE'):
        for i in list(range(680, 732)):
            d = bytearray(gr[i]); p = d.find(b'Kakizaki')
            if p > 0: d[p+7] = ord('j'); gr[i] = bytes(d)
    import gfx
    gfx.build(gr)
    elf_auto_names()
    elf2 = elf if os.environ.get('SKIP_ELF') else build_elf(elf, ko)
    import ime_patch
    elf2 = ime_patch.apply(elf2, gr)
    print('경고 %d건' % len(WARN))
    with open(os.path.join(ROOT, 'work/build_warn.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(WARN))
    if WARN: raise RuntimeError('Build warnings must be resolved before delivery; see work/build_warn.txt')
    import hashlib, elfpatch
    os.makedirs(os.path.join(ROOT, 'validation'), exist_ok=True)
    manifest = dict(version='2.6', resources=[dict(index=i, size=len(d), sha256=hashlib.sha256(d).hexdigest(),
                    changed=d!=ORIG[i]) for i,d in enumerate(gr)],
                    elf_sha256=hashlib.sha256(elf2).hexdigest(), elf_strings=list(elfpatch.REPORT),
                    runtime_tested=False, warnings=WARN)
    with open(os.path.join(ROOT, 'validation/build_manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    if a.check: return
    grbin = pack_gr(gr, hdr_sect)
    write_iso(a.iso, elf2, grbin)

if __name__ == '__main__':
    main()
