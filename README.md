# Video Editor

App desktop Python để chỉnh một video và xuất MP4 mới. **Đã có GUI, engine và Windows EXE được build/kiểm chứng trên GitHub Actions. Release `v0.1.0` giữ trạng thái nháp trong khi chờ corresponding source của FFmpeg trước khi phân phối công khai.**

## Chức năng

- Chọn video và thư mục xuất; tên mặc định lấy từ tên input.
- Tốc độ 0.25–4×, audio giữ cao độ; lật ngang/dọc.
- Cắt đoạn từ/tới theo phút:giây hoặc số phút; tốc độ áp dụng sau khi cắt.
- Crop bằng kéo góc/cạnh, di chuyển vùng, nhập pixel hoặc preset 9:16 / 16:9 / 1:1.
- Blur một vùng cố định; kéo để di chuyển/đổi kích thước logo và chữ watermark.
- Chữ tiếng Việt nhiều dòng trên đầu video, thời gian hiển thị chỉnh được.
- Phát/tạm dừng video có hiệu ứng và âm thanh ngay trong app; seek trên thanh thời gian.
- Tiến trình/hủy xuất; bảo vệ video nguồn và file đích khi xuất lỗi.

## Build Windows EXE

Trên **Windows 10/11 x64**, tải/clone source rồi chạy `build.bat`. Nếu dùng Git Bash:

```bash
./build.sh
```

Không cần cài Python, FFmpeg hoặc package Python riêng. Bootstrap PowerShell tìm Python 3.13.12 x64 phù hợp; nếu chưa có thì tải installer chính thức, kiểm tra SHA-256 và chữ ký Python Software Foundation, cài riêng cho build không thêm PATH/launcher. Script tạo venv mới, cài các wheel đã khóa phiên bản/hash, tải ZIP FFmpeg 8.1.2 đã kiểm tra hash và chạy PyInstaller. Thất bại ở bất kỳ bước nào sẽ dừng build.

Kết quả dự kiến: `dist/VideoEditor.exe`, SHA-256 và thư mục giấy phép. Chạy EXE offline, không cài dependencies khi mở app. Chạy build cần mạng tới `www.python.org`, `github.com` và host release assets, `pypi.org`, `files.pythonhosted.org`. Linux/macOS được báo không hỗ trợ build Windows EXE.

Cache ở `.build-cache/` và được kiểm tra trước khi dùng archive; venv được tạo lại mỗi lần. Nếu cache sai hash, script báo file lỗi và dừng; xóa đúng file đó để tải lại. Build dùng PowerShell x64 có sẵn trên Windows; `build.sh` cần Git Bash.

