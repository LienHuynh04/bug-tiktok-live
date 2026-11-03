# 🐱 Nhà của Bug — Live TikTok tương tác

Live treo tương tác cho kênh **"IT có con mèo tên Bug"**, làm theo phong cách
"đi chùa online": người xem vào live là **được chơi ngay bằng comment**,
không cần tặng quà. Cứ treo live, mọi người tự vào chơi với nhau.

> Bản tham khảo `workaipvlinh-byte/di-chua-online` (MIT License): bản gốc là
> app Node.js + React + Three.js **3D** (nhân vật 3D thắp hương trong chánh điện),
> đọc sự kiện bằng thư viện JS `tiktok-live-connector` và đọc giọng bằng `msedge-tts`.
> Bản "Nhà của Bug" này được viết lại từ đầu — bối cảnh chùa → nhà của mèo Bug,
> giao diện **2D nhẹ hơn** (không cần model 3D), và đọc sự kiện bằng thư viện
> **Python TikTokLive (isaackogan)** theo đúng link bạn yêu cầu.
> _(Đính chính 03/11/2026: bản giao đầu tiên ghi nhầm repo tham khảo "không clone
> được / riêng tư" — thực tế repo công khai và clone được bình thường; lần tải
> đầu bị ngắt kết nối giữa chừng nên báo lỗi tạm thời.)_

## Sân khấu v3 — "Chạy cùng Bug" (theo 2 live mẫu chủ kênh gửi)

Sân khấu được làm lại theo đúng phong cách 2 ảnh mẫu:

- Kiểu **"Chạy cùng Kitzy"**: thế giới **chạy vô tận** vẽ bằng canvas — trời, mây, hồ sen,
  đường chạy 4 làn, đường xe phía dưới; mèo của người xem **tự chạy liên tục**,
  bảng menu lệnh cố định bên trái, panel thống kê phiên (⭐ / tim / follow / số mèo / tổng km / thời gian),
  bảng **BẠN ĐỒNG HÀNH** xếp theo km và **tự lật trang**.
- Kiểu **"Chùa An Lạc"**: tiêu đề kênh chữ vàng trang trọng trên cùng, và khi có quà,
  mèo của người tặng được đưa ra **giữa sân khấu với vòng sáng spotlight**.

## Người xem chơi như thế nào?

| Người xem làm | Chuyện gì xảy ra |
|---|---|
| Vào live / comment lần đầu | Được cấp 1 bé mèo mang **tên + avatar TikTok của họ**, đứng ở khu chờ bên trái đường chạy |
| Gõ **CHẠY** | Vào đội chạy cùng Bug — mèo tự chạy liên tục và tích lũy km |
| Gõ **CHẠY NHANH** | Tăng tốc ×2 trong 20 giây, +2⭐ |
| Gõ **NGHỈ** | Chạy chậm lại 15 giây (có 💤 trên đầu) |
| Gõ **NHẢY** | Mèo nhảy lên |
| Gõ **HẠNG** | Giọng đọc + bong bóng báo hạng và số km của chính họ |
| Gõ **MEOW** | Bé mèo nhảy lên kêu meow |
| Gõ **HẠT** / **PATE** / **CHO ĂN** | Cho Bug ăn, **+5⭐**. Đặc biệt: **Bug đói (độ no < 25) thì CẢ ĐỘI chạy chậm 30%** — cả phòng phải thay nhau cho Bug ăn để giữ tốc độ |
| Gõ **ĐUA** | (Chế độ cũ, vẫn chạy) Vào sảnh đua mèo 3–8 mèo; đang đua gõ **CHẠY** để tăng tốc. Thắng **+50⭐**, nhì +30⭐, ba +20⭐ |
| Thả tim | Đủ **500 tim** (tùy chỉnh được) → **mưa cá 30 giây** toàn màn hình |
| Comment có lời cầu ("mai thi cầu điểm cao", "xin vía sức khỏe"…) | Giọng đọc chúc đúng điều đó: thi cử / sức khỏe / tình duyên / gia đình / công việc / bình an |
| Follow | +10⭐, giọng đọc cảm ơn, và **một chú chó 🐕 xuất hiện đuổi theo đội chạy** |
| *Nếu* có quà (kênh **không kêu gọi**) | Mèo của người tặng lên **giữa sân khấu spotlight** + được **cưỡi xe** 20 giây (quà nhỏ 🛒 xe đẩy, vừa 🛵 xe máy, lớn 🦖 khủng long), mưa cá, giọng đọc cảm ơn **đọc trước tất cả** |

