# Phase 9 — Giữ nguyên video khi không đủ dài để cắt

Ngày 2026-10-14. Yêu cầu: cùng khoảng cắt cho video đơn/hàng loạt, video ngắn hơn mốc tới giữ nguyên toàn bộ, video đủ dài cắt bình thường. Không thay tốc độ hay các hiệu ứng khác.

source_interval kiểm tra cấu hình hữu hạn/không âm và tới > từ trước. Khoảng hợp lệ nhưng tới vượt thời lượng nguồn (hoặc từ nằm ngoài nguồn khi tới để mặc định) trả khoảng toàn bộ 0..duration. Nếu tới đúng cuối video thì vẫn cắt vì đủ dài. Dùng resolver chung cho validate, output duration/intro, video/audio pipeline, preview và batch, không ghi đè hoặc sửa tùy chọn người dùng.

Regression source/FFmpeg/batch: 6 failed/2 passed trước sửa; sau sửa toàn bộ trim/batch38passed. Giữ test từ/tới đảo ngược và số âm/NaN/infinity là lỗi; bỏ expectation cũ coi video ngắn là cấu hình sai. Batch thực source4s/8s, khoảng1..6, speed2 cho output2s/2.5s; cả hai thành công kể cả dùng reference ngắn. CLI test RED missing flags; packaged smoke bổ sung short/long source để kiểm chứng rule trong EXE Windows.

Review độc lập không có Critical/Important/Minor; không cần fix pass. Full suite **242 passed in113.54s**, không skip/warning/timeout hay stack dump; diff check sạch. Windows/version acceptance **SUCCESS**: tag v0.2.2, [run38507642747](https://github.com/kenproxx/edit-video/actions/runs/38507642747), code3b58d35. Native build/repeat/cache và toàn bộ EXE checks qua, gồm batch source2s/5s chọn1..4, speed2; kiểm tra output short1s (giữ toàn bộ) và long1.5s (cắt3s nguồn). Workflow tự tạo draft và gắn đủ bốn asset; API xác nhận target đúng codeSHA, tất cả uploaded/digest SHA256. Release v0.2.2 ID412319085 vẫn draft theo policy FFmpeg hiện có.
