# Video Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** App Python chỉnh video bằng GUI và Windows EXE chạy offline, không cài dependencies riêng.

**Architecture:** CustomTkinter dùng model cấu hình chung cho preview và render FFmpeg. Worker nền giao tiếp bằng event queue; bootstrap Windows chuẩn bị Python và binaries rồi đóng gói PyInstaller.

**Tech Stack:** Python 3.12, CustomTkinter, Pillow, FFmpeg/ffprobe, pytest, PyInstaller; khóa phiên bản cụ thể trong task liên quan.

**Spec:** `docs/superpowers/specs/2026-10-11-video-editor-design.md`

## Global Constraints

- Windows 10/11 x64; một video mỗi lần, không batch/timeline/GPU.
- Tốc độ 0.25–4; text đầu mặc định 1 giây theo thời gian đầu ra.
- MP4 H.264/AAC, CRF 20/preset medium, yuv420p, faststart; video/audio stream đầu tiên.
- Thứ tự orientation → lật → crop → tốc độ → blur → watermark → text đầu.
- Không ghi đè input; tên mặc định thân input + `.mp4`; file tạm chỉ thay thế đích sau thành công và kiểm tra xung đột.
- Dependencies/binaries bundled; TLS/hash verification; không cài dependency khi chạy EXE.
- GUI tiếng Việt; crop 9:16, 16:9, 1:1; một blur, một logo, một text watermark.
- Dùng checkout cloud hiện tại; không tạo worktree. Không push/publish release.

## Review Focus

- Video điện thoại có rotation và SAR khác 1: preview và tọa độ theo ảnh hiển thị thực (task 2).
- Tên Unicode, dấu nháy, dấu hai chấm: không lỗi filter hoặc command injection (task 3).
- Đích xuất xuất hiện/thay đổi trong lúc render: giữ file mới và không tự ghi đè (task 4).
- Preview cũ hoàn tất sau preview mới: kết quả cũ không thay màn hình (task 5).
- EXE chạy trong thư mục chỉ đọc: log/overlay dùng thư mục user, không cần admin (task 6).

## Phase 2 — engine

### Task 1: Cấu hình và kiểm tra đầu vào

**Files:** `app/__init__.py`, `app/models.py`, `app/geometry.py`, `requirements.txt`, `requirements-dev.txt`, `.gitignore`, `tests/test_models.py`, `tests/test_geometry.py`.

**Interfaces:** Produces frozen dataclasses `Rect(x:int,y:int,width:int,height:int)`, `TextOverlay(text:str,font:Path,size:int,color:str,stroke_color:str,stroke_width:int,x:int,y:int,opacity:float)`, `LogoOverlay(path:Path,x:int,y:int,width:int,opacity:float)`, `EditOptions(speed:float=1,flip_horizontal:bool=False,flip_vertical:bool=False,crop:Rect|None=None,blur:Rect|None=None,blur_strength:int=10,logo:LogoOverlay|None=None,watermark:TextOverlay|None=None,intro:TextOverlay|None=None,intro_duration:float=1)`. `validate_options(options:EditOptions,width:int,height:int,duration:float)->None` raises `ValueError`; `default_output(input_path:Path,directory:Path)->Path`; `canvas_to_pixel(x:float,y:float,image_box:Rect,image_size:tuple[int,int])->tuple[int,int]|None`; `preset_crop(width:int,height:int,ratio:tuple[int,int])->Rect`.

- [ ] Write parameterized tests: speed endpoints accepted/outside rejected; invalid/odd/out-of-bounds regions rejected or explicitly normalized to even encoder dimensions; intro cannot exceed duration/speed; assets/fonts checked; empty text optional; output `đầu.mov` → `đầu.mp4`; letterbox click returns None, center maps to image center; presets retain ratio and fit bounds.
- [ ] Run `python -m pytest tests/test_models.py tests/test_geometry.py -q`; confirm failures from absent implementation.
- [ ] Implement signatures above; pin runtime/dev dependencies compatible with Python 3.12, ignore venv/build/generated media. Keep model independent of Tk.
- [ ] Run same tests; all cases pass. Commit `feat: add edit configuration and geometry validation`.

### Task 2: Binaries, probe và orientation

**Files:** `app/resources.py`, `app/media.py`, `tests/conftest.py`, `tests/test_media.py`, `scripts/setup-dev.sh`.