Có **bảng TOP BẠN CỦA BUG** theo điểm ⭐, điểm được lưu lại (file `data/scores.json`)
nên tắt live mở lại vẫn còn TOP.

## Bảng giọng thật (v2 — Edge TTS) & tiếng mèo kêu

Mặc định v2 dùng **Edge TTS** — giọng neural của Microsoft, nghe như người thật,
miễn phí, không cần API key. Tiếng Việt có đúng 2 giọng (đã kiểm chứng trên thư viện):

| Giọng | Kiểu | Hợp với |
|---|---|---|
| **Hoài My** `vi-VN-HoaiMyNeural` ⭐ | Nữ | Ấm, mềm, tự nhiên — giọng "sen" dẫn live, đọc lời chúc, kể chuyện (mặc định) |
| **Nam Minh** `vi-VN-NamMinhNeural` | Nam | Trẻ, rõ chữ, nhiều năng lượng — lúc đua mèo, công bố người thắng |

Chọn giọng / nghe thử / chỉnh tốc độ (-10% → +20%) / đổi máy đọc ở **trang điều khiển mục 3**.
Có sẵn 3 preset bấm là đổi ngay: **🌸 Dễ thương** (Hoài My, cao độ +35Hz, tốc độ +5% —
**đang là mặc định theo yêu cầu của chủ kênh**), 💛 Ấm áp (Hoài My nguyên bản),
⚡ Năng lượng (Nam Minh, +10%).
Giọng thật cần internet; mất mạng sân khấu tự lùi về giọng máy của trình duyệt.

**Tiếng mèo kêu**: tổng hợp trực tiếp bằng Web Audio (không cần file, không cần mạng),
có 5 kiểu — mèo con (người mới vào), vui (cho ăn/có quà), thường (gõ MEOW),
hào hứng (sắp đua), đồng thanh (có người thắng). Có chống dội âm: mèo mới tối đa 3 giây/lần.
Bật/tắt ở trang điều khiển mục 3.

> Đã chạy v1 trước đây? **Xóa thư mục `.venv`** rồi chạy lại BAT để cài thêm `edge-tts`.
> Hướng dẫn đưa lên live: xem **[HUONG-DAN-TIKTOK-STUDIO.md](HUONG-DAN-TIKTOK-STUDIO.md)**.

## Giọng đọc tiếng Việt tự động

- Chào từng người mới vào — live đông thì gom theo lô ("Chào A, B, C và 2 bạn nữa…")
  để không bị đọc dồn hàng giờ.
- Đọc theo độ ưu tiên: quà → đua → follow → chào → cho ăn/lời chúc → nhắc khi im lặng.
- Live im lặng quá 75 giây: tự nhắc mọi người cách chơi + thả tim/chia sẻ.
- Trang điều khiển có ô **"Đọc ngay"**: gõ câu bất kỳ, bấm là đọc ngay sau câu đang đọc.
- Tên kênh đặt trong trang điều khiển sẽ hiện trên sân khấu và được dùng khi xưng hô.

Giọng đọc dùng giọng `vi-VN` có sẵn trong trình duyệt (Web Speech API) — không tốn phí.
**Lưu ý:** phải mở sân khấu bằng Chrome/Edge và **bấm nút "Bật giọng đọc" trên sân khấu 1 lần**
(trình duyệt chặn phát tiếng tự động khi chưa có thao tác).

## Cách cài & chạy

### Windows (đơn giản nhất)

