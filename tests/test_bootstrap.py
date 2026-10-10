import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]

def test_bundle_manifest():
    manifest=json.loads((ROOT/'packaging/downloads.json').read_text())
    for key in ('python','ffmpeg'):
        item=manifest[key]
        assert len(item['sha256'])==64
        assert item['url'].startswith('https://') and 'latest' not in item['url']
        assert item['version'] in item['url']
    assert (ROOT/'EditVideo.spec').is_file()

@pytest.mark.skipif(os.name!='nt',reason='PowerShell bootstrap must run on Windows CI')
def test_bootstrap_rejects_bad_hash(tmp_path):
    f=tmp_path/'bad.zip'; f.write_bytes(b'bad')
    command=f". '{ROOT / 'scripts/download.ps1'}'; Assert-Hash '{f}' '{'0'*64}'"
    p=subprocess.run(['powershell','-NoProfile','-Command',command],capture_output=True)
    assert p.returncode!=0
    assert b'SHA256' in p.stderr

@pytest.mark.skipif(os.name!='nt',reason='PowerShell bootstrap must run on Windows CI')
def test_bootstrap_stops_on_download_failure(tmp_path):
    dest=tmp_path/'absent.zip'
    command=f". '{ROOT / 'scripts/download.ps1'}'; Get-VerifiedDownload 'http://127.0.0.1:9/missing' '{dest}' '{'0'*64}'"
    p=subprocess.run(['powershell','-NoProfile','-Command',command],capture_output=True,timeout=30)
    assert p.returncode!=0 and not dest.exists()

def test_self_test(tmp_path,qapp,binaries):
    from edit_video.self_test import run_self_test
    assert run_self_test(tmp_path,binaries)==0
    result=json.loads((tmp_path/'self-test.json').read_text())
    assert result['success'] is True and (tmp_path/'edited.mp4').is_file()
