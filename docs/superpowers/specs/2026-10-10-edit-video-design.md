# Đặc tả ứng dụng Edit Video cho Windows

Ngày: 10/10/2026. Repo: https://github.com/kenproxx/edit-video.
Trạng thái: thiết kế trong hội thoại đã được duyệt; bản đặc tả này chờ duyệt trước khi lập kế hoạch triển khai.

## 1. Mục tiêu và phạm vi

Ứng dụng desktop viết bằng Python, giao diện tiếng Việt, dành cho Windows 10/11 x64. Người dùng chọn một video, chỉnh các hiệu ứng, chọn thư mục và xuất video mới. Chạy bản phân phối không cần cài Python hoặc FFmpeg riêng. Xử lý media tại máy, không tải video lên dịch vụ.

Các chức năng đã thống nhất: tốc độ, lật ngang/dọc, crop, logo/text watermark, làm mờ một vùng cố định, ảnh bìa có chữ và xuất video. Ảnh bìa là JPG/PNG riêng lấy từ một khung hình, không chèn vào đầu video. Bản đầu xử lý một video mỗi lần; không có timeline nhiều clip, xử lý hàng loạt, tracking vùng mờ hay đăng TikTok tự động.

## 2. Công nghệ và ranh giới thành phần

Chọn PySide6 cho giao diện và thao tác trực quan; FFmpeg/ffprobe cho đọc thông tin, lấy khung hình và render; PyInstaller đóng gói Windows. Tkinter ít phù hợp thao tác vùng trên preview, còn MoviePy không cần thiết khi xử lý trực tiếp qua FFmpeg.

Các thành phần độc lập:

- `models`: thông tin media, thiết lập hiệu ứng và kiểm tra giá trị hợp lệ; không phụ thuộc widget.
- `media`: tìm binary được đóng gói, đọc metadata và chuẩn hóa hướng hiển thị video.
- `render`: dựng chuỗi filter và tham số xuất từ cấu hình; dùng chung quy tắc hình ảnh cho preview và xuất.
- `jobs`: chạy tiến trình nền, báo tiến độ, hủy tác vụ, quản lý file tạm và công bố kết quả.
- `ui`: chọn file, điều khiển thiết lập, preview và chuyển đổi tọa độ chuột sang tọa độ ảnh.
- `thumbnail`: kết xuất chữ và ảnh bìa; dùng cùng cơ chế vẽ chữ cho text watermark để hỗ trợ tiếng Việt.
- `packaging`: script bootstrap, cấu hình đóng gói, kiểm tra binary và workflow Windows.

Không gọi shell để ghép lệnh FFmpeg; truyền danh sách đối số để xử lý tên file có dấu, khoảng trắng và ký tự đặc biệt. Không đưa trực tiếp nội dung người dùng vào biểu thức filter.

## 3. Luồng sử dụng và giao diện

1. Chọn video bằng hộp thoại. ffprobe đọc kích thước hiển thị, thời lượng, hướng xoay và audio. Báo lỗi rõ ràng nếu media không đọc được hoặc không có video.
2. Khu vực giữa hiển thị khung hình với thanh kéo thời gian theo video nguồn. Xem trước là khung hình tĩnh được cập nhật khi đổi thời gian/thiết lập, không yêu cầu phát liên tục thời gian thực.
3. Bảng bên cạnh chia nhóm tốc độ/lật, crop, vùng mờ, watermark và ảnh bìa. Có thao tác đặt lại thiết lập.
4. Người dùng kéo vùng crop/mờ và vị trí lớp phủ trên preview; cũng có ô nhập số để chỉnh chính xác. Phần viền letterbox không tính vào tọa độ ảnh.
5. Chọn thư mục xuất, xem tên đích và nhấn xuất video hoặc xuất ảnh bìa. Hiển thị tiến độ, nút hủy và đường dẫn thành phẩm khi thành công.

Các tác vụ đọc/render chạy nền, không làm đứng giao diện. Preview mới thay thế yêu cầu cũ; kết quả của cấu hình cũ không được ghi lên preview hiện tại. Khi xuất, chụp một bản cấu hình cố định và khóa các thao tác gây thay đổi nguồn/cấu hình cho tới khi xong hoặc hủy.

