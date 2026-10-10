# Edit Video Windows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tạo app Windows chỉnh sửa video, xuất ảnh bìa riêng và bộ build EXE tự chuẩn bị toàn bộ dependencies.

**Architecture:** PySide6 quản lý giao diện và vẽ chữ; FFmpeg/ffprobe đọc và xử lý media qua tiến trình nền. Cấu hình chỉnh sửa độc lập với widget, dùng chung pipeline hình ảnh cho preview/ảnh bìa/video. Bootstrap Windows tạo bản portable bằng PyInstaller.

**Tech Stack:** Python, PySide6, FFmpeg/ffprobe, PyInstaller, pytest, pytest-qt, PowerShell, GitHub Actions Windows.

**Spec:** `docs/superpowers/specs/2026-10-10-edit-video-design.md` — người dùng duyệt ngày 10/10/2026.

## Global Constraints

- Windows 10/11 x64; giao diện và README tiếng Việt; xử lý media tại máy.
- Tốc độ 0,25×–4×, mặc định 1×; audio đồng bộ và giữ cao độ.
- Crop tự do và preset 9:16, 16:9, 1:1; lật ngang/dọc độc lập.
- Một vùng mờ cố định, một logo và một lớp text watermark; có thể bật đồng thời.
- Ảnh bìa JPG/PNG riêng; chữ bìa không xuất hiện trong video.
- Video MP4/H.264/yuv420p, AAC nếu có audio, faststart; tên mặc định `<tên-gốc>.mp4`.
- Không ghi đè nguồn; giữ file đích cũ khi lỗi/hủy; chỉ công bố kết quả đã kiểm tra.
- `build_exe.bat` và `build_exe.sh` cho Git Bash trên Windows; tự tải Python, FFmpeg/ffprobe và thư viện, không yêu cầu cài chúng trước.
- Portable ZIP chứa `EditVideo.exe` và dependencies; không yêu cầu EXE đơn lẻ.
- Phiên bản/SHA-256 cố định cho bộ tải về, kiểm tra trước khi chạy; kèm giấy phép bên thứ ba.
- Chỉ xử lý một video mỗi lần. Preview là khung hình tĩnh cập nhật khi đổi thời gian/thiết lập.

## Review Focus

- Video điện thoại có rotation, tỷ lệ pixel khác 1 hoặc kích thước lẻ: preview và output phải cùng hướng/hình học (Task 2, 4).
- Tên nguồn Unicode và ký tự shell, đích khác cách viết nhưng cùng file: không lỗi đường dẫn hoặc ghi đè nguồn (Task 2, 5).
- Kéo thanh thời gian liên tục rồi xuất/đóng app: không hiện kết quả cũ hoặc để tiến trình chạy mồ côi (Task 5, 6).
- Chữ tiếng Việt nhiều dòng, logo lớn và vùng crop rất nhỏ: kiểm tra biên và render thống nhất (Task 1, 3, 4).
- Máy Windows thiếu Python/FFmpeg trong PATH hoặc tải bộ build hỏng: bootstrap chạy độc lập, checksum sai phải dừng (Task 7).

## File map

- `pyproject.toml`, `requirements-dev.txt`: khai báo package và công cụ test.
- `src/edit_video/models.py`: các kiểu dữ liệu và validation thuần Python.
- `src/edit_video/binaries.py`, `media.py`: tìm binary, ffprobe và metadata.
- `src/edit_video/overlays.py`: lớp ảnh chữ/logo bằng Qt.
- `src/edit_video/pipeline.py`: tạo lệnh preview, ảnh bìa và video.
- `src/edit_video/jobs.py`, `output.py`: tiến trình nền, hủy, tiến độ và file đích.
- `src/edit_video/ui/{window,preview,controls,controller}.py`: cửa sổ, canvas, panel và điều phối.
- `src/edit_video/__main__.py`: điểm vào ứng dụng.
- `scripts/{bootstrap.ps1,verify_bundle.py}`, `build_exe.bat`, `build_exe.sh`, `EditVideo.spec`: build.
- `packaging/downloads.json`, `requirements-build.lock`, `THIRD_PARTY_NOTICES.md`: manifest, dependency lock và giấy phép.
- `tests/{conftest,test_models,test_media,test_overlays,test_pipeline,test_output,test_jobs,test_ui,test_bootstrap}.py`: kiểm thử theo trách nhiệm.
- `.github/workflows/windows.yml`, `README.md`: CI và hướng dẫn.

