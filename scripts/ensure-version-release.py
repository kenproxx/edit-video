"""Create or reuse a matching draft and preserve its authoritative metadata."""
import json
import os
from pathlib import Path
import re
import subprocess


def ensure_release(repo,tag,sha):
    if not re.fullmatch(r'v\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?',tag): raise ValueError('Invalid version')
    pages=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/releases','--paginate','--slurp']))
    release=next((r for page in pages for r in page if r['tag_name']==tag),None)
    refs=subprocess.run(['git','ls-remote','origin',f'refs/tags/{tag}',f'refs/tags/{tag}^{{}}'],check=True,capture_output=True,text=True).stdout.splitlines()
    if refs:
        resolved=next((line.split()[0] for line in refs if line.endswith('^{}')),refs[0].split()[0])
        if resolved!=sha: raise ValueError('Version tag points at a different commit')
    if release is None:
        payload={'tag_name':tag,'target_commitish':sha,'draft':True,'name':f'VideoEditor {tag}','body':'Verified Windows x64 EXE. Release remains draft pending the matching FFmpeg corresponding-source bundle.'}
        release=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/releases','--method','POST','--input','-'],input=json.dumps(payload).encode()))
    if release.get('tag_name')!=tag or not release.get('draft') or release.get('target_commitish')!=sha:
        raise ValueError('Release must be a matching draft')
    return release


if __name__=='__main__':
    release=ensure_release(os.environ['GITHUB_REPOSITORY'],os.environ['RELEASE_TAG'],os.environ['GITHUB_SHA'])
    Path('release.json').write_text(json.dumps(release),encoding='utf-8')
