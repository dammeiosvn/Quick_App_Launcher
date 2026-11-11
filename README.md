# Quick App Launcher

Bản thử **2.5.0-beta.5** của Quick App Launcher, © Sentechtipsvn.

Beta.5 sửa đầu vào rỗng ở bước Thay thế văn bản khi thêm app từ App Store, thêm emoji cho các menu phụ và bổ sung hướng dẫn mở nhanh sau khi plugin chạy xong. Menu chính giữ vCard Sáng/Tối.

## Sử dụng bản thử

1. Tải [tệp beta.5 đã ký](shortcuts/Quick-App-Launcher-v2.5.0-beta.5.shortcut) và mở trong Phím tắt. Nếu tự dựng, tải [phím tắt beta chưa ký](shortcuts/Quick-App-Launcher-v2.5.0-beta.5.unsigned.shortcut), ký bằng [Shortcuty](https://sign.shortcuty.app/) rồi tải tệp đã ký. Có thể đặt tên **Quick App Launcher Beta** để chạy song song với v2.4.
2. Lần đầu chạy, bấm **Tải dữ liệu**. Cấp quyền truy cập GitHub và iCloud Drive nếu iOS hỏi.
3. Sau thông báo đã lưu, chạy lại và chọn ngôn ngữ nếu chưa có. Menu vCard gồm **Mở ứng dụng**, **Thêm ứng dụng**, **Quản lý danh sách**, **Dữ liệu & sao lưu** và **Cài đặt**.
4. Vào **Dữ liệu & sao lưu → Tải hoặc cập nhật dữ liệu** khi cần tải lại gói. Phím tắt dùng kho dữ liệu công khai trong **iCloud Drive → Quick App Launcher Data**.

## Plugin và mở nhanh

- Mở ứng dụng kiểm tra tên `Plugin_Quickapplauncher` mỗi lần, kể cả đã lưu cờ hướng dẫn. Thiếu plugin thì hiện cảnh báo và mở [link tải](https://www.icloud.com/shortcuts/abe06a3f96834c369d5a5bcd6b22a32e). Cài xong giữ nguyên tên và chạy lại Mở ứng dụng.
- Khi plugin trả quyền điều khiển, menu hướng dẫn xuất hiện nếu chưa có `Quick App Launcher/QuickAccessHint-v1.txt` trong iCloud Drive.
- Chọn Màn hình chính mở action thêm icon hiện có. Khi action trả về, lưu cờ `home_screen`. Cờ ghi nhận đã chọn hướng dẫn, không chứng minh iOS đã thêm icon. Nếu chưa tải icon dữ liệu, hiển thị hướng dẫn và mở trình sửa plugin để thêm thủ công.
- Control Center hiển thị hướng dẫn thao tác thủ công cho iOS 18 trở lên. Để sau và xem hướng dẫn Control Center không lưu cờ. Có thể thêm lại icon qua Cài đặt → Màn hình chính.
- Không hiện hướng dẫn mở nhanh sau thao tác thêm/xóa/đổi icon ứng dụng. Thư mục cá nhân luôn được tạo cả khi chưa tải gói dữ liệu.

## Dữ liệu và tương thích

- Dữ liệu công khai gồm 37 bộ ngôn ngữ, menu vCard Sáng/Tối, icon màn hình chính và 66 thẻ ứng dụng hệ thống. Các nhãn mới dùng tiếng Việt hoặc tiếng Anh, kèm bản dịch cũ cho các chức năng đã có.
- Luồng tải kiểm tra phiên bản định dạng và SHA-256 trước khi giải nén. Bản mới được lưu vào thư mục riêng, kiểm tra đủ sáu tệp, rồi mới ghi dấu kích hoạt. Khi thiếu tệp lõi hoặc tệp giao diện Sáng hay Tối đang dùng, phím tắt thử gói dự phòng. Mở menu đã lưu đọc từ iCloud Drive.
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

Kiểm tra đầu vào của action Đếm, các nhánh menu và bước xác minh tệp iCloud trước khi ký.

~~~sh
python3 tests/check_dispatch.py shortcuts/Quick-App-Launcher-v2.5.0-beta.5.unsigned.shortcut
~~~

- Tải dữ liệu lần đầu, chuyển sang Sáng/Tối và mở lại với mạng tắt khi tệp đã có trên máy.
- Chạy beta trên máy đã dùng v2.4 và kiểm tra ngôn ngữ, icon riêng, giới hạn và danh sách app.
- Thêm một app hệ thống và một app từ App Store, thử tên trùng, mở app, đổi icon và thử xóa mục được chọn.
- Ngắt mạng giữa lần tải lại, mở lại menu để xác nhận bản đã lưu vẫn dùng được. Kiểm tra sao lưu và khôi phục trên một danh sách thử.

Kiểm tra mô phỏng (không thay thế thử trên iPhone):

~~~sh
python3 tests/flow_model.py
python3 tests/test_plugin_flow.py
~~~