## Task 1: Cấu hình chỉnh sửa và quy tắc hình học

**Files:** tạo `pyproject.toml`, `requirements-dev.txt`, `src/edit_video/__init__.py`, `src/edit_video/models.py`, `tests/test_models.py`, `.gitignore`.

**Interfaces:**
- `Rect(x: float, y: float, width: float, height: float)`: tọa độ chuẩn hóa, biên trong 0–1.
- `TextLayer(text: str, font_family: str, size_px: int, color: str, stroke_color: str, stroke_px: int, opacity: float, x: float, y: float)`.
- `LogoLayer(path: Path, x: float, y: float, width: float, opacity: float)`; width tương đối với ảnh xuất, giữ tỷ lệ logo.
- `BlurLayer(rect: Rect, sigma: float)`; `EditSettings(speed=1.0, flip_h=False, flip_v=False, crop=None, blur=None, logo=None, watermark=None, cover=None)`.
- `validate(settings: EditSettings) -> None`: lỗi `ValueError`; `crop_pixels(crop: Rect | None, width: int, height: int) -> tuple[int,int,int,int]` trả `(x,y,w,h)` hợp lệ, w/h chẵn và ít nhất 2.

- [ ] Viết test `test_speed_bounds`, `test_rect_bounds`, `test_even_crop`: nhận 0.25/1/4, từ chối 0/4.01/NaN; từ chối rectangle vượt biên/diện tích 0; full crop 641×481 cho w=640,h=480. Kiểm tra opacity 0–1, size dương, stroke không âm, sigma dương.
- [ ] Chạy `python -m pytest tests/test_models.py -q`; xác nhận fail vì chưa có implementation.
- [ ] Triển khai dataclass và validation; không phụ thuộc Qt; kiểm tra giá trị hữu hạn ở mọi trường số.
- [ ] Chạy lại cùng lệnh, yêu cầu tất cả pass.
- [ ] Commit `feat: add validated editing settings`.

## Task 2: Đọc media và tìm binary

**Files:** tạo `src/edit_video/binaries.py`, `src/edit_video/media.py`, `tests/conftest.py`, `tests/test_media.py`.

**Interfaces:**
- `Binaries(ffmpeg: Path, ffprobe: Path)`; `resolve_binaries() -> Binaries`: ưu tiên bản đóng gói, dev cho phép đường dẫn cấu hình rồi PATH.
- `MediaInfo(path: Path, video_index: int, audio_index: int | None, width: int, height: int, duration: float, fps: float, rotation: int, sar: float)`; width/height là kích thước sau chuẩn hóa hướng và SAR.
- `probe(path: Path, binaries: Binaries) -> MediaInfo`; `MediaError` chứa lỗi thân thiện và chi tiết stderr.
- Fixtures: `binaries`, `sample_video`, `silent_video`, `rotated_video`, `odd_sar_video`; tạo clip ngắn bằng FFmpeg, có góc màu và audio mốc, dùng thư mục tạm.

- [ ] Viết `test_probe_unicode_and_shell_chars`, `test_probe_rotation_sar`, `test_probe_silent`, `test_invalid_media`: đọc đường dẫn có dấu/khoảng trắng/`&`; hướng và display size đúng fixture; audio_index=None cho clip câm; file lỗi tạo MediaError.
- [ ] Chạy `python -m pytest tests/test_media.py -q`; xác nhận fail ở module/chức năng mới.
- [ ] Triển khai ffprobe JSON với timeout, argv list, không shell; chọn video stream thật đầu tiên (bỏ attached picture), audio đầu tiên; xử lý display matrix, rotation tag, SAR và frame-rate phân số.
- [ ] Chạy lại test; môi trường phát triển phải có FFmpeg để test thực, không đánh dấu skip rồi coi là đã đạt.
- [ ] Commit `feat: inspect source media and locate bundled tools`.

## Task 3: Lớp chữ và logo

**Files:** tạo `src/edit_video/overlays.py`, `tests/test_overlays.py`.

**Interfaces:** consumes `TextLayer`, `LogoLayer` từ Task 1.
- `text_overlay(layer: TextLayer, size: tuple[int,int]) -> QImage`: ảnh ARGB trong suốt kích thước canvas, QPainterPath chữ nhiều dòng, stroke/opacity đúng thiết lập.
- `logo_overlay(layer: LogoLayer, size: tuple[int,int]) -> QImage`.
- `write_overlays(settings: EditSettings, size: tuple[int,int], directory: Path, include_cover: bool) -> list[Path]`: logo → watermark → chữ bìa nếu yêu cầu.

