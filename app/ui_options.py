"""Vietnamese edit controls; all widget access remains on the Tk thread."""
from contextlib import contextmanager
import os
from pathlib import Path
import tkinter as tk
from tkinter import colorchooser, filedialog
import customtkinter as ctk
from .geometry import preset_crop
from .models import EditOptions, Rect, TextOverlay, LogoOverlay


def default_font() -> str:
    candidates = [Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'arial.ttf', Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    return str(next((p for p in candidates if p.is_file()), ''))


class TextPanel(ctk.CTkFrame):
    def __init__(self, master, title, changed):
        super().__init__(master)
        self.columnconfigure(1, weight=1)
        self.changed = changed
        self.vars = {name: tk.StringVar(value=value) for name, value in dict(text='',font=default_font(),size='32',color='#ffffff',stroke_color='#000000',stroke_width='2',x='0',y='0',opacity='1').items()}
        self.vars['enabled'] = tk.BooleanVar(value=False)
        self.controls = []
        enabled = ctk.CTkCheckBox(self, text=title, variable=self.vars['enabled'])
        enabled.grid(row=0,column=0,columnspan=2,sticky='w',padx=8,pady=8)
        self.controls.append(enabled)
        self.textbox = ctk.CTkTextbox(self, height=66)
        self.textbox.grid(row=1,column=0,columnspan=2,sticky='ew',padx=8,pady=4)
        self.controls.append(self.textbox)
        self._syncing = False
        self.textbox.bind('<<Modified>>', self._text_modified)
        for row, (name, label) in enumerate([('size','Cỡ chữ (px)'),('x','X'),('y','Y'),('opacity','Độ đậm 0–1'),('stroke_width','Viền (px)')], 2):
            ctk.CTkLabel(self,text=label).grid(row=row,column=0,sticky='w',padx=8)
            widget = ctk.CTkEntry(self,textvariable=self.vars[name])
            widget.grid(row=row,column=1,sticky='ew',padx=8,pady=3)
            self.controls.append(widget)
        font = ctk.CTkEntry(self,textvariable=self.vars['font'])
        font.grid(row=7,column=0,columnspan=2,sticky='ew',padx=8,pady=4)
        self.controls.append(font)
        button = ctk.CTkButton(self,text='Chọn font TTF/OTF',command=self.choose_font)
        button.grid(row=8,column=0,columnspan=2,sticky='ew',padx=8,pady=4)
        self.controls.append(button)
        for row, (name,label) in enumerate([('color','Màu chữ'),('stroke_color','Màu viền')],9):
            line = ctk.CTkFrame(self,fg_color='transparent')
            line.grid(row=row,column=0,columnspan=2,sticky='ew',padx=8,pady=3)
            line.columnconfigure(0,weight=1)
            entry = ctk.CTkEntry(line,textvariable=self.vars[name])
            entry.grid(row=0,column=0,sticky='ew')
            picker = ctk.CTkButton(line,text=label,width=100,command=lambda n=name:self.choose_color(n))
            picker.grid(row=0,column=1,padx=(4,0))
            self.controls.extend((entry,picker))
        for name, variable in self.vars.items():
            variable.trace_add('write', lambda *args,n=name:self._changed(n))

    def _text_modified(self, event=None):
        if self._syncing or not self.textbox.edit_modified():
            return
        self._syncing = True
        try:
            self.vars['text'].set(self.textbox.get('1.0','end-1c'))
            self.textbox.edit_modified(False)
        finally:
            self._syncing = False

    def _changed(self,name):
        if name == 'text' and not self._syncing:
            self._syncing = True
            try:
                self.textbox.delete('1.0','end')
                self.textbox.insert('1.0',self.vars['text'].get())
                self.textbox.edit_modified(False)
            finally: self._syncing = False
        self.changed('edit')

    def choose_font(self):
        path = filedialog.askopenfilename(parent=self.winfo_toplevel(),title='Chọn font hỗ trợ tiếng Việt',filetypes=[('Font','*.ttf *.otf')])
        if path: self.vars['font'].set(path)

    def choose_color(self,name):
        color = colorchooser.askcolor(parent=self.winfo_toplevel(),title='Chọn màu')[1]
        if color: self.vars[name].set(color)

    def read(self) -> TextOverlay | None:
        if not self.vars['enabled'].get() or not self.vars['text'].get().strip():
            return None
        return TextOverlay(self.vars['text'].get(),Path(self.vars['font'].get()),int(self.vars['size'].get()),self.vars['color'].get(),self.vars['stroke_color'].get(),int(self.vars['stroke_width'].get()),int(self.vars['x'].get()),int(self.vars['y'].get()),float(self.vars['opacity'].get().replace(',','.')))


class OptionsPanel(ctk.CTkScrollableFrame):
    def __init__(self, master, changed):
        super().__init__(master,label_text='Tùy chọn chỉnh sửa',width=330)
        self.columnconfigure(0,weight=1)
        self.changed = changed
        self._suspend = 0
        self.info = None
        defaults = dict(speed='1',crop_x='0',crop_y='0',crop_width='0',crop_height='0',blur_x='0',blur_y='0',blur_width='40',blur_height='40',blur_strength='10',logo_path='',logo_x='0',logo_y='0',logo_width='64',logo_height='',logo_opacity='1',trim_start='00:00',trim_end='00:00',intro_duration='1')
        self.vars = {n:tk.StringVar(value=v) for n,v in defaults.items()}
        for n in ('flip_horizontal','flip_vertical','crop_enabled','blur_enabled','logo_enabled','trim_enabled'):
            self.vars[n] = tk.BooleanVar(value=False)
        self.controls = []
        self._row = 0
        self._check('trim_enabled','Cắt đoạn video nguồn')
        self._entry('trim_start','Từ (phút:giây)')
        self._entry('trim_end','Tới (phút:giây)')
        self._entry('speed','Tốc độ (0.25–4)')
        self._check('flip_horizontal','Lật ngang')
        self._check('flip_vertical','Lật dọc')
        self._check('crop_enabled','Bật crop')
        line = ctk.CTkFrame(self,fg_color='transparent')
        line.grid(row=self._row,column=0,sticky='ew',padx=3,pady=4);self._row+=1
        for i,ratio in enumerate(('9:16','16:9','1:1')):
            button = ctk.CTkButton(line,text=ratio,width=85,command=lambda r=ratio:self.set_preset(r))
            button.grid(row=0,column=i,padx=3)
            self.controls.append(button)
        for key in ('x','y','width','height'):
            self._entry('crop_'+key,'Crop '+{'width':'rộng','height':'cao'}.get(key,key.upper()))
        self._check('blur_enabled','Bật làm mờ vùng cố định')
        for key in ('x','y','width','height','strength'):
            self._entry('blur_'+key,'Blur '+{'width':'rộng','height':'cao','strength':'mức 1–100'}.get(key,key.upper()))
        self._check('logo_enabled','Bật watermark logo')
        self._entry('logo_path','File logo PNG/JPEG')
        button = ctk.CTkButton(self,text='Chọn logo',command=self.choose_logo)
        button.grid(row=self._row,column=0,sticky='ew',pady=4,padx=3);self._row+=1
        self.controls.append(button)
        for key in ('x','y','width','height','opacity'):
            self._entry('logo_'+key,'Logo '+{'width':'rộng (px)','height':'cao (để trống: giữ tỷ lệ)','opacity':'độ đậm 0–1'}.get(key,key.upper()))
        self.text_panels = {}
        for key,title in [('watermark','Bật watermark chữ toàn video'),('intro','Bật chữ đầu video')]:
            panel = TextPanel(self,title,self._notify)
            panel.grid(row=self._row,column=0,sticky='ew',pady=8);self._row+=1
            self.text_panels[key] = panel
            self.controls.extend(panel.controls)
        self._entry('intro_duration','Text đầu: số giây đầu ra')
        for name, variable in self.vars.items():
            variable.trace_add('write',lambda *args,n=name:self._field_changed(n))

    def _entry(self,name,label):
        line = ctk.CTkFrame(self,fg_color='transparent')
        line.grid(row=self._row,column=0,sticky='ew',padx=3,pady=2);self._row+=1
        line.columnconfigure(1,weight=1)
        ctk.CTkLabel(line,text=label,width=120,anchor='w').grid(row=0,column=0,sticky='w')
        widget = ctk.CTkEntry(line,textvariable=self.vars[name],width=120)
        widget.grid(row=0,column=1,sticky='ew',padx=(5,0))
        self.controls.append(widget)

    def _check(self,name,label):
        widget = ctk.CTkCheckBox(self,text=label,variable=self.vars[name])
        widget.grid(row=self._row,column=0,sticky='w',padx=3,pady=8);self._row+=1
        self.controls.append(widget)

    @contextmanager
    def batch(self):
        self._suspend += 1
        try: yield
        finally: self._suspend -= 1

    def _notify(self,reason):
        if not self._suspend: self.changed(reason)

    def _field_changed(self,name):
        if self._suspend: return
        reason = 'flip' if name.startswith('flip_') else 'crop' if name.startswith('crop_') else 'edit'
        if reason in ('flip','crop'):
            with self.batch():
                if reason == 'flip': self.vars['crop_enabled'].set(False)
                self.vars['blur_enabled'].set(False)
                self.vars['logo_enabled'].set(False)
                for panel in self.text_panels.values(): panel.vars['enabled'].set(False)
        self._notify(reason)

    def set_media(self,info):
        self.info = info
        with self.batch():
            from .timing import format_time
            self.vars['trim_start'].set('00:00');self.vars['trim_end'].set(format_time(info.duration))
            self.vars['logo_height'].set('')
            self.vars['speed'].set('1')
            for name in ('flip_horizontal','flip_vertical','crop_enabled','blur_enabled','logo_enabled','trim_enabled'):
                self.vars[name].set(False)
            for prefix in ('crop','blur','logo'):
                self.vars[prefix+'_x'].set('0');self.vars[prefix+'_y'].set('0')
            self.vars['crop_width'].set(str(info.width//2*2));self.vars['crop_height'].set(str(info.height//2*2))
            self.vars['blur_width'].set(str(min(40,info.width//2*2)));self.vars['blur_height'].set(str(min(40,info.height//2*2)))
            self.vars['logo_width'].set(str(min(64,info.width//2*2)))
            self.vars['intro_duration'].set(str(min(1,info.duration)))
            for panel in self.text_panels.values():
                panel.vars['enabled'].set(False);panel.vars['x'].set('0');panel.vars['y'].set('0')
        self._notify('media')

    def set_preset(self,ratio):
        if self.info is None: return
        self.apply_region('crop',preset_crop(self.info.width,self.info.height,tuple(map(int,ratio.split(':')))))

    def fit_text_region(self,kind,region,bounds,handle='',original=None,fit_only=False):
        """Use the actual font raster, preserving the opposite resize edge."""
        from dataclasses import replace
        from PIL import ImageFont
        from .overlays import text_bounds
        overlay=self.text_panels[kind].read()
        if overlay is None: return region,1
        def size_at(size):
            return text_bounds(replace(overlay,size=size),ImageFont.truetype(str(overlay.font),size))[1]
        w,h=size_at(overlay.size)
        ratio=region.width/w if abs(region.width-w)>=abs(region.height-h) else region.height/h
        desired=max(1,round(overlay.size*ratio))
        anchor=original or region
        def geometry(size):
            width,height=size_at(size)
            x=anchor.x+anchor.width-width if 'w' in handle else region.x
            y=anchor.y+anchor.height-height if 'n' in handle else region.y
            return Rect(x,y,width,height)
        low,high,best=1,(max(bounds)*2 if fit_only else desired),1
        while low<=high:
            middle=(low+high)//2;r=geometry(middle)
            fits=0<=r.x and 0<=r.y and r.x+r.width<=bounds[0] and r.y+r.height<=bounds[1]
            if fit_only: fits=fits and r.width<=region.width and r.height<=region.height
            if fits: best=middle;low=middle+1
            else: high=middle-1
        return geometry(best),best

    def adjust_canvas_region(self,kind,region,bounds,handle,original):
        if kind not in self.text_panels or not isinstance(region,Rect): return region
        return self.fit_text_region(kind,region,bounds,handle,original)[0]

    def apply_region(self,kind,region):
        with self.batch():
            if kind in ('crop','blur'):
                for field in ('x','y','width','height'): self.vars[f'{kind}_{field}'].set(str(getattr(region,field)))
                self.vars[kind+'_enabled'].set(True)
            elif kind == 'logo':
                if isinstance(region,Rect):
                    for field in ('x','y','width','height'): self.vars['logo_'+field].set(str(getattr(region,field)))
                else:
                    self.vars['logo_x'].set(str(region[0]));self.vars['logo_y'].set(str(region[1]))
                self.vars['logo_enabled'].set(True)
            else:
                panel = self.text_panels[kind]
                if isinstance(region,Rect):
                    bounds=(self.info.width,self.info.height)
                    crop=self.read_options().crop
                    if crop is not None: bounds=(crop.width,crop.height)
                    region,size=self.fit_text_region(kind,region,bounds,fit_only=True)
                    panel.vars['size'].set(str(size))
                    panel.vars['x'].set(str(region.x));panel.vars['y'].set(str(region.y))
                else:
                    panel.vars['x'].set(str(region[0]));panel.vars['y'].set(str(region[1]))
                panel.vars['enabled'].set(True)
        if kind == 'crop': self._field_changed('crop_enabled')
        else: self._notify('edit')

    def choose_logo(self):
        path = filedialog.askopenfilename(parent=self.winfo_toplevel(),title='Chọn watermark logo',filetypes=[('Ảnh','*.png *.jpg *.jpeg')])
        if path: self.vars['logo_path'].set(path)

    def base_options(self):
        from .timing import parse_time
        enabled=self.vars['trim_enabled'].get()
        return EditOptions(speed=float(self.vars['speed'].get().replace(',','.')),flip_horizontal=self.vars['flip_horizontal'].get(),flip_vertical=self.vars['flip_vertical'].get(),trim_start=parse_time(self.vars['trim_start'].get()) if enabled else 0,trim_end=parse_time(self.vars['trim_end'].get()) if enabled else None)

    def read_options(self, exclude: str | None = None) -> EditOptions:
        try:
            base = self.base_options()
            def rect(prefix):
                if prefix == exclude or not self.vars[prefix+'_enabled'].get(): return None
                return Rect(*(int(self.vars[prefix+'_'+field].get()) for field in ('x','y','width','height')))
            logo = None
            if exclude != 'logo' and self.vars['logo_enabled'].get():
                logo = LogoOverlay(Path(self.vars['logo_path'].get()),int(self.vars['logo_x'].get()),int(self.vars['logo_y'].get()),int(self.vars['logo_width'].get()),float(self.vars['logo_opacity'].get().replace(',','.')),int(self.vars['logo_height'].get()) if self.vars['logo_height'].get().strip() else None)
            from dataclasses import replace
            intro = None if exclude == 'intro' else self.text_panels['intro'].read()
            return replace(base,crop=rect('crop'),blur=rect('blur'),blur_strength=int(self.vars['blur_strength'].get()) if exclude != 'blur' and self.vars['blur_enabled'].get() else 10,logo=logo,watermark=None if exclude == 'watermark' else self.text_panels['watermark'].read(),intro=intro,intro_duration=float(self.vars['intro_duration'].get().replace(',','.')) if intro else 1)
        except ValueError as exc:
            raise ValueError('Kiểm tra các ô số: X/Y/kích thước là số nguyên; tốc độ/thời gian/độ đậm là số thực') from exc

    def selection_snapshot(self,kind,bounds):
        from PIL import Image,ImageFont
        from .overlays import text_bounds,write_text
        from .resources import user_data_dir
        import tempfile
        width,height=bounds
        def number(value,default):
            try: return int(value)
            except ValueError: return default
        if kind=='logo':
            if not self.vars['logo_enabled'].get(): return None
            try:
                with Image.open(self.vars['logo_path'].get()) as source: image=source.convert('RGBA')
            except (OSError,ValueError): return None
            w=max(1,min(width,number(self.vars['logo_width'].get(),64)))
            h=max(1,min(height,number(self.vars['logo_height'].get(),round(image.height*w/image.width))))
            x=max(0,min(width-w,number(self.vars['logo_x'].get(),0)))
            y=max(0,min(height-h,number(self.vars['logo_y'].get(),0)))
            try: opacity=max(0,min(1,float(self.vars['logo_opacity'].get().replace(',','.'))))
            except ValueError: opacity=1
            image.putalpha(image.getchannel('A').point(lambda value:round(value*opacity)))
            return Rect(x,y,w,h),image
        if kind in self.text_panels:
            try:
                overlay=self.text_panels[kind].read()
                if overlay is None: return None
                w,h=text_bounds(overlay,ImageFont.truetype(str(overlay.font),overlay.size))[1]
                with tempfile.TemporaryDirectory(prefix='canvas-text-',dir=user_data_dir()) as directory:
                    target=Path(directory)/'text.png';write_text(overlay,target)
                    with Image.open(target) as source: image=source.convert('RGBA')
                return Rect(overlay.x,overlay.y,w,h),image
            except (OSError,ValueError): return None
        return None

    def set_enabled(self,enabled):
        for widget in self.controls: widget.configure(state='normal' if enabled else 'disabled')
