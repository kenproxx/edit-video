# Phase 5 — Cắt đoạn, chỉnh vùng trực tiếp và playback trong app

Ngày 2026-10-12. Tiếp tục Native execution trên main theo quyền đã cấp; không tạo worktree hay implementer subagent.

## Kết quả

- Cắt đoạn nguồn theo phút:giây/giờ:phút:giây hoặc số phút; cắt trước tốc độ. Video/audio, intro và timeline dùng cùng đoạn đã cắt.
- Crop/blur có tám handle; kéo bên trong để di chuyển, kéo góc/cạnh để resize. Crop giữ pixel chẵn và nằm trong video.
- Logo kéo giãn độc lập ngang/dọc, text thay font size và giữ tỷ lệ raster; kéo trực tiếp trong canvas. Ô tọa độ vẫn dùng được khi cần nhập chính xác.
- Phát/tạm dừng/seek video có hiệu ứng ngay trong app, với audio bằng ffplay không mở cửa sổ riêng. Preview chuẩn bị lại sau chỉnh hiệu ứng, giữ cache khi pause/seek; ảnh tạm dừng dùng độ phân giải thật để chọn vùng.
- Preview tối đa 960×540, 15 fps, CRF 28/ultrafast; export giữ pipeline chất lượng CRF 20/medium. Không thêm thư viện Python runtime; bundle ffplay từ cùng archive FFmpeg đã xác thực.
- Hủy/đóng app dọn renderer, decoder, audio và file proxy; đợi tiến trình giữ file đóng trước khi unlink trên Windows.

## Kiểm chứng và review

Tests dùng FFmpeg thật, Tk/Pillow và audio SDL dummy; kiểm tra nội dung audio sớm/trễ, thời lượng/ảnh xuất, seek/invalidation, queue frame giới hạn, đóng app và khóa file kiểu Windows.

Reviewer độc lập read-only theo Native workflow tìm bốn Important, không Critical hay Minor. Một lượt sửa, không rereview:

1. Format endpoint làm tròn vượt thời lượng: truncate millisecond, không xuất giây 60.
2. Trim không có frame có thể FFmpeg exit 0: probe file đã render trước publish, giữ destination cũ nếu video không hợp lệ.
3. Resize text sát mép làm raster vượt khung: dùng kích thước font thật cho live drag và release, giữ cạnh đối diện.
4. Input -re chạy display sớm: thay bằng lịch frame theo monotonic clock; completed sau đủ thời lượng, không cắt audio ở decoder EOF sớm.

Regression targeted: trước sửa 6 failed/1 passed, sau sửa 7 passed. Full suite: **169 passed in 77.92s**, không skip/warning. `git diff --check` sạch. Native Windows acceptance **thành công**: run [38262691731](https://github.com/kenproxx/edit-video/actions/runs/38262691731) tại code commit `d7f82298eca6a2ef401ca7861a51e2a846d4fba7`. Bootstrap không có Python/FFmpeg trên PATH, kiểm tra cache/tamper, build lại, chính EXE xuất video với Unicode/read-only app directory/restricted PATH, GUI startup/close và embedded playback/seek/audio/cleanup đều qua.

Artifact [VideoEditor-windows-x64](https://github.com/kenproxx/edit-video/actions/runs/38262691731/artifacts/11753322445): 130,392,946 bytes, SHA256 `a42bab44c55876881ff97e80aad204a87b05c1de6265a785076e0f1607a97541`. GitHub metadata xác nhận artifact chưa expired; artifact có EXE và giấy phép/checksum. Không tạo hay publish release mới trong phase này.

## Rulings

Proxy cần thời gian chuẩn bị sau đổi hiệu ứng; lựa chọn này giữ GUI native và dùng chung pipeline với export. Khởi động thiết bị audio có độ trễ phụ thuộc máy; output audio/video được kiểm tra riêng qua integration tests. Không coi Linux tests là kiểm chứng Windows EXE. Release v0.1.0 cũ vẫn draft vì corresponding source FFmpeg còn pending; phase này không publish release công khai.
