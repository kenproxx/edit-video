import sys
import os
from pathlib import Path
from PySide6.QtWidgets import QApplication,QMessageBox
from .binaries import resolve_binaries
from .ui.window import EditorWindow
from .ui.controller import EditorController

def main() -> int:
    if '--self-test' in sys.argv: os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    app=QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('Edit Video')
    try:binaries=resolve_binaries()
    except Exception as exc:
        QMessageBox.critical(None,'Không khởi động được',str(exc)); return 1
    if '--self-test' in sys.argv:
        from .self_test import run_self_test
        return run_self_test(Path(sys.argv[sys.argv.index('--self-test')+1]),binaries)
    window=EditorWindow(); window.controller=EditorController(window,binaries); window.show()
    return app.exec()

if __name__=='__main__':raise SystemExit(main())