- [ ] Viết `test_vietnamese_multiline`, `test_logo_alpha_and_aspect`, `test_cover_is_optional`: ảnh có pixel chữ cả hai dòng và alpha ngoài chữ=0; logo giữ tỷ lệ; cover chỉ có trong danh sách include_cover=True. Viết `test_oversized_overlay_bounds`: lớp quá lớn được thu vừa canvas và chặn vị trí để toàn lớp nằm trong ảnh.
- [ ] Chạy `python -m pytest tests/test_overlays.py -q`, xác nhận fail.
- [ ] Triển khai Qt image painting, cùng một asset cho preview/output; font fallback hỗ trợ tiếng Việt, không nội suy text thành FFmpeg filter. Cỡ chữ UI là pixel ảnh xuất.
- [ ] Chạy lại test bằng Qt offscreen khi không có display, yêu cầu pass.
- [ ] Commit `feat: render Vietnamese text and logo overlays`.

## Task 4: Pipeline hình ảnh, tốc độ và ảnh bìa

**Files:** tạo `src/edit_video/pipeline.py`, `tests/test_pipeline.py`.

**Interfaces:** consumes `MediaInfo`, `Binaries`, `EditSettings`, `write_overlays`.
- `RenderRequest(media: MediaInfo, settings: EditSettings, destination: Path, mode: Literal['video','preview','thumbnail'], source_time: float=0.0)`.
- `build_command(request: RenderRequest, binaries: Binaries, workspace: Path) -> list[str]`; workspace chứa asset tạm, output do request chỉ định.
- `output_size(media: MediaInfo, settings: EditSettings) -> tuple[int,int]`.

- [ ] Viết `test_speed_duration_and_audio` tham số hóa 0.25/1/4: chạy lệnh, probe output, duration gần nguồn/speed trong một frame cộng độ trễ AAC; audio mốc khớp video. `test_crop_flip_corners` kiểm tra pixel góc sau crop/lật; `test_blur_locality` kiểm tra variance vùng chọn giảm, vùng ngoài giữ nguyên trước nén.
- [ ] Viết `test_combined_overlays_and_cover`, `test_silent_export`, `test_rotation_sar_odd_output`: tất cả hiệu ứng chạy cùng nhau; chữ bìa chỉ có ở thumbnail; clip câm không audio; rotation/SAR được chuẩn hóa, kích thước chẵn và preview khớp output. PNG và JPG đọc được đúng kích thước.
- [ ] Chạy `python -m pytest tests/test_pipeline.py -q`, xác nhận fail.
- [ ] Triển khai chuỗi chuẩn hóa SAR/hướng → crop → lật → blur → overlay. Chọn một cơ chế rotation nhất quán (FFmpeg autorotate), xóa rotation output, không xoay hai lần. Dùng setpts và chuỗi atempo cho 0.25–4; reset timestamps cùng điểm gốc, giữ khoảng lệch A/V có chủ đích.
- [ ] Triển khai xuất CPU libx264/yuv420p, AAC, faststart; thumbnail lấy thời điểm nguồn, chặn timestamp cuối vào frame hợp lệ; preview dùng pipeline không có chữ bìa trừ khi tab bìa đang bật. PNG lossless, JPG quality cao. Không dùng `-shortest` theo cách cắt ngắn video khi audio ngắn hơn.
- [ ] Chạy lại bộ test pipeline, ghi nhận output thực bằng ffprobe và so sánh pixel với tolerance nén; commit `feat: render edited video and separate cover images`.

## Task 5: Tác vụ nền và bảo vệ file

**Files:** tạo `src/edit_video/output.py`, `src/edit_video/jobs.py`, `tests/test_output.py`, `tests/test_jobs.py`.

**Interfaces:**
- `OutputTarget(source: Path, destination: Path, overwrite: bool)`; `validate_target(target: OutputTarget) -> None`.
- `run_export(request: RenderRequest, binaries: Binaries, overwrite: bool, cancel: threading.Event, progress: Callable[[float], None]) -> Path`.
- `PreviewCoordinator.submit(request: RenderRequest) -> int`, `close() -> None`; Qt signal `ready(generation: int, path: str)`, `failed(generation: int, message: str)`; sở hữu asset tạm cho tới khi UI đọc ảnh.

