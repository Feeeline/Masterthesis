#!/usr/bin/env python3
"""
Copy all .tex files from Overleaf_LaTeX/tabellen, create _round copies,
and apply rounding rules:
- Default: two decimals (except special columns)
- For molfrac files (filename contains 'molfrac'): apply sig-fig rules,
  remove floating artifacts, thresholds, and normalize rows to sum=1.

Usage: python scripts/round_latex_tables.py [--dir PATH]
"""
import re
import os
import argparse
from decimal import Decimal


def parse_num(token):
    t = token.strip()
    if t == '':
        return None
    # remove braces and replace unicode minus and decimal comma
    t = t.replace('{', '').replace('}', '')
    t = t.replace('−', '-')
    t = t.replace(',', '.')
    # extract a numeric substring that may include scientific notation
    m = re.search(r"[-+]?(?:\d+\.?\d*|\.?\d+)(?:[eE][-+]?\d+)?", t)
    if not m:
        return None
    num_txt = m.group(0)
    try:
        return float(num_txt)
    except Exception:
        return None


def format_non_mol(x, decimals=2):
    return (f"{x:.{decimals}f}").replace('.', ',')


def format_scientific(x, sig):
    s = f"{x:.{sig}e}"
    # normalize exponent format like 1.23e-05
    parts = s.split('e')
    mant = parts[0].rstrip('0').rstrip('.')
    exp = parts[1].lstrip('+').zfill(2) if parts[1].startswith('-') else parts[1].lstrip('+')
    return mant + 'e' + exp


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
            s = format_scientific(float(s), sig)
    elif 1e-4 < ax <= 0.01:
        sig = 6
        s = f"{x:.{sig}g}"
        if 'e' in s:
            s = format_scientific(float(s), sig)
    else:
        sig = 3
        s = format_scientific(x, sig)
    # remove trailing decimal dot if present
    if 'e' not in s and '.' in s:
        s = s.rstrip('0').rstrip('.')
    s = s.replace('.', ',')
    return s


def process_table_block(block_lines, filename):
    out = []
    # find header (first line with & that contains non-numeric tokens like $ or letters)
    header_idx = None
    for i, line in enumerate(block_lines):
        if '&' in line:
            if re.search(r"\\\\|hline", line):
                continue
            # treat as header if it contains $ or letters (not numbers)
            if re.search(r"\\\$|[A-Za-z\\{}_^*]", line) and not re.search(r"\d", line.split('&', 1)[1]):
                header_idx = i
                break
            # fallback: first & line before numeric rows
            if header_idx is None:
                header_idx = i
                break
    col_names = []
    if header_idx is not None:
        cols = [c.strip() for c in block_lines[header_idx].split('&')]
        col_names = [re.sub(r"\$|\\", '', c).strip() for c in cols]

    is_mol = 'molfrac' in filename.lower()
    # detect special columns to skip 2-decimal rounding
    special_cols = set()
    for idx, name in enumerate(col_names):
        if any(tok in name for tok in ['varepsilon', 'y_{D,k}', 'y^*_{D,k}', 'epsilon', 'y_D', 'y^*']):
            special_cols.add(idx)

    # Process each line
    for line in block_lines:
        if '&' not in line or line.strip().startswith('%'):
            out.append(line)
            continue
        parts = [p for p in line.split('&')]
        new_parts = []
        numeric_indices = []
        nums = []
        # first pass: detect numeric columns
        for i, p in enumerate(parts):
            # remove trailing LaTeX backslashes and end-of-line comments for numeric detection
            p_clean = re.sub(r"\\\\\s*$", "", p).strip()
            p_clean = re.sub(r"%.*$", "", p_clean).strip()
            n = parse_num(p_clean)
            if n is not None:
                numeric_indices.append(i)
                nums.append(n)
        # If molfrac and we have numeric columns, normalize row
        if is_mol and nums:
            total = sum(nums)
            if total == 0:
                norm = nums
            else:
                norm = [v / total for v in nums]
            # assign back
            num_iter = iter(norm)
            for i, p in enumerate(parts):
                p_clean = re.sub(r"\\\\\s*$", "", p).strip()
                p_clean = re.sub(r"%.*$", "", p_clean).strip()
                n = parse_num(p_clean)
                if n is None:
                    new_parts.append(p)
                else:
                    v = next(num_iter)
                    # thresholding
                    if abs(v) < 1e-12:
                        s = '0'
                    elif v > 0.999999:
                        s = '1'
                    else:
                        s = format_sigfig(v)
                    # keep original trailing backslashes if present
                    trailing = ''
                    m = re.search(r"(\\\\\s*)$", p)
                    if m:
                        trailing = m.group(1)
                    new_parts.append(' ' + s + ' ' + trailing)
        elif nums:
            # non-molfrac numeric rounding: two decimals except special columns
            num_iter = iter(nums)
            for i, p in enumerate(parts):
                p_clean = re.sub(r"\\\\\s*$", "", p).strip()
                p_clean = re.sub(r"%.*$", "", p_clean).strip()
                n = parse_num(p_clean)
                if n is None:
                    new_parts.append(p)
                else:
                    if i in special_cols:
                        # keep original with cleaned artifacts: strip excessive digits
                        s = ('%g' % n)
                        s = s.replace('.', ',')
                    else:
                        s = format_non_mol(n, decimals=2)
                    # preserve trailing backslashes if present
                    trailing = ''
                    m = re.search(r"(\\\\\s*)$", p)
                    if m:
                        trailing = m.group(1)
                    new_parts.append(' ' + s + ' ' + trailing)
        else:
            new_parts = parts
        newline = '&'.join(new_parts)
        # ensure trailing \\\\ if original line had it
        if '\\\\' in line:
            if not newline.strip().endswith('\\\\'):
                newline = newline.rstrip() + ' \\\\'
        out.append(newline)
    return out


def process_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    # find longtable blocks
    pattern = re.compile(r"(\\begin\{longtable\}.*?\\end\{longtable\})", re.S)
    new_text = text
    for m in pattern.finditer(text):
        block = m.group(1)
        lines = block.splitlines()
        processed = process_table_block(lines, os.path.basename(path))
        new_block = '\n'.join(processed)
        new_text = new_text.replace(block, new_block)

    return new_text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', default='Overleaf_LaTeX/tabellen', help='folder with .tex tables')
    args = parser.parse_args()
    folder = args.dir
    if not os.path.isdir(folder):
        print('Folder not found:', folder)
        return
    for fname in os.listdir(folder):
        # skip already-rounded outputs to avoid creating _round_round files
        if not fname.lower().endswith('.tex'):
            continue
        if fname.lower().endswith('_round.tex'):
            continue
        src = os.path.join(folder, fname)
        base, ext = os.path.splitext(fname)
        dst_name = base + '_round' + ext
        dst = os.path.join(folder, dst_name)
        print('Processing', fname, '->', dst_name)
        new = process_file(src)
        with open(dst, 'w', encoding='utf-8') as f:
            f.write(new)


if __name__ == '__main__':
    main()
