# -*- coding: utf-8 -*-
"""게임 영문 표기(헵번식, 장음 0xC0=Ō 0xC1=ō 0xC2=Ū 0xC3=ū) -> 히라가나 -> 한글(kana2hangul).
성/이름 등 단어마다 따로 변환해야 어두 규칙이 맞는다."""
import re
from kana2hangul import word

MAC = {'À': 'O-', 'Á': 'o-', 'Â': 'U-', 'Ã': 'u-', 'Ō': 'O-', 'ō': 'o-', 'Ū': 'U-', 'ū': 'u-'}
# 장음부호는 'ー'(생략), 철자 ou 는 장음으로 보되 ~ouchi(内) 는 오+우치
T = {
 'kya':'きゃ','kyu':'きゅ','kyo':'きょ','sha':'しゃ','shu':'しゅ','sho':'しょ','cha':'ちゃ','chu':'ちゅ','cho':'ちょ',
 'nya':'にゃ','nyu':'にゅ','nyo':'にょ','hya':'ひゃ','hyu':'ひゅ','hyo':'ひょ','mya':'みゃ','myu':'みゅ','myo':'みょ',
 'rya':'りゃ','ryu':'りゅ','ryo':'りょ','gya':'ぎゃ','gyu':'ぎゅ','gyo':'ぎょ','ja':'じゃ','ju':'じゅ','jo':'じょ',
 'bya':'びゃ','byu':'びゅ','byo':'びょ','pya':'ぴゃ','pyu':'ぴゅ','pyo':'ぴょ',
 'shi':'し','chi':'ち','tsu':'つ','ji':'じ','fu':'ふ',
 'ka':'か','ki':'き','ku':'く','ke':'け','ko':'こ','ga':'が','gi':'ぎ','gu':'ぐ','ge':'げ','go':'ご',
 'sa':'さ','su':'す','se':'せ','so':'そ','za':'ざ','zu':'ず','ze':'ぜ','zo':'ぞ',
 'ta':'た','te':'て','to':'と','da':'だ','de':'で','do':'ど','di':'ぢ','du':'づ',
 'na':'な','ni':'に','nu':'ぬ','ne':'ね','no':'の','ha':'は','hi':'ひ','he':'へ','ho':'ほ',
 'ba':'ば','bi':'び','bu':'ぶ','be':'べ','bo':'ぼ','pa':'ぱ','pi':'ぴ','pu':'ぷ','pe':'ぺ','po':'ぽ',
 'ma':'ま','mi':'み','mu':'む','me':'め','mo':'も','ya':'や','yu':'ゆ','yo':'よ',
 'ra':'ら','ri':'り','ru':'る','re':'れ','ro':'ろ','wa':'わ','wo':'を',
 'a':'あ','i':'い','u':'う','e':'え','o':'お',
}
def to_kana(s):
    s = ''.join(MAC.get(c, c) for c in s).lower()
    s = re.sub(r'ou(?=chi|e)', 'o_u', s).replace('ou', 'o-').replace('o_u', 'ou')
    out = []; i = 0
    while i < len(s):
        c = s[i]
        if c == "'": i += 1; continue
        if c == '-': out.append('ー'); i += 1; continue
        if c == 'n' and (i + 1 == len(s) or s[i+1] not in 'aiueoy'):
            out.append('ん'); i += 1
            if i < len(s) and s[i] == "'": i += 1
            continue
        if c == 'm' and i + 1 < len(s) and s[i+1] in 'bpm':
            out.append('ん'); i += 1; continue
        if i + 1 < len(s) and c == s[i+1] and c not in 'aiueon':
            out.append('っ'); i += 1; continue
        if c == 't' and s[i:i+3] == 'tch':
            out.append('っ'); i += 1; continue
        for L in (3, 2, 1):
            if s[i:i+L] in T:
                out.append(T[s[i:i+L]]); i += L; break
        else:
            return None
    return ''.join(out)

def ko(s):
    """영문 단어(공백/하이픈 구분) -> 한글. 변환 불가면 None."""
    parts = re.split(r'( |-(?=[A-ZŌŪÀÂ]))', s)
    res = []
    for p in parts:
        if p == ' ':
            res.append(' '); continue
        if p == '-':
            res.append('·'); continue
        if not p: continue
        k = to_kana(p)
        if k is None: return None
        res.append(word(k, keep_long=True))
    return ''.join(res)

if __name__ == '__main__':
    for t in ['Kakizaki','Kond\xc1','Nanj\xc1','Ch\xc1sokabe','Ry\xc3z\xc1ji','Kikkawa','Hattori','Shin\'ichi','Honganji','Ii','Sanada','Ky\xc3sh\xc3','\xc0saka','Nobunaga','Gamou','Sait\xc1 D\xc1san']:
        print(t, to_kana(t), ko(t))
