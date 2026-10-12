"""Main-thread UI coordination; native media work runs in bounded controllers."""
from dataclasses import replace
from pathlib import Path
import os
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from .loader import MediaLoader
from .models import Rect, validate_options, default_output
from .output import reserve_output
from .preview import PreviewController
from .worker import RenderWorker
from .ui_options import OptionsPanel
from .ui_canvas import PreviewCanvas
from .timing import trimmed_duration

MODES = {'Xem kết quả':'preview','Chọn crop':'crop','Chọn vùng blur':'blur','Vị trí logo':'logo','Vị trí watermark':'watermark','Vị trí text đầu':'intro'}


class VideoEditorApp(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode('dark')
        # System fonts cover Vietnamese even when bundled Roboto cannot register
        # in a read-only Linux home; Windows Segoe UI is present by default.
        ctk.ThemeManager.theme['CTkFont']['family'] = 'Segoe UI' if os.name == 'nt' else 'DejaVu Sans'
        super().__init__()
        self.title('Video Editor')
        self.geometry('1120x820');self.minsize(700,560)
        self.columnconfigure(0,weight=1);self.rowconfigure(1,weight=1)
        self.source_path = self.media_info = None
        self.worker = RenderWorker()
        self.preview = PreviewController()
        self.loader = MediaLoader()
        self._load_generation = self._preview_generation = 0
        self._preview_context = None
        self._display_mode = None
        self._last_terminal = None
        self._closing = self._destroyed = False
        self._preview_after = None
        self._warning = ''
        self.source_var = tk.StringVar(value='Chưa chọn video')
        self.output_dir_var = tk.StringVar()
        self.output_name_var = tk.StringVar()
        self.status_var = tk.StringVar(value='Chọn video để bắt đầu')
        self.mode_var = tk.StringVar(value='Xem kết quả')
        self.time_var = tk.DoubleVar(value=0)
        self._build()
        self.protocol('WM_DELETE_WINDOW',self.request_close)
        self._poll_after = self.after(40,self._poll)

    def _build(self):
        top = ctk.CTkFrame(self)
        top.grid(row=0,column=0,sticky='ew',padx=12,pady=(12,6));top.columnconfigure(1,weight=1)
        self.video_button = ctk.CTkButton(top,text='Chọn video',width=140,command=self.choose_video)
        self.video_button.grid(row=0,column=0,padx=8,pady=6)
        self.source_entry = ctk.CTkEntry(top,textvariable=self.source_var,state='readonly')
        self.source_entry.grid(row=0,column=1,sticky='ew',padx=8,pady=6)
        self.directory_button = ctk.CTkButton(top,text='Thư mục xuất',width=140,command=self.choose_directory)
        self.directory_button.grid(row=1,column=0,padx=8,pady=6)
        self.directory_entry = ctk.CTkEntry(top,textvariable=self.output_dir_var,placeholder_text='Chọn thư mục xuất')
        self.directory_entry.grid(row=1,column=1,sticky='ew',padx=8,pady=6)
        ctk.CTkLabel(top,text='Tên output MP4').grid(row=2,column=0,padx=8,pady=6)
        self.name_entry = ctk.CTkEntry(top,textvariable=self.output_name_var)
        self.name_entry.grid(row=2,column=1,sticky='ew',padx=8,pady=6)
        body = ctk.CTkFrame(self,fg_color='transparent')
        body.grid(row=1,column=0,sticky='nsew',padx=12,pady=6)
        body.rowconfigure(0,weight=1);body.columnconfigure(0,weight=1)
        left = ctk.CTkFrame(body)
        left.grid(row=0,column=0,sticky='nsew',padx=(0,8));left.columnconfigure(0,weight=1);left.rowconfigure(2,weight=1)
        self.info_label = ctk.CTkLabel(left,text='Ảnh xem trước • không phát realtime',anchor='w')
        self.info_label.grid(row=0,column=0,sticky='ew',padx=10,pady=4)
        self.mode_menu = ctk.CTkOptionMenu(left,values=list(MODES),variable=self.mode_var,command=self.selection_mode_changed)
        self.mode_menu.grid(row=1,column=0,sticky='ew',padx=10,pady=4)
        self.preview_canvas = PreviewCanvas(left,self._selected)
        self.preview_canvas.grid(row=2,column=0,sticky='nsew',padx=10,pady=4)
        self.timeline = ctk.CTkSlider(left,from_=0,to=1,variable=self.time_var,command=lambda value:self.options_changed('time'))
        self.timeline.grid(row=3,column=0,sticky='ew',padx=14,pady=8)
        self.time_label = ctk.CTkLabel(left,text='0.00 s (thời gian đầu ra)')
        self.time_label.grid(row=4,column=0,padx=10)
        self.help_label = ctk.CTkLabel(left,text='Crop: kéo vùng trên ảnh nguồn sau lật.\nBlur/logo/text: chọn trên ảnh sau crop.\nChọn “Xem kết quả” để thấy đầy đủ hiệu ứng.',justify='left',anchor='w')
        self.help_label.grid(row=5,column=0,sticky='ew',padx=10,pady=8)
        self.options = OptionsPanel(body,self.options_changed)
        self.options.grid(row=0,column=1,sticky='ns')
        bottom = ctk.CTkFrame(self)
        bottom.grid(row=2,column=0,sticky='ew',padx=12,pady=(6,12));bottom.columnconfigure(0,weight=1)
        self.progress = ctk.CTkProgressBar(bottom)
        self.progress.grid(row=0,column=0,columnspan=2,sticky='ew',padx=10,pady=(10,4));self.progress.set(0)
        self.status_label = ctk.CTkLabel(bottom,textvariable=self.status_var,anchor='w',justify='left',wraplength=640)
        self.status_label.grid(row=1,column=0,columnspan=2,sticky='ew',padx=10,pady=4)
        actions = ctk.CTkFrame(bottom,fg_color='transparent')
        actions.grid(row=2,column=0,columnspan=2,sticky='ew',padx=10,pady=(4,10));actions.columnconfigure(0,weight=1)
        self.export_button = ctk.CTkButton(actions,text='Xuất video',command=self.start_export,state='disabled')
        self.export_button.grid(row=0,column=1,padx=5)
        self.cancel_button = ctk.CTkButton(actions,text='Hủy xuất',command=self.cancel_export,state='disabled',fg_color='#a13a42')
        self.cancel_button.grid(row=0,column=2,padx=5)

    def choose_video(self):
        path = filedialog.askopenfilename(parent=self,title='Chọn video',filetypes=[('Video','*.mp4 *.mov *.mkv *.avi *.webm'),('Tất cả','*')])
        if path: self.load_video(Path(path))

    def load_video(self,path):
        if self.worker.running or self._closing: return
        self.source_path = Path(path)
        self.source_var.set(str(path))
        self.media_info = None
        self.output_name_var.set(default_output(Path(path),Path('.')).name)
        self.export_button.configure(state='disabled')
        self._invalidate_preview()
        self.preview_canvas.clear()
        self._warning = ''
        self.status_var.set('Đang đọc thông tin video…')
        self._load_generation = self.loader.request(Path(path))

    def choose_directory(self):
        path = filedialog.askdirectory(parent=self,title='Chọn thư mục xuất')
        if path: self.output_dir_var.set(path)

    def _mode(self):
        value = self.mode_var.get()
        return MODES.get(value,value)

    def _invalidate_preview(self):
        self._preview_generation = self.preview.invalidate()
        self._display_mode = None
        self.preview_canvas.enabled = False
        if self._preview_after:
            self.after_cancel(self._preview_after);self._preview_after = None

    def options_changed(self,reason):
        if self._closing or self.worker.running: return
        self._last_terminal = None
        self._invalidate_preview()
        if reason in ('crop','flip'):
            self._warning = 'Crop/lật đã đổi: chọn lại vùng blur và vị trí logo/text trước khi bật lại.'
            self.status_var.set(self._warning)
        if self.media_info is not None:
            self._preview_after = self.after(180,self._request_preview)

    def selection_mode_changed(self,value=None):
        self.options_changed('mode')

    def _request_preview(self):
        self._preview_after = None
        if self.media_info is None or self._closing or self.worker.running: return
        try:
            mode = self._mode()
            selection = None
            if mode == 'crop':
                options = self.options.base_options()
                if self.options.vars['crop_enabled'].get():
                    try:
                        selection = Rect(*(int(self.options.vars['crop_'+field].get()) for field in ('x','y','width','height')))
                        validate_options(replace(options,crop=selection),self.media_info.width,self.media_info.height,self.media_info.duration)
                    except ValueError:
                        selection = None
            else:
                options = self.options.read_options(exclude=mode)
            validate_options(options,self.media_info.width,self.media_info.height,self.media_info.duration)
            end = max(0,trimmed_duration(options,self.media_info.duration) - 1/self.media_info.fps)
            self.timeline.configure(to=max(.001,end))
            time = min(max(0,self.time_var.get()),end)
            self.time_var.set(time)
            self.time_label.configure(text=f'{time:.2f} s (thời gian đầu ra)')
            overlay=None
            if mode in ('logo','watermark','intro'):
                width,height=(options.crop.width,options.crop.height) if options.crop else (self.media_info.width//2*2,self.media_info.height//2*2)
                snapshot=self.options.selection_snapshot(mode,(width,height))
                if snapshot: selection,overlay=snapshot
            if self._preview_context is not None and len(self._preview_context)>3 and self._preview_context[3] is not None:
                self._preview_context[3].close()
            self._preview_context = (mode,options,selection,overlay)
            self._preview_generation = self.preview.request(self.source_path,self.media_info,options,time)
            if not self._warning and self._last_terminal is None: self.status_var.set('Đang cập nhật ảnh xem trước…')
        except (ValueError,OSError) as exc:
            self.status_var.set(str(exc))

    def _selected(self,kind,region):
        if self._display_mode != kind or self.worker.running: return
        self.options.apply_region(kind,region)

    def start_export(self):
        if self.worker.running or self._closing: return
        try:
            if self.source_path is None or self.media_info is None: raise ValueError('Hãy chọn video hợp lệ')
            options = self.options.read_options()
            validate_options(options,self.media_info.width,self.media_info.height,self.media_info.duration)
            directory = self.output_dir_var.get()
            if not directory: raise ValueError('Hãy chọn thư mục xuất')
            name = self.output_name_var.get()
            if not name or Path(name).name != name: raise ValueError('Tên output không chứa đường dẫn')
            destination = Path(directory)/name
            try: reservation = reserve_output(self.source_path,destination,False)
            except FileExistsError:
                if not messagebox.askyesno('Xác nhận ghi đè',f'File đã tồn tại:\n{destination}\n\nThay thế sau khi xuất thành công?',parent=self): return
                reservation = reserve_output(self.source_path,destination,True)
            self._invalidate_preview()
            self._last_terminal = None
            self.worker.start(self.source_path,self.media_info,options,reservation)
            self.progress.set(0)
            self._set_busy(True)
            self.status_var.set('Đang xuất video…')
        except (ValueError,OSError,RuntimeError) as exc:
            self.status_var.set(str(exc))
            messagebox.showerror('Không thể xuất',str(exc),parent=self)

    def cancel_export(self):
        if self.worker.running:
            self.worker.cancel()
            self.status_var.set('Đang hủy và dọn file tạm…')
            self.cancel_button.configure(state='disabled')

    def _set_busy(self,busy):
        state = 'disabled' if busy else 'normal'
        for widget in (self.video_button,self.directory_button,self.directory_entry,self.name_entry,self.mode_menu,self.timeline): widget.configure(state=state)
        self.options.set_enabled(not busy)
        self.preview_canvas.enabled = not busy and self._display_mode is not None
        self.export_button.configure(state='disabled' if busy or self.media_info is None else 'normal')
        self.cancel_button.configure(state='normal' if busy else 'disabled')

    def _handle_worker_event(self,event):
        if event.kind == 'progress':
            self.progress.set(event.progress or 0)
            if not self._closing: self.status_var.set(f'Đang xuất: {(event.progress or 0)*100:.1f}%')
            return
        self._last_terminal = event
        self._set_busy(False)
        if event.kind == 'completed':
            self.progress.set(1);self.status_var.set(f'Đã xuất: {event.output}')
        elif event.kind == 'cancelled': self.status_var.set('Đã hủy xuất; file đích cũ được giữ nguyên')
        else:
            self.status_var.set('Xuất thất bại; xem chi tiết lỗi')
            if not self._closing: messagebox.showerror('Xuất thất bại',event.message,parent=self)

        if not self._closing:
            self._request_preview()

    def _poll(self):
        if self._destroyed: return
        for result in self.loader.poll():
            if result.generation != self._load_generation or self._closing: continue
            if result.error:
                self.status_var.set(result.error)
                messagebox.showerror('Không đọc được video',result.error,parent=self)
            else:
                self.source_path,self.media_info = result.path,result.info
                self.time_var.set(0)
                self.info_label.configure(text=f'{result.info.width} × {result.info.height} • {result.info.duration:.2f} s • {result.info.fps:g} fps')
                self.options.set_media(result.info)
                self.export_button.configure(state='normal')
        for result in self.preview.poll():
            if result.generation == self._preview_generation and not self._closing:
                if result.error: self.status_var.set(result.error)
                else:
                    mode,options,selection,overlay = self._preview_context
                    self._display_mode = mode
                    self.preview_canvas.mode = mode
                    self.preview_canvas.set_image(result.image)
                    self.preview_canvas.enabled = not self.worker.running
                    if selection is not None:
                        if overlay is not None: self.preview_canvas.set_overlay(overlay,selection)
                        else: self.preview_canvas.set_selection(selection)
                    if self._last_terminal is None:
                        self.status_var.set(self._warning or 'Ảnh xem trước đã cập nhật')
            if result.image: result.image.close()
        for event in self.worker.poll(): self._handle_worker_event(event)
        if self._closing and not self.worker.running and not self.preview.busy and not self.loader.busy:
            self._finish_close();return
        self._poll_after = self.after(40,self._poll)

    def request_close(self):
        if self._closing: return
        if self.worker.running and not messagebox.askyesno('Thoát ứng dụng','Hủy tác vụ xuất rồi thoát?',parent=self): return
        self._closing = True
        self._invalidate_preview()
        self.worker.cancel()
        self.preview.close()
        self.loader.close()
        self._set_busy(True)
        self.cancel_button.configure(state='disabled')
        self.status_var.set('Đang dừng tác vụ trước khi thoát…')
        if not self.worker.running and not self.preview.busy and not self.loader.busy: self._finish_close()

    def _finish_close(self):
        if self._destroyed: return
        self._destroyed = True
        if self._poll_after: self.after_cancel(self._poll_after)
        self.preview_canvas.clear()
        if self._preview_context is not None and self._preview_context[3] is not None: self._preview_context[3].close()
        self.destroy()
