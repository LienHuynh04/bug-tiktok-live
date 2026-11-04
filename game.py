"""
Game state cho live tương tác "Nhà của Bug".

File này KHÔNG phụ thuộc TikTokLive / aiohttp -> test được độc lập.
Mọi sự kiện TikTok (join / comment / like / gift / follow / share)
đều được app.py dịch thành lời gọi vào GameState, và GameState
trả về danh sách "effect dict" để app.py broadcast xuống stage.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
import time
import unicodedata
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


def normalize(text: str) -> str:
    """Bỏ dấu tiếng Việt, hạ chữ thường, bỏ ký tự lạ -> so lệnh cho dễ."""
    text = (text or "").lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("đ", "d")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# --- Vườn Mèo: 6 tính cách mèo + Mèo Vàng hiếm -------------------------------
# Mỗi người xem là một bé mèo với tính cách riêng: gán ỔN ĐỊNH theo tên
# (hash chuẩn hoá) nên vào lại phòng vẫn giữ nguyên tính cách cũ.
PERSONALITIES = {
    "foodie": {"name": "Ham Ăn", "icon": "🍚", "coat": "tabby"},
    "sleepy": {"name": "Lười Ngủ", "icon": "😴", "coat": "grey"},
    "hyper": {"name": "Tăng Động", "icon": "🧶", "coat": "calico"},
    "diva": {"name": "Chảnh", "icon": "💅", "coat": "white"},
    "shy": {"name": "Nhút Nhát", "icon": "🌿", "coat": "cream"},
    "fishy": {"name": "Mê Cá", "icon": "🐟", "coat": "brownwhite"},
}
PERSONALITY_KEYS = ["foodie", "sleepy", "hyper", "diva", "shy", "fishy"]
GOLD_INFO = {"name": "Mèo Vàng", "icon": "👑", "coat": "gold"}


def personality_info(key: str) -> dict:
    if key == "gold":
        return GOLD_INFO
    return PERSONALITIES.get(key or "", {"name": "", "icon": "", "coat": ""})


def personality_for_uid(unique_id: str) -> str:
    """Tính cách ổn định của một người xem: hash md5 của tên đã chuẩn hoá."""
    digest = hashlib.md5(normalize(unique_id or "khach").encode("utf-8")).hexdigest()
    return PERSONALITY_KEYS[int(digest[:8], 16) % len(PERSONALITY_KEYS)]


def mood_face_of(happiness: float, sleeping: bool = False) -> str:
    """Mặt tâm trạng của mèo trong vườn theo độ vui."""
    if sleeping:
        return "😴"
    if happiness >= 75:
        return "😊"
    if happiness >= 40:
        return "🙂"
    if happiness >= 20:
        return "😐"
    return "😾"


# Từ khoá khen (đã chuẩn hoá): nghe khen là Chảnh tạo dáng, Nhút Nhát ló đầu ra
PRAISE_WORDS = ("xinh", "de thuong", "dep qua", "cute", "ngoan qua", "yeu qua")


@dataclass
class Player:
    unique_id: str
    nickname: str
    avatar_url: str = ""
    points: int = 0
    feeds: int = 0
    races: int = 0
    wins: int = 0
    seat: int = 0
    joined_at: float = field(default_factory=time.time)
    last_feed_at: float = 0.0
    last_boost_at: float = 0.0
    last_chat_point_at: float = 0.0
    # --- chạy vô tận (theme v3) ---
    distance_m: float = 0.0
    in_team: bool = False
    pace: float = 1.0               # nhịp chạy riêng 0.85..1.15
    speed_mode: str = "normal"      # normal | boost | slow
    speed_until: float = 0.0        # theo đồng hồ monotonic
    last_cmd_boost_at: float = 0.0
    last_claw_at: float = 0.0       # cooldown lệnh CÀO ở chế độ Đánh Boss (monotonic)
    # --- Vườn Mèo: tính cách + trạng thái trong vườn ---
    personality: str = ""           # foodie|sleepy|hyper|diva|shy|fishy|gold
    golden: bool = False            # Mèo Vàng hiếm (tim vườn x2 khi có mặt)
    happiness: float = 60.0         # độ vui trong vườn: 0..100
    state: str = "idle"             # idle|eat|sleep|play|pose|hide|peek|hoard|feast
    state_until: float = 0.0        # mốc wall-clock hết trạng thái vườn
    hearts: int = 0                 # số tim vườn đã sinh ra trong phiên
    treat_until: float = 0.0        # mốc wall-clock còn hiệu ứng bát đặc biệt (quà)
    # --- Đào Vàng PK ---
    team: Optional[str] = None      # "meo" | "chuot" | None (chưa vào đội)
    gold_round: int = 0             # vàng đào được trong hiệp hiện tại
    gold_total: int = 0             # vàng cộng dồn cả phiên (đua Vua Đào Vàng)
    last_dao_at: float = 0.0        # cooldown lệnh ĐÀO (monotonic)
    # --- Kéo Co (trường riêng, KHÔNG dùng chung `team` của Đào Vàng) ---
    tug_team: Optional[str] = None  # "cam" | "xam" | None (chưa vào đội)
    tug_pulls: int = 0              # tổng số cú kéo cả phiên
    tug_force: float = 0.0          # tổng lực kéo cả phiên (đua Lực Sĩ)
    tug_force_round: float = 0.0    # lực kéo trong hiệp hiện tại (chọn MVP)
    stamina: float = 100.0          # thể lực kéo co: 0..100, kéo tốn sức
    last_tug_at: float = 0.0        # cooldown lệnh KÉO (monotonic)
    last_cheer_at: float = 0.0      # cooldown lệnh HÒ (monotonic)
    # --- Văn Phòng Lén Lút ---
    office_pts: int = 0             # điểm lén trong ca hiện tại
    office_pts_total: int = 0       # điểm lén cộng dồn cả phiên (đua TOP)
    suspicion: float = 0.0          # mức bị sếp để ý: 0..100 (>= 100 -> bị bắt)
    penalty_until: float = 0.0      # mốc wall-clock hết đứng góc phạt
    office_act: str = ""            # hành động lén gần nhất (sân khấu diễn hoạt)
    office_act_until: float = 0.0   # mốc wall-clock hết hiệu ứng hành động (~2.5s)
    caught_round: int = 0           # số lần bị bắt trong ca hiện tại
    last_office: Dict[str, float] = field(default_factory=dict)  # cooldown từng hành động (monotonic)

    def eff_speed_mode(self, now_mono: float) -> str:
        if self.speed_mode != "normal" and now_mono >= self.speed_until:
            return "normal"
        return self.speed_mode

    def eff_state(self, now_wall: Optional[float] = None) -> str:
        """Trạng thái vườn hiệu lực: hết hạn thì tự về idle."""
        now_wall = time.time() if now_wall is None else now_wall
        if self.state != "idle" and now_wall >= self.state_until:
            return "idle"
        return self.state

    def public(self, now_mono: Optional[float] = None) -> dict:
        now_mono = time.monotonic() if now_mono is None else now_mono
        now_wall = time.time()
        info = personality_info(self.personality)
        state = self.eff_state(now_wall)
        return {
            "unique_id": self.unique_id,
            "nickname": self.nickname,
            "avatar_url": self.avatar_url,
            "points": self.points,
            "feeds": self.feeds,
            "races": self.races,
            "wins": self.wins,
            "seat": self.seat,
            "distance_km": round(self.distance_m / 1000.0, 2),
            "in_team": self.in_team,
            "speed_mode": self.eff_speed_mode(now_mono),
            # --- Vườn Mèo ---
            "personality": self.personality,
            "personality_name": info["name"],
            "icon": info["icon"],
            "coat": info["coat"],
            "happiness": round(self.happiness),
            "mood_face": mood_face_of(self.happiness, state == "sleep"),
            "state": state,
            "golden": self.golden,
            "hearts": self.hearts,
            "treat": now_wall < self.treat_until,
            # --- Đào Vàng PK ---
            "team": self.team,
            "gold_total": self.gold_total,
            # --- Kéo Co ---
            "tug_team": self.tug_team,
            "tug_pulls": self.tug_pulls,
            "tug_force": round(self.tug_force, 1),
            "stamina": round(self.stamina),
            "tired": self.stamina < TUG_TIRED_UNDER,
            # --- Văn Phòng Lén Lút ---
            "desk": self.seat % OFFICE_DESKS,
            "office_pts": self.office_pts,
            "office_pts_total": self.office_pts_total,
            "suspicion": round(self.suspicion),
            "penalty_left": (max(0, round(self.penalty_until - now_wall))
                             if self.penalty_until else 0),
            "action": self.office_act if now_wall < self.office_act_until else "",
            "action_left": (max(0, round(self.office_act_until - now_wall))
                            if now_wall < self.office_act_until else 0),
        }


class Race:
    IDLE = "idle"
    LOBBY = "lobby"
    COUNTDOWN = "countdown"
    RUNNING = "running"
    FINISHED = "finished"

    def __init__(self) -> None:
        self.state = self.IDLE
        self.racers: List[str] = []          # unique_id theo thứ tự đăng ký
        self.positions: Dict[str, float] = {}  # 0..100
        self.deadline: float = 0.0           # hết hạn lobby / countdown
        self.winners: List[str] = []

    def public(self, players: Dict[str, Player]) -> dict:
        return {
            "state": self.state,
            "racers": [
                {
                    "unique_id": uid,
                    "nickname": players[uid].nickname if uid in players else uid,
                    "avatar_url": players[uid].avatar_url if uid in players else "",
                    "position": round(self.positions.get(uid, 0.0), 1),
                }
                for uid in self.racers
            ],
            "winners": self.winners,
        }


class Boss:
    """Chuột Trùm Răng Sắt — boss của chế độ Đánh Boss, mò tới trộm kho cá
    của Bug. Thời gian dùng time.time() (wall clock) như máy trạng thái đua,
    để tick() xử lý hồi sinh."""

    NAME = "CHUỘT TRÙM RĂNG SẮT"
    RESPAWN_SECONDS = 15
    BAR_HP = 250        # mỗi "thanh máu" trên HUD = 250 HP (kiểu raid ×N thanh)

    def __init__(self, max_hp: int = 1000) -> None:
        self.round = 1
        self.max_hp = int(max_hp)
        self.hp = int(max_hp)
        self.alive = True
        self.respawn_at = 0.0    # mốc time.time() sẽ hồi sinh (0 = không chờ)
        self.stun_until = 0.0    # mốc time.time() hết choáng


def boss_bars_left(hp: int) -> int:
    """Số thanh máu còn lại (mỗi thanh BAR_HP, thanh cuối tính phần lẻ)."""
    hp = int(hp)
    return -(-hp // Boss.BAR_HP) if hp > 0 else 0


def boss_bars_total(max_hp: int) -> int:
    return max(1, -(-int(max_hp) // Boss.BAR_HP))


# Hạng mèo theo sát thương cộng dồn trong phiên: (ngưỡng, icon, danh hiệu)
BOSS_RANKS = [
    (0, "🐾", "Mèo Con"),
    (50, "🏹", "Mèo Săn"),
    (150, "⚔️", "Mèo Chiến"),
    (400, "🎖️", "Mèo Tướng"),
    (1000, "👑", "Mèo Vương"),
]


def boss_rank(damage: int) -> dict:
    """Hạng của một người chơi theo tổng sát thương đã gây lên boss."""
    icon, title = BOSS_RANKS[0][1], BOSS_RANKS[0][2]
    for _threshold, ic, ti in BOSS_RANKS:
        if damage >= _threshold:
            icon, title = ic, ti
    return {"icon": icon, "title": title}


def boss_rank_index(damage: int) -> int:
    idx = 0
    for i, (threshold, _ic, _ti) in enumerate(BOSS_RANKS):
        if damage >= threshold:
            idx = i
    return idx


# Thoại chửi lại của Răng Sắt — viết riêng cho boss này, giọng vừa ghét vừa hề.
BOSS_TAUNT_STAGE = {
    1: "Á! Cái ăng-ten của ta! Đánh thế là chơi bẩn!",
    2: "Khói bốc là chuyện nhỏ... ta vẫn còn khỏe chán!",
    3: "Dừng lại đi! Ta chỉ... mượn tạm ít cá thôi mà!",
}
BOSS_TAUNT_SWARM = "Ở đâu ra lắm mèo thế này?!"
BOSS_TAUNT_BARRAGE = "Á á! Cá ở đâu rơi xuống thế này?!"
BOSS_TAUNTS_IDLE = [
    "Đừng tưởng đông mà ta sợ!",
    "Kho cá này là của ta!",
    "Mèo con mà đòi bắt chuột trùm à?",
    "Cào nữa đi, mới ngứa ngứa thôi!",
    "Ta đếm rồi, mèo nào cào nhiều nhất ta nhớ mặt!",
]


# Tàn Ảnh của Răng Sắt: mỗi vòng đấu, boss hiện hình một màu pha lê khác nhau
# (ảnh AI nhúng ở static/boss-art.js; sân khấu tra theo khoá skin).
SKINS = {
    "tu": "TỬ QUANG",
    "bang": "BĂNG QUANG",
    "luc": "LỤC QUANG",
    "hoa": "HỎA QUANG",
    "kim": "KIM QUANG",
}
# Tự động theo vòng: 1 Tử -> 2 Băng -> 3 Lục -> 4 Hỏa -> từ 5 trở đi Kim.
ROUND_SKINS = ["tu", "bang", "luc", "hoa", "kim"]


def boss_skin_for_round(round_no: int) -> str:
    """Khoá Tàn Ảnh của một vòng đấu (vòng >= 5 giữ Kim Quang)."""
    idx = min(max(int(round_no), 1), len(ROUND_SKINS)) - 1
    return ROUND_SKINS[idx]


# --- Câu mở màn / nhắc luật theo chế độ sân khấu (run giữ nguyên văn cũ) ---
OPENING_RUN = "Cả nhà gõ MEOW để nhận mèo, gõ CHẠY để vào đội chạy cùng Bug nha!"
OPENING_BOSS = ("Chào cả nhà đến với nhà của Bug! Hôm nay Chuột Trùm Răng Sắt mò vào "
                "cướp kho cá — cả nhà gõ CÀO để đánh boss cùng Bug nha! Tim đầy thanh Nộ, "
                "đủ 200 là mưa cá trút xuống đầu nó luôn!")
IDLE_RUN = ("Cả nhà ơi, gõ meow để nhận một bé mèo mang tên mình, gõ hạt để cho Bug ăn, "
            "gõ đua để đua mèo cùng nhau nha!")
IDLE_BOSS = ("Cả nhà ơi, gõ CÀO để tấn công Chuột Trùm Răng Sắt cùng Bug nha! Tim đầy "
             "thanh Nộ, đủ 200 là mưa cá trút xuống boss. Gõ HẠT cho Bug ăn lấy sức, "
             "gõ NGỦ cho Bug nghỉ một lát nha!")
OPENING_GARDEN = ("Chào cả nhà đến với Vườn Mèo của Bug! Mỗi bạn là một bé mèo với tính cách riêng — "
                  "gõ HẠT gọi ăn, gõ CHƠI rủ chơi, khen XINH QUÁ là có mèo tạo dáng liền. "
                  "Gom đủ 500 tim vườn là cả vườn mở tiệc nha!")
IDLE_GARDEN = ("Cả nhà ơi, đây là Vườn Mèo của Bug — mỗi bé mèo một tính cách! Gõ HẠT gọi mèo ăn, "
               "gõ CHƠI rủ hội Tăng Động đuổi bóng, gõ NGỦ cho hội Lười đi ngủ, khen XINH QUÁ là "
               "Chảnh tạo dáng liền. Tim vườn đủ mục tiêu là cả vườn mở tiệc nha!")
OPENING_MINER = ("Chào mừng cả nhà đến với MỎ VÀNG CỦA BUG! Hai đội Mèo và Chuột tranh nhau "
                 "từng cục vàng — gõ MÈO hoặc CHUỘT để vào đội, gõ ĐÀO để thả móc giật vàng. "
                 "Ai đào được nhiều vàng nhất sẽ là Vua Đào Vàng hôm nay!")
IDLE_MINER = ("Cả nhà ơi, mỏ vàng đang nóng! Gõ MÈO hoặc CHUỘT để vào đội, canh lúc móc quét "
              "qua cục vàng to thì gõ ĐÀO để giật về cho đội mình nha! Tim đầy thanh "
              "thuốc nổ là NỔ MÌN lộ vàng đó!")
OPENING_TUG = ("Chào cả nhà đến với HỘI KÉO CO của làng Bug! Gõ CAM vào đội Mèo Cam, "
               "gõ XÁM vào đội Mèo Xám — gõ KÉO là kéo dây, gõ HÒ là hò lấy sức! "
               "Đội nào kéo được cờ qua vạch của mình là thắng hiệp!")
IDLE_TUG = ("Cả nhà ơi, hội kéo co làng Bug đang sôi! Gõ CAM hoặc XÁM để vào đội, "
            "gõ KÉO kéo dây, gõ HÒ DÔ lấy khí thế cho đội mình nha! Kéo phải giữ sức — "
            "mèo đuối sức là kéo yếu hẳn đó. Tim đủ mốc là trống hội nổi lên, "
            "cả hai đội kéo mạnh hẳn!")
OPENING_OFFICE = ("Chào cả nhà đến với văn phòng của Bug! Sếp Răng Sắt đi tuần liên tục — "
                  "canh lúc sếp đi pha cà phê mà ăn vụng, nói chuyện, chơi game lén nha! "
                  "Bị bắt là ra đứng góc phạt đó. Đủ 200 tim là sếp phải đi nghỉ pha cà phê đó!")
IDLE_OFFICE = ("Cả nhà ơi, văn phòng đang giờ làm — sếp Răng Sắt đi tuần liên tục đó! "
               "Gõ ĂN ăn vụng, CHAT nói chuyện, GAME chơi lén, BUG cho Bug ăn, "
               "LÀM giả vờ gõ phím cho đỡ bị để ý nha. Canh lúc sếp xao lãng là điểm "
               "nhân đôi. Đủ 200 tim là sếp phải đi nghỉ pha cà phê 15 giây!")

# --- Đào Vàng PK: 2 đội móc vàng thi đấu theo hiệp ---------------------------
# Trường mỏ dùng toạ độ chuẩn hoá 0..1 (x theo chiều ngang sân khấu, y từ trên
# xuống). Giá trị + cân nặng của vật phẩm chỉ nằm phía server; sân khấu chỉ
# nhận {id, x, y, kind, r} — túi vàng giữ bí mật giá trị tới lúc giật trúng.
MINER_TEAM_NAMES = {"meo": "Mèo", "chuot": "Chuột"}
MINER_PIVOTS = {"meo": (0.20, 0.145), "chuot": (0.80, 0.145)}
MINER_ITEMS = {
    # kind:     (bán kính, giá trị (None = túi bí mật 5..100), cân nặng, % xuất hiện)
    "gold_s":  (0.028, 10,   1, 34),
    "gold_m":  (0.042, 25,   2, 24),
    "gold_l":  (0.060, 60,   4, 10),
    "diamond": (0.034, 150,  2, 4),
    "rock":    (0.040, 5,    5, 18),
    "bag":     (0.036, None, 2, 6),
    "bone":    (0.030, 1,    1, 4),
}
MINER_FIELD_SIZE = 26          # số vật phẩm giữ trên trường mỏ
MINER_ROUND_SECONDS = 100      # 1 hiệp đào
MINER_PODIUM_SECONDS = 12      # nghỉ công bố kết quả giữa 2 hiệp
MINER_HOOK_REACH = 0.825       # len=1 -> đầu móc chạm tối đa y=0.97 ở góc 0
MINER_DROP_PER_SEC = 1 / 0.9   # thả móc: hết tầm trong ~0.9s
MINER_PULL_PER_SEC = 1 / 0.7   # kéo tay không: về hết trong ~0.7s
MINER_SWING_DEG = 68.0         # biên độ quét của móc (độ)
MINER_SWING_PERIOD = 2.6       # chu kỳ quét qua lại (giây)
MINER_DAO_COOLDOWN = 1.5       # giây, chống spam ĐÀO theo monotonic
MINER_BAG_TARGET_VALUE = 50    # giá trị danh định của túi khi chọn mục tiêu móc vàng (quà to)

# --- Kéo Co: 2 đội mèo kéo dây theo hiệp -----------------------------------
# Vị trí cờ giữa dây: -100 (đầu sân Đội Cam) .. +100 (đầu sân Đội Xám);
# Cam kéo về phía âm, Xám kéo về phía dương. Vật lý xung lực + giảm chấn:
# một cú kéo chuẩn (lực 10) làm vel nhảy 10*K = 5.0, quãng dây chạy thêm
# trước khi tắt dần ~= vel/hệ số giảm chấn = 5.0/2.2 ~= 2.3 đơn vị.
TUG_TEAM_NAMES = {"cam": "Cam", "xam": "Xám"}
TUG_DIRS = {"cam": -1.0, "xam": 1.0}
TUG_ROUND_SECONDS = 90         # 1 hiệp kéo
TUG_PODIUM_SECONDS = 10        # nghỉ công bố kết quả giữa 2 hiệp
TUG_WIN_POS = 85.0             # |pos| >= 85 -> đoạt cờ, thắng hiệp ngay
TUG_PULL_COOLDOWN = 1.2        # giây, chống spam KÉO theo monotonic
TUG_CHEER_COOLDOWN = 3.0       # giây, chống spam HÒ theo monotonic
TUG_BASE_FORCE = 10.0          # lực gốc của 1 cú kéo
TUG_IMPULSE_K = 0.5            # hệ số xung lực: vel += hướng * lực * K
TUG_DAMPING = 2.2              # vel *= exp(-TUG_DAMPING * dt) mỗi tick
TUG_PULL_COST = 12.0           # thể lực trừ mỗi cú kéo
TUG_STAMINA_REGEN = 4.0        # thể lực hồi mỗi giây trong tick
TUG_TIRED_UNDER = 30.0         # thể lực dưới mốc này -> kéo yếu (hệ số 0.55)
TUG_TIRED_FACTOR = 0.55
TUG_CHEER_MORALE = 18.0        # khí thế cộng mỗi lần HÒ
TUG_MORALE_DECAY = 6.0         # khí thế hao mỗi giây trong tick
TUG_COMEBACK_POS = 70.0        # dây bị kéo lệch >= 70 chống lại đội mình
TUG_COMEBACK_FACTOR = 1.25     # -> hệ số lội ngược dòng
TUG_DRUMS_SECONDS = 15         # trống hội: cả 2 đội x1.5 trong 15s
TUG_DRUMS_MULT = 1.5
TUG_SUPER_YANK = 12.0          # giật siêu cấp (quà >= 100 kim cương): dây nhảy 12

# --- Văn Phòng Lén Lút: sếp tuần tra, cấm ăn uống ---------------------------
# Cả phòng HỢP TÁC chống sếp: nhân viên mèo lén ăn vụng / nói chuyện / chơi
# game lấy điểm; sếp Răng Sắt (mặc vest) đi tuần qua lại, dừng lại QUÉT MẮT
# là lúc nguy hiểm nhất. Canh sếp xao lãng (pha cà phê / nghe điện thoại /
# ngắm cửa sổ / tiệc / bánh) thì điểm NHÂN ĐÔI và không ai bị bắt.
OFFICE_DESKS = 8               # số bàn trong văn phòng (bàn của người chơi = ghế % 8)
OFFICE_FUND_GOAL = 500         # quỹ ăn vụng đủ 500 -> TIỆC VĂN PHÒNG 20s
OFFICE_COFFEE_GOAL = 200       # đủ 200 tim -> sếp buộc đi nghỉ pha cà phê 15s
OFFICE_SHIFT_SECONDS = 180     # 1 ca làm việc
OFFICE_SUMMARY_SECONDS = 12    # nghỉ tổng kết giữa 2 ca
OFFICE_ACTION_COOLDOWN = 2.0   # giây, chống spam theo TỪNG hành động (monotonic)
OFFICE_PENALTY_SECONDS = 20    # bị bắt -> đứng góc phạt 20s
OFFICE_BOSS_SPEED = 0.07       # tốc độ sếp đi tuần (đơn vị trục x 0..1 / giây)
OFFICE_DISTRACT_KINDS = ["coffee", "phone", "window"]  # xao lãng TỰ NHIÊN, xoay vòng
OFFICE_DISTRACT_PHRASES = {"coffee": "pha cà phê", "phone": "nghe điện thoại",
                           "window": "ngắm cửa sổ"}
# Hành động lén: điểm gốc + hệ số rủi ro (chỉ nguy hiểm khi sếp KHÔNG xao lãng;
# lúc sếp quét mắt (watch) rủi ro x0.55, lúc đi tuần (patrol) chỉ x0.18, và còn
# nhân hệ số gần-xa theo vị trí sếp so với cột bàn của người chơi).
OFFICE_ACTIONS = {
    "eat":  {"pts": 10, "risk": 0.50},   # ĂN: ăn vụng
    "chat": {"pts": 8,  "risk": 0.65},   # CHAT: nói chuyện với bạn cùng bàn
    "game": {"pts": 16, "risk": 0.90},   # GAME: chơi game lén (điểm cao, rủi ro cao)
    "work": {"pts": 2,  "risk": 0.0},    # LÀM: giả vờ gõ phím (an toàn, hạ nghi ngờ)
    "nap":  {"pts": 6,  "risk": 0.55},   # NGỦ: ngủ gật tại bàn
}
OFFICE_TEXT_TO_ACTION = {
    "an": "eat", "an vung": "eat", "an com": "eat", "an banh": "eat",
    "chat": "chat", "noi chuyen": "chat", "tam": "chat",
    "game": "game", "choi game": "game",
    "bug": "bug",
    "lam": "work", "lam viec": "work", "go phim": "work",
    "ngu": "nap", "ngu gat": "nap", "buon ngu": "nap",
}
# Thoại mắng của Sếp Răng Sắt khi bắt quả tang — viết riêng cho văn phòng này.
OFFICE_SCOLDS = [
    "Ai ăn vụng đó?! Ta ngửi thấy mùi mì tôm!",
    "Làm việc đi! Ta thấy hết đấy!",
    "Ra góc đứng! Chưa hết giờ làm đâu!",
    "Văn phòng là chỗ làm việc, không phải quán ăn!",
    "Ta nhắc lần cuối: cất hết đồ ăn đi!",
]

# --- Thoại tâm trạng của Bug (xoay vòng cho đỡ lặp) ---
OVERFEED_LINES = [
    "Bug no căng bụng rồi, đừng cho ăn nữa!",
    "No quá à... Bug khó chịu rồi đó!",
    "Ơ ơ, bụng Bug tròn vo rồi!",
]
REFUSE_FEED_LINES = [
    "Bug đang khó chịu, để Bug yên một lát!",
    "Bug chưa muốn ăn đâu, để Bug nghỉ chút!",
    "Thôi thôi, Bug đang khó chịu, lát nữa hãy cho ăn nha!",
]
SLEEP_TEXTS = {"ngu", "di ngu", "ngu di", "buon ngu", "cho bug ngu", "bug ngu", "ngu thoi"}


class GameState:
    MAX_SEATS = 120
    FEED_COOLDOWN = 5.0        # giây, chống spam cho ăn / cho ăn quá độ
    BOOST_COOLDOWN = 1.0
    CHAT_POINT_COOLDOWN = 10.0
    CLAW_COOLDOWN = 3.0        # giây, chống spam lệnh CÀO đánh boss
    RAGE_MAX = 200             # tim nạp đầy thanh Nộ ở chế độ Đánh Boss
    SYNC_WINDOW = 3.0          # cửa sổ trượt (giây) tính đòn ĐỒNG LOẠT
    SYNC_MIN_USERS = 5         # số người khác nhau cào trong cửa sổ để kích hoạt
    SYNC_DURATION = 3.0        # đồng loạt kéo dài 3s: mọi đòn cào đau x2
    SYNC_COOLDOWN = 10.0       # sau khi kích hoạt, 10s mới kích hoạt lại được
    COUNTER_INTERVAL = 40.0    # boss phản đòn (quét đuôi) mỗi ~40s nếu đủ người
    GOLD_CHANCE = 0.02         # tỉ lệ Mèo Vàng khi một người xem lần đầu vào phòng
    PRAISE_THROTTLE = 3.0      # giây (monotonic) giữa 2 lần cả vườn hưởng ứng lời khen
    HEART_TICK_SECONDS = 5.0   # nhịp sinh tim vườn (giây giờ game)
    RACE_MIN_PLAYERS = 3
    RACE_MAX_PLAYERS = 8
    RACE_LOBBY_SECONDS = 20
    RACE_COUNTDOWN_SECONDS = 5
    RACE_FINISH = 100.0

    def __init__(self, like_goal: int = 500, scores_path: Optional[str] = None,
                 rng: Optional[random.Random] = None, stage_mode: str = "run",
                 boss_max_hp: int = 1000, boss_taunts: bool = True,
                 boss_skin: str = "auto") -> None:
        self.players: Dict[str, Player] = {}
        self.like_goal = like_goal
        self.likes_since_rain = 0
        self.total_likes = 0
        self.bug_satiety = 55          # Độ no của Bug: 0..100
        self.bug_mood = "happy"
        # --- Tâm trạng Bug: cho ăn quá độ / bị phá giấc ngủ -> khó chịu ---
        self.bug_annoyance = 0.0       # Mức khó chịu: 0..100 (>= 60 là đang khó chịu)
        self.bug_sleep_until = 0.0     # Mốc wall-clock Bug ngủ tới; 0 = đang thức
        self.bug_annoyed_until = 0.0   # Mốc wall-clock còn khó chịu tối thiểu (~12s)
        self.bug_sleep_disturbances = 0  # Số lần bị phá trong giấc ngủ hiện tại
        self._bug_last_tick_at: Optional[float] = None  # tick trước, tính decay tâm trạng
        self._overfeed_idx = 0         # xoay vòng câu thoại khi bị cho ăn quá độ
        self._refuse_idx = 0           # xoay vòng câu thoại khi Bug từ chối (đang khó chịu)
        self.follows_count = 0
        self.shares_count = 0
        self.race = Race()
        self.scores_path = scores_path
        self.rng = rng or random.Random()
        self._next_seat = 0
        # --- chế độ sân khấu: run | boss | garden | miner | tug | office ---
        self.stage_mode = stage_mode if stage_mode in ("run", "boss", "garden", "miner", "tug", "office") else "run"
        # --- Vườn Mèo ---
        self.garden_hearts = 0             # tim vườn đã gom trong phiên
        self.garden_hearts_goal = 1000     # đủ mốc này -> Giờ Vàng (rồi mốc +1000)
        self.garden_feast_until = 0.0      # mốc wall-clock Bữa Tiệc Vườn còn mở
        self.garden_golden_hour_until = 0.0  # mốc wall-clock Giờ Vàng còn hiệu lực
        self.garden_decor_until = 0.0      # mốc wall-clock vườn còn trang trí (quà)
        self._garden_heart_acc = 0.0       # dồn dt cho nhịp sinh tim 5s
        self._garden_last_tick_at: Optional[float] = None  # tick vườn trước (tính dt)
        self._last_praise_mono = -100.0    # mốc monotonic lời khen hưởng ứng gần nhất
        self._golden_rolled: set = set()   # uid đã tung xúc xắc Mèo Vàng trong phiên
        self._golden_announced: set = set()  # uid Mèo Vàng đã được xướng tên
        # --- Đào Vàng PK: trường mỏ xây LƯỜI (lazy) khi vào chế độ miner, để
        # không tiêu tốn rng của các chế độ khác lúc khởi tạo ---
        self._miner_ready = False
        self.miner_items: List[dict] = []        # vật phẩm đang nằm trên trường mỏ
        self.miner_respawn_due: List[float] = []  # mốc wall-clock vật phẩm hồi lại
        self._miner_next_item_id = 1
        self.miner_hooks: Dict[str, dict] = {}   # mỗi đội 1 móc (xây ở _miner_ensure)
        self.miner_round = 1
        self.miner_phase = "play"                # play | podium
        self.miner_deadline = 0.0                # mốc wall-clock hết pha hiện tại
        self.miner_score: Dict[str, int] = {"meo": 0, "chuot": 0}   # điểm hiệp
        self.miner_wins: Dict[str, int] = {"meo": 0, "chuot": 0}    # số hiệp thắng
        self.miner_buffs: Dict[str, dict] = {
            t: {"mult": 1.0, "until": 0.0} for t in MINER_PIVOTS}
        self._miner_elapsed = 0.0                # giờ game của mỏ (cho móc quét)
        self._miner_last_tick_at: Optional[float] = None
        self._miner_reach: Dict[str, float] = {}  # uid -> mốc wall-clock đạt mốc vàng hiệp hiện tại
        self._miner_last_grab_speak_at = -100.0  # throttle đọc tin giật vàng to
        self._miner_last_join_speak = -100.0     # throttle đọc tin vào đội (monotonic)
        # --- Kéo Co: trạng thái dây; mốc hiệp hẹn LƯỜI (lazy) như mỏ để các
        # chế độ khác không bị ảnh hưởng lúc khởi tạo ---
        self._tug_ready = False
        self.tug_pos = 0.0                       # vị trí cờ: -100..+100
        self.tug_vel = 0.0                       # vận tốc dây (đơn vị/giây)
        self.tug_round = 1
        self.tug_phase = "play"                  # play | podium
        self.tug_deadline = 0.0                  # mốc wall-clock hết pha hiện tại
        self.tug_wins: Dict[str, int] = {"cam": 0, "xam": 0}      # số hiệp thắng
        self.tug_morale: Dict[str, float] = {"cam": 0.0, "xam": 0.0}  # khí thế 0..100
        self.tug_buffs: Dict[str, dict] = {
            t: {"mult": 1.0, "until": 0.0} for t in TUG_TEAM_NAMES}
        self.tug_drums_until = 0.0               # mốc wall-clock hết trống hội
        self._tug_last_tick_at: Optional[float] = None
        self._tug_last_pull_wall = 0.0           # mốc wall-clock cú kéo gần nhất
        self._tug_reach: Dict[str, float] = {}   # uid -> mốc đạt lực hiệp (chọn MVP)
        self._tug_last_join_speak = -100.0       # throttle đọc tin vào đội (monotonic)
        # --- Văn Phòng Lén Lút: máy trạng thái sếp + quỹ/cà phê/ca làm; đồng
        # hồ hẹn LƯỜI (lazy) như mỏ/kéo co để các chế độ khác không đổi rng ---
        self._office_ready = False
        self.ob_state = "patrol"          # patrol | watch | distracted | party | coffee | cake
        self.ob_kind = ""                 # loại xao lãng tự nhiên: coffee | phone | window
        self.ob_x = 0.5                   # vị trí sếp trên trục ngang sân khấu (0..1)
        self.ob_dir = 1                   # hướng sếp đang đi: -1 (trái) | +1 (phải)
        self.ob_deadline = 0.0            # mốc wall-clock hết trạng thái sếp hiện tại
        self._office_kind_idx = 0         # xoay vòng loại xao lãng tự nhiên
        self.office_fund = 0              # quỹ ăn vụng của cả phòng (đủ 500 -> tiệc)
        self.office_party_until = 0.0     # mốc wall-clock tiệc văn phòng còn mở
        self.office_coffee_likes = 0      # tim rót cà phê cho sếp (đủ 200 -> sếp nghỉ 15s)
        self.office_shift = 1             # số thứ tự ca làm việc
        self.office_phase = "play"        # play | summary (tổng kết ca)
        self.office_deadline = 0.0        # mốc wall-clock hết pha ca hiện tại
        self.office_bug_desk = 0          # bàn Bug đang nằm lang thang (0..7)
        self.office_bug_move_at = 0.0     # mốc wall-clock Bug đổi bàn lần tới
        self.office_bug_target_desk: Optional[int] = None  # bàn có người vừa gọi Bug tới
        self._office_last_tick_at: Optional[float] = None
        self._office_reach: Dict[str, float] = {}  # uid -> mốc đạt điểm ca (chọn người điểm cao nhất)
        self._office_last_feedbug_speak = -100.0   # throttle câu cảm ơn khi cho Bug ăn (monotonic)
        self.boss = Boss(boss_max_hp)
        self.damage_by_user: Dict[str, int] = {}   # sát thương cộng dồn trong phiên
        self.boss_total_damage = 0                 # gồm cả sát thương mưa cá (cả đội)
        self.boss_rage = 0                         # thanh Nộ: 0..RAGE_MAX
        self.last_hit_user: Optional[str] = None   # người ra đòn gần nhất (đòn kết liễu)
        self._boss_spawn_spoken = False            # chống lặp câu chào boss mỗi snapshot
        # --- boss v2: thoại / biến hình / đồng loạt / hạng / phản đòn ---
        self.boss_taunts = bool(boss_taunts)       # công tắc "Boss chửi lại"
        # Tàn Ảnh: "auto" = đổi màu theo vòng đấu; khoá skin = luôn dùng màu đó
        self.boss_skin_pref = boss_skin if boss_skin in SKINS else "auto"
        self._boss_stage_now = 0                  # giai đoạn biến hình hiện tại (0..3)
        self._boss_taunted: set = set()            # giai đoạn đã chửi ở vòng này
        self.claw_window: List = []                # [(uid, mono_ts)] cửa sổ trượt ĐỒNG LOẠT
        self.sync_until = 0.0                      # mốc monotonic hết hiệu lực đồng loạt
        self._last_sync_at: Optional[float] = None  # mốc monotonic kích hoạt gần nhất
        self._rank_announced: Dict[str, int] = {}  # uid -> chỉ số hạng đã xướng
        self._last_counter_at: Optional[float] = None  # mốc wall clock phản đòn gần nhất
        self._next_idle_taunt_at: Optional[float] = None  # mốc wall clock thoại rảnh tiếp
        self._now_mono = 0.0                       # mốc monotonic mới nhất thấy qua comment
        self._load_scores()
        if self.stage_mode == "miner":
            self._miner_ensure()
        if self.stage_mode == "tug":
            self._tug_ensure()
        if self.stage_mode == "office":
            self._office_ensure()

    # ------------------------------------------------------------- chế độ boss
    def set_boss_skin(self, pref: Optional[str]) -> None:
        """Đặt tuỳ chọn Tàn Ảnh: "auto" (theo vòng) hoặc một khoá trong SKINS."""
        if pref == "auto" or pref in SKINS:
            self.boss_skin_pref = pref

    def current_boss_skin(self) -> str:
        """Khoá Tàn Ảnh đang hiển thị: tuỳ chọn cố định thắng, không thì theo vòng."""
        if self.boss_skin_pref in SKINS:
            return self.boss_skin_pref
        return boss_skin_for_round(self.boss.round)

    # ------------------------------------------------------- tâm trạng Bug
    def opening_line(self) -> str:
        """Câu hướng dẫn đọc mở màn khi live kết nối / DEMO bắt đầu — theo chế độ."""
        if self.stage_mode == "boss":
            return OPENING_BOSS
        if self.stage_mode == "garden":
            return OPENING_GARDEN
        if self.stage_mode == "miner":
            return OPENING_MINER
        if self.stage_mode == "tug":
            return OPENING_TUG
        if self.stage_mode == "office":
            return OPENING_OFFICE
        return OPENING_RUN

    def idle_line(self) -> str:
        """Câu nhắc luật khi live im lặng lâu — theo chế độ sân khấu."""
        if self.stage_mode == "boss":
            return IDLE_BOSS
        if self.stage_mode == "garden":
            return IDLE_GARDEN
        if self.stage_mode == "miner":
            return IDLE_MINER
        if self.stage_mode == "tug":
            return IDLE_TUG
        if self.stage_mode == "office":
            return IDLE_OFFICE
        return IDLE_RUN

    # ------------------------------------------------------- Đào Vàng PK
    def _miner_ensure(self) -> None:
        """Dựng trường mỏ + 2 móc lần đầu vào chế độ miner (lazy, xem __init__)."""
        if self._miner_ready:
            return
        self._miner_ready = True
        self.miner_hooks = {
            team: {"pivot": pivot, "angle": 0.0, "len": 0.0, "state": "swing",
                   "carrying": None, "carrying_kind": None, "caller": None,
                   "golden": False}
            for team, pivot in MINER_PIVOTS.items()
        }
        self.miner_deadline = time.time() + MINER_ROUND_SECONDS
        while len(self.miner_items) < MINER_FIELD_SIZE:
            if self._miner_spawn_item() is None:
                break

    def _miner_random_kind(self) -> str:
        roll = self.rng.uniform(0, 100)
        acc = 0.0
        for kind, (_r, _v, _w, pct) in MINER_ITEMS.items():
            acc += pct
            if roll < acc:
                return kind
        return "gold_s"

    def _miner_spawn_item(self, kind: Optional[str] = None) -> Optional[dict]:
        """Sinh 1 vật phẩm ở vị trí ngẫu nhiên không chồng lấn (tối đa 40 lần thử)."""
        kind = kind or self._miner_random_kind()
        r, value, weight, _pct = MINER_ITEMS[kind]
        for _ in range(40):
            x = self.rng.uniform(0.03, 0.97)
            if kind == "gold_l":
                y = self.rng.uniform(0.55, 0.96)   # vàng to chìm sâu dưới đáy mỏ
            else:
                y = self.rng.uniform(0.20, 0.96)
            ok = True
            for it in self.miner_items:
                dx, dy = x - it["x"], y - it["y"]
                rr = r + it["r"] + 0.012
                if dx * dx + dy * dy < rr * rr:
                    ok = False
                    break
            if ok:
                item = {"id": self._miner_next_item_id, "kind": kind,
                        "x": round(x, 4), "y": round(y, 4), "r": r,
                        "value": value, "weight": weight}
                self._miner_next_item_id += 1
                self.miner_items.append(item)
                return item
        return None

    def _miner_team_size(self, team: str) -> int:
        return sum(1 for p in self.players.values() if p.team == team)

    def _miner_smaller_team(self) -> str:
        return "meo" if self._miner_team_size("meo") <= self._miner_team_size("chuot") else "chuot"

    def _miner_buff_mult(self, team: str, now_wall: float) -> float:
        buff = self.miner_buffs.get(team) or {}
        if now_wall < float(buff.get("until", 0.0)):
            return float(buff.get("mult", 1.0))
        return 1.0

    def _miner_join_team(self, p: Player, team: str, now: float) -> List[dict]:
        """Vào / đổi đội: điểm cá nhân giữ nguyên, vàng đội ở lại nơi đã kiếm."""
        self._miner_ensure()
        if p.team == team:
            return []
        p.team = team
        eff: dict = {"type": "miner_join", "user": p.unique_id,
                     "name": p.nickname, "team": team, "player": p.public(now)}
        if now - self._miner_last_join_speak >= 3.0:
            self._miner_last_join_speak = now
            eff["speak"] = (f"{p.nickname} vào Đội {MINER_TEAM_NAMES[team]}! "
                            "Gõ ĐÀO để thả móc đào vàng nha!")
            eff["speak_priority"] = 4
        return [eff]

    def _miner_try_dao(self, p: Player, now: float) -> List[dict]:
        """Gõ ĐÀO: chưa có đội thì tự vào đội ít người hơn trước, rồi thả móc
        của đội mình (móc đang bận / đang nguội / ngoài giờ đấu -> bỏ qua lặng lẽ)."""
        self._miner_ensure()
        effects: List[dict] = []
        if p.team is None:
            effects += self._miner_join_team(p, self._miner_smaller_team(), now)
        if self.miner_phase != "play":
            return effects
        if now - p.last_dao_at < MINER_DAO_COOLDOWN:
            return effects
        hook = self.miner_hooks[p.team]
        if hook["state"] != "swing":
            return effects
        p.last_dao_at = now
        hook["state"] = "drop"      # góc móc đóng băng tại thời điểm này
        hook["caller"] = p.unique_id
        hook["golden"] = False
        effects.append({"type": "miner_drop", "team": p.team,
                        "user": p.unique_id, "name": p.nickname})
        return effects

    def _miner_hook_tip(self, hook: dict) -> tuple:
        px, py = hook["pivot"]
        rad = math.radians(hook["angle"])
        reach = hook["len"] * MINER_HOOK_REACH
        return px + reach * math.sin(rad), py + reach * math.cos(rad)

    def _miner_credit(self, team: str, hook: dict, now_wall: float) -> List[dict]:
        """Móc kéo vật phẩm về tới nơi: cộng vàng cho đội + người thả móc."""
        item = hook["carrying"]
        caller_uid = hook["caller"]
        hook["carrying"] = None
        hook["carrying_kind"] = None
        hook["golden"] = False
        hook["caller"] = None
        if item is None:
            return []
        value = int(item["value"])
        self.miner_score[team] += value
        caller = self.players.get(caller_uid or "")
        if caller is not None:
            caller.gold_round += value
            caller.gold_total += value
            self._miner_reach[caller.unique_id] = now_wall
        eff: dict = {"type": "miner_grab", "team": team,
                     "user": caller_uid,
                     "name": caller.nickname if caller else "",
                     "kind": item["kind"], "value": value}
        flavor = {"gold_l": "VÀNG TO", "diamond": "KIM CƯƠNG", "bag": "TÚI VÀNG"}.get(item["kind"])
        if (flavor and value >= 60 and caller is not None
                and now_wall - self._miner_last_grab_speak_at >= 4.0):
            self._miner_last_grab_speak_at = now_wall
            eff["speak"] = (f"{caller.nickname} giật được {flavor} +{value} "
                            f"cho Đội {MINER_TEAM_NAMES[team]}!")
            eff["speak_priority"] = 3
        return [eff]

    def _miner_end_round(self, now_wall: float) -> List[dict]:
        """Hết giờ đào: chốt điểm, xướng đội thắng + Vua Đào Vàng của hiệp."""
        score_meo = self.miner_score["meo"]
        score_chuot = self.miner_score["chuot"]
        if score_meo > score_chuot:
            winner: Optional[str] = "meo"
        elif score_chuot > score_meo:
            winner = "chuot"
        else:
            winner = None
        if winner:
            self.miner_wins[winner] += 1
        mvp: Optional[Player] = None
        for p in self.players.values():
            if p.gold_round <= 0:
                continue
            if (mvp is None or p.gold_round > mvp.gold_round
                    or (p.gold_round == mvp.gold_round
                        and self._miner_reach.get(p.unique_id, 0.0)
                        < self._miner_reach.get(mvp.unique_id, 0.0))):
                mvp = p
        round_no = self.miner_round
        if winner:
            speak = (f"Hết hiệp {round_no}! Đội {MINER_TEAM_NAMES[winner]} thắng "
                     f"{score_meo}–{score_chuot}!")
        else:
            speak = f"Hiệp {round_no} hoà {score_meo}–{score_chuot}!"
        if mvp is not None:
            speak += (f" Vua Đào Vàng hiệp này là {mvp.nickname} "
                      f"với {mvp.gold_round} vàng!")
        eff = {"type": "miner_round_end", "round": round_no, "winner": winner,
               "score_meo": score_meo, "score_chuot": score_chuot,
               "mvp": mvp.unique_id if mvp else None,
               "mvp_name": mvp.nickname if mvp else "",
               "mvp_gold": mvp.gold_round if mvp else 0,
               "speak": speak, "speak_priority": 1}
        # Reset điểm hiệp + móc về trạng thái quét (vật đang kéo dở -> hồi lại sau)
        self.miner_score = {"meo": 0, "chuot": 0}
        self._miner_reach = {}
        for p in self.players.values():
            p.gold_round = 0
        for hook in self.miner_hooks.values():
            if hook["carrying"] is not None:
                self.miner_respawn_due.append(now_wall + self.rng.uniform(4, 8))
            hook["state"] = "swing"
            hook["len"] = 0.0
            hook["carrying"] = None
            hook["carrying_kind"] = None
            hook["caller"] = None
            hook["golden"] = False
        self.miner_phase = "podium"
        self.miner_deadline = now_wall + MINER_PODIUM_SECONDS
        return [eff]

    def _miner_tick(self, now_wall: float) -> List[dict]:
        """Nhịp mỏ trong tick(): chuyển pha hiệp, hồi vật phẩm, mô phỏng 2 móc.
        dt lấy theo mốc now_wall truyền vào (kẹp 0..5s) nên test bước được."""
        effects: List[dict] = []
        if not self._miner_ready:
            return effects
        if self._miner_last_tick_at is None:
            dt = 0.0
        else:
            dt = max(0.0, min(5.0, now_wall - self._miner_last_tick_at))
        self._miner_last_tick_at = now_wall
        self._miner_elapsed += dt

        # --- chuyển pha: hết giờ đào -> podium 12s -> hiệp mới ---
        if now_wall >= self.miner_deadline:
            if self.miner_phase == "play":
                effects += self._miner_end_round(now_wall)
            elif self.miner_phase == "podium":
                self.miner_round += 1
                self.miner_phase = "play"
                self.miner_deadline = now_wall + MINER_ROUND_SECONDS

        # --- hồi vật phẩm đã hẹn giờ ---
        if self.miner_respawn_due:
            due = [t for t in self.miner_respawn_due if t <= now_wall]
            self.miner_respawn_due = [t for t in self.miner_respawn_due if t > now_wall]
            for _ in due:
                self._miner_spawn_item()

        # --- mô phỏng móc từng đội ---
        for team, hook in self.miner_hooks.items():
            if hook["state"] == "swing":
                hook["angle"] = MINER_SWING_DEG * math.sin(
                    self._miner_elapsed * 2 * math.pi / MINER_SWING_PERIOD)
            elif hook["state"] == "drop":
                prev_x, prev_y = self._miner_hook_tip(hook)
                hook["len"] = min(1.0, hook["len"] + MINER_DROP_PER_SEC * dt)
                tip_x, tip_y = self._miner_hook_tip(hook)
                # Va chạm dọc ĐOẠN đường móc đi trong tick này: tick 0.5s móc
                # đi được một quãng dài, chỉ soi điểm cuối sẽ bỏ sót vật nhỏ.
                seg_dx, seg_dy = tip_x - prev_x, tip_y - prev_y
                seg_len2 = seg_dx * seg_dx + seg_dy * seg_dy
                hit = None
                hit_t = None
                for it in self.miner_items:
                    if seg_len2 <= 0:
                        t = 0.0
                    else:
                        t = ((it["x"] - prev_x) * seg_dx
                             + (it["y"] - prev_y) * seg_dy) / seg_len2
                        t = max(0.0, min(1.0, t))
                    cx, cy = prev_x + t * seg_dx, prev_y + t * seg_dy
                    dx, dy = it["x"] - cx, it["y"] - cy
                    if dx * dx + dy * dy <= it["r"] * it["r"] \
                            and (hit_t is None or t < hit_t):
                        hit, hit_t = it, t
                if hit is not None:
                    self.miner_items.remove(hit)
                    if hit["value"] is None:   # túi bí mật: tung giá trị lúc giật trúng
                        hit["value"] = self.rng.randint(5, 100)
                    hook["carrying"] = hit
                    hook["carrying_kind"] = hit["kind"]
                    hook["state"] = "pull"
                    self.miner_respawn_due.append(now_wall + self.rng.uniform(4, 8))
                elif hook["len"] >= 1.0 or not (0.01 < tip_x < 0.99) or tip_y > 0.98:
                    hook["state"] = "pull"
            elif hook["state"] == "pull":
                item = hook["carrying"]
                if item is None:
                    speed = MINER_PULL_PER_SEC
                else:
                    speed = (MINER_PULL_PER_SEC / (0.6 + 0.45 * item["weight"])
                             * self._miner_buff_mult(team, now_wall))
                    if hook["golden"]:
                        speed *= 3
                hook["len"] = max(0.0, hook["len"] - speed * dt)
                if hook["len"] <= 0.0:
                    hook["state"] = "swing"
                    effects += self._miner_credit(team, hook, now_wall)
        return effects

    # ------------------------------------------------------- Kéo Co
    def _tug_ensure(self) -> None:
        """Hẹn giờ hiệp đầu lần đầu vào chế độ kéo co (lazy, xem __init__)."""
        if self._tug_ready:
            return
        self._tug_ready = True
        self.tug_deadline = time.time() + TUG_ROUND_SECONDS

    def _tug_team_size(self, team: str) -> int:
        return sum(1 for p in self.players.values() if p.tug_team == team)

    def _tug_smaller_team(self) -> str:
        return "cam" if self._tug_team_size("cam") <= self._tug_team_size("xam") else "xam"

    def _tug_buff_mult(self, team: str, now_wall: float) -> float:
        buff = self.tug_buffs.get(team) or {}
        if now_wall < float(buff.get("until", 0.0)):
            return float(buff.get("mult", 1.0))
        return 1.0

    def _tug_set_buff(self, team: str, mult: float, seconds: float,
                      now_wall: float) -> dict:
        """Mỗi đội chỉ 1 ô buff: làm mới thì giữ hệ số cao hơn + hạn xa hơn."""
        cur = self.tug_buffs.get(team) or {"mult": 1.0, "until": 0.0}
        if (now_wall < float(cur.get("until", 0.0))
                and float(cur.get("mult", 1.0)) >= mult):
            cur = {"mult": float(cur["mult"]),
                   "until": max(float(cur["until"]), now_wall + seconds)}
        else:
            cur = {"mult": float(mult), "until": now_wall + seconds}
        self.tug_buffs[team] = cur
        return cur

    def _tug_join_team(self, p: Player, team: str, now: float) -> List[dict]:
        """Vào / đổi đội kéo co: thành tích cá nhân giữ nguyên."""
        self._tug_ensure()
        if p.tug_team == team:
            return []
        p.tug_team = team
        eff: dict = {"type": "tug_join", "user": p.unique_id,
                     "name": p.nickname, "team": team, "player": p.public(now)}
        if now - self._tug_last_join_speak >= 3.0:
            self._tug_last_join_speak = now
            eff["speak"] = (f"{p.nickname} vào Đội Mèo {TUG_TEAM_NAMES[team]}! "
                            "Gõ KÉO là kéo dây, gõ HÒ là hò lấy sức nha!")
            eff["speak_priority"] = 4
        return [eff]

    def _tug_try_pull(self, p: Player, now: float) -> List[dict]:
        """Gõ KÉO: chưa có đội thì tự vào đội ít người hơn trước; cú kéo tạo
        xung lực lên dây — lực tính theo thể lực (đuối sức kéo yếu), khí thế
        đội, buff quà/trống hội (lấy hệ số cao hơn) và thế trận lội ngược dòng
        khi dây đang bị kéo lệch sâu chống lại đội mình."""
        self._tug_ensure()
        effects: List[dict] = []
        if p.tug_team is None:
            effects += self._tug_join_team(p, self._tug_smaller_team(), now)
        if self.tug_phase != "play":
            return effects
        if now - p.last_tug_at < TUG_PULL_COOLDOWN:
            return effects
        p.last_tug_at = now
        team = p.tug_team
        now_wall = time.time()
        stamina_factor = 1.0 if p.stamina >= TUG_TIRED_UNDER else TUG_TIRED_FACTOR
        morale_factor = 1.0 + self.tug_morale[team] / 200.0
        buff_factor = max(self._tug_buff_mult(team, now_wall),
                          TUG_DRUMS_MULT if now_wall < self.tug_drums_until else 1.0)
        against = ((team == "cam" and self.tug_pos >= TUG_COMEBACK_POS)
                   or (team == "xam" and self.tug_pos <= -TUG_COMEBACK_POS))
        comeback_factor = TUG_COMEBACK_FACTOR if against else 1.0
        force = (TUG_BASE_FORCE * stamina_factor * morale_factor
                 * buff_factor * comeback_factor)
        self.tug_vel += TUG_DIRS[team] * force * TUG_IMPULSE_K
        p.stamina = max(0.0, p.stamina - TUG_PULL_COST)
        p.tug_pulls += 1
        p.tug_force += force
        p.tug_force_round += force
        self._tug_reach[p.unique_id] = now_wall
        self._tug_last_pull_wall = now_wall
        effects.append({"type": "tug_pull", "user": p.unique_id,
                        "name": p.nickname, "team": team,
                        "force": round(force, 1)})
        return effects

    def _tug_try_cheer(self, p: Player, now: float) -> List[dict]:
        """Gõ HÒ / HÒ DÔ: nạp khí thế cho đội mình (lực kéo + tối đa 50%)."""
        self._tug_ensure()
        effects: List[dict] = []
        if p.tug_team is None:
            effects += self._tug_join_team(p, self._tug_smaller_team(), now)
        if now - p.last_cheer_at < TUG_CHEER_COOLDOWN:
            return effects
        p.last_cheer_at = now
        team = p.tug_team
        self.tug_morale[team] = min(100.0, self.tug_morale[team] + TUG_CHEER_MORALE)
        effects.append({"type": "tug_cheer", "user": p.unique_id,
                        "name": p.nickname, "team": team,
                        "morale": round(self.tug_morale[team])})
        return effects

    def _tug_end_round(self, now_wall: float) -> List[dict]:
        """Chốt hiệp: thắng theo phía dây lệch (đoạt cờ |pos|>=85 hoặc hết giờ
        đội đang dẫn thắng; dây đứng giữa -> hoà). MVP = lực hiệp cao nhất,
        hoà lực thì ai chạm mốc trước thắng."""
        if self.tug_pos < 0:
            winner: Optional[str] = "cam"
        elif self.tug_pos > 0:
            winner = "xam"
        else:
            winner = None
        if winner:
            self.tug_wins[winner] += 1
        mvp: Optional[Player] = None
        for p in self.players.values():
            if p.tug_force_round <= 0:
                continue
            if (mvp is None or p.tug_force_round > mvp.tug_force_round
                    or (p.tug_force_round == mvp.tug_force_round
                        and self._tug_reach.get(p.unique_id, 0.0)
                        < self._tug_reach.get(mvp.unique_id, 0.0))):
                mvp = p
        round_no = self.tug_round
        if winner:
            speak = (f"Đoạt cờ! Đội Mèo {TUG_TEAM_NAMES[winner]} "
                     f"thắng hiệp {round_no}!")
            if mvp is not None:
                speak += f" Lực sĩ của hiệp: {mvp.nickname}!"
        else:
            speak = f"Hiệp {round_no} hoà — hai đội ngang tài ngang sức!"
        eff = {"type": "tug_round_end", "round": round_no,
               "winner": winner if winner else "draw",
               "pos": round(self.tug_pos, 1),
               "mvp": mvp.unique_id if mvp else None,
               "mvp_name": mvp.nickname if mvp else "",
               "mvp_force": int(round(mvp.tug_force_round)) if mvp else 0,
               "wins": dict(self.tug_wins),
               "speak": speak, "speak_priority": 1}
        # Reset cho hiệp sau: dây về giữa, vận tốc xoá, khí thế giữ một nửa
        self.tug_pos = 0.0
        self.tug_vel = 0.0
        for t in TUG_TEAM_NAMES:
            self.tug_morale[t] *= 0.5
        for p in self.players.values():
            p.tug_force_round = 0.0
        self._tug_reach = {}
        self.tug_phase = "podium"
        self.tug_deadline = now_wall + TUG_PODIUM_SECONDS
        return [eff]

    def _tug_tick(self, now_wall: float) -> List[dict]:
        """Nhịp kéo co trong tick(): chuyển pha hiệp, hao khí thế, hồi thể
        lực, tích phân vật lý dây + kiểm tra đoạt cờ. dt theo now_wall truyền
        vào (kẹp 0..5s) nên test bước được như mỏ."""
        effects: List[dict] = []
        if not self._tug_ready:
            return effects
        if self._tug_last_tick_at is None:
            dt = 0.0
        else:
            dt = max(0.0, min(5.0, now_wall - self._tug_last_tick_at))
        self._tug_last_tick_at = now_wall

        # --- chuyển pha: hết giờ -> công bố 10s -> hiệp mới ---
        if now_wall >= self.tug_deadline:
            if self.tug_phase == "play":
                effects += self._tug_end_round(now_wall)
            elif self.tug_phase == "podium":
                self.tug_round += 1
                self.tug_phase = "play"
                self.tug_deadline = now_wall + TUG_ROUND_SECONDS

        # --- khí thế hao dần, thể lực hồi dần ---
        if dt > 0:
            for t in TUG_TEAM_NAMES:
                self.tug_morale[t] = max(
                    0.0, self.tug_morale[t] - TUG_MORALE_DECAY * dt)
            for pl in self.players.values():
                if pl.stamina < 100.0:
                    pl.stamina = min(100.0, pl.stamina + TUG_STAMINA_REGEN * dt)

        # --- vật lý dây (chỉ trong giờ đấu) ---
        if self.tug_phase == "play" and dt > 0:
            self.tug_pos += self.tug_vel * dt
            self.tug_vel *= math.exp(-TUG_DAMPING * dt)
            # Cả phòng im ắng > 5s: dây tự nhích về giữa cho đỡ bế tắc
            # (chỉ trong vùng ±20, tránh lật ngược thế trận đang lệch sâu).
            if (now_wall - self._tug_last_pull_wall > 5.0
                    and 0.0 < abs(self.tug_pos) < 20.0):
                creep = min(abs(self.tug_pos), 0.4 * dt)
                self.tug_pos -= math.copysign(creep, self.tug_pos)
            self.tug_pos = max(-100.0, min(100.0, self.tug_pos))
            if abs(self.tug_pos) >= TUG_WIN_POS:
                effects += self._tug_end_round(now_wall)
        return effects

    # ------------------------------------------------------- Văn Phòng Lén Lút
    def _office_ensure(self) -> None:
        """Dựng đồng hồ sếp + ca làm lần đầu vào chế độ văn phòng (lazy)."""
        if self._office_ready:
            return
        self._office_ready = True
        now_wall = time.time()
        self.ob_state = "patrol"
        self.ob_kind = ""
        self.ob_deadline = now_wall + self.rng.uniform(8, 14)
        self.office_deadline = now_wall + OFFICE_SHIFT_SECONDS
        self.office_bug_desk = self.rng.randrange(OFFICE_DESKS)
        self.office_bug_move_at = now_wall + self.rng.uniform(12, 20)

    def _office_is_safe(self, now_wall: Optional[float] = None) -> bool:
        """An toàn = sếp đang xao lãng (tự nhiên / cà phê / bánh / tiệc):
        hành động lén không bị bắt và điểm nhân đôi."""
        now_wall = time.time() if now_wall is None else now_wall
        return (self.ob_state in ("distracted", "party", "coffee", "cake")
                or now_wall < self.office_party_until)

    @staticmethod
    def _office_desk_x(desk: int) -> float:
        """Trục x của cột bàn: bàn chẵn (cột trái) 0.30, bàn lẻ (cột phải) 0.70."""
        return 0.30 if desk % 2 == 0 else 0.70

    def _office_boss_advance(self, now_wall: float) -> List[dict]:
        """Hết giờ một trạng thái sếp -> chuyển trạng thái kế:
        patrol -> watch -> (45% xao lãng tự nhiên | quay lại patrol) -> patrol...
        Các trạng thái bị ÉP (coffee/cake) hết giờ cũng về patrol."""
        effects: List[dict] = []
        if self.ob_state == "patrol":
            self.ob_state = "watch"
            self.ob_kind = ""
            self.ob_deadline = now_wall + self.rng.uniform(4, 6)
        elif self.ob_state == "watch":
            if self.rng.random() < 0.45:
                kind = OFFICE_DISTRACT_KINDS[
                    self._office_kind_idx % len(OFFICE_DISTRACT_KINDS)]
                self._office_kind_idx += 1
                self.ob_state = "distracted"
                self.ob_kind = kind
                self.ob_deadline = now_wall + self.rng.uniform(6, 10)
                effects.append({
                    "type": "office_safe", "kind": kind,
                    "speak": (f"Sếp đi {OFFICE_DISTRACT_PHRASES[kind]} rồi — "
                              "LÉN THÔI CẢ NHÀ ƠI!"),
                    "speak_priority": 3,
                })
            else:
                self.ob_state = "patrol"
                self.ob_kind = ""
                self.ob_deadline = now_wall + self.rng.uniform(8, 14)
        else:  # distracted | coffee | cake
            self.ob_state = "patrol"
            self.ob_kind = ""
            self.ob_deadline = now_wall + self.rng.uniform(8, 14)
        return effects

    def _office_start_party(self, now_wall: float, seconds: float) -> None:
        """Mở / gia hạn TIỆC VĂN PHÒNG: sếp bị ép sang trạng thái party
        (an toàn tuyệt đối) tới mốc party_until xa nhất."""
        self.office_party_until = max(self.office_party_until,
                                      now_wall + seconds)
        self.ob_state = "party"
        self.ob_kind = ""
        self.ob_deadline = self.office_party_until

    def _office_check_party(self, now_wall: float) -> List[dict]:
        """Quỹ ăn vụng đủ 500 và đang không tiệc -> mở TIỆC VĂN PHÒNG 20s."""
        if (self.office_fund >= OFFICE_FUND_GOAL
                and now_wall >= self.office_party_until):
            self.office_fund -= OFFICE_FUND_GOAL
            self._office_start_party(now_wall, 20)
            return [{
                "type": "office_party", "source": "fund",
                "speak": ("🎉 TIỆC VĂN PHÒNG! Sếp cũng ăn bánh rồi — làm gì "
                          "cũng không bị bắt đâu, quẩy lên!"),
                "speak_priority": 1,
            }]
        return []

    def _office_caught(self, p: Player, action: str,
                       now_wall: float) -> List[dict]:
        """Bắt quả tang: đứng góc phạt 20s, cả phòng bị trừ quỹ 30,
        nghi ngờ xoá sạch, sếp đọc một câu mắng (xoay vòng ngẫu nhiên)."""
        p.penalty_until = now_wall + OFFICE_PENALTY_SECONDS
        p.caught_round += 1
        self.office_fund = max(0, self.office_fund - 30)
        p.suspicion = 0.0
        line = self.rng.choice(OFFICE_SCOLDS)
        return [{
            "type": "office_caught", "user": p.unique_id, "name": p.nickname,
            "action": action, "boss_line": line,
            "speak": line, "speak_priority": 2,
        }]

    def _office_try_action(self, p: Player, action: str,
                           now: float) -> List[dict]:
        """Một hành động lén lút của nhân viên mèo (ĂN/CHAT/GAME/BUG/LÀM/NGỦ).

        Chặn khi: đang tổng kết ca, đang đứng góc phạt, còn cooldown của
        chính hành động đó (2s). Bắt quả tang: an toàn -> không bao giờ bị
        bắt; không thì xác suất = risk x (0.55 nếu sếp đang quét mắt, 0.18
        nếu đang đi tuần) x hệ số gần-xa theo cột bàn. Thoát bắt lúc sếp
        quét mắt vẫn bị +30 nghi ngờ (thoát hoạ trong gang tấc) — nghi ngờ
        chạm 100 thì bị bắt vì "bị để ý quá nhiều"."""
        self._office_ensure()
        if self.office_phase != "play":
            return []
        now_wall = time.time()
        if now_wall < p.penalty_until:
            return []
        if now - p.last_office.get(action, -100.0) < OFFICE_ACTION_COOLDOWN:
            return []
        p.last_office[action] = now
        desk = p.seat % OFFICE_DESKS
        safe = self._office_is_safe(now_wall)

        # --- phân loại hành động: cho Bug ăn tuỳ Bug có đang ở bàn mình ---
        if action == "bug":
            if self.office_bug_desk == desk:
                key, pts, risk = "feedbug", 20, 0.40
            else:
                key, pts, risk = "callbug", 3, 0.40
                self.office_bug_target_desk = desk  # gọi Bug lần mò tới bàn mình
        else:
            spec = OFFICE_ACTIONS[action]
            key, pts, risk = action, spec["pts"], spec["risk"]
        p.office_act = key
        p.office_act_until = now_wall + 2.5

        effects: List[dict] = []
        if risk > 0 and not safe:
            prox = (1.15 if abs(self.ob_x - self._office_desk_x(desk)) < 0.25
                    else 0.8)
            catch_p = risk * (0.55 if self.ob_state == "watch" else 0.18) * prox
            if self.rng.random() < catch_p:
                return self._office_caught(p, key, now_wall)
            if self.ob_state == "watch":
                p.suspicion += 30
                if p.suspicion >= 100:
                    return self._office_caught(p, key, now_wall)
                effects.append({
                    "type": "office_warn", "user": p.unique_id,
                    "name": p.nickname, "suspicion": round(p.suspicion),
                })

        # --- thành công: điểm (nhân đôi lúc an toàn) vào cá nhân + quỹ ---
        if safe:
            pts *= 2
        if key == "work":
            p.suspicion = max(0.0, p.suspicion - 20)
        p.office_pts += pts
        p.office_pts_total += pts
        self._office_reach[p.unique_id] = now_wall
        self.office_fund += pts
        eff: dict = {"type": "office_action", "user": p.unique_id,
                     "name": p.nickname, "action": key, "pts": pts,
                     "safe": safe, "desk": desk}
        if (key == "feedbug"
                and now - self._office_last_feedbug_speak >= 6.0):
            self._office_last_feedbug_speak = now
            eff["speak"] = f"Bug cảm ơn {p.nickname}!"
            eff["speak_priority"] = 4
        effects.append(eff)
        effects += self._office_check_party(now_wall)
        return effects

    def _office_end_shift(self, now_wall: float) -> List[dict]:
        """Chốt ca: xướng nhân viên lén lút điểm cao nhất + người bị bắt
        nhiều nhất của ca, rồi vào 12s tổng kết (hành động bị khoá)."""
        top: Optional[Player] = None
        for p in self.players.values():
            if p.office_pts <= 0:
                continue
            if (top is None or p.office_pts > top.office_pts
                    or (p.office_pts == top.office_pts
                        and self._office_reach.get(p.unique_id, 0.0)
                        < self._office_reach.get(top.unique_id, 0.0))):
                top = p
        most: Optional[Player] = None
        for p in self.players.values():
            if p.caught_round <= 0:
                continue
            if most is None or p.caught_round > most.caught_round:
                most = p
        speak = f"Hết ca {self.office_shift}!"
        if top is not None:
            speak += (f" 🏆 Nhân viên lén lút của ca: {top.nickname} "
                      f"với {top.office_pts} điểm!")
        if most is not None:
            speak += (f" 🐀 Bị bắt nhiều nhất: {most.nickname} — "
                      f"{most.caught_round} lần ra góc!")
        if top is None and most is None:
            speak += " Cả phòng ngoan quá, chẳng ai lén lút gì cả!"
        eff = {"type": "office_shift_end", "shift": self.office_shift,
               "top_user": top.unique_id if top else None,
               "top_name": top.nickname if top else "",
               "top_pts": top.office_pts if top else 0,
               "most_caught_user": most.unique_id if most else None,
               "most_caught_name": most.nickname if most else "",
               "most_caught": most.caught_round if most else 0,
               "speak": speak, "speak_priority": 1}
        self.office_phase = "summary"
        self.office_deadline = now_wall + OFFICE_SUMMARY_SECONDS
        return [eff]

    def _office_tick(self, now_wall: float) -> List[dict]:
        """Nhịp văn phòng trong tick(): tiệc ép trạng thái sếp, máy trạng
        thái sếp, sếp đi tuần, nghi ngờ nguội dần, Bug đổi bàn, chuyển ca.
        dt theo now_wall truyền vào (kẹp 0..5s) nên test bước được."""
        effects: List[dict] = []
        if not self._office_ready:
            return effects
        if self._office_last_tick_at is None:
            dt = 0.0
        else:
            dt = max(0.0, min(5.0, now_wall - self._office_last_tick_at))
        self._office_last_tick_at = now_wall

        # --- tiệc văn phòng: sếp bị cuốn vào tiệc cho tới party_until ---
        if now_wall < self.office_party_until:
            if self.ob_state != "party":
                self.ob_state = "party"
                self.ob_kind = ""
            self.ob_deadline = self.office_party_until
        elif self.ob_state == "party":
            self.ob_state = "patrol"
            self.ob_kind = ""
            self.ob_deadline = now_wall + self.rng.uniform(8, 14)

        # --- máy trạng thái sếp (tiệc xử lý riêng ở trên) ---
        if self.ob_state != "party" and now_wall >= self.ob_deadline:
            effects += self._office_boss_advance(now_wall)

        # --- sếp đi tuần: chạy qua lại giữa 0.12 và 0.88, chạm biên thì quay đầu ---
        if self.ob_state == "patrol" and dt > 0:
            self.ob_x += self.ob_dir * OFFICE_BOSS_SPEED * dt
            if self.ob_x >= 0.88:
                self.ob_x = 0.88
                self.ob_dir = -1
            elif self.ob_x <= 0.12:
                self.ob_x = 0.12
                self.ob_dir = 1

        # --- nghi ngờ nguội dần theo thời gian ---
        if dt > 0:
            for pl in self.players.values():
                if pl.suspicion > 0:
                    pl.suspicion = max(0.0, pl.suspicion - 3.0 * dt)

        # --- Bug lang thang: mỗi 12–20s đổi sang bàn khác; có người gọi thì
        # 50% Bug mò đúng tới bàn người gọi ---
        if now_wall >= self.office_bug_move_at:
            target = self.office_bug_target_desk
            self.office_bug_target_desk = None
            if (target is not None and target != self.office_bug_desk
                    and self.rng.random() < 0.5):
                self.office_bug_desk = target
            else:
                choices = [d for d in range(OFFICE_DESKS)
                           if d != self.office_bug_desk]
                self.office_bug_desk = self.rng.choice(choices)
            self.office_bug_move_at = now_wall + self.rng.uniform(12, 20)

        # --- chuyển pha ca: hết giờ -> tổng kết 12s -> ca mới, reset điểm ca ---
        if now_wall >= self.office_deadline:
            if self.office_phase == "play":
                effects += self._office_end_shift(now_wall)
            else:
                self.office_shift += 1
                self.office_phase = "play"
                self.office_deadline = now_wall + OFFICE_SHIFT_SECONDS
                for pl in self.players.values():
                    pl.office_pts = 0
                    pl.caught_round = 0
                    pl.suspicion = 0.0
                    pl.penalty_until = 0.0
                self._office_reach = {}
        return effects

    # ------------------------------------------------------- Vườn Mèo: tính cách
    def _assign_cat(self, p: Player) -> None:
        """Gán tính cách ổn định theo tên + tung xúc xắc Mèo Vàng đúng 1 lần/phiên."""
        if not p.personality:
            p.personality = personality_for_uid(p.unique_id)
        if p.unique_id not in self._golden_rolled:
            self._golden_rolled.add(p.unique_id)
            if self.rng.random() < self.GOLD_CHANCE:
                p.personality = "gold"
                p.golden = True

    def _golden_fx(self, p: Player) -> List[dict]:
        """Xướng Mèo Vàng xuất hiện (1 lần mỗi bé, chỉ ở chế độ vườn)."""
        if (self.stage_mode != "garden" or not p.golden
                or p.unique_id in self._golden_announced):
            return []
        self._golden_announced.add(p.unique_id)
        return [{
            "type": "garden_golden", "player": p.public(),
            "speak": "✨ Mèo Vàng xuất hiện trong vườn! Ở gần là tim nhân đôi đó cả nhà ơi!",
            "speak_priority": 1,
        }]

    def _garden_set_state(self, p: Player, state: str, seconds: float,
                          now_wall: float) -> None:
        p.state = state
        p.state_until = now_wall + seconds

    def _garden_bump(self, p: Player, delta: float) -> None:
        p.happiness = max(0.0, min(100.0, p.happiness + delta))

    def _garden_react_feed(self, actor: Player) -> List[dict]:
        """Gõ HẠT/PATE: hội Ham Ăn lao tới bát; mèo đang ngủ trưa bị đánh thức."""
        now_wall = time.time()
        for cat in self.players.values():
            sleeping = cat.eff_state(now_wall) == "sleep"
            if cat.personality == "foodie" or cat.golden:
                self._garden_set_state(cat, "eat", 6, now_wall)
                self._garden_bump(cat, 20)
            elif cat.personality == "sleepy" and sleeping:
                self._garden_set_state(cat, "idle", 0, now_wall)
                self._garden_bump(cat, -8)
            else:
                self._garden_set_state(cat, "eat", 4, now_wall)
                self._garden_bump(cat, 6)
        return [{"type": "garden_feed", "user": actor.unique_id, "name": actor.nickname}]

    def _garden_react_sleep(self) -> None:
        """Gõ NGỦ: hội Lười Ngủ chìm vào giấc 20s; hội Tăng Động thì buồn chán."""
        now_wall = time.time()
        for cat in self.players.values():
            if cat.personality == "sleepy":
                self._garden_set_state(cat, "sleep", 20, now_wall)
                self._garden_bump(cat, 15)
            elif cat.personality == "hyper":
                self._garden_bump(cat, -5)

    def _garden_react_play(self, actor: Player) -> List[dict]:
        """Gõ CHƠI: hội Tăng Động đuổi bóng; Chảnh phớt lờ; Nhút Nhát giật mình núp."""
        now_wall = time.time()
        for cat in self.players.values():
            if cat.personality == "hyper" or cat.golden:
                self._garden_set_state(cat, "play", 6, now_wall)
                self._garden_bump(cat, 20)
            elif cat.personality == "diva":
                pass  # Chảnh phớt lờ, không đổi trạng thái lẫn độ vui
            elif cat.personality == "shy":
                self._garden_set_state(cat, "hide", 3, now_wall)
                self._garden_bump(cat, -4)
            else:
                self._garden_bump(cat, 4)
        return [{"type": "garden_play", "user": actor.unique_id, "name": actor.nickname}]

    def _garden_react_praise(self, actor: Player, now_mono: float) -> List[dict]:
        """Lời khen: Chảnh tạo dáng, Nhút Nhát ló đầu ra. Chặn spam 1 lần / 3s."""
        if now_mono - self._last_praise_mono < self.PRAISE_THROTTLE:
            return []
        self._last_praise_mono = now_mono
        now_wall = time.time()
        diva = None
        for cat in self.players.values():
            if cat.personality == "diva":
                diva = cat
                self._garden_set_state(cat, "pose", 5, now_wall)
                self._garden_bump(cat, 20)
            elif cat.personality == "shy":
                self._garden_set_state(cat, "peek", 3, now_wall)
                self._garden_bump(cat, 12)
            else:
                self._garden_bump(cat, 3)
        eff: dict = {"type": "garden_praise", "user": actor.unique_id,
                     "name": actor.nickname}
        if diva is not None:
            eff["speak"] = f"{diva.nickname} nghe khen là tạo dáng liền kìa!"
            eff["speak_priority"] = 5
        return [eff]

    def _garden_react_fish(self, actor: Player) -> List[dict]:
        """Gõ CÁ: hội Mê Cá chầu chực kho cá; Ham Ăn cũng hóng theo."""
        now_wall = time.time()
        for cat in self.players.values():
            if cat.personality == "fishy" or cat.golden:
                self._garden_set_state(cat, "hoard", 6, now_wall)
                self._garden_bump(cat, 18)
            elif cat.personality == "foodie":
                self._garden_bump(cat, 6)
        return [{"type": "garden_fish", "user": actor.unique_id, "name": actor.nickname}]

    def _garden_scatter(self) -> List[dict]:
        """Bug bị phá giấc dậy cáu (ở chế độ vườn): cả đàn mèo tản ra né."""
        now_wall = time.time()
        for cat in self.players.values():
            self._garden_set_state(cat, "hide", 3, now_wall)
            self._garden_bump(cat, -5)
        return [{"type": "garden_scatter"}]

    def _garden_check_golden_hour(self, now_wall: float) -> List[dict]:
        """Đủ mốc tim vườn -> Giờ Vàng 30s: cả vườn mở tiệc lớn, mốc sau +1000."""
        if self.garden_hearts < self.garden_hearts_goal:
            return []
        if now_wall < self.garden_golden_hour_until:
            return []
        self.garden_golden_hour_until = now_wall + 30
        self.garden_hearts_goal += 1000
        for cat in self.players.values():
            self._garden_set_state(cat, "feast", 30, now_wall)
        return [{
            "type": "garden_golden_hour",
            "speak": "🌇 Giờ Vàng tới rồi! Cả vườn mở tiệc lớn, tim bay ngập trời!",
            "speak_priority": 1,
        }]

    def _garden_tick(self, now_wall: float) -> List[dict]:
        """Nhịp vườn trong tick(): độ vui trôi về 55 + sinh tim mỗi 5s giờ game.
        Có Mèo Vàng trong vườn thì lượng tim sinh ra nhân đôi."""
        effects: List[dict] = []
        if self._garden_last_tick_at is None:
            dt = 0.0
        else:
            dt = max(0.0, min(5.0, now_wall - self._garden_last_tick_at))
        self._garden_last_tick_at = now_wall
        if dt > 0:
            for cat in self.players.values():
                drift = 55.0 - cat.happiness
                step = max(-0.6 * dt, min(0.6 * dt, drift))
                cat.happiness = max(0.0, min(100.0, cat.happiness + step))
        self._garden_heart_acc += dt
        while self._garden_heart_acc >= self.HEART_TICK_SECONDS:
            self._garden_heart_acc -= self.HEART_TICK_SECONDS
            mult = 2 if any(c.golden for c in self.players.values()) else 1
            batch = 0
            for cat in self.players.values():
                gain = (1 + (1 if cat.happiness >= 75 else 0)) * mult
                cat.hearts += gain
                batch += gain
            self.garden_hearts += batch
            effects += self._garden_check_golden_hour(now_wall)
        return effects

    def _bug_sleeping(self, now_wall: float) -> bool:
        return self.bug_sleep_until > now_wall

    def _bug_annoyed(self, now_wall: float) -> bool:
        """Đang khó chịu: mức bực >= 60, hoặc còn trong ~12s dư âm sau khi hạ nhiệt."""
        return self.bug_annoyance >= 60 or now_wall < self.bug_annoyed_until

    def _bug_disturb(self, now_wall: float) -> List[dict]:
        """Phá giấc ngủ của Bug (cho ăn / gọi ngủ / tặng quà lúc Bug đang ngủ).
        Lần thứ 3 trong cùng một giấc: Bug thức dậy trong trạng thái khó chịu."""
        self.bug_sleep_disturbances += 1
        effects: List[dict] = [{"type": "bug_disturbed",
                                "disturbances": self.bug_sleep_disturbances}]
        if self.bug_sleep_disturbances >= 3:
            self.bug_sleep_until = 0.0
            self.bug_sleep_disturbances = 0
            self.bug_annoyance = max(self.bug_annoyance, 70.0)
            self.bug_annoyed_until = now_wall + 12
            effects.append({
                "type": "bug_wake_annoyed",
                "speak": "Ai phá giấc ngủ của Bug hoài vậy! Bug khó chịu rồi đó!",
                "speak_priority": 2,
            })
            if self.stage_mode == "garden":
                # Bug cáu ở Vườn Mèo: cả đàn mèo tản ra né một lúc
                effects += self._garden_scatter()
        return effects

    def _mood_tick(self, now_wall: float) -> List[dict]:
        """Chạy trong tick(): hạ nhiệt mức khó chịu (ngủ hạ nhanh hơn),
        Bug ngủ đủ giấc thì tự thức dậy, còn bực thì gia hạn trạng thái khó chịu."""
        effects: List[dict] = []
        if self._bug_last_tick_at is None:
            dt = 0.5
        else:
            dt = max(0.0, min(5.0, now_wall - self._bug_last_tick_at))
        self._bug_last_tick_at = now_wall
        # Ngủ đủ giấc -> tự dậy, hạ bớt khó chịu
        if self.bug_sleep_until and now_wall >= self.bug_sleep_until:
            self.bug_sleep_until = 0.0
            self.bug_sleep_disturbances = 0
            self.bug_annoyance = max(0.0, self.bug_annoyance - 20)
            effects.append({
                "type": "bug_wake",
                "speak": "Bug ngủ dậy rồi nè, khỏe re!",
                "speak_priority": 4,
            })
        sleeping = self._bug_sleeping(now_wall)
        rate = 2.0 if sleeping else 0.4
        if self.bug_annoyance > 0:
            self.bug_annoyance = max(0.0, self.bug_annoyance - rate * dt)
        if self.bug_annoyance >= 60:
            self.bug_annoyed_until = now_wall + 12
        return effects

    def set_stage_mode(self, mode: str, boss_max_hp: Optional[int] = None,
                       boss_taunts: Optional[bool] = None,
                       boss_skin: Optional[str] = None) -> None:
        """Đổi chế độ sân khấu (run | boss | garden | miner | tug | office) + áp máu boss / thoại từ config."""
        if mode not in ("run", "boss", "garden", "miner", "tug", "office"):
            return
        if mode == "miner":
            self._miner_ensure()
        if mode == "tug":
            self._tug_ensure()
        if mode == "office":
            self._office_ensure()
        if boss_taunts is not None:
            self.boss_taunts = bool(boss_taunts)
        if boss_skin is not None:
            self.set_boss_skin(boss_skin)
        if mode == "boss" and self.stage_mode != "boss":
            self._boss_spawn_spoken = False  # lần tick tới sẽ xướng boss xuất hiện
            self._boss_stage_now = 0
            self._boss_taunted = set()
        self.stage_mode = mode
        if boss_max_hp:
            boss_max_hp = int(boss_max_hp)
            untouched = self.boss.hp >= self.boss.max_hp
            self.boss.max_hp = boss_max_hp
            if untouched:
                self.boss.hp = boss_max_hp
            elif self.boss.hp > boss_max_hp:
                self.boss.hp = boss_max_hp

    def _top_damage(self, top: int = 5) -> List[dict]:
        ranked = sorted(self.damage_by_user.items(), key=lambda kv: (-kv[1], kv[0]))
        return [{
            "unique_id": uid,
            "name": self.players[uid].nickname if uid in self.players else uid,
            "damage": dmg,
            "rank": boss_rank(dmg),
        } for uid, dmg in ranked[:top]]

    def _boss_form_stage(self) -> int:
        """Giai đoạn biến hình theo tỉ lệ máu còn: 0 thường, 1 rụng ăng-ten/hút khói,
        2 khói + mắt đỏ, 3 nứt vỏ + run rẩy. Boss chết thì về 0."""
        if not self.boss.alive or self.boss.max_hp <= 0:
            return 0
        frac = self.boss.hp / self.boss.max_hp
        if frac > 0.75:
            return 0
        if frac > 0.50:
            return 1
        if frac > 0.25:
            return 2
        return 3

    def _boss_taunt_effect(self, text: str, spoken: bool = True) -> dict:
        """Effect thoại boss: sân khấu hiện bong bóng; spoken=True thì đọc luôn
        bằng giọng đọc ở mức ưu tiên THẤP NHẤT (5) để không chen câu chính."""
        eff: dict = {"type": "boss_taunt", "text": text}
        if spoken:
            eff["speak"] = text
            eff["speak_priority"] = 5
        return eff

    def _boss_apply_damage(self, dmg: int, uid: Optional[str] = None,
                           now_wall: Optional[float] = None) -> List[dict]:
        """Trừ máu boss + ghi công người đánh (uid=None = sát thương cả đội).
        Trả effects phụ có thể phát sinh: rank_up (thăng hạng), boss_taunt
        (vượt mốc biến hình) và boss_down nếu đòn này kết liễu boss."""
        if dmg <= 0 or not self.boss.alive:
            return []
        self.boss.hp = max(0, self.boss.hp - int(dmg))
        self.boss_total_damage += int(dmg)
        effects: List[dict] = []
        if uid:
            self.damage_by_user[uid] = self.damage_by_user.get(uid, 0) + int(dmg)
            self.last_hit_user = uid
            # Thăng hạng mèo: chỉ xướng 1 lần cho mỗi mốc của mỗi người
            new_idx = boss_rank_index(self.damage_by_user[uid])
            if new_idx > self._rank_announced.get(uid, 0):
                self._rank_announced[uid] = new_idx
                rank = boss_rank(self.damage_by_user[uid])
                name = self.players[uid].nickname if uid in self.players else uid
                effects.append({
                    "type": "rank_up", "user": uid, "name": name,
                    "rank_icon": rank["icon"], "rank_title": rank["title"],
                    "speak": f"Chúc mừng {name} thăng hạng {rank['title']}!",
                    "speak_priority": 2,
                })
        if self.boss.hp <= 0:
            effects += self._boss_die(time.time() if now_wall is None else now_wall)
            return effects
        # Vượt mốc biến hình (75/50/25%): boss chửi 1 câu, đúng 1 lần mỗi mốc mỗi vòng
        stage = self._boss_form_stage()
        if stage > self._boss_stage_now:
            for s in range(self._boss_stage_now + 1, stage + 1):
                self._boss_taunted.add(s)
            self._boss_stage_now = stage
            if self.boss_taunts and stage in BOSS_TAUNT_STAGE:
                effects.append(self._boss_taunt_effect(BOSS_TAUNT_STAGE[stage]))
        return effects

    def _boss_die(self, now_wall: float) -> List[dict]:
        self.boss.alive = False
        self.boss.hp = 0
        self.boss.respawn_at = now_wall + Boss.RESPAWN_SECONDS
        killer = self.players.get(self.last_hit_user or "")
        name = killer.nickname if killer else "cả đội mèo"
        return [{
            "type": "boss_down",
            "final_blow": {"user": self.last_hit_user, "name": name},
            "top3": self._top_damage(3),
            "round": self.boss.round,
            "speak": f"Hạ gục Chuột Trùm Răng Sắt! Đòn kết liễu thuộc về {name}!",
            "speak_priority": 1,
        }]

    # ------------------------------------------------------------------ utils
    def ensure_player(self, unique_id: str, nickname: str = "",
                      avatar_url: str = "") -> tuple[Player, bool]:
        """Tạo mèo cho người xem nếu chưa có. Trả (player, is_new)."""
        uid = (unique_id or nickname or "khach").strip()
        if uid in self.players:
            p = self.players[uid]
            if nickname:
                p.nickname = nickname
            if avatar_url:
                p.avatar_url = avatar_url
            self._assign_cat(p)
            return p, False
        p = Player(
            unique_id=uid,
            nickname=nickname or uid,
            avatar_url=avatar_url or "",
            seat=self._next_seat % self.MAX_SEATS,
            pace=self.rng.uniform(0.85, 1.15),
        )
        self._next_seat += 1
        self.players[uid] = p
        self._assign_cat(p)
        return p, True

    def leaderboard(self, top: int = 5) -> List[dict]:
        ranked = sorted(self.players.values(),
                          key=lambda p: (-p.points, p.joined_at))
        return [p.public() for p in ranked[:top]]

    def snapshot(self) -> dict:
        ranked = sorted(self.players.values(),
                          key=lambda p: (-p.points, p.joined_at))
        # Sân khấu chỉ cần tối đa MAX_SEATS mèo, ưu tiên người mới vào + điểm cao:
        # đơn giản & ổn định: giữ thứ tự ghế.
        seated = sorted(self.players.values(), key=lambda p: p.seat)
        for p in seated:
            self._assign_cat(p)   # mèo nạp từ điểm lưu cũng phải có tính cách
        now_mono = time.monotonic()
        now_wall_snap = time.time()
        snap = {
            "players": [p.public(now_mono) for p in seated[: self.MAX_SEATS]],
            "player_count": len(self.players),
            "leaderboard": self.leaderboard(5),
            "bug_satiety": round(self.bug_satiety),
            "bug_mood": self.bug_mood,
            "bug": {
                "satiety": round(self.bug_satiety),
                "mood": self.bug_mood,
                "sleeping": self._bug_sleeping(now_wall_snap),
                "annoyed": self._bug_annoyed(now_wall_snap),
                "annoyance": round(self.bug_annoyance),
            },
            "likes_since_rain": self.likes_since_rain,
            "like_goal": self.like_goal,
            "total_likes": self.total_likes,
            "team_km": round(sum(p.distance_m for p in self.players.values()) / 1000.0, 2),
            "team_size": sum(1 for p in self.players.values() if p.in_team),
            "follows_count": self.follows_count,
            "shares_count": self.shares_count,
            "race": self.race.public(self.players),
            "stage_mode": self.stage_mode,
        }
        if self.stage_mode == "boss":
            now_wall = time.time()
            now_mono = self._now_mono if self._now_mono else time.monotonic()
            self.claw_window = [(u, t) for (u, t) in self.claw_window
                                if now_mono - t <= self.SYNC_WINDOW]
            skin = self.current_boss_skin()
            snap["boss"] = {
                "name": Boss.NAME,
                "skin": skin,
                "skin_name": SKINS[skin],
                "hp": self.boss.hp,
                "max_hp": self.boss.max_hp,
                "round": self.boss.round,
                "alive": self.boss.alive,
                "rage": self.boss_rage,
                "rage_max": self.RAGE_MAX,
                "stun_left": round(max(0.0, self.boss.stun_until - now_wall)) if self.boss.alive else 0,
                "respawn_in": round(max(0.0, self.boss.respawn_at - now_wall)) if not self.boss.alive else 0,
                "total_damage": self.boss_total_damage,
                "top_damage": self._top_damage(5),
                # --- v2: máu ×N thanh + % đã hạ + biến hình + đồng loạt ---
                "bars_left": boss_bars_left(self.boss.hp),
                "bars_total": boss_bars_total(self.boss.max_hp),
                "percent_destroyed": round(
                    (1 - self.boss.hp / max(1, self.boss.max_hp)) * 100, 4),
                "form_stage": self._boss_form_stage(),
                "sync_left": round(max(0.0, self.sync_until - now_mono)) if self.boss.alive else 0,
                "sync_count": len({u for u, _t in self.claw_window}),
            }
        if self.stage_mode == "garden":
            now_g = time.time()
            top_hearts = sorted(self.players.values(),
                                key=lambda p: (-p.hearts, p.joined_at))[:5]
            snap["garden"] = {
                "hearts": self.garden_hearts,
                "hearts_goal": self.garden_hearts_goal,
                "feast_active": now_g < self.garden_feast_until,
                "golden_hour_active": now_g < self.garden_golden_hour_until,
                "decor_active": now_g < self.garden_decor_until,
                "golden_present": any(p.golden for p in self.players.values()),
            }
            snap["garden_top"] = [{
                "name": p.nickname,
                "hearts": p.hearts,
                "personality_name": personality_info(p.personality)["name"],
            } for p in top_hearts]
        if self.stage_mode == "miner":
            self._miner_ensure()
            now_m = time.time()
            hooks_snap = {}
            for team, hook in self.miner_hooks.items():
                hooks_snap[team] = {
                    "angle": round(hook["angle"], 1),
                    "len": round(hook["len"], 3),
                    "state": hook["state"],
                    "carrying_kind": hook["carrying_kind"],
                }
            buffs_snap = {}
            for team in MINER_PIVOTS:
                buff = self.miner_buffs.get(team) or {}
                until = float(buff.get("until", 0.0))
                buffs_snap[team] = {
                    "mult": float(buff.get("mult", 1.0)) if now_m < until else 1.0,
                    "until": until,
                }
            snap["miner"] = {
                "round": self.miner_round,
                "phase": self.miner_phase,
                "time_left": max(0, round(self.miner_deadline - now_m)),
                "wins": dict(self.miner_wins),
                "scores": dict(self.miner_score),
                "members": {"meo": self._miner_team_size("meo"),
                            "chuot": self._miner_team_size("chuot")},
                "hooks": hooks_snap,
                "items": [{"id": it["id"], "x": it["x"], "y": it["y"],
                           "kind": it["kind"], "r": it["r"]}
                          for it in self.miner_items],
                "blast_progress": {"likes": self.likes_since_rain,
                                   "goal": self.like_goal},
                "buffs": buffs_snap,
            }
            top_gold = sorted(self.players.values(),
                              key=lambda p: (-p.gold_total, p.joined_at))[:5]
            snap["miner_top"] = [{"name": p.nickname, "gold": p.gold_total,
                                  "team": p.team} for p in top_gold]
        if self.stage_mode == "tug":
            self._tug_ensure()
            now_t = time.time()
            buffs_snap = {}
            for team in TUG_TEAM_NAMES:
                buff = self.tug_buffs.get(team) or {}
                until = float(buff.get("until", 0.0))
                buffs_snap[team] = {
                    "mult": float(buff.get("mult", 1.0)) if now_t < until else 1.0,
                    "until": until,
                }
            snap["tug"] = {
                "round": self.tug_round,
                "phase": self.tug_phase,
                "time_left": max(0, round(self.tug_deadline - now_t)),
                "pos": round(self.tug_pos, 1),
                "wins": dict(self.tug_wins),
                "members": {"cam": self._tug_team_size("cam"),
                            "xam": self._tug_team_size("xam")},
                "morale": {t: round(self.tug_morale[t]) for t in TUG_TEAM_NAMES},
                "buffs": buffs_snap,
                "drums_until": self.tug_drums_until,
            }
            top_force = sorted(self.players.values(),
                               key=lambda p: (-p.tug_force, p.joined_at))[:5]
            snap["tug_top"] = [{"name": p.nickname,
                                "force": round(p.tug_force, 1),
                                "pulls": p.tug_pulls,
                                "team": p.tug_team} for p in top_force]
        if self.stage_mode == "office":
            self._office_ensure()
            now_o = time.time()
            if self.ob_state == "distracted":
                kind_o = self.ob_kind
            elif self.ob_state in ("party", "coffee", "cake"):
                kind_o = self.ob_state
            else:
                kind_o = ""
            snap["office"] = {
                "shift": self.office_shift,
                "phase": self.office_phase,
                "time_left": max(0, round(self.office_deadline - now_o)),
                "fund": self.office_fund,
                "fund_goal": OFFICE_FUND_GOAL,
                "coffee": {"likes": self.office_coffee_likes,
                           "goal": OFFICE_COFFEE_GOAL},
                "party_active": now_o < self.office_party_until,
                "bug_desk": self.office_bug_desk,
            }
            snap["office_boss"] = {
                "state": self.ob_state,
                "kind": kind_o,
                "x": round(self.ob_x, 3),
                "facing": "right" if self.ob_dir > 0 else "left",
                "state_left": max(0, round(self.ob_deadline - now_o)),
                "safe": self._office_is_safe(now_o),
            }
            top_office = sorted(self.players.values(),
                                key=lambda p: (-p.office_pts_total,
                                               p.joined_at))[:5]
            snap["office_top"] = [{"name": p.nickname,
                                   "pts": p.office_pts_total}
                                  for p in top_office]
        return snap

    # ------------------------------------------------------------- sự kiện
    def handle_join(self, unique_id: str, nickname: str = "",
                    avatar_url: str = "") -> List[dict]:
        p, is_new = self.ensure_player(unique_id, nickname, avatar_url)
        if not is_new:
            return []
        p.points += 2
        effects = [{
            "type": "spawn", "player": p.public(),
            "speak": f"Chào {p.nickname} vừa vào nhà của Bug!",
            "speak_priority": 3,
        }]
        effects += self._golden_fx(p)
        return effects

    def handle_comment(self, unique_id: str, nickname: str, comment: str,
                       avatar_url: str = "", now: Optional[float] = None) -> List[dict]:
        now = time.monotonic() if now is None else now
        self._now_mono = now
        effects: List[dict] = []
        p, is_new = self.ensure_player(unique_id, nickname, avatar_url)
        if is_new:
            p.points += 2
            effects.append({
                "type": "spawn", "player": p.public(),
                "speak": f"Chào {p.nickname} vừa vào nhà của Bug!",
                "speak_priority": 3,
            })
            effects += self._golden_fx(p)

        text = normalize(comment)
        tokens = set(text.split())

        # --- Văn Phòng Lén Lút: hành động lén của nhân viên mèo ---
        # Phải chặn ĐẦU TIÊN: "an" trùng lệnh cho Bug ăn, "ngu"/"buon ngu"
        # trùng lệnh NGỦ của Bug — ở văn phòng chúng là việc riêng của nhân viên.
        if self.stage_mode == "office":
            office_action = OFFICE_TEXT_TO_ACTION.get(text)
            if office_action is not None:
                effects += self._office_try_action(p, office_action, now)
                return effects

        # --- Đào Vàng PK: vào đội (MÈO / CHUỘT) + thả móc (ĐÀO) ---
        # Phải chặn TRƯỚC handler MEOW ở dưới vì "meo" là lệnh vào Đội Mèo ở mỏ.
        if self.stage_mode == "miner":
            if text in ("meo", "doi meo"):
                effects += self._miner_join_team(p, "meo", now)
                return effects
            if text in ("chuot", "doi chuot"):
                effects += self._miner_join_team(p, "chuot", now)
                return effects
            if text == "dao":
                effects += self._miner_try_dao(p, now)
                return effects

        # --- Kéo Co: vào đội (CAM / XÁM) + kéo dây (KÉO) + hò (HÒ / HÒ DÔ) ---
        if self.stage_mode == "tug":
            if text in ("cam", "doi cam"):
                effects += self._tug_join_team(p, "cam", now)
                return effects
            if text in ("xam", "doi xam"):
                effects += self._tug_join_team(p, "xam", now)
                return effects
            if text == "keo":
                effects += self._tug_try_pull(p, now)
                return effects
            if text in ("ho", "ho do"):
                effects += self._tug_try_cheer(p, now)
                return effects

        # --- Vườn Mèo: cả vườn phản ứng THEO TÍNH CÁCH với bình luận ---
        # (chỉ ở chế độ garden; các lệnh gốc cho Bug ở dưới vẫn chạy như cũ)
        if self.stage_mode == "garden":
            if tokens & {"hat", "pate"} or text in ("an", "cho an", "an di", "bug an", "cho bug an"):
                effects += self._garden_react_feed(p)
            if text in SLEEP_TEXTS:
                self._garden_react_sleep()
            if text in ("choi", "choi di", "di choi"):
                effects += self._garden_react_play(p)
            if text in ("ca", "an ca"):
                effects += self._garden_react_fish(p)
            if any(w in text for w in PRAISE_WORDS):
                effects += self._garden_react_praise(p, now)

        # --- Lệnh ĐUA: đăng ký vào sảnh đua ---
        if text == "dua" or text.startswith("dua ") or "tham gia dua" in text:
            effects += self._join_race(p, now)
            return effects

        # --- Lệnh CHẠY: tăng tốc khi đang đua ---
        if self.race.state == Race.RUNNING and p.unique_id in self.race.positions:
            if text in ("chay", "go", "chay di", "len", "bug oi chay"):
                if now - p.last_boost_at >= self.BOOST_COOLDOWN:
                    p.last_boost_at = now
                    self.race.positions[p.unique_id] = min(
                        self.RACE_FINISH,
                        self.race.positions[p.unique_id] + self.rng.uniform(1.5, 3.5),
                    )
                    effects.append({"type": "boost", "player": p.public(),
                                    "race": self.race.public(self.players)})
                return effects

        # --- Lệnh CÀO: tấn công boss (chỉ ở chế độ Đánh Boss) ---
        if self.stage_mode == "boss" and text == "cao":
            if not self.boss.alive:
                return effects
            if now - p.last_claw_at < self.CLAW_COOLDOWN:
                return effects
            p.last_claw_at = now
            now_wall = time.time()
            stunned = now_wall < self.boss.stun_until
            # ĐỒNG LOẠT: ghi nhận cú cào vào cửa sổ trượt 3s; >= 5 người KHÁC NHAU
            # cùng cào -> kích hoạt 3s cào đau x2 cho cả đội (nguội 10s mới kích lại).
            self.claw_window = [(u, t) for (u, t) in self.claw_window
                                if now - t <= self.SYNC_WINDOW]
            self.claw_window.append((p.unique_id, now))
            sync_count = len({u for u, _t in self.claw_window})
            sync_on = now < self.sync_until
            sync_fired = 0
            if (not sync_on and sync_count >= self.SYNC_MIN_USERS
                    and (self._last_sync_at is None
                         or now - self._last_sync_at >= self.SYNC_COOLDOWN)):
                self.sync_until = now + self.SYNC_DURATION
                self._last_sync_at = now
                sync_on = True
                sync_fired = sync_count
            dmg = self.rng.randint(1, 3) * (2 if stunned else 1) * (2 if sync_on else 1)
            die = self._boss_apply_damage(dmg, uid=p.unique_id, now_wall=now_wall)
            effects.append({
                "type": "boss_attack", "player": p.public(now),
                "user": p.unique_id, "name": p.nickname, "avatar": p.avatar_url,
                "kind": "cao", "damage": dmg,
                "hp": self.boss.hp, "max_hp": self.boss.max_hp,
                "stunned": stunned, "sync": sync_on,
            })
            if sync_fired:
                effects.append({"type": "boss_sync", "count": sync_fired})
            effects += die
            return effects

        # --- Lệnh CHẠY VÔ TẬN (theme v3 — kiểu "Chạy cùng Kitzy") ---
        if text in ("chay nhanh", "nhanh", "tang toc"):
            if now - p.last_cmd_boost_at >= 8:
                p.last_cmd_boost_at = now
                p.speed_mode = "boost"
                p.speed_until = now + 20
                if not p.in_team:
                    p.in_team = True
                p.points += 2
                effects.append({"type": "run_boost", "player": p.public(now),
                                "message": f"🏃 {p.nickname} tăng tốc!"})
            return effects
        if text == "nghi":
            p.speed_mode = "slow"
            p.speed_until = now + 15
            effects.append({"type": "run_slow", "player": p.public(now),
                            "message": f"🐌 {p.nickname} nghỉ một chút, chạy chậm lại"})
            return effects
        if text == "nhay":
            effects.append({"type": "jump", "player": p.public(now)})
            return effects
        if text == "hang":
            ranking = sorted(self.players.values(), key=lambda x: -x.distance_m)
            rank = next((i + 1 for i, x in enumerate(ranking)
                         if x.unique_id == p.unique_id), len(ranking))
            effects.append({
                "type": "rank", "player": p.public(now), "rank": rank,
                "speak": f"{p.nickname} đang hạng {rank} toàn đội với {p.distance_m / 1000:.2f} ki lô mét!",
                "speak_priority": 4,
            })
            return effects
        if text == "chay":
            if not p.in_team:
                p.in_team = True
                p.points += 2
                effects.append({"type": "run_join", "player": p.public(now),
                                "message": f"🐱 {p.nickname} vào đội chạy cùng Bug!"})
            else:
                p.distance_m += 5
                effects.append({"type": "run_surge", "player": p.public(now)})
            return effects

        # --- Lệnh NGỦ: gõ NGỦ / ĐI NGỦ / NGỦ ĐI / BUỒN NGỦ -> Bug ngủ 25s ---
        if text in SLEEP_TEXTS:
            now_wall = time.time()
            if self._bug_sleeping(now_wall):
                # Đang ngủ mà còn gọi ngủ tiếp = phá giấc ngủ
                effects += self._bug_disturb(now_wall)
                return effects
            if self._bug_annoyed(now_wall):
                effects.append({
                    "type": "bug_refuse", "reason": "sleep", "player": p.public(),
                    "speak": "Bug đang khó chịu, chưa muốn ngủ đâu!",
                    "speak_priority": 4,
                })
                return effects
            self.bug_sleep_until = now_wall + 25
            self.bug_sleep_disturbances = 0
            effects.append({
                "type": "bug_sleep", "player": p.public(),
                "speak": "Bug đi ngủ đây, cả nhà nói khẽ thôi nha~",
                "speak_priority": 5,
            })
            return effects

        # --- Lệnh CHO ĂN: gõ HẠT / PATE / CHO ĂN ---
        # Lưu ý: không dùng token "ca" vì "cả nhà ơi" cũng normalize thành "ca nha oi".
        if tokens & {"hat", "pate"} or text in ("an", "cho an", "an di", "bug an", "cho bug an"):
            now_wall = time.time()
            if self._bug_sleeping(now_wall):
                # Cho ăn lúc Bug đang ngủ = phá giấc, không tính là cho ăn
                effects += self._bug_disturb(now_wall)
                return effects
            if self._bug_annoyed(now_wall):
                # Đang khó chịu: Bug từ chối ăn (dùng cooldown cho ăn để chống spam thoại)
                if now - p.last_feed_at >= self.FEED_COOLDOWN:
                    p.last_feed_at = now
                    line = REFUSE_FEED_LINES[self._refuse_idx % len(REFUSE_FEED_LINES)]
                    self._refuse_idx += 1
                    effects.append({
                        "type": "bug_refuse", "reason": "feed", "player": p.public(),
                        "speak": line, "speak_priority": 4,
                    })
                return effects
            if now - p.last_feed_at < self.FEED_COOLDOWN:
                effects.append({"type": "feed_blocked", "player": p.public(),
                                  "message": f"{p.nickname} chờ {int(self.FEED_COOLDOWN - (now - p.last_feed_at))}s nữa mới cho ăn tiếp được nha"})
                return effects
            p.last_feed_at = now
            p.feeds += 1
            p.points += 5
            overfed = self.bug_satiety >= 90
            self.bug_satiety = min(100, self.bug_satiety + 2)
            if overfed:
                # Đã no >= 90 mà còn cho ăn: Bug khó chịu, kêu no thay vì cảm ơn
                self.bug_annoyance = min(100.0, self.bug_annoyance + 30)
                line = OVERFEED_LINES[self._overfeed_idx % len(OVERFEED_LINES)]
                self._overfeed_idx += 1
                effects.append({"type": "feed", "player": p.public(),
                                "bug_satiety": round(self.bug_satiety)})
                effects.append({
                    "type": "bug_overfed", "player": p.public(),
                    "annoyance": round(self.bug_annoyance),
                    "speak": line, "speak_priority": 3,
                })
            else:
                self.bug_annoyance = max(0.0, self.bug_annoyance - 10)
                self.bug_mood = "happy"
                effects.append({
                    "type": "feed", "player": p.public(),
                    "bug_satiety": round(self.bug_satiety),
                    "speak": f"Cảm ơn {p.nickname} đã cho Bug ăn!",
                    "speak_priority": 4,
                })
            self._save_scores()
            return effects

        # --- Lệnh MEOW / nhận mèo ---
        if text in ("meow", "bug", "tham gia", "meo", "hello bug", "hi bug"):
            effects.append({"type": "pet", "player": p.public(),
                            "bubble": "Meow! 🐾"})
            return effects

        # --- Comment thường: hiện bong bóng chat + điểm thân thiết (có cooldown) ---
        if now - p.last_chat_point_at >= self.CHAT_POINT_COOLDOWN:
            p.last_chat_point_at = now
            p.points += 1
        effects.append({
            "type": "chat", "player": p.public(),
            "bubble": (comment or "")[:60],
        })
        # Nhận diện lời chúc / điều cầu như bản "đi chùa online": thi cử, sức khỏe...
        wish = detect_wish(text)
        if wish:
            effects.append({
                "type": "wish", "player": p.public(),
                "speak": f"Bug chúc {p.nickname} {wish}!",
                "speak_priority": 4,
            })
        return effects

    def handle_like(self, count: int = 1) -> List[dict]:
        count = max(0, int(count))
        self.total_likes += count
        if self.stage_mode == "miner":
            # Đào Vàng PK: tim nạp thanh thuốc nổ; đầy like_goal -> NỔ MÌN:
            # đá trên trường mỏ bay hết, 5 cục vàng mới lộ ra, chu trình tim reset.
            self._miner_ensure()
            self.likes_since_rain += count
            effects: List[dict] = [{"type": "likes",
                                    "likes_since_rain": self.likes_since_rain,
                                    "like_goal": self.like_goal,
                                    "total_likes": self.total_likes}]
            if self.likes_since_rain >= self.like_goal:
                self.likes_since_rain = 0
                now_wall = time.time()
                rocks = [it for it in self.miner_items if it["kind"] == "rock"]
                self.miner_items = [it for it in self.miner_items
                                    if it["kind"] != "rock"]
                for _ in rocks:
                    self.miner_respawn_due.append(now_wall + self.rng.uniform(4, 8))
                for kind in ("gold_l", "gold_m", "gold_m", "gold_l", "gold_m"):
                    self._miner_spawn_item(kind)
                effects.append({
                    "type": "miner_blast",
                    "speak": "💥 NỔ MÌN! Đá bay hết, vàng lộ ra rồi — ĐÀO mau cả nhà ơi!",
                    "speak_priority": 1,
                })
            return effects
        if self.stage_mode == "tug":
            # Kéo Co: tim nạp trống hội; đầy like_goal -> TRỐNG HỘI NỔI LÊN:
            # cả 2 đội kéo mạnh x1.5 trong 15s, chu trình tim reset như các chế độ.
            self._tug_ensure()
            self.likes_since_rain += count
            effects: List[dict] = [{"type": "likes",
                                    "likes_since_rain": self.likes_since_rain,
                                    "like_goal": self.like_goal,
                                    "total_likes": self.total_likes}]
            if self.likes_since_rain >= self.like_goal:
                self.likes_since_rain = 0
                self.tug_drums_until = time.time() + TUG_DRUMS_SECONDS
                effects.append({
                    "type": "tug_drums",
                    "until": self.tug_drums_until,
                    "speak": "🥁 TRỐNG HỘI NỔI LÊN! Cả hai đội kéo mạnh hẳn — HÒ DÔ TA!",
                    "speak_priority": 1,
                })
            return effects
        if self.stage_mode == "office":
            # Văn Phòng Lén Lút: tim = cả phòng RÓT CÀ PHÊ cho sếp (bộ đếm
            # riêng, tách khỏi chu trình tim chung); đủ 200 tim sếp buộc phải
            # đi nghỉ pha cà phê 15s — cửa sổ an toàn cho cả phòng lén lút.
            self._office_ensure()
            self.office_coffee_likes += count
            effects: List[dict] = [{"type": "likes",
                                    "likes_since_rain": self.likes_since_rain,
                                    "like_goal": self.like_goal,
                                    "total_likes": self.total_likes}]
            if self.office_coffee_likes >= OFFICE_COFFEE_GOAL:
                self.office_coffee_likes = 0
                now_wall = time.time()
                if now_wall >= self.office_party_until:
                    self.ob_state = "coffee"
                    self.ob_kind = ""
                    self.ob_deadline = now_wall + 15
                effects.append({
                    "type": "office_coffee",
                    "speak": "☕ Cả phòng rót cà phê — sếp đi nghỉ pha cà phê 15 giây, tranh thủ lén thôi!",
                    "speak_priority": 1,
                })
            return effects
        if self.stage_mode == "boss":
            # Chế độ Đánh Boss: tim nạp thanh Nộ thay cho đếm mưa cá.
            # Đầy Nộ -> mưa cá trút xuống boss, sát thương cả đội (không tính riêng ai).
            self.boss_rage = min(self.RAGE_MAX, self.boss_rage + count)
            effects: List[dict] = [{"type": "likes",
                                    "likes_since_rain": self.likes_since_rain,
                                    "like_goal": self.like_goal,
                                    "total_likes": self.total_likes,
                                    "rage": self.boss_rage,
                                    "rage_max": self.RAGE_MAX}]
            if self.boss_rage >= self.RAGE_MAX and self.boss.alive:
                self.boss_rage = 0
                dmg = max(1, round(self.boss.max_hp * 0.15))
                die = self._boss_apply_damage(dmg)
                effects.append({"type": "boss_attack", "kind": "mua_ca",
                                "damage": dmg, "hp": self.boss.hp,
                                "max_hp": self.boss.max_hp})
                effects.append({
                    "type": "rain", "kind": "fish", "seconds": 8,
                    "speak": "Đầy nộ rồi! Cơn mưa cá trút xuống Chuột Trùm Răng Sắt!",
                    "speak_priority": 1,
                })
                effects += die
                if self.boss_taunts and self.boss.alive:
                    effects.append(self._boss_taunt_effect(BOSS_TAUNT_BARRAGE))
            return effects
        if self.stage_mode == "garden":
            # Vườn Mèo: mỗi tim thả = +1 tim vườn; đủ mục tiêu tim của phiên
            # (like_goal) thì mở BỮA TIỆC VƯỜN thay cho mưa cá.
            self.garden_hearts += count
            self.likes_since_rain += count
            effects: List[dict] = [{"type": "likes",
                                    "likes_since_rain": self.likes_since_rain,
                                    "like_goal": self.like_goal,
                                    "total_likes": self.total_likes}]
            now_wall = time.time()
            if self.likes_since_rain >= self.like_goal:
                self.likes_since_rain = 0
                self.garden_feast_until = now_wall + 20
                for cat in self.players.values():
                    self._garden_set_state(cat, "feast", 20, now_wall)
                effects.append({
                    "type": "garden_feast",
                    "speak": "Bữa Tiệc Vườn mở rồi! Cả đàn mèo vào bàn ăn thôi!",
                    "speak_priority": 1,
                })
            effects += self._garden_check_golden_hour(now_wall)
            return effects
        self.likes_since_rain += count
        effects: List[dict] = [{"type": "likes",
                                "likes_since_rain": self.likes_since_rain,
                                "like_goal": self.like_goal,
                                "total_likes": self.total_likes}]
        if self.likes_since_rain >= self.like_goal:
            self.likes_since_rain = 0
            effects.append({
                "type": "rain", "kind": "fish", "seconds": 30,
                "speak": "Đủ tim rồi! Mưa cá cho cả nhà Bug đây!",
                "speak_priority": 1,
            })
        return effects

    def handle_gift(self, unique_id: str, nickname: str, gift_name: str = "quà",
                    diamond_count: int = 1, avatar_url: str = "") -> List[dict]:
        """Có quà thì cảm ơn + zoom + mưa cá. Kênh KHÔNG kêu gọi tặng quà,
        đây chỉ là phản ứng cảm ơn khi sự kiện tự xảy ra."""
        p, _ = self.ensure_player(unique_id, nickname, avatar_url)
        p.points += max(1, min(int(diamond_count or 1), 100))
        self._save_scores()
        effects: List[dict] = [{
            "type": "gift", "player": p.public(), "gift_name": gift_name,
            "diamond_count": int(diamond_count or 1),
            "speak": f"Cảm ơn {p.nickname} đã tặng {gift_name} cho Bug! Chúc bạn một ngày thật vui!",
            "speak_priority": 0,
        }]
        # Quà đến lúc Bug đang ngủ cũng tính là phá giấc (vẫn cảm ơn như thường)
        now_wall_gift = time.time()
        if self._bug_sleeping(now_wall_gift):
            effects += self._bug_disturb(now_wall_gift)
        # Chế độ Đánh Boss: quà (khi tự đến) hóa thành đòn đánh lên boss.
        # Chỉ là phản ứng hiệu ứng — kênh vẫn KHÔNG kêu gọi tặng quà.
        if self.stage_mode == "boss" and self.boss.alive:
            d = int(diamond_count or 1)
            dmg = d * 2
            kind = "tatca" if d < 10 else ("va" if d < 100 else "doan")
            now_wall = time.time()
            if kind == "doan":
                self.boss.stun_until = now_wall + 3
            die = self._boss_apply_damage(dmg, uid=p.unique_id, now_wall=now_wall)
            atk: dict = {
                "type": "boss_attack", "player": p.public(),
                "user": p.unique_id, "name": p.nickname, "avatar": p.avatar_url,
                "kind": kind, "damage": dmg, "gift_name": gift_name,
                "diamond_count": d, "hp": self.boss.hp, "max_hp": self.boss.max_hp,
            }
            if kind == "doan":
                atk["speak"] = f"Đoàn mèo trợ trận của {p.nickname} xông lên rồi!"
                atk["speak_priority"] = 1
            effects.append(atk)
            effects += die
            if kind == "doan" and self.boss_taunts and self.boss.alive:
                effects.append(self._boss_taunt_effect(BOSS_TAUNT_SWARM))
        # Vườn Mèo: quà (khi tự đến) -> mèo của người tặng nhận bát đặc biệt +
        # vườn được trang trí một lúc. Chỉ là phản ứng cảm ơn, KHÔNG kêu gọi quà.
        if self.stage_mode == "garden":
            d = int(diamond_count or 1)
            now_wall = time.time()
            self._garden_set_state(p, "feast", 8, now_wall)
            p.happiness = 100.0
            p.treat_until = now_wall + 8
            decor_seconds = 120 if d >= 100 else 60
            self.garden_decor_until = max(self.garden_decor_until,
                                          now_wall + decor_seconds)
            if d >= 100:
                for cat in self.players.values():
                    self._garden_bump(cat, 10)
            effects.append({"type": "garden_treat", "player": p.public(),
                            "gift_name": gift_name, "diamond_count": d})
        # Đào Vàng PK: quà (khi tự đến) buff tốc độ kéo cho đội người tặng;
        # quà thật to (>=100 kim cương) -> MÓC VÀNG: móc tự chĩa thẳng cục giá trị
        # nhất trên mỏ và kéo x3. Chỉ là phản ứng cảm ơn, KHÔNG kêu gọi quà.
        if self.stage_mode == "miner":
            self._miner_ensure()
            d = int(diamond_count or 1)
            if p.team is None:
                p.team = self._miner_smaller_team()
            team = p.team
            now_wall = time.time()
            buffed = False
            if d >= 100:
                hook = self.miner_hooks[team]
                targets = [it for it in self.miner_items
                           if it["kind"] in ("gold_s", "gold_m", "gold_l",
                                             "diamond", "bag")]
                if hook["state"] == "swing" and targets:
                    def _target_value(it):
                        return it["value"] if it["value"] is not None \
                            else MINER_BAG_TARGET_VALUE
                    target = max(targets, key=_target_value)
                    px, py = hook["pivot"]
                    angle = math.degrees(math.atan2(target["x"] - px,
                                                    target["y"] - py))
                    hook["angle"] = max(-MINER_SWING_DEG,
                                        min(MINER_SWING_DEG, angle))
                    hook["state"] = "drop"
                    hook["caller"] = p.unique_id
                    hook["golden"] = True
                    effects.append({"type": "miner_golden_grab", "team": team,
                                    "user": p.unique_id, "name": p.nickname,
                                    "kind": target["kind"]})
                    buffed = True
            if not buffed:
                mult, seconds = (1.6, 30) if d >= 10 else (1.3, 15)
                self.miner_buffs[team] = {"mult": mult,
                                          "until": now_wall + seconds}
                effects.append({"type": "miner_buff", "team": team,
                                "mult": mult, "until": now_wall + seconds,
                                "user": p.unique_id, "name": p.nickname})
        # Kéo Co: quà (khi tự đến) buff lực kéo cho đội người tặng; quà thật to
        # (>=100 kim cương) -> GIẬT SIÊU CẤP: dây nhảy thẳng 12 đơn vị về phía
        # đội mình (có thể đoạt cờ luôn). Chỉ là phản ứng cảm ơn, KHÔNG kêu gọi quà.
        if self.stage_mode == "tug":
            self._tug_ensure()
            d = int(diamond_count or 1)
            if p.tug_team is None:
                p.tug_team = self._tug_smaller_team()
            team = p.tug_team
            now_wall = time.time()
            if d >= 100:
                self.tug_pos = max(-100.0, min(
                    100.0, self.tug_pos + TUG_DIRS[team] * TUG_SUPER_YANK))
                effects.append({"type": "tug_super", "team": team,
                                "user": p.unique_id, "name": p.nickname,
                                "pos": round(self.tug_pos, 1)})
                if (self.tug_phase == "play"
                        and abs(self.tug_pos) >= TUG_WIN_POS):
                    effects += self._tug_end_round(now_wall)
            else:
                mult, seconds = (1.6, 30) if d >= 10 else (1.3, 15)
                buff = self._tug_set_buff(team, mult, seconds, now_wall)
                effects.append({"type": "tug_buff", "team": team,
                                "mult": buff["mult"], "until": buff["until"],
                                "user": p.unique_id, "name": p.nickname})
        # Văn Phòng Lén Lút: quà (khi tự đến) -> BÁNH làm sếp xao lãng 10s;
        # quà thật to (>=100 kim cương) -> TIỆC MINI 12s, cả phòng an toàn.
        # Chỉ là phản ứng cảm ơn, KHÔNG kêu gọi tặng quà.
        if self.stage_mode == "office":
            self._office_ensure()
            d = int(diamond_count or 1)
            now_wall = time.time()
            if d >= 100:
                self._office_start_party(now_wall, 12)
                effects.append({"type": "office_party", "source": "gift",
                                "user": p.unique_id, "name": p.nickname})
            else:
                if self._office_is_safe(now_wall):
                    # đang an toàn sẵn: kéo dài cửa sổ an toàn thêm cho đủ 10s
                    self.ob_deadline = max(self.ob_deadline, now_wall + 10)
                    if self.ob_state == "party":
                        self.office_party_until = max(
                            self.office_party_until, now_wall + 10)
                        self.ob_deadline = self.office_party_until
                else:
                    self.ob_state = "cake"
                    self.ob_kind = ""
                    self.ob_deadline = now_wall + 10
                effects.append({"type": "office_cake",
                                "user": p.unique_id, "name": p.nickname})
        return effects

    def handle_follow(self, unique_id: str, nickname: str,
                      avatar_url: str = "") -> List[dict]:
        p, _ = self.ensure_player(unique_id, nickname, avatar_url)
        p.points += 10
        self.follows_count += 1
        effects: List[dict] = [{"type": "follow", "player": p.public(),
                                "speak": f"Cảm ơn {p.nickname} đã follow nhà Bug!",
                                "speak_priority": 2}]
        effects += self._golden_fx(p)
        if self.stage_mode == "miner":
            # Đào Vàng PK: follow = +10 vàng cho đội (chưa có đội -> vào đội ít người)
            self._miner_ensure()
            if p.team is None:
                p.team = self._miner_smaller_team()
            p.gold_round += 10
            p.gold_total += 10
            self.miner_score[p.team] += 10
            self._miner_reach[p.unique_id] = time.time()
            effects.append({"type": "miner_follow_bonus", "user": p.unique_id,
                            "name": p.nickname, "team": p.team, "value": 10})
        if self.stage_mode == "garden":
            # Vườn Mèo: mèo của người follow chuyển vào vườn ở hẳn phiên này
            # (+25 tim vườn) — và KHÔNG có màn chó đuổi như chế độ chạy.
            self.garden_hearts += 25
            effects += self._garden_check_golden_hour(time.time())
        if self.stage_mode == "tug":
            # Kéo Co: follow -> vào đội ít người hơn (nếu chưa có đội) +
            # nạp thêm chút khí thế cho đội của mình.
            self._tug_ensure()
            if p.tug_team is None:
                p.tug_team = self._tug_smaller_team()
            self.tug_morale[p.tug_team] = min(
                100.0, self.tug_morale[p.tug_team] + 10)
            effects.append({"type": "tug_follow", "user": p.unique_id,
                            "name": p.nickname, "team": p.tug_team})
        if self.stage_mode == "office":
            # Văn Phòng Lén Lút: follow = nhân viên mới nhận bàn làm việc.
            self._office_ensure()
            effects.append({"type": "office_join", "user": p.unique_id,
                            "name": p.nickname, "desk": p.seat % OFFICE_DESKS})
        return effects

    def handle_share(self, unique_id: str, nickname: str,
                     avatar_url: str = "") -> List[dict]:
        p, _ = self.ensure_player(unique_id, nickname, avatar_url)
        p.points += 10
        self.shares_count += 1
        effects: List[dict] = [{"type": "share", "player": p.public()}]
        if self.stage_mode == "garden":
            # Vườn Mèo: chia sẻ live = +10 tim vườn, cả đàn mèo nhảy mừng
            self.garden_hearts += 10
            effects.append({"type": "garden_share", "player": p.public()})
            effects += self._garden_check_golden_hour(time.time())
        return effects

    def run_tick(self, dt: float, now_mono: Optional[float] = None) -> None:
        """Chạy vô tận: mèo trong đội tự chạy liên tục, tích lũy km.
        Bug đói (<25 độ no) thì cả đội chạy chậm còn 70% — cả phòng phải
        thay nhau gõ HẠT cho Bug ăn để giữ tốc độ."""
        now_mono = time.monotonic() if now_mono is None else now_mono
        stamina = 0.7 if self.bug_satiety < 25 else 1.0
        for p in self.players.values():
            if not p.in_team:
                continue
            mode = p.eff_speed_mode(now_mono)
            if mode != p.speed_mode and now_mono >= p.speed_until:
                p.speed_mode = "normal"
            mult = {"boost": 2.0, "slow": 0.4}.get(mode, 1.0)
            p.distance_m += 2.2 * p.pace * mult * stamina * dt

    # ------------------------------------------------------------- đua mèo
    def _join_race(self, p: Player, now: float) -> List[dict]:
        if self.race.state == Race.RUNNING:
            return [{"type": "race_info",
                     "message": "Đang đua rồi, chờ vòng sau nha! Gõ CHẠY để cổ vũ."}]
        if p.unique_id in self.race.racers:
            return [{"type": "race_info",
                     "message": f"{p.nickname} đã có mặt trong sảnh đua rồi"}]
        if len(self.race.racers) >= self.RACE_MAX_PLAYERS:
            return [{"type": "race_info", "message": "Sảnh đua đã đủ 8 mèo, chờ vòng sau nha"}]
        self.race.racers.append(p.unique_id)
        self.race.positions[p.unique_id] = 0.0
        p.points += 2
        effects = [{"type": "race_join", "player": p.public(),
                    "race": self.race.public(self.players)}]
        if self.race.state == Race.IDLE:
            self.race.state = Race.LOBBY
            self.race.deadline = time.time() + self.RACE_LOBBY_SECONDS
            effects.append({"type": "race_info",
                            "message": f"🏁 Sảnh đua mở! Gõ ĐUA để tham gia — còn {self.RACE_LOBBY_SECONDS}s",
                            "speak": "Mở sảnh đua mèo! Gõ chữ đua để tham gia nha cả nhà.",
                            "speak_priority": 1})
        return effects

    def force_start_race(self) -> List[dict]:
        if len(self.race.racers) >= 2 and self.race.state in (Race.LOBBY, Race.IDLE):
            self.race.state = Race.COUNTDOWN
            self.race.deadline = time.time() + self.RACE_COUNTDOWN_SECONDS
            return [{"type": "race", "race": self.race.public(self.players),
                     "speak": "Đua mèo sắp bắt đầu! Chuẩn bị gõ chữ chạy để tăng tốc cho mèo của mình!",
                     "speak_priority": 1}]
        return []

    def tick(self, now_wall: Optional[float] = None) -> List[dict]:
        """Gọi mỗi ~0.5s từ app.py: giảm độ no, chạy máy trạng thái đua."""
        now_wall = time.time() if now_wall is None else now_wall
        effects: List[dict] = []

        # --- Tâm trạng Bug: hạ nhiệt / ngủ đủ giấc tự dậy ---
        effects += self._mood_tick(now_wall)

        # --- Vườn Mèo: độ vui trôi về 55 + sinh tim vườn mỗi 5s ---
        if self.stage_mode == "garden":
            effects += self._garden_tick(now_wall)

        # --- Đào Vàng PK: nhịp hiệp + mô phỏng móc ---
        if self.stage_mode == "miner":
            effects += self._miner_tick(now_wall)

        # --- Kéo Co: nhịp hiệp + vật lý dây ---
        if self.stage_mode == "tug":
            effects += self._tug_tick(now_wall)

        # --- Văn Phòng Lén Lút: sếp tuần tra + ca làm việc ---
        if self.stage_mode == "office":
            effects += self._office_tick(now_wall)

        # --- Đánh Boss: xướng boss xuất hiện 1 lần + hồi sinh sau 15s ---
        if self.stage_mode == "boss":
            if not self._boss_spawn_spoken:
                self._boss_spawn_spoken = True
                effects.append({
                    "type": "boss_spawn",
                    "speak": "Chuột Trùm Răng Sắt mò tới trộm kho cá của Bug! Cả nhà gõ CÀO để tấn công nha!",
                    "speak_priority": 1,
                })
            if not self.boss.alive and now_wall >= self.boss.respawn_at:
                self.boss.round += 1
                self.boss.max_hp = round(self.boss.max_hp * 1.2)
                self.boss.hp = self.boss.max_hp
                self.boss.alive = True
                self.boss.respawn_at = 0.0
                self.boss.stun_until = 0.0
                self._boss_stage_now = 0      # vòng mới: biến hình + thoại mốc làm lại
                self._boss_taunted = set()
                skin = self.current_boss_skin()
                effects.append({
                    "type": "boss_respawn",
                    "round": self.boss.round, "max_hp": self.boss.max_hp,
                    "hp": self.boss.hp,
                    "skin": skin, "skin_name": SKINS[skin],
                    "speak": f"Vòng {self.boss.round} — Chuột Trùm Răng Sắt hiện hình {SKINS[skin]}! Máu trâu hơn rồi, cả nhà gõ CÀO tấn công tiếp nha!",
                    "speak_priority": 1,
                })
            if self.boss.alive:
                # Phản đòn quét đuôi: mỗi ~40s, chỉ khi có từ 3 mèo trong phòng.
                # Thuần hiệu ứng hình ảnh trên sân khấu, không trừ điểm ai.
                if self._last_counter_at is None:
                    self._last_counter_at = now_wall
                elif (now_wall - self._last_counter_at >= self.COUNTER_INTERVAL
                        and len(self.players) >= 3):
                    self._last_counter_at = now_wall
                    effects.append({"type": "boss_counter"})
                # Thoại rảnh: boss tự lẩm bẩm chửi (chỉ bong bóng, không đọc)
                if self.boss_taunts:
                    if self._next_idle_taunt_at is None:
                        self._next_idle_taunt_at = now_wall + self.rng.uniform(45, 70)
                    elif now_wall >= self._next_idle_taunt_at:
                        self._next_idle_taunt_at = now_wall + self.rng.uniform(45, 70)
                        effects.append(self._boss_taunt_effect(
                            self.rng.choice(BOSS_TAUNTS_IDLE), spoken=False))

        if self.race.state == Race.LOBBY:
            if len(self.race.racers) >= self.RACE_MIN_PLAYERS and now_wall >= self.race.deadline:
                effects += self.force_start_race()
            elif len(self.race.racers) >= self.RACE_MAX_PLAYERS:
                effects += self.force_start_race()
            elif now_wall >= self.race.deadline and len(self.race.racers) < self.RACE_MIN_PLAYERS:
                # Ít người quá thì gia hạn thêm 1 lần
                self.race.deadline = now_wall + self.RACE_LOBBY_SECONDS
                effects.append({"type": "race_info",
                                "message": "Sảnh đua cần tối thiểu 3 mèo — gõ ĐUA để vào thêm nha!"})

        elif self.race.state == Race.COUNTDOWN:
            if now_wall >= self.race.deadline:
                self.race.state = Race.RUNNING
                for uid in self.race.racers:
                    if uid in self.players:
                        self.players[uid].races += 1
                effects.append({"type": "race", "race": self.race.public(self.players),
                                "speak": "Xuất phát! Gõ chữ chạy thật nhanh nào!",
                                "speak_priority": 1})

        elif self.race.state == Race.RUNNING:
            finished = []
            for uid in self.race.racers:
                self.race.positions[uid] = min(
                    self.RACE_FINISH,
                    self.race.positions.get(uid, 0.0) + self.rng.uniform(0.4, 1.6),
                )
                if self.race.positions[uid] >= self.RACE_FINISH:
                    finished.append(uid)
            if finished:
                effects += self._finish_race(finished[0])
            else:
                effects.append({"type": "race", "race": self.race.public(self.players)})

        return effects

    def _finish_race(self, winner_uid: str) -> List[dict]:
        self.race.state = Race.FINISHED
        ranking = sorted(self.race.racers,
                         key=lambda uid: -self.race.positions.get(uid, 0.0))
        self.race.winners = ranking[:3]
        prizes = {0: 50, 1: 30, 2: 20}
        for idx, uid in enumerate(ranking):
            if uid in self.players:
                self.players[uid].points += prizes.get(idx, 10)
                if idx == 0:
                    self.players[uid].wins += 1
        winner = self.players.get(winner_uid)
        name = winner.nickname if winner else winner_uid
        effects = [{
            "type": "race_finish", "race": self.race.public(self.players),
            "winner": winner.public() if winner else {"nickname": name},
            "speak": f"Chúc mừng {name} thắng cuộc đua mèo! Cả nhà gõ đua để chơi vòng tiếp theo nha.",
            "speak_priority": 1,
        }]
        # Reset sảnh sau khi công bố
        self.race = Race()
        self._save_scores()
        return effects

    def decay_satiety(self, amount: float = 0.3) -> None:
        if self._bug_sleeping(time.time()):
            amount *= 0.5  # Đang ngủ thì Bug đói chậm lại một nửa
        self.bug_satiety = max(0.0, self.bug_satiety - amount)
        if self.bug_satiety < 25:
            self.bug_mood = "hungry"
        elif self.bug_satiety > 70:
            self.bug_mood = "happy"

    def reset_scores(self) -> None:
        for p in self.players.values():
            p.points = 0
            p.feeds = 0
            p.races = 0
            p.wins = 0
            p.distance_m = 0.0
            p.in_team = False
            p.hearts = 0
            p.happiness = 60.0
            p.team = None
            p.gold_round = 0
            p.gold_total = 0
        self.damage_by_user = {}
        self.boss_total_damage = 0
        self._rank_announced = {}
        self.garden_hearts = 0
        self.garden_hearts_goal = 1000
        self.miner_score = {"meo": 0, "chuot": 0}
        self.miner_wins = {"meo": 0, "chuot": 0}
        self.miner_round = 1
        self._miner_reach = {}
        self._save_scores()

    # ------------------------------------------------------------- lưu điểm
    def _save_scores(self) -> None:
        if not self.scores_path:
            return
        try:
            data = {uid: asdict(p) for uid, p in self.players.items()}
            tmp = self.scores_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, self.scores_path)
        except OSError:
            pass

    def _load_scores(self) -> None:
        if not self.scores_path or not os.path.exists(self.scores_path):
            return
        try:
            with open(self.scores_path, encoding="utf-8") as f:
                data = json.load(f)
            for uid, raw in data.items():
                keep = {k: raw[k] for k in
                        ("unique_id", "nickname", "avatar_url", "points",
                         "feeds", "races", "wins", "seat", "distance_m",
                         "in_team", "pace") if k in raw}
                p = Player(**keep)
                self.players[uid] = p
                self._next_seat = max(self._next_seat, p.seat + 1)
        except (OSError, ValueError, TypeError):
            pass


WISHES = [
    (("thi", "hoc", "diem cao", "do ", "tot nghiep"), "thi cử thật tốt, điểm cao"),
    (("suc khoe", "benh", "khoe"), "thật nhiều sức khỏe"),
    (("tinh duyen", "nguoi yeu", "crush", "yeu"), "tình duyên như ý, sớm có người thương"),
    (("gia dinh", "ba me", "cha me", "con cai"), "gia đình luôn bình an, hạnh phúc"),
    (("cong viec", "thang chuc", "luong", "kinh doanh", "ban hang"), "công việc thuận lợi, tài lộc đầy nhà"),
    (("binh an", "may man", "cau"), "luôn bình an và gặp nhiều may mắn"),
]


def detect_wish(normalized_text: str) -> Optional[str]:
    for keys, wish in WISHES:
        if any(k in normalized_text for k in keys):
            return wish
    return None
