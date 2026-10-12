"""Letterboxed image canvas and selection feedback, in display-pixel coordinates."""
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
from .geometry import canvas_to_pixel,move_region,resize_region
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
        self._operation = self._original = None
        self._overlay = self._overlay_photo = None
        self.canvas.bind('<Configure>',lambda event:self._redraw())
        self.canvas.bind('<ButtonPress-1>',self.press)
        self.canvas.bind('<B1-Motion>',self.drag)
        self.canvas.bind('<ButtonRelease-1>',self.release)

    def clear(self):
        if self._image: self._image.close()
        if self._overlay: self._overlay.close()
        self._overlay = self._overlay_photo = None
        self._image = self._photo = self.image_size = None
        self._selection = self._start = None
        self.canvas.delete('all')

    def set_image(self,image):
        self.clear()
        self._image = image.copy()
        self.image_size = self._image.size
        self._redraw()

    def set_overlay(self,image,region):
        if self._overlay: self._overlay.close()
        self._overlay = image.copy() if image is not None else None
        self.set_selection(region)

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

    def _point(self,event,clamp=False):
        if self.image_size is None: return None
        point=canvas_to_pixel(event.x,event.y,self.image_box,self.image_size)
        if point is None and clamp and self.image_box.width and self.image_box.height:
            box=self.image_box;w,h=self.image_size
            point=(max(0,min(w,int((event.x-box.x)*w/box.width))),max(0,min(h,int((event.y-box.y)*h/box.height))))
        return point

    def _handles(self,region):
        l,t=region.x,region.y;r,b=l+region.width,t+region.height
        return dict(nw=(l,t),n=((l+r)/2,t),ne=(r,t),e=(r,(t+b)/2),se=(r,b),s=((l+r)/2,b),sw=(l,b),w=(l,(t+b)/2))

    def _handle_at(self,event):
        if not isinstance(self._selection,Rect) or self.image_size is None: return None
        box=self.image_box;sx,sy=box.width/self.image_size[0],box.height/self.image_size[1]
        for handle,(x,y) in self._handles(self._selection).items():
            if abs(event.x-(box.x+x*sx))<=7 and abs(event.y-(box.y+y*sy))<=7: return handle
        return None

    def press(self,event):
        if not self.enabled or self.mode=='preview': return
        handle=self._handle_at(event)
        self._start=self._point(event,clamp=handle is not None)
        self._original=self._selection
        self._operation=handle or 'draw'
        if self._start is not None and not handle and isinstance(self._selection,Rect):
            x,y=self._start;r=self._selection
            if r.x<=x<=r.x+r.width and r.y<=y<=r.y+r.height: self._operation='move'
            elif self.mode in ('logo','watermark','intro'): self._operation='place'

    def _drag_region(self,end):
        start=self._start
        if self._operation=='move':
            return move_region(self._original,end[0]-start[0],end[1]-start[1],self.image_size,self.mode=='crop')
        if self._operation not in ('draw','place'):
            return resize_region(self._original,self._operation,end[0]-start[0],end[1]-start[1],self.image_size,self.mode=='crop')
        if self._operation=='place':
            r=self._original
            return Rect(min(end[0],self.image_size[0]-r.width),min(end[1],self.image_size[1]-r.height),r.width,r.height)
        if self.mode in ('crop','blur'): return self._rectangle(start,end)
        return end

    def drag(self,event):
        if self._start is None or not self.enabled: return
        end=self._point(event,clamp=True)
        if end is not None: self.set_selection(self._drag_region(end))

    def _rectangle(self,start,end):
        x,y=min(start[0],end[0]),min(start[1],end[1])
        w,h=abs(end[0]-start[0]),abs(end[1]-start[1])
        if self.mode=='crop': x,y,w,h=(v//2*2 for v in (x,y,w,h))
        return Rect(x,y,w,h)

    def release(self,event):
        if not self.enabled or self._start is None: return
        end=self._point(event,clamp=True)
        if end is None: self._start=None;return
        region=self._drag_region(end)
        self._start=None
        if isinstance(region,Rect) and min(region.width,region.height)<(2 if self.mode=='crop' else 1): return
        self.set_selection(region)
        self.selected(self.mode,region)

    def _draw_selection(self):
        self.canvas.delete('selection')
        self.canvas.delete('overlay')
        if self._selection is None or self.image_size is None: return
        box = self.image_box
        sx,sy = box.width/self.image_size[0],box.height/self.image_size[1]
        region = self._selection
        if isinstance(region,Rect):
            if self._overlay is not None:
                size=(max(1,int(region.width*sx)),max(1,int(region.height*sy)))
                resized=self._overlay.resize(size,Image.Resampling.LANCZOS)
                self._overlay_photo=ImageTk.PhotoImage(resized,master=self.canvas);resized.close()
                self.canvas.create_image(box.x+region.x*sx,box.y+region.y*sy,image=self._overlay_photo,anchor='nw',tags='overlay')
            self.canvas.create_rectangle(box.x+region.x*sx,box.y+region.y*sy,box.x+(region.x+region.width)*sx,box.y+(region.y+region.height)*sy,outline='#f9c74f',width=2,tags='selection')
            for x,y in self._handles(region).values():
                cx,cy=box.x+x*sx,box.y+y*sy
                self.canvas.create_rectangle(cx-4,cy-4,cx+4,cy+4,fill='#f9c74f',outline='#151a23',tags='selection')
        else:
            x,y = box.x+region[0]*sx,box.y+region[1]*sy
            self.canvas.create_line(x-8,y,x+8,y,fill='#f9c74f',width=2,tags='selection')
            self.canvas.create_line(x,y-8,x,y+8,fill='#f9c74f',width=2,tags='selection')