- [ ] Viết `test_same_source_rejected` cho resolved path, Windows case-insensitive và samefile/hardlink; `test_failed_export_preserves_destination`, `test_cancel_cleans_partial`, `test_existing_target_needs_consent`. Với test failure/cancel, assert bytes đích cũ không đổi và không còn temp do job tạo.
- [ ] Viết `test_newest_preview_wins`, `test_close_terminates_children`, `test_progress_finishes_after_publish`; dùng tiến trình giả có điều khiển để tái hiện race, cộng một integration hủy FFmpeg thực.
- [ ] Chạy `python -m pytest tests/test_output.py tests/test_jobs.py -q`, xác nhận fail.
- [ ] Triển khai file tạm cùng filesystem, probe/đọc ảnh xác minh trước replace, kiểm tra lại đích trước công bố. Khi overwrite=False, công bố theo cơ chế không clobber nếu file khác xuất hiện giữa chừng. Không dùng shell; drain stderr đồng thời với progress để tránh deadlock.
- [ ] Triển khai cancel terminate rồi kill với timeout 3 giây; cleanup chỉ file thuộc job. Debounce preview 150ms, tăng generation mỗi request, bỏ kết quả cũ, dừng worker lúc đóng; progress video giới hạn dưới 100% tới khi file hoàn tất.
- [ ] Chạy lại test, commit `feat: run cancellable exports with safe output handling`.

## Task 6: Giao diện tiếng Việt và luồng hoàn chỉnh

**Files:** tạo `src/edit_video/ui/__init__.py`, `window.py`, `preview.py`, `controls.py`, `controller.py`, `src/edit_video/__main__.py`, `tests/test_ui.py`.

**Interfaces:** consumes Task 1–5.
- `PreviewCanvas(QWidget).set_frame(image: QImage) -> None`, `image_rect() -> QRectF`; signals cho thay đổi rectangle và vị trí layer, quy đổi sang tọa độ chuẩn hóa.
- `EditorWindow(QMainWindow)` cung cấp canvas và controls; `EditorController(window: EditorWindow, binaries: Binaries)` điều phối nguồn, settings, preview và jobs.
- `main() -> int` trong `__main__.py`; chạy bằng `python -m edit_video`.

- [ ] Viết `test_open_edit_export_flow` với pytest-qt: chọn fixture, sửa speed/crop/logo/text/blur, xuất video/ảnh bìa và kiểm tra file; mặc định stem đúng, cover tách biệt.
- [ ] Viết `test_drag_ignores_letterbox`, `test_crop_presets`, `test_export_locks_settings`, `test_close_cancels_job`, `test_error_is_visible`: drag đúng pixel khi cửa sổ resize; tỷ lệ 9:16/16:9/1:1; controls khóa và mở lại cả khi fail; đóng app kết thúc job; lỗi hiển thị tiếng Việt.
- [ ] Chạy `python -m pytest tests/test_ui.py -q`, xác nhận fail.
- [ ] Triển khai cửa sổ co giãn với panel cuộn: chọn video, timeline nguồn, nhóm hiệu ứng, tab video/bìa, thư mục/tên đích, tiến độ và hủy. Chọn crop trên ảnh nguồn chuẩn hóa, vùng mờ/layers trên ảnh sau crop/lật; hỗ trợ kéo và nhập số, reset mặc định.
- [ ] Nối worker với Qt signal, chỉ cập nhật widget trên UI thread; xác nhận ghi đè file khác, chặn nguồn, báo chi tiết log và đường dẫn kết quả. Export snapshot settings, disable thao tác ảnh hưởng tác vụ đang chạy.
- [ ] Chạy lại test và mở GUI để kiểm tra bố cục/tiếng Việt, ghi nhận ảnh chụp nếu môi trường cho phép. Commit `feat: add Vietnamese desktop editor interface`.

## Task 7: Bootstrap và portable Windows

**Files:** tạo `scripts/bootstrap.ps1`, `scripts/verify_bundle.py`, `build_exe.bat`, `build_exe.sh`, `EditVideo.spec`, `packaging/downloads.json`, `requirements-build.lock`, `THIRD_PARTY_NOTICES.md`, `tests/test_bootstrap.py`.

**Interfaces:**
- `build_exe.bat` và `bash build_exe.sh` gọi bootstrap; exit code khác 0 nếu tải/cài/test/build lỗi.
- Manifest mỗi download có `version`, `url`, `sha256`, `license_url`; lock Python packages gồm phiên bản và hashes.
- Output `dist/EditVideo/EditVideo.exe` và `dist/EditVideo-windows-x64.zip`.
- `EditVideo.exe --self-test <working-directory>` chạy smoke test đóng gói: tìm binary, tạo fixture, render video/cover, ghi JSON kết quả và exit code.

