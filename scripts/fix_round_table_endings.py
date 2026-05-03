#!/usr/bin/env python3
import os
import re

FOLDER = 'Overleaf_LaTeX/tabellen'

def fix_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    out = []
    for line in lines:
        s = line.replace('\\"', ' \\\\')
        stripped = s.strip()
        if '&' in s and not stripped.startswith('\\hline') and not stripped.startswith('\\end') and not stripped.startswith('\\begin') and not stripped.startswith('\\caption') and not stripped.startswith('%'):
            # normalize first column: remove comma+digits suffix for component names containing letters
            parts = s.split('&', 1)
            first = parts[0]
            rest = parts[1] if len(parts) > 1 else ''
            if re.search(r"[A-Za-zÄÖÜäöüß]", first):
                new_first = re.sub(r",\d+(?:[.,]\d+)?", "", first).strip()
                # ensure spacing matches original (keep a single space after the field)
                s = new_first + ' & ' + rest.lstrip()
            # ensure trailing \\\\ at line end
            if not re.search(r"\\\\\s*$", s):
                s = s.rstrip() + ' \\\\' + '\n'
        out.append(s)
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(out)

if __name__ == '__main__':
    if not os.path.isdir(FOLDER):
        print('Folder not found:', FOLDER)
        raise SystemExit(1)
    for fname in os.listdir(FOLDER):
        if not fname.lower().endswith('_round.tex'):
            continue
        p = os.path.join(FOLDER, fname)
        print('Fixing', p)
        fix_file(p)
    print('Done')
