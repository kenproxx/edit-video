"""Validate tools and collect full license texts before PyInstaller runs."""
import argparse
from importlib.metadata import distribution, distributions
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def collect_wheel_licenses(destination: Path, names=None) -> None:
    selected = [distribution(name) for name in names] if names else list(distributions())
    for dist in selected:
        found = False
        for file in dist.files or ():
            # Only distribution metadata; avoid modules named "licenses".
            text = str(file).lower()
            if '.dist-info/' not in text or not any(token in Path(text).name for token in ('license','copying','notice','authors')):
                continue
            source = Path(dist.locate_file(file))
            if not source.is_file(): continue
            relative = Path(*Path(file).parts[1:])
            target = destination/dist.metadata['Name']/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
            found = True
        if not found: raise ValueError('Missing full license text: '+dist.metadata['Name'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--licenses',type=Path,required=True)
    args = parser.parse_args()
    from app.selftest import verify_media_tools
    versions = verify_media_tools()
    print(versions)
    manifest = ROOT/'scripts/build-manifest.json'
    import json
    expected = json.loads(manifest.read_text())['ffmpeg']['version']
    if expected not in versions['ffmpeg']: raise ValueError('FFmpeg version mismatch')
    collect_wheel_licenses(args.licenses)
    python_license = Path(sys.base_prefix)/'LICENSE.txt'
    if not python_license.is_file(): raise ValueError('Missing Python/Tcl/Tk license text')
    target = args.licenses/'python';target.mkdir(exist_ok=True)
    shutil.copy2(python_license,target/'LICENSE.txt')
    for name in ('tcl8.6','tk8.6'):
        source = Path(sys.base_prefix)/'tcl'/name/'license.terms'
        if source.is_file(): shutil.copy2(source,target/(name+'-license.terms'))
    import customtkinter
    assets = Path(customtkinter.__file__).parent/'assets'
    for source in assets.rglob('*'):
        if source.is_file() and any(token in source.name.lower() for token in ('license','copying','notice')):
            target = args.licenses/'customtkinter-assets'/source.relative_to(assets)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)


if __name__ == '__main__': main()
