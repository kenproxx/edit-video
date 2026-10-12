"""Real folder jobs, transactional outputs and cancellation."""
import time
from pathlib import Path
import pytest
from app.media import probe
from app.models import EditOptions,Rect


def batch_api():
    from app import batch
    return batch


def finish(worker,timeout=30):
    events=[];deadline=time.monotonic()+timeout
    while worker.running and time.monotonic()<deadline:
        events.extend(worker.poll());time.sleep(.01)
    if worker.running: worker.cancel()
    assert not worker.running,'Batch timed out'
    return events+worker.poll()


def folder(tmp_path,clips):
    source=tmp_path/'đầu vào';output=tmp_path/'kết quả';source.mkdir();output.mkdir()
    (source/'a.mp4').write_bytes(clips['silent'].read_bytes())
    (source/'b.MOV').write_bytes(clips['source'].read_bytes())
    return source,output


def test_scan_direct_videos_and_allocate_distinct_names(tmp_path):
    api=batch_api();source=tmp_path/'source';output=tmp_path/'out';source.mkdir();output.mkdir()
    for name in ('clip.mov','clip.mp4','clip_2.mp4','notes.txt'): (source/name).write_bytes(b'x')
    nested=source/'nested';nested.mkdir();(nested/'child.mp4').write_bytes(b'x')
    files=api.scan_videos(source)
    assert len(files)==3 and all(p.parent==source for p in files)
    jobs=api.plan_batch(files,output)
    names=[j.destination.name.casefold() for j in jobs]
    assert len(set(names))==3 and 'clip.mp4' in names and 'clip_2.mp4' in names


def test_reject_input_output_same_folder(tmp_path,clips):
    api=batch_api();source,_=folder(tmp_path,clips)
    before=(source/'a.mp4').read_bytes()
    with pytest.raises(ValueError): api.plan_batch(api.scan_videos(source),source)
    assert (source/'a.mp4').read_bytes()==before


def test_batch_applies_same_options_to_all_and_tracks_progress(tmp_path,clips):
    api=batch_api();source,output=folder(tmp_path,clips)
    before={p.name:p.read_bytes() for p in source.iterdir()}
    worker=api.BatchWorker();worker.start(api.scan_videos(source),output,EditOptions(speed=2,crop=Rect(0,0,160,120),source_volume=.5))
    events=finish(worker)
    assert events[-1].kind=='completed'
    assert [r.status for r in worker.results]==['completed','completed']
    for name in ('a.mp4','b.mp4'):
        info=probe(output/name);assert info.duration==pytest.approx(2,abs=.07) and (info.width,info.height)==(160,120)
    assert all(p.read_bytes()==before[p.name] for p in source.iterdir())
    assert any(e.kind=='progress' for e in events)
    assert worker.report_path.is_file()
    assert not list(output.glob('.videoeditor-*'))


def test_bad_file_and_existing_output_do_not_stop_later_jobs(tmp_path,clips):
    api=batch_api();source,output=folder(tmp_path,clips)
    (source/'0-bad.mp4').write_bytes(b'broken');(output/'a.mp4').write_bytes(b'keep')
    worker=api.BatchWorker();worker.start(api.scan_videos(source),output,EditOptions())
    events=finish(worker)
    assert events[-1].kind=='completed'
    assert [r.status for r in worker.results]==['error','skipped','completed']
    assert (output/'a.mp4').read_bytes()==b'keep'
    assert probe(output/'b.mp4').duration==pytest.approx(4,abs=.07)


def test_invalid_options_per_video_continue(tmp_path,clips):
    api=batch_api();source,output=folder(tmp_path,clips)
    worker=api.BatchWorker();worker.start(api.scan_videos(source),output,EditOptions(trim_start=3,trim_end=5))
    finish(worker)
    assert [r.status for r in worker.results]==['error','error'] and not list(output.iterdir())


