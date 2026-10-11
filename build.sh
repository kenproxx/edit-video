#!/usr/bin/env bash
set -euo pipefail
case "$(uname -s)" in
  MINGW*|MSYS*) ;;
  *) echo 'Build requires Windows x64 with Git Bash; PyInstaller cannot cross-build Windows EXE on Linux.' >&2; exit 1 ;;
esac
script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w "$script_dir/scripts/bootstrap-build.ps1")" "$@"
