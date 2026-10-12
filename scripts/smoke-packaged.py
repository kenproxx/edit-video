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
    audio=input_dir/'nhạc chèn.wav'
    run([args.ffmpeg.resolve(),'-v','error','-y','-f','lavfi','-i','sine=frequency=880:sample_rate=44100:duration=0.4',audio])
    silent=input_dir/'video im lặng.mp4'
    run([args.ffmpeg.resolve(),'-v','error','-y','-i',source,'-an','-c:v','copy',silent])
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
        # Exercise mixed export with independently measurable source/insert levels.
        mixed_dir=root/'trộn âm thanh';mixed_dir.mkdir(exist_ok=True)
        mix_report=root/'mix.json'
        run([exe,'--smoke-test',source,'--audio-file',audio,'--source-volume','25','--added-volume','60','--audio-loop','--output-dir',mixed_dir,'--report',mix_report],env=restricted,cwd=app_dir)
        mixed=json.loads(mix_report.read_text(encoding='utf-8'))
        assert mixed['ok'] and mixed['audio_codec']=='aac',mixed
        from array import array
        import math
        decoded=subprocess.check_output([str(args.ffmpeg.resolve()),'-v','error','-i',mixed['output'],'-vn','-ac','1','-ar','48000','-f','f32le','pipe:1'],timeout=30)
        values=array('f');values.frombytes(decoded)
        segment=values[48000:57600]
        def amplitude(frequency):
            real=sum(v*math.cos(2*math.pi*frequency*i/48000) for i,v in enumerate(segment))
            imag=sum(v*math.sin(2*math.pi*frequency*i/48000) for i,v in enumerate(segment))
            return 2*math.hypot(real,imag)/len(segment)
        assert abs(amplitude(440)-.03125)<.004
        assert abs(amplitude(880)-.075)<.004
        stereo=input_dir/'nhạc stereo.wav'
        run([args.ffmpeg.resolve(),'-v','error','-y','-f','lavfi','-i','aevalsrc=0.1*sin(2*PI*880*t)|-0.1*sin(2*PI*880*t):s=48000:d=0.4',stereo])
        stereo_dir=root/'stereo';stereo_dir.mkdir(exist_ok=True)
        stereo_report=root/'stereo.json'
        run([exe,'--smoke-test',source,'--audio-file',stereo,'--source-volume','0','--added-volume','50','--audio-loop','--output-dir',stereo_dir,'--report',stereo_report],env=restricted,cwd=app_dir)
        stereo_result=json.loads(stereo_report.read_text(encoding='utf-8'))
        assert stereo_result['ok'],stereo_result
        raw=subprocess.check_output([str(args.ffmpeg.resolve()),'-v','error','-i',stereo_result['output'],'-vn','-ac','2','-ar','48000','-f','f32le','pipe:1'],timeout=30)
        channels=array('f');channels.frombytes(raw)
        left,right=channels[::2],channels[1::2]
        assert max(abs(v) for v in left[48000:57600])>.04
        assert max(abs(v) for v in right[48000:57600])>.04
        assert max(abs(a+b) for a,b in zip(left[48000:57600],right[48000:57600]))<.002
        long_audio=input_dir/'nhạc dài.wav'
        run([args.ffmpeg.resolve(),'-v','error','-y','-f','lavfi','-i','sine=frequency=880:sample_rate=48000:duration=2',long_audio])
        limited_dir=root/'giới hạn nhạc';limited_dir.mkdir(exist_ok=True)
        limited_report=root/'limited.json'
        run([exe,'--smoke-test',silent,'--audio-file',long_audio,'--audio-duration','0.6','--output-dir',limited_dir,'--report',limited_report],env=restricted,cwd=app_dir)
        limited=json.loads(limited_report.read_text(encoding='utf-8'));assert limited['ok'],limited
        pcm=subprocess.check_output([str(args.ffmpeg.resolve()),'-v','error','-i',limited['output'],'-vn','-ac','1','-ar','48000','-f','f32le','pipe:1'],timeout=30)
        played_samples=array('f');played_samples.frombytes(pcm)
        assert max(abs(v) for v in played_samples[9600:19200])>.1
        assert max(abs(v) for v in played_samples[48000:57600])<.001
        inserted_play=root/'inserted-playback.json'
        run([exe,'--playback-smoke-test',silent,'--audio-file',audio,'--report',inserted_play],env=playback_env,cwd=app_dir)
        inserted=json.loads(inserted_play.read_text(encoding='utf-8'))
        assert inserted['ok'] and inserted['audio'] and inserted['frames']>=4,inserted
        failure=root/'collision.json'
        original=source.read_bytes()
        process=subprocess.run([str(exe),'--smoke-test',str(source),'--output-dir',str(input_dir),'--report',str(failure)],env=restricted,cwd=app_dir,timeout=30)
        assert process.returncode!=0 and not json.loads(failure.read_text(encoding='utf-8'))['ok']
        assert source.read_bytes()==original
        print('Packaged acceptance passed:',root)
    finally:
        run(['icacls',app_dir,'/grant:r',f'*{sid}:(OI)(CI)(F)'])


if __name__=='__main__': main()
