import os
import pytest
from edit_video.output import OutputTarget, validate_target, publish

def test_same_source_rejected(tmp_path):
    source=tmp_path/'source.mp4'; source.write_bytes(b'source')
    alias=tmp_path/'alias.mp4'; os.link(source,alias)
    for dest in (source,alias,source.parent/'.'/source.name):
        with pytest.raises(ValueError): validate_target(OutputTarget(source,dest,True))
    if os.name=='nt':
        with pytest.raises(ValueError): validate_target(OutputTarget(source,tmp_path/'SOURCE.mp4',True))

def test_existing_target_needs_consent(tmp_path):
    source=tmp_path/'source'; source.write_bytes(b'source')
    dest=tmp_path/'out'; dest.write_bytes(b'old')
    with pytest.raises(FileExistsError): validate_target(OutputTarget(source,dest,False))
    validate_target(OutputTarget(source,dest,True))

def test_publish_race_keeps_existing(tmp_path):
    source=tmp_path/'source'; source.write_bytes(b'source')
    temp=tmp_path/'temp'; temp.write_bytes(b'new')
    dest=tmp_path/'out'; target=OutputTarget(source,dest,False)
    validate_target(target); dest.write_bytes(b'other')
    with pytest.raises(FileExistsError): publish(temp,target)
    assert dest.read_bytes()==b'other'
