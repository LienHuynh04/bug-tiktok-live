# Hướng dẫn chạy "Nhà của Bug" trên TikTok LIVE Studio

Làm theo thứ tự 6 bước. Lần đầu mất khoảng 10 phút, các lần sau chỉ còn bước 1 → 4 → 6.

---

## Bước 0 — Chuẩn bị (chỉ làm 1 lần)

1. Cài **Python 3.11+** từ python.org, nhớ tick **Add Python to PATH**.
2. Tải **TikTok LIVE Studio** từ trang chính thức của TikTok (mục Download / LIVE Studio),
   cài và **đăng nhập đúng tài khoản kênh "IT có con mèo tên Bug"**.
   - LIVE Studio yêu cầu tài khoản đủ điều kiện mở LIVE (thường là 18+ và đạt ngưỡng
     người theo dõi theo chính sách hiện hành của TikTok). Nếu tài khoản chưa đủ điều
     kiện LIVE thì vẫn test được toàn bộ bằng chế độ DEMO ở bước 2.
3. Nếu bạn đã chạy bản cũ (v1) trước đây: **xóa thư mục `.venv`** trong thư mục
   bug-live rồi mới chạy lại BAT — để nó cài thêm thư viện giọng thật `edge-tts`.

## Bước 1 — Chạy app trên máy bạn

1. Bấm đúp **`BAT-LIVE.bat`** (Windows) hoặc `bash run.sh` (macOS/Linux).
2. Giữ nguyên cửa sổ đen đó suốt buổi live — **đóng là app tắt**.
3. Trang điều khiển tự mở tại http://localhost:3000

## Bước 2 — Kiểm tra trước khi live (khuyên làm mỗi lần)

1. Ở trang điều khiển, mục **3. Bảng giọng thật**: bấm **▶️ Nghe** ở giọng Hoài My
   và Nam Minh để nghe thử, bấm **Chọn giọng này** cho giọng bạn thích.
   Bấm **🐱 Nghe thử tiếng mèo** để nghe tiếng kêu mẫu.
2. Bấm **Chạy DEMO**: mở xem trước sân khấu ở mục 5, thấy mèo giả vào phòng,
   cho ăn, đua nhau, giọng đọc + tiếng mèo kêu phát ra là đạt.
3. Bấm **Tắt DEMO** trước khi sang bước tiếp theo.

## Bước 3 — Đưa sân khấu vào TikTok LIVE Studio

1. Mở **TikTok LIVE Studio** → chọn bố cục màn hình **dọc 9:16** (Portrait).
2. Ở panel **Nguồn (Sources)** → **Thêm nguồn (Add source)** → chọn **Link / Webpage**
   (tên gọi có thể là "Liên kết" tùy phiên bản/ngôn ngữ).
3. Nhập URL: **`http://lvh.me:3000/stage`**
   - Kích thước: **Width 1080 × Height 1920**. Kéo cho sân khấu phủ kín khung dọc.
   - Nếu LIVE Studio báo không tải được `lvh.me`, thử `http://localhost:3000/stage`.
     Cả hai đều trỏ về chính máy bạn, không phải máy chủ bên ngoài.
4. **Bật tiếng + bấm bật giọng (bắt buộc, làm 1 lần mỗi buổi):**
   - Nhấp chuột phải vào nguồn sân khấu → **Tương tác (Interact)** → cửa sổ sân khấu hiện ra
     → bấm nút vàng **"🔊 Bấm vào đây để bật giọng đọc + tiếng mèo kêu"** → đóng cửa sổ Interact.
   - Lý do: trình duyệt chỉ cho phát âm thanh sau khi có người bấm 1 lần. Không bấm là
     live vẫn chạy hình nhưng **câm tiếng**.
   - Kiểm tra thanh âm lượng của nguồn trong LIVE Studio không bị mute / kéo về 0.

## Bước 4 — Kết nối sự kiện TikTok

