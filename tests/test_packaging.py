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
