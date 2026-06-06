import os

src = os.path.join(os.path.dirname(__file__), 'test_aspen_luftzerlegung_single.py')
dst = os.path.join(os.path.dirname(__file__), 'single2.py')

replacements = {
    'parser_run_single.log': 'parser_run_single2.log',
    'aspen_luftzerlegung_single.json': 'aspen_luftzerlegung_single2.json',
    'aspen_luftzerlegung_streams_single.tex': 'aspen_luftzerlegung_streams_single2.tex',
    'aspen_luftzerlegung_components_single.tex': 'aspen_luftzerlegung_components_single2.tex',
    'aspen_luftzerlegung_components_work_single.tex': 'aspen_luftzerlegung_components_work_single2.tex',
    'aspen_luftzerlegung_blocks_ed_single.tex': 'aspen_luftzerlegung_blocks_ed_single2.tex',
    'aspen_luftzerlegung_blocks_ed_comparison.tex': 'aspen_luftzerlegung_blocks_ed_comparison2.tex',
    'aspen_luftzerlegung_streams_molfrac_single.tex': 'aspen_luftzerlegung_streams_molfrac_single2.tex',
}

with open(src, 'r', encoding='utf-8') as f:
    text = f.read()

for a, b in replacements.items():
    text = text.replace(a, b)

with open(dst, 'w', encoding='utf-8') as f:
    f.write(text)

print(f'Created {dst} from {src} with updated output filenames.')