1. Cài **Python 3.11+** từ python.org — nhớ tick **"Add Python to PATH"**.
   (Bản gốc đi-chua-online dùng Node.js; bản này dùng Python vì thư viện
   [TikTokLive của isaackogan](https://github.com/isaackogan/TikTokLive) là thư viện Python.)
2. Giải nén thư mục này, bấm đúp **`BAT-LIVE.bat`**.
   Lần đầu nó tự tạo môi trường + cài thư viện (1–2 phút), trang điều khiển tự mở.
3. Trong trang điều khiển: đặt tên kênh → nhập username TikTok → bấm **Kết nối**
   (phải đang LIVE mới kết nối được; chưa live thì bấm **Chạy DEMO** để xem thử).
4. Trong **TikTok LIVE Studio**: Thêm nguồn → **Link** →
   `http://lvh.me:3000/stage`, kích thước **1080 × 1920**.
   (Nếu LIVE Studio nhận localhost thì dùng `http://localhost:3000/stage` cũng được —
   `lvh.me` chỉ là tên miền trỏ về chính máy của bạn, 127.0.0.1.)

### macOS / Linux

```bash
bash run.sh
```

### Địa chỉ

- Trang điều khiển: http://localhost:3000
- Sân khấu: http://localhost:3000/stage (hoặc http://lvh.me:3000/stage)

## Chế độ DEMO

Chưa live vẫn test được toàn bộ: trang điều khiển → **Chạy DEMO**.
10 "người xem giả" sẽ tự vào phòng, gõ meow / cho ăn / đua / thả tim / tặng quà
để bạn xem trước sân khấu chạy như thế nào. Nhớ **tắt DEMO** trước khi kết nối live thật.

## Cấu trúc thư mục

```
bug-live/
├── BAT-LIVE.bat        # bấm đúp để chạy (Windows)
├── run.sh              # chạy trên macOS/Linux
├── app.py              # server + kết nối TikTokLive + demo + API điều khiển
├── game.py             # toàn bộ luật chơi (spawn / cho ăn / đua / điểm / TOP)
├── config.json         # tên kênh, username, mục tiêu tim, thời gian mưa cá
├── requirements.txt    # aiohttp + TikTokLive
├── static/
│   ├── stage.html/css/js    # sân khấu 1080×1920: phòng mèo, đua, mưa cá, giọng đọc
│   └── control.html/css/js  # trang điều khiển
├── tests/test_game.py  # test luật chơi: python tests/test_game.py
└── data/scores.json    # điểm TOP (tự sinh khi chạy)
```

## Vài điều cần biết trước khi dùng

- App đọc sự kiện TikTok bằng thư viện **không chính thức** (reverse-engineering),
  nên có thể ngừng chạy bất cứ lúc nào nếu TikTok thay đổi. Lỗi kết nối thường gặp nhất:
  **chưa bắt đầu LIVE**, sai username, hoặc TikTok vừa đổi API (cập nhật lại thư viện:
  `pip install -U TikTokLive` trong thư mục `.venv`).
- Mọi xử lý đều chạy trên máy của bạn, không gửi dữ liệu đi nơi khác ngoài kết nối tới TikTok.
- Ai dùng thì tự tìm hiểu và tuân thủ điều khoản của TikTok và pháp luật hiện hành.
- Luật chơi chống lạm dụng thú cưng đã có sẵn trong code: cho ăn có cooldown,
  độ no tối đa 100 — đây là mèo ảo đại diện người xem, không ép mèo thật ăn theo live.
- Code miễn phí, cứ thoải mái sửa (giữ tinh thần giấy phép MIT của bản tham khảo).

## Muốn sửa lệnh chơi?

Tất cả lệnh nằm ở hàm `handle_comment` trong `game.py` (đã bỏ dấu trước khi so:
gõ có dấu hay không dấu đều nhận). Thêm lệnh mới chỉ cần thêm 1 nhánh `if` ở đó
và 1 hiệu ứng tương ứng trong `static/stage.js`.
