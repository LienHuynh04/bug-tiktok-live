"use strict";
const $ = (id) => document.getElementById(id);
const post = (url, body = {}) =>
  fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

function log(text) {
  const el = document.createElement("div");
  el.textContent = new Date().toLocaleTimeString("vi-VN") + " — " + text;
  const box = $("log");
  box.prepend(el);
  while (box.children.length > 80) box.lastChild.remove();
}

fetch("/api/config").then((r) => r.json()).then((cfg) => {
  if (cfg.app_version) $("appVersion").textContent = "Phiên bản app: " + cfg.app_version + " (bản mới nhất phải là v3.1 — không thấy số này tức là đang chạy bản cũ/tiến trình cũ)";
  $("channelName").value = cfg.channel_name || "";
  $("username").value = (cfg.tiktok_username || "").replace(/^@/, "");
  $("likeGoal").value = cfg.like_goal || 500;
  $("rainSeconds").value = cfg.rain_seconds || 30;
  $("bossMaxHp").value = cfg.boss_max_hp || 1000;
  if (typeof cfg.boss_taunts === "boolean") $("bossTaunts").checked = cfg.boss_taunts;
  $("bossSkin").value = cfg.boss_skin || "auto";
  setModeUI(cfg.stage_mode || "run");
  if (typeof cfg.meow_enabled === "boolean") $("meowEnabled").checked = cfg.meow_enabled;
  if (cfg.vbee_app_id) $("vbeeAppId").value = cfg.vbee_app_id;
  $("vbeeToken").placeholder = cfg.vbee_token_set ? "•••••• (đã lưu — để trống nếu không đổi)" : "Dán Access Token từ Vbee";
  setVbeeVoice(cfg.vbee_voice || "");
  updateVbeePanel(cfg.tts_engine);
});

