"""Real edited-proxy render/decode and bounded process lifecycle."""
import time
from pathlib import Path
import pytest
from app.models import EditOptions,Rect
from app.media import probe


def controller():
    from app.playback import PlaybackController
    return PlaybackController()


def wait(player,predicate,timeout=15):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        events=player.poll()
        for event in events:
            if predicate(event): return event
            if event.image is not None: event.image.close()
        time.sleep(.02)
    pytest.fail('Playback operation timed out')


def close(player):
    player.close()
    end=time.monotonic()+10
    while player.busy and time.monotonic()<end:
        player.poll();time.sleep(.02)
    assert not player.busy


def test_edited_proxy_embedded_frames_and_trim(clips):
    player=controller()
    try:
        edit=EditOptions(trim_start=1,trim_end=3,speed=2,flip_horizontal=True,crop=Rect(0,0,160,120))
        generation=player.prepare(clips['silent'],probe(clips['silent']),edit)
        event=wait(player,lambda e:e.kind in ('ready','error'))
        assert event.kind=='ready',event.message
        assert player.duration==pytest.approx(1,abs=.07)
        player.play(0)
        event=wait(player,lambda e:e.kind=='frame')
        assert event.generation==generation and event.image.size==(160,120)
        assert max(abs(a-b) for a,b in zip(event.image.getpixel((10,10)),(0,128,0)))<25
        event.image.close()
        assert player.playing
    finally: close(player)


def test_pause_seek_and_invalidate_drop_stale_frames(clips):
    player=controller()
    try:
        player.prepare(clips['silent'],probe(clips['silent']),EditOptions())
        wait(player,lambda e:e.kind=='ready')
        player.play(0);event=wait(player,lambda e:e.kind=='frame');event.image.close()
        player.pause();assert not player.playing and player.ready
        assert not any(e.kind=='frame' for e in player.poll())
        player.play(2)
        event=wait(player,lambda e:e.kind=='frame')
        assert event.time>=2;event.image.close()
        player.invalidate();assert not player.ready and not player.playing
        assert not any(e.kind=='frame' for e in player.poll())
    finally: close(player)


def test_close_during_proxy_preparation_cleans_resources(clips):
    player=controller();directory=player.directory
    player.prepare(clips['source'],probe(clips['source']),EditOptions(speed=.25))
    close(player)
    assert not directory.exists()


def test_audio_process_and_frame_queue_are_bounded(clips,monkeypatch):
    monkeypatch.setenv('SDL_AUDIODRIVER','dummy')
    player=controller()
    try:
        player.prepare(clips['source'],probe(clips['source']),EditOptions())
        wait(player,lambda e:e.kind=='ready')
        player.play(0)
        event=wait(player,lambda e:e.kind=='frame');event.image.close()
        reader=player._reader
        assert reader.audio_process is not None
        time.sleep(.4)
        assert reader.pending_frames<=1
        decoder,audio=reader.process,reader.audio_process
    finally: close(player)
    assert decoder.poll() is not None and audio.poll() is not None


def test_invalidation_defers_deleting_proxy_until_reader_reaped(clips,monkeypatch):
    player=controller()
    try:
        player.prepare(clips['silent'],probe(clips['silent']),EditOptions())
        wait(player,lambda e:e.kind=='ready')
        path=player._proxy[0]
        player.play(0);event=wait(player,lambda e:e.kind=='frame');event.image.close()
        original=Path.unlink
        def locked_unlink(self,*args,**kwargs):
            if self==path and any(r.active for r in player._retired): raise PermissionError('Windows reader still holds the proxy')
            return original(self,*args,**kwargs)
        monkeypatch.setattr(Path,'unlink',locked_unlink)
        player.invalidate()
        end=time.monotonic()+5
        while player.busy and time.monotonic()<end: player.poll();time.sleep(.02)
        player.poll()
        assert not path.exists()
    finally: close(player)


def test_proxy_audio_materializes_leading_silence(tmp_path):
    from array import array
    import subprocess
    from app.render import prepare_render
    source=tmp_path/'delayed.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=blue:size=320x240:rate=30:duration=3','-itsoffset','1','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=2','-c:v','libx264','-threads','2','-c:a','aac',str(source)],check=True)
    out=tmp_path/'proxy.mp4'
    prepared=prepare_render(source,probe(source),EditOptions(),out,tmp_path/'assets',preview=True)
    subprocess.run(prepared.args,check=True,capture_output=True)
    raw=subprocess.run(['ffmpeg','-v','error','-i',str(out),'-vn','-ac','1','-ar','48000','-f','f32le','pipe:1'],capture_output=True,check=True).stdout
    samples=array('f');samples.frombytes(raw)
    assert max(abs(v) for v in samples[:24000])<.001
    assert max(abs(v) for v in samples[60000:72000])>.05
