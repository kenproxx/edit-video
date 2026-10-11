# Báo cáo phase 3 — GUI desktop

Đã triển khai giao diện tiếng Việt bằng CustomTkinter: chọn video/thư mục, tên output mặc định, speed/lật, crop preset/kéo chuột/nhập số, blur, logo/text watermark và text đầu video. Preview chọn thời điểm, tọa độ theo ảnh video sau các biến đổi tương ứng. Các nhóm tùy chọn cuộn; tiến trình và hủy xuất luôn ở thanh dưới.

Probe và preview chạy nền, mỗi controller chỉ giữ tác vụ mới nhất; kết quả cũ không được đưa lên canvas. Hủy/đóng cửa sổ chờ dừng child process. Export dùng worker và cơ chế bảo vệ input/file đích của phase 2. Đổi crop/lật tắt các layer phụ thuộc và yêu cầu chọn lại tọa độ. Startup không cài package.

## Kiểm chứng

- Các test GUI dùng cửa sổ Tk thật dưới Xvfb, FFmpeg thật và video tổng hợp; chỉ mock hộp thoại chọn file/xác nhận để chạy tự động.
- Kiểm tra mỗi tính năng đi vào model, tọa độ letterbox, text nhiều dòng, Unicode font, preview cũ, export đầy đủ hiệu ứng, progress/hủy/lỗi, thoát và bố cục cửa sổ hẹp.
- Reviewer độc lập: 86 tests pass trên commit GUI đầu; phát hiện hai lỗi Important và một lỗi Minor. Đã sửa trong một lượt: dữ liệu crop nhập dở không làm chết polling; sau terminal export tự refresh preview để chọn tiếp; layer đang đặt vị trí được loại trước khi parse nên có thể sửa tọa độ bằng chuột.
- Ba regression test tái hiện lỗi trước sửa đều thất bại; kết quả sau sửa được ghi bên dưới.

## Môi trường và giới hạn

Python 3.12/Tk 9 mặc định trên cloud thiếu renderer font Unicode. Kiểm chứng GUI dùng `_tkinter` Tk 8.6 cục bộ, build từ CPython v3.12.14 commit `2abcf904b8dac8c999d2b3aac76681abb333798a`, liên kết thư viện Tk/Tcl 8.6 hệ thống. Header và Xvfb lấy từ Debian trixie qua index có chữ ký và hash package; mọi artifact bổ sung ở `/tmp`. Không sửa môi trường hệ thống, không bundle shim này vào app.

Lệnh chạy test cloud:

```bash
PYTHONPATH=/tmp/edit-video-tk86 \
PATH="/tmp/edit-video-display-root/usr/bin:$PATH" \
/tmp/edit-video-display-root/usr/bin/xvfb-run -a .venv/bin/python -m pytest -q
```

Đã quan sát ảnh GUI hiển thị tiếng Việt đúng. CustomTkinter có cảnh báo font/drawing fallback khi chạy standalone trong home chỉ đọc của cloud; bộ pytest không bỏ qua test GUI. Preview là ảnh tĩnh theo timeline, không phát audio/realtime. Windows GUI native, bootstrap và EXE chưa kiểm chứng; thuộc phase 4. Filesystem xuất cần hỗ trợ hardlink; các giới hạn cạnh tranh file được ghi trong README/phase 2.

Kết quả cuối: full suite **89 passed in 53.64s**, sau đó hai test bổ sung kiểm tra chọn blur ngay sau terminal hủy/lỗi **2 passed in 4.25s** (tổng 91 test đã chạy qua). `git diff --check` sạch. Không có Windows executor nên không tuyên bố kiểm chứng Windows/EXE.
