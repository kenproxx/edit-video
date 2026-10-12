# Phase 7 — Áp dụng chỉnh sửa cho thư mục video

Ngày 2026-10-12. Tiếp tục Native execution và commit/báo cáo trên main theo quyền đã cấp. Thêm coordinator tuần tự dùng lại RenderWorker, không thay pipeline video/audio hay thêm dependency runtime.

## Hành vi

Chọn thư mục input, chọn video mẫu trong dropdown, chỉnh các tùy chọn hiện có và chọn thư mục xuất khác nguồn. Quét video trực tiếp trong thư mục, không đệ quy hay theo symlink. Giữ tên stem từng video, xuất MP4; trùng stem/case dùng suffix _2/_3 tránh giành tên tự nhiên của video khác. Không tự ghi đè: output đã có bỏ qua.

Theo phản hồi người dùng, crop co giãn theo kích thước nguồn; blur/logo/text theo kích thước sau crop. Crop giữ pixel chẵn, text giữ tỷ lệ font và giới hạn theo raster thật. Đổi video mẫu co giãn vùng và giữ speed, trim, âm lượng/nhạc cùng các thiết lập khác. Tốc độ, mốc cắt, thời lượng intro/nhạc giữ nguyên; không tự cắt bớt mốc để ép video ngắn hợp lệ.

Chạy từng file trong nền để giữ GUI phản hồi và tải CPU/RAM vừa phải. Tiến trình hiện file i/N và tổng %. File lỗi/không phù hợp báo riêng, tiếp tục file sau; hủy/đóng app dừng native renderer và không bắt đầu phần còn lại, giữ output đã hoàn tất. Mọi job có kết quả thành công/bỏ qua/lỗi/hủy, gồm cả job chưa chạy. GUI có cửa sổ kết quả; báo cáo JSON lưu riêng trong user data, không ghi vào thư mục app hay input.

## Kiểm chứng

RED7 cho coordinator/UI mới; GREEN7. RED2 riêng khi bỏ adaptation xác nhận test phát hiện không co giãn; test crop thực so sánh output 160×120/80×60 cho source 320×240/160×120. GUI chuyển video khi ô số không hợp lệ tái hiện polling ngừng (RED), thêm xử lý lỗi để giữ polling. Tests đo đầu ra, nguyên vẹn nguồn/file đích cũ, bỏ file hỏng, hủy tiến trình, giữ file đã xong và ghi nhận unstarted jobs.

CLI smoke dùng cùng BatchWorker và EXE. Hai guard RED cho tiến trình không tụt khi events coalesce và report không chiếm tên output; đã sửa trong UI/entrypoint. Windows packaged smoke bổ sung folder Unicode, độ phân giải khác nhau, file hỏng và output có sẵn trên PATH giới hạn/thư mục app chỉ đọc.

Full suite trước review: **220 passed in 106.15s**. Reviewer độc lập tìm hai Important, không Critical/Minor: đổi mẫu nhanh hoặc qua file hỏng làm reset tùy chọn; rescale thất bại đổi metadata khi geometry vẫn theo mẫu cũ. Ba regression RED tái hiện cả hai. Một lượt sửa giữ reference qua pending/failed loads và rescale transactional; ô số sửa lại sẽ retry, preview/export chờ geometry sẵn sàng. Targeted review fix: **4 passed in 4.25s**, gồm test polling khi nhập sai. Không rereview. Full suite cuối: **223 passed in 110.65s**, không timeout/skip/warning hay stack dump; `git diff --check` sạch. Native Windows acceptance **thành công**: run [38279410582](https://github.com/kenproxx/edit-video/actions/runs/38279410582) tại code commit `4d1af40d1adf6d389fc09cac62bb7e951b01910d`. Bootstrap không có Python/FFmpeg trên PATH, cache/tamper, build lại và chính EXE export/GUI/playback/audio cùng folder batch smoke đều qua. Batch xử lý source 320×240/160×120 thành output 160×120/80×60, một file lỗi tiếp tục và một output có sẵn được giữ nguyên.

Artifact [VideoEditor-windows-x64](https://github.com/kenproxx/edit-video/actions/runs/38279410582/artifacts/11761010783): 130,413,716 bytes, GitHub metadata digest `sha256:bbd2e4ff49f5ca6cffd2a76ac4e38e60ee3345b5d3daf2946023b778ce917e33`, chưa expired. Có EXE và giấy phép/checksum. Không tạo/publish release mới trong phase này.
