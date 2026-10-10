# Edit Video — chỉnh sửa video trên Windows

Ứng dụng Python, giao diện tiếng Việt, xử lý video tại máy bằng FFmpeg.
Bản portable dành cho **Windows 10/11 x64**: giải nén và mở `EditVideo.exe`,
không cần cài Python hoặc FFmpeg riêng.

## Tải ứng dụng

1. Mở [GitHub Actions](https://github.com/kenproxx/edit-video/actions/workflows/windows.yml).
2. Chọn lần chạy có dấu xanh cho commit bạn muốn dùng.
3. Tải artifact **EditVideo-windows-x64** (GitHub có thể yêu cầu đăng nhập).
4. Giải nén artifact, rồi giải nén `EditVideo-windows-x64.zip` bên trong.
5. Giữ nguyên thư mục `EditVideo`, bao gồm `_internal`, và mở `EditVideo.exe`.

Artifact có thời hạn 30 ngày; có thể chạy lại workflow hoặc tự build.
EXE chưa được ký số; chỉ dùng file do repo và lần build bạn đã kiểm tra tạo ra.

## Sử dụng

1. **Chọn video**: MP4, MOV, MKV, AVI, WEBM hoặc video khác mà FFmpeg đọc được.
2. Kéo thanh thời gian để xem khung hình. Đây là **preview ảnh tĩnh**, chưa phát liên tục.
3. Chỉnh tốc độ **0,25×–4×**, lật ngang/dọc hoặc crop tự do, **9:16 / 16:9 / 1:1**.
4. Chọn chế độ **Chọn vùng crop** hoặc **Chọn vùng làm mờ**, rồi kéo hình chữ nhật trên ảnh.
   Crop được chọn trên ảnh nguồn đã xoay đúng; vùng mờ chọn trên ảnh sau crop/lật.
   Có thể nhập tọa độ/kích thước phần trăm để chỉnh chính xác.
5. Thêm logo PNG/JPG hoặc chữ watermark. PNG giữ nền trong suốt. Chỉnh vị trí,
   kích thước, mức hiển thị, font, màu và viền; chọn chế độ đặt lớp rồi nhấn trên ảnh.
6. **Ảnh bìa**: chọn khung hình, bật chữ bìa, nhập nội dung và chọn chế độ
   **Ảnh bìa / đặt chữ**. Nhấn **Xuất ảnh bìa** để tạo PNG/JPG riêng.
   Chữ bìa không được chèn vào video. Ảnh bìa giữ các hiệu ứng video hiện tại.
7. Chọn thư mục, sửa tên nếu cần, nhấn **Xuất video MP4**.

Tên video mặc định là `<tên-gốc>.mp4`; ảnh bìa là `<tên-gốc>_thumbnail.png/jpg`.
Thư mục gợi ý là `edited` cạnh nguồn. App luôn chặn ghi đè video nguồn,
đòi xác nhận khi trùng file khác và chỉ thay file đích sau khi render thành công.
Nhấn **Hủy** để dừng; file đích cũ được giữ nguyên khi tác vụ lỗi/hủy.

## Tự build EXE — không cần cài môi trường trước

Tải source bằng **Code → Download ZIP**, giải nén vào thư mục có quyền ghi,
rồi chạy trên Windows x64 có Internet:

```bat
build_exe.bat
```

Nếu dùng Git Bash trên Windows:

```bash
bash build_exe.sh
```

Script tự tải Python NuGet 3.12.10, tạo môi trường riêng trong `.build`, cài
các thư viện khóa phiên bản/hash, tải FFmpeg/ffprobe 7.1.1, chạy kiểm thử và
đóng gói bằng PyInstaller. Không cần admin, Python hệ thống, FFmpeg trong PATH,
hoặc cài Bash nếu dùng file BAT. Bash trên Linux không tạo được EXE Windows;
hãy dùng workflow Windows hoặc máy Windows.

Kết quả: `dist/EditVideo-windows-x64.zip`. Script kiểm tra cả bản build và
bản giải nén ZIP với PATH không có Python/FFmpeg ngoài. Self-test mở cửa sổ
Qt offscreen và xuất video/ảnh bìa bằng binary đóng gói.

Nguồn tải và SHA-256 trong `packaging/downloads.json`; các wheel Windows được
khóa trong `requirements-build.lock`. Nếu tải lỗi, chạy lại; nếu checksum sai,
script dừng trước khi chạy bộ tải về. Xóa đúng file cache được báo lỗi rồi thử lại.
Không bỏ bước xác minh hash.

## Phát triển và kiểm thử

Trên môi trường đã có Python 3.11+ và FFmpeg/ffprobe:

```bash
python -m pip install -e . -r requirements-dev.txt
python -m edit_video
python -m pytest -q
```

Nếu binary không ở PATH, đặt `EDIT_VIDEO_FFMPEG_DIR` tới thư mục chứa cả hai.
Bản frozen luôn ưu tiên binary đi kèm, không cần biến này.

Test dùng video tổng hợp, so sánh hình ảnh, thời lượng/audio, đường dẫn tiếng Việt,
rotation/SAR, lỗi/hủy, chống ghi đè và luồng giao diện Qt. Hai test PowerShell
chỉ chạy trên Windows. CI chạy toàn bộ và kiểm tra ZIP; kiểm tra offscreen
không thay thế hoàn toàn thử tương tác thủ công trên Windows.

## Giới hạn và xử lý lỗi

- Một video, một vùng mờ, một logo và một lớp watermark chữ mỗi lần; ảnh bìa có lớp chữ riêng.
- Vùng mờ cố định toàn thời lượng, không theo dõi đối tượng di chuyển.
- Xuất H.264/AAC bằng CPU; không giữ các track audio/subtitle phụ, HDR hoặc metadata gốc.
- Giữ tốc độ khung hình nguồn; kích thước xuất chẵn để tương thích H.264.
- Dung lượng đĩa phải đủ chứa file tạm và thành phẩm. File nguồn hỏng hoặc codec
  không đọc được sẽ hiện lỗi, có ô chi tiết bên dưới.
- Thư mục đích phải hỗ trợ hard link (NTFS thông dụng) để công bố file mới mà
  không ghi đè ngoài ý muốn. Với USB FAT/exFAT, hãy xuất vào NTFS rồi chép sang USB.
- Phân phối có thông báo giấy phép trong `_internal/licenses`; xem
  [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) trước khi phân phối lại.

## Thiết kế

- [Đặc tả đã duyệt](docs/superpowers/specs/2026-10-10-edit-video-design.md)
- [Kế hoạch triển khai](docs/superpowers/plans/2026-10-10-edit-video.md)
