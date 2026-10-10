# Build on Windows. The runtime remains replaceable in an onedir distribution.
from pathlib import Path
import os
root=Path(SPECPATH)
ffmpeg=Path(os.environ['EDIT_VIDEO_FFMPEG_DIR'])
a=Analysis([str(root/'scripts/launch.py')],pathex=[str(root/'src')],
 binaries=[(str(ffmpeg/'ffmpeg.exe'),'bin'),(str(ffmpeg/'ffprobe.exe'),'bin')],
 datas=[(str(root/'.build/licenses'),'licenses'),(str(root/'THIRD_PARTY_NOTICES.md'),'.'),(str(root/'README.md'),'.')],
 hiddenimports=['edit_video.self_test'],excludes=['PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets','PySide6.QtQml','PySide6.QtQuick'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='EditVideo',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='EditVideo')
