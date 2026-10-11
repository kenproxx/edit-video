# Build on Windows x64 using scripts/bootstrap-build.ps1 only.
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_data_files

if sys.platform != 'win32':
    raise SystemExit('VideoEditor.spec requires Windows x64; no cross-compilation.')
root = Path(SPECPATH)
licenses = root/'build'/'licenses'
if not licenses.is_dir():
    raise SystemExit('Run bootstrap-build.ps1 first to collect licenses.')
binaries = [(str(root/'tools'/name),'tools') for name in ('ffmpeg.exe','ffprobe.exe')]
datas = collect_data_files('customtkinter') + [
    (str(licenses),'licenses'),
    (str(root/'THIRD_PARTY_NOTICES.md'),'.'),
    (str(root/'scripts'/'build-manifest.json'),'build-metadata'),
    (str(root/'scripts'/'build-wheels.json'),'build-metadata'),
    (str(root/'requirements-build.txt'),'build-metadata'),
]
a = Analysis([str(root/'main.py')],pathex=[str(root)],binaries=binaries,datas=datas,
             hiddenimports=[],hookspath=[],hooksconfig={},runtime_hooks=[],excludes=[],noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,a.binaries,a.datas,[],name='VideoEditor',debug=False,
          bootloader_ignore_signals=False,strip=False,upx=False,console=False,
          disable_windowed_traceback=False)
