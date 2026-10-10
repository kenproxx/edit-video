from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import tempfile
import threading
from PySide6.QtCore import QObject,Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QFileDialog,QMessageBox
from ..models import EditSettings,Rect,validate
from ..media import probe
from ..pipeline import RenderRequest
from ..jobs import run_export,PreviewCoordinator,Cancelled
from ..output import OutputTarget,validate_target

class EditorController(QObject):
    loaded=Signal(object,str)
    finished=Signal(str,str)
    progressed=Signal(float)
    def __init__(self,window,binaries):
        super().__init__(window); self.w=window; self.binaries=binaries; self.media=None; self.busy=False; self.closed=False
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='export'); self.cancel=threading.Event()
        self.folder=tempfile.TemporaryDirectory(prefix='edit-video-preview-'); self.preview=PreviewCoordinator(binaries)
        self.preview.ready.connect(self.show_preview); self.preview.failed.connect(lambda _,error:self.error(error))
        self.loaded.connect(self._loaded); self.finished.connect(self._finished); self.progressed.connect(lambda p:self.w.progress.setValue(round(p*100)))
        window.open_button.clicked.connect(self.select_video); window.folder_button.clicked.connect(self.select_folder)
        window.controls.changed.connect(self.refresh); window.timeline.valueChanged.connect(self.refresh); window.mode.currentIndexChanged.connect(self.refresh)
        window.controls.preset.currentTextChanged.connect(self.preset)
        window.canvas.region_changed.connect(self.region); window.canvas.position_changed.connect(self.position)
        window.export_button.clicked.connect(lambda:self.export('video')); window.cover_button.clicked.connect(lambda:self.export('thumbnail'))
        window.cancel_button.clicked.connect(self.cancel.set)
    def select_video(self):
        path,_=QFileDialog.getOpenFileName(self.w,'Chọn video','','Video (*.mp4 *.mov *.mkv *.avi *.webm *.m4v);;Tất cả (*)')
        if path:self.load_video(Path(path))
    def select_folder(self):
        path=QFileDialog.getExistingDirectory(self.w,'Chọn thư mục xuất',self.w.output_dir.text())
        if path:self.w.output_dir.setText(path)
    def set_busy(self,value):
        self.busy=value
        for widget in (self.w.controls,self.w.open_button,self.w.timeline,self.w.mode,self.w.output_dir,self.w.output_name,self.w.folder_button,self.w.format,self.w.export_button,self.w.cover_button): widget.setEnabled(not value)
        self.w.cancel_button.setEnabled(value and self.media is not None)
    def load_video(self,path):
        if self.busy or self.closed:return
        self.media=None; self.set_busy(True); self.w.status.setText('Đang đọc video…')
        def work():
            try:self.loaded.emit(probe(Path(path),self.binaries),'')
            except Exception as exc:self.loaded.emit(None,str(exc))
        self.executor.submit(work)
    def _loaded(self,media,error):
        if self.closed:return
        self.set_busy(False)
        if error:self.error(error);return
        self.media=media; self.w.controls.reset_all(); self.w.timeline.setValue(0)
        self.w.source_label.setText(str(media.path)); self.w.output_name.setText(media.path.stem+'.mp4')
        self.w.output_dir.setText(str(media.path.parent/'edited'))
        self.w.info.setText(f'{media.width} × {media.height}  •  {media.duration:.2f} giây  •  {media.fps:.2f} fps  •  '+('Có âm thanh' if media.audio_index is not None else 'Không có âm thanh'))
        self.w.status.setText('Video đã sẵn sàng. Chọn hiệu ứng hoặc xuất ảnh bìa.'); self.refresh()
    def error(self,message):
        self.w.status.setText(message.splitlines()[0]); self.w.log.setPlainText(message); self.w.log.show()
    def refresh(self,*_):
        if self.media is None or self.busy or self.closed:return
        try:
            settings=self.w.controls.settings(); validate(settings)
            mode=self.w.mode.currentData(); self.w.canvas.mode=mode
            if mode=='crop':settings=EditSettings()
            time=self.w.timeline.value()/1000*max(0,self.media.duration-1/self.media.fps)
            self.w.time_label.setText(f'{int(time)//60:02}:{time%60:06.3f}')
            path=Path(self.folder.name)/f'frame-{self.preview.generation+1}.png'
            request=RenderRequest(self.media,settings,path,'thumbnail' if mode=='cover' else 'preview',time)
            self.preview.submit(request)
        except Exception as exc:self.error(str(exc))
    def show_preview(self,generation,path):
        self.w.canvas.set_frame(QImage(path))
        # QImage owns decoded pixels. Old PNGs can now be discarded.
        for old in Path(self.folder.name).glob('frame-*.png'):
            if str(old)!=path:
                try:old.unlink()
                except OSError:pass
    def preset(self,text):
        if self.media is None or text=='Tự do':return
        a,b=map(float,text.split(':')); target=a/b; source=self.media.width/self.media.height
        width,height=(target/source,1) if source>target else (1,source/target)
        self.w.controls.crop.set_rect(Rect((1-width)/2,(1-height)/2,width,height))
    def region(self,mode,rect):
        if self.busy:return
        if mode=='crop':self.w.controls.preset.setCurrentText('Tự do')
        getattr(self.w.controls,mode).set_rect(rect)
    def position(self,mode,x,y):
        if self.busy:return
        if mode=='logo':self.w.controls.logo_x.setValue(x*100); self.w.controls.logo_y.setValue(y*100)
        else:
            layer=getattr(self.w.controls,mode); layer.x.setValue(x*100); layer.y.setValue(y*100)
    def export(self,mode):
        if self.media is None or self.busy or self.closed:return
        try:
            settings=self.w.controls.settings(); validate(settings)
            directory=Path(self.w.output_dir.text()).expanduser()
            if not self.w.output_dir.text().strip():raise ValueError('Hãy chọn thư mục xuất.')
            name=self.w.output_name.text().strip() if mode=='video' else self.media.path.stem+'_thumbnail.'+self.w.format.currentText().lower()
            if Path(name).name!=name or not name or name in ('.','..'):raise ValueError('Tên file không hợp lệ.')
            if mode=='video' and not name.lower().endswith('.mp4'):name+='.mp4'
            directory.mkdir(parents=True,exist_ok=True); dest=directory/name
            validate_target(OutputTarget(self.media.path,dest,True))
            overwrite=False
            if dest.exists():
                overwrite=QMessageBox.question(self.w,'File đã tồn tại',f'Ghi đè {dest.name}?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes
                if not overwrite:return
            request=RenderRequest(self.media,settings,dest,mode,self.w.timeline.value()/1000*max(0,self.media.duration-1/self.media.fps))
            self.cancel=threading.Event(); self.set_busy(True); self.w.progress.setValue(0); self.w.log.hide(); self.w.status.setText('Đang xuất…')
            def work():
                try:self.finished.emit(str(run_export(request,self.binaries,overwrite,self.cancel,self.progressed.emit)),'')
                except Cancelled:self.finished.emit('','Đã hủy tác vụ.')
                except Exception as exc:self.finished.emit('',str(exc))
            self.executor.submit(work)
        except Exception as exc:self.error(str(exc))
    def _finished(self,path,error):
        if self.closed:return
        self.set_busy(False)
        if error:self.error(error)
        else:self.w.status.setText('Đã xuất: '+path)
    def close(self):
        if self.closed:return
        self.closed=True; self.cancel.set(); self.preview.close(); self.executor.shutdown(wait=True,cancel_futures=True); self.folder.cleanup()
