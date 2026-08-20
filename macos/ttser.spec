# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

SPECDIR = Path(SPECPATH).resolve()
REPO = SPECDIR.parent
PAYLOAD = SPECDIR / "payload"
VERSION = os.environ.get("TTSER_VERSION", "0.5.0")

binaries: list[tuple[str, str]] = []
datas: list[tuple[str, str]] = [
    (str(REPO / "dictionaries" / "s2_terms_ru.json"), "dictionaries"),
    (str(REPO / "dictionaries" / "s2_pronunciation_ru.json"), "dictionaries"),
    (str(REPO / "voices" / "tankindycast.s2voice"), "voices"),
    (str(REPO / "s2.cpp" / "tokenizer.json"), "s2.cpp"),
]
if PAYLOAD.is_dir():
    for path in PAYLOAD.rglob("*"):
        if not path.is_file():
            continue
        rel_dir = str(path.parent.relative_to(PAYLOAD))
        if path.suffix == ".dylib" or path.name == "ffmpeg":
            binaries.append((str(path), rel_dir))
        else:
            datas.append((str(path), rel_dir))

icon_icns = SPECDIR / "ttser.icns"
icon = str(icon_icns) if icon_icns.is_file() else None

qt_excludes = [
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtGraphs",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNfc",
    "PySide6.QtPdf",
    "PySide6.QtPositioning",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngine",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
    "PySide6.QtXml",
]

hiddenimports = sorted(set(collect_submodules("engine") + collect_submodules("ttser")))

gui_a = Analysis(
    [str(SPECDIR / "gui_entry.py")],
    pathex=[str(REPO)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=qt_excludes,
    noarchive=False,
)
gui_pyz = PYZ(gui_a.pure)
gui_exe = EXE(
    gui_pyz,
    gui_a.scripts,
    [],
    exclude_binaries=True,
    name="ttser",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

synth_a = Analysis(
    [str(REPO / "engine" / "s2_synth.py")],
    pathex=[str(REPO)],
    binaries=binaries,
    datas=[],
    hiddenimports=collect_submodules("engine"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6", "shiboken6", *qt_excludes],
    noarchive=False,
)
synth_pyz = PYZ(synth_a.pure)
synth_exe = EXE(
    synth_pyz,
    synth_a.scripts,
    [],
    exclude_binaries=True,
    name="ttser-synth",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    gui_exe,
    gui_a.binaries,
    gui_a.datas,
    synth_exe,
    synth_a.binaries,
    synth_a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ttser",
)

app = BUNDLE(
    coll,
    name="ttser.app",
    icon=icon,
    bundle_identifier="com.tagantank.ttser",
    info_plist={
        "CFBundleName": "ttser",
        "CFBundleDisplayName": "ttser",
        "CFBundleShortVersionString": VERSION.lstrip("v"),
        "CFBundleVersion": VERSION.lstrip("v"),
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
    },
)
