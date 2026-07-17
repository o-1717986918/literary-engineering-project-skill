"""Test-time import shim for unittest discovery.

`python -m unittest discover -s tests` may put `tests/` on sys.path without
putting the repository root or `src/` there. This shim redirects imports to the
real src-layout package so tests do not depend on an editable install.
"""

from pathlib import Path


REAL_PACKAGE = Path(__file__).resolve().parents[2] / "src" / "literary_engineering_workbench"
__path__ = [str(REAL_PACKAGE)]

init_file = REAL_PACKAGE / "__init__.py"
if init_file.exists():
    exec(compile(init_file.read_text(encoding="utf-8"), str(init_file), "exec"), globals())
