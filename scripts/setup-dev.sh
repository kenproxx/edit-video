#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${VIDEO_EDITOR_PYTHON:-python3}"
"$PYTHON_BIN" -c 'import sys; assert sys.version_info[:2] == (3, 12), "Use Python 3.12"'
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install --requirement requirements-dev.txt
if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  if command -v apt-get >/dev/null; then
    if [[ $(id -u) == 0 ]]; then
      apt-get update
      apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core
    else
      sudo apt-get update
      sudo apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core
    fi
  else
    echo 'Linux development setup requires apt-get; Windows build bootstrap is delivered in phase 4.' >&2
    exit 1
  fi
fi
ffmpeg -version
ffprobe -version
