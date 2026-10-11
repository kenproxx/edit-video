# Báo cáo phase 4 — bootstrap và đóng gói Windows

Đã viết `build.bat`, `build.sh` (Windows Git Bash), bootstrap PowerShell và `VideoEditor.spec` cho onefile/windowed `dist/VideoEditor.exe`. Máy build không cần cài Python/FFmpeg riêng: Python chính thức được tải khi chưa có bản phù hợp, kiểm tra SHA-256 + Authenticode, không thêm PATH/launcher/association; venv cô lập được tạo lại. Tất cả wheel runtime/build và transitive dependencies đã khóa phiên bản và hash. FFmpeg/ffprobe static được tải, kiểm tra hash, giải nén lại từ archive đã xác thực, kiểm tra codec/filter và bundle cùng dữ liệu CustomTkinter, license, manifest.

Startup của app không cài package. CLI `--smoke-test INPUT --output-dir DIR --report FILE` chạy engine không mở Tk; `--gui-smoke-test --report FILE` mở/đóng GUI. Report JSON dùng được với EXE windowed không có stdout. File report được tạo độc quyền trước xử lý; cần đường dẫn mới và thư mục cha có sẵn, không được trùng output. Smoke test dùng cơ chế bảo vệ input/output thật của worker.

## Kiểm chứng đã thực hiện trên Linux

- Tests mới RED: tám packaging case thất bại ở phần còn thiếu; license collector test thất bại trước triển khai.
- Packaging suite: **11 passed in 4.67s**; full suite với GUI Tk8.6/Xvfb + FFmpeg thật: **102 passed in 49.04s**, không skip. Kiểm chứng input/output Unicode, codec/thời lượng, collision giữ input, thiếu/corrupt bundled tools không fallback PATH, dữ liệu user ngoài bundle, build từ chối Linux, cache sửa bị từ chối và cache hợp lệ kiểm tra lại được.
- `pip download --require-hashes --only-binary=:all: --platform win_amd64 --python-version 313 --implementation cp --abi cp313 -r requirements-build.txt` tải đủ **11 wheel** từ PyPI và kiểm tra hash; không cài/chạy wheel Windows trên Linux.
- ZIP FFmpeg 8.1.2 tải thực tế, SHA-256 khớp digest upstream GitHub release; đã đọc README/license và build configuration.
- SHA-256 installer Python 3.13.12 x64 khớp manifest WinGet; **chưa tải/chạy installer** vì `www.python.org` bị proxy cloud từ chối (403). Không bypass TLS/proxy hoặc bỏ verification.
- PowerShell 7.5.4 Linux tải từ release Microsoft, xác thực SHA-256 của upstream; chạy các kiểm tra cache và từ chối platform. Không thay thế kiểm chứng PowerShell 5.1/installer trên Windows.
- Chạy lại `scripts/setup-dev.sh`: exit 0. Lệnh readiness headless được lưu trong draft: **71 passed in 16.93s**. `git diff --check` sạch.

Lệnh full suite cloud dùng Tk8.6 shim đã nêu ở báo cáo phase 3, thêm writable XDG directories cho PowerShell:

```bash
PYTHONPATH=/tmp/edit-video-tk86 \
XDG_CACHE_HOME=/tmp/edit-video-pwsh-cache \
XDG_CONFIG_HOME=/tmp/edit-video-pwsh-config \
XDG_DATA_HOME=/tmp/edit-video-pwsh-data \
PATH="/tmp/edit-video-display-root/usr/bin:$PATH" \
/tmp/edit-video-display-root/usr/bin/xvfb-run -a .venv/bin/python -m pytest -q
```

## Phần còn chờ

**Chưa có Windows executor nên chưa tạo EXE, chưa chạy bootstrap Windows hai lần, Authenticode, EXE offline/PATH giới hạn, Unicode trên NTFS, thư mục app chỉ đọc hoặc GUI native Windows.** Workflow Windows đã viết đủ các bước này; artifact chỉ xuất khi chúng thành công. Không có đường dẫn EXE đã build trong phiên này, không dùng PyInstaller Linux thay thế.

