"""Windows acceptance test of the actual EXE, with no Python/FFmpeg on PATH."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def run(args,**kwargs):
    return subprocess.run([str(a) for a in args],check=True,timeout=180,**kwargs)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--exe',type=Path,required=True)
    parser.add_argument('--ffmpeg',type=Path,required=True)
    parser.add_argument('--work-dir',type=Path)
    args=parser.parse_args()
    if os.name!='nt': parser.error('Packaged acceptance requires native Windows')
    root=args.work_dir or Path(tempfile.mkdtemp(prefix='VideoEditor-acceptance-'))
    root=root.resolve();root.mkdir(parents=True,exist_ok=True)
    app_dir=root/'readonly-app';app_dir.mkdir(exist_ok=True)
    exe=app_dir/'VideoEditor.exe';shutil.copy2(args.exe,exe)
    input_dir=root/'đầu vào';input_dir.mkdir(exist_ok=True)
    output_dir=root/'kết quả';output_dir.mkdir(exist_ok=True)
    source=input_dir/'đầu video.mp4'
    run([args.ffmpeg.resolve(),'-v','error','-y','-f','lavfi','-i','testsrc2=size=320x240:rate=30','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','2','-c:v','libx264','-threads','2','-pix_fmt','yuv420p','-c:a','aac',source])
    restricted=os.environ.copy()
    restricted['PATH']=str(Path(os.environ['SystemRoot'])/'System32')
    restricted['LOCALAPPDATA']=str(root/'user-data')
    if shutil.which('ffmpeg',path=restricted['PATH']) or shutil.which('python',path=restricted['PATH']):
        raise RuntimeError('Acceptance PATH unexpectedly supplies Python/FFmpeg')
    sid=subprocess.check_output(['whoami','/user','/fo','csv','/nh'],text=True).strip().split(',')[-1].strip('"')
    run(['icacls',app_dir,'/inheritance:r','/grant:r',f'*{sid}:(OI)(CI)(RX)'])
    try:
        report=root/'export.json'
        run([exe,'--smoke-test',source,'--output-dir',output_dir,'--report',report],env=restricted,cwd=app_dir)
        result=json.loads(report.read_text(encoding='utf-8'))
        assert result['ok'] and result['video_codec']=='h264' and result['audio_codec']=='aac',result
        assert (result['width'],result['height'])==(320,240) and abs(result['duration']-2)<.15,result
        assert (output_dir/source.name).is_file()
        gui=root/'gui.json'
        run([exe,'--gui-smoke-test','--report',gui],env=restricted,cwd=app_dir)
        assert json.loads(gui.read_text(encoding='utf-8'))=={'ok':True,'gui':True}
        playback=root/'playback.json'
        playback_env=restricted.copy();playback_env['SDL_AUDIODRIVER']='dummy'
        run([exe,'--playback-smoke-test',source,'--report',playback],env=playback_env,cwd=app_dir)
        played=json.loads(playback.read_text(encoding='utf-8'))
        assert played['ok'] and played['playback'] and played['frames']>=4 and played['audio'],played
        assert abs(played['duration']-1)<.04,played
        failure=root/'collision.json'
        original=source.read_bytes()
        process=subprocess.run([str(exe),'--smoke-test',str(source),'--output-dir',str(input_dir),'--report',str(failure)],env=restricted,cwd=app_dir,timeout=30)
        assert process.returncode!=0 and not json.loads(failure.read_text(encoding='utf-8'))['ok']
        assert source.read_bytes()==original
        print('Packaged acceptance passed:',root)
    finally:
        run(['icacls',app_dir,'/grant:r',f'*{sid}:(OI)(CI)(F)'])


if __name__=='__main__': main()
