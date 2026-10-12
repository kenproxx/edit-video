"""Packaging contract: tests must fail on unsafe fallback or broken CLI/build."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from app import resources

ROOT = Path(__file__).resolve().parents[1]


def test_frozen_missing_tool_never_uses_path(tmp_path,monkeypatch):
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    monkeypatch.setattr(sys,'_MEIPASS',str(tmp_path),raising=False)
    with pytest.raises(FileNotFoundError): resources.binary_path('ffmpeg')


def test_frozen_tools_and_user_data_outside_bundle(tmp_path,monkeypatch):
    bundle=tmp_path/'readonly';(bundle/'tools').mkdir(parents=True)
    name='ffmpeg.exe' if os.name=='nt' else 'ffmpeg'
    tool=bundle/'tools'/name;tool.write_bytes(b'corrupt binary')
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    monkeypatch.setattr(sys,'_MEIPASS',str(bundle),raising=False)
    assert resources.binary_path('ffmpeg')==tool
    assert not resources.user_data_dir().is_relative_to(bundle)
    from app import selftest
    with pytest.raises((OSError,ValueError,subprocess.SubprocessError)):
        selftest.verify_media_tools()


def test_help_does_not_open_gui_or_install_packages():
    result=subprocess.run([sys.executable,str(ROOT/'main.py'),'--help'],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert '--smoke-test' in result.stdout


def test_headless_smoke_exports_and_reports(clips,tmp_path):
    output=tmp_path/'xuất video';output.mkdir()
    report=tmp_path/'report.json'
    source=tmp_path/'đầu video.mp4';source.write_bytes(clips['source'].read_bytes())
    result=subprocess.run([sys.executable,str(ROOT/'main.py'),'--smoke-test',str(source),'--output-dir',str(output),'--report',str(report)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    data=json.loads(report.read_text(encoding='utf-8'))
    assert data['ok'] and data['video_codec']=='h264' and data['audio_codec']=='aac'
    assert data['duration']==pytest.approx(4,abs=.07)
    assert Path(data['output']).is_file()


def test_smoke_rejects_input_collision(clips,tmp_path):
    source=tmp_path/'clip.mp4';source.write_bytes(clips['silent'].read_bytes())
    original=source.read_bytes();report=tmp_path/'failure.json'
    result=subprocess.run([sys.executable,str(ROOT/'main.py'),'--smoke-test',str(source),'--output-dir',str(tmp_path),'--report',str(report)],capture_output=True,text=True,timeout=30)
    assert result.returncode!=0
    assert source.read_bytes()==original
    assert not json.loads(report.read_text(encoding='utf-8'))['ok']


def test_build_explicitly_rejects_linux():
    if os.name=='nt': pytest.skip('Linux-specific rejection')
    result=subprocess.run(['bash',str(ROOT/'build.sh')],capture_output=True,text=True)
    assert result.returncode!=0 and 'Windows' in result.stderr


def pwsh():
    executable=shutil.which('pwsh') or '/tmp/edit-video-powershell/pwsh'
    if not Path(executable).is_file(): pytest.skip('PowerShell unavailable; Windows bootstrap checks unrun')
    return executable


def powershell(*args):
    return subprocess.run([pwsh(),'-NoProfile','-File',str(ROOT/'scripts/bootstrap-build.ps1'),*map(str,args)],capture_output=True,text=True,timeout=20)


def test_bootstrap_rejects_non_windows_before_download(tmp_path):
    if os.name=='nt': pytest.skip('Linux-specific rejection')
    result=powershell('-CacheDir',tmp_path)
    assert result.returncode!=0 and 'Windows x64' in result.stderr
    assert not list(tmp_path.iterdir())


def test_tampered_cached_artifact_fails_without_download(tmp_path):
    manifest=json.loads((ROOT/'scripts/build-manifest.json').read_text())
    cached=tmp_path/manifest['ffmpeg']['filename'];cached.write_bytes(b'tampered')
    result=powershell('-VerifyCache','-CacheDir',tmp_path)
    assert result.returncode!=0 and 'SHA256 mismatch' in result.stderr
    assert cached.read_bytes()==b'tampered'


def test_verified_cache_is_repeatable(tmp_path):
    import hashlib
    content=b'fixture verified artifact';cached=tmp_path/'artifact.zip';cached.write_bytes(content)
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'schema_version':1,'python':{'filename':cached.name,'sha256':hashlib.sha256(content).hexdigest()},'ffmpeg':{'filename':cached.name,'sha256':hashlib.sha256(content).hexdigest()}}))
    for _ in range(2):
        result=powershell('-VerifyCache','-CacheDir',tmp_path,'-ManifestPath',manifest)
        assert result.returncode==0,result.stderr
    assert cached.read_bytes()==content


def test_collect_licenses_copies_full_runtime_license_texts(tmp_path):
    import importlib.util
    path=ROOT/'scripts/prepare-package.py'
    assert path.is_file(), 'Package license collector is missing'
    spec=importlib.util.spec_from_file_location('prepare_package',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.collect_wheel_licenses(tmp_path,['customtkinter','Pillow','darkdetect','packaging'])
    texts='\n'.join(p.read_text(encoding='utf-8',errors='replace') for p in tmp_path.rglob('*') if p.is_file())
    assert 'Permission is hereby granted' in texts
    assert 'Apache License' in texts and 'Pillow' in texts


def test_gui_smoke_reports_native_startup_and_close(tmp_path):
    assert os.environ.get('DISPLAY') or os.name=='nt', 'GUI validation needs an actual display or Xvfb'
    report=tmp_path/'gui.json'
    result=subprocess.run([sys.executable,str(ROOT/'main.py'),'--gui-smoke-test','--report',str(report)],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr
    assert json.loads(report.read_text(encoding='utf-8'))=={'ok':True,'gui':True}


def test_smoke_report_cannot_overwrite_input(clips,tmp_path):
    source=tmp_path/'clip.mp4';source.write_bytes(clips['silent'].read_bytes())
    original=source.read_bytes()
    result=subprocess.run([sys.executable,str(ROOT/'main.py'),'--smoke-test',str(source),'--output-dir',str(tmp_path),'--report',str(source)],capture_output=True,text=True,timeout=30)
    assert result.returncode!=0
    assert source.read_bytes()==original


def test_smoke_report_cannot_replace_existing_file(clips,tmp_path):
    source=tmp_path/'clip.mp4';source.write_bytes(clips['silent'].read_bytes())
    report=tmp_path/'existing.json';report.write_bytes(b'keep existing report')
    result=subprocess.run([sys.executable,str(ROOT/'main.py'),'--smoke-test',str(source),'--output-dir',str(tmp_path),'--report',str(report)],capture_output=True,text=True,timeout=30)
    assert result.returncode!=0
    assert report.read_bytes()==b'keep existing report'


def test_smoke_report_cannot_take_output_name(clips,tmp_path):
    source=tmp_path/'clip.mp4';source.write_bytes(clips['silent'].read_bytes())
    output=tmp_path/'export';output.mkdir()
    result=subprocess.run([sys.executable,str(ROOT/'main.py'),'--smoke-test',str(source),'--output-dir',str(output),'--report',str(output/source.name)],capture_output=True,text=True,timeout=30)
    assert result.returncode!=0
    assert not (output/source.name).exists()


def test_bootstrap_parameter_binding_does_not_require_script_root(tmp_path):
    # Windows PowerShell can bind default parameters before PSScriptRoot is set.
    # Execute the real param block with an unset root, not a rewritten stand-in.
    script=tmp_path/'binding.ps1'
    script.write_text('''$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($args[0], [ref]$tokens, [ref]$errors)
$PSScriptRoot = ''
& ([scriptblock]::Create($ast.ParamBlock.Extent.Text + "`nWrite-Output 'BOUND'"))
''',encoding='utf-8')
    result=subprocess.run([pwsh(),'-NoProfile','-File',str(script),str(ROOT/'scripts/bootstrap-build.ps1')],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr
    assert 'BOUND' in result.stdout


def test_bootstrap_default_paths_are_relative_to_script_not_cwd(tmp_path):
    import hashlib
    project=tmp_path/'dự án build';scripts=project/'scripts';scripts.mkdir(parents=True)
    shutil.copy2(ROOT/'scripts/bootstrap-build.ps1',scripts/'bootstrap-build.ps1')
    cache=project/'.build-cache';cache.mkdir()
    content=b'verified default-cache artifact';(cache/'artifact.zip').write_bytes(content)
    artifact={'filename':'artifact.zip','sha256':hashlib.sha256(content).hexdigest()}
    (scripts/'build-manifest.json').write_text(json.dumps({'schema_version':1,'python':artifact,'ffmpeg':artifact}))
    other=tmp_path/'unrelated';other.mkdir()
    result=subprocess.run([pwsh(),'-NoProfile','-File',str(scripts/'bootstrap-build.ps1'),'-VerifyCache'],capture_output=True,text=True,timeout=20,cwd=other)
    assert result.returncode==0,result.stderr
    assert 'Verified 2' in result.stdout
    assert not list(other.iterdir())


# FFmpeg 8.1.2 opt_common.c show_filters prints two flags (%c%c),
# whereas FFmpeg 7 prints three. Same capabilities, different table format.
FILTER_TABLE_8 = '''Filters:
  T.. = Timeline support
  .S. = Slice threading
  A = Audio input/output
  V = Video input/output
  ------
 .. aformat           A->A       Convert audio format.
 .. volume            A->A       Adjust volume.
 .. amix              AA->A      Mix audio.
 .. anull             A->A       Pass audio.
 .. adelay            A->A       Delay audio.
 .. apad              A->A       Pad audio.
 .. trim              V->V       Trim video.
 .. asetpts           A->A       Set timestamps for the output audio frame.
 .. atempo            A->A       Adjust audio tempo.
 .. atrim             A->A       Pick one continuous section from the input.
 .. crop              V->V       Crop the input video.
 .. format            V->V       Convert the input video to one of the specified pixel formats.
 .. fps               V->V       Force constant framerate.
 TS gblur             V->V       Apply Gaussian Blur filter.
 .S hflip             V->V       Horizontally flip the input video.
 TS overlay           VV->V      Overlay a video source on top of the input.
 .. scale             V->V       Scale the input video size and/or convert the image format.
 .. setpts            V->V       Set timestamps for the output video frame.
 .. setsar            V->V       Set the pixel sample aspect ratio.
 .. split             V->N       Pass on the input to N video outputs.
 .S vflip             V->V       Flip the input video vertically.
'''
ENCODER_TABLE = '''Encoders:
 V..... libx264       libx264 H.264 / AVC (codec h264)
 A..... aac           AAC (Advanced Audio Coding)
'''


def media_tables(monkeypatch,filters=FILTER_TABLE_8,encoders=ENCODER_TABLE):
    from app import selftest
    # Isolate the external tool version; assertions check verifier behavior.
    def output(args):
        if args[-1]=='-filters': return filters
        if args[-1]=='-encoders': return encoders
        return Path(args[0]).stem+' version 8.1.2\n'
    monkeypatch.setattr(selftest,'_run',output)
    return selftest


@pytest.mark.parametrize('flag_columns',[2,3])
def test_tool_validation_accepts_ffmpeg_7_and_8_tables(monkeypatch,flag_columns):
    table=FILTER_TABLE_8
    if flag_columns==3:
        table='\n'.join(line[:3]+'.'+line[3:] if line.startswith((' .. ',' TS ',' .S ')) else line for line in table.splitlines())
    selftest=media_tables(monkeypatch,filters=table)
    assert selftest.verify_media_tools()['ffmpeg']=='ffmpeg version 8.1.2'


@pytest.mark.parametrize('missing',['gblur','libx264','aac'])
def test_tool_validation_still_rejects_missing_capabilities(monkeypatch,missing):
    filters='\n'.join(line for line in FILTER_TABLE_8.splitlines() if missing not in line)
    encoders='\n'.join(line for line in ENCODER_TABLE.splitlines() if missing not in line)
    selftest=media_tables(monkeypatch,filters,encoders)
    with pytest.raises(ValueError,match=missing) as error:
        selftest.verify_media_tools()
    assert str(error.value).split(': ',1)[1]==missing


def test_embedded_playback_smoke_cli(clips,tmp_path,monkeypatch):
    assert os.environ.get('DISPLAY') or os.name=='nt','Playback CLI needs an actual display'
    monkeypatch.setenv('SDL_AUDIODRIVER','dummy')
    source=tmp_path/'movie.mp4';source.write_bytes(clips['source'].read_bytes())
    report=tmp_path/'playback.json'
    result=subprocess.run([sys.executable,str(ROOT/'main.py'),'--playback-smoke-test',str(source),'--report',str(report)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    data=json.loads(report.read_text(encoding='utf-8'))
    assert data['ok'] and data['playback'] and data['frames']>=4 and data['audio']
    assert data['duration']==pytest.approx(1,abs=.04)


def test_cli_exports_with_independent_audio_levels(tmp_path,clips):
    import subprocess,sys,json
    source=tmp_path/'movie.mp4';source.write_bytes(clips['silent'].read_bytes())
    audio=tmp_path/'track.wav'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=880:duration=0.4',str(audio)],check=True)
    output=tmp_path/'out';output.mkdir();report=tmp_path/'audio.json'
    result=subprocess.run([sys.executable,str(ROOT/'main.py'),'--smoke-test',str(source),'--audio-file',str(audio),'--source-volume','25','--added-volume','60','--audio-loop','--output-dir',str(output),'--report',str(report)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    data=json.loads(report.read_text(encoding='utf-8'))
    assert data['ok'] and data['audio_codec']=='aac'
    from test_audio_edit import samples,tone
    assert tone(samples(output/'movie.mp4'),880,1.2,1.4)==pytest.approx(.075,abs=.004)


def test_cli_embedded_playback_uses_inserted_audio_on_silent_video(tmp_path,clips):
    import subprocess,sys,json
    audio=tmp_path/'track.wav';report=tmp_path/'play.json'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=880:duration=0.4',str(audio)],check=True)
    result=subprocess.run([sys.executable,str(ROOT/'main.py'),'--playback-smoke-test',str(clips['silent']),'--audio-file',str(audio),'--report',str(report)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    data=json.loads(report.read_text(encoding='utf-8'))
    assert data['ok'] and data['playback'] and data['audio']


def test_cli_inserted_audio_duration_caps_once_track(tmp_path,clips):
    import subprocess,sys,json
    audio=tmp_path/'long.wav';output=tmp_path/'out';output.mkdir();report=tmp_path/'limited.json'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=880:duration=2',str(audio)],check=True)
    result=subprocess.run([sys.executable,str(ROOT/'main.py'),'--smoke-test',str(clips['silent']),'--audio-file',str(audio),'--audio-duration','0.6','--output-dir',str(output),'--report',str(report)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    data=json.loads(report.read_text(encoding='utf-8'));assert data['ok'],data
    from test_audio_edit import samples,tone
    values=samples(Path(data['output']))
    assert tone(values,880,.2,.4)==pytest.approx(.125,abs=.004)
    assert tone(values,880,1.2,1.4)==pytest.approx(0,abs=.003)


def test_cli_folder_batch_uses_shared_engine_and_reports_errors(tmp_path,clips):
    import subprocess,sys,json
    folder=tmp_path/'input';folder.mkdir();output=tmp_path/'out';output.mkdir();report=tmp_path/'batch.json'
    (folder/'a.mp4').write_bytes(clips['source'].read_bytes());(folder/'b.mov').write_bytes(clips['silent'].read_bytes());(folder/'bad.mp4').write_bytes(b'broken')
    result=subprocess.run([sys.executable,str(ROOT/'main.py'),'--batch-smoke-test',str(folder),'--output-dir',str(output),'--report',str(report)],capture_output=True,text=True,timeout=40)
    assert result.returncode==0,result.stderr
    data=json.loads(report.read_text(encoding='utf-8'))
    assert data['ok'] and data['batch'] and data['counts']=={'completed':2,'error':1,'skipped':0,'cancelled':0}
    from app.media import probe
    assert probe(output/'a.mp4').duration==pytest.approx(2,abs=.07)


def test_batch_cli_report_cannot_shadow_planned_video(tmp_path,clips):
    import main
    folder=tmp_path/'input';folder.mkdir();output=tmp_path/'out';output.mkdir()
    (folder/'a.mp4').write_bytes(clips['source'].read_bytes())
    target=output/'a.mp4'
    assert main.main(['--batch-smoke-test',str(folder),'--output-dir',str(output),'--report',str(target)])==1
    assert not target.exists()
