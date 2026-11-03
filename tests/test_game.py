"""Test logic game — chạy:  python tests/test_game.py"""
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from game import GameState, Race, normalize  # noqa: E402


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

    print("✅ Tất cả test game đều PASS")


if __name__ == "__main__":
    run()
