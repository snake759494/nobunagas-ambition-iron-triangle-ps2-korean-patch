"""Reconstruct private build inputs from a hash-checked, user-supplied ISO."""
from pathlib import Path
import hashlib,json,struct
import pycdlib
import codec
from n12f import parse
ROOT=Path(__file__).resolve().parent.parent
SOURCE_SHA='e362862b1f2dd430dc88e8dbde63e71f33170974737fca55cc942a0d2b23ae9f'
def main():
    iso=ROOT/"Nobunaga's Ambition - Iron Triangle (USA).iso"
    with iso.open('rb')as f:assert hashlib.file_digest(f,'sha256').hexdigest()==SOURCE_SHA,'Wrong original ISO'
    for d in ['work/GR','translation/src','translation/jobs','translation/ko','validation']:(ROOT/d).mkdir(parents=True,exist_ok=True)
    disk=pycdlib.PyCdlib();disk.open(str(iso))
    disk.get_file_from_iso(local_path=str(ROOT/'work/SLUS_218.68'),iso_path='/SLUS_218.68;1')
    rec=disk.get_record(iso_path='/GRAPHRES.BIN;1');base=rec.extent_location()*2048;disk.close()
    gr={}
    with iso.open('rb')as f:
        f.seek(base);header=f.read(16384);assert header[:4]==b'LINK'
        for i in range(struct.unpack_from('<I',header,4)[0]):
            sector,size=struct.unpack_from('<II',header,16+8*i);f.seek(base+sector*2048);gr[i]=f.read(size)
            (ROOT/f'work/GR/{i:04d}.bin').write_bytes(gr[i])
    b=(ROOT/'work/SLUS_218.68').read_bytes();blue=json.loads((ROOT/'translation/source_index.json').read_text(encoding='utf-8'))
    def checked(text,h):
        assert hashlib.sha256(text.encode()).hexdigest()==h,'Source text hash mismatch'
        return text
    def write(path,rows):(ROOT/path).write_text('\n'.join(rows)+'\n',encoding='utf-8')
    sources={};rows=[];cache={}
    for f,k,msg,h in blue['n12f']:
        if f not in cache:cache[f]=parse(gr[f])
        assert cache[f][1]+k==msg
        text=checked(codec.decode(cache[f][2][k]),h);sources[f'{f}:{k}']=text
        rows.append(f'{f}\t{k}\t{msg}\t{text}')
    write('translation/src/n12f.tsv',rows);rows=[]
    for o,cap,h in blue['elf']:
        text=checked(codec.decode(b[o:b.index(0,o)]).replace('\n','\\n'),h);sources[f'{o:X}']=text
        rows.append(f'{o:X}\t{cap}\t{text}')
    write('translation/src/elf.tsv',rows)
    import tables
    for g in range(tables.NGROUP):
        raw=gr[tables.GROUP0+g*tables.GSIZE+15]
        for label,at in [("title",8),("desc",84)]:sources[f"scen{g}:{label}"]=codec.decode(raw[at:raw.index(0,at)]).replace("\r","<CR>").replace("\n","<LF>").replace("\t","<TAB>")
    keys={}
    for hashed,(f,o,n) in blue['terms'].items():
        kind,h=hashed.split('|',1);text=checked(codec.decode(gr[f][o:o+n]),h);keys[hashed]=kind+'|'+text
    for name,items in blue['jobs'].items():
        rows=[]
        for k,lim,h in items:
            full=keys.get(k,k);text=full.split('|',1)[1] if h is None else checked(sources[k],h)
            rows.append(f'{full}\t{lim}\t{text}')
        write(f'translation/jobs/{name}.tsv',rows)
    for p in (ROOT/'translation/data').glob('*.tsv'):
        rows=[]
        for row in p.read_text(encoding='utf-8').splitlines():
            k,sep,text=row.partition('\t');rows.append(keys.get(k,k)+sep+text)
        write('translation/ko/'+p.name,rows)
    rows=[]
    for row in (ROOT/'translation/fix_data.tsv').read_text(encoding='utf-8').splitlines():
        k,sep,text=row.partition('\t');rows.append(keys.get(k,k)+sep+text)
    write('translation/fix.tsv',rows);rows=[]
    for o,h,ko in blue['extra']:
        original=checked(codec.decode(b[o:b.index(0,o)]).replace('\n','\\n'),h);rows.append(f'{o:X}\t{original}\t{ko}')
    write('translation/elf_extra.tsv',rows)
    print('Original ISO verified; private resources and source text reconstructed.')
if __name__=='__main__':main()
