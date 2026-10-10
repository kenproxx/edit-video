# Third-party components

The portable build includes dynamically loaded Python 3.12.10 and Qt/PySide6 6.8.3,
and separate FFmpeg/ffprobe 7.1.1 executables. Original license files are copied to
`_internal/licenses` by the build. Do not remove them when redistributing the ZIP.

- Python: PSF license; https://www.python.org/downloads/release/python-31210/
  Source: https://www.python.org/ftp/python/3.12.10/Python-3.12.10.tar.xz
- Qt/PySide6: LGPLv3/GPLv3 or commercial terms; this build uses the open-source
  dynamically linked Qt Core/Gui/Widgets libraries. Source for Qt 6.8.3:
  https://download.qt.io/archive/qt/6.8/6.8.3/single/
  PySide source: https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.8.3-src/
  Qt libraries in `_internal` may be replaced with compatible modified builds.
- FFmpeg: Gyan essentials GPL build with libx264. It is invoked as an independent
  executable, not linked into the Python application. Binary distribution:
  https://github.com/GyanD/codexffmpeg/releases/tag/7.1.1
  FFmpeg source: https://github.com/FFmpeg/FFmpeg/tree/n7.1.1
  Build information and dependencies: https://www.gyan.dev/ffmpeg/builds/
  See the included FFmpeg LICENSE and README for its configuration and terms.
- PyInstaller: GPL with the bootloader exception; https://pyinstaller.org/en/v6.13.0/license.html

The project does not assign a license to the application's own source code on
behalf of the repository owner. Dependency notices do not change ownership.
