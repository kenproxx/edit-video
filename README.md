# Video Editor

App desktop Python để chỉnh một video và xuất MP4 mới. **Phase 3: đã có GUI và engine; Windows EXE/script build tự chuẩn bị dependencies thuộc phase 4, chưa có ở bản này.**

## Chức năng

- Chọn video và thư mục xuất; tên mặc định lấy từ tên input.
- Tốc độ 0.25–4×, audio giữ cao độ; lật ngang/dọc.
- Crop bằng kéo chuột, nhập pixel hoặc preset 9:16 / 16:9 / 1:1.
- Blur một vùng cố định, logo và chữ watermark.
- Chữ tiếng Việt nhiều dòng trên đầu video, thời gian hiển thị chỉnh được.
- Preview bằng ảnh ở thời điểm chọn, tiến trình/hủy xuất; bảo vệ video nguồn.

## Chạy source để phát triển

Python 3.12 có Tk, FFmpeg/ffprobe. Trên Linux:

```bash
./scripts/setup-dev.sh
.venv/bin/python main.py
```

GUI cần màn hình thật hoặc Xvfb. Bản đóng gói cuối dành cho Windows 10/11 x64 sẽ chứa dependencies; hướng dẫn source này dành cho phát triển, không phải yêu cầu cài riêng cho người dùng EXE.

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

Xem [báo cáo phase 2](docs/phase-2-report.md), [báo cáo phase 3](docs/phase-3-report.md), [đặc tả](docs/superpowers/specs/2026-10-11-video-editor-design.md) và [kế hoạch](docs/superpowers/plans/2026-10-11-video-editor.md). Kiểm chứng Windows và build EXE sẽ báo riêng ở phase 4.
