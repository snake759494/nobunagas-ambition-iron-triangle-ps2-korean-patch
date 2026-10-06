"""Independent ISO read-back, translation, relocation and container checks."""
import collections
import hashlib
import json
import pathlib
import re
import struct
import sys

import numpy as np
import pycdlib
from PIL import Image, ImageDraw, ImageFont

import build
import codec
import elfpatch
import font
import gfx
import f11n2
import tables
from extract import unesc
from n12f import parse

ROOT = pathlib.Path(build.ROOT)


def sha(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def records(path):
    iso = pycdlib.PyCdlib()
    iso.open(str(path))
    out = {}
    for name in ('GRAPHRES.BIN;1', 'SLUS_218.68;1', 'STREAM.BIN;1'):
        rec = iso.get_record(iso_path='/' + name)
        out[name] = (rec.extent_location(), rec.get_data_length())
    iso.close()
    return out


def verify(path):
    manifest = json.loads((ROOT / 'validation/build_manifest.json').read_text(encoding='utf-8'))
    assert not manifest['warnings']
    source = pathlib.Path(build.ISO_SRC)
    path = pathlib.Path(path)
    src_records, dst_records = records(source), records(path)
    assert path.stat().st_size == source.stat().st_size
    assert src_records['STREAM.BIN;1'] == dst_records['STREAM.BIN;1']
    assert src_records['SLUS_218.68;1'] == dst_records['SLUS_218.68;1']
    original_elf = (ROOT / 'work/SLUS_218.68').read_bytes()
    with path.open('rb') as f:
        elba, esize = dst_records['SLUS_218.68;1']
        f.seek(elba * 2048)
        elf = f.read(esize)
        assert hashlib.sha256(elf).hexdigest() == manifest['elf_sha256']
        glba, gsize = dst_records['GRAPHRES.BIN;1']
        f.seek(glba * 2048)
        header = f.read(16384)
        assert header[:4] == b'LINK'
        count = struct.unpack_from('<I', header, 4)[0]
        assert count == len(manifest['resources']) == 1030
        gr = []
        end = 0
        for i, meta in enumerate(manifest['resources']):
            sector, size = struct.unpack_from('<II', header, 16+i*8)
            start = sector * 2048
            assert start >= end and start + size <= gsize
            f.seek(glba * 2048 + start)
            data = f.read(size)
            assert size == meta['size'] and hashlib.sha256(data).hexdigest() == meta['sha256'], i
            gr.append(data)
            end = (start + size + 2047) // 2048 * 2048

    # Independent read-back of every IME hook, its immutable code bank and glyphs.
    import ime_patch
    ime=json.loads((ROOT/'validation/ime_patch.json').read_text(encoding='utf-8'))
    tests=json.loads((ROOT/'validation/ime_tests.json').read_text(encoding='utf-8'))
    assert tests['result']=='PASS' and tests['bank_sha256']==ime['bank_sha256']
    bank=elf[font.TABLE_OFF:font.TABLE_OFF+ime['bank_bytes']]
    assert hashlib.sha256(bank).hexdigest()==ime['bank_sha256']
    assert not any(elf[font.TABLE_OFF+ime['bank_bytes']:font.TABLE_OFF+ime['bank_capacity']])
    for address,old,new in ime['hooks']:
        assert struct.unpack_from('<I',elf,address-0xfff80)[0]==new
        assert struct.unpack_from('<I',original_elf,address-0xfff80)[0]==old
    _,ime_entries,ime_extra=ime_patch.catalog()
    for ch in ime_extra:
        code,index=ime_entries[ch]
        expected=font.to_glyph(font.render(ch,str(ROOT/'NanumSquareNeo-cBd.ttf'),19))
        assert np.array_equal(font.decode(gr[31],index),expected),('IME glyph',ch)
    expected_menu=json.loads((ROOT/'validation/menu_v23_expected.json').read_text(encoding='utf-8'))
    for resource,digest in expected_menu.items():
        assert hashlib.sha256(gr[int(resource)]).hexdigest()==digest,('v2.3 resource restoration',resource)

    expected_headings=json.loads((ROOT/'validation/menu_v23_headings.json').read_text(encoding='utf-8'))
    for i,expected in enumerate(expected_headings):
        pointer=struct.unpack_from('<I',elf,0x62f2c0-0xfff80+4*i)[0]-0xfff80
        assert elf[pointer:elf.index(0,pointer)].hex()==expected,('v2.3 heading',i)

    # Every applied string and every relocated reference must point to the bytes
    # that the builder promised, including strings moved across 64 KiB boundaries.
    cross_bank = moved = 0
    for row in manifest['elf_strings']:
        start = row['target']
        expected = bytes.fromhex(row['encoded']) + b'\0'
        assert elf[start:start+len(expected)] == expected, ('ELF bytes', hex(row['source']))
        if start == row['source']:
            continue
        moved += 1
        newva = elfpatch.va(start)
        oldva = elfpatch.va(row['source'])
        for p in row['data_refs']:
            assert struct.unpack_from('<I', elf, p)[0] == newva
        for p in row['code_refs']:
            old = struct.unpack_from('<I', original_elf, p)[0]
            new = struct.unpack_from('<I', elf, p)[0]
            assert new >> 16 == old >> 16 and new & 65535 == newva & 65535
            if (newva+0x8000) >> 16 != (oldva+0x8000) >> 16:
                high = elfpatch.exclusive_lui(original_elf, p)
                assert high is not None and row['high_refs'][str(p)] == high
                highword = struct.unpack_from('<I', elf, high)[0]
                assert highword & 65535 == (newva+0x8000) >> 16
                assert (highword >> 16) == (struct.unpack_from('<I', original_elf, high)[0] >> 16)
                cross_bank += 1

    ko, en = build.load_ko()
    source_rows = [l.split('\t',3) for l in (ROOT/'translation/src/n12f.tsv').read_text(encoding='utf-8').splitlines()]
    duplicates = {}
    for f,k,msg,text in source_rows:
        key=f+':'+k
        if key in ko and len(text)>=25: duplicates.setdefault(text,ko[key])
    parsed = {}
    translated = unchanged = 0
    for f,k,msg,text in source_rows:
        i,j=int(f),int(k)
        if i not in parsed:
            original=(ROOT/('work/GR/%04d.bin'%i)).read_bytes()
            old=parse(original);new=parse(gr[i])
            assert old[1] == new[1] and len(old[2]) == len(new[2])
            assert len(gr[i])%4 == 0
            parsed[i]=(old[2],new[2])
        old,new=parsed[i]
        tr=ko.get(f+':'+k,duplicates.get(text) if len(text)>=25 else None)
        if tr is not None and text not in ('','Error'):
            assert new[j] == codec.encode(unesc(tr)), (i,j)
            translated+=1
        else:
            assert new[j] == old[j]
            assert text in ('','Error'), ('Untranslated N12F',i,j,text)
            unchanged+=1

    by=build.term_dict(ko,build.load_names())
    field_count=0
    for g in range(tables.NGROUP):
        for t,spec in tables.SPEC.items():
            i=tables.GROUP0+g*tables.GSIZE+t
            original=(ROOT/('work/GR/%04d.bin'%i)).read_bytes()
            r,n=tables.recsize(original)
            assert len(original)==len(gr[i])
            for j in range(n):
                last=None
                for o,w,kind,yo in spec:
                    at=j*r+o
                    english=codec.decode(tables.cstr(original[at:at+w]))
                    key=(('desc_'+last) if kind=='desc' else kind,english)
                    if kind!='desc':last=kind
                    if english and key in by:
                        assert tables.cstr(gr[i][at:at+w])==codec.encode(by[key]), (i,j,kind,english)
                        field_count+=1

    for i in range(680,732):
        d=gr[i]
        seg=np.frombuffer(d[0x4f4:-4],np.uint8).astype(np.uint64)
        checksum=int((seg*np.arange(len(seg),dtype=np.uint64)).sum())&0xffffffff
        assert struct.unpack_from('<I',d,0x4f0)[0]==checksum==struct.unpack_from('<I',d,len(d)-4)[0]

    original_font=(ROOT/'work/GR/0031.bin').read_bytes()
    assert len(gr[31])==len(original_font)
    for i in range(len(original_font)//font.GB):
        p=i*font.GB
        assert gr[31][p:p+16]==original_font[p:p+16]
        assert gr[31][p+216:p+224]==original_font[p+216:p+224]
    slots=font.slots(original_elf,2350)
    assert len({i for _,i in slots})==2350
    native_font = ImageFont.truetype(str(ROOT/'NanumSquareNeo-cBd.ttf'), 19)
    for ch, (_,i) in zip(font.hangul2350(), slots):
        glyph=font.decode(gr[31],i)
        assert glyph.max()==15 and np.count_nonzero(glyph)>10
        # An occupied border is not clipping. Render with a 20px guard on all
        # sides and prove that every nonzero coverage pixel fits the game cell.
        canvas = Image.new('L', (60,60))
        ImageDraw.Draw(canvas).text((30,30), ch, 255, font=native_font, anchor='mm')
        coverage = np.asarray(canvas).copy()
        expected = np.rint(coverage[20:40,20:40].astype(np.float32)/255*15).astype(np.uint8)
        assert np.array_equal(glyph,expected), ('Altered native font',ch)
        coverage[20:40,20:40] = 0
        assert not np.any(coverage), ('Clipped glyph',ch)
    tab=font.read_table(original_elf)
    for ch in '「」『』…・★':
        i=tab[font.k_of(int.from_bytes(ch.encode('cp932'),'big'))]
        old=font.decode(original_font,i);new=font.decode(gr[31],i)
        assert np.all(new[old==14]==0), ('Opaque symbol background',ch)

    # Pixel edits must stay inside approved labels. Shared palette variants keep
    # their original colours; only the two standalone logo palettes are replaced.
    graphic_pixels=0
    for i,mapping,logo in [(33,gfx.MAP33,None),(34,gfx.MAP34,None),
                            (35,gfx.MAP35,72),(1012,{1:'START'},0)]:
        original=(ROOT/('work/GR/%04d.bin'%i)).read_bytes()
        assert len(original)==len(gr[i])
        sprites,oldtx=f11n2.parse(original);newsp,newtx=f11n2.parse(gr[i])
        assert sprites==newsp
        masks={t['i']:np.zeros(t['idx'].shape,bool) for t in oldtx if t['pixsrc']==t['i']}
        permitted=np.zeros(len(original),bool)
        for number in list(mapping)+([logo] if logo is not None else []):
            x,y,w,h,_,c=f11n2.sxy(sprites[number]);src=oldtx[c]['pixsrc']
            masks[src][y:y+h,x:x+w]=True
        for old,new in zip(oldtx,newtx):
            if old['pixsrc']==old['i']:
                diff=old['idx']!=new['idx']
                assert not np.any(diff & ~masks[old['i']]), ('Adjacent sprite altered',i,old['i'])
                graphic_pixels+=int(diff.sum())
                size=old['idx'].size//2 if old['bpp']==4 else old['idx'].size
                permitted[old['pix_off']:old['pix_off']+size]=True
            if logo is not None and old['i']==sprites[logo][4]:
                permitted[old['pal_off']:old['pal_off']+old['pal'].size]=True
            else:
                assert np.array_equal(old['pal'],new['pal']), ('Palette state changed',i,old['i'])
        diff=np.frombuffer(original,np.uint8)!=np.frombuffer(gr[i],np.uint8)
        assert not np.any(diff & ~permitted), ('Graphics metadata changed',i)
    original=(ROOT/'work/GR/0039.bin').read_bytes()
    permitted=np.zeros(len(original),bool)
    for number in range(116,152):
        p=2048+number*124928+1024
        assert original[p:p+512*60]!=gr[39][p:p+512*60]
        permitted[p:p+512*60]=True
    diff=np.frombuffer(original,np.uint8)!=np.frombuffer(gr[39],np.uint8)
    assert not np.any(diff & ~permitted), 'BGM labels changed adjacent artwork'
    original=(ROOT/'work/GR/0868.bin').read_bytes()
    old=np.frombuffer(original,np.uint8,640*448,128).reshape(448,640)
    new=np.frombuffer(gr[868],np.uint8,640*448,128).reshape(448,640)
    permitted=np.zeros_like(old,dtype=bool)
    for x,y,w,h in [(300,2,38,18),(444,2,62,16),(171,130,222,25),(174,54,175,74)]:
        permitted[y:y+h,x:x+w]=True
    assert not np.any((old!=new)&~permitted), 'Loading atlas icons altered'
    assert original[:128]==gr[868][:128] and original[128+640*448:]==gr[868][128+640*448:]

    # Byte-for-byte preservation of all other disc regions, including STREAM.
    with source.open('rb') as a,path.open('rb') as b:
        a.seek(16*2048);pvd=a.read(2048)
        root_lba=struct.unpack_from('<I',pvd,158)[0]
        root_len=struct.unpack_from('<I',pvd,166)[0]
        allowed=sorted([(root_lba*2048,root_lba*2048+root_len),
                        (elba*2048,elba*2048+esize),
                        (glba*2048,glba*2048+(gsize+2047)//2048*2048)])
        cursor=0;preserved=0
        for lo,hi in allowed+[(source.stat().st_size,source.stat().st_size)]:
            assert lo>=cursor
            a.seek(cursor);b.seek(cursor)
            while cursor<lo:
                n=min(4*1024*1024,lo-cursor)
                assert a.read(n)==b.read(n), ('Unrelated ISO data changed',cursor)
                cursor+=n;preserved+=n
            cursor=hi

    report=dict(result='PASS',version=manifest['version'],source_sha256=sha(source),iso_sha256=sha(path),
                iso_bytes=path.stat().st_size,resources=count,
                changed_resources=sum(m['changed'] for m in manifest['resources']),
                n12f_files=len(parsed),n12f_translated=translated,n12f_blank_or_error=unchanged,
                table_fields_checked=field_count,scenario_checksums=52,hangul_glyphs=2350,
                elf_strings=len(manifest['elf_strings']),relocated_strings=moved,cross_bank_code_refs=cross_bank,
                untouched_disc_bytes_verified=preserved,elf_extra_strings=len((ROOT/'translation/elf_extra.tsv').read_text(encoding='utf-8').splitlines()),
                ime_bank_verified=True,ime_syllables=ime['syllables'],ime_jamo=ime['jamo'],ime_tests=tests['result'],runtime_tested=False)
    report.update(bgm_title_images=36,graphics_neighbor_preservation='PASS',changed_f11n_pixels=graphic_pixels)
    report.update(menu_style='v2.3',menu_resources_exact_match=len(expected_menu),heading_entries_exact_match=len(expected_headings),square_callback_cases=tests['square_callback_cases'])
    (ROOT/'validation/verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    verify(sys.argv[1] if len(sys.argv)>1 else build.ISO_OUT)
