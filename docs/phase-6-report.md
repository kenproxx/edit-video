# Phase 6 — Âm lượng và âm thanh chèn

Ngày 2026-10-12. Bổ sung vào engine audio hiện có, tiếp tục Native execution và commit/báo cáo trên main theo quyền đã cấp.

## Phạm vi và cách dùng

Âm lượng gốc và âm lượng file chèn chỉnh riêng từ 0–200%, mặc định 100%; 0% tắt tiếng. Chọn một file MP3/WAV/M4A/AAC/FLAC/OGG, phát từ đầu đoạn đầu ra sau cắt và tốc độ; file chèn giữ tốc độ/cao độ gốc. Mặc định phát một lần, sau đó chỉ còn tiếng gốc. Theo phản hồi mới của người dùng, thêm giới hạn thời gian phát nhạc bằng giây: để trống phát hết bản nhạc/đến hết video, giá trị dương cắt nhạc sau số giây chọn, không rút ngắn video hay tiếng gốc. Có checkbox lặp tới giới hạn/hết video, mặc định tắt. Nhạc dài cắt theo thời lượng đầu ra. Chèn được cả vào video không có tiếng.

Preview và export dùng chung filter graph. Giữ đồng bộ nguồn audio sớm/trễ; materialize khoảng im lặng khi trộn. Khi trộn, xuất stereo để giữ hai kênh bản nhạc kể cả nguồn video mono; nguồn surround được downmix thành stereo. amix không tự hạ âm lượng hai nguồn; nếu tổng mức gây vỡ tiếng thì giảm mức người dùng chọn. Không thêm package Python hay yêu cầu cài riêng trên máy chạy EXE.

Bảo vệ file âm thanh chèn khi output trùng đường dẫn hoặc hardlink, trước khi worker bắt đầu. File thiếu hoặc không chứa audio stream báo lỗi, không thay destination cũ. Đổi tùy chọn âm thanh dừng playback và chuẩn bị lại proxy; chọn video mới reset tùy chọn âm thanh.

## Kiểm chứng

Tests đo mẫu PCM/tần số thật sau render: 0/25/200% tiếng gốc; hai mức trộn độc lập; trim/speed kèm logo; nhạc lặp/phát một lần vào silent video; đồng bộ tiếng gốc bị trễ; preview/export; file sai và bảo vệ destination/hardlink. GUI picker/fields/reset và native ffplay cho silent source có âm thanh chèn. CLI smoke chạy chung entry point EXE.

Đã quan sát RED cho API/model/UI/CLI mới. Một fixture duration dùng .4 được sửa thành 0.4 rồi chạy lại RED đúng missing feature. Regression bảo vệ secondary input được xác minh RED riêng khi bỏ guard, GREEN khi phục hồi. Targeted engine/CLI: 22 passed; GUI/playback mới đã qua riêng. Full suite trước review: 193 passed in 99.23s. Reviewer độc lập tìm một Important: nguồn mono làm mất kênh stereo của nhạc chèn, có thể triệt tiêu tín hiệu ngược pha; không Critical/Minor. Regression PCM hai kênh tái hiện RED. Một lượt sửa format stereo trước amix, không rereview. Stereo regression GREEN; 21 audio engine tests passed. Lần full suite sau sửa có `test_export_overwrite_and_progress_main_thread` timeout 15s (193 passed/1 failed); chạy riêng không đổi code qua trong 1.96s. Rerun toàn suite với stack dump khi test quá 10s: **194 passed in 92.55s**, không timeout/skip/warning hay stack dump; timeout chưa tái hiện, không tăng timeout hay bỏ assertion. `git diff --check` sạch. Bản cơ sở đã qua Windows run 38267821586 tại aae61d9. Sau phản hồi người dùng thêm duration/default once: tests mới RED12 trước triển khai; Full suite revision cập nhật: **205 passed in 97.93s**, không timeout/skip/warning hay stack dump. Stereo test chọn loop rõ ràng thay vì dựa vào default cũ; không bỏ assertion. Native Windows acceptance chờ CI cho revision cập nhật.

Windows packaged smoke bổ sung xuất trộn 25% tiếng gốc/60% tiếng chèn, đo biên độ 440/880Hz thực; playback/seek/close với silent source và file chèn trên PATH giới hạn/thư mục app chỉ đọc/đường dẫn tiếng Việt.
