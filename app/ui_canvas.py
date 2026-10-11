"""Letterboxed image canvas and selection feedback, in display-pixel coordinates."""
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
from .geometry import canvas_to_pixel
from .models import Rect


class PreviewCanvas(ctk.CTkFrame):
    def __init__(self,master,selected):
        super().__init__(master)
        self.rowconfigure(0,weight=1);self.columnconfigure(0,weight=1)
        self.canvas = tk.Canvas(self,bg='#151a23',highlightthickness=0,width=320,height=240)
        self.canvas.grid(row=0,column=0,sticky='nsew')
        self.selected = selected
        self.mode = 'preview'
        self.image_size = None
        self.image_box = Rect(0,0,0,0)
        self._image = None
        self._photo = None
        self._start = None
        self.enabled = True
        self._selection = None
        self.canvas.bind('<Configure>',lambda event:self._redraw())
        self.canvas.bind('<ButtonPress-1>',self.press)
        self.canvas.bind('<B1-Motion>',self.drag)
        self.canvas.bind('<ButtonRelease-1>',self.release)

    def clear(self):
        if self._image: self._image.close()
        self._image = self._photo = self.image_size = None
        self._selection = self._start = None
        self.canvas.delete('all')

    def set_image(self,image):
        self.clear()
        self._image = image.copy()
        self.image_size = self._image.size
        self._redraw()

    def set_selection(self,selection):
        self._selection = selection
        self._draw_selection()

    def _redraw(self):
        if self._image is None: return
        width,height = max(1,self.canvas.winfo_width()),max(1,self.canvas.winfo_height())
        iw,ih = self._image.size
        scale = min(width/iw,height/ih)
        w,h = max(1,int(iw*scale)),max(1,int(ih*scale))
        self.image_box = Rect((width-w)//2,(height-h)//2,w,h)
        resized = self._image.resize((w,h),Image.Resampling.LANCZOS)
        self._photo = ImageTk.PhotoImage(resized,master=self.canvas)
        resized.close()
        self.canvas.delete('all')
        self.canvas.create_image(self.image_box.x,self.image_box.y,image=self._photo,anchor='nw')
        self._draw_selection()

    def _point(self,event):
        if self.image_size is None: return None
        return canvas_to_pixel(event.x,event.y,self.image_box,self.image_size)

    def press(self,event):
        if not self.enabled or self.mode=='preview': return
        self._start = self._point(event)

    def drag(self,event):
        if self._start is None or not self.enabled: return
        end = self._point(event)
        if end is None: return
        if self.mode in ('crop','blur'):
            self.set_selection(self._rectangle(self._start,end))
        else: self.set_selection(end)

    def _rectangle(self,start,end):
        x,y = min(start[0],end[0]),min(start[1],end[1])
        w,h = abs(end[0]-start[0]),abs(end[1]-start[1])
        if self.mode == 'crop': x,y,w,h = (v//2*2 for v in (x,y,w,h))
        return Rect(x,y,w,h)

    def release(self,event):
        if not self.enabled or self._start is None: return
        start,self._start = self._start,None
        end = self._point(event)
        if end is None: return
        if self.mode in ('crop','blur'):
            region = self._rectangle(start,end)
            minimum = 2 if self.mode == 'crop' else 1
            if min(region.width,region.height)<minimum: return
        else: region = end
        self.set_selection(region)
        self.selected(self.mode,region)

    def _draw_selection(self):
        self.canvas.delete('selection')
        if self._selection is None or self.image_size is None: return
        box = self.image_box
        sx,sy = box.width/self.image_size[0],box.height/self.image_size[1]
        region = self._selection
        if isinstance(region,Rect):
            self.canvas.create_rectangle(box.x+region.x*sx,box.y+region.y*sy,box.x+(region.x+region.width)*sx,box.y+(region.y+region.height)*sy,outline='#f9c74f',width=2,tags='selection')
        else:
            x,y = box.x+region[0]*sx,box.y+region[1]*sy
            self.canvas.create_line(x-8,y,x+8,y,fill='#f9c74f',width=2,tags='selection')
            self.canvas.create_line(x,y-8,x,y+8,fill='#f9c74f',width=2,tags='selection')
