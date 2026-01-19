# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller спецификация для TransGoogleTest
"""

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Добавляем примеры конфигурации
        ('config.json.example', '.'),
        ('README.md', '.'),
        ('QUICKSTART.md', '.'),
    ],
    hiddenimports=[
        # App modules
        'app.ui.main_window',
        'app.services.translation_service',
        'app.services.speech_service',
        'app.services.tts_service',
        'app.services.tts_factory',
        'app.services.tts_providers.base_provider',
        'app.services.tts_providers.elevenlabs_provider',
        'app.services.tts_providers.google_cloud_provider',
        'app.models.dialogue',
        'app.widgets.chat_widget',
        'app.config',
        # External libraries
        'speech_recognition',
        'sounddevice',
        'numpy',
        'scipy',
        'requests',
        'PyQt5.QtMultimedia',
        'PyQt5.QtMultimediaWidgets',
        # Speech recognition backends
        'speech_recognition.audio',
        'speech_recognition.exceptions',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'PIL',
        'tkinter',
        'jupyter',
        'notebook',
        'IPython',
        'pandas',
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
    name='TransGoogleTest',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # С консолью для отладки
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Можно добавить свою иконку: icon='icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TransGoogleTest',
)