**Interfaces:** Consumes Rect. Produces `MediaInfo(width:int,height:int,duration:float,fps:float,has_audio:bool,rotation:int,is_hdr:bool)`, `binary_path(name:str)->Path`, `user_data_dir()->Path`, `probe(path:Path)->MediaInfo`, `extract_source_frame(path:Path,time:float,destination:Path)->Path`. Width/height are display-oriented square pixels. Renderer must use the same FFmpeg autorotation/SAR normalization and metadata policy as probe.

- [ ] Create FFmpeg synthetic SDR fixtures with colored quadrants, sine audio, silent version, rotation metadata, non-square SAR, HDR metadata and malformed file. Assert display dimensions/rotation, fps fallback, audio detection, HDR rejection before rendering and frame corner orientation.
- [ ] Run `python -m pytest tests/test_media.py -q`; confirm meaningful failures (missing tools is prerequisite failure, not success/skip).
- [ ] Implement probe via ffprobe JSON with timeout and useful errors, binary lookup preferring bundled `tools/` under frozen resource root. Setup dev venv and system FFmpeg with supported package tools; never disable verification. Use inherited cloud network/CA settings.
- [ ] Run tests with real FFmpeg; record fixture counts and commit `feat: probe media and normalize preview orientation`.

### Task 3: Filter graph và preview

**Files:** `app/overlays.py`, `app/render.py`, `tests/test_filters.py`, `tests/test_effects.py`.

**Interfaces:** Consumes task 1/2 types. Produces `PreparedRender(args:list[str],duration:float)`, `prepare_render(source:Path,info:MediaInfo,options:EditOptions,destination:Path,workspace:Path)->PreparedRender`, `render_preview(source:Path,info:MediaInfo,options:EditOptions,time:float,destination:Path)->Path`. Time is output timeline. Workspace owns generated overlays; preview uses the same filter builder, retains source temporal mapping and returns post-edit image.

- [ ] Write unit tests asserting filter order, atempo chaining for 0.25/4, optional audio mapping and exact encoding settings. Integration tests assert duration within one output frame plus audio encoder tolerance; preserved sine pitch within 2%; crop dimensions and quadrant flip; blur reduces local variance without changing distant region; logo alpha blend; Vietnamese multiline text visible at 0.5s and absent after intro duration. Test Unicode/quotes/colon filenames and text, silent clip and preview frame matching decoded render within lossy tolerance.
- [ ] Run `python -m pytest tests/test_filters.py tests/test_effects.py -q`; verify failures before implementation.
- [ ] Implement rasterized text PNG with Pillow, logo scaling/opacity, fixed blur filter, timestamps and encoding. Pass subprocess args as lists; use safe temporary relative names for filter assets and no user strings embedded in graph. Strip output rotation/subtitle/private metadata. Validate before spawning.
- [ ] Run tests with actual outputs inspected via ffprobe/frame sampling/audio analysis; commit `feat: render video edits and matching previews`.

### Task 4: Xuất an toàn và worker

**Files:** `app/output.py`, `app/worker.py`, `tests/test_output.py`, `tests/test_worker.py`.

**Interfaces:** Consumes prepare_render. Produces `OutputReservation` capturing destination identity/existence and overwrite consent; `reserve_output(source:Path,destination:Path,overwrite:bool)->OutputReservation`; `RenderWorker.start(source:Path,info:MediaInfo,options:EditOptions,reservation:OutputReservation)->None`, `.cancel()->None`, `.poll()->list[WorkerEvent]`, `.running:bool`; `WorkerEvent(kind:str,progress:float|None=None,message:str='',output:Path|None=None)`. Kinds progress/completed/cancelled/error. Output helper publishes only against unchanged reservation; use supported atomic commit/locking rather than treating a non-atomic existence check as race protection.

- [ ] Tests reject source aliases (resolved path, Windows case, symlink/hardlink where available), require overwrite consent, preserve existing bytes after encoder failure/hủy. Inject destination appearing/changing during render; assert conflict preserves it. Verify actual cancellation terminates FFmpeg, cleanup removes only job files, one job maximum and progress event memory bounded under flood.
- [ ] Run `python -m pytest tests/test_output.py tests/test_worker.py -q`; verify failures.
- [ ] Implement same-directory unique MP4 temp, destination reservation and safe publish, bounded progress coalescing, stderr diagnostic tail/log and termination timeout. Use runtime user directory for overlays/log, output directory for video temp. Report permission/space/process errors distinctly.
- [ ] Run tests plus phase 2 full `python -m pytest -q`; commit `feat: export safely with cancellable background worker`. Report phase 2 evidence.

## Phase 3 — GUI

### Task 5: Form, canvas và điều phối preview

**Files:** `main.py`, `app/ui.py`, `app/ui_options.py`, `app/preview.py`, `tests/test_preview.py`, `tests/test_ui.py`.

