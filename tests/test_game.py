"""Test logic game — chạy:  python tests/test_game.py"""
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from game import (GameState, Race, normalize,  # noqa: E402
                  OPENING_RUN, OPENING_BOSS, IDLE_RUN, IDLE_BOSS)


def run():
    g = GameState(like_goal=10, rng=random.Random(42))

    # normalize bỏ dấu đúng
    assert normalize("Cho Ăn Đua Chạy") == "cho an dua chay"

    # join -> spawn + 2 điểm
    eff = g.handle_join("u1", "Bạn A")
    assert eff and eff[0]["type"] == "spawn"
    assert g.players["u1"].points == 2

    # comment thường -> bubble; "cả nhà" KHÔNG được tính là cho ăn
    eff = g.handle_comment("u1", "Bạn A", "cả nhà ơi hello", now=100.0)
    assert any(e["type"] == "chat" for e in eff)

    # cho ăn bằng chữ "hạt" -> +5 điểm, Bug no hơn
    satiety_before = g.bug_satiety
    eff = g.handle_comment("u1", "Bạn A", "hạt", now=101.0)
    assert any(e["type"] == "feed" for e in eff)
    assert g.players["u1"].points >= 7
    assert g.bug_satiety > satiety_before

    # cho ăn liên tục -> bị cooldown chặn
    eff = g.handle_comment("u1", "Bạn A", "hạt", now=102.0)
    assert any(e["type"] == "feed_blocked" for e in eff)

    # cầu nguyện / lời chúc được nhận diện
    eff = g.handle_comment("u2", "Bạn B", "mai thi rồi, cầu điểm cao", now=103.0)
    assert any(e["type"] == "wish" for e in eff)

    # đủ tim -> mưa cá
    eff = g.handle_like(10)
    assert any(e["type"] == "rain" for e in eff)
    assert g.likes_since_rain == 0

    # đua: 3 người gõ ĐUA -> lobby -> hết giờ -> countdown -> running -> có người thắng
    g.handle_comment("u1", "Bạn A", "đua", now=110.0)
    g.handle_comment("u2", "Bạn B", "dua", now=110.0)
    g.handle_comment("u3", "Bạn C", "tham gia đua", now=110.0)
    assert g.race.state == Race.LOBBY and len(g.race.racers) == 3
    g.race.deadline = time.time() - 1
    g.tick()
    assert g.race.state == Race.COUNTDOWN
    g.race.deadline = time.time() - 1
    g.tick()
    assert g.race.state == Race.RUNNING

    finished = False
    for i in range(400):
        # người chơi spam CHẠY để tăng tốc
        g.handle_comment("u1", "Bạn A", "chạy", now=200.0 + i * 2)
        eff = g.tick()
        if any(e["type"] == "race_finish" for e in eff):
            finished = True
            break
    assert finished, "đua mãi không xong"
    assert g.players["u1"].races == 1
    assert sum(p.points for p in g.players.values()) > 0

    # quà -> có speak cảm ơn ưu tiên 0
    eff = g.handle_gift("u9", "Bạn Q", "Hoa hồng", 1)
    assert eff[0]["speak_priority"] == 0

    # --- chạy vô tận (theme v3) ---
    g2 = GameState(like_goal=10, rng=random.Random(7))
    g2.handle_join("r1", "Runner 1")
    assert not g2.players["r1"].in_team
    eff = g2.handle_comment("r1", "Runner 1", "chạy", now=100.0)
    assert any(e["type"] == "run_join" for e in eff)
    assert g2.players["r1"].in_team
    g2.run_tick(10.0, now_mono=101.0)
    d_normal = g2.players["r1"].distance_m
    assert d_normal > 15, d_normal  # ~2.2 m/s * pace * 10s

    # chạy nhanh -> quãng đường cùng thời gian phải dài hơn rõ rệt
    g2.handle_comment("r1", "Runner 1", "chạy nhanh", now=102.0)
    assert g2.players["r1"].speed_mode == "boost"
    before = g2.players["r1"].distance_m
    g2.run_tick(10.0, now_mono=103.0)
    assert g2.players["r1"].distance_m - before > d_normal * 1.5

    # nghỉ -> chậm lại
    g2.handle_comment("r1", "Runner 1", "nghỉ", now=120.0)
    before = g2.players["r1"].distance_m
    g2.run_tick(10.0, now_mono=121.0)
    assert g2.players["r1"].distance_m - before < d_normal

    # nhảy + hạng
    eff = g2.handle_comment("r1", "Runner 1", "nhảy", now=130.0)
    assert any(e["type"] == "jump" for e in eff)
    eff = g2.handle_comment("r1", "Runner 1", "hạng", now=131.0)
    assert any(e["type"] == "rank" and e["rank"] == 1 for e in eff)

    # Bug đói -> cả đội chạy chậm còn 70%
    g2.players["r1"].speed_mode = "normal"
    g2.bug_satiety = 10
    before = g2.players["r1"].distance_m
    g2.run_tick(10.0, now_mono=140.0)
    hungry_run = g2.players["r1"].distance_m - before
    assert hungry_run < d_normal, (hungry_run, d_normal)

    # snapshot có đủ số liệu cho sân khấu v3
    snap = g2.snapshot()
    assert snap["team_km"] > 0 and "follows_count" in snap and "team_size" in snap
    assert snap["players"][0]["distance_km"] > 0

    # ================= Đánh Boss Chuột Trùm Răng Sắt =================
    # --- CÀO: sát thương 1..3, cooldown 3s, chỉ ở chế độ boss ---
    gb = GameState(like_goal=10, rng=random.Random(3))
    gb.set_stage_mode("boss", 100)
    assert gb.snapshot()["stage_mode"] == "boss"
    b = gb.snapshot()["boss"]
    assert b["hp"] == 100 and b["max_hp"] == 100 and b["round"] == 1 and b["alive"]
    gb.handle_join("b1", "Thợ Săn Chuột")
    hp0 = gb.boss.hp
    eff = gb.handle_comment("b1", "Thợ Săn Chuột", "cào", now=100.0)
    atk = [e for e in eff if e["type"] == "boss_attack"]
    assert atk and atk[0]["kind"] == "cao" and 1 <= atk[0]["damage"] <= 3
    assert gb.boss.hp == hp0 - atk[0]["damage"]
    assert gb.damage_by_user["b1"] == atk[0]["damage"]
    # cào tiếp ngay lập tức -> cooldown chặn, máu không đổi
    hp1 = gb.boss.hp
    eff = gb.handle_comment("b1", "Thợ Săn Chuột", "cào", now=101.0)
    assert not any(e["type"] == "boss_attack" for e in eff)
    assert gb.boss.hp == hp1
    # sau 3s thì cào lại được (kể cả viết hoa có dấu)
    eff = gb.handle_comment("b1", "Thợ Săn Chuột", "CÀO", now=103.5)
    assert any(e["type"] == "boss_attack" for e in eff)
    # ở chế độ chạy, "cào" chỉ là chat thường — không có boss_attack
    gr = GameState(like_goal=10, rng=random.Random(3))
    eff = gr.handle_comment("x1", "Người Chạy", "cào", now=100.0)
    assert not any(e["type"] == "boss_attack" for e in eff)
    assert "boss" not in gr.snapshot()

    # --- Quà: biên mốc 9/10/100 kim cương + sát thương = kim cương x2 ---
    gg = GameState(like_goal=10, rng=random.Random(5))
    gg.set_stage_mode("boss", 1000)
    eff = gg.handle_gift("g1", "Quà Nhỏ", "Hoa hồng", 9)
    atk = [e for e in eff if e["type"] == "boss_attack"][0]
    assert atk["kind"] == "tatca" and atk["damage"] == 18
    eff = gg.handle_gift("g1", "Quà Nhỏ", "Xe đồ chơi", 10)
    atk = [e for e in eff if e["type"] == "boss_attack"][0]
    assert atk["kind"] == "va" and atk["damage"] == 20
    assert gg.damage_by_user["g1"] == 38
    eff = gg.handle_gift("g2", "Đại Gia", "Sư tử", 100)
    atk = [e for e in eff if e["type"] == "boss_attack"][0]
    assert atk["kind"] == "doan" and atk["damage"] == 200
    assert gg.boss.stun_until > time.time()  # quà to làm boss choáng 3s
    # đang choáng thì CÀO đau gấp đôi: sát thương phải là số chẵn 2/4/6
    eff = gg.handle_comment("g3", "Mèo Nhanh", "cào", now=200.0)
    atk = [e for e in eff if e["type"] == "boss_attack"][0]
    assert atk["damage"] in (2, 4, 6), atk["damage"]

    # --- Thanh Nộ: đủ 200 tim -> mưa cá = 15% máu tối đa, nộ về 0 ---
    gn = GameState(like_goal=10, rng=random.Random(9))
    gn.set_stage_mode("boss", 1000)
    eff = gn.handle_like(199)
    assert not any(e["type"] == "rain" for e in eff) and gn.boss_rage == 199
    eff = gn.handle_like(1)
    assert any(e["type"] == "rain" for e in eff)
    atk = [e for e in eff if e["type"] == "boss_attack"][0]
    assert atk["kind"] == "mua_ca" and atk["damage"] == 150
    assert gn.boss.hp == 850 and gn.boss_rage == 0
    assert gn.damage_by_user == {}  # sát thương cả đội, không tính riêng ai

    # --- Đòn kết liễu: boss_down có final_blow + top3 đúng thứ tự ---
    gd = GameState(like_goal=10, rng=random.Random(11))
    gd.set_stage_mode("boss", 100)
    gd.handle_gift("d1", "Mèo A", "Xe đồ chơi", 30)   # 60 dmg
    eff = gd.handle_gift("d2", "Mèo B", "Xe đồ chơi", 25)  # 50 dmg -> kết liễu
    down = [e for e in eff if e["type"] == "boss_down"]
    assert down, "boss phải gục"
    down = down[0]
    assert down["final_blow"]["user"] == "d2" and down["final_blow"]["name"] == "Mèo B"
    assert [t["name"] for t in down["top3"]] == ["Mèo A", "Mèo B"]
    assert down["top3"][0]["damage"] == 60 and down["top3"][1]["damage"] == 50
    assert not gd.boss.alive and gd.boss.hp == 0
    snap = gd.snapshot()
    assert snap["boss"]["top_damage"][0]["name"] == "Mèo A"
    assert snap["boss"]["respawn_in"] > 0

    # --- Hồi sinh: vòng +1, máu x1.2 (tick xử lý khi tới giờ) ---
    gd.boss.respawn_at = time.time() - 1
    eff = gd.tick()
    resp = [e for e in eff if e["type"] == "boss_respawn"]
    assert resp and resp[0]["round"] == 2 and resp[0]["max_hp"] == 120
    assert gd.boss.alive and gd.boss.hp == 120 and gd.boss.round == 2

    # ================= Boss v2: thanh máu ×N + % đã hạ =================
    gm = GameState(like_goal=10, rng=random.Random(21))
    gm.set_stage_mode("boss", 1000)
    snap = gm.snapshot()["boss"]
    assert snap["name"] == "CHUỘT TRÙM RĂNG SẮT"
    assert snap["bars_total"] == 4 and snap["bars_left"] == 4
    assert snap["percent_destroyed"] == 0.0 and snap["form_stage"] == 0
    gm.handle_gift("m1", "Mèo Mạnh", "Sư tử", 250)   # 500 dmg (quà đoàn trợ trận)
    snap = gm.snapshot()["boss"]
    assert snap["hp"] == 500 and snap["bars_left"] == 2
    assert snap["percent_destroyed"] == 50.0

    # ================= Boss v2: ĐỒNG LOẠT =================
    gs = GameState(like_goal=10, rng=random.Random(31))
    gs.set_stage_mode("boss", 100000)
    for i in range(1, 6):
        gs.handle_join(f"s{i}", f"Mèo Sync {i}")
    # 4 người khác nhau cào -> chưa kích hoạt
    for i in range(1, 5):
        eff = gs.handle_comment(f"s{i}", f"Mèo Sync {i}", "cào", now=100.0 + i * 0.5)
        assert not any(e["type"] == "boss_sync" for e in eff), i
    # người thứ 5 trong cửa sổ 3s -> kích hoạt ĐỒN ĐỒNG LOẠT, count = 5
    eff = gs.handle_comment("s5", "Mèo Sync 5", "cào", now=102.5)
    syncs = [e for e in eff if e["type"] == "boss_sync"]
    assert syncs and syncs[0]["count"] == 5
    # snapshot thấy đồng loạt đang bật + đủ 5 người trong cửa sổ
    snap = gs.snapshot()["boss"]
    assert snap["sync_count"] == 5 and snap["sync_left"] > 0
    # cú cào tiếp theo trong lúc đồng loạt: đau gấp đôi (2/4/6, boss không choáng)
    gs.handle_join("s6", "Mèo Sync 6")
    eff = gs.handle_comment("s6", "Mèo Sync 6", "cào", now=102.8)
    atk = [e for e in eff if e["type"] == "boss_attack"][0]
    assert atk["damage"] in (2, 4, 6) and atk["sync"] is True, atk
    # 5 người MỚI cùng cào ngay sau đó -> còn nguội 10s, không kích hoạt lại
    for i in range(7, 12):
        gs.handle_join(f"s{i}", f"Mèo Sync {i}")
        eff = gs.handle_comment(f"s{i}", f"Mèo Sync {i}", "cào", now=103.0 + (i - 7) * 0.4)
        assert not any(e["type"] == "boss_sync" for e in eff), i

    # ================= Boss v2: HẠNG MÈO =================
    gk = GameState(like_goal=10, rng=random.Random(37))
    gk.set_stage_mode("boss", 100000)
    eff = gk.handle_gift("k1", "Mèo Leo Hạng", "Xe đồ chơi", 25)  # 50 dmg -> Mèo Săn
    ups = [e for e in eff if e["type"] == "rank_up"]
    assert ups and ups[0]["rank_title"] == "Mèo Săn" and ups[0]["user"] == "k1"
    assert ups[0]["speak_priority"] == 2
    # gây thêm sát thương mà chưa qua mốc mới -> không xướng lại
    eff = gk.handle_gift("k1", "Mèo Leo Hạng", "Hoa hồng", 1)    # +2 dmg
    assert not any(e["type"] == "rank_up" for e in eff)
    snap = gk.snapshot()["boss"]
    assert snap["top_damage"][0]["rank"]["title"] == "Mèo Săn"
    assert snap["top_damage"][0]["rank"]["icon"] == "🏹"
    # qua mốc 150 -> Mèo Chiến, xướng đúng 1 lần nữa
    eff = gk.handle_gift("k1", "Mèo Leo Hạng", "Sư tử", 50)      # +100 dmg = 152
    ups = [e for e in eff if e["type"] == "rank_up"]
    assert ups and ups[0]["rank_title"] == "Mèo Chiến"

    # ================= Boss v2: THOẠI theo mốc biến hình =================
    gt = GameState(like_goal=10, rng=random.Random(41))
    gt.set_stage_mode("boss", 1000)
    taunts = []
    for _ in range(4):  # 4 món quà 99 kim cương = 198 dmg/món, đi qua 3 mốc
        eff = gt.handle_gift("t1", "Mèo Đánh Đau", "Xe đồ chơi", 99)
        taunts += [e["text"] for e in eff if e["type"] == "boss_taunt"]
    assert taunts == [
        "Á! Cái ăng-ten của ta! Đánh thế là chơi bẩn!",
        "Khói bốc là chuyện nhỏ... ta vẫn còn khỏe chán!",
        "Dừng lại đi! Ta chỉ... mượn tạm ít cá thôi mà!",
    ], taunts
    # đánh thêm mà không qua mốc mới -> không thêm thoại mốc
    eff = gt.handle_gift("t1", "Mèo Đánh Đau", "Hoa hồng", 5)    # +10 dmg
    assert not any(e["type"] == "boss_taunt" for e in eff)
    # tắt công tắc thoại -> qua mốc cũng im lặng
    gtoff = GameState(like_goal=10, rng=random.Random(43), boss_taunts=False)
    gtoff.set_stage_mode("boss", 1000)
    eff = gtoff.handle_gift("t2", "Mèo Im Lặng", "Xe đồ chơi", 99)  # 198 dmg, qua mốc 1
    assert not any(e["type"] == "boss_taunt" for e in eff)
    assert gtoff.snapshot()["boss"]["form_stage"] == 0  # 802/1000 = 80,2% vẫn mốc 0
    eff = gtoff.handle_gift("t2", "Mèo Im Lặng", "Xe đồ chơi", 99)  # qua mốc 1 thật
    assert not any(e["type"] == "boss_taunt" for e in eff)
    assert gtoff.snapshot()["boss"]["form_stage"] == 1

    # ================= Boss v2: PHẢN ĐÒN quét đuôi =================
    gc = GameState(like_goal=10, rng=random.Random(47))
    gc.set_stage_mode("boss", 1000)
    for i in range(3):
        gc.handle_join(f"c{i}", f"Mèo Chịu Đòn {i}")
    gc.tick()  # tick đầu: chỉ khởi động đồng hồ phản đòn, chưa quét
    assert not any(e["type"] == "boss_counter" for e in gc.tick())
    gc._last_counter_at = time.time() - 41   # giả lập đã qua 40s
    eff = gc.tick()
    assert any(e["type"] == "boss_counter" for e in eff)
    # chưa đủ 3 người trong phòng -> không phản đòn
    gc2 = GameState(like_goal=10, rng=random.Random(53))
    gc2.set_stage_mode("boss", 1000)
    gc2.handle_join("c9", "Mèo Đơn Độc")
    gc2.tick()
    gc2._last_counter_at = time.time() - 41
    assert not any(e["type"] == "boss_counter" for e in gc2.tick())

    # ================= Boss v2: TÀN ẢNH theo vòng / tuỳ chọn cố định =================
    from game import SKINS, boss_skin_for_round  # noqa: E402
    # ánh xạ vòng -> skin: 1 Tử, 2 Băng, 3 Lục, 4 Hỏa, 5+ Kim
    assert [boss_skin_for_round(r) for r in (1, 2, 3, 4, 5, 6)] == \
        ["tu", "bang", "luc", "hoa", "kim", "kim"]
    assert SKINS == {"tu": "TỬ QUANG", "bang": "BĂNG QUANG", "luc": "LỤC QUANG",
                     "hoa": "HỎA QUANG", "kim": "KIM QUANG"}
    # snapshot (boss_state) luôn kèm skin + skin_name, mặc định auto -> theo vòng
    gskin = GameState(like_goal=10, rng=random.Random(59))
    gskin.set_stage_mode("boss", 100)
    snap = gskin.snapshot()["boss"]
    assert snap["skin"] == "tu" and snap["skin_name"] == "TỬ QUANG"
    # hồi sinh sang vòng 2 -> tự đổi sang Băng Quang, câu xướng có tên Tàn Ảnh
    gskin.handle_gift("sk1", "Mèo Hạ Boss", "Sư tử", 100)   # 200 dmg -> gục (100 máu)
    assert not gskin.boss.alive
    gskin.boss.respawn_at = time.time() - 1
    eff = gskin.tick()
    resp = [e for e in eff if e["type"] == "boss_respawn"]
    assert resp and resp[0]["round"] == 2
    assert resp[0]["skin"] == "bang" and resp[0]["skin_name"] == "BĂNG QUANG"
    assert "BĂNG QUANG" in resp[0]["speak"]
    snap = gskin.snapshot()["boss"]
    assert snap["skin"] == "bang" and snap["skin_name"] == "BĂNG QUANG"
    # tuỳ chọn cố định thắng vòng đấu: đang vòng 2 vẫn giữ Kim Quang
    gfix = GameState(like_goal=10, rng=random.Random(61), boss_skin="kim")
    gfix.set_stage_mode("boss", 1000)
    gfix.boss.round = 2
    assert gfix.current_boss_skin() == "kim"
    snap = gfix.snapshot()["boss"]
    assert snap["skin"] == "kim" and snap["skin_name"] == "KIM QUANG"
    # đổi tuỳ chọn qua set_stage_mode (đường trang điều khiển) + giá trị lạ bị bỏ qua
    gfix.set_stage_mode("boss", 1000, None, "hoa")
    assert gfix.current_boss_skin() == "hoa"
    gfix.set_boss_skin("khong-ton-tai")
    assert gfix.current_boss_skin() == "hoa"
    gfix.set_boss_skin("auto")
    assert gfix.current_boss_skin() == "bang"   # về auto -> vòng 2 = Băng Quang

    # ---------- Tâm trạng Bug: ăn quá độ / ngủ / phá giấc / khó chịu ----------
    gm2 = GameState(like_goal=10, rng=random.Random(67))

    # Câu mở màn + nhắc luật theo chế độ: run giữ nguyên văn, boss hướng boss
    assert gm2.opening_line() == OPENING_RUN
    assert gm2.idle_line() == IDLE_RUN
    gm2.set_stage_mode("boss", 1000)
    assert gm2.opening_line() == OPENING_BOSS and "CÀO" in gm2.opening_line()
    assert gm2.idle_line() == IDLE_BOSS
    gm2.set_stage_mode("run")
    assert gm2.opening_line() == OPENING_RUN

    # Cho ăn bình thường (chưa no): giảm 10 khó chịu
    gm2.bug_annoyance = 25.0
    gm2.bug_satiety = 50
    eff = gm2.handle_comment("m1", "Sen Ăn", "hạt", now=100.0)
    assert any(e["type"] == "feed" for e in eff)
    assert gm2.bug_annoyance == 15.0

    # Cho ăn khi độ no >= 90 -> quá độ: +30 khó chịu + sự kiện bug_overfed
    gm2.bug_satiety = 95
    eff = gm2.handle_comment("m2", "Sen No", "hạt", now=101.0)
    assert any(e["type"] == "bug_overfed" for e in eff)
    assert gm2.bug_annoyance == 45.0
    assert gm2.bug_satiety == 97

    # Khó chịu >= 60: cho ăn bị từ chối (độ no không đổi), gọi ngủ cũng bị từ chối
    gm2.bug_annoyance = 80.0
    satiety_before = gm2.bug_satiety
    eff = gm2.handle_comment("m3", "Sen Cứng", "hạt", now=102.0)
    assert any(e["type"] == "bug_refuse" for e in eff)
    assert not any(e["type"] == "feed" for e in eff)
    assert gm2.bug_satiety == satiety_before
    eff = gm2.handle_comment("m3", "Sen Cứng", "ngủ", now=103.0)
    assert any(e["type"] == "bug_refuse" for e in eff)
    assert gm2.bug_sleep_until == 0

    # Hạ nhiệt khi thức: 0.4/s (tick đầu chỉ chốt mốc; dt mỗi tick kẹp tối đa 5s)
    gm2.tick(now_wall=2000.0)
    gm2.bug_annoyance = 50.0
    gm2.tick(now_wall=2005.0)
    assert abs(gm2.bug_annoyance - 48.0) < 0.01

    # Lệnh NGỦ: sự kiện bug_sleep + snapshot báo đang ngủ, đủ 3 khoá tâm trạng
    gm2.bug_annoyance = 0.0
    eff = gm2.handle_comment("m4", "Sen Ru", "ngủ", now=110.0)
    assert any(e["type"] == "bug_sleep" for e in eff)
    snap = gm2.snapshot()
    assert snap["bug"]["sleeping"] is True
    assert snap["bug"]["annoyed"] is False
    assert {"sleeping", "annoyed", "annoyance"} <= set(snap["bug"].keys())

    # Đang ngủ: hạ nhiệt nhanh 2.0/s (đặt lại mức bực sau tick chốt mốc)
    t0 = time.time()
    gm2.tick(now_wall=t0)
    gm2.bug_annoyance = 40.0
    gm2.tick(now_wall=t0 + 5)
    assert abs(gm2.bug_annoyance - 30.0) < 0.01

    # Phá giấc 3 lần trong một giấc (cho ăn + gọi ngủ + quà) -> dậy khó chịu
    eff = gm2.handle_comment("m5", "Sen Phá", "hạt", now=120.0)
    assert any(e["type"] == "bug_disturbed" for e in eff)
    eff = gm2.handle_comment("m6", "Sen Phá 2", "đi ngủ", now=121.0)
    assert any(e["type"] == "bug_disturbed" for e in eff)
    eff = gm2.handle_gift("m7", "Sen Quà", "Hoa hồng", 1)
    assert any(e["type"] == "bug_wake_annoyed" for e in eff)
    assert gm2.bug_sleep_until == 0
    assert gm2.bug_annoyance >= 70
    snap = gm2.snapshot()
    assert snap["bug"]["annoyed"] is True and snap["bug"]["sleeping"] is False

    # Ngủ đủ giấc -> tự dậy (bug_wake) + hạ 20 khó chịu
    gm2.bug_annoyance = 50.0
    gm2.bug_annoyed_until = 0.0
    gm2.bug_sleep_until = time.time() - 1  # giả lập đã ngủ đủ giấc
    eff = gm2.tick()
    assert any(e["type"] == "bug_wake" for e in eff)
    assert gm2.bug_sleep_until == 0
    assert gm2.bug_annoyance <= 30.0

    # ================= Vườn Mèo: tính cách + phản ứng theo tính cách =================
    from game import (PERSONALITY_KEYS, personality_for_uid,  # noqa: E402
                      OPENING_GARDEN, IDLE_GARDEN)

    def uid_of(personality, tag):
        i = 0
        while True:
            uid = f"{tag}{i}"
            if personality_for_uid(uid) == personality:
                return uid
            i += 1

    gv = GameState(like_goal=10, rng=random.Random(71))
    gv.GOLD_CHANCE = 0.0   # tắt xúc xắc Mèo Vàng cho các test tính cách thường
    gv.set_stage_mode("garden")
    assert gv.snapshot()["stage_mode"] == "garden"
    assert gv.opening_line() == OPENING_GARDEN
    assert gv.idle_line() == IDLE_GARDEN
    assert "garden" in gv.snapshot() and "garden_top" in gv.snapshot()

    uid_foodie = uid_of("foodie", "vf")
    uid_sleepy = uid_of("sleepy", "vs")
    uid_hyper = uid_of("hyper", "vh")
    uid_diva = uid_of("diva", "vd")
    uid_shy = uid_of("shy", "vy")
    uid_fishy = uid_of("fishy", "vc")
    assert set(PERSONALITY_KEYS) == {"foodie", "sleepy", "hyper", "diva", "shy", "fishy"}
    for uid, nick in [(uid_foodie, "Mèo Ham Ăn"), (uid_sleepy, "Mèo Lười"),
                      (uid_hyper, "Mèo Tăng Động"), (uid_diva, "Mèo Chảnh"),
                      (uid_shy, "Mèo Nhút Nhát"), (uid_fishy, "Mèo Mê Cá")]:
        gv.handle_join(uid, nick)
    for uid, key in [(uid_foodie, "foodie"), (uid_sleepy, "sleepy"),
                     (uid_hyper, "hyper"), (uid_diva, "diva"),
                     (uid_shy, "shy"), (uid_fishy, "fishy")]:
        assert gv.players[uid].personality == key, (uid, key)
        assert gv.players[uid].happiness == 60
    # tính cách ổn định giữa các phiên (cùng tên -> cùng tính cách), run không có block vườn
    gv2 = GameState(rng=random.Random(1))
    gv2.GOLD_CHANCE = 0.0
    gv2.handle_join(uid_foodie, "Mèo Ham Ăn")
    assert gv2.players[uid_foodie].personality == "foodie"
    assert "garden" not in gv2.snapshot()

    # --- HẠT: Ham Ăn +20 về bát 6s; mèo khác +6 về bát 4s ---
    eff = gv.handle_comment(uid_hyper, "Mèo Tăng Động", "hạt", now=100.0)
    assert any(e["type"] == "garden_feed" for e in eff)
    assert gv.players[uid_foodie].happiness == 80 and gv.players[uid_foodie].state == "eat"
    assert gv.players[uid_hyper].happiness == 66 and gv.players[uid_hyper].state == "eat"

    # --- NGỦ: Lười Ngủ ngủ 20s (+15); Tăng Động buồn chán -5 ---
    gv.players[uid_sleepy].happiness = 60.0
    gv.players[uid_hyper].happiness = 60.0
    gv.handle_comment(uid_sleepy, "Mèo Lười", "ngủ", now=110.0)
    assert gv.players[uid_sleepy].state == "sleep" and gv.players[uid_sleepy].happiness == 75
    assert gv.players[uid_hyper].happiness == 55

    # --- Cho ăn lúc Lười Ngủ đang ngủ trưa: bị đánh thức, -8 (Bug cũng bị phá giấc) ---
    eff = gv.handle_comment(uid_foodie, "Mèo Ham Ăn", "hạt", now=120.0)
    assert any(e["type"] == "bug_disturbed" for e in eff)
    assert gv.players[uid_sleepy].state == "idle" and gv.players[uid_sleepy].happiness == 67

    # --- CHƠI: Tăng Động +20 đuổi bóng; Nhút Nhát -4 núp; Chảnh phớt lờ ---
    for uid in (uid_hyper, uid_shy, uid_diva):
        gv.players[uid].happiness = 60.0
        gv.players[uid].state = "idle"
    eff = gv.handle_comment(uid_hyper, "Mèo Tăng Động", "chơi", now=130.0)
    assert any(e["type"] == "garden_play" for e in eff)
    assert gv.players[uid_hyper].happiness == 80 and gv.players[uid_hyper].state == "play"
    assert gv.players[uid_shy].happiness == 56 and gv.players[uid_shy].state == "hide"
    assert gv.players[uid_diva].happiness == 60 and gv.players[uid_diva].state == "idle"

    # --- Khen: Chảnh tạo dáng +20; Nhút Nhát ló đầu +12; chặn spam 1 lần / 3s ---
    gv.players[uid_diva].happiness = 60.0
    gv.players[uid_shy].happiness = 60.0
    gv.players[uid_shy].state = "idle"
    eff = gv.handle_comment(uid_foodie, "Mèo Ham Ăn", "xinh quá", now=200.0)
    assert any(e["type"] == "garden_praise" for e in eff)
    assert gv.players[uid_diva].happiness == 80 and gv.players[uid_diva].state == "pose"
    assert gv.players[uid_shy].happiness == 72 and gv.players[uid_shy].state == "peek"
    gv.players[uid_diva].happiness = 60.0
    eff = gv.handle_comment(uid_foodie, "Mèo Ham Ăn", "dễ thương quá", now=201.0)
    assert not any(e["type"] == "garden_praise" for e in eff)
    assert gv.players[uid_diva].happiness == 60
    eff = gv.handle_comment(uid_foodie, "Mèo Ham Ăn", "cute quá", now=204.0)
    assert any(e["type"] == "garden_praise" for e in eff)

    # --- CÁ: Mê Cá chầu kho cá +18; Ham Ăn hóng +6 ---
    gv.players[uid_fishy].happiness = 60.0
    gv.players[uid_foodie].happiness = 60.0
    eff = gv.handle_comment(uid_fishy, "Mèo Mê Cá", "cá", now=210.0)
    assert any(e["type"] == "garden_fish" for e in eff)
    assert gv.players[uid_fishy].happiness == 78 and gv.players[uid_fishy].state == "hoard"
    assert gv.players[uid_foodie].happiness == 66

    # --- Mèo Vàng: ép xúc xắc 100% -> hiện hình + xướng tên; sinh tim nhân đôi ---
    gg2 = GameState(like_goal=500, rng=random.Random(73))
    gg2.GOLD_CHANCE = 1.0
    gg2.set_stage_mode("garden")
    eff = gg2.handle_join("gold1", "Mèo Vàng Một")
    assert any(e["type"] == "garden_golden" for e in eff)
    assert gg2.players["gold1"].golden and gg2.players["gold1"].personality == "gold"
    snap = gg2.snapshot()
    assert snap["garden"]["golden_present"] is True
    gn2 = GameState(like_goal=500, rng=random.Random(79))
    gn2.GOLD_CHANCE = 0.0
    gn2.set_stage_mode("garden")
    gn2.handle_join("norm1", "Mèo Thường")
    t0 = time.time()
    for g_ in (gg2, gn2):
        g_.tick(now_wall=t0)          # tick đầu: chốt mốc dt
        g_.tick(now_wall=t0 + 5.5)    # +5s giờ game -> sinh đúng 1 đợt tim
    assert gn2.garden_hearts == 1 and gn2.players["norm1"].hearts == 1
    assert gg2.garden_hearts == 2 and gg2.players["gold1"].hearts == 2   # có vàng: x2

    # --- Đủ like_goal ở vườn: Bữa Tiệc Vườn thay mưa cá + snapshot vườn đầy đủ ---
    gf = GameState(like_goal=10, rng=random.Random(83))
    gf.GOLD_CHANCE = 0.0
    gf.set_stage_mode("garden")
    gf.handle_join("f1", "Mèo Tiệc")
    eff = gf.handle_like(10)
    assert any(e["type"] == "garden_feast" for e in eff)
    assert not any(e["type"] == "rain" for e in eff)
    assert gf.likes_since_rain == 0 and gf.garden_hearts == 10
    snap = gf.snapshot()
    assert snap["garden"]["feast_active"] is True
    assert {"hearts", "hearts_goal", "feast_active", "golden_hour_active",
            "decor_active", "golden_present"} <= set(snap["garden"].keys())
    assert snap["garden_top"][0]["name"] == "Mèo Tiệc"
    assert snap["garden_top"][0]["personality_name"]
    p0 = snap["players"][0]
    assert {"personality", "personality_name", "icon", "happiness", "mood_face",
            "state", "golden", "hearts"} <= set(p0.keys())

    # --- Đủ mốc tim vườn -> Giờ Vàng; mốc sau +1000; tim không bị reset ---
    gh = GameState(like_goal=500, rng=random.Random(89))
    gh.GOLD_CHANCE = 0.0
    gh.set_stage_mode("garden")
    gh.handle_join("h1", "Mèo Giờ Vàng")
    gh.garden_hearts = 999
    eff = gh.handle_like(1)
    assert any(e["type"] == "garden_golden_hour" for e in eff)
    assert gh.garden_hearts == 1000 and gh.garden_hearts_goal == 2000
    assert gh.snapshot()["garden"]["golden_hour_active"] is True
    assert gh.players["h1"].state == "feast"

    # --- Follow ở vườn: +25 tim vườn; Share: +10 tim + garden_share. Chạy: không có ---
    gfs = GameState(like_goal=500, rng=random.Random(97))
    gfs.GOLD_CHANCE = 0.0
    gfs.set_stage_mode("garden")
    eff = gfs.handle_follow("fw1", "Mèo Follow")
    assert any(e["type"] == "follow" for e in eff)
    assert gfs.garden_hearts == 25
    eff = gfs.handle_share("fw1", "Mèo Follow")
    assert any(e["type"] == "garden_share" for e in eff)
    assert gfs.garden_hearts == 35
    grr = GameState(like_goal=500, rng=random.Random(97))
    grr.GOLD_CHANCE = 0.0
    grr.handle_follow("fw1", "Mèo Follow")
    eff = grr.handle_share("fw1", "Mèo Follow")
    assert grr.garden_hearts == 0
    assert not any(e["type"] == "garden_share" for e in eff)

    # --- Quà ở vườn: người tặng mở tiệc 8s + vui 100 + bát đặc biệt; vườn trang trí ---
    ggt = GameState(like_goal=500, rng=random.Random(101))
    ggt.GOLD_CHANCE = 0.0
    ggt.set_stage_mode("garden")
    ggt.handle_join("gt1", "Mèo Quà")
    ggt.handle_join("gt2", "Mèo Bạn")
    ggt.handle_gift("gt1", "Mèo Quà", "Hoa hồng", 1)
    p_gt = ggt.players["gt1"]
    assert p_gt.happiness == 100 and p_gt.state == "feast"
    assert p_gt.public()["treat"] is True
    assert ggt.snapshot()["garden"]["decor_active"] is True
    assert 0 < ggt.garden_decor_until - time.time() <= 61
    ggt.players["gt2"].happiness = 50.0
    ggt.players["gt1"].happiness = 40.0
    ggt.handle_gift("gt2", "Mèo Bạn", "Sư tử", 150)   # quà to: cả vườn +10, trang trí 120s
    assert ggt.players["gt1"].happiness == 50
    assert ggt.garden_decor_until - time.time() > 100

    # --- Bug bị phá giấc dậy cáu ở vườn: cả đàn tản ra né (garden_scatter) ---
    gsc = GameState(like_goal=500, rng=random.Random(103))
    gsc.GOLD_CHANCE = 0.0
    gsc.set_stage_mode("garden")
    gsc.handle_join("sc1", "Mèo Phá")
    gsc.handle_join("sc2", "Mèo Né")
    gsc.handle_comment("sc1", "Mèo Phá", "ngủ", now=100.0)
    assert gsc.bug_sleep_until > time.time()
    eff = gsc.handle_comment("sc1", "Mèo Phá", "hạt", now=101.0)
    assert any(e["type"] == "bug_disturbed" for e in eff)
    eff = gsc.handle_comment("sc1", "Mèo Phá", "đi ngủ", now=102.0)
    assert any(e["type"] == "bug_disturbed" for e in eff)
    hap_before = gsc.players["sc2"].happiness
    eff = gsc.handle_gift("sc1", "Mèo Phá", "Hoa hồng", 1)
    assert any(e["type"] == "bug_wake_annoyed" for e in eff)
    assert any(e["type"] == "garden_scatter" for e in eff)
    assert gsc.players["sc2"].state == "hide"
    assert gsc.players["sc2"].happiness == hap_before - 5

    # ================= Đào Vàng PK: 2 đội móc vàng theo hiệp =================
    from game import OPENING_MINER, IDLE_MINER  # noqa: E402
    import math as _math  # noqa: E402

    gm = GameState(like_goal=10, rng=random.Random(201))
    gm.set_stage_mode("miner")
    assert gm.snapshot()["stage_mode"] == "miner"
    assert gm.opening_line() == OPENING_MINER
    assert gm.idle_line() == IDLE_MINER
    assert "miner" not in GameState(rng=random.Random(1)).snapshot()

    # --- vào đội bằng MÈO / CHUỘT; đổi đội giữ nguyên vàng cá nhân ---
    eff = gm.handle_comment("mm1", "Mèo Một", "mèo", now=100.0)
    assert any(e["type"] == "miner_join" and e["team"] == "meo" for e in eff)
    assert gm.players["mm1"].team == "meo"
    gm.handle_comment("mc1", "Chuột Một", "chuột", now=100.1)
    gm.handle_comment("mc2", "Chuột Hai", "đội chuột", now=100.2)
    assert gm.players["mc2"].team == "chuot"
    gm.players["mm1"].gold_total = 50
    gm.handle_comment("mm1", "Mèo Một", "đội chuột", now=100.3)
    assert gm.players["mm1"].team == "chuot" and gm.players["mm1"].gold_total == 50

    # --- ĐÀO khi chưa có đội: tự vào đội ít người hơn trước (mèo 0 < chuột 3) ---
    eff = gm.handle_comment("mx1", "Khách Đào", "đào", now=101.0)
    assert gm.players["mx1"].team == "meo"
    assert any(e["type"] == "miner_join" and e["team"] == "meo" for e in eff)
    assert gm.miner_hooks["meo"]["state"] == "drop"
    assert gm.miner_hooks["meo"]["caller"] == "mx1"
    # móc đang bận: người khác trong đội ĐÀO nữa cũng bị bỏ qua lặng lẽ
    gm.handle_comment("mm2", "Mèo Hai", "mèo", now=101.2)
    gm.handle_comment("mm2", "Mèo Hai", "đào", now=103.0)
    assert gm.miner_hooks["meo"]["caller"] == "mx1"

    # --- chu trình móc: thả -> giật trúng -> cộng vàng người thả + đội ---
    gd = GameState(like_goal=500, rng=random.Random(202))
    gd.set_stage_mode("miner")
    gd.handle_comment("dg1", "Thợ Đào", "mèo", now=100.0)
    gd.miner_items = [{"id": 999, "kind": "gold_s", "x": 0.20, "y": 0.60,
                       "r": 0.028, "value": 10, "weight": 1}]
    hook = gd.miner_hooks["meo"]
    hook["angle"] = 0.0
    gd.handle_comment("dg1", "Thợ Đào", "đào", now=101.0)
    assert hook["state"] == "drop"
    base = time.time()
    grab = None
    for k in range(1, 60):
        eff = gd.tick(now_wall=base + k * 0.25)
        hits = [e for e in eff if e["type"] == "miner_grab"]
        if hits:
            grab = hits[0]
            break
    assert grab and grab["kind"] == "gold_s" and grab["value"] == 10
    assert grab["team"] == "meo" and grab["user"] == "dg1"
    assert gd.players["dg1"].gold_round == 10 and gd.players["dg1"].gold_total == 10
    assert gd.miner_score["meo"] == 10
    assert hook["state"] == "swing" and hook["carrying"] is None
    assert len(gd.miner_respawn_due) == 1   # vật đã giật hẹn giờ hồi lại trên mỏ

    # giật VÀNG TO (>= 60): có câu đọc giật vàng cho đội
    gd.miner_items = [{"id": 1000, "kind": "gold_l", "x": 0.20, "y": 0.60,
                       "r": 0.06, "value": 60, "weight": 4}]
    hook["angle"] = 0.0
    gd.handle_comment("dg1", "Thợ Đào", "đào", now=105.0)
    grab2 = None
    for k in range(1, 60):
        eff = gd.tick(now_wall=base + 30 + k * 0.25)
        hits = [e for e in eff if e["type"] == "miner_grab"]
        if hits:
            grab2 = hits[0]
            break
    assert grab2 and grab2["value"] == 60
    assert grab2.get("speak") and "VÀNG TO" in grab2["speak"]
    assert gd.miner_score["meo"] == 70

    # --- kéo tay không: không cộng vàng cho ai ---
    ge = GameState(like_goal=500, rng=random.Random(203))
    ge.set_stage_mode("miner")
    ge.handle_comment("eg1", "Tay Không", "chuột", now=100.0)
    ge.miner_items = []
    hook_e = ge.miner_hooks["chuot"]
    hook_e["angle"] = 0.0
    ge.handle_comment("eg1", "Tay Không", "đào", now=101.0)
    saw_grab = False
    for k in range(1, 60):
        eff = ge.tick(now_wall=base + k * 0.25)
        saw_grab = saw_grab or any(e["type"] == "miner_grab" for e in eff)
        if hook_e["state"] == "swing" and k > 2:
            break
    assert not saw_grab and ge.players["eg1"].gold_total == 0
    assert ge.miner_score["chuot"] == 0

    # --- kéo nặng chậm hơn: đá (nặng 5) lâu về hơn vàng nhỏ (nặng 1) ---
    def pull_ticks(kind, value, weight):
        gx = GameState(like_goal=500, rng=random.Random(204))
        gx.set_stage_mode("miner")
        gx.handle_comment("px1", "Thợ Kéo", "mèo", now=100.0)
        gx.miner_items = [{"id": 1, "kind": kind, "x": 0.20, "y": 0.60,
                           "r": 0.04, "value": value, "weight": weight}]
        hk = gx.miner_hooks["meo"]
        hk["angle"] = 0.0
        gx.handle_comment("px1", "Thợ Kéo", "đào", now=101.0)
        for k in range(1, 120):
            gx.tick(now_wall=base + k * 0.25)
            if hk["state"] == "swing" and gx.players["px1"].gold_total > 0:
                return k
        return 999

    t_rock = pull_ticks("rock", 5, 5)
    t_gold = pull_ticks("gold_s", 10, 1)
    assert t_rock > t_gold, (t_rock, t_gold)

    # --- NỔ MÌN ở mốc tim: đá bay hết, vàng mới lộ ra, chu trình tim reset ---
    gb2 = GameState(like_goal=10, rng=random.Random(205))
    gb2.set_stage_mode("miner")
    gb2.miner_items = [
        {"id": 1, "kind": "rock", "x": 0.3, "y": 0.5, "r": 0.04, "value": 5, "weight": 5},
        {"id": 2, "kind": "rock", "x": 0.6, "y": 0.6, "r": 0.04, "value": 5, "weight": 5},
        {"id": 3, "kind": "gold_s", "x": 0.5, "y": 0.4, "r": 0.028, "value": 10, "weight": 1},
    ]
    eff = gb2.handle_like(10)
    assert any(e["type"] == "miner_blast" for e in eff)
    assert gb2.likes_since_rain == 0
    assert all(it["kind"] != "rock" for it in gb2.miner_items)
    assert len(gb2.miner_items) >= 5
    assert sum(1 for it in gb2.miner_items if it["kind"] in ("gold_m", "gold_l")) >= 4

    # --- hết hiệp: chốt đội thắng + MVP (hoà vàng -> ai chạm mốc trước) + reset ---
    gr = GameState(like_goal=500, rng=random.Random(206))
    gr.set_stage_mode("miner")
    gr.handle_join("ra", "Đào Thủ A")
    gr.handle_join("rb", "Đào Thủ B")
    gr.handle_comment("ra", "Đào Thủ A", "mèo", now=100.0)
    gr.handle_comment("rb", "Đào Thủ B", "chuột", now=100.1)
    gr.miner_score["meo"] = 120
    gr.miner_score["chuot"] = 80
    gr.players["ra"].gold_round = 70
    gr.players["rb"].gold_round = 70
    gr._miner_reach["ra"] = time.time() - 10   # A chạm mốc 70 trước B
    gr._miner_reach["rb"] = time.time() - 5
    gr.miner_deadline = time.time() - 1
    eff = gr.tick()
    ends = [e for e in eff if e["type"] == "miner_round_end"]
    assert ends and ends[0]["winner"] == "meo"
    assert ends[0]["score_meo"] == 120 and ends[0]["score_chuot"] == 80
    assert ends[0]["mvp"] == "ra" and ends[0]["mvp_gold"] == 70
    assert "Vua Đào Vàng" in ends[0]["speak"]
    assert gr.miner_wins["meo"] == 1 and gr.miner_wins["chuot"] == 0
    assert gr.miner_score == {"meo": 0, "chuot": 0}
    assert gr.players["ra"].gold_round == 0
    assert gr.miner_phase == "podium"
    # podium: móc bị khoá, ĐÀO bị bỏ qua
    gr.handle_comment("ra", "Đào Thủ A", "đào", now=200.0)
    assert gr.miner_hooks["meo"]["state"] == "swing"
    # podium hết giờ -> hiệp 2 bắt đầu
    gr.miner_deadline = time.time() - 1
    gr.tick()
    assert gr.miner_phase == "play" and gr.miner_round == 2

    # hiệp hoà: winner None, không MVP, thoại có chữ "hoà"
    gh = GameState(like_goal=500, rng=random.Random(207))
    gh.set_stage_mode("miner")
    gh.miner_score["meo"] = 50
    gh.miner_score["chuot"] = 50
    gh.miner_deadline = time.time() - 1
    eff = gh.tick()
    ends = [e for e in eff if e["type"] == "miner_round_end"]
    assert ends and ends[0]["winner"] is None and ends[0]["mvp"] is None
    assert "hoà" in ends[0]["speak"]

    # --- quà: buff tốc độ kéo theo kim cương; quà to -> MÓC VÀNG chĩa cục to nhất ---
    gg = GameState(like_goal=500, rng=random.Random(208))
    gg.set_stage_mode("miner")
    gg.handle_comment("gf1", "Thợ Quà", "mèo", now=100.0)
    eff = gg.handle_gift("gf1", "Thợ Quà", "Hoa hồng", 5)
    buffs = [e for e in eff if e["type"] == "miner_buff"]
    assert buffs and buffs[0]["mult"] == 1.3
    assert 0 < gg.miner_buffs["meo"]["until"] - time.time() <= 16
    gg.handle_gift("gf1", "Thợ Quà", "Xe đồ chơi", 30)
    assert gg.miner_buffs["meo"]["mult"] == 1.6
    assert 25 < gg.miner_buffs["meo"]["until"] - time.time() <= 31
    gg.miner_items = [
        {"id": 1, "kind": "gold_s", "x": 0.30, "y": 0.50, "r": 0.028, "value": 10, "weight": 1},
        {"id": 2, "kind": "diamond", "x": 0.35, "y": 0.80, "r": 0.034, "value": 150, "weight": 2},
    ]
    hook_g = gg.miner_hooks["meo"]
    assert hook_g["state"] == "swing"
    eff = gg.handle_gift("gf1", "Thợ Quà", "Sư tử", 150)
    grabs = [e for e in eff if e["type"] == "miner_golden_grab"]
    assert grabs and grabs[0]["kind"] == "diamond" and grabs[0]["team"] == "meo"
    assert hook_g["state"] == "drop" and hook_g["golden"] is True
    expected = _math.degrees(_math.atan2(0.35 - 0.20, 0.80 - 0.145))
    assert abs(hook_g["angle"] - expected) < 0.6
    # móc đang bận: quà to rơi về buff x1.6 / 30s
    eff = gg.handle_gift("gf1", "Thợ Quà", "Sư tử", 150)
    assert any(e["type"] == "miner_buff" and e["mult"] == 1.6 for e in eff)

    # --- follow: chưa có đội -> vào đội ít người hơn + 10 vàng cho đội đó ---
    gf = GameState(like_goal=500, rng=random.Random(209))
    gf.set_stage_mode("miner")
    gf.handle_comment("fw1", "Chuột Follow", "chuột", now=100.0)   # chuột 1, mèo 0
    eff = gf.handle_follow("fw2", "Khách Follow")
    bonus = [e for e in eff if e["type"] == "miner_follow_bonus"]
    assert bonus and bonus[0]["team"] == "meo" and bonus[0]["value"] == 10
    assert gf.players["fw2"].team == "meo"
    assert gf.players["fw2"].gold_round == 10 and gf.players["fw2"].gold_total == 10
    assert gf.miner_score["meo"] == 10

    # --- snapshot mỏ: đủ khoá cho sân khấu dựng hình ---
    snap = gf.snapshot()
    assert {"round", "phase", "time_left", "wins", "scores", "members",
            "hooks", "items", "blast_progress", "buffs"} <= set(snap["miner"].keys())
    assert set(snap["miner"]["hooks"].keys()) == {"meo", "chuot"}
    assert {"angle", "len", "state", "carrying_kind"} <= set(
        snap["miner"]["hooks"]["meo"].keys())
    assert snap["miner"]["items"] and set(snap["miner"]["items"][0].keys()) == {
        "id", "x", "y", "kind", "r"}
    assert snap["miner"]["blast_progress"] == {"likes": 0, "goal": 500}
    assert snap["miner_top"][0]["name"] == "Khách Follow"
    assert snap["miner_top"][0]["gold"] == 10
    pub = gf.players["fw2"].public()
    assert pub["team"] == "meo" and pub["gold_total"] == 10

    # ================= Kéo Co: 2 đội mèo kéo dây theo hiệp =================
    from game import OPENING_TUG, IDLE_TUG  # noqa: E402

    gt = GameState(like_goal=10, rng=random.Random(301))
    gt.set_stage_mode("tug")
    assert gt.snapshot()["stage_mode"] == "tug"
    assert gt.opening_line() == OPENING_TUG
    assert gt.idle_line() == IDLE_TUG
    assert "tug" not in GameState(rng=random.Random(1)).snapshot()

    # --- vào đội CAM / XÁM; KÉO khi chưa có đội -> tự vào đội ít người hơn ---
    eff = gt.handle_comment("ta", "Kéo Thủ A", "cam", now=100.0)
    assert any(e["type"] == "tug_join" and e["team"] == "cam" for e in eff)
    assert gt.players["ta"].tug_team == "cam"
    # cam 1 > xám 0 -> người KÉO đầu tiên không đội tự vào XÁM
    eff = gt.handle_comment("tb", "Kéo Thủ B", "kéo", now=100.1)
    assert gt.players["tb"].tug_team == "xam"
    assert any(e["type"] == "tug_join" and e["team"] == "xam" for e in eff)
    assert any(e["type"] == "tug_pull" for e in eff)
    # hoà số người (1-1) -> vào CAM
    gt.handle_comment("tc", "Kéo Thủ C", "kéo", now=100.2)
    assert gt.players["tc"].tug_team == "cam"
    # đổi đội được, thành tích cá nhân giữ nguyên
    gt.players["ta"].tug_force = 33.0
    gt.handle_comment("ta", "Kéo Thủ A", "đội xám", now=100.3)
    assert gt.players["ta"].tug_team == "xam" and gt.players["ta"].tug_force == 33.0

    # --- một cú kéo CAM làm dây chạy về phía âm; XÁM thì ngược lại ---
    def pull_pos(team, text_team):
        gx = GameState(like_goal=500, rng=random.Random(302))
        gx.set_stage_mode("tug")
        gx.handle_comment("p1", "Lực Sĩ", text_team, now=100.0)
        gx.handle_comment("p1", "Lực Sĩ", "kéo", now=101.0)
        base_t = time.time()
        for k in range(1, 13):
            gx.tick(now_wall=base_t + k * 0.25)
        return gx.tug_pos

    assert pull_pos("cam", "cam") < -1.5
    assert pull_pos("xam", "xám") > 1.5

    # --- cooldown KÉO 1.2s: kéo liền bị chặn, qua cooldown mới kéo được ---
    gc = GameState(like_goal=500, rng=random.Random(303))
    gc.set_stage_mode("tug")
    gc.handle_comment("c1", "Spam Thủ", "cam", now=100.0)
    eff = gc.handle_comment("c1", "Spam Thủ", "kéo", now=101.0)
    assert any(e["type"] == "tug_pull" for e in eff)
    eff = gc.handle_comment("c1", "Spam Thủ", "kéo", now=101.5)
    assert not any(e["type"] == "tug_pull" for e in eff)
    assert gc.players["c1"].tug_pulls == 1
    gc.handle_comment("c1", "Spam Thủ", "kéo", now=102.3)
    assert gc.players["c1"].tug_pulls == 2

    # --- thể lực: mỗi cú kéo -12; dưới 30 kéo yếu (x0.55); tick hồi +4/s ---
    gs = GameState(like_goal=500, rng=random.Random(304))
    gs.set_stage_mode("tug")
    gs.handle_comment("s1", "Sức Bền", "cam", now=100.0)
    for i in range(6):
        gs.handle_comment("s1", "Sức Bền", "kéo", now=101.0 + i * 1.3)
    assert gs.players["s1"].stamina == 28.0
    assert gs.players["s1"].public()["tired"] is True
    eff = gs.handle_comment("s1", "Sức Bền", "kéo", now=101.0 + 6 * 1.3)
    pulls = [e for e in eff if e["type"] == "tug_pull"]
    assert pulls and pulls[0]["force"] == 5.5   # 10 * 0.55 (khí thế 0, không buff)
    assert gs.players["s1"].stamina == 16.0
    base_s = time.time()
    gs.tick(now_wall=base_s)          # tick đầu dt = 0
    gs.tick(now_wall=base_s + 5)      # 5s -> hồi 20 thể lực
    assert gs.players["s1"].stamina == 36.0

    # --- HÒ nạp khí thế (+18, cooldown 3s); khí thế 100 -> lực x1.5 ---
    gh2 = GameState(like_goal=500, rng=random.Random(305))
    gh2.set_stage_mode("tug")
    gh2.handle_comment("h1", "Hò Thủ", "cam", now=100.0)
    eff = gh2.handle_comment("h1", "Hò Thủ", "hò", now=101.0)
    cheers = [e for e in eff if e["type"] == "tug_cheer"]
    assert cheers and cheers[0]["morale"] == 18
    eff = gh2.handle_comment("h1", "Hò Thủ", "hò dô", now=102.0)
    assert not any(e["type"] == "tug_cheer" for e in eff)   # đang cooldown
    assert gh2.tug_morale["cam"] == 18.0
    gh2.tug_morale["cam"] = 100.0
    eff = gh2.handle_comment("h1", "Hò Thủ", "kéo", now=103.0)
    pulls = [e for e in eff if e["type"] == "tug_pull"]
    assert pulls and pulls[0]["force"] == 15.0  # 10 * (1 + 100/200)

    # --- lội ngược dòng: dây lệch >= 70 chống lại đội mình -> lực x1.25 ---
    gcb = GameState(like_goal=500, rng=random.Random(306))
    gcb.set_stage_mode("tug")
    gcb.handle_comment("cb1", "Ngược Dòng", "cam", now=100.0)
    gcb.tug_pos = 75.0
    eff = gcb.handle_comment("cb1", "Ngược Dòng", "kéo", now=101.0)
    pulls = [e for e in eff if e["type"] == "tug_pull"]
    assert pulls and pulls[0]["force"] == 12.5

    # --- đoạt cờ ở |pos| >= 85: chốt hiệp ngay, xướng MVP, podium khoá kéo ---
    gw = GameState(like_goal=500, rng=random.Random(307))
    gw.set_stage_mode("tug")
    gw.handle_comment("w1", "Vô Địch", "cam", now=100.0)
    gw.players["w1"].tug_force_round = 50.0
    gw._tug_reach["w1"] = time.time() - 5
    gw.tug_pos = -84.0
    gw.tug_vel = -30.0
    base_w = time.time()
    ends = []
    for k in range(1, 10):
        eff = gw.tick(now_wall=base_w + k * 0.25)
        ends = [e for e in eff if e["type"] == "tug_round_end"]
        if ends:
            break
    assert ends and ends[0]["winner"] == "cam"
    assert ends[0]["mvp"] == "w1" and ends[0]["mvp_force"] == 50
    assert "Đoạt cờ" in ends[0]["speak"] and "Lực sĩ của hiệp" in ends[0]["speak"]
    assert gw.tug_wins["cam"] == 1 and gw.tug_pos == 0.0
    assert gw.tug_phase == "podium"
    pulls_before = gw.players["w1"].tug_pulls
    eff = gw.handle_comment("w1", "Vô Địch", "kéo", now=200.0)
    assert not any(e["type"] == "tug_pull" for e in eff)
    assert gw.players["w1"].tug_pulls == pulls_before
    # podium hết giờ -> hiệp 2
    gw.tug_deadline = time.time() - 1
    gw.tick()
    assert gw.tug_phase == "play" and gw.tug_round == 2

    # --- hết giờ: đội đang dẫn thắng; dây đứng giữa -> hoà ---
    gt2 = GameState(like_goal=500, rng=random.Random(308))
    gt2.set_stage_mode("tug")
    gt2.tug_pos = 30.0
    gt2.tug_deadline = time.time() - 1
    eff = gt2.tick()
    ends = [e for e in eff if e["type"] == "tug_round_end"]
    assert ends and ends[0]["winner"] == "xam" and gt2.tug_wins["xam"] == 1
    gt3 = GameState(like_goal=500, rng=random.Random(309))
    gt3.set_stage_mode("tug")
    gt3.tug_deadline = time.time() - 1
    eff = gt3.tick()
    ends = [e for e in eff if e["type"] == "tug_round_end"]
    assert ends and ends[0]["winner"] == "draw"
    assert gt3.tug_wins == {"cam": 0, "xam": 0}
    assert "hoà" in ends[0]["speak"]

    # --- trống hội ở mốc tim: cả 2 đội x1.5 trong 15s, chu trình tim reset ---
    gd2 = GameState(like_goal=10, rng=random.Random(310))
    gd2.set_stage_mode("tug")
    eff = gd2.handle_like(10)
    assert any(e["type"] == "tug_drums" for e in eff)
    assert gd2.likes_since_rain == 0
    assert gd2.tug_drums_until > time.time()
    gd2.handle_comment("d1", "Trống Thủ", "xám", now=100.0)
    eff = gd2.handle_comment("d1", "Trống Thủ", "kéo", now=101.0)
    pulls = [e for e in eff if e["type"] == "tug_pull"]
    assert pulls and pulls[0]["force"] == 15.0  # 10 * 1.5 trống hội

    # --- quà: buff lực theo kim cương; quà to -> GIẬT SIÊU CẤP ±12, đoạt cờ được ---
    gg2 = GameState(like_goal=500, rng=random.Random(311))
    gg2.set_stage_mode("tug")
    gg2.handle_comment("g1", "Quà Thủ", "cam", now=100.0)
    eff = gg2.handle_gift("g1", "Quà Thủ", "Hoa hồng", 5)
    buffs = [e for e in eff if e["type"] == "tug_buff"]
    assert buffs and buffs[0]["mult"] == 1.3
    assert 0 < gg2.tug_buffs["cam"]["until"] - time.time() <= 16
    gg2.handle_gift("g1", "Quà Thủ", "Xe đồ chơi", 30)
    assert gg2.tug_buffs["cam"]["mult"] == 1.6
    eff = gg2.handle_gift("g1", "Quà Thủ", "Sư tử", 150)
    supers = [e for e in eff if e["type"] == "tug_super"]
    assert supers and supers[0]["team"] == "cam"
    assert gg2.tug_pos == -12.0
    gg2.tug_pos = -78.0
    eff = gg2.handle_gift("g1", "Quà Thủ", "Sư tử", 150)
    ends = [e for e in eff if e["type"] == "tug_round_end"]
    assert ends and ends[0]["winner"] == "cam" and gg2.tug_wins["cam"] == 1

    # --- follow: chưa có đội -> vào đội ít người + khí thế đội +10 ---
    gfw = GameState(like_goal=500, rng=random.Random(312))
    gfw.set_stage_mode("tug")
    gfw.handle_comment("f1", "Xám Follow", "xám", now=100.0)   # xám 1, cam 0
    eff = gfw.handle_follow("f2", "Khách Kéo")
    fols = [e for e in eff if e["type"] == "tug_follow"]
    assert fols and fols[0]["team"] == "cam"
    assert gfw.players["f2"].tug_team == "cam"
    assert gfw.tug_morale["cam"] == 10.0

    # --- snapshot kéo co: đủ khoá cho sân khấu dựng hình ---
    snap = gfw.snapshot()
    assert {"round", "phase", "time_left", "pos", "wins", "members",
            "morale", "buffs", "drums_until"} <= set(snap["tug"].keys())
    assert snap["tug"]["members"] == {"cam": 1, "xam": 1}
    gfw.handle_comment("f2", "Khách Kéo", "kéo", now=101.0)
    snap = gfw.snapshot()
    assert snap["tug_top"][0]["name"] == "Khách Kéo"
    assert snap["tug_top"][0]["pulls"] == 1 and snap["tug_top"][0]["team"] == "cam"
    assert snap["tug_top"][0]["force"] > 0
    pub = gfw.players["f2"].public()
    assert pub["tug_team"] == "cam" and pub["tug_pulls"] == 1
    assert pub["stamina"] == 88 and pub["tired"] is False

    print("✅ Tất cả test game đều PASS")


if __name__ == "__main__":
    run()
