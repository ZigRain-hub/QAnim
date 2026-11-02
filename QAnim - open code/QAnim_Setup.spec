# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\lovec\\QULW\\cmd\\QAnim\\installer.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\lovec\\QULW\\cmd\\QAnim\\qanim_payload.zip', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick', 'PySide6.QtWebChannel', 'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.Qt3DInput', 'PySide6.Qt3DLogic', 'PySide6.Qt3DAnimation', 'PySide6.Qt3DExtras', 'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets', 'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'PySide6.QtPdf', 'PySide6.QtPdfWidgets', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets', 'PySide6.QtQml', 'PySide6.QtQmlModels', 'PySide6.QtQmlWorkerScript', 'PySide6.QtSql', 'PySide6.QtTest', 'PySide6.QtHelp', 'PySide6.QtDesigner', 'PySide6.QtUiTools', 'PySide6.QtBluetooth', 'PySide6.QtNfc', 'PySide6.QtPositioning', 'PySide6.QtLocation', 'PySide6.QtSerialPort', 'PySide6.QtSensors', 'PySide6.QtSvg', 'PySide6.QtSvgWidgets', 'PySide6.QtXml', 'PySide6.QtNetwork', 'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets', 'PySide6.QtConcurrent', 'PySide6.QtDBus', 'PySide6.QtStateMachine', 'PySide6.QtRemoteObjects', 'PySide6.QtScxml', 'PySide6.QtSpatialAudio', 'PySide6.QtTextToSpeech', 'PySide6.QtWebSockets', 'PySide6.QtHttpServer', 'tkinter', 'unittest', 'pydoc', 'doctest', 'test', 'distutils', 'setuptools', 'pip', 'lib2to3', 'xmlrpc', 'sqlite3', 'curses', 'readline'],
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
    name='QAnim_Setup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
