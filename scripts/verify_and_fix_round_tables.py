#!/usr/bin/env python3
"""
Verify and fix _round .tex tables in Overleaf_LaTeX/tabellen.
- For files with 'molfrac' in the name: ensure each numeric row sums to 1,
  apply sig-fig formatting, thresholds (0, 1), and consistent scientific format.
- For other _round files: check formatting consistency (commas as decimal sep).

Usage: python scripts/verify_and_fix_round_tables.py --dir Overleaf_LaTeX/tabellen
"""
import re
import os
import argparse


def parse_num_token(t):
    s = t.strip()
    if s == '':
        return None
    s = s.replace('{', '').replace('}', '')
    s = s.replace('\u2212', '-')
    s = s.replace(',', '.')
    # handle scientific with e (maybe comma decimal)
    try:
        return float(s)
    except Exception:
        return None


def format_scientific(x, sig):
    s = f"{x:.{sig}e}"
    mant, exp = s.split('e')
    mant = mant.rstrip('0').rstrip('.')
    exp = exp.lstrip('+')
    # ensure 2-digit exponent with sign
    if not exp.startswith('-'):
        exp = exp
    return mant.replace('.', ',') + 'e' + exp


def format_sigfig(x):
    ax = abs(x)
    if ax < 1e-12:
        return '0'
    if x > 0.999999:
        return '1'
    if ax > 0.01:
        sig = 4
        s = f"{x:.{sig}g}"
        if 'e' in s:
            return format_scientific(float(s), sig)
        return s.replace('.', ',')
    elif 1e-4 < ax <= 0.01:
        sig = 6
        s = f"{x:.{sig}g}"
        if 'e' in s:
            return format_scientific(float(s), sig)
        return s.replace('.', ',')
    else:
        sig = 3
        return format_scientific(x, sig)


def process_longtable(block_lines, is_mol):
    out = []
    # detect header and special columns (epsilon, y_{D,k}, y^*_{D,k})
    special_cols = set()
    for i, line in enumerate(block_lines):
        if '&' in line:
            if any(tok in line for tok in ['varepsilon', '\\varepsilon', 'y_{D,k}', 'y^*_{D,k}', 'y_D', 'y^*']):
                cols = [c.strip() for c in line.split('&')]
                for idx, c in enumerate(cols):
                    clean = c.replace('$', '').replace('\\', '').replace(' ', '')
                    if any(name in clean for name in ['varepsilon', 'y_{D,k}', 'y^*_{D,k}', 'y_D', 'y^*']):
                        special_cols.add(idx)
                break
    for line in block_lines:
        if '&' not in line or line.strip().startswith('%'):
            out.append(line)
            continue
        parts = line.split('&')
        nums_idx = []
        nums = []
        for i, p in enumerate(parts):
            n = parse_num_token(p)
            if n is not None:
                nums_idx.append(i)
                nums.append(n)
        if is_mol and nums:
            total = sum(nums)
            if total == 0:
                norm = nums
            else:
                norm = [v / total for v in nums]
            # apply thresholds and formatting
            new_parts = list(parts)
            for idx, v in zip(nums_idx, norm):
                if abs(v) < 1e-12:
                    s = '0'
                elif v > 0.999999:
                    s = '1'
                else:
                    s = format_sigfig(v)
                new_parts[idx] = ' ' + s + ' '
            newline = '&'.join(new_parts)
            out.append(newline)
        else:
            # ensure decimal commas for non-mol numeric tokens
            new_parts = list(parts)
            for idx in range(len(parts)):
                if parse_num_token(parts[idx]) is not None:
                    v = parse_num_token(parts[idx])
                    # if this column is special, force 4 decimals
                    if idx in special_cols:
                        s = f"{v:.4f}".replace('.', ',')
                    else:
                        if abs(v) >= 1:
                            s = f"{v:.2f}".replace('.', ',')
                        else:
                            s = f"{v:.4f}".rstrip('0').rstrip('.').replace('.', ',')
                    new_parts[idx] = ' ' + s + ' '
            out.append('&'.join(new_parts))
    return out


def verify_and_fix(folder):
    files = [f for f in os.listdir(folder) if f.endswith('_round.tex')]
    for fname in files:
        path = os.path.join(folder, fname)
        text = open(path, 'r', encoding='utf-8').read()
        is_mol = 'molfrac' in fname.lower()
        changed = False
        pattern = re.compile(r"(\\begin\{longtable\}.*?\\end\{longtable\})", re.S)
        new_text = text
        for m in pattern.finditer(text):
            block = m.group(1)
            lines = block.splitlines()
            processed = process_longtable(lines, is_mol)
            new_block = '\n'.join(processed)
            if new_block != block:
                new_text = new_text.replace(block, new_block)
                changed = True
        if changed:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_text)
            print('Fixed', fname)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', default='Overleaf_LaTeX/tabellen')
    args = parser.parse_args()
    folder = args.dir
    if not os.path.isdir(folder):
        print('Folder not found:', folder)
        return
    verify_and_fix(folder)


if __name__ == '__main__':
    main()
