#!/usr/bin/env bash
set -euo pipefail
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) ;; *) echo 'Chay script nay trong Git Bash tren Windows x64, hoac dung build_exe.bat.' >&2; exit 1;; esac
cd -- "$(dirname -- "$0")"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./scripts/bootstrap.ps1 "$@"
