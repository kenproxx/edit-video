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
        defaults = dict(speed='1',crop_x='0',crop_y='0',crop_width='0',crop_height='0',blur_x='0',blur_y='0',blur_width='40',blur_height='40',blur_strength='10',logo_path='',logo_x='0',logo_y='0',logo_width='64',logo_opacity='1',intro_duration='1')
        self.vars = {n:tk.StringVar(value=v) for n,v in defaults.items()}
        for n in ('flip_horizontal','flip_vertical','crop_enabled','blur_enabled','logo_enabled'):
            self.vars[n] = tk.BooleanVar(value=False)
        self.controls = []
        self._row = 0
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
        for key in ('x','y','width','opacity'):
            self._entry('logo_'+key,'Logo '+{'width':'rộng (px)','opacity':'độ đậm 0–1'}.get(key,key.upper()))
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
            self.vars['speed'].set('1')
            for name in ('flip_horizontal','flip_vertical','crop_enabled','blur_enabled','logo_enabled'):
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

    def apply_region(self,kind,region):
        with self.batch():
            if kind in ('crop','blur'):
                for field in ('x','y','width','height'): self.vars[f'{kind}_{field}'].set(str(getattr(region,field)))
                self.vars[kind+'_enabled'].set(True)
            elif kind == 'logo':
                self.vars['logo_x'].set(str(region[0]));self.vars['logo_y'].set(str(region[1]));self.vars['logo_enabled'].set(True)
            else:
                panel = self.text_panels[kind]
                panel.vars['x'].set(str(region[0]));panel.vars['y'].set(str(region[1]));panel.vars['enabled'].set(True)
        if kind == 'crop': self._field_changed('crop_enabled')
        else: self._notify('edit')

    def choose_logo(self):
        path = filedialog.askopenfilename(parent=self.winfo_toplevel(),title='Chọn watermark logo',filetypes=[('Ảnh','*.png *.jpg *.jpeg')])
        if path: self.vars['logo_path'].set(path)

    def base_options(self):
        return EditOptions(speed=float(self.vars['speed'].get().replace(',','.')),flip_horizontal=self.vars['flip_horizontal'].get(),flip_vertical=self.vars['flip_vertical'].get())

    def read_options(self, exclude: str | None = None) -> EditOptions:
        try:
            base = self.base_options()
            def rect(prefix):
                if prefix == exclude or not self.vars[prefix+'_enabled'].get(): return None
                return Rect(*(int(self.vars[prefix+'_'+field].get()) for field in ('x','y','width','height')))
            logo = None
            if exclude != 'logo' and self.vars['logo_enabled'].get():
                logo = LogoOverlay(Path(self.vars['logo_path'].get()),int(self.vars['logo_x'].get()),int(self.vars['logo_y'].get()),int(self.vars['logo_width'].get()),float(self.vars['logo_opacity'].get().replace(',','.')))
            from dataclasses import replace
            intro = None if exclude == 'intro' else self.text_panels['intro'].read()
            return replace(base,crop=rect('crop'),blur=rect('blur'),blur_strength=int(self.vars['blur_strength'].get()) if exclude != 'blur' and self.vars['blur_enabled'].get() else 10,logo=logo,watermark=None if exclude == 'watermark' else self.text_panels['watermark'].read(),intro=intro,intro_duration=float(self.vars['intro_duration'].get().replace(',','.')) if intro else 1)
        except ValueError as exc:
            raise ValueError('Kiểm tra các ô số: X/Y/kích thước là số nguyên; tốc độ/thời gian/độ đậm là số thực') from exc

    def set_enabled(self,enabled):
        for widget in self.controls: widget.configure(state='normal' if enabled else 'disabled')
