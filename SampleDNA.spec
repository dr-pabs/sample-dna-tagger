# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Sample DNA Tagger.

Builds a one-folder bundle containing the FastAPI backend + compiled React
SPA.  On macOS this is wrapped in a .app bundle; on Windows it produces a
directory with a windowed (console=False) executable.

Usage:
    pyinstaller SampleDNA.spec --clean --noconfirm
"""

import os
import sys
from pathlib import Path

block_cipher = None


# ── Helpers ───────────────────────────────────────────────────────────────

def _walk_datas(root: str, dest_prefix: str) -> list[tuple[str, str]]:
    """Walk *root* and return (src, dest_dir) tuples for every regular file.

    __pycache__ directories are skipped to avoid shipping stale bytecode.
    """
    entries: list[tuple[str, str]] = []
    p = Path(root)
    if not p.is_dir():
        print(f"WARNING: {root} is not a directory — SPA will be missing!")
        return entries
    for f in p.rglob("*"):
        if f.is_file() and "__pycache__" not in f.parts:
            dest = Path(dest_prefix) / f.relative_to(p).parent
            entries.append((str(f), str(dest)))
    return entries


# ── Data files ────────────────────────────────────────────────────────────

# Ship the compiled React SPA so FastAPI can serve it at runtime.
# server.py resolves frontend/dist relative to its own location:
#   Path(__file__).resolve().parent.parent / "frontend" / "dist"
# In the bundle this maps to {MEIPASS}/frontend/dist — which matches the
# dest_prefix used here.
datas = _walk_datas("frontend/dist", "frontend/dist")


# ── Hidden imports ────────────────────────────────────────────────────────

hiddenimports = [
    # ── ASGI / FastAPI ──
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "fastapi",
    "fastapi.middleware",
    "fastapi.middleware.cors",
    "starlette",
    # ── pywebview ──
    "webview",
    "webview.platforms.cocoa",
    # ── Audio processing ──
    "librosa",
    "librosa.core",
    "librosa.feature",
    "librosa.util",
    "soundfile",
    "numpy",
    "numpy.core",
    "numpy.linalg",
    "numpy.fft",
    "numpy.random",
    "numpy.random._common",
    "essentia",
    "essentia.standard",
    # ── AI / LLM ──
    "openai",
    # ── Database ──
    "aiosqlite",
    "sqlalchemy",
    "sqlalchemy.ext.asyncio",
    # ── Data validation ──
    "pydantic",
    "pydantic.deprecated",
    "pydantic.fields",
    # ── Utilities ──
    "aiofiles",
    "dotenv",
    "python_multipart",
    # ── App modules ──
    "sample_dna_tagger",
    "sample_dna_tagger.db",
    "sample_dna_tagger.scanner",
    "sample_dna_tagger.llm",
    "sample_dna_tagger.server",
    "sample_dna_tagger.routes",
    "sample_dna_tagger.routes.browse",
    "sample_dna_tagger.routes.samples",
    "sample_dna_tagger.routes.scan",
    "sample_dna_tagger.routes.search",
    "sample_dna_tagger.routes.settings",
    "sample_dna_tagger.waveform",
    "sample_dna_tagger.watcher",
    "watchdog",
    "watchdog.observers",
    "watchdog.events",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
]

# macOS-specific: pywebview needs the Cocoa bridge
if sys.platform == "darwin":
    hiddenimports.extend([
        "pywebview.platforms.cocoa",
        "Foundation",
        "AppKit",
        "WebKit",
        "objc",
        "CoreFoundation",
    ])

# Windows-specific: pywebview needs the WinForms bridge
if sys.platform == "win32":
    hiddenimports.extend([
        "pywebview.platforms.winforms",
        "clr",
        "System",
        "System.Windows.Forms",
        "System.Drawing",
    ])


# ── Excludes ──────────────────────────────────────────────────────────────

excludes = [
    "test",
    "tests",
    "pytest",
    "unittest",
    "doctest",
    "setuptools",
    "pip",
    "wheel",
    "pkg_resources",
    "easy_install",
    "tkinter",
    "turtle",
    "matplotlib",
    "pylab",
    "IPython",
    "jupyter",
    "sphinx",
    "cx_Freeze",
    "py2app",
    "email.mime",
    "distutils",
]


# ═══════════════════════════════════════════════════════════════════════════
#  Analysis — resolve all imports and data files
# ═══════════════════════════════════════════════════════════════════════════

a = Analysis(
    ["launch.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)


# ═══════════════════════════════════════════════════════════════════════════
#  PYZ — compress pure-Python modules
# ═══════════════════════════════════════════════════════════════════════════

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)


# ═══════════════════════════════════════════════════════════════════════════
#  EXE — bootstrap executable
# ═══════════════════════════════════════════════════════════════════════════

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Sample DNA Tagger",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,                     # no terminal window on Windows
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,                         # TODO: add .ico path for Windows
)


# ═══════════════════════════════════════════════════════════════════════════
#  COLLECT — gather everything into the output directory
# ═══════════════════════════════════════════════════════════════════════════

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Sample DNA Tagger",
)


# ═══════════════════════════════════════════════════════════════════════════
#  BUNDLE — macOS .app wrapper
# ═══════════════════════════════════════════════════════════════════════════

if sys.platform == "darwin":
    # Allow codesign identity to be set via env var for CI/CD
    codesign_identity = os.environ.get("CODESIGN_IDENTITY", None)
    entitlements_file = "entitlements.plist" if os.path.exists("entitlements.plist") else None

    app = BUNDLE(
        coll,
        name="Sample DNA Tagger.app",
        icon=None,                     # TODO: add .icns path when icon is available
        bundle_identifier="com.sampledna.tagger",
        info_plist={
            "CFBundleName": "Sample DNA Tagger",
            "CFBundleDisplayName": "Sample DNA Tagger",
            "CFBundleIdentifier": "com.sampledna.tagger",
            "CFBundleVersion": "0.1.0",
            "CFBundleShortVersionString": "0.1.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSRequiresAquaSystemAppearance": False,
        },
        codesign_identity=codesign_identity,
        entitlements_file=entitlements_file,
    )