## 4. Hành vi chỉnh sửa

### Hệ tọa độ và thứ tự xử lý

Chuẩn hóa rotation metadata và tỷ lệ pixel về hình ảnh hiển thị, sau đó crop → lật → làm mờ → logo/text watermark. Cuối cùng thay đổi thời gian và mã hóa. Kích thước đầu ra được điều chỉnh xuống số chẵn hợp lệ cho H.264 yuv420p, thể hiện đúng trong preview.

Vùng crop định nghĩa trên ảnh nguồn đã chuẩn hóa hướng, có chế độ xem ảnh nguồn riêng khi chọn crop. Vùng mờ và lớp phủ định nghĩa theo ảnh sau crop/lật; UI lưu tọa độ tương đối trong khoảng 0–1 và đổi sang pixel lúc render. Thay đổi crop giữ vị trí tương đối của vùng mờ/lớp phủ và cập nhật preview. Các hình chữ nhật phải nằm trong ảnh và có diện tích dương.

### Tốc độ, crop và lật

- Tốc độ 0,25×–4×, mặc định 1×; thời lượng đầu ra bằng thời lượng nguồn chia tốc độ, trong sai số mã hóa.
- Nếu có âm thanh, đổi tempo đồng bộ và giữ cao độ; video không có audio vẫn xuất bình thường. Chọn video stream chính và audio stream đầu tiên nếu có; không đưa các stream phụ vào bản xuất đầu tiên.
- Hai tùy chọn lật ngang/dọc độc lập, mặc định tắt.
- Crop tự do và preset 9:16, 16:9, 1:1; người dùng di chuyển/đổi kích thước vùng. Mặc định dùng toàn bộ ảnh.

### Watermark và làm mờ

- Một logo PNG/JPG, hỗ trợ alpha của PNG; chỉnh vị trí, kích thước và độ trong suốt, giữ tỷ lệ logo.
- Một lớp text watermark, hỗ trợ nhiều dòng, tiếng Việt, font, cỡ chữ, màu, viền và độ trong suốt; có thể dùng cùng logo.
- Một hình chữ nhật làm mờ cố định xuyên suốt video; chỉnh vị trí, kích thước và cường độ. Lớp phủ watermark được đặt sau vùng mờ nên không bị làm mờ.
- Chữ được vẽ ra lớp ảnh trong suốt bằng Qt với font đã chọn, sau đó overlay; preview và bản xuất dùng cùng asset và quy tắc bố trí.

### Ảnh bìa riêng

- Chọn thời điểm nguồn trên thanh kéo; lấy khung hình đã áp dụng crop, lật, vùng mờ và watermark hiện tại.
- Thêm lớp chữ bìa riêng: nội dung nhiều dòng, font hỗ trợ tiếng Việt, cỡ chữ, màu, viền và vị trí kéo thả. Lớp chữ bìa không xuất hiện trong video.
- Xuất PNG mặc định hoặc JPG theo lựa chọn. Kích thước bằng khung video đã chỉnh; JPG có chất lượng mặc định cao.
- Tên mặc định `<tên-gốc>_thumbnail.png` hoặc `.jpg`, cùng thư mục xuất được chọn. Xuất ảnh độc lập, không cần render video trước.

## 5. Xuất file, an toàn dữ liệu và lỗi

- Video đầu ra MP4, H.264, yuv420p, âm thanh AAC nếu có; bật faststart. Dùng CPU để hoạt động mà không yêu cầu GPU cụ thể.
- Tên mặc định `<tên-gốc>.mp4`; giữ nguyên phần tên, đổi phần mở rộng nếu nguồn khác MP4. Cho phép sửa tên trước khi xuất.
- Luôn chặn đích trùng chính file nguồn, kể cả người dùng chọn ghi đè. Nếu trùng một file khác, yêu cầu chọn tên mới hoặc xác nhận ghi đè file đó.
- Render vào file tạm duy nhất trong thư mục đích; chỉ thay thế/công bố file đích sau khi FFmpeg thành công và xác minh output đọc được. Khi lỗi/hủy, giữ file đích cũ và xóa file tạm của tác vụ.
- Hủy sẽ dừng tiến trình đang chạy, có bước buộc dừng sau khoảng chờ giới hạn nếu cần; không để FFmpeg chạy mồ côi khi đóng app.
- Kiểm tra quyền ghi, tham số và binary trước khi chạy. Khi hết dung lượng, codec không hỗ trợ hoặc FFmpeg lỗi, hiện thông báo tiếng Việt kèm khả năng xem chi tiết log.
- Tiến độ video tính theo timestamp đầu ra và thời lượng sau đổi tốc độ; không báo hoàn tất trước khi kiểm tra và công bố file.

