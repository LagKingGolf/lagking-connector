# -*- mode: python ; coding: utf-8 -*-
import glob


a = Analysis(
    ['LagKingConnector.py'],
    pathex=[],
    binaries=[],
    # OCR language data for the screenshot launch monitors -- without these
    # bundled, every screenshot-based monitor is dead in the built exe. Plus
    # LICENSE and README so the binary carries its licence, the GPLv3 5(a)
    # modification notice, and the source location.
    datas=[(f, '.') for f in glob.glob('*.traineddata')]
          + [('LICENSE', '.'), ('README.md', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LagKingConnector',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
