import threading
import time
from pathlib import Path
from types import SimpleNamespace
import pytest
from PIL import Image
from app.ui import VideoEditorApp
from app.models import Rect
from app.media import probe


def spin(app,predicate,timeout=15):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        app.update()
        if predicate(): return
        time.sleep(.01)
    pytest.fail('GUI operation timed out: '+app.status_var.get())


@pytest.fixture
def editor(monkeypatch):
    messages=[]
    import app.ui as ui
    monkeypatch.setattr(ui.messagebox,'showerror',lambda title,text,**kwargs:messages.append(('error',text)))
    monkeypatch.setattr(ui.messagebox,'showinfo',lambda title,text,**kwargs:messages.append(('info',text)))
    monkeypatch.setattr(ui.messagebox,'askyesno',lambda *args,**kwargs:True)
    app=VideoEditorApp()
    app._test_messages=messages
    app.update()
    yield app
    if not app._destroyed:
        app.request_close()
        end=time.monotonic()+15
        while not app._destroyed and time.monotonic()<end:
            app.update(); time.sleep(.01)


def load(app,path):
    app.load_video(path)
    spin(app,lambda:app.media_info is not None and app.preview_canvas.image_size is not None)


def test_choose_video_folder_default_name_and_preview(editor,clips,tmp_path,monkeypatch):
    import app.ui as ui
    monkeypatch.setattr(ui.filedialog,'askopenfilename',lambda **kwargs:str(clips['source']))
    editor.choose_video()
    spin(editor,lambda:editor.media_info is not None and editor.preview_canvas.image_size is not None)
    assert editor.source_path==clips['source']
    assert editor.output_name_var.get()==clips['source'].stem+'.mp4'
    monkeypatch.setattr(ui.filedialog,'askdirectory',lambda **kwargs:str(tmp_path))
    editor.choose_directory()
    assert editor.output_dir_var.get()==str(tmp_path)
    assert editor.preview_canvas.image_size==(320,240)


def test_every_control_reaches_options(editor,clips,tmp_path,font,monkeypatch):
    load(editor,clips['source'])
    panel=editor.options
    panel.apply_region('crop',Rect(0,0,300,220))
    panel.apply_region('blur',Rect(40,40,40,40))
    panel.vars['speed'].set('0.5')
    logo=tmp_path/'logo.png'; Image.new('RGBA',(20,20),'white').save(logo)
    import app.ui_options as controls
    monkeypatch.setattr(controls.filedialog,'askopenfilename',lambda **kw:str(logo))
    panel.choose_logo()
    panel.vars['logo_enabled'].set(True)
    panel.vars['logo_x'].set('240');panel.vars['logo_y'].set('170')
    for key in ('intro','watermark'):
        text=panel.text_panels[key]
        text.vars['enabled'].set(True)
        text.vars['text'].set('Tiếng Việt')
        text.vars['size'].set('16')
        monkeypatch.setattr(controls.filedialog,'askopenfilename',lambda **kw:str(font))
        text.choose_font()
        text.vars['y'].set('120' if key=='intro' else '10')
    options=panel.read_options()
    assert options.crop==Rect(0,0,300,220) and options.blur==Rect(40,40,40,40)
    assert options.speed==.5 and options.logo.path==logo
    assert options.intro.text=='Tiếng Việt' and options.intro_duration==1
    assert options.watermark.font==font
    panel.vars['flip_horizontal'].set(True)
    assert panel.read_options().flip_horizontal
    assert not panel.vars['crop_enabled'].get() and not panel.vars['blur_enabled'].get()
    assert not panel.text_panels['intro'].vars['enabled'].get()
    assert 'chọn lại' in editor.status_var.get().lower()


def test_crop_presets_and_geometry_change_reset(editor,clips):
    load(editor,clips['source'])
    panel=editor.options
    panel.set_preset('1:1')
    assert panel.read_options().crop==Rect(40,0,240,240)
    panel.apply_region('blur',Rect(0,0,40,40))
    panel.vars['crop_width'].set('200')
    assert not panel.vars['blur_enabled'].get()


