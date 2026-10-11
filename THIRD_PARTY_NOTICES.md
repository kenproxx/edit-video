# Third-party components

Build pins and upstream checksum sources are in `scripts/build-manifest.json` and `scripts/build-wheels.json`. Full license texts are collected from installed distribution metadata and the verified FFmpeg archive into `dist/licenses/`; the same texts and these notices are embedded in the EXE. Keep the external notices/licenses with a shared build so recipients can read them without launching it.

| Component | Version | License / upstream |
| --- | --- | --- |
| Python, Tcl/Tk | Python 3.13.12; Tcl/Tk supplied by official installer | PSF and bundled third-party terms; https://www.python.org/ |
| CustomTkinter | 5.2.2 | MIT; https://github.com/TomSchimansky/CustomTkinter |
| darkdetect | 0.8.0 | BSD-3-Clause; https://github.com/albertosottile/darkdetect |
| Pillow | 12.3.0 | HPND and bundled codec/font libraries; full composite Pillow license in licenses/Pillow |
| packaging | 26.3 | Apache-2.0 / BSD-2-Clause |
| FFmpeg / ffprobe, Gyan essentials static build | 8.1.2 | GPL v3 as stated by the release README; https://github.com/GyanD/codexffmpeg/releases/tag/8.1.2 |
| PyInstaller bootloader/runtime hooks | 6.22.3 | GPL-2.0-or-later with bootloader exception; runtime hooks Apache-2.0; full terms included |

Build-only wheel dependencies (pip, setuptools, altgraph, pefile, pywin32-ctypes and pyinstaller-hooks-contrib) are pinned in `requirements-build.txt`; their license texts are also collected. CustomTkinter font/shape assets are collected with package data. Roboto fonts use Apache-2.0; `licenses/Roboto-APACHE-2.0.txt` contains the full text obtained from https://github.com/googlefonts/roboto-2/blob/38062f4b4a0be4346d07a928408da21602545e9e/LICENSE . Other asset license files supplied by the package are copied where available. Windows fonts are loaded from the recipient's own system, not redistributed.

## FFmpeg corresponding source

The verified archive README identifies FFmpeg source commit https://github.com/FFmpeg/FFmpeg/commit/38b88335f9 and lists the static build configuration and external libraries, including x264/x265. `licenses/ffmpeg/README.txt` preserves that complete list; `licenses/ffmpeg/LICENSE` preserves the upstream GPL text. Builder information: https://www.gyan.dev/ffmpeg/builds/ and https://github.com/m-ab-s/media-autobuild_suite .

This repository does not yet contain a complete corresponding-source bundle for that third-party static build, including external-library sources and build scripts. A link to the FFmpeg core alone is not a substitute. Before distributing its binaries, provide the complete corresponding source under the applicable GPL terms alongside the binary distribution, using the build provider's matching source/build information. No release publication is performed by the supplied workflow.
