# Thiết kế Video Editor — phase 1

## Mục tiêu và phạm vi

App desktop Python cho Windows 10/11 x64, chỉnh một video mỗi lần và xuất video mới. Người dùng chọn video, các hiệu ứng và thư mục xuất. EXE chạy độc lập, không yêu cầu cài Python hoặc FFmpeg. Tham khảo cấu trúc `kenproxx/facebook-scheduler`: `main.py`, package `app/`, CustomTkinter, worker nền và script build.

Không gồm timeline nhiều clip, xử lý hàng loạt, đăng mạng xã hội hoặc GPU trong phiên bản đầu.

## Giao diện và luồng sử dụng

Chọn video → đọc thông tin → chọn hiệu ứng trên ảnh xem trước → chọn thư mục xuất → xuất. Màn hình có vùng chọn file, preview, các nhóm tùy chọn cuộn được và thanh tiến trình/hủy luôn nhìn thấy.

Preview là ảnh khung hình, có thanh chọn thời điểm; không phải trình phát realtime. Preview phản ánh các hiệu ứng bằng cùng cấu hình xử lý như xuất. Người dùng chọn vùng crop trên ảnh nguồn sau lật; vùng blur, watermark và chữ trên ảnh sau crop. Khi thay crop/lật, các vùng phụ thuộc phải được kiểm tra lại, không giữ tọa độ sai một cách im lặng. Tọa độ hiển thị được ánh xạ về pixel thực, không bao gồm viền letterbox. Giao diện tiếng Việt.

## Tính năng

- Tốc độ: 0.25–4 lần; audio đi cùng tốc độ, giữ cao độ. Video không audio vẫn xuất được.
- Lật: ngang, dọc hoặc cả hai.
- Crop: kéo vùng chữ nhật hoặc nhập x/y/rộng/cao; có preset 9:16, 16:9, 1:1. Crop không kéo giãn ảnh; kích thước xuất làm tròn phù hợp encoder, vùng phải nằm trong ảnh.
- Text đầu video: chèn chữ trên các khung hình đầu, mặc định 1 giây theo thời gian video đầu ra, chỉnh được và không vượt thời lượng đầu ra. Không thêm khung hình, không kéo dài video. Hỗ trợ tiếng Việt, xuống dòng, font, màu chữ/viền, kích thước và vị trí. Font mặc định lấy từ Windows có tiếng Việt; cho phép chọn file TTF/OTF.
- Watermark: một logo PNG/JPEG và một text tùy chọn, xuất hiện toàn video; chọn vị trí, kích thước, độ trong suốt. Logo giữ tỷ lệ và alpha nếu có.
- Blur: một vùng chữ nhật cố định suốt video, có mức làm mờ. Tọa độ tính trên video sau crop; không theo dõi vật thể.
- Xuất: MP4 H.264/AAC, giữ frame rate hợp lệ của nguồn, chất lượng mặc định CRF 20/preset medium, pixel format yuv420p và faststart. Bản đầu xử lý video SDR thông thường; nguồn HDR được báo không hỗ trợ thay vì âm thầm xuất sai màu. Dùng video stream đầu tiên và audio stream đầu tiên nếu có, không sao chép subtitle hay metadata riêng.

Thứ tự: chuẩn hóa orientation nguồn → lật → crop → tốc độ → blur → watermark → text đầu video. Blur không làm mờ watermark hay chữ. Preview và tọa độ dùng cùng orientation với xuất.

## File đầu vào/đầu ra và lỗi

Nhận MP4, MOV, MKV, AVI, WEBM khi FFmpeg đọc được. Đọc thông tin bằng ffprobe; lỗi codec/file hỏng được hiển thị trước khi xuất nếu phát hiện được. Chọn thư mục xuất bắt buộc, tên mặc định là tên thân input với đuôi `.mp4`, cho phép sửa tên.

Không bao giờ ghi đè input, kể cả chọn chính thư mục nguồn. Nếu output trùng input, yêu cầu đổi tên/thư mục. Output đã tồn tại cần xác nhận ghi đè. Render vào file tạm duy nhất trong thư mục output rồi thay thế đích khi thành công; thất bại/hủy xóa file tạm của tác vụ, giữ nguyên file đích cũ. Kiểm tra lại xung đột trước thay thế, không tự ghi đè file mới xuất hiện.

Kiểm tra tốc độ, vùng, thời lượng text, asset/font và quyền ghi trước chạy. Không tạo shell command từ nội dung text hoặc đường dẫn. Worker dùng subprocess argument list; text được rasterize thành overlay PNG bằng Pillow để hỗ trợ Unicode và tránh lỗi escape filter. Lỗi FFmpeg hiển thị thông báo ngắn, log có chi tiết chẩn đoán, không ghi nội dung video.

