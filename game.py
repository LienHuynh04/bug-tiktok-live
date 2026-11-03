"""
Game state cho live tương tác "Nhà của Bug".

File này KHÔNG phụ thuộc TikTokLive / aiohttp -> test được độc lập.
Mọi sự kiện TikTok (join / comment / like / gift / follow / share)
đều được app.py dịch thành lời gọi vào GameState, và GameState
trả về danh sách "effect dict" để app.py broadcast xuống stage.
"""
from __future__ import annotations

import json
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

    def eff_speed_mode(self, now_mono: float) -> str:
        if self.speed_mode != "normal" and now_mono >= self.speed_until:
            return "normal"
        return self.speed_mode

    def public(self, now_mono: Optional[float] = None) -> dict:
        now_mono = time.monotonic() if now_mono is None else now_mono
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
                "cướp kho cá — cả nhà gõ CÀO để đánh boss cùng Bug nha! Thả tim nạp Nộ, "
                "đủ 200 là mưa cá trút xuống đầu nó luôn!")
IDLE_RUN = ("Cả nhà ơi, gõ meow để nhận một bé mèo mang tên mình, gõ hạt để cho Bug ăn, "
            "gõ đua để đua mèo cùng nhau nha! Nhớ thả tim và chia sẻ live giúp Bug với.")
IDLE_BOSS = ("Cả nhà ơi, gõ CÀO để tấn công Chuột Trùm Răng Sắt cùng Bug nha! Thả tim "
             "nạp Nộ, đủ 200 là mưa cá trút xuống boss. Gõ HẠT cho Bug ăn lấy sức, "
             "gõ NGỦ cho Bug nghỉ một lát nha!")

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
        # --- chế độ Đánh Boss ---
        self.stage_mode = stage_mode if stage_mode in ("run", "boss") else "run"
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
        return OPENING_BOSS if self.stage_mode == "boss" else OPENING_RUN

    def idle_line(self) -> str:
        """Câu nhắc luật khi live im lặng lâu — theo chế độ sân khấu."""
        return IDLE_BOSS if self.stage_mode == "boss" else IDLE_RUN

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
        """Đổi chế độ sân khấu (run <-> boss) + áp máu boss / công tắc thoại từ config."""
        if mode not in ("run", "boss"):
            return
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
        return snap

    # ------------------------------------------------------------- sự kiện
    def handle_join(self, unique_id: str, nickname: str = "",
                    avatar_url: str = "") -> List[dict]:
        p, is_new = self.ensure_player(unique_id, nickname, avatar_url)
        if not is_new:
            return []
        p.points += 2
        return [{
            "type": "spawn", "player": p.public(),
            "speak": f"Chào {p.nickname} vừa vào nhà của Bug!",
            "speak_priority": 3,
        }]

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

        text = normalize(comment)
        tokens = set(text.split())

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
        return effects

    def handle_follow(self, unique_id: str, nickname: str,
                      avatar_url: str = "") -> List[dict]:
        p, _ = self.ensure_player(unique_id, nickname, avatar_url)
        p.points += 10
        self.follows_count += 1
        return [{"type": "follow", "player": p.public(),
                 "speak": f"Cảm ơn {p.nickname} đã follow nhà Bug!",
                 "speak_priority": 2}]

    def handle_share(self, unique_id: str, nickname: str,
                     avatar_url: str = "") -> List[dict]:
        p, _ = self.ensure_player(unique_id, nickname, avatar_url)
        p.points += 10
        self.shares_count += 1
        return [{"type": "share", "player": p.public()}]

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
        self.damage_by_user = {}
        self.boss_total_damage = 0
        self._rank_announced = {}
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
