"""Prepare assets from a successful main build for an existing DRAFT release."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import zipfile


def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()


def prepare_release(archive,artifact,release,run,output):
    if not release.get('draft'): raise ValueError('Only a draft release may receive these assets')
    tag=release['tag_name']
    if not re.fullmatch(r'v\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?',tag): raise ValueError('Invalid release version')
    if run.get('status')!='completed' or run.get('conclusion')!='success' or run.get('head_branch')!='main' or run.get('path')!='.github/workflows/windows-build.yml':
        raise ValueError('Release requires a successful Windows build from main')
    if run.get('head_sha')!=release.get('target_commitish'): raise ValueError('Release commit does not match tested build')
    if artifact.get('name')!='VideoEditor-windows-x64' or artifact.get('expired'): raise ValueError('Wrong or expired build artifact')
    if artifact.get('digest')!='sha256:'+digest(archive): raise ValueError('GitHub artifact SHA256 mismatch')
    # Validate in private scratch before writing any release output.
    with tempfile.TemporaryDirectory(prefix='videoeditor-release-') as scratch:
        root=Path(scratch)
        with zipfile.ZipFile(archive) as z:
            names=z.namelist()
            if len(names)!=len(set(names)): raise ValueError('Duplicate archive entries')
            for name in names:
                if not (root/name).resolve().is_relative_to(root): raise ValueError('Unsafe artifact path')
            z.extractall(root)
        exe=root/'VideoEditor.exe'
        expected=(root/'VideoEditor.exe.sha256').read_text(encoding='utf-8-sig').split()[0]
        if digest(exe)!=expected: raise ValueError('Executable SHA256 mismatch')
        with exe.open('rb') as stream:
            header=stream.read(64)
            if header[:2]!=b'MZ': raise ValueError('Not a Windows executable')
            stream.seek(int.from_bytes(header[60:64],'little'))
            pe=stream.read(6)
            if pe!=b'PE\0\0\x64\x86': raise ValueError('Executable is not Windows x64')
        notices=root/'THIRD_PARTY_NOTICES.md'
        if not notices.is_file() or not (root/'licenses/ffmpeg/LICENSE').is_file(): raise ValueError('Missing distribution notices/licenses')
        output.mkdir(exist_ok=False)
        exe_out=output/'VideoEditor.exe';shutil.copy2(exe,exe_out)
        zip_out=output/f'VideoEditor-windows-x64-{tag}.zip';shutil.copy2(archive,zip_out)
        notices_out=output/notices.name;shutil.copy2(notices,notices_out)
        sums=output/'SHA256SUMS.txt'
        sums.write_text(''.join(digest(p)+'  '+p.name+'\n' for p in (exe_out,zip_out)),encoding='utf-8')
        return [exe_out,zip_out,sums,notices_out]


def main():
    parser=argparse.ArgumentParser()
    for name in ('archive','artifact-json','release-json','run-json','output-dir'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    files=prepare_release(args.archive,json.loads(args.artifact_json.read_text()),json.loads(args.release_json.read_text()),json.loads(args.run_json.read_text()),args.output_dir)
    (args.output_dir/'upload-files.json').write_text(json.dumps([str(p.resolve()) for p in files]),encoding='utf-8')
    print('Verified release assets prepared:',args.output_dir)


if __name__=='__main__': main()