- [ ] Xác minh nguồn phân phối chính thức cho Python/Qt/PyInstaller và bản FFmpeg Windows, chọn các phiên bản tương thích tại thời điểm triển khai; ghi URL/version/hash thực đã kiểm tra, không dùng latest hoặc hash giả. Dùng Python standalone có pip được phân phối kèm hoặc installer chính thức cài riêng theo user trong thư mục build; không giả định embedded Python hỗ trợ pip/venv.
- [ ] Viết `test_bootstrap_rejects_bad_hash`, `test_bootstrap_stops_on_download_failure`, `test_bundle_manifest` và smoke `--self-test`: lỗi tải/hash dừng trước thực thi; manifest đủ binary/Qt/plugins/notices. Test script PowerShell chạy trên Windows với fixture tải cục bộ có kiểm soát.
- [ ] Chạy test trước implementation để ghi nhận fail, rồi triển khai bootstrap không cần admin/PATH Python; cache có xác minh, venv riêng, dependencies khóa; wrappers chỉ chuyển tiếp args và exit code.
- [ ] Triển khai PyInstaller onedir, dùng Qt dynamic libraries và FFmpeg subprocess, đóng gói giấy phép/notices và thông tin nguồn tương ứng với binaries đã chọn; không tự đặt license cho repo.
- [ ] Trên Windows chạy `build_exe.bat`, giải nén ZIP ra thư mục mới và chạy `EditVideo.exe --self-test <temp-dir>` với PATH không chứa Python/FFmpeg cài ngoài. Yêu cầu JSON success và exit 0; không coi build Linux là đạt.
- [ ] Commit `build: bootstrap dependencies and package Windows portable app`.

## Task 8: CI, README và kiểm tra bàn giao

**Files:** tạo `.github/workflows/windows.yml`, sửa `README.md`; cập nhật trạng thái checklist kế hoạch theo kết quả thực.

**Interfaces:** workflow kích hoạt push/pull_request/workflow_dispatch; artifact `EditVideo-windows-x64` chứa ZIP, kết quả smoke và log test cần thiết.

- [ ] Viết workflow Windows gọi bootstrap chung, chạy toàn bộ test, build rồi self-test bản đã giải nén; fail ngay khi bước lỗi, upload artifact khi thành công. Đặt permissions tối thiểu `contents: read` và timeout hữu hạn.
- [ ] Viết README tiếng Việt: tải artifact, giải nén và chạy, hướng dẫn mỗi tính năng, ảnh bìa riêng, giới hạn preview tĩnh, tên file, máy build cần Internet, cách dùng BAT/Git Bash, log lỗi và giấy phép.
- [ ] Chạy `python -m pytest -q` và `git diff --check`; kiểm tra không có binary/cache/output mẫu bị commit. Đối chiếu 8 tiêu chí nghiệm thu của spec với test và ghi rõ tiêu chí nào chưa có kiểm chứng thực.
- [ ] Review toàn nhánh theo phương thức thực thi được người dùng chọn; sửa lỗi và chạy lại đúng các test bị ảnh hưởng cùng gate bắt buộc.
- [ ] Commit `ci: verify Windows bundle and document Vietnamese usage`, push nhánh triển khai lên repo, tạo PR để review; không tự coi yêu cầu push là yêu cầu merge main.
- [ ] Theo dõi CI đúng commit cuối, sửa nếu fail; bàn giao URL commit/PR, run và artifact. Nếu không có Windows GUI để thử thủ công, báo giới hạn đó riêng, không tuyên bố đã kiểm thử tương tác trực tiếp.

## Tự rà soát kế hoạch

- Scope một app, một pipeline; 8 task có đầu ra kiểm thử độc lập, phụ thuộc theo thứ tự.
- Đủ đặc tả: tính năng/preview Task 1–4/6, an toàn/hủy Task 5, build Task 7, CI/tài liệu Task 8.
- Năm mục Review Focus đều có test được chỉ định trong task sở hữu.
- Giao diện dùng cùng models/render/jobs, không tạo pipeline preview khác với bản xuất.
- Bản đặc tả đã duyệt; kế hoạch này chờ người dùng duyệt và chọn thực thi trực tiếp hoặc qua subagent trước khi viết mã ứng dụng.
