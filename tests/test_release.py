"""Release preparation must reject unverified builds and preserve draft state."""
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile
import pytest

ROOT=Path(__file__).resolve().parents[1]


def preparer():
    path=ROOT/'scripts/prepare-release.py'
    assert path.is_file(), 'Verified release preparer is missing'
    spec=importlib.util.spec_from_file_location('prepare_release',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.prepare_release


@pytest.fixture
def release_inputs(tmp_path):
    # Minimal PE signature payload; native executable behavior is covered by CI.
    exe=bytearray(70);exe[:2]=b'MZ';exe[60:64]=(64).to_bytes(4,'little');exe[64:70]=b'PE\0\0\x64\x86'
    archive=tmp_path/'artifact.zip'
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('VideoEditor.exe',exe)
        z.writestr('VideoEditor.exe.sha256',hashlib.sha256(exe).hexdigest()+'  VideoEditor.exe\n')
        z.writestr('THIRD_PARTY_NOTICES.md','License/source information')
        z.writestr('licenses/ffmpeg/LICENSE','GPL terms')
    digest=hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()
    sha='a'*40
    return archive,{'name':'VideoEditor-windows-x64','expired':False,'digest':'sha256:'+digest},{'draft':True,'tag_name':'v0.1.0','target_commitish':sha},{'status':'completed','conclusion':'success','head_branch':'main','head_sha':sha,'path':'.github/workflows/windows-build.yml'}


def test_prepare_release_contains_verified_exe_zip_and_checksums(release_inputs,tmp_path):
    files=preparer()(*release_inputs,tmp_path/'assets')
    assert {p.name for p in files}=={'VideoEditor.exe','VideoEditor-windows-x64-v0.1.0.zip','SHA256SUMS.txt','THIRD_PARTY_NOTICES.md'}
    sums=next(p for p in files if p.name=='SHA256SUMS.txt').read_text()
    for file in files[:2]:
        assert hashlib.file_digest(file.open('rb'),'sha256').hexdigest()+'  '+file.name in sums


@pytest.mark.parametrize('case',['failed','wrong_commit','pull_request','published','expired','bad_digest','wrong_workflow'])
def test_release_rejects_unverified_or_public_inputs(release_inputs,tmp_path,case):
    archive,artifact,release,run=release_inputs
    if case=='failed': run['conclusion']='failure'
    if case=='wrong_commit': run['head_sha']='b'*40
    if case=='pull_request': run['head_branch']='feature'
    if case=='published': release['draft']=False
    if case=='expired': artifact['expired']=True
    if case=='bad_digest': artifact['digest']='sha256:'+'0'*64
    if case=='wrong_workflow': run['path']='.github/workflows/unrelated.yml'
    with pytest.raises(ValueError): preparer()(archive,artifact,release,run,tmp_path/'assets')
    assert not (tmp_path/'assets').exists()


def test_release_rejects_tampered_exe_even_with_valid_zip_digest(release_inputs,tmp_path):
    archive,artifact,release,run=release_inputs
    with zipfile.ZipFile(archive) as z: contents={n:z.read(n) for n in z.namelist()}
    contents['VideoEditor.exe.sha256']=('0'*64+'  VideoEditor.exe\n').encode()
    with zipfile.ZipFile(archive,'w') as z:
        for name,data in contents.items(): z.writestr(name,data)
    artifact['digest']='sha256:'+hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()
    with pytest.raises(ValueError): preparer()(archive,artifact,release,run,tmp_path/'assets')


def test_release_does_not_overwrite_existing_output(release_inputs,tmp_path):
    output=tmp_path/'assets';output.mkdir();file=output/'keep';file.write_text('keep')
    with pytest.raises(FileExistsError): preparer()(*release_inputs,output)
    assert file.read_text()=='keep'


def test_version_workflow_can_attach_after_verified_build_job(release_inputs,tmp_path):
    archive,artifact,release,run=release_inputs
    run.update(id=42,path='.github/workflows/version-release.yml',head_branch=release['tag_name'],event='push',status='in_progress',conclusion=None)
    artifact['workflow_run']={'id':42,'head_sha':run['head_sha']}
    jobs={'jobs':[{'run_id':42,'name':'build / build-and-smoke','status':'completed','conclusion':'success'}]}
    files=preparer()(archive,artifact,release,run,tmp_path/'assets',build_jobs=jobs)
    assert len(files)==4


@pytest.mark.parametrize('case',['failed_job','pending_job','wrong_run','wrong_artifact','wrong_event'])
def test_version_workflow_requires_matching_successful_job(release_inputs,tmp_path,case):
    archive,artifact,release,run=release_inputs
    run.update(id=42,path='.github/workflows/version-release.yml',head_branch='main',event='workflow_dispatch',status='in_progress',conclusion=None)
    artifact['workflow_run']={'id':42,'head_sha':run['head_sha']}
    job={'run_id':42,'name':'build / build-and-smoke','status':'completed','conclusion':'success'}
    if case=='failed_job': job['conclusion']='failure'
    if case=='pending_job': job['status']='in_progress'
    if case=='wrong_run': job['run_id']=7
    if case=='wrong_artifact': artifact['workflow_run']['id']=7
    if case=='wrong_event': run['event']='pull_request'
    with pytest.raises(ValueError): preparer()(archive,artifact,release,run,tmp_path/'assets',build_jobs={'jobs':[job]})


def test_version_retry_selects_latest_build_attempt(release_inputs,tmp_path):
    archive,artifact,release,run=release_inputs
    run.update(id=42,path='.github/workflows/version-release.yml',head_branch='main',event='workflow_dispatch',status='in_progress',conclusion=None)
    artifact['workflow_run']={'id':42,'head_sha':run['head_sha']}
    jobs={'jobs':[{'id':1,'run_id':42,'name':'build / build-and-smoke','status':'completed','conclusion':'failure'}, {'id':2,'run_id':42,'name':'build / build-and-smoke','status':'completed','conclusion':'success'}]}
    assert len(preparer()(archive,artifact,release,run,tmp_path/'assets',build_jobs=jobs))==4
