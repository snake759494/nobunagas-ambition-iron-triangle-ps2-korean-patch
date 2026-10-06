# N12F 텍스트/스크립트 컨테이너
# 0x00 'N12F' | u32 str_sec(문자열부 절대오프셋) | u32 nscript | u32 a | u32 b
# 0x14 u32 script_off[nscript] + 스크립트 텍스트
# str_sec: u32 N, u32 base_id, u32 off[N+1] (풀 시작 기준, 마지막=풀 길이), 풀(종료문자 없음)
import struct
def parse(d):
    assert d[:4]==b'N12F'
    sec=struct.unpack_from('<I',d,4)[0]
    n,base=struct.unpack_from('<II',d,sec)
    offs=struct.unpack_from(f'<{n+1}I',d,sec+8)
    pool=sec+8+4*(n+1)
    strs=[d[pool+offs[i]:pool+offs[i+1]] for i in range(n)]
    return sec,base,strs,pool+offs[n]
def build(d,strs):
    sec,base,old,end=parse(d)
    blob=b''.join(strs); offs=[0]
    for s in strs: offs.append(offs[-1]+len(s))
    out=d[:sec]+struct.pack('<II',len(strs),base)+struct.pack(f'<{len(offs)}I',*offs)+blob
    tail=d[end:]
    out+=tail
    return out
