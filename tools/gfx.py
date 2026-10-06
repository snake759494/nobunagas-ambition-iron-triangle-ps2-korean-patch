# -*- coding: utf-8 -*-
"""그래픽 라벨 한글화: F11N 34(커맨드/월/계절), 33(待機/出陣), 868(로딩), 1012(타이틀)."""
import os, sys, struct, collections
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from f11n2 import parse, sxy
from relabel import relabel
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CMDS = ['시장', '징병', '요새', '조달', '동맹', '혼인', '고무', '위보', '연구', '철거', '해체', '요구', '편집', '빼내기',
        '방침', '이동', '은거', '위임', '가보', '개수', '관위', '협박', '포상', '건설', '소환', '습격', '교섭', '유언', '생산',
        '선동', '편성', '처벌', '출진', '수리', '탐색', '정전', '파괴', '등용', '역직', '호출', '요청', '수송']
CATS = ['외교', '군사', '군단', '인사', '정보', '계략', '마을', '평정']
MAP34 = {66: '봄', 67: '여름', 68: '가을', 69: '겨울'}
MAP34.update({70 + i: '%d월' % (i + 1) for i in range(12)})
for i, t in enumerate(CATS): MAP34[91 + i] = t
for i, t in enumerate(CATS[:7]): MAP34[99 + i] = t
MAP34[106] = '평정'
for base in (107, 149, 191):
    for i, t in enumerate(CMDS): MAP34[base + i] = t
for base in (233, 237, 241):
    for i, t in enumerate(['무장', '기술', '거점', '개요']): MAP34[base + i] = t
for k, t in zip(range(265, 269), ['동맹', '대상', '정전', '요청']): MAP34[k] = t
MAP34.update({272: '계획', 273: '계획', 274: '실행', 275: '실행'})

def patch_f11n(d, mapping, size_scale=1.0, align='center', font_size=None):
    d = bytearray(d)
    spr, tx = parse(bytes(d))
    done = set(); n = 0
    for k, text in sorted(mapping.items()):
        sx, sy, w, h, t, c = sxy(spr[k])
        tex = tx[c]
        src = tex['pixsrc']
        key = (src, sx, sy, w, h)
        if key in done: continue
        done.add(key)
        base = tx[src]
        idx = base['idx'].copy()
        if relabel(idx, base['pal'], (sx, sy, w, h), text, align=align, size_scale=size_scale, font_size=font_size):
            n += 1
            write_idx(d, base, idx)
            base['idx'] = idx
    return bytes(d), n

