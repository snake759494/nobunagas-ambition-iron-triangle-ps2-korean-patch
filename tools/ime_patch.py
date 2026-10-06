"""Build and inject the bounded Korean name-entry IME into the old lookup table.

The original 22 KiB sparse table is losslessly represented by consecutive runs.
No ELF/BSS growth, allocation, ISO relocation, or save-record expansion is used.
"""
from pathlib import Path
import hashlib,json,struct,subprocess,sys
import font

ROOT=Path(__file__).resolve().parent.parent
BASE=0x635500
SIZE=font.TABLE_N*2
DIR=ROOT/'tools/ime'
TMP=ROOT/'work/ime_build'

def catalog():
    original=(ROOT/'work/SLUS_218.68').read_bytes()
    common=font.hangul2350()
    extra=[chr(i) for i in range(0x3131,0x3164)]
    extra += [chr(0xac00+(l*21+v)*28) for l in range(19) for v in range(21)
              if chr(0xac00+(l*21+v)*28) not in set(common)]
    slots=font.slots(original,len(common)+len(extra))
    return original,dict(zip(common+extra,slots)),extra

def prepare():
    original,entries,extra=catalog()
    table=font.read_table(original);runs=[];i=0
    while i<len(table):
        if table[i]==65535:i+=1;continue
        start=i;first=table[i];i+=1
        while i<len(table) and table[i]==first+i-start:i+=1
        runs.append([start,i-start,first])
    rows=sorted((ord(ch),code) for ch,(code,gi) in entries.items())
    page=['']*99
    for row,text in enumerate(['ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋ','ㅌㅍㅎㄲㄸㅃㅆㅉ','ㅏㅑㅓㅕㅗㅛㅜㅠㅡㅣㅐ','ㅒㅔㅖㅘㅙㅚㅝㅞㅟㅢ','ㄳㄵㄶㄺㄻㄼㄽㄾㄿㅀㅄ']):
        for x,ch in enumerate(text):page[row*11+x]=ch
    for x,ch in enumerate('0123456789'):page[88+x]=ch
    latin=list('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 !"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')
    latin += ['']*(99-len(latin))
    def encoded(ch):
        if not ch:return [0,0,0,0]
        if ord(ch)<128:return [ord(ch),0,0,0]
        c=entries[ch][0];return [c>>8,c&255,0,0]
    def arr(a):return '{'+','.join(str(x) if isinstance(x,int) else arr(x) for x in a)+'}'
    header=f'#define RANGE_COUNT {len(runs)}\n#define CHAR_COUNT {len(rows)}\n'
    header+='static const u16 ranges[][3]='+arr(runs)+';\n'
    header+='static const u16 chars[]='+arr([r[0] for r in rows])+';\n'
    header+='static const u16 codes[]='+arr([r[1] for r in rows])+';\n'
    header+='static const u8 keytext[2][99][4]='+arr([[encoded(c) for c in page],[encoded(c) for c in latin]])+';\n'
    (DIR/'tables.h').write_text(header,encoding='ascii')
    asm=['.set noreorder','.set noat','.text']
    for name in ['glyph_lookup','input','erase','left','right','keylabel','setup','frame']:
        asm += [f'.globl e_{name}',f'e_{name}:','addiu $sp,$sp,-480']
        regs=[r for r in range(1,32) if r not in (2,29)]
        for n,r in enumerate(regs):asm.append('.word 0x%08x'%((0x1f<<26)|(29<<21)|(r<<16)|(16+n*16)))
        asm += [f'jal {name}','nop']
        for n,r in enumerate(regs):asm.append('.word 0x%08x'%((0x1e<<26)|(29<<21)|(r<<16)|(16+n*16)))
        asm += ['jr $ra','addiu $sp,$sp,480']
    asm += ['.globl setup_tail','setup_tail:','jal e_setup','move $a0,$s1',
            '.word 0xdfbf0090','.word 0x7bb50080','j 0x5e2258','nop',
            '.globl cursor_fx','cursor_fx:','addiu $t0,$zero,1','j 0x15db40','nop']
    (DIR/'hooks.S').write_text('\n'.join(asm)+'\n',encoding='ascii')
    (DIR/'bank.ld').write_text('SECTIONS { . = 0x635500; .bank : { *(.text*) *(.rodata*) *(.data*) *(.sdata*) *(.bss*) *(.sbss*) } /DISCARD/ : { *(.MIPS.abiflags) *(.reginfo) *(.comment) *(.pdr) *(.gnu.attributes) *(.eh_frame*) *(.got) } }',encoding='ascii')
    TMP.mkdir(exist_ok=True)
    # R5900 engine callees save 128-bit GPRs with SQ/LQ: O32 default 8-byte
    # alignment corrupts the erase -> refresh -> engine path. Require 16.
    args=[sys.executable,'-m','ziglang','cc','-target','mipsel-freestanding','-march=mips2','-mabi=32',
          '-msoft-float','-mfp32','-mstack-alignment=16','-mno-abicalls','-fno-pic','-G0','-ffreestanding','-fno-builtin','-fno-stack-protector',
          '-nostdlib','-Os','-g','-fno-asynchronous-unwind-tables','-fno-unwind-tables','-Wl,--build-id=none','-Wl,-T,'+str(DIR/'bank.ld'),'-Wl,-e,e_input',
          str(DIR/'ime.c'),str(DIR/'hooks.S'),'-o',str(TMP/'ime.elf')]
    result=subprocess.run(args,cwd=ROOT,capture_output=True)
    if result.returncode:raise RuntimeError(result.stderr.decode('utf-8',errors='replace'))
    data=(TMP/'ime.elf').read_bytes()
    shoff=struct.unpack_from('<I',data,32)[0];ent,n,ss=struct.unpack_from('<HHH',data,46)
    sec=[struct.unpack_from('<10I',data,shoff+i*ent) for i in range(n)]
    shstr=data[sec[ss][4]:sec[ss][4]+sec[ss][5]]
    names=[shstr[s[0]:].split(b'\0')[0].decode() for s in sec]
    bank=sec[names.index('.bank')];blob=data[bank[4]:bank[4]+bank[5]]
    assert bank[3]==BASE and len(blob)<=SIZE,(hex(len(blob)),hex(SIZE))
    symbols={}
    for s in sec:
        if s[1]!=2:continue
        st=sec[s[6]];strings=data[st[4]:st[4]+st[5]]
        for off in range(s[4],s[4]+s[5],s[9]):
            name,value,size,info,other,idx=struct.unpack_from('<IIIBBH',data,off)
            if idx: symbols[strings[name:].split(b'\0')[0].decode()]=value
    (TMP/'symbols.json').write_text(json.dumps(symbols,indent=2),encoding='utf-8')
    (TMP/'bank.bin').write_bytes(blob)
    return blob,symbols,entries,extra