Workflow [Windows standalone editor](.github/workflows/windows-build.yml) chuẩn bị build khi PATH không cung cấp Python/FFmpeg, build lại, kiểm tra cache bị sửa, rồi chạy chính EXE với PATH giới hạn, đường dẫn tiếng Việt, thư mục app chỉ đọc và GUI startup/close. Artifact chỉ được upload nếu những bước đó qua; Run [38262691731](https://github.com/kenproxx/edit-video/actions/runs/38262691731) đã chạy thành công trên Windows với playback/seek/audio ngay trong app. Tải build mới ở artifact **VideoEditor-windows-x64** của run này. Workflow build không tự publish release.

Trước khi phân phối bản chứa FFmpeg GPL, bổ sung complete corresponding source của static build; xem [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Giấy phép đi kèm hiện không thay thế source bundle còn thiếu.

## Chạy source để phát triển

Python 3.12 có Tk, FFmpeg/ffprobe/ffplay. Trên Linux:

```bash
./scripts/setup-dev.sh
.venv/bin/python main.py
```

GUI cần màn hình thật hoặc Xvfb. Bản đóng gói dành cho Windows 10/11 x64 chứa dependencies; hướng dẫn source này dành cho phát triển. Python build Windows 3.13.12 được khóa riêng, còn môi trường source Linux đã kiểm chứng dùng 3.12.

## Cách dùng

1. Chọn video, thư mục xuất và kiểm tra tên MP4. Không chọn output trùng video nguồn.
2. Chỉnh tùy chọn bên phải; cuộn để thấy logo/text. Bật **Cắt đoạn** rồi nhập từ/tới: `2:30` là 2 phút 30 giây, `2.5` là 2.5 phút. Các tọa độ/kích thước là pixel video, độ đậm từ 0 đến 1.
3. Dropdown preview: **Chọn crop** dùng ảnh nguồn sau lật; **Chọn vùng blur** dùng ảnh sau crop. Kéo vùng chữ nhật; kéo góc/cạnh để resize, kéo bên trong để di chuyển. Với logo/watermark/text đầu, bật layer, chọn mode tương ứng rồi kéo trực tiếp. Logo cho phép kéo giãn độc lập; text giữ tỷ lệ theo font.
4. Chọn **Xem kết quả** hoặc **Phát preview** để xem đủ hiệu ứng ngay trong app. Lần đầu hoặc sau thay đổi, app chuẩn bị bản preview; các lần phát/seek sau dùng lại. **Tạm dừng** để chỉnh vùng trên ảnh rõ nét. Thanh thời gian tính theo đoạn đầu ra sau cắt và đổi tốc độ.
5. Đổi crop/lật sẽ tắt các vùng/layer phụ thuộc và báo chọn lại để tránh dùng nhầm tọa độ. Nội dung chữ/file logo được giữ để bật lại sau khi kiểm tra.
6. **Xuất video**; xác nhận nếu file đích đã tồn tại. Có thể hủy hoặc đóng cửa sổ để hủy và chờ dọn tác vụ.

Preview phát tối đa 960×540/15 fps để giảm tải; xuất giữ độ phân giải đã chọn. Đoạn quá ngắn không chứa frame sẽ báo lỗi và giữ file đích cũ.

Xuất H.264/AAC MP4, CRF 20, SDR. HDR chưa hỗ trợ. Xuất an toàn hiện yêu cầu filesystem hỗ trợ hardlink (Windows NTFS, Linux ext4); filesystem không hỗ trợ sẽ báo lỗi, giữ file cũ. Nếu ứng dụng khác tạo file đúng tên đích giữa lúc publish, file đó được giữ; có thể có backup file cũ với đường dẫn trong lỗi. Không đồng thời sửa file đích bằng ứng dụng khác.

## Kiểm thử

Máy Linux có Tk 8.6 và Xvfb:

```bash
xvfb-run -a .venv/bin/python -m pytest -q
```

Môi trường cloud đã kiểm chứng thêm Python 3.13/Tk 8.6, FFmpeg/ffprobe/ffplay và Xvfb; công cụ Linux không được đóng gói với Windows app.

Để kiểm chứng EXE sau build trên Windows:

```powershell
.build-cache\venv\Scripts\python.exe scripts/smoke-packaged.py --exe dist/VideoEditor.exe --ffmpeg tools/ffmpeg.exe
```

CLI headless cũng chạy từ source (thư mục output và thư mục cha của report phải có sẵn; file report phải chưa tồn tại):

```bash
.venv/bin/python main.py --smoke-test input.mp4 --output-dir output --report report.json
```

Xem [báo cáo phase 2](docs/phase-2-report.md), [báo cáo phase 3](docs/phase-3-report.md), [báo cáo phase 4](docs/phase-4-report.md), [đặc tả](docs/superpowers/specs/2026-10-11-video-editor-design.md) và [kế hoạch](docs/superpowers/plans/2026-10-11-video-editor.md). Windows/EXE đã qua CI; source bundle FFmpeg để phân phối công khai vẫn còn chờ.

## GitHub Release

Release nháp `v0.1.0` lấy artifact của run Windows đã thành công, kèm EXE trực tiếp, ZIP gồm notices/licenses và `SHA256SUMS.txt`. Chủ repository có thể mở [Releases](https://github.com/kenproxx/edit-video/releases) để tải assets của bản nháp.

Workflow `Attach verified EXE to draft release` nhận tag bản nháp và run ID của workflow Windows. Nó chỉ nhận build thành công từ `main` đúng commit đích release, kiểm tra digest artifact + hash EXE + PE x64 và giữ release ở trạng thái draft. Asset đã có chỉ được giữ lại nếu cùng digest; không ghi đè file khác và không tự Publish.

Trong cloud, API đọc/tạo release hoạt động nhưng upload trực tiếp trả 401; workflow dùng token repository để upload. Trước Publish cần bổ sung complete corresponding source của FFmpeg static; xem `THIRD_PARTY_NOTICES.md`.