def write_idx(d, tex, idx):
    xo = tex['pix_off']
    if tex['bpp'] == 4:
        f = idx.reshape(-1).astype(np.uint8)
        d[xo:xo + len(f) // 2] = (f[0::2] | (f[1::2] << 4)).tobytes()
    else:
        f = idx.reshape(-1).astype(np.uint8).tobytes()
        d[xo:xo + len(f)] = f

def find_label_sprites(d, word_hint=None):
    pass

MAP33 = {788: '대기', 789: '출진', 918: '신규'}
W35 = {'Continue': '이어하기', 'Create': '신규 작성', 'Officer Edit': '무장 편집', 'Unification Mode': '천하통일 모드',
       'Local Mode': '지방제패 모드', 'Edit': '편집', 'Created Officers': '신무장', 'Historical Officers': '실존 무장',
       'Game Settings': '환경 설정', 'BGM Gallery': 'BGM 감상', 'Delete': '삭제', 'Register': '등록', 'Reset': '초기화',
       'Options': '옵션', 'Save': '세이브', 'Challenge Mode': '도전 모드', 'New Game': '새 게임', 'Load': '로드',
       'Tutorial': '튜토리얼', 'Game Previews': '게임 소개'}
_seq = [(98, 'Continue'), (99, 'Create'), (100, 'Officer Edit'), (101, 'Unification Mode'), (102, 'Local Mode'), (103, 'Edit'),
        (104, 'Created Officers'), (105, 'Historical Officers'), (106, 'Game Settings'), (125, 'BGM Gallery'), (126, 'Delete'),
        (128, 'Created Officers'), (129, 'Historical Officers'), (130, 'Register'), (131, 'Edit'), (132, 'Reset'), (133, 'Register'),
        (134, 'Options'), (135, 'Save'), (158, 'Challenge Mode'), (159, 'New Game'), (160, 'Load'), (161, 'Tutorial'), (176, 'Game Previews')]
_row = ['Continue', 'Create', 'Officer Edit', 'Unification Mode', 'Local Mode', 'Edit', 'Created Officers', 'Historical Officers', 'Game Settings']
_seq += [(107 + i, w) for i, w in enumerate(_row)] + [(116 + i, w) for i, w in enumerate(_row)]
_row2 = ['BGM Gallery', 'Delete', None, 'Created Officers', 'Historical Officers', 'Register', 'Edit', 'Reset', 'Register', 'Options', 'Save']
_seq += [(136 + i, w) for i, w in enumerate(_row2) if w] + [(147 + i, w) for i, w in enumerate(_row2) if w]
_seq += [(164, 'Challenge Mode'), (165, 'New Game'), (166, 'Load'), (167, 'Tutorial'), (170, 'Challenge Mode'), (171, 'New Game'),
         (172, 'Load'), (173, 'Tutorial'), (177, 'Game Previews'), (178, 'Game Previews')]
MAP35 = {k: W35[w] for k, w in _seq}
MAP35.update({127: '모바일 연동', 138: '모바일 연동', 149: '모바일 연동',
              162: '설치', 168: '설치', 174: '설치',
              163: '설치 삭제', 169: '설치 삭제', 175: '설치 삭제'})

def patch_logo(d, sprite):
    """Encode the reviewed Korean logo into the existing texture/palette."""
    from PIL import Image, ImageOps
    from f11n import unswizzle
    d = bytearray(d)
    spr, tx = parse(bytes(d))
    x,y,w,h,t,c = sxy(spr[sprite]); tex=tx[c]; base=tx[tex['pixsrc']]
    im=Image.open(os.path.join(ROOT, 'assets/title_ko.png')).convert('RGBA')
    im=im.crop(im.getchannel('A').getbbox())
    im=ImageOps.contain(im,(w-2,h-2),Image.Resampling.LANCZOS)
    canvas=Image.new('RGBA',(w,h)); canvas.alpha_composite(im,((w-im.width)//2,(h-im.height)//2))
    idx=base['idx'].copy()
    assert [z['i'] for z in tx if z['pixsrc']==base['i']] == [base['i']]
    assert [k for k,s in enumerate(spr) if tx[s[4]]['pixsrc']==base['i']] == [sprite]
    # Both logo textures own their palettes. Retain the generated alpha instead
    # of forcing it onto the original white shadow ramp.
    q=canvas.quantize(colors=len(tex['pal']),method=Image.Quantize.FASTOCTREE)
    pal=np.array(q.getpalette('RGBA'),dtype=np.uint8).reshape(-1,4)[:len(tex['pal'])]
    pal[:,3]=np.rint(pal[:,3].astype(float)*128/255).astype(np.uint8)
    po=tex['pal_off']
    d[po:po+len(pal)*4]=(unswizzle(pal) if len(pal)==256 else pal).tobytes()
    idx[y:y+h,x:x+w]=np.asarray(q)
    write_idx(d,base,idx)
    return bytes(d)

def patch_868(d):
    from f11n import unswizzle
    d = bytearray(d)
    idx = np.frombuffer(bytes(d), np.uint8, 640*448, 0x80).reshape(448, 640).copy()
    pal = unswizzle(np.frombuffer(bytes(d), np.uint8, 1024, len(d) - 1024).reshape(256, 4))
    n = 0
    for box, text, sc in (((300, 2, 38, 18), '도움말', 1.5), ((444, 2, 62, 16), "스크롤", 1.5), ((171, 130, 222, 25), '로딩 중', 1.2)):
        n += relabel(idx, pal, box, text, size_scale=sc, font=os.path.join(ROOT, 'NanumSquareNeo-cBd.ttf') if box[3] < 20 else os.path.join(ROOT, 'SeoulHangangB.ttf'))
    from PIL import Image, ImageOps
    from relabel import nearest_palette
    im=Image.open(os.path.join(ROOT,'assets/title_ko.png')).convert('RGBA')
    im=im.crop(im.getchannel('A').getbbox())
    im=ImageOps.contain(im,(173,72),Image.Resampling.LANCZOS)
    canvas=Image.new('RGBA',(175,74))
    canvas.alpha_composite(im,((175-im.width)//2,(74-im.height)//2))
    idx[54:128,174:349]=nearest_palette(np.asarray(canvas),pal)
    d[0x80:0x80 + 640*448] = idx.tobytes()
    return bytes(d), n

def patch_1012(d):
    d = bytearray(d)
    spr, tx = parse(bytes(d))
    t = tx[1]
    idx = t['idx'].copy()
    ok = relabel(idx, t['pal'], (0, 0, t['w'], t['h']), 'START 버튼을 누르세요')
    if ok: write_idx(d, t, idx)
    return bytes(d), int(ok)

def patch_fixed39(d):
    """F11N fixed records: 2 KiB header, 152 independent 512x240 textures.
    Records 116..151 are BGM titles, not portraits or script strings.
    """
    from f11n import unswizzle
    d=bytearray(d)
    count, copies, stride=struct.unpack_from('<III',d,4)
    assert (count,copies,stride)==(152,152,124928)
    assert len(d)==2048+count*stride
    rows=[line.rstrip('\n').split('\t') for line in open(os.path.join(ROOT,'translation/image_bgm.tsv'),encoding='utf-8')]
    assert [int(row[0]) for row in rows]==list(range(116,152))
    for number,original,text in rows:
        at=2048+int(number)*stride
        pal=unswizzle(np.frombuffer(bytes(d),np.uint8,1024,at).reshape(256,4))
        idx=np.frombuffer(bytes(d),np.uint8,512*240,at+1024).reshape(240,512).copy()
        assert relabel(idx,pal,(0,0,512,60),text,align='left',size_scale=1.0)
        d[at+1024:at+1024+512*240]=idx.tobytes()
    return bytes(d),len(rows)

def build(gr):
    gr[34], n = patch_f11n(gr[34], MAP34, size_scale=1.15)
    gr[33], n2 = patch_f11n(gr[33], MAP33, size_scale=1.3)
    gr[35], n5 = patch_f11n(gr[35], MAP35, size_scale=1.1, align='left')
    gr[35] = patch_logo(gr[35], 72)
    print('35번 메뉴', n5)
    gr[868], n3 = patch_868(gr[868])
    gr[1012], n4 = patch_1012(gr[1012])
    gr[1012] = patch_logo(gr[1012], 0)
    gr[39], n6 = patch_fixed39(gr[39])
    print('BGM 곡명 이미지', n6)
    print('그래픽 라벨', n, n2, n3, n4)