1. Trong LIVE Studio: đặt **tiêu đề live** (ví dụ: "🐱 Nhà của Bug — gõ MEOW nhận mèo,
   gõ ĐUA đua mèo cùng nhau!"), chọn chủ đề/giải trí, rồi bấm **Phát LIVE (Go LIVE)**.
2. Quay lại trang điều khiển (http://localhost:3000): nhập **username TikTok** của bạn
   → bấm **🔌 Kết nối**. Dòng trạng thái chuyển thành "Đã kết nối live" là xong.
   - Phải bấm Kết nối **sau khi đã Go LIVE** — chưa live thì thư viện không tìm thấy phòng.
3. Lấy điện thoại (tài khoản khác) vào xem live, comment "meow" để kiểm tra:
   mèo của bạn hiện trên sân khấu + có tiếng kêu + giọng đọc chào là đạt.

## Bước 5 — Trong lúc live

- Cứ treo máy, người xem tự chơi. Bạn chỉ cần thỉnh thoảng nhìn trang điều khiển.
- Muốn nói gì: ô **"Đọc ngay"** ở trang điều khiển — giọng đọc sẽ chen lên đọc trước.
- Muốn khuấy động: bấm **🏁 Bắt đầu đua ngay** hoặc **🌧️🐟 Mưa cá**.
- Giọng đọc + tiếng mèo kêu đi theo **âm thanh của nguồn sân khấu** trong LIVE Studio,
  người xem nghe được cùng hình. Mic của bạn không cần bật nếu chỉ treo live.

## Bước 6 — Kết thúc

1. Kết thúc live trong LIVE Studio.
2. Trang điều khiển: bấm **Ngắt kết nối**.
3. Đóng cửa sổ BAT (hoặc Ctrl+C). Điểm TOP đã tự lưu (data/scores.json) cho buổi sau.

---

## Xử lý sự cố thường gặp

| Hiện tượng | Nguyên nhân & cách xử lý |
|---|---|
| Sân khấu trong LIVE Studio đen/trắng xóa | App chưa chạy (quay lại bước 1), hoặc sai URL/cổng. Mở thử http://localhost:3000/stage bằng Chrome trên chính máy — không lên thì LIVE Studio cũng không lên. |
| Có hình, không có tiếng đọc/kêu | Chưa bấm nút bật giọng trong cửa sổ **Interact** (bước 3.4), hoặc nguồn bị mute trong LIVE Studio. |
| Nghe thử giọng ở trang điều khiển báo lỗi | Kiểm tra internet (giọng thật do Microsoft tạo online). Nếu mới nâng cấp từ v1: xóa `.venv` chạy lại BAT để cài `edge-tts`. Vẫn lỗi thì bấm **Đổi máy đọc → Trình duyệt** để dùng tạm giọng máy. |
| Bấm Kết nối mà không thấy sự kiện | (1) Chưa Go LIVE; (2) sai username; (3) TikTok vừa đổi API → cập nhật thư viện: mở thư mục bug-live, chạy `.venv\Scripts\pip install -U TikTokLive edge-tts` rồi chạy lại BAT. |
| Báo **UserNotFoundError** ("not capable of going LIVE… or does not exist") | Không phải lỗi code. Chỉ có 3 nguyên nhân: (1) **sai username** — phải lấy đúng @tên ở trang cá nhân (link tiktok.com/@…), đừng gõ tên hiển thị "IT có con mèo tên Bug"; (2) **chưa Go LIVE** — phải đang live mới kết nối được; (3) tài khoản **chưa từng live / chưa đủ điều kiện** mở LIVE. Thử nhanh: phát live bằng điện thoại 1 phút rồi bấm Kết nối trong lúc đang live. |
| Báo **ValueError: invalid literal for int() with base 10: ''** | TikTok trả về một trường số bị rỗng. Thường gặp nhất khi tài khoản chưa được mở LIVE (chưa đủ 1.000 followers) hoặc chưa từng phát live — không có phòng live để lấy dữ liệu. Bản app mới nhất đã vá: các sự kiện tim/quà có field rỗng sẽ bị bỏ qua thay vì làm rớt kết nối, và thông báo lỗi đã được dịch rõ. Hãy dùng bản ZIP mới nhất; khi đủ điều kiện LIVE và đang phát live thật thì kết nối bình thường. |
| Tiếng mèo kêu vang quá nhiều khi đông người | Đã có chống dội sẵn (mèo mới tối đa 3 giây/lần). Muốn tắt hẳn: bỏ tick **Bật tiếng mèo kêu** ở trang điều khiển. |
| Muốn đổi mục tiêu tim / thời gian mưa cá | Trang điều khiển mục 1 → Lưu cài đặt. |

## Lưu ý

- App + sân khấu chạy **trên máy của bạn**; LIVE Studio chỉ lấy hình/tiếng từ đó phát đi.
  Máy ngủ (sleep) hoặc tắt app là live mất sân khấu — nhớ tắt chế độ ngủ khi treo live lâu.
- Thư viện đọc sự kiện TikTok là thư viện **không chính thức**, có thể ngừng chạy khi
  TikTok thay đổi — cách xử lý ở dòng "Bấm Kết nối mà không thấy sự kiện" phía trên.
