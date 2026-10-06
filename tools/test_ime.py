"""Execute the actual compiled MIPS input routines in Unicorn, not a Python clone."""
import json,struct,sys,hashlib
from pathlib import Path
import unicorn as uc
from unicorn.mips_const import *
import ime_patch,font

ROOT=ime_patch.ROOT

class Machine:
    def __init__(self):
        self.u=uc.Uc(uc.UC_ARCH_MIPS,uc.UC_MODE_MIPS32|uc.UC_MODE_LITTLE_ENDIAN)
        self.u.mem_map(0,32*1024*1024)
        self.u.mem_write(ime_patch.BASE,(ime_patch.TMP/'bank.bin').read_bytes())
        self.sym=json.loads((ime_patch.TMP/'symbols.json').read_text())
        _,entries,_=ime_patch.catalog()
        self.codes={c:v[0] for c,v in entries.items()};self.reverse={v:c for c,v in self.codes.items()}
        self.obj=0x1000000;self.stop=0x1000
        self.events=[]
        self.engine_calls=0
        def engine_boundary(machine,address,size,user):
            sp=machine.reg_read(UC_MIPS_REG_SP)
            assert sp%16==0,('EE stack alignment',hex(address),hex(sp))
            self.engine_calls+=1
        for address in [0x1a3d40,0x5e1370,0x13f4b0,0x1d4540,0x15db40,0x5e1130,0x5e1060,0x1100]:
            self.u.mem_write(address,struct.pack('<II',0x03e00008,0))
            self.u.hook_add(uc.UC_HOOK_CODE,engine_boundary,begin=address,end=address)
        def ee_memory(machine,address,size,user):
            word=struct.unpack('<I',machine.mem_read(address,4))[0]
            op=word>>26
            if op not in (0x1e,0x1f,0x37,0x3f):return
            rs=(word>>21)&31;rt=(word>>16)&31;imm=word&65535
            if imm&32768:imm-=65536
            target=(machine.reg_read(UC_MIPS_REG_0+rs)+imm)&0xffffffff
            if op in (0x1f,0x3f):machine.mem_write(target,struct.pack('<I',machine.reg_read(UC_MIPS_REG_0+rt))+bytes(12 if op==0x1f else 4))
            else:machine.reg_write(UC_MIPS_REG_0+rt,struct.unpack('<I',machine.mem_read(target,4))[0])
            machine.reg_write(UC_MIPS_REG_PC,address+4)
        self.u.hook_add(uc.UC_HOOK_CODE,ee_memory,begin=min(v for k,v in self.sym.items() if k.startswith('e_')),end=self.sym['setup_tail']+64)
        # The game's real Square-button callback, including its SD/LD frame.
        original=(ROOT/'work/SLUS_218.68').read_bytes()
        self.u.mem_write(0x5e16d0,original[0x5e16d0-0xfff80:0x5e16f0-0xfff80])
        self.u.mem_write(0x5e1470,struct.pack('<II',0x08000000|(self.sym['e_erase']>>2),0))
        self.sym['square_callback']=0x5e16d0
        self.u.hook_add(uc.UC_HOOK_CODE,ee_memory,begin=0x5e16d0,end=0x5e16ec)
        self.reset()
    def call(self,name,*args):
        for reg,value in zip([UC_MIPS_REG_A0,UC_MIPS_REG_A1,UC_MIPS_REG_A2,UC_MIPS_REG_A3],args):self.u.reg_write(reg,value)
        self.u.reg_write(UC_MIPS_REG_SP,0x1f00000);self.u.reg_write(UC_MIPS_REG_RA,self.stop)
        self.u.emu_start(self.sym[name],self.stop,count=2000000)
        assert self.u.reg_read(UC_MIPS_REG_PC)==self.stop,('runaway',name,hex(self.u.reg_read(UC_MIPS_REG_PC)))
        return self.u.reg_read(UC_MIPS_REG_V0)
    def reset(self,text='',cap=11):
        self.u.mem_write(self.obj,b'\0'*0x1700)
        self.u.mem_write(self.obj+0x150c,struct.pack('<I',cap))
        encoded=self.encode(text);assert len(encoded)<=11
        self.u.mem_write(self.obj+0x1500,encoded+b'\0')
        self.u.mem_write(self.obj+0x1514,struct.pack('<I',200))
        # Non-null text/cursor objects make refresh exercise every engine call.
        vt=self.obj+0x3000
        self.u.mem_write(vt+0x14,struct.pack('<I',0x1100))
        self.u.mem_write(vt+0x44,struct.pack('<I',0x1100))
        for i in range(13):
            ptr=self.obj+0x4000+i*0x100
            self.u.mem_write(ptr,struct.pack('<I',vt))
            self.u.mem_write(self.obj+(0x153c+i*16 if i<12 else 0x1528),struct.pack('<I',ptr))
        self.u.mem_write(self.obj+0x14ff,b'\xA5');self.u.mem_write(self.obj+0x150b,b'\0')
        self.call('setup',self.obj)
    def encode(self,text):
        return b''.join(bytes([ord(c)]) if ord(c)<128 else self.codes[c].to_bytes(2,'big') for c in text)
    def text(self):
        b=bytes(self.u.mem_read(self.obj+0x1500,12)).split(b'\0')[0];out='';i=0
        while i<len(b):
            if b[i]<128:out+=chr(b[i]);i+=1
            else:out+=self.reverse[int.from_bytes(b[i:i+2],'big')];i+=2
        assert self.u.mem_read(self.obj+0x14ff,1)==b'\xA5'
        assert self.u.mem_read(self.obj+0x150c,4)==struct.pack('<I',11)
        return out
    def type(self,keys):
        for c in keys:
            key=ord(c)<<8 if ord(c)<128 else self.codes[c]
            assert self.call('input',self.obj,key)==1,('Rejected',keys,c,self.text())

