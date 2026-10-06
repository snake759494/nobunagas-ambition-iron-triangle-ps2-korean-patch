# -*- coding: utf-8 -*-
"""번역 작업 파일 생성: translation/jobs/{t,e,n}NN.tsv (+ _names.tsv)
  id <TAB> lim <TAB> en       lim = 결과 최대 바이트(한글=2) 또는 '-'"""
import os, sys, re, collections
sys.path.insert(0, os.path.dirname(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = os.path.join(ROOT, 'translation/jobs')
NAME_A0, NAME_A1 = 0x544A80, 0x548400   # ELF 무작위 이름 목록(자동 음역)

def load_names():
    full = {}
    for l in open(os.path.join(ROOT, 'translation/fullnames.tsv'), encoding='utf-8'):
        e, k = l.rstrip('\n').split('\t'); full[e] = k
    single = {}
    for l in list(open(os.path.join(ROOT, 'translation/names.tsv'), encoding='utf-8'))[1:]:
        kind, en, ko, y, note = l.rstrip('\n').split('\t')
        single.setdefault(en, set()).add((kind, ko))
    return full, single

CAP = re.compile(r"[A-ZŌŪ][a-zōū']+(?:[ -][A-ZŌŪ][a-zōū']+)*")
def names_in(text, full, single):
    out = {}
    for m in CAP.finditer(text):
        words = re.split(r'(?<=[a-zōū]) ', m.group())
        # 가장 긴 성명부터
        i = 0
        while i < len(words):
            hit = False
            for L in (3, 2):
                cand = ' '.join(words[i:i+L])
                if cand in full:
                    out[cand] = full[cand]; i += L; hit = True; break
                for suf, ko in ((' Castle', '성'), (' Port', '항')):
                    pass
            if hit: continue
            w = words[i]
            for cand in (w, w + ' Castle'):
                if cand in single:
                    out[cand] = ' / '.join(sorted({k for _, k in single[cand]}))
            i += 1
    return out

def write_job(name, rows, full, single):
    os.makedirs(J, exist_ok=True)
    with open(os.path.join(J, name + '.tsv'), 'w', encoding='utf-8') as f:
        for r in rows: f.write('\t'.join(map(str, r)) + '\n')
    nm = {}
    for r in rows: nm.update(names_in(r[2], full, single))
    with open(os.path.join(J, name + '_names.tsv'), 'w', encoding='utf-8') as f:
        for e in sorted(nm): f.write(e + '\t' + nm[e] + '\n')

def blen(s): return sum(2 if ord(c) > 0x7f else 1 for c in s)

def main():
    full, single = load_names()
    # 1) 용어
    terms = [l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'translation/src/terms.tsv'), encoding='utf-8')]
    a = [('%s|%s' % (t[0], t[2]), t[1], t[2] + ('' if not t[4] else '   ⟨%s⟩' % t[4])) for t in terms if t[0] in ('item', 'title', 'rank')]
    b = [('%s|%s' % (t[0], t[2]), t[1], t[2] + ('' if not t[4] else '   ⟨%s⟩' % t[4])) for t in terms if t[0] not in ('item', 'title', 'rank')]
    write_job('t01', a, full, single); write_job('t02', b, full, single)
    # 2) ELF
    elf = [l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'translation/src/elf.tsv'), encoding='utf-8')]
    rows = []
    for o, cap, t in elf:
        oo = int(o, 16)
        if NAME_A0 <= oo < NAME_A1: continue
        if t.startswith('\\') or t.startswith('789:'): continue
        rows.append((o, cap, t))
    n = (len(rows) + 2) // 3
    for k in range(3): write_job('e%02d' % (k + 1), rows[k*n:(k+1)*n], full, single)
    # 3) N12F
    src = [l.rstrip('\n').split('\t', 3) for l in open(os.path.join(ROOT, 'translation/src/n12f.tsv'), encoding='utf-8')]
    seen = set(); jobs = []; cur = []; size = 0; lastf = None
    LIMIT = 27000
    for f, k, m, t in src:
        if t in ('', 'Error'): continue
        if len(t) >= 25:
            if t in seen: continue
            seen.add(t)
        lim = blen(t) if len(t) < 40 else '-'
        if cur and (size >= LIMIT or (f != lastf and size >= LIMIT * 0.6)):
            jobs.append(cur); cur = []; size = 0
        cur.append(('%s:%s' % (f, k), lim, t)); size += len(t); lastf = f
    if cur: jobs.append(cur)
    for i, rows in enumerate(jobs): write_job('n%02d' % (i + 1), rows, full, single)
    print('n jobs', len(jobs), [sum(len(r[2]) for r in j) for j in jobs])

if __name__ == '__main__':
    main()