def test_canvas_letterbox_drag_and_overlay_point(editor,clips):
    load(editor,clips['source'])
    canvas=editor.preview_canvas
    editor.mode_var.set('crop');editor.selection_mode_changed()
    spin(editor,lambda:editor._display_mode=='crop' and canvas.image_size==(320,240))
    editor.update()
    box=canvas.image_box
    canvas.press(SimpleNamespace(x=box.x+box.width//4,y=box.y+box.height//4))
    canvas.release(SimpleNamespace(x=box.x+box.width*3//4,y=box.y+box.height*3//4))
    crop=editor.options.read_options().crop
    assert crop and abs(crop.width-160)<=2 and abs(crop.height-120)<=2
    editor.mode_var.set('blur');editor.selection_mode_changed()
    spin(editor,lambda:editor._display_mode=='blur' and canvas.image_size==(crop.width,crop.height))
    editor.update();box=canvas.image_box
    canvas.press(SimpleNamespace(x=0,y=0));canvas.release(SimpleNamespace(x=0,y=0))
    assert not editor.options.vars['blur_enabled'].get()
    canvas.press(SimpleNamespace(x=box.x+10,y=box.y+10));canvas.release(SimpleNamespace(x=box.x+30,y=box.y+30))
    assert editor.options.read_options().blur is not None


def test_invalid_options_do_not_start_export(editor,clips,tmp_path):
    load(editor,clips['source'])
    editor.output_dir_var.set(str(tmp_path));editor.output_name_var.set('out.mp4')
    editor.options.vars['speed'].set('not-number')
    editor.start_export()
    assert not editor.worker.running and editor._test_messages[-1][0]=='error'
    editor.options.vars['speed'].set('1')
    editor.output_dir_var.set(str(clips['silent'].parent));editor.output_name_var.set(clips['source'].name)
    before=clips['source'].read_bytes()
    editor.start_export()
    assert not editor.worker.running and clips['source'].read_bytes()==before


def test_export_overwrite_and_progress_main_thread(editor,clips,tmp_path,monkeypatch):
    load(editor,clips['source'])
    target=tmp_path/'out.mp4';target.write_bytes(b'old')
    editor.output_dir_var.set(str(tmp_path));editor.output_name_var.set('out.mp4')
    import app.ui as ui
    confirmations=[]
    monkeypatch.setattr(ui.messagebox,'askyesno',lambda *a,**k:confirmations.append(a) or False)
    editor.start_export()
    assert confirmations and not editor.worker.running and target.read_bytes()==b'old'
    monkeypatch.setattr(ui.messagebox,'askyesno',lambda *a,**k:True)
    main_thread=threading.get_ident();updates=[]
    original=editor._handle_worker_event
    def capture(event):
        updates.append(threading.get_ident());return original(event)
    monkeypatch.setattr(editor,'_handle_worker_event',capture)
    editor.start_export()
    assert editor.export_button.cget('state')=='disabled'
    spin(editor,lambda:editor._last_terminal is not None)
    assert editor._last_terminal.kind=='completed'
    assert probe(target).duration==pytest.approx(4,abs=.07)
    assert updates and set(updates)=={main_thread}
    assert editor.progress.get()==1


def test_cancel_and_close_waits_for_export(editor,clips,tmp_path):
    import subprocess
    source=tmp_path/'long.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-stream_loop','-1','-i',str(clips['source']),'-t','120','-c','copy',str(source)],check=True)
    load(editor,source)
    editor.output_dir_var.set(str(tmp_path));editor.output_name_var.set('out.mp4')
    editor.options.vars['speed'].set('.25')
    editor.start_export()
    spin(editor,lambda:editor.worker._process is not None)
    process=editor.worker._process
    editor.cancel_export()
    spin(editor,lambda:editor._last_terminal is not None)
    assert editor._last_terminal.kind=='cancelled' and process.poll() is not None
    assert not (tmp_path/'out.mp4').exists()
    editor.start_export()
    spin(editor,lambda:editor.worker._process is not None)
    process=editor.worker._process
    editor.request_close()
    spin(editor,lambda:editor._destroyed)
    assert process.poll() is not None


def test_narrow_window_keeps_bottom_controls(editor):
    editor.geometry('720x600');editor.update()
    assert editor.export_button.winfo_ismapped() and editor.cancel_button.winfo_ismapped()
    assert editor.export_button.winfo_rooty()+editor.export_button.winfo_height()<=editor.winfo_rooty()+editor.winfo_height()
    assert editor.options.winfo_height()>0


def test_text_picker_color_and_canvas_position(editor,clips,font,monkeypatch):
    load(editor,clips['source'])
    panel=editor.options.text_panels['intro']
    import app.ui_options as controls
    monkeypatch.setattr(controls.colorchooser,'askcolor',lambda **kwargs:((255,0,0),'#ff0000'))
    panel.choose_color('color')
    assert panel.vars['color'].get()=='#ff0000'
    panel.vars['text'].set('Đầu');panel.vars['size'].set('16')
    panel.vars['font'].set(str(font))
    editor.mode_var.set('intro');editor.selection_mode_changed()
    spin(editor,lambda:editor._display_mode=='intro')
    canvas=editor.preview_canvas;box=canvas.image_box
    canvas.press(SimpleNamespace(x=box.x+box.width//4,y=box.y+box.height//4))
    canvas.release(SimpleNamespace(x=box.x+box.width//4,y=box.y+box.height//4))
    options=editor.options.read_options()
    assert options.intro is not None
    assert abs(options.intro.x-80)<=1 and abs(options.intro.y-60)<=1
    editor.mode_var.set('preview');editor.selection_mode_changed()
    spin(editor,lambda:editor._display_mode=='preview')


def test_bad_video_recovers_and_close_can_be_declined(editor,clips,tmp_path,monkeypatch):
    import app.ui as ui
    bad=tmp_path/'bad.mp4';bad.write_bytes(b'not media')
    editor.load_video(bad)
    spin(editor,lambda:bool(editor._test_messages))
    assert editor.media_info is None and editor.export_button.cget('state')=='disabled'
    load(editor,clips['silent'])
    assert editor.export_button.cget('state')=='normal'
    monkeypatch.setattr(editor.worker.__class__,'running',property(lambda self:True))
    monkeypatch.setattr(ui.messagebox,'askyesno',lambda *a,**k:False)
    editor.request_close()
    assert not editor._closing
    monkeypatch.undo()


def test_crop_pending_result_cannot_change_display_mode(editor,clips):
    load(editor,clips['source'])
    old=editor._preview_generation
    from app.preview import PreviewResult
    editor.mode_var.set('crop');editor.selection_mode_changed()
    assert editor._preview_generation>old and editor._display_mode is None
    # Obsolete engine result is rejected again at the UI boundary.
    image=Image.new('RGB',(99,99),'red')
    result=PreviewResult(old,image)
    original=editor.preview.poll
    editor.preview.poll=lambda:[result]
    editor.after_cancel(editor._poll_after)
    editor._poll()
    editor.preview.poll=original
    assert editor.preview_canvas.image_size != (99,99) and editor._display_mode is None


def test_ui_uses_system_unicode_font(editor):
    import os
    family=editor.info_label.cget('font').actual('family').lower()
    assert ('segoe' in family if os.name=='nt' else 'dejavu' in family)


def test_textbox_typing_updates_model(editor,clips):
    load(editor,clips['source'])
    panel=editor.options.text_panels['intro']
    panel.vars['enabled'].set(True)
    panel.textbox.insert('1.0','Đầu\nVideo')
    editor.update()
    assert panel.vars['text'].get()=='Đầu\nVideo'
    assert editor.options.read_options().intro.text=='Đầu\nVideo'


def test_export_all_effects_from_gui(editor,clips,tmp_path,font):
    load(editor,clips['silent'])
    panel=editor.options
    panel.vars['flip_horizontal'].set(True)
    panel.apply_region('crop',Rect(0,0,160,120))
    panel.apply_region('blur',Rect(40,40,30,30))
    panel.vars['speed'].set('2')
    logo=tmp_path/'logo.png';Image.new('RGBA',(20,20),'white').save(logo)
    panel.vars['logo_path'].set(str(logo));panel.vars['logo_width'].set('20')
    panel.apply_region('logo',(120,80))
    for key,text in [('intro','Đầu'),('watermark','WM')]:
        widget=panel.text_panels[key]
        widget.vars['font'].set(str(font));widget.vars['size'].set('14');widget.vars['text'].set(text)
        panel.apply_region(key,(10,10 if key=='watermark' else 70))
    editor.output_dir_var.set(str(tmp_path));editor.output_name_var.set('edited.mp4')
    editor.start_export()
    spin(editor,lambda:editor._last_terminal is not None)
    assert editor._last_terminal.kind=='completed',editor._last_terminal.message
    result=probe(tmp_path/'edited.mp4')
    assert (result.width,result.height)==(160,120) and result.duration==pytest.approx(2,abs=.07)


def test_worker_error_reenables_ui(editor,clips,tmp_path):
    source=tmp_path/'source.mp4';source.write_bytes(clips['source'].read_bytes())
    load(editor,source)
    source.write_bytes(b'corrupted after probe')
    editor.output_dir_var.set(str(tmp_path));editor.output_name_var.set('out.mp4')
    editor.start_export()
    spin(editor,lambda:editor._last_terminal is not None)
    assert editor._last_terminal.kind=='error'
    assert editor.export_button.cget('state')=='normal' and editor.cancel_button.cget('state')=='disabled'
    assert editor._test_messages[-1][0]=='error'
    assert not (tmp_path/'out.mp4').exists()


def test_incomplete_crop_does_not_stop_polling(editor,clips):
    load(editor,clips['source'])
    errors=[]
    editor.report_callback_exception=lambda *args:errors.append(args)
    editor.options.apply_region('crop',Rect(0,0,160,120))
    editor.mode_var.set('crop');editor.selection_mode_changed()
    editor.options.vars['crop_x'].set('')
    spin(editor,lambda:editor._display_mode=='crop' or bool(errors))
    assert not errors
    editor.options.vars['crop_x'].set('0')
    spin(editor,lambda:editor._display_mode=='crop')
    assert editor.preview_canvas.enabled


def test_export_restores_selection_without_mode_toggle(editor,clips,tmp_path):
    load(editor,clips['source'])
    editor.options.apply_region('crop',Rect(0,0,160,120))
    editor.mode_var.set('crop');editor.selection_mode_changed()
    spin(editor,lambda:editor._display_mode=='crop')
    editor.output_dir_var.set(str(tmp_path));editor.output_name_var.set('restored.mp4')
    editor.start_export()
    spin(editor,lambda:editor._last_terminal is not None)
    spin(editor,lambda:editor._display_mode=='crop')
    assert editor.preview_canvas.enabled
    assert editor.status_var.get().startswith('Đã xuất:')


def test_placement_can_repair_incomplete_selected_layer(editor,clips):
    load(editor,clips['source'])
    editor.options.apply_region('blur',Rect(10,10,30,30))
    editor.options.vars['blur_x'].set('')
    editor.mode_var.set('blur');editor.selection_mode_changed()
    spin(editor,lambda:editor._display_mode=='blur')
    editor._selected('blur',Rect(20,20,30,30))
    assert editor.options.read_options().blur==Rect(20,20,30,30)


@pytest.mark.parametrize('kind',['cancelled','error'])
def test_terminal_event_restores_blur_selection(editor,clips,kind):
    from app.worker import WorkerEvent
    load(editor,clips['source'])
    editor.mode_var.set('blur');editor.selection_mode_changed()
    spin(editor,lambda:editor._display_mode=='blur')
    editor._invalidate_preview();editor._set_busy(True)
    editor._handle_worker_event(WorkerEvent(kind,message='test failure'))
    spin(editor,lambda:editor._display_mode=='blur')
    canvas=editor.preview_canvas;box=canvas.image_box
    canvas.press(SimpleNamespace(x=box.x+box.width//4,y=box.y+box.height//4))
    canvas.release(SimpleNamespace(x=box.x+box.width//2,y=box.y+box.height//2))
    assert editor.options.read_options().blur is not None


def canvas_point(canvas,x,y):
    box=canvas.image_box;w,h=canvas.image_size
    return SimpleNamespace(x=box.x+x*box.width/w,y=box.y+y*box.height/h)


def test_trim_controls_and_output_timeline(editor,clips):
    load(editor,clips['source'])
    panel=editor.options
    panel.vars['trim_enabled'].set(True)
    panel.vars['trim_start'].set('00:01');panel.vars['trim_end'].set('00:03')
    panel.vars['speed'].set('2')
    assert panel.read_options().trim_start==1 and panel.read_options().trim_end==3
    spin(editor,lambda:editor._display_mode=='preview')
    assert editor.timeline.cget('to')==pytest.approx(1-1/30)


def test_crop_can_resize_corner_and_move_existing_frame(editor,clips):
    load(editor,clips['source'])
    editor.options.apply_region('crop',Rect(40,40,120,100))
    editor.mode_var.set('crop');editor.selection_mode_changed()
    spin(editor,lambda:editor._display_mode=='crop')
    canvas=editor.preview_canvas
    canvas.press(canvas_point(canvas,160,140));canvas.drag(canvas_point(canvas,200,180));canvas.release(canvas_point(canvas,200,180))
    assert editor.options.read_options().crop==Rect(40,40,160,140)
    spin(editor,lambda:editor._display_mode=='crop')
    canvas.press(canvas_point(canvas,100,100));canvas.drag(canvas_point(canvas,120,110));canvas.release(canvas_point(canvas,120,110))
    assert editor.options.read_options().crop==Rect(60,50,160,140)


def test_logo_drag_and_resize_directly(editor,clips,tmp_path):
    load(editor,clips['source'])
    path=tmp_path/'logo.png';Image.new('RGBA',(20,10),'white').save(path)
    panel=editor.options
    panel.vars['logo_path'].set(str(path));panel.vars['logo_width'].set('40')
    panel.apply_region('logo',(40,40))
    editor.mode_var.set('logo');editor.selection_mode_changed()
    spin(editor,lambda:editor._display_mode=='logo')
    canvas=editor.preview_canvas
    assert isinstance(canvas._selection,Rect)
    canvas.press(canvas_point(canvas,80,60));canvas.drag(canvas_point(canvas,100,90));canvas.release(canvas_point(canvas,100,90))
    logo=panel.read_options().logo
    assert (logo.x,logo.y,logo.width,logo.height)==(40,40,60,50)
    spin(editor,lambda:editor._display_mode=='logo')
    canvas.press(canvas_point(canvas,60,60));canvas.release(canvas_point(canvas,100,80))
    logo=panel.read_options().logo
    assert (logo.x,logo.y,logo.width,logo.height)==(80,60,60,50)


def test_embedded_play_pause_and_edit_invalidates_proxy(editor,clips):
    load(editor,clips['silent'])
    editor.options.vars['trim_enabled'].set(True)
    editor.options.vars['trim_start'].set('00:01');editor.options.vars['trim_end'].set('00:03')
    editor.start_playback()
    spin(editor,lambda:editor.playback.playing and editor.time_var.get()>.1)
    assert not editor.preview_canvas.enabled
    editor.pause_playback()
    spin(editor,lambda:editor._display_mode=='preview')
    assert not editor.playback.playing and editor.playback.ready
    editor.options.vars['flip_horizontal'].set(True)
    assert not editor.playback.ready
    editor.start_playback()
    spin(editor,lambda:editor.playback.playing)
    editor.request_close()
    spin(editor,lambda:editor._destroyed)
    assert not editor.playback.busy


def test_watermark_moves_and_resizes_from_canvas(editor,clips,font):
    load(editor,clips['source'])
    panel=editor.options.text_panels['watermark']
    panel.vars['font'].set(str(font));panel.vars['text'].set('WM');panel.vars['size'].set('16')
    editor.options.apply_region('watermark',(40,40))
    editor.mode_var.set('watermark');editor.selection_mode_changed()
    spin(editor,lambda:editor._display_mode=='watermark')
    canvas=editor.preview_canvas;region=canvas._selection
    canvas.press(canvas_point(canvas,region.x+region.width/2,region.y+region.height/2))
    canvas.release(canvas_point(canvas,region.x+region.width/2+20,region.y+region.height/2+20))
    text=editor.options.read_options().watermark
    assert (text.x,text.y)==(60,60)
    spin(editor,lambda:editor._display_mode=='watermark')
    region=canvas._selection
    canvas.press(canvas_point(canvas,region.x+region.width,region.y+region.height))
    canvas.release(canvas_point(canvas,region.x+region.width*2,region.y+region.height*2))
    assert editor.options.read_options().watermark.size>16