def main():
    ime_patch.prepare();m=Machine();cases=[]
    for keys,want in [('ㄱㅣㅁ','김'),('ㅎㅗㅇㄱㅣㄹㄷㅗㅇ','홍길동'),('ㅇㅣㅅㅜㄴㅅㅣㄴ','이순신'),
                       ('ㄱㅗㅏ','과'),('ㄱㅗㅏㅣㄴ','괜'),('ㄱㅏㅂㅅ','값'),('ㅇㅣㄹㄱㅇㅓ','읽어'),
                       ('ㄷㅏㄹㄱㅣ','달기'),('ㅇㅏㄴㅈㅏ','안자'),('ㄱㅏㄲㅏ','가까'),
                       ('ㄱㄱㅏ','까'),('Aㄱㅣㅁ7','A김7'),
                       ('ㄱㅏㄱㄱㅏ','각가'),('ㄱㅜㄱㄱㅏ','국가'),('ㅎㅏㄱㄱㅛ','학교'),
                       ('ㅇㅏㅅㅅㅏ','앗사'),('ㄲㅏㄲ','깎')]:
        m.reset();m.type(keys);assert m.text()==want,(keys,m.text(),want);cases.append([keys,want])
    m.reset();m.type('ㄱㅏㄱㄱㅏ')
    for want in ['각ㄱ','각','']:
        m.call('square_callback',m.obj);assert m.text()==want
    m.reset();m.type('ㄱㅏㄴㅏㄷㅏㄹㅏㄱㅏㄱ')
    assert m.text()=='가나다라각'
    assert not m.call('input',m.obj,m.codes['ㄱ'])
    assert m.text()=='가나다라각'
    m.call('square_callback',m.obj);assert m.text()=='가나다라가'
    m.reset();m.type('ㄱㅏㅂㅅ')
    for want in ['갑','가','ㄱ','']:
        m.call('erase',m.obj);assert m.text()==want,('backspace',m.text(),want)
    m.reset();m.type('ㄱㄱㅗㅏㅣ')
    for want in ['꽈','꼬','ㄲ','ㄱ','']:
        m.call('erase',m.obj);assert m.text()==want,('composition history',m.text(),want)
    square_cases=0
    for text in ['', '김', '홍길동', 'A김7', 'abcdefghijk', '가나다라마']:
        m.reset(text)
        for _ in text:m.call('e_right',m.obj)
        for remaining in range(len(text)-1,-2,-1):
            assert m.call('square_callback',m.obj)==1
            assert m.text()==text[:max(remaining,0)]
            m.call('e_frame',m.obj)
            square_cases+=1
    m.reset();m.type('ㄱㅏㅂㅅ')
    for want in ['갑','가','ㄱ','']:
        m.call('square_callback',m.obj);m.call('e_frame',m.obj)
        assert m.text()==want;square_cases+=1
    # Recovered original animation tail must release active cells after 40 ticks.
    m.u.mem_write(m.obj+0x1534,struct.pack('<II',1,0))
    for _ in range(41):m.call('e_frame',m.obj)
    assert struct.unpack('<II',m.u.mem_read(m.obj+0x1534,8))==(0,41)
    m.reset('홍길동');m.call('right',m.obj);m.call('right',m.obj);m.call('erase',m.obj)
    assert m.text()=='홍동';m.type('ㄱㅣㄹ');assert m.text()=='홍길동'
    m.call('left',m.obj);m.call('left',m.obj);m.type('A');assert m.text()=='A홍길동'
    m.reset();m.type('ㄱㅏㄴㅏㄷㅏㄹㅏㅁㅏ');assert m.text()=='가나다라마'
    assert not m.call('input',m.obj,m.codes['ㄸ']);assert m.text()=='가나다라마'
    # At the byte limit, replacing the current syllable must still work.
    m.call('input',m.obj,m.codes['ㄴ']);assert m.text()=='가나다라만'
    m.reset();m.type('abcdefghijk');assert not m.call('input',m.obj,ord('x')<<8)
    assert m.text()=='abcdefghijk'
    initial='ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ';final=' ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ'
    count=0
    for ch in font.hangul2350():
        n=ord(ch)-0xac00;l=n//588;v=n//28%21;t=n%28
        m.reset();m.type(initial[l]+chr(0x314f+v)+(final[t] if t else ''))
        assert m.text()==ch,(ch,m.text());count+=1
    # Mapper preserves every original entry, including uncommon Japanese symbols.
    original,entries,extra=ime_patch.catalog();table=font.read_table(original)
    checked=0
    for hi in list(range(0x81,0xa0))+list(range(0xe0,0xeb))+[0xed,0xee,0xef]:
        for lo in range(256):
            k=((hi-0x81) if hi<0xa0 else (hi-0xc1 if hi<0xeb else hi-0xc3 if hi<0xef else hi-0xc4))*256+lo
            if k<len(table):assert m.call('glyph_lookup',hi*256+lo)==table[k];checked+=1
    # Run actual ABI wrappers too; emulate the EE-specific SQ/LQ instructions
    # at their memory boundaries (Unicorn MIPS32 has no 128-bit EE GPR support).
    m.reset();m.u.reg_write(UC_MIPS_REG_T3,0x12345678)
    assert m.call('e_input',m.obj,m.codes['ㄱ'])==1
    assert m.u.reg_read(UC_MIPS_REG_T3)==0x12345678
    assert m.text()=='ㄱ'
    assert m.call('e_glyph_lookup',m.codes['김'])==entries['김'][1]
    assert m.u.reg_read(UC_MIPS_REG_T3)==0x12345678
    for mode in [0,1]:
        for y in range(9):
            for x in range(11):
                address=m.call('e_keylabel',mode,x,y)
                value=bytes(m.u.mem_read(address,4)).split(b'\0')[0]
                assert len(value)<=2
                if len(value)==2:assert int.from_bytes(value,'big') in m.reverse
    report=dict(bank_sha256=hashlib.sha256((ime_patch.TMP/'bank.bin').read_bytes()).hexdigest(),result='PASS',method='Actual compiled MIPS code in Unicorn; game rendering/audio stubbed; EE SQ/LQ modeled at low-32-bit memory boundaries',
                syllables_tested=count,original_lookup_entries_tested=checked,cases=cases,
                checks=['composition','compound vowels','compound finals','final migration','backspace','cursor insertion','reopen','11-byte limit','buffer guards'],
                square_callback_cases=square_cases,engine_stack_alignment=16,engine_boundary_calls=m.engine_calls,
                animation_completion='PASS',runtime_game_tested=False)
    (ROOT/'validation/ime_tests.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
