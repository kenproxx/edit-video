"""Source and packaged entry point; startup never installs dependencies."""
import argparse
import json
from pathlib import Path
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Video Editor')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--smoke-test',type=Path,metavar='INPUT',help='Export with bundled tools without opening the GUI')
    modes.add_argument('--batch-smoke-test',type=Path,metavar='FOLDER',help='Exercise folder export with shared scaled options')
    modes.add_argument('--gui-smoke-test',action='store_true',help='Open and close the native GUI')
    modes.add_argument('--playback-smoke-test',type=Path,metavar='INPUT',help='Exercise embedded playback, trim, pause and seek')
    parser.add_argument('--audio-file',type=Path,help='Inserted audio for export/playback smoke checks')
    parser.add_argument('--source-volume',type=float,default=100,help='Original audio volume percent (0–200)')
    parser.add_argument('--added-volume',type=float,default=100,help='Inserted audio volume percent (0–200)')
    audio_mode=parser.add_mutually_exclusive_group()
    audio_mode.add_argument('--audio-loop',action='store_true',help='Loop inserted audio until its duration limit or video end')
    audio_mode.add_argument('--audio-once',action='store_true',help='Play inserted audio once (default)')
    parser.add_argument('--audio-duration',type=float,help='Maximum inserted audio playback seconds')
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--report',type=Path,help='JSON result file (required for packaged smoke tests)')
    args = parser.parse_args(argv)
    if (args.smoke_test is not None or args.batch_smoke_test is not None) and args.output_dir is None: parser.error('--smoke-test requires --output-dir')
    if args.batch_smoke_test is not None or args.smoke_test is not None or args.gui_smoke_test or args.playback_smoke_test is not None:
        report = None
        try:
            if args.report is not None:
                if args.batch_smoke_test is not None:
                    from app.batch import scan_videos,plan_batch
                    jobs=plan_batch(scan_videos(args.batch_smoke_test),args.output_dir)
                    if any(args.report.resolve()==job.destination.resolve() for job in jobs):
                        raise ValueError('Report không được trùng video đầu ra hàng loạt')
                if args.smoke_test is not None:
                    output = args.output_dir / (args.smoke_test.stem + '.mp4')
                    if args.report.resolve() == output.resolve():
                        raise ValueError('Report không được trùng file video đầu ra')
                # Reserve before any work; exclusive creation protects input,
                # existing reports, symlinks and concurrent file creation.
                report = args.report.open('x',encoding='utf-8')
            if args.batch_smoke_test is not None:
                from app.selftest import smoke_batch
                result=smoke_batch(args.batch_smoke_test,args.output_dir)
            elif args.smoke_test is not None:
                from app.selftest import smoke_export
                from app.models import EditOptions
                options=EditOptions(source_volume=args.source_volume/100,audio_path=args.audio_file,added_volume=args.added_volume/100,audio_loop=args.audio_loop,audio_duration=args.audio_duration)
                result = smoke_export(args.smoke_test,args.output_dir,options=options)
            elif args.playback_smoke_test is not None:
                from app.selftest import smoke_embedded_playback
                result = smoke_embedded_playback(args.playback_smoke_test,args.audio_file)
            else:
                from app.ui import VideoEditorApp
                app = VideoEditorApp()
                app.after(500,app.request_close)
                app.mainloop()
                result = {'ok':True,'gui':True}
            code = 0
        except Exception as exc:
            result = {'ok':False,'error':str(exc)}
            code = 1
        text = json.dumps(result,ensure_ascii=False,indent=2)
        if report is not None:
            with report:
                report.write(text+'\n')
        if sys.stdout is not None: print(text)
        return code
    from app.ui import VideoEditorApp
    app = VideoEditorApp()
    app.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
