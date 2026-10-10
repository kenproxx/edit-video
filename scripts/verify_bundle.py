import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

bundle=Path(sys.argv[1]).resolve()
for relative in ('EditVideo.exe','_internal/bin/ffmpeg.exe','_internal/bin/ffprobe.exe','_internal/licenses','_internal/THIRD_PARTY_NOTICES.md'):
    if not (bundle/relative).exists():raise SystemExit(f'Missing bundle component: {relative}')
env=os.environ.copy()
env['PATH']=os.path.join(env.get('SystemRoot','C:\\Windows'),'System32')
env.pop('EDIT_VIDEO_FFMPEG_DIR',None); env.pop('PYTHONPATH',None); env.pop('PYTHONHOME',None)
env['QT_QPA_PLATFORM']='offscreen'
with tempfile.TemporaryDirectory(prefix='edit-video-smoke-') as folder:
    result=subprocess.run([str(bundle/'EditVideo.exe'),'--self-test',folder],env=env,timeout=90)
    report=json.loads((Path(folder)/'self-test.json').read_text(encoding='utf-8'))
    if result.returncode or not report['success']:raise SystemExit(str(report))
    for name in ('ffmpeg','ffprobe'):
        if not Path(report[name]).is_relative_to(bundle):raise SystemExit('External binary used')
    (bundle/'self-test.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Portable bundle smoke test passed without external Python/FFmpeg in PATH.')