def apply(elf,gr):
    blob,sym,entries,extra=prepare();out=bytearray(elf);patches=[]
    def put(address,expected,new):
        off=address-0xfff80;old=struct.unpack_from('<I',out,off)[0]
        assert old==expected,(hex(address),hex(old),hex(expected))
        struct.pack_into('<I',out,off,new);patches.append([address,expected,new])
    def jump(address,name,expected,delay):
        put(address,expected,0x08000000|(sym[name]>>2));put(address+4,delay,0)
    jump(0x19b420,'e_glyph_lookup',0x3083ffff,0x34028100)
    jump(0x5e1160,'e_input',0x27bdffb0,0x3c0301fb)
    jump(0x5e1470,'e_erase',0x27bdffb0,0x3c0201fb)
    jump(0x5e1890,'e_left',0x27bdffd0,0x3c0201fb)
    jump(0x5e17f0,'e_right',0x27bdffd0,0xffbf0020)
    jump(0x5e2a50,'e_keylabel',0x3c020063,0x24030001)
    jump(0x5e19c0,'e_frame',0x27bdffd0,0xffbf0020)
    jump(0x5e2250,'setup_tail',0xdfbf0090,0x7bb50080)
    # Keep existing multibyte names intact when reopening the editor.
    put(0x5e2414,0x1040002c,0x1000002c)
    # Initially blank cells are filled as complete characters by setup_tail.
    put(0x5e2064,0x80421500,0x00001021)
    out[font.TABLE_OFF:font.TABLE_OFF+SIZE]=blob+bytes(SIZE-len(blob))
    raw=bytearray(gr[31])
    for ch in extra:
        code,gi=entries[ch];g=font.to_glyph(font.render(ch,str(ROOT/'NanumSquareNeo-cBd.ttf'),19))
        raw[gi*font.GB+16:gi*font.GB+216]=font.encode(g)
    gr[31]=bytes(raw)
    report=dict(version='2.6',bank_address=BASE,bank_bytes=len(blob),bank_capacity=SIZE,
                bank_sha256=hashlib.sha256(blob).hexdigest(),hooks=patches,
                syllables=2350+len(extra)-51,jamo=51,additional_glyphs=len(extra),
                name_bytes=11,max_hangul_per_field=5,save_format_changed=False,
                runtime_tested=False,symbols=sym)
    (ROOT/'validation/ime_patch.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Korean IME:',len(blob),'bytes,',len(extra),'additional glyphs')
    return bytes(out)

if __name__=='__main__':
    blob,sym,entries,extra=prepare();print('IME bank',len(blob),'/',SIZE,'extra glyphs',len(extra))
