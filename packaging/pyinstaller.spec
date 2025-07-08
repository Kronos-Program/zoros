# PyInstaller spec for Zoros executable
block_cipher = None

import os
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules('zoros_whisper_cpp') + collect_submodules('zoros_lang_service')

a = Analysis(
    ['zoros/cli.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=[('pyproject.toml', '.')],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='zoros',
    debug=False,
    strip=False,
    upx=True,
    console=True,
)
