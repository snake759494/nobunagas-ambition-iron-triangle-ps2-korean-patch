# -*- coding: utf-8 -*-
"""N12F 문자열 -> translation/src/n12f.tsv (file, idx, msgid, text). 제어바이트는 <LF><CR><TAB>."""
import os, sys, glob
sys.path.insert(0, os.path.dirname(__file__))
from n12f import parse
from codec import decode
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def esc(t): return t.replace('\n', '<LF>').replace('\r', '<CR>').replace('\t', '<TAB>')
def unesc(t): return t.replace('<LF>', '\n').replace('<CR>', '\r').replace('<TAB>', '\t')
def main():
    rows = []
    for p in sorted(glob.glob(os.path.join(ROOT, 'work/GR/*.bin'))):
        d = open(p, 'rb').read()
        if d[:4] != b'N12F': continue
        i = int(os.path.basename(p)[:4])
        sec, base, strs, end = parse(d)
        for k, s in enumerate(strs):
            rows.append((i, k, base + k, esc(decode(s))))
    with open(os.path.join(ROOT, 'translation/src/n12f.tsv'), 'w', encoding='utf-8') as f:
        for r in rows: f.write('%d\t%d\t%d\t%s\n' % r)
    return rows
if __name__ == '__main__':
    rows = main()
    print(len(rows), sum(len(r[3]) for r in rows))