def test_cancel_stops_active_renderer_and_does_not_start_next(tmp_path,clips):
    import subprocess
    api=batch_api();source,output=folder(tmp_path,clips)
    subprocess.run(['ffmpeg','-v','error','-y','-stream_loop','-1','-i',str(clips['source']),'-t','120','-c','copy',str(source/'a.mp4')],check=True)
    worker=api.BatchWorker();worker.start(api.scan_videos(source),output,EditOptions(speed=.25,blur=Rect(0,0,300,200)))
    deadline=time.monotonic()+10
    while worker._worker._process is None and worker.running and time.monotonic()<deadline: time.sleep(.01)
    process=worker._worker._process;assert process is not None
    worker.cancel();events=finish(worker)
    assert events[-1].kind=='cancelled' and process.poll() is not None
    assert not list(output.iterdir()) and not any(r.status=='completed' for r in worker.results)


def test_adapt_regions_logo_and_text_relative_to_crop(clips,tmp_path,font):
    from dataclasses import replace
    from app.models import LogoOverlay,TextOverlay,validate_options
    from PIL import Image
    api=batch_api();reference=probe(clips['source']);target=replace(reference,width=160,height=120)
    image=tmp_path/'logo.png';Image.new('RGBA',(20,10),'white').save(image)
    text=TextOverlay('WM',font,16,'white','black',2,10,50,1)
    options=EditOptions(speed=2,trim_start=1,trim_end=3,crop=Rect(40,20,240,200),blur=Rect(20,10,40,20),logo=LogoOverlay(image,180,120,40,1,height=20),watermark=text,source_volume=.25)
    edit=api.adapt_options(options,reference,target)
    assert edit.crop==Rect(20,10,120,100) and edit.blur==Rect(10,5,20,10)
    assert (edit.logo.x,edit.logo.y,edit.logo.width,edit.logo.height)==(90,60,20,10)
    assert (edit.watermark.x,edit.watermark.y,edit.watermark.size,edit.watermark.stroke_width)==(5,25,8,1)
    assert edit.speed==2 and edit.trim_start==1 and edit.trim_end==3 and edit.source_volume==.25
    validate_options(edit,160,120,4)


def test_batch_scales_crop_for_different_resolutions(tmp_path,clips):
    import subprocess
    api=batch_api();source,output=folder(tmp_path,clips)
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(clips['source']),'-vf','scale=160:120','-c:v','libx264','-threads','2','-c:a','aac',str(source/'b.MOV')],check=True)
    reference=probe(source/'a.mp4')
    worker=api.BatchWorker();worker.start(api.scan_videos(source),output,EditOptions(crop=Rect(0,0,160,120)),reference=reference,scale=True)
    finish(worker)
    assert all(r.status=='completed' for r in worker.results)
    assert (probe(output/'a.mp4').width,probe(output/'a.mp4').height)==(160,120)
    assert (probe(output/'b.mp4').width,probe(output/'b.mp4').height)==(80,60)


def test_cancel_keeps_completed_output_and_records_unstarted_jobs(tmp_path,clips):
    import subprocess
    api=batch_api();source,output=folder(tmp_path,clips)
    subprocess.run(['ffmpeg','-v','error','-y','-stream_loop','-1','-i',str(clips['source']),'-t','120','-c','copy',str(source/'b.MOV')],check=True)
    (source/'c.mp4').write_bytes(clips['silent'].read_bytes())
    worker=api.BatchWorker();worker.start(api.scan_videos(source),output,EditOptions(speed=.25))
    deadline=time.monotonic()+10
    while (not worker.results or worker._worker._process is None) and worker.running and time.monotonic()<deadline: time.sleep(.01)
    assert worker.results and worker.results[0].status=='completed'
    worker.cancel();finish(worker)
    assert probe(output/'a.mp4').duration==pytest.approx(16,abs=.1)
    assert [r.status for r in worker.results]==['completed','cancelled','cancelled']
    assert not (output/'b.mp4').exists() and not (output/'c.mp4').exists()
