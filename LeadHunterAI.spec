# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec para gerar LeadHunterAI.app (macOS)."""
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

hiddenimports = (
    collect_submodules("PySide6")
    + collect_submodules("sqlalchemy.dialects")
    + ["openai", "loguru", "phonenumbers", "fake_useragent",
       "playwright", "playwright.sync_api"]
)

datas = [
    ("config/settings.default.json", "config"),
] + collect_data_files("fake_useragent")

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["selenium", "tkinter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LeadHunterAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="LeadHunterAI",
)

app = BUNDLE(
    coll,
    name="LeadHunterAI.app",
    icon=None,
    bundle_identifier="ai.leadhunter.desktop",
    info_plist={
        "CFBundleDisplayName": "LeadHunter AI",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
    },
)
