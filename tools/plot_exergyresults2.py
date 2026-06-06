"""Run tools/plot_exergy_results.py but append '2' to all saved plot filenames.

This lightweight wrapper monkeypatches matplotlib.figure.Figure.savefig so
the original plotting module doesn't need to be modified. Any call that
saves a figure to a filename (str/Path or kwarg 'fname') will get a '2'
inserted before the file extension.
"""

from pathlib import Path
import runpy
import builtins
from matplotlib.figure import Figure


def _patched_savefig(self, *args, **kwargs):
    orig = _patched_savefig.__orig
    fname = None
    if args:
        candidate = args[0]
        if isinstance(candidate, (str, Path)):
            fname = Path(candidate)
    if fname is None and 'fname' in kwargs:
        candidate = kwargs['fname']
        if isinstance(candidate, (str, Path)):
            fname = Path(candidate)

    if fname is not None:
        new_name = fname.with_name(fname.stem + '2' + fname.suffix)
        try:
            new_name.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        if args:
            args = (str(new_name),) + args[1:]
        else:
            kwargs['fname'] = str(new_name)
        return orig(self, *args, **kwargs)

    return orig(self, *args, **kwargs)


def main():
    # patch Figure.savefig
    orig_save = Figure.savefig
    _patched_savefig.__orig = orig_save
    Figure.savefig = _patched_savefig

    # patch Path.open and builtins.open to prefer '*single2*' files when available
    _orig_path_open = Path.open
    _orig_builtin_open = builtins.open

    def _patched_path_open(self, *args, **kwargs):
        try:
            name = self.name
        except Exception:
            return _orig_path_open(self, *args, **kwargs)
        if 'single' in name and 'single2' not in name:
            candidate = self.with_name(self.stem + '2' + self.suffix)
            if candidate.exists():
                return _orig_path_open(candidate, *args, **kwargs)
        return _orig_path_open(self, *args, **kwargs)

    def _patched_builtin_open(file, *args, **kwargs):
        try:
            p = Path(file)
            name = p.name
        except Exception:
            return _orig_builtin_open(file, *args, **kwargs)
        if 'single' in name and 'single2' not in name:
            candidate = p.with_name(p.stem + '2' + p.suffix)
            if candidate.exists():
                return _orig_builtin_open(str(candidate), *args, **kwargs)
        return _orig_builtin_open(file, *args, **kwargs)

    Path.open = _patched_path_open
    builtins.open = _patched_builtin_open

    try:
        # run the original plotting script in its module context
        runpy.run_path(str(Path(__file__).parent / 'plot_exergy_results.py'), run_name='__main__')
    finally:
        # restore patched functions
        Figure.savefig = orig_save
        Path.open = _orig_path_open
        builtins.open = _orig_builtin_open


if __name__ == '__main__':
    main()
