# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for NeuroView
Build with: pyinstaller neuroview.spec
"""

import sys
from pathlib import Path

block_cipher = None

# Get the project directory
PROJECT_DIR = Path(SPECPATH)

# Data files to include
datas = [
    (str(PROJECT_DIR / 'brain_viewer.html'), '.'),
    (str(PROJECT_DIR / 'backend' / 'server.py'), 'backend'),
]

# Hidden imports that PyInstaller might miss
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    'fastapi',
    'starlette',
    'starlette.routing',
    'starlette.middleware',
    'starlette.middleware.cors',
    'nibabel',
    'nibabel.nifti1',
    'nibabel.nifti2',
    'scipy.ndimage',
    'scipy.spatial',
    'skimage',
    'skimage.measure',
    'PIL',
    'webview',
]

a = Analysis(
    ['desktop_app.py'],
    pathex=[str(PROJECT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'tkinter',
        'PyQt5',
        'PySide2',
    ],
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
    name='NeuroView',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=True,  # For macOS
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
    upx=True,
    upx_exclude=[],
    name='NeuroView',
)

# macOS app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='NeuroView.app',
        icon=None,  # Add icon path here if you have one
        bundle_identifier='com.neuroview.app',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleName': 'NeuroView',
            'CFBundleDisplayName': 'NeuroView',
            'NSRequiresAquaSystemAppearance': 'False',  # Support dark mode
        },
    )