**Interfaces:** Consumes all phase 2 interfaces. Produces `VideoEditorApp` CustomTkinter root, `OptionsPanel.read_options()->EditOptions`, `PreviewController.request(source:Path,info:MediaInfo,options:EditOptions,time:float)->int`, `.poll()->list[PreviewResult]`, `.close()->None`; generation IDs reject stale completion. Canvas uses task 1 geometry; crop selection uses source-after-flip view, other selections post-crop view.

- [ ] Tests cover file chooser/name default, folder and validation, each feature reaching EditOptions, presets/drag mapping under resized letterboxing, crop/lật change invalidating dependent selections, text defaults, logo/font picker, overwrite/input protection, worker event progress/cancel/error. Force preview completion out of order and assert newest generation remains displayed; ensure UI updates only main thread and controls remain available at narrow size. Display-dependent tests explicitly report unavailable display as unrun, never validated.
- [ ] Run controller tests and GUI tests with `xvfb-run -a python -m pytest tests/test_preview.py tests/test_ui.py -q` on Linux (or native Windows display); confirm expected red tests.
- [ ] Implement Vietnamese scrolling option groups, preview timeline, crop/blur/text/logo selections and numeric fallback controls. Debounce preview, disable conflicting controls during render, keep cancel/progress fixed, prevent close leaving child process. Startup does not install packages.
- [ ] Run full tests plus interactive or automated GUI smoke: select fixture, preview all edits, export, cancel, reopen. Commit `feat: add Vietnamese desktop video editor`. Report phase 3 evidence.

## Phase 4 — build và bàn giao

### Task 6: Bootstrap Windows và EXE

**Files:** `build.bat`, `build.sh`, `scripts/bootstrap-build.ps1`, `scripts/build-manifest.json`, `VideoEditor.spec`, `scripts/smoke-packaged.py`, `tests/test_packaging.py`, `.github/workflows/windows-build.yml`, `README.md`, `THIRD_PARTY_NOTICES.md`.

**Interfaces:** Entry points build.bat/build.sh → bootstrap-build.ps1 → isolated Python/build dependencies → PyInstaller → `dist/VideoEditor.exe`. Manifest pins Python installer and Windows FFmpeg archive versions, official URLs and authoritative checksums; manifest is non-secret. `main.py --smoke-test INPUT --output-dir DIR` exercises probe/render without opening GUI, then exits nonzero on failure; default launch opens GUI.

- [ ] Write packaging tests for frozen resource lookup, missing/corrupt tools, user resource location when install directory is read-only, explicit non-Windows rejection and startup without pip. Windows bootstrap negative test tampers cached download and expects hash rejection. Packaged smoke asserts output codec/duration and runs GUI startup/close separately.
- [ ] Run `python -m pytest tests/test_packaging.py -q`; verify red tests. Obtain version/hash/license metadata from authoritative release sources; do not invent checksums or bypass blocked domains.
- [ ] Implement signed Python per-user private bootstrap when matching Python unavailable, venv installation and integrity-verified FFmpeg/ffprobe bundle (libx264/AAC, required filters). Build script must fail on every failed download/install/build; repeat invocation reuses only verified artifacts. Include CustomTkinter resources and distribution licenses. build.sh requires Windows Git Bash and invokes PowerShell, reports Linux limitation explicitly. Add Windows CI artifact build/smoke without release publishing.
- [ ] Document offline EXE usage, source setup, effects coordinates/preview limitations, build commands, third-party licenses and phase validation. Do not claim unfinished platform tests passed.
- [ ] Run Linux full suite. On Windows without Python/FFmpeg on PATH run bootstrap twice; verify both builds, run EXE smoke with restricted PATH, Unicode paths and read-only app directory, launch GUI and export synthetic fixture. Inspect bundled licenses. If Windows executor unavailable, report Windows build/EXE checks unrun and keep that deliverable pending; do not substitute Linux PyInstaller output.
- [ ] Commit `build: bootstrap and package standalone Windows editor`; report final test counts, EXE location if actually built, and remaining platform limitations. Obtain whole-branch review using selected execution method before declaring implementation complete.

## Execution handoff

Khuyến nghị Native: một agent triển khai theo thứ tự vì GUI/worker/build dùng chung nhiều interface, giảm context và token. Cuối nhánh có reviewer độc lập. Phương án Subagent-driven có implementer/reviewer mới mỗi task, kiểm tra độc lập sớm hơn nhưng tốn token hơn. Chờ người dùng duyệt kế hoạch và chọn phương pháp trước code.