/* ---------- Vbee (giọng Việt 3 miền qua API) ---------- */
const VBEE_DEFAULT_VOICE = "sg_female_thaotrinh_48k-fhg";
function setVbeeVoice(code) {
  const sel = $("vbeeVoice");
  if (code && [...sel.options].some((o) => o.value === code)) {
    sel.value = code; $("vbeeVoiceCustom").value = "";
  } else if (code) {
    $("vbeeVoiceCustom").value = code;
  } else {
    sel.value = VBEE_DEFAULT_VOICE;
  }
}
function currentVbeeVoice() {
  return $("vbeeVoiceCustom").value.trim() || $("vbeeVoice").value;
}
function updateVbeePanel(engine) {
  $("vbeePanel").style.display = engine === "vbee" ? "" : "none";
}
async function saveVbee(silent) {
  const body = { tts_engine: "vbee", vbee_app_id: $("vbeeAppId").value.trim(), vbee_voice: currentVbeeVoice() };
  const tok = $("vbeeToken").value.trim();
  if (tok) body.vbee_token = tok;
  await post("/api/config", body);
  $("vbeeToken").value = "";
  $("vbeeToken").placeholder = "•••••• (đã lưu — để trống nếu không đổi)";
  updateVbeePanel("vbee");
  if (!silent) log("Đã lưu Vbee — sân khấu sẽ đọc bằng giọng: " + body.vbee_voice);
  try {
    const cfg = await (await fetch("/api/config")).json();
    if (!cfg.vbee_token_set || !cfg.vbee_app_id) {
      log("⚠️ Chưa đủ App ID + Token Vbee — sân khấu tạm lùi về giọng trình duyệt cho tới khi nhập đủ.");
    }
  } catch { /* bỏ qua */ }
}
$("vbeeEngineBtn").onclick = async () => { updateVbeePanel("vbee"); await saveVbee(); };
$("vbeeSave").onclick = async () => { await saveVbee(); };
$("vbeeVoice").onchange = () => { $("vbeeVoiceCustom").value = ""; };
$("vbeeLoadVoices").onclick = async () => {
  await saveVbee(true);
  try {
    const r = await fetch("/api/vbee/voices");
    const data = await r.json();
    if (!r.ok) { log("Không lấy được danh sách giọng Vbee: " + (data.error || ("HTTP " + r.status))); return; }
    const arr = Array.isArray(data) ? data : (data.result || data.data || data.voices || []);
    const items = (Array.isArray(arr) ? arr : []).map((it) => {
      if (!it || typeof it !== "object") return null;
      const code = it.voice_code || it.code || it.id || "";
      const name = it.name || it.display_name || it.voice_name || it.title || code;
      return code ? { code: String(code), name: String(name) } : null;
    }).filter(Boolean);
    if (!items.length) {
      log("Vbee trả về " + (Array.isArray(arr) ? arr.length : 0) + " mục nhưng định dạng không nhận diện được — giữ danh sách giọng có sẵn.");
      return;
    }
    const keep = currentVbeeVoice();
    const sel = $("vbeeVoice");
    sel.innerHTML = "";
    items.forEach(({ code, name }) => {
      const opt = document.createElement("option");
      opt.value = code;
      opt.textContent = name + " (" + code + ")";
      sel.appendChild(opt);
    });
    setVbeeVoice(keep);
    log("Đã tải " + items.length + " giọng thật từ Vbee — chọn giọng rồi bấm 'Lưu Vbee & dùng giọng này'.");
  } catch (e) { log("Lỗi lấy danh sách giọng Vbee: " + e.message); }
};
$("vbeePreview").onclick = async (ev) => {
  const btn = ev.currentTarget;
  await saveVbee(true);
  btn.textContent = "⏳ Đang tạo…";
  try {
    const r = await post("/api/tts", { text: "Chào cả nhà! Mình là sen của Bug đây. Gõ meow để nhận một bé mèo mang tên bạn, gõ chạy để vào đội chạy cùng Bug nha!" });
    const out = await r.json();
    if (!r.ok) throw new Error(out.error || ("HTTP " + r.status));
    await new Audio(out.url).play();
    log("Đang nghe thử giọng Vbee: " + (out.voice || currentVbeeVoice()));
  } catch (e) {
    log("Vbee chưa tạo được giọng (" + e.message + ")");
  }
  btn.textContent = "🔊 Nghe thử giọng Vbee";
};

