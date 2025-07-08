"""Build the Zoros executable using PyInstaller."""
from __future__ import annotations

import subprocess
from pathlib import Path

SPEC_PATH = Path(__file__).resolve().parent.parent / 'packaging' / 'pyinstaller.spec'


def main() -> None:
    subprocess.run([
        'pyinstaller',
        '--clean',
        '--onefile',
        str(SPEC_PATH),
    ], check=True)


if __name__ == '__main__':
    main()