FFmpeg static build là GPL v3. Full license/config/source link được giữ nguyên, Roboto Apache-2.0 và các license wheel/runtime được thu thập. **Complete corresponding source cho FFmpeg cùng external libraries/build scripts chưa có**, nên public redistribution vẫn chờ bổ sung bundle đó. Không có release publication hoặc push được thực hiện.

## Quyết định triển khai và môi trường

- Bootstrap Windows dùng **Python 3.13.12** có installer chính thức thay cho dòng source dev 3.12; runtime pins hỗ trợ cả hai. Linux dev vẫn giữ 3.12; Windows tương thích thực tế phải qua CI.
- Chọn Gyan **FFmpeg 8.1.2 essentials** ZIP static thay full build; build phải xác nhận libx264/AAC và các filter đang dùng, thiếu sẽ dừng.
- Cài package vào venv mới mỗi build; cache tải xuống chỉ dùng sau hash validation. Không sửa Python hệ thống.
- Hướng dẫn setup/start và explicit domain `www.python.org` đã lưu vào environment draft; package-manager presets được giữ. Draft yêu cầu người dùng **review/save rồi publish trong Environment settings**; chưa áp dụng vào runtime và chưa xác nhận restoration ở task mới.
- Cloud không cần dịch vụ chạy thường trực; Xvfb, Tk8.6 shim và PowerShell local dùng cho kiểm chứng, không bundle vào Windows app.

## Review toàn nhánh

Reviewer độc lập kiểm tra bootstrap/spec/CI, CLI/license và các contract engine/UI; tự chạy 11 packaging tests qua, kiểm tra đủ license metadata của 11 wheel Windows. Không có Critical; một Important: report CLI có thể ghi đè input, output hoặc file report cũ. Ba regression test tái hiện đều RED trước sửa; một lượt sửa tạo report độc quyền trước export, từ chối trùng output và giữ handle đã reserve, không mở lại đường dẫn để ghi. Không có Minor bị hoãn.

Windows PowerShell 5.1, installer/Authenticode, Windows PyInstaller/EXE/GUI/ACL vẫn chưa được kiểm chứng. Ruling: giữ nguyên các hạng mục này ở trạng thái pending, không suy từ kết quả Linux hoặc review code thành validated Windows. Ruling: giữ complete matching FFmpeg source pending và chưa phân phối binary; license/link core không thay thế corresponding source.

Đã giữ nhánh `work` và checkout hiện tại theo yêu cầu commit/báo cáo từng phase; không merge/push. Ledger được giữ vì acceptance Windows còn pending. Kết quả suite cuối sau sửa ghi bên dưới.

Kết quả cuối sau review fix: **105 passed in 73.50s**, full suite có GUI thật và PowerShell cache tests, không skip/warning pytest. Ba regression report RED→GREEN; `git diff --check` sạch. Đây là kiểm chứng Linux/source và logic bootstrap khả dụng, không phải bằng chứng đã tạo hoặc chạy Windows EXE.

## Sửa lỗi bootstrap khi chạy từ Windows PowerShell

Sau merge, người dùng báo `Join-Path ... Path ... empty string` ngay khi mở `build.sh`/`build.bat`. Giá trị mặc định của `CacheDir`/`ManifestPath` gọi `Join-Path $PSScriptRoot` trong `param()`, khi script root chưa được gán trong ngữ cảnh bind tham số đó. Đã bỏ phép tính khỏi `param()`, xác định script directory trong thân script (fallback qua `MyInvocation.MyCommand.Path`), rồi mới gán các đường dẫn mặc định. Hai launcher dùng chung bootstrap nên cùng nhận bản sửa.

Regression thực thi chính param block của production với script root rỗng: RED lỗi `Join-Path`, GREEN sau sửa. Test thứ hai chạy bản sao script ở đường dẫn Unicode/khoảng trắng từ cwd khác, xác nhận default manifest/cache thuộc project và không tạo file ở cwd. Hai test chạy qua trên PowerShell 7 Linux; không thay thế kiểm chứng toàn bộ installer/EXE Windows.

Full suite sau bản sửa bootstrap: **107 passed in 36.67s**, không skip. Kiểm chứng dùng Python 3.13/Tk8.6 hệ thống, virtual display Xvfb và PowerShell 7 trên Linux.