## Kiến trúc

- `main.py`: khởi động app; không tự pip install lúc người dùng chạy EXE.
- `app/models.py`: cấu hình chỉnh sửa và kiểm tra giá trị.
- `app/media.py`: tìm FFmpeg/ffprobe bundled, đọc metadata và tạo ảnh preview.
- `app/render.py`: xây filter graph, overlay assets, render và xử lý file tạm.
- `app/worker.py`: tác vụ nền, progress, hủy và hàng đợi event có giới hạn.
- `app/ui.py` và các widget tập trung: form, preview, ánh xạ vùng chọn.
- `app/resources.py`: đường dẫn tài nguyên khi chạy source hoặc PyInstaller.
- `scripts/`: bootstrap và build; `tests/`: kiểm thử logic và tích hợp media.

UI chỉ cập nhật trên main thread qua queue/after. Chỉ một render chạy tại một thời điểm. Preview chạy nền, debounce và loại kết quả cũ. Hủy dừng tiến trình FFmpeg, chờ/kill có giới hạn rồi dọn tài nguyên. File tạm overlay và log nằm ở thư mục user phù hợp, không yêu cầu quyền admin.

## Build và dependencies

Python + CustomTkinter + Pillow + FFmpeg/ffprobe + PyInstaller; khóa phiên bản dependencies khi triển khai. Cung cấp `build.bat` làm entry point Windows và `build.sh` cho Git Bash trên Windows, dùng chung bootstrap PowerShell. Bootstrap tự tải Python riêng cho build nếu chưa có phiên bản phù hợp, tạo môi trường cô lập, cài dependencies, tải FFmpeg/ffprobe và đóng gói `dist/VideoEditor.exe` dạng onefile/windowed. Không sửa Python hệ thống hoặc yêu cầu người dùng cài thủ công các dependencies.

Downloads dùng TLS, phiên bản cố định và kiểm tra hash từ nguồn phát hành tin cậy; Python kiểm tra chữ ký phát hành khi dùng installer. FFmpeg bundle phải có codec/filter cần thiết và kèm thông tin giấy phép phân phối. Build thất bại rõ ràng nếu platform không phải Windows x64 hoặc kiểm tra integrity thất bại. Không hứa build Windows EXE trực tiếp bằng PyInstaller trên Linux. Có thể cung cấp workflow Windows CI để build tự động; không tự đẩy/publish release.

Máy người dùng cuối chạy EXE offline; kết nối mạng chỉ cần lúc bootstrap build. Source dev có script cài dependencies riêng. Cloud Linux kiểm thử logic, FFmpeg và GUI bằng virtual display nếu khả dụng; Windows runner cần để xác thực EXE.

## Kiểm chứng và tiêu chí hoàn tất

Unit tests cho validation, tọa độ preview/crop, filter graph, tên output và chống ghi đè input. Integration tests tạo clip ngắn có audio bằng FFmpeg: tốc độ thay đúng thời lượng video/audio; lật/crop đúng pixel/kích thước; overlay chữ tiếng Việt đúng thời gian; logo alpha và vùng blur đúng vị trí; video không audio; tên file Unicode/khoảng trắng; hủy/lỗi giữ file đích cũ và không sót file tạm. Không chỉ kiểm tra file tồn tại: dùng ffprobe, trích frame và audio để kiểm tra kết quả thực.

GUI smoke test cho chọn video, cập nhật preview, validation, worker/progress/hủy. Windows build kiểm tra bootstrap trên máy chưa có Python/FFmpeg, chạy EXE với PATH không cung cấp hai công cụ này và xuất clip mẫu. Nếu không có Windows runner, báo phần kiểm chứng EXE chưa chạy, không gọi EXE đã được xác thực.

## Các phase tiếp theo

1. Phase 1 hiện tại: duyệt đặc tả, sau đó lập kế hoạch triển khai theo phase.
2. Phase 2: model, probe, preview engine, render và kiểm thử tích hợp.
3. Phase 3: UI, thao tác vùng chọn, progress/hủy và GUI smoke test.
4. Phase 4: bootstrap/build tự động, tài liệu chạy/build, Windows EXE validation.

Mỗi phase báo thay đổi, kết quả kiểm chứng và giới hạn còn lại ngắn gọn. Bảo toàn phạm vi đã duyệt; thay đổi làm phát sinh kiến trúc mới cần cập nhật thiết kế.
