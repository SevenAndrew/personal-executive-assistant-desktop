# -*- mode: python ; coding: utf-8 -*-

import re
from pathlib import Path

ROOT = Path(SPECPATH).parent
VERSION_SOURCE = (ROOT / "pea_app" / "__init__.py").read_text(encoding="utf-8")
VERSION = re.search(r'__version__ = "([^"]+)"', VERSION_SOURCE).group(1)
ICON = ROOT / "build" / "macos" / "PEA.icns"

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "pea_app" / "assets"), "pea_app/assets"),
        (str(ROOT / "pea_app" / "installer_assets"), "pea_app/installer_assets"),
        (str(ROOT / "LICENSES"), "LICENSES"),
        (str(ROOT / "THIRD_PARTY_NOTICES.md"), "."),
        (str(ROOT / "LICENSE"), "."),
    ],
    hiddenimports=["keyring.backends.macOS"],
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
    [],
    exclude_binaries=True,
    name="PEA",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PEA",
)
app = BUNDLE(
    coll,
    name="PEA.app",
    icon=str(ICON),
    bundle_identifier="com.sevenandrew.pea",
    info_plist={
        "CFBundleDisplayName": "PEA",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSApplicationCategoryType": "public.app-category.productivity",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "Copyright © SevenAndrew 2026",
    },
)
