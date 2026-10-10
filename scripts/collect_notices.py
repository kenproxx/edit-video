from importlib import metadata
from pathlib import Path
import os
import shutil
out=Path('.build/licenses'); out.mkdir(parents=True,exist_ok=True)
for dist in metadata.distributions():
    name=dist.metadata['Name']
    for file in dist.files or []:
        if any(word in str(file).lower() for word in ('license','copying','notice')):
            source=Path(dist.locate_file(file))
            if source.is_file():
                dest=out/name/str(file).replace('..','_')
                dest.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(source,dest)
for source in (Path('.build/python/tools/LICENSE.txt'),Path(os.environ['EDIT_VIDEO_FFMPEG_DIR']).parent/'LICENSE',Path(os.environ['EDIT_VIDEO_FFMPEG_DIR']).parent/'README.txt'):
    if not source.is_file(): raise FileNotFoundError(f'Missing third-party notice: {source}')
    shutil.copyfile(source,out/(source.parent.name+'-'+source.name))
