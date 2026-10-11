# Phase 2 — engine chỉnh sửa video

## Kết quả

Đã thực hiện tasks 1–4 của kế hoạch, chưa có GUI/EXE. Engine có cấu hình/validation, tọa độ crop/preview, ffprobe metadata, orientation/SAR, tốc độ/audio, lật/crop, blur cố định, PNG logo/text watermark, text đầu video, preview và worker xuất/hủy.

Dependencies Python được khóa trong requirements. FFmpeg/ffprobe hiện dùng bản hệ thống 7.1.5; đóng gói Windows và tải binaries tự động thuộc phase 4. `scripts/setup-dev.sh` chuẩn bị venv và kiểm tra công cụ cho phát triển Linux; đã chạy lặp lại thành công ở cloud hiện tại.

## Kiểm chứng

Lệnh: `.venv/bin/python -m pytest -q` tại root repository.

Kết quả sau sửa review: **60 passed**, không có test skipped hoặc warning. Các clip được tạo trong thư mục test tạm, không đưa vào Git. Kiểm thử dùng FFmpeg thật, ffprobe, phân tích pixel và zero crossings audio; không chỉ kiểm tra file tồn tại.

- Tốc độ 0.25/1/4, thời lượng video/audio và cao độ sine 440 Hz.
- Rotation, SAR, cả rotation + SAR; HDR/file hỏng bị báo lỗi.
- Lật/crop theo pixel; blur giảm phương sai đúng vùng, có vùng kích thước lẻ.
- Logo alpha, watermark, chữ tiếng Việt nhiều dòng và thời điểm kết thúc intro.
- Preview video chuyển động khớp frame xuất, có xét sai số encoder và lượng tử thời gian CFR.
- Đường dẫn Unicode, dấu nháy và dấu hai chấm trên Linux qua argument list.
- Chống ghi đè input, alias symlink/hardlink; xác nhận overwrite; xung đột trước và giữa publish.
- Xuất thật, hủy FFmpeg đang chạy, một job mỗi worker, progress coalescing, lỗi encoder/cleanup.

## Review độc lập và sửa lỗi

Reviewer chỉ đọc phase 2, không triển khai task thay agent chính. Không có finding Critical. Bốn Important đã có regression test RED → GREEN:

1. Giữ offset giữa audio/video khi thay tốc độ: bổ sung `MediaInfo.audio_offset` mặc định 0.
2. Kiểm tra khả năng hardlink trước khi chuyển file đích cũ: filesystem không hỗ trợ sẽ dừng với đích cũ nguyên vị trí.
3. Lỗi cleanup luôn kết thúc trạng thái worker và phát terminal error, kèm đường dẫn file chưa xóa được.
4. Preview/source frame dùng PNG tạm mới, kiểm tra ảnh hợp lệ rồi thay thế đích; EOF không trả ảnh cũ.

Finding preview chuyển động lệch một frame được coi là ảnh hưởng quan trọng tới tính nhất quán preview/xuất. Đã dùng chung filter CFR trước overlay và kiểm thử bằng clip chuyển động. Không còn finding được hoãn từ review này. Full suite chạy lại sau sửa, không dispatch vòng review thứ hai.

## Quyết định triển khai và giới hạn

- Checkout cloud đang ở nhánh `work`, giữ nguyên; không tạo worktree.
- Skill scripts/reference phụ không đọc được qua các resource path được cung cấp; dùng ledger, brief từ kế hoạch và log kiểm thử thủ công tại `.superpowers/sdd/2026-10-11-video-editor/`. Đây là thay đổi bookkeeping, không thay scope hoặc bỏ RED/GREEN.
- Dùng Python 3.12 và FFmpeg hệ thống để kiểm thử Linux. Fixture rotation dùng API `display_rotation` của FFmpeg 7; fixture HDR dùng x264 VUI vì thử nghiệm ffprobe cho thấy cách metadata cũ không tạo dữ liệu yêu cầu. Bản Windows chưa được kiểm chứng.
- Helper kích thước text được tạo ở task 1, trước rasterization task 3, để validation và ảnh thực dùng cùng phép đo Pillow.
- Không có compare-and-replace filesystem portable để thay file đích và đồng thời chống mọi writer ngoài app. Publish dùng lock giữa các exporter của app, backup có tên duy nhất và hardlink không thay thế file đã tồn tại; kiểm tra identity file cũ trước/sau chuyển. Nếu writer ngoài app tạo file ở đích khi publish, giữ file đó và giữ backup cũ nếu không thể phục hồi an toàn. Error cung cấp vị trí backup. Có khoảng ngắn tên đích trống khi ghi đè đã xác nhận; hardlink filesystem là điều kiện bắt buộc, fail closed nếu không hỗ trợ. Không thể khóa hoàn toàn việc writer POSIX không hợp tác sửa inode cũ tại mọi thời điểm. Vì vậy không nên dùng ứng dụng khác đồng thời sửa chính file đích.
- CFR giữ fps của nguồn nhưng lấy mẫu frame theo interval; preview và xuất cùng phép lấy mẫu. Không cam kết lấy một frame nguồn chính xác ở mọi timestamp phân số.
- Windows case-insensitive paths, EXE offline, private Python bootstrap, FFmpeg bundle và GUI smoke chưa chạy; thuộc phase 3/4. Không có GUI hoặc EXE được công bố ở phase này.

## Tiếp tục

Chờ người dùng yêu cầu phase 3: giao diện tiếng Việt, crop/blur/overlay trên preview, tiến trình và hủy. Không tự triển khai phase 3 trong lượt phase 2.
