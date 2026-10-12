# Interactive Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans with preserved Native execution. Steps use checkbox syntax.

**Goal:** Source trim, direct manipulation of overlays/crop, embedded edited video playback.
**Architecture:** Shared FFmpeg pipeline with source interval; full-resolution paused canvas and temporary edited proxy for embedded playback. Native subprocess lifecycle, bounded frame queue and main-thread Tk updates.
**Tech Stack:** Existing Python/CustomTkinter/Pillow; bundled FFmpeg/ffprobe/ffplay, no extra runtime Python libraries.
**Spec:** docs/superpowers/specs/2026-10-12-interactive-video-design.md

## Global Constraints
- Keep input/output protection, no startup installation, Windows x64 EXE bundled dependencies.
- Source trim before speed; output timeline/intro use trimmed output duration.
- Playback proxy scales only after effects; export retains original configured resolution/quality.
- Full-resolution paused editing; discard obsolete render/decode events, stop native processes on close.

## Review Focus
- Trim intersects delayed/early audio or lies wholly before audio begins.
- Handle resize outside letterbox, crossing opposite edge, odd bounds and tiny regions.
- Text/transparent logo drag agrees with exported bounds after crop/speed/trim.
- Seek/edit/close during proxy preparation or playback never leaves stale frames/processes.
- Frozen ffplay resolution/Windows no-window audio launch, no end-user install.

### Task 1: Source trim and geometry model
Files app/models.py app/render.py app/overlays.py app/timing.py tests/test_trim.py tests/test_models.py.
Interfaces EditOptions adds trim_start=0,trim_end=None; trimmed_duration(options,duration) validates interval; LogoOverlay height=None; parse_time(value) accepts mm:ss/hh:mm:ss or decimal minutes.
- [ ] Write validation/format tests and real FFmpeg source interval, speed, preview/intro and early/delayed audio tests; run RED.
- [ ] Implement interval filters with video/audio origin preserved, independent logo height backwards compatible; run GREEN.
- [ ] Commit task model/engine.

### Task 2: Canvas handles and trim controls
Files app/geometry.py app/ui_canvas.py app/ui_options.py app/ui.py tests/test_ui.py tests/test_geometry.py.
Interfaces resize_region(original,handle,dx,dy,bounds,even=False)->Rect; move_region(original,dx,dy,bounds,even=False)->Rect. Canvas selected callback supports Rect for overlay and legacy point; set_overlay(image,Rect) gives live dragged item. UI updates options once per release, crop/flip dependencies remain explicit.
- [ ] Write drag/move/each-handle, bounds/letterbox, actual overlay placement and trim field GUI tests; run RED.
- [ ] Implement visible eight handles, live overlay feedback and optional numeric fields; add trim UI/timeline clipped duration; run GREEN.
- [ ] Commit direct manipulation UI.

### Task 3: Embedded proxy playback and bundle
Files app/playback.py app/render.py app/worker.py app/resources.py app/ui.py scripts/bootstrap-build.ps1 VideoEditor.spec scripts/smoke-packaged.py tests/test_playback.py tests/test_ui.py.
Interfaces prepare_render(...,preview=False), preview_size(info,options); worker.start(...,preview=False). PlaybackController prepare,play(time),pause,invalidate,poll,close; busy/playing/ready; events progress/ready/frame/error/completed carrying generation.
- [ ] Write actual render/decode playback, stale/edit/seek/close, bounded frame/audio lifecycle and GUI play/pause tests; run RED.
- [ ] Implement edited proxy, bounded decoder/audio subprocesses, main-thread playback controls; bundle ffplay; run GREEN.
- [ ] Full suite, fresh Native reviewer, one fix pass with RED/GREEN, update docs and commit. Confirm Windows build/acceptance through CI before claiming EXE validated.
