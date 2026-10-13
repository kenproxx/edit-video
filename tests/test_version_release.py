"""GitHub boundary: preserve authoritative creation response, avoid stale relists."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest


def module():
    path=Path(__file__).resolve().parents[1]/'scripts/ensure-version-release.py'
    assert path.is_file(),'Version release metadata helper missing'
    spec=importlib.util.spec_from_file_location('ensure_version_release',path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def test_created_draft_metadata_used_without_second_list(monkeypatch):
    helper=module();sha='a'*40;created={'id':12,'tag_name':'v0.2.1','draft':True,'target_commitish':sha};calls=[]
    def gh(args,**kwargs):
        calls.append(args)
        if '--slurp' in args: return b'[[]]'
        assert '--method' in args and 'POST' in args
        payload=json.loads(kwargs['input']);assert payload['draft'] and payload['target_commitish']==sha
        return json.dumps(created).encode()
    monkeypatch.setattr(helper.subprocess,'check_output',gh)
    monkeypatch.setattr(helper.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout=sha+'\trefs/tags/v0.2.1\n'))
    assert helper.ensure_release('owner/repo','v0.2.1',sha)==created
    assert len(calls)==2


@pytest.mark.parametrize('case',['matching','published','different_commit'])
def test_existing_release_retained_or_rejected_without_creation(monkeypatch,case):
    helper=module();sha='a'*40;release={'id':12,'tag_name':'v0.2.1','draft':case!='published','target_commitish':'b'*40 if case=='different_commit' else sha}
    def gh(args,**kwargs):
        assert '--slurp' in args
        return json.dumps([[release]]).encode()
    monkeypatch.setattr(helper.subprocess,'check_output',gh)
    monkeypatch.setattr(helper.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout=sha+'\trefs/tags/v0.2.1\n'))
    if case=='matching': assert helper.ensure_release('owner/repo','v0.2.1',sha)==release
    else:
        with pytest.raises(ValueError): helper.ensure_release('owner/repo','v0.2.1',sha)
