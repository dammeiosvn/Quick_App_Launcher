# Quick App Launcher

Bản thử **2.5.0-beta.1** của Quick App Launcher, © Sentechtipsvn.

## Sử dụng bản thử

1. Ký tệp [phím tắt beta](shortcuts/Quick-App-Launcher-v2.5.0-beta.1.unsigned.shortcut) trên macOS theo lệnh bên dưới. Mở tệp đã ký trong Phím tắt và đặt tên **Quick App Launcher Beta** để chạy song song với v2.4.
2. Lần đầu chạy, bấm **Tải dữ liệu**. Cấp quyền truy cập GitHub và iCloud Drive nếu iOS hỏi.
3. Sau thông báo đã lưu, chạy lại và chọn ngôn ngữ nếu chưa có. Menu vCard gồm **Mở ứng dụng**, **Thêm ứng dụng**, **Quản lý danh sách**, **Dữ liệu & sao lưu** và **Cài đặt**.
4. Vào **Dữ liệu & sao lưu → Tải hoặc cập nhật dữ liệu** khi cần tải lại gói. Phím tắt dùng kho dữ liệu công khai trong **iCloud Drive → Quick App Launcher Data**.

Tệp trong repo là plist nhị phân chưa ký. Trên Mac đã đăng nhập iCloud, chạy lệnh sau từ thư mục repo để ký trước khi nhập trên iPhone.

~~~sh
shortcuts sign --mode anyone \
  --input shortcuts/Quick-App-Launcher-v2.5.0-beta.1.unsigned.shortcut \
  --output Quick-App-Launcher-Beta.shortcut
~~~

## Dữ liệu và tương thích

- Dữ liệu công khai gồm 37 bộ ngôn ngữ, menu vCard Sáng/Tối, icon màn hình chính và 66 thẻ ứng dụng hệ thống. Các nhãn mới dùng tiếng Việt hoặc tiếng Anh, kèm bản dịch cũ cho các chức năng đã có.
- Luồng tải kiểm tra phiên bản định dạng và SHA-256 trước khi giải nén. Bản mới được lưu vào thư mục riêng, kiểm tra đủ sáu tệp, rồi mới ghi dấu kích hoạt. Khi tệp lõi của bản hiện tại thiếu, phím tắt thử bản trước. Mở menu đã lưu đọc từ iCloud Drive.
- Gói dữ liệu và danh sách riêng được lưu riêng. Danh sách app, icon cá nhân, ngôn ngữ và giới hạn tiếp tục dùng các tệp trong **iCloud Drive → Quick App Launcher**. Sao lưu và đặt lại áp dụng cho thư mục cá nhân này. Bản beta đọc và sửa cùng danh sách với v2.4, vì vậy nên sao lưu trước khi thử xóa hoặc khôi phục.
- **Mở ứng dụng** và **App List** gọi `Plugin_Quickapplauncher`. Phần mở app của plugin và thao tác thêm vào màn hình chính cần kiểm thử trên iPhone. Để dùng offline, giữ các tệp iCloud cần thiết đã tải xuống máy. Tìm App Store vẫn cần mạng.

## Cập nhật gói dữ liệu

Sửa tệp nguồn trong [data](data) rồi đóng gói với số phiên bản mới. Gói và manifest được đưa lên cùng một commit.

~~~sh
python3 build_data.py --data-version 2
python3 build_data.py --check
~~~

`dist/manifest.json` là đầu mối tải. Mỗi tệp `launcher-data-vN.zip` có SHA-256 và phiên bản riêng. Phần dữ liệu gốc được chuyển từ repo công khai cũ và tệp v2.4 do tác giả cung cấp.

## Kiểm thử trên iPhone

- Tải dữ liệu lần đầu, chuyển sang Sáng/Tối và mở lại với mạng tắt khi tệp đã có trên máy.
- Chạy beta trên máy đã dùng v2.4 và kiểm tra ngôn ngữ, icon riêng, giới hạn và danh sách app.
- Thêm một app hệ thống và một app từ App Store, thử tên trùng, mở app, đổi icon và thử xóa mục được chọn.
- Ngắt mạng giữa lần tải lại, mở lại menu để xác nhận bản đã lưu vẫn dùng được. Kiểm tra sao lưu và khôi phục trên một danh sách thử.
