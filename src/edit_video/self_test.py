"""End-to-end smoke entry point for the frozen executable."""
import json
from pathlib import Path
import subprocess
import threading
from .binaries import process_options
from .media import probe
from .models import EditSettings,TextLayer,BlurLayer,Rect
from .pipeline import RenderRequest
from .jobs import run_export

def run_self_test(directory: Path,binaries) -> int:
    directory.mkdir(parents=True,exist_ok=True)
    result={'success':False,'ffmpeg':str(binaries.ffmpeg),'ffprobe':str(binaries.ffprobe)}
    try:
        source=directory/'nguồn thử.mp4'
        subprocess.run([str(binaries.ffmpeg),'-v','error','-y','-f','lavfi','-i','testsrc2=size=160x120:rate=20:duration=1','-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','libx264','-threads','1','-c:a','aac',str(source)],check=True,capture_output=True,timeout=30,**process_options())
        media=probe(source,binaries)
        settings=EditSettings(speed=2,flip_h=True,blur=BlurLayer(Rect(0,0,.5,.5)),watermark=TextLayer(text='Tiếng Việt',size_px=14),cover=TextLayer(text='Ảnh bìa',size_px=20,y=.5))
        for mode,name in [('video','edited.mp4'),('thumbnail','cover.png')]:
            run_export(RenderRequest(media,settings,directory/name,mode),binaries,True,threading.Event(),lambda _:None)
        from .ui.window import EditorWindow
        from PySide6.QtWidgets import QApplication
        window=EditorWindow(); window.show(); QApplication.processEvents()
        window.grab().save(str(directory/'window.png')); window.close()
        result['success']=True
    except Exception as exc:result['error']=str(exc)
    (directory/'self-test.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if result['success'] else 1