/* ---------- bảng giọng thật + tiếng mèo ---------- */
let currentVoice = "";
async function loadVoices() {
  try {
    const data = await (await fetch("/api/voices")).json();
    currentVoice = data.current;
    $("ttsRate").value = String(data.rate ?? 0);
    $("pitchInfo").textContent = `Cao độ hiện tại: ${data.pitch >= 0 ? "+" : ""}${data.pitch ?? 0}Hz — tăng cao độ là giọng trẻ và dễ thương hơn, giảm là ấm/trầm hơn.`;
    const tbody = document.querySelector("#voiceTable tbody");
    tbody.innerHTML = "";
    data.voices.forEach((v) => {
      const tr = document.createElement("tr");
      if (v.id === data.current) tr.className = "current";
      tr.innerHTML = `<td><b>${v.name}</b> ${v.recommended ? '<span class="badge">⭐ Khuyên dùng</span>' : ""}<small>${v.desc}</small></td>
        <td>${v.gender}</td>
        <td><button data-listen="${v.id}">▶️ Nghe</button></td>
        <td><button data-choose="${v.id}">${v.id === data.current ? "✅ Đang dùng" : "Chọn giọng này"}</button></td>`;
      tbody.appendChild(tr);
    });
    tbody.querySelectorAll("[data-listen]").forEach((btn) => {
      btn.onclick = async () => {
        const v = data.voices.find((x) => x.id === btn.dataset.listen);
        btn.textContent = "⏳ Đang tạo…";
        try {
          const r = await post("/api/tts", { text: v.sample, voice: v.id, rate: Number($("ttsRate").value) || 0, pitch: v.id === currentVoice ? undefined : 0 });
          const out = await r.json();
          if (!r.ok) throw new Error(out.error || r.status);
          await new Audio(out.url).play();
          log("Nghe thử giọng " + v.name);
        } catch (e) {
          log("Edge TTS chưa tạo được giọng (" + e.message + ") — kiểm tra internet, hoặc thư viện edge-tts chưa cài (xóa .venv chạy lại BAT).");
        }
        btn.textContent = "▶️ Nghe";
      };
    });
    tbody.querySelectorAll("[data-choose]").forEach((btn) => {
      btn.onclick = async () => {
        await post("/api/config", { tts_voice: btn.dataset.choose, tts_engine: "edge" });
        log("Đã chọn giọng: " + btn.dataset.choose);
        loadVoices();
      };
    });
  } catch { /* server cũ chưa có /api/voices */ }
}
loadVoices();
document.querySelectorAll("[data-preset]").forEach((btn) => {
  btn.onclick = async () => {
    await post("/api/config", { voice_preset: btn.dataset.preset });
    log("Đã đổi preset giọng: " + btn.textContent.trim());
    loadVoices();
  };
});
$("ttsRate").onchange = async () => { await post("/api/config", { tts_rate: Number($("ttsRate").value) || 0 }); log("Đã đổi tốc độ đọc"); };
$("meowEnabled").onchange = async () => { await post("/api/config", { meow_enabled: $("meowEnabled").checked }); log("Tiếng mèo: " + ($("meowEnabled").checked ? "BẬT" : "TẮT")); };
$("engineToggle").onclick = async () => {
  const cfg = await (await fetch("/api/config")).json();
  const next = cfg.tts_engine === "edge" ? "browser" : "edge";
  await post("/api/config", { tts_engine: next });
  updateVbeePanel(next);
  log("Máy đọc hiện tại: " + (next === "edge" ? "Edge TTS (giọng thật)" : "Trình duyệt (giọng máy)"));
};
$("meowTest").onclick = () => {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const t = ctx.currentTime + 0.02;
  [[720, 1080, 560, 0.45], [620, 980, 1180, 0.38]].forEach(([f0, f1, f2, dur], i) => {
    const osc = ctx.createOscillator(); const gain = ctx.createGain();
    const start = t + i * 0.5;
    osc.type = "sine";
    osc.frequency.setValueAtTime(f0, start);
    osc.frequency.exponentialRampToValueAtTime(f1, start + dur * 0.45);
    osc.frequency.exponentialRampToValueAtTime(f2, start + dur);
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(0.16, start + dur * 0.25);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + dur);
    osc.connect(gain); gain.connect(ctx.destination);
    osc.start(start); osc.stop(start + dur + 0.05);
  });
  log("🐱 Meow! (tiếng kêu sẽ phát trên sân khấu khi có sự kiện)");
};

/* ---------- chế độ sân khấu: Chạy cùng Bug / Đánh Boss ---------- */
function setModeUI(mode) {
  $("modeRun").classList.toggle("primary", mode === "run");
  $("modeBoss").classList.toggle("primary", mode === "boss");
  $("modeGarden").classList.toggle("primary", mode === "garden");
}
$("modeRun").onclick = async () => {
  await post("/api/config", { stage_mode: "run" });
  setModeUI("run");
  log("Chế độ sân khấu: 🏃 Chạy cùng Bug");
};
$("modeBoss").onclick = async () => {
  await post("/api/config", { stage_mode: "boss", boss_max_hp: Number($("bossMaxHp").value) || 1000 });
  setModeUI("boss");
  log("Chế độ sân khấu: 🐭 Đánh Boss Chuột Trùm Răng Sắt");
};
$("modeGarden").onclick = async () => {
  await post("/api/config", { stage_mode: "garden" });
  setModeUI("garden");
  log("Chế độ sân khấu: 🌿 Vườn Mèo của Bug");
};
$("bossMaxHp").onchange = async () => {
  await post("/api/config", { boss_max_hp: Number($("bossMaxHp").value) || 1000 });
  log("Đã đổi máu boss vòng 1: " + ($("bossMaxHp").value || 1000));
};
$("bossTaunts").onchange = async () => {
  await post("/api/config", { boss_taunts: $("bossTaunts").checked });
  log("Boss chửi lại: " + ($("bossTaunts").checked ? "BẬT" : "TẮT"));
};
$("bossSkin").onchange = async () => {
  await post("/api/config", { boss_skin: $("bossSkin").value });
  log("Tàn ảnh boss: " + $("bossSkin").selectedOptions[0].textContent);
};