## 6. Build và phân phối

- `build_exe.bat` là điểm vào Windows; `build_exe.sh` là wrapper cho Git Bash trên Windows, cùng gọi một bootstrap PowerShell. Không yêu cầu người dùng tự cài Bash để dùng bản `.bat`.
- Máy build cần Windows x64 và Internet lần đầu. Script tự tải runtime Python riêng vào thư mục build, chuẩn bị pip, cài dependencies, tải FFmpeg/ffprobe rồi chạy PyInstaller; không phụ thuộc Python/FFmpeg trong PATH và không cần thay đổi cài đặt Python toàn hệ thống.
- Phiên bản và SHA-256 của các bộ tải về được cố định trong mã cấu hình build; kiểm tra hash trước khi giải nén/chạy, dừng với thông báo rõ nếu sai hoặc tải thất bại. Các bản cụ thể sẽ được xác minh khi lập kế hoạch/triển khai.
- Phân phối portable dạng ZIP chứa `EditVideo.exe`, runtime, Qt và các binary cần thiết. Người dùng giải nén toàn bộ rồi chạy EXE, không cài thêm thư viện. Không yêu cầu một EXE đơn lẻ tự giải nén.
- Đóng gói thông báo và giấy phép bên thứ ba tương ứng với bản Qt/FFmpeg đã chọn. Không tự thay đổi giấy phép mã nguồn repo khi chưa có quyết định của chủ repo.
- GitHub Actions trên Windows kiểm thử và build, lưu ZIP làm artifact tải về. README tiếng Việt hướng dẫn chạy app, build bằng một lệnh và tải artifact.

## 7. Tiêu chí nghiệm thu

1. Chọn được video đường dẫn Unicode/có khoảng trắng; đọc đúng video dọc có rotation metadata và video không audio.
2. Video mẫu có mốc hình/âm cho thấy đúng tốc độ 0,25×, 1×, 4×, thời lượng và đồng bộ audio trong sai số một frame cộng độ trễ codec.
3. Fixture có góc màu phân biệt xác nhận crop/lật đúng, vùng mờ chỉ tác động vùng chọn, logo/text đúng vị trí; phối hợp tất cả hiệu ứng thành công.
4. Preview và file xuất thống nhất hệ tọa độ, bố cục, nội dung chữ tiếng Việt; chấp nhận sai khác do nén video/JPG.
5. Ảnh bìa đúng khung hình, có chữ riêng, đúng định dạng/kích thước; video không chứa chữ bìa.
6. Kiểm tra tên mặc định, chống đè nguồn, xác nhận trùng đích, lỗi quyền ghi, hủy xuất và giữ file cũ khi render thất bại.
7. Giao diện vẫn phản hồi khi render; không hiển thị preview lỗi thời; đóng cửa sổ không để tiến trình con tiếp tục chạy.
8. Build Windows từ môi trường không có Python/FFmpeg trong PATH; chạy app đóng gói và xử lý video fixture bằng binary đi kèm. Kiểm tra giao diện thủ công trên Windows phải được ghi nhận riêng nếu môi trường CI không đủ để xác minh.

## 8. Bàn giao và trạng thái phê duyệt

Bàn giao mã nguồn, kiểm thử, README tiếng Việt, script build và workflow vào repo đã chỉ định. Báo chính xác commit/nhánh, kết quả CI và vị trí artifact; không coi kiểm thử Linux là bằng chứng EXE chạy được trên Windows.

Người dùng đã chọn ảnh bìa riêng và duyệt thiết kế trong hội thoại. Bước tiếp theo là duyệt tài liệu này, sau đó viết kế hoạch triển khai theo Superpowers; chưa bắt đầu viết mã ứng dụng ở giai đoạn đặc tả.
