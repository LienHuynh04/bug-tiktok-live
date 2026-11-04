"""
Nhà của Bug — server live tương tác TikTok.

Chạy:  python app.py
Mở:    http://localhost:3000          -> trang điều khiển
       http://localhost:3000/stage    -> sân khấu 1080x1920 (đưa vào TikTok LIVE Studio / OBS)

Sự kiện TikTok được đọc bằng thư viện KHÔNG chính thức TikTokLive
(https://github.com/isaackogan/TikTokLive). Nếu thư viện chưa cài
hoặc chưa có phiên live, server vẫn chạy bình thường ở CHẾ ĐỘ DEMO.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import re
import sys
import time
from typing import Optional, Set

from aiohttp import ClientSession, ClientTimeout, web

from game import GameState

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
CONFIG_PATH = os.path.join(BASE, "config.json")
SCORES_PATH = os.path.join(BASE, "data", "scores.json")
os.makedirs(os.path.join(BASE, "data"), exist_ok=True)

# Tem phiên bản: hiện ở trang điều khiển + banner khởi động để phân biệt bản mới/bản cũ
# (tránh cảnh app cũ còn chạy chiếm cổng 3000 mà người dùng tưởng đang chạy bản mới).
APP_VERSION = "v3.1"

DEFAULT_CONFIG = {
    "channel_name": "IT có con mèo tên Bug",
    "tiktok_username": "",
    "like_goal": 500,
    "rain_seconds": 30,
    # Giọng đọc: "edge" = Edge TTS giọng thật (cần internet), "browser" = giọng máy của trình duyệt
    "tts_engine": "edge",
    "tts_voice": "vi-VN-HoaiMyNeural",
    "tts_rate": 5,          # % : -50..+50
    "tts_pitch": 35,        # Hz: -100..+100 — mặc định preset DỄ THƯƠNG (Hoài My cao giọng)
    "meow_enabled": True,
    # Vbee: giọng Việt 3 miền qua API (cần App ID + Access Token của tài khoản Vbee của chủ kênh;
    # chỉ lưu trong config.json trên máy này — file đóng gói giao đi luôn để trống).
    "vbee_app_id": "",
    "vbee_token": "",
    "vbee_voice": "sg_female_thaotrinh_48k-fhg",  # Thảo Trinh — nữ miền Nam (mã đã xác thực)
    # Chế độ sân khấu: "run" = Chạy cùng Bug (mặc định), "boss" = Đánh Boss Chuột Trùm Răng Sắt,
    # "garden" = Vườn Mèo của Bug (mỗi người xem một bé mèo, mỗi bé một tính cách)
    "stage_mode": "run",
    "boss_max_hp": 1000,
    "boss_taunts": True,    # boss chửi lại: thoại châm chọc theo mốc máu / khi bị dội đòn
    # Tàn Ảnh boss: "auto" = đổi màu theo vòng (Tử -> Băng -> Lục -> Hỏa -> Kim),
    # hoặc khoá một màu: "tu" | "bang" | "luc" | "hoa" | "kim"
    "boss_skin": "auto",
}

# Preset giọng đặt nhanh ở trang điều khiển
VOICE_PRESETS = {
    "de-thuong": {"label": "🌸 Dễ thương", "voice": "vi-VN-HoaiMyNeural", "pitch": 35, "rate": 5},
    "am-ap": {"label": "💛 Ấm áp", "voice": "vi-VN-HoaiMyNeural", "pitch": 0, "rate": 0},
    "nang-luong": {"label": "⚡ Năng lượng", "voice": "vi-VN-NamMinhNeural", "pitch": 0, "rate": 10},
}

# Bảng giọng Edge TTS dùng được cho kênh (tiếng Việt hiện có đúng 2 giọng neural).
VOICES = [
    {
        "id": "vi-VN-HoaiMyNeural",
        "name": "Hoài My",
        "gender": "Nữ",
        "desc": "Ấm, mềm, rất tự nhiên — hợp giọng 'sen' dẫn live, đọc lời chúc, kể chuyện về Bug",
        "recommended": True,
        "sample": "Chào cả nhà! Mình là sen của Bug đây. Gõ meow để nhận một bé mèo mang tên bạn nha!",
    },
    {
        "id": "vi-VN-NamMinhNeural",
        "name": "Nam Minh",
        "gender": "Nam",
        "desc": "Trẻ, rõ chữ, nhiều năng lượng — hợp lúc đua mèo, công bố người thắng, khuấy động phòng",
        "recommended": False,
        "sample": "Đua mèo sắp bắt đầu! Cả nhà gõ chữ đua để tham gia, gõ chạy để tăng tốc nha!",
    },
]
VOICE_IDS = {v["id"] for v in VOICES}

TTS_CACHE_DIR = os.path.join(BASE, "data", "tts_cache")
os.makedirs(TTS_CACHE_DIR, exist_ok=True)
_tts_semaphore = asyncio.Semaphore(2)


async def make_tts_file(text: str, voice: str, rate: int, pitch: int = 0) -> str:
    """Tạo (hoặc lấy từ cache) file mp3 Edge TTS. Trả tên file trong TTS_CACHE_DIR."""
    import hashlib

    import edge_tts  # import lười: chưa cài thì nơi gọi tự fallback

    key = hashlib.sha256(f"{voice}|{rate}|{pitch}|{text}".encode("utf-8")).hexdigest()[:24]
    filename = f"{key}.mp3"
    path = os.path.join(TTS_CACHE_DIR, filename)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return filename
    async with _tts_semaphore:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return filename
        tmp_path = path + ".part"
        try:
            communicate = edge_tts.Communicate(text, voice, rate=f"{int(rate):+d}%",
                                               pitch=f"{int(pitch):+d}Hz")
            await communicate.save(tmp_path)
            os.replace(tmp_path, path)  # chỉ đưa vào cache khi tạo thành công trọn vẹn
        except Exception:
            for p in (tmp_path, path):
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except OSError:
                    pass
            raise
    # Dọn cache: giữ tối đa 300 file mới nhất
    try:
        files = sorted(
            (os.path.join(TTS_CACHE_DIR, f) for f in os.listdir(TTS_CACHE_DIR)),
            key=lambda p: os.path.getmtime(p),
        )
        for old in files[:-300]:
            os.remove(old)
    except OSError:
        pass
    return filename


# ---------------- Vbee TTS (giọng Việt 3 miền, API bất đồng bộ) ----------------
VBEE_API_BASE = "https://vbee.vn/api/v1"
# Mã Thảo Trinh + Lan Hương đã xác thực theo tài liệu/mẫu API Vbee công khai.
# Mã Mỹ Linh suy theo đúng mẫu đặt tên của Vbee nhưng CHƯA xác thực — trang điều khiển có nút
# "Lấy danh sách giọng thật từ Vbee" (GET /api/v1/voices) để chọn đúng mã thật của tài khoản.
VBEE_VOICES = [
    {"code": "sg_female_thaotrinh_48k-fhg", "name": "Thảo Trinh — Nữ miền Nam (mã đã xác thực)"},
    {"code": "sg_female_lanhuong_48k-fhg", "name": "Lan Hương — Nữ miền Nam (mã đã xác thực)"},
    {"code": "sg_female_mylinh_48k-fhg", "name": "Mỹ Linh — Nữ miền Nam (mã CHƯA xác thực)"},
]


class VbeeError(Exception):
    """Lỗi nghiệp vụ từ Vbee (sai key, sai mã giọng, hết hạn mức...) — báo rõ cho người dùng."""


def _prune_tts_cache() -> None:
    try:
        files = sorted(
            (os.path.join(TTS_CACHE_DIR, f) for f in os.listdir(TTS_CACHE_DIR)),
            key=lambda p: os.path.getmtime(p),
        )
        for old in files[:-300]:
            os.remove(old)
    except OSError:
        pass


async def make_vbee_tts_file(text: str, voice_code: str, speed_rate: float,
                             app_id: str, token: str) -> str:
    """Tạo (hoặc lấy từ cache) file mp3 bằng Vbee API. Trả tên file trong TTS_CACHE_DIR.

    Luồng theo đúng tài liệu Vbee: POST /tts (callback_url bắt buộc dù dùng polling)
    -> poll GET /tts/{request_id} tới khi SUCCESS có audio_link -> tải ngay (link CDN tạm thời)
    -> ghi .part rồi thay thế nguyên tử vào cache như pipeline Edge.
    """
    import hashlib

    key = hashlib.sha256(
        f"vbee|{voice_code}|{speed_rate:.2f}|{text}".encode("utf-8")).hexdigest()[:24]
    filename = f"{key}.mp3"
    path = os.path.join(TTS_CACHE_DIR, filename)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return filename
    async with _tts_semaphore:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return filename
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        tmp_path = path + ".part"
        try:
            async with ClientSession() as session:
                async with session.post(
                        f"{VBEE_API_BASE}/tts", headers=headers,
                        timeout=ClientTimeout(total=25),
                        json={"app_id": app_id,
                              "input_text": text,
                              "voice_code": voice_code,
                              "audio_type": "mp3",
                              "speed_rate": speed_rate,
                              "callback_url": "https://example.com/callback"}) as resp:
                    data = await resp.json(content_type=None)
                if not isinstance(data, dict) or str(data.get("status")) != "1":
                    msg = ""
                    if isinstance(data, dict):
                        msg = str(data.get("error_message") or data.get("error_code") or "")
                    raise VbeeError(f"Vbee từ chối tạo giọng: {msg or 'không rõ lý do'}")
                result = data.get("result") or {}
                audio_link = result.get("audio_link")
                request_id = result.get("request_id")
                if not audio_link and request_id:
                    for _ in range(16):  # poll ~1,2s/lần, tối đa ~20 giây
                        await asyncio.sleep(1.2)
                        async with session.get(
                                f"{VBEE_API_BASE}/tts/{request_id}", headers=headers,
                                timeout=ClientTimeout(total=10)) as resp:
                            pdata = await resp.json(content_type=None)
                        presult = (pdata or {}).get("result") or {}
                        if presult.get("status") == "SUCCESS" and presult.get("audio_link"):
                            audio_link = presult["audio_link"]
                            break
                        if presult.get("status") == "FAILURE":
                            raise VbeeError("Vbee xử lý thất bại (FAILURE) — kiểm tra lại mã giọng/hạn mức")
                    if not audio_link:
                        raise VbeeError("Vbee xử lý quá lâu (>20 giây), thử lại sau")
                if not audio_link:
                    raise VbeeError("Vbee không trả về link audio")
                async with session.get(audio_link, timeout=ClientTimeout(total=25)) as resp:
                    audio = await resp.read()
            if len(audio) <= 1000:
                raise VbeeError(
                    f"File audio Vbee trả về quá nhỏ ({len(audio)} byte) — có thể sai mã giọng")
            with open(tmp_path, "wb") as f:
                f.write(audio)
            os.replace(tmp_path, path)  # chỉ đưa vào cache khi tải trọn vẹn
        except Exception:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            raise
    _prune_tts_cache()
    return filename


def public_config(cfg: dict) -> dict:
    """Bản config an toàn để trả ra API/WS: KHÔNG kèm Access Token Vbee thô,
    chỉ kèm cờ vbee_token_set cho trang điều khiển hiện trạng thái 'đã lưu'."""
    out = dict(cfg)
    out["vbee_token_set"] = bool(str(out.get("vbee_token", "")).strip())
    out["vbee_token"] = ""
    return out


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (OSError, ValueError):
            pass
    return cfg


def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


class Hub:
    """Giữ các websocket của stage/control và broadcast sự kiện."""

    def __init__(self) -> None:
        self.clients: Set[web.WebSocketResponse] = set()

    async def broadcast(self, payload: dict) -> None:
        if not self.clients:
            return
        data = json.dumps(payload, ensure_ascii=False)
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_str(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)


def _safe_int(value, default=None):
    """Ép số nguyên phòng thủ: TikTokLive thỉnh thoảng trả '' hoặc None cho
    các trường số (total_like_count, repeat_end...) — int('') sẽ nổ ValueError
    và làm rớt cả kết nối. Trả default khi không ép được."""
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def friendly_tiktok_error(exc: Exception, username: str = "") -> str:
    """Dịch lỗi thô của TikTokLive sang hướng dẫn tiếng Việt làm-được-ngay."""
    name = type(exc).__name__
    text = str(exc)
    if name == "ValueError" and "invalid literal for int" in text:
        return ("TikTok trả về một trường số bị rỗng nên bị vấp lỗi int(''). "
                "Nguyên nhân thường gặp nhất: tài khoản CHƯA được mở LIVE hoặc chưa từng phát live, "
                "nên TikTok không có phòng live nào để lấy dữ liệu. "
                "Kiểm tra: đủ 1.000 followers chưa (kênh Bug từng đo được 799), nếu đủ rồi thì phát live thử "
                "1 lần bằng điện thoại trước, đang live mới quay lại bấm Kết nối. "
                "Bản app mới nhất đã vá để lỗi vặt kiểu này không làm rớt kết nối nữa — hãy dùng bản ZIP mới nhất.")
    if name == "UserNotFoundError" or "not capable of going LIVE" in text:
        return (f"Không tìm thấy phòng live của {username or 'tài khoản này'}. "
                "Lỗi này chỉ có 3 nguyên nhân: "
                "(1) sai username — phải lấy đúng @tên ở trang cá nhân TikTok, không phải tên hiển thị của kênh; "
                "(2) bạn chưa bấm Go LIVE — phải ĐANG live thì mới kết nối được, kết nối trước khi live là báo lỗi này; "
                "(3) tài khoản chưa từng live / chưa đủ điều kiện mở LIVE trên TikTok. "
                "Cách thử nhanh: mở app TikTok trên điện thoại, bấm LIVE phát thử 1 phút, giữ nguyên rồi quay lại bấm Kết nối.")
    if name in ("UserOfflineError",) or "offline" in text.lower():
        return (f"{username or 'Tài khoản'} hiện không có phiên live nào đang chạy. "
                "Hãy bấm Go LIVE trước, rồi mới bấm Kết nối ở trang điều khiển.")
    if "SignApiError" in name or "sign" in text.lower():
        return ("Lỗi ký kết nối với TikTok (SignApiError) — thường do TikTok vừa đổi cơ chế. "
                "Hãy cập nhật thư viện: trong thư mục bug-live chạy "
                "`.venv/bin/pip install -U TikTokLive` (Windows: .venv\\Scripts\\pip) rồi chạy lại app.")
    if "Connection" in name or "connect" in text.lower():
        return f"Mất kết nối mạng tới TikTok: {text}. Kiểm tra internet rồi bấm Kết nối lại."
    return f"Mất kết nối TikTok: {name}: {text}"


class TikTokConnector:
    """Bọc TikTokLive: import lười, trích xuất field phòng thủ theo phiên bản."""

    def __init__(self, hub: Hub, game: GameState, emit_status) -> None:
        self.hub = hub
        self.game = game
        self.emit_status = emit_status
        self.client = None
        self.task: Optional[asyncio.Task] = None
        self.username = ""
        self._last_total_likes: Optional[int] = None

    # ---------------------------------------------------------- trích xuất
    @staticmethod
    def _get(obj, *names, default=None):
        for name in names:
            if obj is not None and hasattr(obj, name):
                val = getattr(obj, name)
                if val is not None:
                    return val
        return default

    @classmethod
    def _avatar_url(cls, user) -> str:
        # avatar_thumb / avatar_medium ở các bản mới là object có url_list / m_urls;
        # bản cũ là string hoặc object có .url / .urls. Đào đệ quy cho chắc.
        def dig(obj, depth=0):
            if obj is None or depth > 3:
                return ""
            if isinstance(obj, str):
                return obj if obj.startswith("http") else ""
            if isinstance(obj, (list, tuple)):
                for item in obj:
                    found = dig(item, depth + 1)
                    if found:
                        return found
                return ""
            for attr in ("url_list", "m_urls", "urls", "url"):
                if hasattr(obj, attr):
                    found = dig(getattr(obj, attr), depth + 1)
                    if found:
                        return found
            return ""

        for attr in ("avatar_thumb", "avatar_medium", "avatar_large",
                     "profile_picture", "avatar"):
            found = dig(getattr(user, attr, None))
            if found:
                return found
        return ""

    def _user_info(self, event) -> dict:
        user = self._get(event, "user", default=None)
        if user is None:
            return {"unique_id": "khach", "nickname": "Khách", "avatar_url": ""}
        return {
            "unique_id": str(self._get(user, "unique_id", "uniqueId", default="khach")),
            "nickname": str(self._get(user, "nickname", "display_id", default="Khách")),
            "avatar_url": self._avatar_url(user),
        }

    # ---------------------------------------------------------- sự kiện
    async def _push(self, effects):
        for eff in effects or []:
            await self.hub.broadcast(eff)
        if effects:
            await self.hub.broadcast({"type": "snapshot", **self.game.snapshot()})

    async def _on_join(self, event):
        info = self._user_info(event)
        await self._push(self.game.handle_join(**info))

    async def _on_comment(self, event):
        info = self._user_info(event)
        comment = str(self._get(event, "comment", "content", default=""))
        await self._push(self.game.handle_comment(comment=comment, **info))

    async def _on_like(self, event):
        count = _safe_int(self._get(event, "like_count", "count", default=None))
        total = _safe_int(self._get(event, "total_like_count", "total_likes", "total", default=None))
        if total is not None:
            if self._last_total_likes is None:
                self._last_total_likes = total
                return
            delta = max(0, total - self._last_total_likes)
            self._last_total_likes = total
            count = delta
        await self._push(self.game.handle_like(count if count else 1))

    async def _on_gift(self, event):
        info = self._user_info(event)
        gift = self._get(event, "gift", default=None)
        gift_name = str(self._get(gift, "name", default=None)
                        or self._get(event, "gift_name", default="quà"))
        diamonds = _safe_int(self._get(gift, "diamond_count", "diamondCount", default=1), 1) or 1
        repeat = _safe_int(self._get(event, "repeat_count", "repeatCount", default=1), 1) or 1
        # Quà streak: chỉ tính khi streak kết thúc (nếu field tồn tại)
        repeat_end = _safe_int(self._get(event, "repeat_end", "repeatEnd", default=None))
        if repeat_end is not None and repeat_end == 0:
            return
        await self._push(self.game.handle_gift(
            gift_name=gift_name, diamond_count=diamonds * max(1, repeat) if repeat_end is not None else diamonds,
            **info))

    async def _on_follow(self, event):
        await self._push(self.game.handle_follow(**self._user_info(event)))

    async def _on_share(self, event):
        await self._push(self.game.handle_share(**self._user_info(event)))

    # ---------------------------------------------------------- kết nối
    async def connect(self, username: str) -> None:
        await self.disconnect()
        username = username.strip()
        if not username:
            await self.emit_status(False, "Chưa nhập username TikTok")
            return
        if not username.startswith("@"):
            username = "@" + username
        self.username = username
        try:
            from TikTokLive import TikTokLiveClient
            try:
                from TikTokLive.events import (CommentEvent, ConnectEvent,
                                               FollowEvent, GiftEvent, JoinEvent,
                                               LikeEvent, ShareEvent)
            except ImportError:
                from TikTokLive.types.events import (  # bản cũ hơn
                    CommentEvent, ConnectEvent, FollowEvent, GiftEvent,
                    JoinEvent, LikeEvent, ShareEvent)
        except ImportError:
            await self.emit_status(False, "Chưa cài thư viện TikTokLive — hãy chạy lại file BAT để nó tự cài, hoặc dùng chế độ Demo")
            return

        try:
            client = TikTokLiveClient(unique_id=username)
        except Exception as exc:
            await self.emit_status(False, f"Không khởi tạo được TikTokLive: {type(exc).__name__}: {exc}")
            return
        self.client = client

        async def on_connect(event=None):
            await self.emit_status(True, f"Đã kết nối live của {username}")
            # Lời chào mở màn: phát file ghi âm giọng mẫu của chủ kênh (nếu có),
            # rồi mới tới câu hướng dẫn bằng giọng đọc thường.
            if os.path.exists(os.path.join(STATIC, "voice", "chao-mung.mp3")):
                await self.hub.broadcast({"type": "welcome_audio",
                                           "url": "/static/voice/chao-mung.mp3"})
            await self.hub.broadcast({"type": "speak",
                                       "text": self.game.opening_line(),
                                       "speak_priority": 1})

        def guarded(fn):
            """Một sự kiện lỗi dữ liệu không được phép làm rớt cả kết nối live."""
            async def wrapper(event):
                try:
                    await fn(event)
                except Exception as exc:
                    print(f"[BugLive] Bỏ qua 1 sự kiện lỗi ({type(exc).__name__}: {exc})")
            return wrapper

        handlers = [
            (ConnectEvent, on_connect),
            (JoinEvent, guarded(self._on_join)),
            (CommentEvent, guarded(self._on_comment)),
            (LikeEvent, guarded(self._on_like)),
            (GiftEvent, guarded(self._on_gift)),
            (FollowEvent, guarded(self._on_follow)),
            (ShareEvent, guarded(self._on_share)),
        ]
        for ev_type, fn in handlers:
            try:
                client.add_listener(ev_type, fn)
            except Exception:
                try:
                    client.on(ev_type)(fn)
                except Exception:
                    pass

        async def runner():
            try:
                # Các phiên bản khác nhau: start() (async) hoặc run() (sync/blocking)
                start = getattr(client, "start", None)
                if start is not None and asyncio.iscoroutinefunction(start):
                    await start()
                elif hasattr(client, "run_async"):
                    await client.run_async()
                elif hasattr(client, "connect"):
                    result = client.connect()
                    if asyncio.iscoroutine(result):
                        await result
                else:
                    await asyncio.to_thread(client.run)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # chưa live / TikTok đổi API / mất mạng...
                await self.emit_status(False, friendly_tiktok_error(exc, username))

        self.task = asyncio.create_task(runner())
        await self.emit_status(False, f"Đang kết nối tới {username}… (cần đang LIVE mới kết nối được)")

    async def disconnect(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = None
        if self.client is not None:
            for name in ("disconnect", "stop"):
                fn = getattr(self.client, name, None)
                if callable(fn):
                    try:
                        result = fn()
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception:
                        pass
                    break
        self.client = None
        self._last_total_likes = None


# ---------------------------------------------------------------------- demo
DEMO_USERS = [
    ("sen_meo_01", "Sen Mèo 01"), ("ban_cua_bug", "Bạn Của Bug"),
    ("meow_chan", "Meow Chan"), ("it_dev_99", "IT Dev 99"),
    ("co_ba_bun_bo", "Cô Ba Bún Bò"), ("anh_tuan_dev", "Anh Tuấn Dev"),
    ("be_cam", "Bé Cam"), ("sen_hai_phong", "Sen Hải Phòng"),
    ("meo_con_07", "Mèo Con 07"), ("chi_linh", "Chị Linh"),
]
DEMO_COMMENTS = [
    "meow", "hạt", "cho ăn", "Bug dễ thương quá", "chạy", "chạy nhanh",
    "cầu may mắn cho cả nhà", "mai thi rồi cầu điểm cao", "hạt", "nhảy",
    "xin vía sức khỏe cho ba mẹ", "meow", "cho ăn", "chạy", "chạy nhanh",
    "hạng", "nghỉ", "chạy", "hạt", "ngủ", "hạt", "ngủ", "buồn ngủ", "cho ăn",
]
# Bình luận demo riêng cho chế độ Đánh Boss: spam CÀO là chính
DEMO_BOSS_COMMENTS = [
    "cào", "cào", "CÀO", "cào", "hạt", "cào", "meow",
    "đánh nó đi cả nhà", "cào", "cố lên Bug ơi", "cào", "cào", "ngủ", "hạt",
]
# (tên quà, kim cương) cho demo boss — quà to thỉnh thoảng mới có
DEMO_BOSS_GIFTS = [("Hoa hồng", 1), ("Bánh quy", 5), ("Xe đồ chơi", 30), ("Sư tử", 150)]
# Bình luận demo riêng cho Vườn Mèo: xoay vòng các lệnh vườn để mèo phản ứng theo tính cách
DEMO_GARDEN_COMMENTS = [
    "hạt", "chơi", "xinh quá", "cá", "ngủ", "chơi đi", "hạt",
    "dễ thương quá", "ăn cá", "chơi", "meow", "cá", "hạt", "buồn ngủ",
]


class DemoSimulator:
    def __init__(self, hub: Hub, game: GameState):
        self.hub = hub
        self.game = game
        self.task: Optional[asyncio.Task] = None
        self.rng = random.Random()

    async def _push(self, effects):
        for eff in effects or []:
            await self.hub.broadcast(eff)
        if effects:
            await self.hub.broadcast({"type": "snapshot", **self.game.snapshot()})

    async def _run(self):
        try:
            for uid, nick in DEMO_USERS[:4]:
                await self._push(self.game.handle_join(uid, nick))
                await asyncio.sleep(0.8)
            gift_count = 0
            last_burst = 0.0  # mốc monotonic của đợt ĐỒNG LOẠT demo gần nhất
            while True:
                # Demo Đánh Boss: cứ ~35s dồn 6 người giả cùng CÀO trong ~1,5s
                # để kích hoạt ĐÒN ĐỒNG LOẠT x2 ngay trên sóng thử.
                if (self.game.stage_mode == "boss"
                        and time.monotonic() - last_burst >= 35):
                    last_burst = time.monotonic()
                    for buid, bnick in self.rng.sample(DEMO_USERS, 6):
                        await self._push(self.game.handle_comment(buid, bnick, "cào"))
                        await asyncio.sleep(0.25)
                    continue
                uid, nick = self.rng.choice(DEMO_USERS)
                roll = self.rng.random()
                if self.game.stage_mode == "boss":
                    # Demo Đánh Boss: cào liên tục, tim dồn dập (đầy Nộ),
                    # quà nhỏ thỉnh thoảng + cứ 3 món quà có 1 món to (>=100 kim cương)
                    if roll < 0.10:
                        await self._push(self.game.handle_join(uid, nick))
                    elif roll < 0.36:
                        await self._push(self.game.handle_like(self.rng.randint(10, 50)))
                    elif roll < 0.54:
                        gift_count += 1
                        if gift_count % 3 == 0:
                            name, diamonds = "Sư tử", 150
                        else:
                            name, diamonds = self.rng.choice(DEMO_BOSS_GIFTS[:3])
                        await self._push(self.game.handle_gift(uid, nick, name, diamonds))
                    else:
                        cmt = self.rng.choice(DEMO_BOSS_COMMENTS)
                        await self._push(self.game.handle_comment(uid, nick, cmt))
                elif self.game.stage_mode == "garden":
                    # Demo Vườn Mèo: tim chảy đều (gom tim vườn + đủ 500 mở tiệc),
                    # follow thỉnh thoảng (mèo mới chuyển vào), còn lại là lệnh vườn
                    if roll < 0.10:
                        await self._push(self.game.handle_join(uid, nick))
                    elif roll < 0.40:
                        await self._push(self.game.handle_like(self.rng.randint(10, 40)))
                    elif roll < 0.45:
                        await self._push(self.game.handle_follow(uid, nick))
                    elif roll < 0.49:
                        await self._push(self.game.handle_gift(uid, nick, "Hoa hồng", 1))
                    elif roll < 0.52:
                        await self._push(self.game.handle_share(uid, nick))
                    else:
                        cmt = self.rng.choice(DEMO_GARDEN_COMMENTS)
                        await self._push(self.game.handle_comment(uid, nick, cmt))
                elif roll < 0.12:
                    await self._push(self.game.handle_join(uid, nick))
                elif roll < 0.22:
                    await self._push(self.game.handle_like(self.rng.randint(5, 40)))
                elif roll < 0.27:
                    await self._push(self.game.handle_gift(uid, nick, "Hoa hồng", 1))
                else:
                    cmt = self.rng.choice(DEMO_COMMENTS)
                    await self._push(self.game.handle_comment(uid, nick, cmt))
                await asyncio.sleep(self.rng.uniform(0.7, 1.6))
        except asyncio.CancelledError:
            raise

    async def start(self):
        if not self.task or self.task.done():
            self.task = asyncio.create_task(self._run())

    async def stop(self):
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = None


# ---------------------------------------------------------------------- app
def build_app() -> web.Application:
    cfg = load_config()
    game = GameState(like_goal=int(cfg.get("like_goal", 500)), scores_path=SCORES_PATH,
                     stage_mode=str(cfg.get("stage_mode", "run")),
                     boss_max_hp=int(cfg.get("boss_max_hp", 1000)),
                     boss_taunts=bool(cfg.get("boss_taunts", True)),
                     boss_skin=str(cfg.get("boss_skin", "auto")))
    hub = Hub()
    state = {"connected": False, "message": "Chưa kết nối TikTok"}

    async def emit_status(connected: bool, message: str):
        state["connected"] = connected
        state["message"] = message
        await hub.broadcast({"type": "status", "connected": connected, "message": message})

    connector = TikTokConnector(hub, game, emit_status)
    demo = DemoSimulator(hub, game)
    last_activity = {"ts": time.time()}

    async def broadcast_effects(effects):
        for eff in effects or []:
            last_activity["ts"] = time.time()
            await hub.broadcast(eff)
        if effects:
            await hub.broadcast({"type": "snapshot", **game.snapshot()})

    # ---- background loop: đua + độ no + nhắc khi live im lặng ----
    async def game_loop():
        idle_spoken_at = 0.0
        loop_count = 0
        while True:
            await asyncio.sleep(0.5)
            loop_count += 1
            game.decay_satiety(0.05)
            game.run_tick(0.5)
            await broadcast_effects(game.tick())
            if loop_count % 4 == 0:
                # Mỗi 2 giây đẩy snapshot để km / độ no / BXH chạy mượt trên sân khấu v3
                await hub.broadcast({"type": "snapshot", **game.snapshot()})
            now = time.time()
            if now - last_activity["ts"] > 75 and now - idle_spoken_at > 120:
                idle_spoken_at = now
                last_activity["ts"] = now
                await hub.broadcast({
                    "type": "speak", "speak_priority": 5,
                    "text": game.idle_line(),
                })

    async def on_startup(app_):
        app_["loop_task"] = asyncio.create_task(game_loop())

    async def on_cleanup(app_):
        app_["loop_task"].cancel()
        await connector.disconnect()
        await demo.stop()

    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    # ---- websocket ----
    async def ws_handler(request):
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        hub.clients.add(ws)
        await ws.send_str(json.dumps({"type": "config", **public_config(load_config()), "app_version": APP_VERSION}, ensure_ascii=False))
        await ws.send_str(json.dumps({"type": "status", **state}, ensure_ascii=False))
        await ws.send_str(json.dumps({"type": "snapshot", **game.snapshot()}, ensure_ascii=False))
        try:
            async for _ in ws:
                pass
        finally:
            hub.clients.discard(ws)
        return ws

    # ---- API ----
    async def api_config_get(request):
        return web.json_response({**public_config(load_config()), "app_version": APP_VERSION})

    async def api_config_post(request):
        body = await request.json()
        cfg_now = load_config()
        for key in ("channel_name", "tiktok_username"):
            if isinstance(body.get(key), str):
                cfg_now[key] = body[key].strip()
        if body.get("like_goal"):
            cfg_now["like_goal"] = max(50, int(body["like_goal"]))
            game.like_goal = cfg_now["like_goal"]
        if body.get("rain_seconds"):
            cfg_now["rain_seconds"] = max(5, min(120, int(body["rain_seconds"])))
        if body.get("tts_voice") in VOICE_IDS:
            cfg_now["tts_voice"] = body["tts_voice"]
        if body.get("tts_engine") in ("edge", "browser", "vbee"):
            cfg_now["tts_engine"] = body["tts_engine"]
        if isinstance(body.get("vbee_app_id"), str):
            cfg_now["vbee_app_id"] = body["vbee_app_id"].strip()[:80]
        # Token: chỉ ghi đè khi gửi lên một giá trị khác rỗng (ô trống = giữ token đã lưu)
        if isinstance(body.get("vbee_token"), str) and body["vbee_token"].strip():
            cfg_now["vbee_token"] = body["vbee_token"].strip()[:300]
        if isinstance(body.get("vbee_voice"), str):
            vcode = body["vbee_voice"].strip()
            if len(vcode) <= 80 and re.fullmatch(r"[A-Za-z0-9_-]+", vcode):
                cfg_now["vbee_voice"] = vcode
        if body.get("tts_rate") is not None:
            cfg_now["tts_rate"] = max(-50, min(50, int(body["tts_rate"])))
        if body.get("tts_pitch") is not None:
            cfg_now["tts_pitch"] = max(-100, min(100, int(body["tts_pitch"])))
        if body.get("voice_preset") in VOICE_PRESETS:
            preset = VOICE_PRESETS[body["voice_preset"]]
            cfg_now["tts_voice"] = preset["voice"]
            cfg_now["tts_pitch"] = preset["pitch"]
            cfg_now["tts_rate"] = preset["rate"]
            cfg_now["tts_engine"] = "edge"
        if body.get("meow_enabled") is not None:
            cfg_now["meow_enabled"] = bool(body["meow_enabled"])
        if body.get("stage_mode") in ("run", "boss", "garden"):
            cfg_now["stage_mode"] = body["stage_mode"]
        if body.get("boss_max_hp") is not None:
            try:
                cfg_now["boss_max_hp"] = max(100, min(100000, int(body["boss_max_hp"])))
            except (TypeError, ValueError):
                pass
        if body.get("boss_taunts") is not None:
            cfg_now["boss_taunts"] = bool(body["boss_taunts"])
        if body.get("boss_skin") in ("auto", "tu", "bang", "luc", "hoa", "kim"):
            cfg_now["boss_skin"] = body["boss_skin"]
        game.set_stage_mode(cfg_now["stage_mode"], int(cfg_now["boss_max_hp"]),
                            bool(cfg_now.get("boss_taunts", True)),
                            str(cfg_now.get("boss_skin", "auto")))
        save_config(cfg_now)
        pub = public_config(cfg_now)  # không phát token Vbee qua WS/response
        await hub.broadcast({"type": "config", **pub, "app_version": APP_VERSION})
        await hub.broadcast({"type": "snapshot", **game.snapshot()})
        return web.json_response(pub)

    async def api_connect(request):
        body = await request.json()
        username = str(body.get("username", "")).strip()
        if username:
            cfg_now = load_config()
            cfg_now["tiktok_username"] = username
            save_config(cfg_now)
        asyncio.create_task(connector.connect(username or load_config()["tiktok_username"]))
        return web.json_response({"ok": True})

    async def api_disconnect(request):
        await connector.disconnect()
        await emit_status(False, "Đã ngắt kết nối TikTok")
        return web.json_response({"ok": True})

    async def api_demo(request):
        if request.match_info["mode"] == "start":
            await demo.start()
            if os.path.exists(os.path.join(STATIC, "voice", "chao-mung.mp3")):
                await hub.broadcast({"type": "welcome_audio",
                                     "url": "/static/voice/chao-mung.mp3"})
            # Câu hướng dẫn mở màn giống lúc live kết nối thật — theo chế độ sân khấu
            await hub.broadcast({"type": "speak",
                                 "text": game.opening_line(),
                                 "speak_priority": 1})
            await emit_status(False, "Đang chạy DEMO (người xem giả) — tắt demo trước khi kết nối live thật")
        else:
            await demo.stop()
        return web.json_response({"ok": True})

    async def api_voices(request):
        cfg_now = load_config()
        return web.json_response({"voices": VOICES, "current": cfg_now["tts_voice"],
                                  "engine": cfg_now["tts_engine"], "rate": cfg_now["tts_rate"],
                                  "pitch": cfg_now.get("tts_pitch", 0),
                                  "presets": VOICE_PRESETS})

    async def api_tts(request):
        body = await request.json()
        text = str(body.get("text", "")).strip()[:300]
        if not text:
            return web.json_response({"error": "thiếu text"}, status=400)
        cfg_now = load_config()
        if cfg_now.get("tts_engine") == "vbee":
            app_id = str(cfg_now.get("vbee_app_id", "")).strip()
            token = str(cfg_now.get("vbee_token", "")).strip()
            if not app_id or not token:
                return web.json_response(
                    {"error": "Chưa nhập API key Vbee — mở trang điều khiển mục 3, nhập App ID + "
                              "Access Token Vbee rồi bấm 'Lưu Vbee & dùng giọng này'"}, status=400)
            voice_code = str(cfg_now.get("vbee_voice") or "").strip()
            body_voice = body.get("vbee_voice")
            if isinstance(body_voice, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", body_voice.strip()):
                voice_code = body_voice.strip()
            if not voice_code:
                return web.json_response({"error": "Chưa chọn giọng Vbee"}, status=400)
            try:
                vbee_rate = int(body.get("rate", cfg_now["tts_rate"]))
            except (TypeError, ValueError):
                vbee_rate = int(cfg_now["tts_rate"])
            speed_rate = max(0.8, min(1.5, 1 + vbee_rate / 100))
            try:
                filename = await make_vbee_tts_file(text, voice_code, speed_rate, app_id, token)
            except Exception as exc:  # sai key/mã giọng, hết hạn mức, mất mạng...
                return web.json_response({"error": f"Vbee TTS lỗi: {type(exc).__name__}: {exc}"},
                                         status=502)
            return web.json_response({"url": f"/tts-cache/{filename}", "voice": voice_code})
        voice = body.get("voice") if body.get("voice") in VOICE_IDS else cfg_now["tts_voice"]
        try:
            rate = int(body.get("rate", cfg_now["tts_rate"]))
            pitch = int(body.get("pitch", cfg_now.get("tts_pitch", 0)))
        except (TypeError, ValueError):
            rate, pitch = 0, 0
        try:
            filename = await make_tts_file(text, voice, rate, pitch)
        except ImportError:
            return web.json_response(
                {"error": "Chưa cài edge-tts — xóa thư mục .venv rồi chạy lại BAT-LIVE.bat để cài lại"}, status=502)
        except Exception as exc:  # mất mạng / Microsoft đổi API...
            return web.json_response({"error": f"Edge TTS lỗi: {type(exc).__name__}: {exc}"}, status=502)
        return web.json_response({"url": f"/tts-cache/{filename}", "voice": voice})

    async def api_vbee_voices(request):
        """Proxy lấy danh sách giọng thật của tài khoản Vbee (GET /api/v1/voices)."""
        cfg_now = load_config()
        token = str(cfg_now.get("vbee_token", "")).strip()
        if not token:
            return web.json_response(
                {"error": "Chưa nhập Access Token Vbee — nhập App ID + Token ở mục 3 rồi bấm Lưu trước"},
                status=400)
        try:
            async with ClientSession() as session:
                async with session.get(f"{VBEE_API_BASE}/voices",
                                       headers={"Authorization": f"Bearer {token}"},
                                       timeout=ClientTimeout(total=20)) as resp:
                    data = await resp.json(content_type=None)
                    if resp.status != 200:
                        detail = ""
                        if isinstance(data, dict):
                            detail = str(data.get("error_message") or data.get("error_code") or "")
                        return web.json_response(
                            {"error": f"Vbee trả lỗi HTTP {resp.status}" + (f": {detail}" if detail else "")},
                            status=502)
            if isinstance(data, (dict, list)):
                return web.json_response(data)
            return web.json_response({"result": data})
        except Exception as exc:
            return web.json_response(
                {"error": f"Không gọi được Vbee: {type(exc).__name__}: {exc}"}, status=502)

    async def api_speak(request):
        body = await request.json()
        text = str(body.get("text", "")).strip()
        if text:
            await hub.broadcast({"type": "speak", "text": text[:300], "speak_priority": 0})
        return web.json_response({"ok": True})

    async def api_action(request):
        body = await request.json()
        action = body.get("action")
        if action == "rain":
            await broadcast_effects([{"type": "rain", "kind": "fish",
                                      "seconds": int(load_config().get("rain_seconds", 30)),
                                      "speak": "Mưa cá theo yêu cầu của chủ kênh đây!",
                                      "speak_priority": 1}])
        elif action == "race_start":
            await broadcast_effects(game.force_start_race())
        elif action == "reset_scores":
            game.reset_scores()
            await hub.broadcast({"type": "snapshot", **game.snapshot()})
        elif action == "reset_likes":
            game.likes_since_rain = 0
            await hub.broadcast({"type": "snapshot", **game.snapshot()})
        return web.json_response({"ok": True})

    # ---- trang ----
    async def stage_page(request):
        return web.FileResponse(os.path.join(STATIC, "stage.html"))

    async def control_page(request):
        return web.FileResponse(os.path.join(STATIC, "control.html"))

    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/stage", stage_page)
    app.router.add_get("/", control_page)
    app.router.add_get("/api/config", api_config_get)
    app.router.add_post("/api/config", api_config_post)
    app.router.add_post("/api/connect", api_connect)
    app.router.add_post("/api/disconnect", api_disconnect)
    app.router.add_post("/api/demo/{mode}", api_demo)
    app.router.add_post("/api/speak", api_speak)
    app.router.add_post("/api/action", api_action)
    app.router.add_get("/api/voices", api_voices)
    app.router.add_get("/api/vbee/voices", api_vbee_voices)
    app.router.add_post("/api/tts", api_tts)
    app.router.add_static("/tts-cache/", TTS_CACHE_DIR)
    app.router.add_static("/static/", STATIC)
    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "3000"))
    print("=" * 62)
    print(f"  NHÀ CỦA BUG — live tương tác TikTok [{APP_VERSION}]")
    print(f"  Trang điều khiển : http://localhost:{port}")
    print(f"  Sân khấu (live)  : http://localhost:{port}/stage")
    print(f"  Nếu LIVE Studio chặn localhost, dùng: http://lvh.me:{port}/stage")
    print("=" * 62)
    web.run_app(build_app(), port=port, print=None)