$("saveConfig").onclick = async () => {
  await post("/api/config", {
    channel_name: $("channelName").value,
    tiktok_username: $("username").value,
    like_goal: Number($("likeGoal").value) || 500,
    rain_seconds: Number($("rainSeconds").value) || 30,
    boss_max_hp: Number($("bossMaxHp").value) || 1000,
    boss_taunts: $("bossTaunts").checked,
    boss_skin: $("bossSkin").value,
  });
  log("Đã lưu cài đặt");
};
$("connectBtn").onclick = async () => {
  await post("/api/config", { channel_name: $("channelName").value, tiktok_username: $("username").value });
  await post("/api/connect", { username: $("username").value });
  log("Đang kết nối TikTok: @" + $("username").value);
};
$("disconnectBtn").onclick = async () => { await post("/api/disconnect"); log("Đã ngắt kết nối"); };
$("demoStart").onclick = async () => { await post("/api/demo/start"); log("Bật DEMO"); };
$("demoStop").onclick = async () => { await post("/api/demo/stop"); log("Tắt DEMO"); };
$("speakBtn").onclick = async () => {
  const text = $("speakText").value.trim();
  if (text) { await post("/api/speak", { text }); log("Đọc ngay: " + text); $("speakText").value = ""; }
};
$("speakText").addEventListener("keydown", (e) => { if (e.key === "Enter") $("speakBtn").click(); });
document.querySelectorAll("[data-action]").forEach((btn) => {
  btn.onclick = async () => { await post("/api/action", { action: btn.dataset.action }); log("Điều khiển: " + btn.textContent.trim()); };
});

const proto = location.protocol === "https:" ? "wss" : "ws";
const ws = new WebSocket(`${proto}://${location.host}/ws`);
ws.onmessage = (ev) => {
  let msg;
  try { msg = JSON.parse(ev.data); } catch { return; }
  if (msg.type === "status") {
    $("status").textContent = msg.message;
    $("status").classList.toggle("on", !!msg.connected);
  } else if (msg.type === "spawn") log("🐱 " + msg.player.nickname + " vào phòng");
  else if (msg.type === "feed") log("🥣 " + msg.player.nickname + " cho Bug ăn");
  else if (msg.type === "gift") log("🎁 " + msg.player.nickname + " tặng " + msg.gift_name);
  else if (msg.type === "race_finish") log("🏆 " + msg.winner.nickname + " thắng đua mèo");
  else if (msg.type === "rain") log("🌧️🐟 Mưa cá!");
  else if (msg.type === "boss_down") log("🐭🎉 Boss gục vòng " + msg.round + " — đòn cuối: " + (msg.final_blow ? msg.final_blow.name : ""));
  else if (msg.type === "boss_respawn") log("🐭 Boss hồi sinh vòng " + msg.round + (msg.skin_name ? " — hiện hình " + msg.skin_name : "") + " (máu " + msg.max_hp + ")");
  else if (msg.type === "garden_feast") log("🌿🎉 Bữa Tiệc Vườn mở — cả đàn mèo vào bàn ăn!");
  else if (msg.type === "garden_golden_hour") log("🌇 Giờ Vàng tới — cả vườn mở tiệc lớn!");
  else if (msg.type === "garden_golden") log("✨ Mèo Vàng xuất hiện trong vườn — tim nhân đôi!");
};
