import os
from pathlib import Path
import pytest
from app.output import reserve_output, publish_output


def test_source_aliases_rejected(tmp_path):
    source=tmp_path/'source.mp4'; source.write_bytes(b'input')
    for target in (source,tmp_path/'link.mp4',tmp_path/'symlink.mp4'):
        if target.name=='link.mp4': os.link(source,target)
        if target.name=='symlink.mp4': target.symlink_to(source)
        with pytest.raises(ValueError): reserve_output(source,target,True)
    assert source.read_bytes()==b'input'


def test_overwrite_consent_and_success(tmp_path):
    source=tmp_path/'input.mp4'; source.write_bytes(b'input')
    target=tmp_path/'out.mp4'; target.write_bytes(b'old')
    temp=tmp_path/'temp.mp4'; temp.write_bytes(b'new')
    with pytest.raises(FileExistsError): reserve_output(source,target,False)
    reservation=reserve_output(source,target,True)
    publish_output(temp,reservation)
    assert target.read_bytes()==b'new'
    assert source.read_bytes()==b'input'
    assert not temp.exists()
    assert not list(tmp_path.glob('.videoeditor-*'))


@pytest.mark.parametrize('existing',[False,True])
def test_changed_destination_preserved(tmp_path,existing):
    source=tmp_path/'source.mp4'; source.write_bytes(b'input')
    target=tmp_path/'out.mp4'
    if existing: target.write_bytes(b'old')
    reservation=reserve_output(source,target,existing)
    target.write_bytes(b'external change')
    temp=tmp_path/'temp.mp4'; temp.write_bytes(b'new')
    with pytest.raises(FileExistsError): publish_output(temp,reservation)
    assert target.read_bytes()==b'external change'


def test_conflict_at_atomic_publish_preserves_new_file(tmp_path,monkeypatch):
    source=tmp_path/'input.mp4'; source.write_bytes(b'input')
    target=tmp_path/'out.mp4'; target.write_bytes(b'old')
    reservation=reserve_output(source,target,True)
    temp=tmp_path/'temp.mp4'; temp.write_bytes(b'new')
    original_link=os.link
    def create_conflict(src,dst,*args,**kwargs):
        if Path(src)==temp and Path(dst)==target:
            target.write_bytes(b'new external file')
        return original_link(src,dst,*args,**kwargs)
    monkeypatch.setattr(os,'link',create_conflict)
    with pytest.raises(FileExistsError): publish_output(temp,reservation)
    assert target.read_bytes()==b'new external file'
    backups=list(tmp_path.glob('.videoeditor-backup-*'))
    assert len(backups)==1 and backups[0].read_bytes()==b'old'


def test_invalid_name_and_missing_folder(tmp_path):
    source=tmp_path/'in.mp4'; source.write_bytes(b'x')
    for target in [tmp_path/'missing'/'out.mp4',tmp_path/'out.mkv']:
        with pytest.raises(ValueError): reserve_output(source,target,False)


def test_publish_failure_restores_old_target(tmp_path,monkeypatch):
    source=tmp_path/'in.mp4'; source.write_bytes(b'input')
    target=tmp_path/'out.mp4'; target.write_bytes(b'old')
    temp=tmp_path/'temp.mp4'; temp.write_bytes(b'new')
    reservation=reserve_output(source,target,True)
    original=os.link
    def unsupported(src,dst):
        if Path(src)==temp: raise OSError('Filesystem does not support links')
        return original(src,dst)
    monkeypatch.setattr(os,'link',unsupported)
    with pytest.raises(OSError): publish_output(temp,reservation)
    assert target.read_bytes()==b'old'
    assert not list(tmp_path.glob('.videoeditor-*'))


def test_changed_during_backup_move_is_restored(tmp_path,monkeypatch):
    source=tmp_path/'in.mp4'; source.write_bytes(b'input')
    target=tmp_path/'out.mp4'; target.write_bytes(b'old')
    temp=tmp_path/'temp.mp4'; temp.write_bytes(b'new')
    reservation=reserve_output(source,target,True)
    original=os.replace
    def replace_with_conflict(src,dst):
        target.write_bytes(b'changed in race')
        return original(src,dst)
    monkeypatch.setattr(os,'replace',replace_with_conflict)
    with pytest.raises(FileExistsError): publish_output(temp,reservation)
    assert target.read_bytes()==b'changed in race'
    assert not list(tmp_path.glob('.videoeditor-*'))


def test_unsupported_hardlinks_fail_without_moving_destination(tmp_path,monkeypatch):
    source=tmp_path/'in.mp4'; source.write_bytes(b'input')
    target=tmp_path/'out.mp4'; target.write_bytes(b'old')
    temp=tmp_path/'temp.mp4'; temp.write_bytes(b'new')
    reservation=reserve_output(source,target,True)
    def unsupported(*args,**kwargs):
        import errno
        raise OSError(errno.EOPNOTSUPP,'No hardlinks')
    monkeypatch.setattr(os,'link',unsupported)
    # A safe implementation may use another atomic no-replace operation.
    try:
        publish_output(temp,reservation)
    except OSError:
        assert target.read_bytes()==b'old'
    else:
        assert target.read_bytes()==b'new'
    assert not list(tmp_path.glob('.videoeditor-*'))
