#!/usr/bin/env bash
# Chạy trên macOS / Linux:  bash run.sh
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[LỖI] Chưa có Python 3. Cài Python 3.11+ trước (python.org hoặc brew install python)."
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Lần đầu chạy: tạo môi trường và cài thư viện (1-2 phút)…"
  python3 -m venv .venv
  . .venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
else
  . .venv/bin/activate
fi

# Nếu bản app cũ còn chạy chiếm cổng 3000 thì tắt đi — tránh cảnh chạy bản mới
# mà trình duyệt vẫn nói chuyện với tiến trình cũ (lỗi cũ hiện lại y hệt).
if command -v lsof >/dev/null 2>&1 && lsof -ti:3000 >/dev/null 2>&1; then
  echo "⚠️ Có tiến trình đang chiếm cổng 3000 (có thể là bản app cũ chưa tắt) — đang tắt giúp bạn…"
  lsof -ti:3000 | xargs kill 2>/dev/null || true
  sleep 1
fi

echo "Trang điều khiển: http://localhost:3000"
echo "Sân khấu:         http://localhost:3000/stage"
(sleep 2 && (command -v open >/dev/null && open http://localhost:3000 || xdg-open http://localhost:3000)) &
python app.py
