from app.models import EditOptions, Rect
from app.media import probe
from app.render import prepare_render
import pytest

@pytest.mark.parametrize('speed,tempos',[(.25,'atempo=0.5,atempo=0.5'),(4,'atempo=2,atempo=2')])
def test_filter_order_and_encoding(clips,tmp_path,speed,tempos):
    p=prepare_render(clips['source'],probe(clips['source']),EditOptions(speed=speed,flip_horizontal=True,crop=Rect(0,0,160,120),blur=Rect(0,0,30,30)),tmp_path/'out.mp4',tmp_path)
    graph=p.args[p.args.index('-filter_complex')+1]
    assert graph.index('scale=')<graph.index('hflip')<graph.index('crop=160:120')<graph.index('setpts=')<graph.index('gblur=')
    assert tempos in graph
    for flag,value in [('-c:v','libx264'),('-crf','20'),('-preset','medium'),('-pix_fmt','yuv420p'),('-movflags','+faststart')]:
        assert p.args[p.args.index(flag)+1]==value
    assert p.duration==4/speed

def test_optional_audio_and_hdr(clips,tmp_path):
    p=prepare_render(clips['silent'],probe(clips['silent']),EditOptions(),tmp_path/'out.mp4',tmp_path)
    assert '-an' in p.args
    from dataclasses import replace
    with pytest.raises(ValueError,match='HDR'):
        prepare_render(clips['silent'],replace(probe(clips['silent']),is_hdr=True),EditOptions(),tmp_path/'out.mp4',tmp_path)
