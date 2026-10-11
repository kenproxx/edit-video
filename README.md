# Video Editor

App desktop Python để chỉnh một video và xuất MP4 mới. **Đã có GUI, engine và script build Windows. Cloud hiện tại là Linux: chưa tạo hoặc xác thực Windows EXE; cần chạy workflow Windows hoặc build trên Windows.**

## Chức năng

- Chọn video và thư mục xuất; tên mặc định lấy từ tên input.
- Tốc độ 0.25–4×, audio giữ cao độ; lật ngang/dọc.
- Crop bằng kéo chuột, nhập pixel hoặc preset 9:16 / 16:9 / 1:1.
- Blur một vùng cố định, logo và chữ watermark.
- Chữ tiếng Việt nhiều dòng trên đầu video, thời gian hiển thị chỉnh được.
- Preview bằng ảnh ở thời điểm chọn, tiến trình/hủy xuất; bảo vệ video nguồn.

## Build Windows EXE

Trên **Windows 10/11 x64**, tải/clone source rồi chạy `build.bat`. Nếu dùng Git Bash:

```bash
./build.sh
```

Không cần cài Python, FFmpeg hoặc package Python riêng. Bootstrap PowerShell tìm Python 3.13.12 x64 phù hợp; nếu chưa có thì tải installer chính thức, kiểm tra SHA-256 và chữ ký Python Software Foundation, cài riêng cho build không thêm PATH/launcher. Script tạo venv mới, cài các wheel đã khóa phiên bản/hash, tải ZIP FFmpeg 8.1.2 đã kiểm tra hash và chạy PyInstaller. Thất bại ở bất kỳ bước nào sẽ dừng build.

Kết quả dự kiến: `dist/VideoEditor.exe`, SHA-256 và thư mục giấy phép. Chạy EXE offline, không cài dependencies khi mở app. Chạy build cần mạng tới `www.python.org`, `github.com` và host release assets, `pypi.org`, `files.pythonhosted.org`. Linux/macOS được báo không hỗ trợ build Windows EXE.

Cache ở `.build-cache/` và được kiểm tra trước khi dùng archive; venv được tạo lại mỗi lần. Nếu cache sai hash, script báo file lỗi và dừng; xóa đúng file đó để tải lại. Build dùng PowerShell x64 có sẵn trên Windows; `build.sh` cần Git Bash.

Workflow [Windows standalone editor](.github/workflows/windows-build.yml) chuẩn bị build khi PATH không cung cấp Python/FFmpeg, build lại, kiểm tra cache bị sửa, rồi chạy chính EXE với PATH giới hạn, đường dẫn tiếng Việt, thư mục app chỉ đọc và GUI startup/close. Artifact chỉ được upload nếu những bước đó qua; workflow chưa được chạy trong phiên cloud này. Không tự push hoặc publish release.

Trước khi phân phối bản chứa FFmpeg GPL, bổ sung complete corresponding source của static build; xem [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Giấy phép đi kèm hiện không thay thế source bundle còn thiếu.

## Chạy source để phát triển

Python 3.12 có Tk, FFmpeg/ffprobe. Trên Linux:

```bash
./scripts/setup-dev.sh
.venv/bin/python main.py
```

GUI cần màn hình thật hoặc Xvfb. Bản đóng gói dành cho Windows 10/11 x64 chứa dependencies; hướng dẫn source này dành cho phát triển. Python build Windows 3.13.12 được khóa riêng, còn môi trường source Linux đã kiểm chứng dùng 3.12.

## Cách dùng

1. Chọn video, thư mục xuất và kiểm tra tên MP4. Không chọn output trùng video nguồn.
2. Chỉnh tùy chọn bên phải; cuộn để thấy logo/text. Các tọa độ/kích thước là pixel video, độ đậm từ 0 đến 1.
3. Dropdown preview: **Chọn crop** dùng ảnh nguồn sau lật; **Chọn vùng blur** dùng ảnh sau crop. Kéo vùng chữ nhật. Với logo/watermark/text đầu, chọn mode tương ứng rồi bấm vị trí góc trên trái.
4. Mode đặt vị trí tạm ẩn chính layer đang đặt; chọn **Xem kết quả** để thấy đủ hiệu ứng. Thanh thời gian theo video đầu ra; preview không phát realtime/audio.
5. Đổi crop/lật sẽ tắt các vùng/layer phụ thuộc và báo chọn lại để tránh dùng nhầm tọa độ. Nội dung chữ/file logo được giữ để bật lại sau khi kiểm tra.
6. **Xuất video**; xác nhận nếu file đích đã tồn tại. Có thể hủy hoặc đóng cửa sổ để hủy và chờ dọn tác vụ.

Xuất H.264/AAC MP4, CRF 20, SDR. HDR chưa hỗ trợ. Xuất an toàn hiện yêu cầu filesystem hỗ trợ hardlink (Windows NTFS, Linux ext4); filesystem không hỗ trợ sẽ báo lỗi, giữ file cũ. Nếu ứng dụng khác tạo file đúng tên đích giữa lúc publish, file đó được giữ; có thể có backup file cũ với đường dẫn trong lỗi. Không đồng thời sửa file đích bằng ứng dụng khác.

## Kiểm thử

Máy Linux có Tk 8.6 và Xvfb:

```bash
xvfb-run -a .venv/bin/python -m pytest -q
```

Cloud hiện tại dùng Python 3.12 với một `_tkinter` Tk 8.6 cục bộ cho kiểm chứng vì renderer Tk 9 mặc định thiếu font Unicode. Xvfb và shim ở `/tmp`, không được đóng gói với sản phẩm:

```bash
PYTHONPATH=/tmp/edit-video-tk86 \
PATH="/tmp/edit-video-display-root/usr/bin:$PATH" \
/tmp/edit-video-display-root/usr/bin/xvfb-run -a .venv/bin/python -m pytest -q
```

Để kiểm chứng EXE sau build trên Windows:

```powershell
.build-cache\venv\Scripts\python.exe scripts/smoke-packaged.py --exe dist/VideoEditor.exe --ffmpeg tools/ffmpeg.exe
```

CLI headless cũng chạy từ source (thư mục output và thư mục cha của report phải có sẵn; file report phải chưa tồn tại):

```bash
.venv/bin/python main.py --smoke-test input.mp4 --output-dir output --report report.json
```

Xem [báo cáo phase 2](docs/phase-2-report.md), [báo cáo phase 3](docs/phase-3-report.md), [báo cáo phase 4](docs/phase-4-report.md), [đặc tả](docs/superpowers/specs/2026-10-11-video-editor-design.md) và [kế hoạch](docs/superpowers/plans/2026-10-11-video-editor.md). Kiểm chứng Windows/EXE và source bundle FFmpeg vẫn còn chờ.
