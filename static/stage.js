"use strict";
/* Sân khấu v3 "Chạy cùng Bug" — thế giới chạy vô tận (canvas) theo phong cách
   2 live mẫu: bảng UI của "Chạy cùng Kitzy" + tiêu đề/spotlight của "Chùa An Lạc".
   Giọng đọc (Edge TTS + dự phòng trình duyệt) và tiếng mèo kêu giữ từ v2. */

const $ = (id) => document.getElementById(id);
const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* ================= TTS (giữ nguyên v2) ================= */
const tts = {
  enabled: false, engine: "edge", voice: "vi-VN-HoaiMyNeural", rate: 5, pitch: 35,
  queue: [], seq: 0, speaking: false, greetBuffer: [], greetTimer: null,
  viVoice() {
    const voices = speechSynthesis.getVoices();
    return voices.find((v) => v.lang && v.lang.toLowerCase().startsWith("vi")) || null;
  },
  push(text, priority = 4) {
    if (!text) return;
    if (priority === 3) {
      this.greetBuffer.push(text);
      if (!this.greetTimer) {
        this.greetTimer = setTimeout(() => {
          const items = this.greetBuffer.splice(0);
          this.greetTimer = null;
          const names = items.map((t) => t.replace(/^Chào /, "").replace(/ vừa vào nhà của Bug!$/, "")).slice(0, 4);
          const extra = items.length - names.length;
          let msg = "Chào " + names.join(", ");
          if (extra > 0) msg += ` và ${extra} bạn nữa`;
          msg += " vừa vào nhà của Bug!";
          this._enqueue(msg, 3);
        }, 3000);
      }
      return;
    }
    this._enqueue(text, priority);
  },
  _enqueue(text, priority) {
    this.queue.push({ text, priority, seq: this.seq++ });
    this.queue.sort((a, b) => a.priority - b.priority || a.seq - b.seq);
    this._next();
  },
  pushFile(url, priority = 1) {
    // Phát một file ghi âm có sẵn (vd lời chào bằng giọng mẫu của chủ kênh)
    this.queue.push({ file: url, priority, seq: this.seq++ });
    this.queue.sort((a, b) => a.priority - b.priority || a.seq - b.seq);
    this._next();
  },
  _next() {
    if (this.speaking || !this.enabled || !this.queue.length) return;
    const item = this.queue.shift();
    this.speaking = true;
    const done = () => { this.speaking = false; setTimeout(() => this._next(), 120); };
    if (item.file) {
      const audio = new Audio(item.file);
      audio.onended = done;
      audio.onerror = done;
      audio.play().catch(done);
      return;
    }
    if (this.engine === "edge" || this.engine === "vbee") {
      fetch("/api/tts", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: item.text, voice: this.voice, rate: this.rate, pitch: this.pitch }),
      })
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error("tts " + r.status))))
        .then((data) => {
          const audio = new Audio(data.url);
          audio.onended = done;
          audio.onerror = () => this._speakBrowser(item.text, done);
          audio.play().catch(() => this._speakBrowser(item.text, done));
        })
        .catch(() => this._speakBrowser(item.text, done));
    } else {
      this._speakBrowser(item.text, done);
    }
  },
  _speakBrowser(text, done) {
    try {
      const utter = new SpeechSynthesisUtterance(text);
      const voice = this.viVoice();
      if (voice) utter.voice = voice;
      utter.lang = "vi-VN";
      utter.rate = 1.03;
      utter.pitch = Math.min(2, Math.max(0.5, 1 + (this.pitch || 0) / 120));
      utter.onend = utter.onerror = done;
      speechSynthesis.speak(utter);
    } catch { done(); }
  },
  speakNow(text) {
    this.queue = this.queue.filter((q) => q.priority > 0);
    this._enqueue(text, 0);
  },
};
if ("speechSynthesis" in window) speechSynthesis.onvoiceschanged = () => {};

/* ================= tiếng mèo kêu (giữ nguyên v2) ================= */
const meow = {
  ctx: null, enabled: true, lastAt: 0, lastSpawnAt: 0,
  unlock() {
    try {
      if (!this.ctx) this.ctx = new (window.AudioContext || window.webkitAudioContext)();
      if (this.ctx.state === "suspended") this.ctx.resume();
    } catch { /* không có audio thì thôi */ }
  },
  _one(startAt, f0, f1, f2, dur, vol = 0.16) {
    const ctx = this.ctx;
    const osc = ctx.createOscillator();
    const osc2 = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine"; osc2.type = "triangle";
    osc.frequency.setValueAtTime(f0, startAt);
    osc.frequency.exponentialRampToValueAtTime(f1, startAt + dur * 0.45);
    osc.frequency.exponentialRampToValueAtTime(f2, startAt + dur);
    osc2.frequency.setValueAtTime(f0 * 2.01, startAt);
    osc2.frequency.exponentialRampToValueAtTime(f2 * 2.01, startAt + dur);
    gain.gain.setValueAtTime(0.0001, startAt);
    gain.gain.exponentialRampToValueAtTime(vol, startAt + dur * 0.25);
    gain.gain.exponentialRampToValueAtTime(0.0001, startAt + dur);
    const g2 = ctx.createGain(); g2.gain.value = 0.35;
    osc.connect(gain); osc2.connect(g2); g2.connect(gain); gain.connect(ctx.destination);
    osc.start(startAt); osc2.start(startAt);
    osc.stop(startAt + dur + 0.05); osc2.stop(startAt + dur + 0.05);
  },
  play(kind = "normal") {
    if (!this.enabled || !this.ctx) return;
    const now = performance.now();
    if (now - this.lastAt < 350) return;
    this.lastAt = now;
    const t = this.ctx.currentTime + 0.02;
    try {
      if (kind === "kitten") this._one(t, 1050, 1450, 900, 0.32, 0.12);
      else if (kind === "happy") { this._one(t, 620, 980, 1180, 0.38); this._one(t + 0.42, 700, 1050, 900, 0.3, 0.12); }
      else if (kind === "excited") { this._one(t, 800, 1250, 700, 0.26, 0.15); this._one(t + 0.3, 850, 1300, 750, 0.26, 0.15); }
      else if (kind === "chorus") { this._one(t, 700, 1100, 650, 0.4); this._one(t + 0.18, 880, 1250, 800, 0.4, 0.12); this._one(t + 0.36, 600, 1000, 600, 0.45, 0.13); }
      else this._one(t, 720, 1080, 560, 0.45);
    } catch { /* bỏ qua */ }
  },
  playSpawn() {
    const now = performance.now();
    if (now - this.lastSpawnAt < 3000) return;
    this.lastSpawnAt = now;
    this.play("kitten");
  },
};
$("ttsEnable").addEventListener("click", () => {
  tts.enabled = true;
  meow.unlock();
  $("ttsEnable").classList.add("hidden");
  meow.play("happy");
  tts.push("Giọng đọc đã bật. Chào mừng cả nhà đến với nhà của Bug!", 1);
});

/* ================= trạng thái thế giới ================= */
const players = new Map(); // uid -> {data, img, imgOk, hue, bubble, bubbleUntil, jumpUntil, mount, mountUntil}
const dogs = [];           // chó đuổi theo khi có follow
const cars = [];           // xe trên đường dưới
let spotlight = { uid: null, until: 0 };
let worldOffset = 0;
let rankedPlayers = [];
let rankPage = 0;
const RANK_PAGE_SIZE = 6;
const sessionStart = Date.now();
let rainUntil = 0;

/* ================= chế độ Đánh Boss ================= */
let stageMode = "run";
let bossState = null;              // snapshot boss mới nhất từ server
const bossDmgByUid = new Map();    // uid -> tổng sát thương (hiện trên nhãn mèo)
const bossRankByUid = new Map();   // uid -> {icon, title} hạng mèo (từ top_damage)
const bossFx = {
  attacks: [],      // {uid, kind, t0, damage}
  numbers: [],      // {val, t0, dx, big}
  swarmUntil: 0,
  flashUntil: 0,
  shakeUntil: 0,
  counterUntil: 0,  // phản đòn quét đuôi đang diễn (hiệu ứng hình ảnh)
  counterT0: 0,
  skinFlashUntil: 0, // chớp sáng 300ms khi boss đổi Tàn Ảnh
};
let bossBannerMode = "";           // "" | "down" (ăn mừng 8s) | "wait" (đếm hồi sinh)
let bossTauntTimer = null;
let bossSyncTimer = null;
const BOSS_BAR_HP = 250;           // mỗi thanh máu trên HUD = 250 HP (khớp game.py)

function setStageMode(mode) {
  if (mode !== "run" && mode !== "boss") return;
  stageMode = mode;
  $("stage").classList.toggle("boss-mode", mode === "boss");
  // nền boss tối sâu -> panel chuyển kính tối cho khỏi "nổi" lạc tông (chỉ boss)
  $("stage").classList.toggle("boss-dark", mode === "boss");
}

function updateBoss(b) {
  bossState = b;
  // Tàn Ảnh đổi (vòng mới / đổi tuỳ chọn) -> chớp sáng chuyển hình trên sân khấu
  if (b.skin) {
    if (lastBossSkin && b.skin !== lastBossSkin) bossFx.skinFlashUntil = performance.now() + 300;
    lastBossSkin = b.skin;
  }
  $("bossName").textContent = b.skin_name
    ? `${b.name || "CHUỘT TRÙM RĂNG SẮT"} • ${b.skin_name}`
    : (b.name || "CHUỘT TRÙM RĂNG SẮT");
  bossDmgByUid.clear();
  bossRankByUid.clear();
  (b.top_damage || []).forEach((t) => {
    bossDmgByUid.set(t.unique_id, t.damage);
    if (t.rank) bossRankByUid.set(t.unique_id, t.rank);
  });
  $("statBossRound").textContent = b.round;
  $("statBossDmg").textContent = b.total_damage || 0;
  $("bossRound").textContent = b.round;
  // Thanh HP chính chỉ hiện THANH ĐANG ĐÁNH (mỗi thanh 250 máu, kiểu raid ×N thanh)
  const barsLeft = typeof b.bars_left === "number" ? b.bars_left : Math.ceil(Math.max(0, b.hp) / BOSS_BAR_HP);
  const barsTotal = typeof b.bars_total === "number" ? b.bars_total : Math.max(1, Math.ceil(b.max_hp / BOSS_BAR_HP));
  const curBarHp = b.hp - Math.max(0, barsLeft - 1) * BOSS_BAR_HP;
  $("bossHpFill").style.width = Math.max(0, Math.min(100, (curBarHp / BOSS_BAR_HP) * 100)) + "%";
  $("bossHpText").textContent = `${b.hp} / ${b.max_hp}`;
  const pct = typeof b.percent_destroyed === "number" ? b.percent_destroyed
    : (1 - b.hp / Math.max(1, b.max_hp)) * 100;
  $("bossBarsText").textContent = `×${barsLeft} THANH MÁU • Đã hạ ${pct.toFixed(4).replace(".", ",")}%`;
  $("bossRageFill").style.width = Math.max(0, Math.min(100, ((b.rage || 0) / Math.max(1, b.rage_max || 200)) * 100)) + "%";
  $("bossRageText").textContent = `🔥 Nộ ${b.rage || 0}/${b.rage_max || 200}`;
  $("bossSyncText").textContent = (b.sync_left || 0) > 0
    ? `⚡ ĐỒNG LOẠT ×2 — còn ${b.sync_left}s!`
    : `Đồng loạt: ${b.sync_count || 0}/5`;
  $("bossRankList").innerHTML = (b.top_damage || []).length
    ? b.top_damage.map((t, i) => `<li><span class="rname">${t.rank ? t.rank.icon + " " : ""}${i + 1}. ${escapeHtml(t.name)}${t.rank ? ` · ${escapeHtml(t.rank.title)}` : ""}</span><span class="rkm">${t.damage}</span></li>`).join("")
    : `<li><span class="rname">Chưa có ai — gõ "cào" để tấn công!</span></li>`;
  if (b.alive) {
    if (bossBannerMode) { bossBannerMode = ""; $("bossBanner").classList.add("hidden"); }
  } else if (bossBannerMode === "wait") {
    showBossWait();
  } else if (!bossBannerMode) {
    bossBannerMode = "wait";
    showBossWait();
  }
}

function showBossDown(msg) {
  bossBannerMode = "down";
  $("bossBannerTitle").textContent = "🎉 HẠ GỤC RĂNG SẮT!";
  $("bossBannerSub").textContent = `Đòn cuối: ${msg.final_blow ? msg.final_blow.name : "?"} • Vòng ${msg.round}`;
  $("bossBannerTop").innerHTML = (msg.top3 || [])
    .map((t, i) => `${["🥇", "🥈", "🥉"][i] || ""} ${escapeHtml(t.name)} — ${t.damage}`).join("<br>");
  $("bossBanner").classList.remove("hidden");
  setTimeout(() => {
    if (bossBannerMode === "down" && bossState && !bossState.alive) {
      bossBannerMode = "wait";
      showBossWait();
    }
  }, 8000);
}
function showBossWait() {
  if (!bossState) return;
  $("bossBannerTitle").textContent = "💀 RĂNG SẮT ĐÃ GỤC";
  $("bossBannerSub").textContent = `Hồi sinh sau ${bossState.respawn_in}s… vòng sau máu +20%`;
  $("bossBannerTop").innerHTML = "";
  $("bossBanner").classList.remove("hidden");
}

function hueOf(str) { let h = 0; for (const c of str) h = (h * 31 + c.charCodeAt(0)) % 360; return h; }

function upsertPlayer(p) {
  let rec = players.get(p.unique_id);
  if (!rec) {
    rec = { data: p, img: null, imgOk: false, hue: hueOf(p.unique_id), bubble: "", bubbleUntil: 0, jumpUntil: 0, mount: "", mountUntil: 0 };
    if (p.avatar_url) {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => { rec.imgOk = true; };
      img.onerror = () => { rec.imgOk = false; };
      img.src = p.avatar_url;
      rec.img = img;
    }
    players.set(p.unique_id, rec);
  } else {
    rec.data = p;
  }
  return rec;
}
function setBubble(rec, text, ms = 4000) {
  if (!rec || !text) return;
  rec.bubble = String(text).slice(0, 60);
  rec.bubbleUntil = performance.now() + ms;
}

/* ================= panel ================= */
function ticker(text) { if (text) $("ticker").textContent = text; }
function logEvent(text) {
  const li = document.createElement("li");
  li.textContent = text;
  const box = $("eventLog");
  box.prepend(li);
  while (box.children.length > 4) box.lastChild.remove();
}
function renderRank() {
  const totalPages = Math.max(1, Math.ceil(rankedPlayers.length / RANK_PAGE_SIZE));
  rankPage = rankPage % totalPages;
  const slice = rankedPlayers.slice(rankPage * RANK_PAGE_SIZE, rankPage * RANK_PAGE_SIZE + RANK_PAGE_SIZE);
  $("rankPage").textContent = `Trang ${rankPage + 1}/${totalPages}`;
  $("rankList").innerHTML = slice.length
    ? slice.map((p, i) => `<li><span class="rname">${rankPage * RANK_PAGE_SIZE + i + 1}. ${escapeHtml(p.nickname)}</span><span class="rkm">${(p.distance_km || 0).toFixed(2)} km</span></li>`).join("")
    : `<li><span class="rname">Chưa có ai — gõ "chạy" để vào đội!</span></li>`;
}
setInterval(() => { rankPage++; renderRank(); }, 8000);

function renderSnapshot(s) {
  if (s.stage_mode) setStageMode(s.stage_mode);
  if (s.boss) updateBoss(s.boss);
  if (s.players) {
    s.players.forEach(upsertPlayer);
    rankedPlayers = [...s.players].sort((a, b) => (b.distance_km || 0) - (a.distance_km || 0));
    renderRank();
    $("statStars").textContent = s.players.reduce((sum, p) => sum + (p.points || 0), 0);
  }
  if (typeof s.total_likes === "number") $("statLikes").textContent = s.total_likes;
  if (typeof s.follows_count === "number") $("statFollows").textContent = s.follows_count;
  if (typeof s.team_size === "number") $("statTeam").textContent = s.team_size;
  if (typeof s.team_km === "number") $("statKm").textContent = s.team_km.toFixed(2);
  if (typeof s.likes_since_rain === "number") {
    $("likeText").textContent = `${s.likes_since_rain} / ${s.like_goal}`;
    $("likeGoalText").textContent = s.like_goal;
    $("likeFill").style.width = Math.min(100, (s.likes_since_rain / s.like_goal) * 100) + "%";
  }
  if (typeof s.bug_satiety === "number") {
    $("satietyFill").style.width = s.bug_satiety + "%";
    const hungry = s.bug_satiety < 25;
    $("bugBar").classList.toggle("hungry", hungry);
    $("bugFace").textContent = hungry ? "😿" : "🐱";
    $("bugMood").textContent = hungry ? "đang đói — cả đội chậm 30%!" : s.bug_satiety > 70 ? "no căng, đang vui vẻ" : "đang vui vẻ";
    $("bugSub").textContent = hungry ? "⚠️ Bug đói rồi — gõ HẠT cho Bug ăn mau!" : "Độ no của Bug — gõ HẠT để cho ăn";
  }
}
setInterval(() => {
  const sec = Math.floor((Date.now() - sessionStart) / 1000);
  const hh = String(Math.floor(sec / 3600)).padStart(2, "0");
  const mm = String(Math.floor((sec % 3600) / 60)).padStart(2, "0");
  const ss = String(sec % 60).padStart(2, "0");
  $("statTime").textContent = sec >= 3600 ? `${hh}:${mm}:${ss}` : `${mm}:${ss}`;
}, 1000);

const GUIDE_TEXTS = [
  "Follow để Bug đuổi theo nha! 🐕",
  "Gõ \"chạy\" để vào đội chạy cùng Bug 🏃",
  "Gõ \"hạng\" để xem thứ hạng của bạn 🏆",
  "Thả tim đủ là mưa cá đó! ❤️🐟",
  "Bug đói là cả đội chạy chậm lại — nhớ gõ \"hạt\" 🥣",
];
const BOSS_GUIDE_TEXTS = [
  "Gõ \"cào\" để mèo của bạn tấn công Chuột Trùm Răng Sắt 🐾",
  "5 mèo cùng \"cào\" trong 3 giây → ĐÒN ĐỒNG LOẠT x2! ⚡",
  "Thả tim nạp Nộ — đầy là mưa cá trút xuống boss! 🔥",
  "Boss choáng là lúc cào đau gấp đôi đó! 💫",
  "Gõ \"hạt\" cho Bug ăn lấy sức 🥣",
];
let guideIdx = 0;
setInterval(() => {
  const arr = stageMode === "boss" ? BOSS_GUIDE_TEXTS : GUIDE_TEXTS;
  guideIdx = (guideIdx + 1) % arr.length;
  $("guideBanner").textContent = arr[guideIdx];
}, 6000);

/* ================= hiệu ứng mưa ================= */
function rain(kind = "fish", seconds = 30) {
  rainUntil = Date.now() + seconds * 1000;
  const layer = $("rainLayer");
  const emojis = ["🐟", "🐠", "🥣", "✨"];
  const timer = setInterval(() => {
    if (Date.now() > rainUntil) { clearInterval(timer); return; }
    const el = document.createElement("div");
    el.className = "rain-drop";
    el.textContent = emojis[Math.floor(Math.random() * emojis.length)];
    el.style.left = Math.random() * 96 + "vw";
    el.style.fontSize = 2.4 + Math.random() * 2.4 + "vh";
    el.style.animationDuration = 1.6 + Math.random() * 1.8 + "s";
    layer.appendChild(el);
    setTimeout(() => el.remove(), 3800);
  }, 110);
}

/* ================= canvas: thế giới chạy ================= */
const canvas = $("world");
const ctx2d = canvas.getContext("2d");
function fitCanvas() {
  const dpr = Math.min(1.5, window.devicePixelRatio || 1);
  canvas.width = Math.floor(window.innerWidth * dpr);
  canvas.height = Math.floor(window.innerHeight * dpr);
}
window.addEventListener("resize", fitCanvas);
fitCanvas();

for (let i = 0; i < 3; i++) {
  cars.push({ x: Math.random(), row: i % 2, speed: 0.05 + Math.random() * 0.05, emoji: ["🚗", "🚕", "🚙", "🛻"][i % 4] });
}

function drawCat(x, y, s, rec, now, scale = 1, labelText = null) {
  const p = rec.data;
  const running = p.in_team;
  const mode = p.speed_mode || "normal";
  const bob = running ? Math.sin(now / (mode === "boost" ? 90 : 150) + rec.hue) * s * 0.07 : 0;
  let jumpY = 0;
  if (rec.jumpUntil > now) {
    const prog = 1 - (rec.jumpUntil - now) / 650;
    jumpY = -Math.sin(prog * Math.PI) * s * 0.85;
  }
  const cy = y + bob + jumpY;
  ctx2d.save();
  ctx2d.translate(x, cy);
  ctx2d.scale(scale, scale);
  // bóng
  ctx2d.fillStyle = "rgba(30,40,20,.25)";
  ctx2d.beginPath(); ctx2d.ellipse(0, s * 0.42 - jumpY * 0.4, s * 0.62, s * 0.13, 0, 0, Math.PI * 2); ctx2d.fill();
  // xe cưỡi (quà)
  if (rec.mountUntil > now) {
    ctx2d.font = `${s * 1.05}px serif`;
    ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
    ctx2d.fillText(rec.mount, 0, s * 0.34);
  }
  // thân mèo
  ctx2d.fillStyle = `hsl(${rec.hue} 65% 62%)`;
  ctx2d.beginPath();
  ctx2d.ellipse(0, 0, s * 0.58, s * 0.4, 0, 0, Math.PI * 2);
  ctx2d.fill();
  // đuôi
  ctx2d.strokeStyle = `hsl(${rec.hue} 65% 50%)`;
  ctx2d.lineWidth = s * 0.11; ctx2d.lineCap = "round";
  ctx2d.beginPath(); ctx2d.moveTo(-s * 0.52, -s * 0.05);
  ctx2d.quadraticCurveTo(-s * 0.85, -s * 0.4, -s * 0.7, -s * 0.62 + bob * 1.4); ctx2d.stroke();
  // chân chạy
  if (running) {
    ctx2d.strokeStyle = `hsl(${rec.hue} 60% 45%)`;
    ctx2d.lineWidth = s * 0.1;
    const ph = Math.sin(now / (mode === "boost" ? 90 : 150) + rec.hue);
    for (const dir of [-1, 1]) {
      ctx2d.beginPath();
      ctx2d.moveTo(dir * s * 0.25, s * 0.3);
      ctx2d.lineTo(dir * s * 0.25 + ph * dir * s * 0.22, s * 0.52);
      ctx2d.stroke();
    }
  }
  // vệt tốc độ
  if (running && mode === "boost") {
    ctx2d.strokeStyle = "rgba(255,255,255,.75)";
    ctx2d.lineWidth = s * 0.06;
    for (let i = 0; i < 3; i++) {
      const ly = -s * 0.2 + i * s * 0.2;
      ctx2d.beginPath(); ctx2d.moveTo(-s * 0.7, ly); ctx2d.lineTo(-s * 1.25, ly); ctx2d.stroke();
    }
  }
  // đầu = avatar người xem + tai mèo
  const hx = s * 0.34, hy = -s * 0.52, hr = s * 0.37;
  ctx2d.fillStyle = "#ffb84d";
  for (const dir of [-1, 1]) {
    ctx2d.beginPath();
    ctx2d.moveTo(hx + dir * hr * 0.72, hy - hr * 0.55);
    ctx2d.lineTo(hx + dir * hr * 0.28, hy - hr * 1.18);
    ctx2d.lineTo(hx + dir * hr * 1.05, hy - hr * 0.92);
    ctx2d.closePath(); ctx2d.fill();
  }
  ctx2d.save();
  ctx2d.beginPath(); ctx2d.arc(hx, hy, hr, 0, Math.PI * 2); ctx2d.clip();
  if (rec.imgOk && rec.img) {
    ctx2d.drawImage(rec.img, hx - hr, hy - hr, hr * 2, hr * 2);
  } else {
    ctx2d.fillStyle = `hsl(${rec.hue} 55% 45%)`;
    ctx2d.fillRect(hx - hr, hy - hr, hr * 2, hr * 2);
    ctx2d.fillStyle = "#fff";
    ctx2d.font = `800 ${hr * 1.05}px sans-serif`;
    ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
    ctx2d.fillText((p.nickname || "?").slice(0, 1).toUpperCase(), hx, hy + 1);
  }
  ctx2d.restore();
  ctx2d.strokeStyle = "#ffb84d"; ctx2d.lineWidth = 2.5;
  ctx2d.beginPath(); ctx2d.arc(hx, hy, hr, 0, Math.PI * 2); ctx2d.stroke();
  if (mode === "slow") {
    ctx2d.font = `${s * 0.5}px serif`;
    ctx2d.textAlign = "center";
    ctx2d.fillText("💤", hx + hr * 0.9, hy - hr * 0.9);
  }
  ctx2d.restore();

  // thẻ tên + km (không scale theo spotlight cho dễ đọc)
  ctx2d.save();
  ctx2d.translate(x, cy);
  const label = labelText || `${p.nickname} • ${(p.distance_km || 0).toFixed(2)}km`;
  ctx2d.font = `600 ${Math.max(11, s * 0.3)}px sans-serif`;
  const tw = ctx2d.measureText(label).width + 14;
  const ly = -s * 1.28 * scale;
  ctx2d.fillStyle = "rgba(15,20,38,.82)";
  ctx2d.beginPath(); ctx2d.roundRect(-tw / 2, ly - s * 0.2, tw, s * 0.42, 8); ctx2d.fill();
  ctx2d.fillStyle = "#fff"; ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
  ctx2d.fillText(label, 0, ly + s * 0.02);
  // bong bóng chat
  if (rec.bubbleUntil > now && rec.bubble) {
    ctx2d.font = `${Math.max(11, s * 0.3)}px sans-serif`;
    const bw = Math.min(260, ctx2d.measureText(rec.bubble).width + 16);
    const by = ly - s * 0.62;
    ctx2d.fillStyle = "#fff";
    ctx2d.beginPath(); ctx2d.roundRect(-bw / 2, by - s * 0.2, bw, s * 0.42, 10); ctx2d.fill();
    ctx2d.fillStyle = "#17304f";
    ctx2d.fillText(rec.bubble, 0, by + s * 0.02, bw - 10);
  }
  ctx2d.restore();
}

/* ---- Ảnh Tàn Ảnh boss: nạp sẵn từ window.BOSS_ART (static/boss-art.js).
   Thiếu file hoặc ảnh chưa nạp xong -> sân khấu lùi về vòng cổng + emoji như cũ. ---- */
const bossArtImages = {};
if (typeof window !== "undefined" && window.BOSS_ART) {
  for (const key of Object.keys(window.BOSS_ART)) {
    const img = new Image();
    img.src = window.BOSS_ART[key];
    bossArtImages[key] = img;
  }
}
// Vị trí mắt trong khung ảnh vuông (tỉ lệ 0..1) — thắp quầng đỏ khi biến hình mốc >= 2
const BOSS_ART_EYES = {
  tu: [[0.418, 0.312], [0.578, 0.312]],
  bang: [[0.420, 0.310], [0.585, 0.310]],
  luc: [[0.415, 0.325], [0.585, 0.325]],
  hoa: [[0.510, 0.324], [0.665, 0.330]],
  kim: [[0.400, 0.355], [0.600, 0.355]],
};
let lastBossSkin = null; // Tàn Ảnh của snapshot trước — đổi khác là chớp sáng chuyển hình

/* ---- Cột sáng trung tâm sau lưng boss (yếu tố chính của nền v2): chùm sáng
   xanh-tím nhạt rủ từ trên xuống vòng ma thuật, mép mềm cả ngang lẫn dọc.
   Vẽ 1 lần vào canvas đệm (đắt vì 2 lớp gradient chéo nhau), mỗi khung chỉ
   drawImage lại với alpha nhấp nháy rất nhẹ cho cảm giác "sống". ---- */
let pillarCache = null; // {w, h, canvas}
function getPillarCanvas(W, H) {
  if (pillarCache && pillarCache.w === W && pillarCache.h === H) return pillarCache.canvas;
  const c = document.createElement("canvas");
  c.width = W; c.height = H;
  const g = c.getContext("2d");
  const cx = W * 0.5;
  const bottom = H * 0.085 + W * 0.94 + H * 0.03; // chạm tới vòng ma thuật dưới chân boss
  const layers = [
    { w: W * 0.80, col: "130, 145, 255", a: 0.16 },  // chùm ngoài: rộng hơn khung thân boss mới lộ 2 bên vai
    { w: W * 0.30, col: "196, 206, 255", a: 0.20 },  // lõi trong sáng hơn
  ];
  for (const L of layers) {
    const x0 = cx - L.w / 2;
    const hg = g.createLinearGradient(x0, 0, x0 + L.w, 0);
    hg.addColorStop(0, `rgba(${L.col}, 0)`);
    hg.addColorStop(0.5, `rgba(${L.col}, ${L.a})`);
    hg.addColorStop(1, `rgba(${L.col}, 0)`);
    g.fillStyle = hg;
    g.fillRect(x0, 0, L.w, bottom);
  }
  // tan dần xuống dưới bằng destination-out (chỉ xén alpha, không sơn màu nền)
  g.globalCompositeOperation = "destination-out";
  const vg = g.createLinearGradient(0, 0, 0, bottom);
  vg.addColorStop(0, "rgba(0, 0, 0, 0)");
  vg.addColorStop(0.55, "rgba(0, 0, 0, 0)");
  vg.addColorStop(1, "rgba(0, 0, 0, 1)");
  g.fillStyle = vg;
  g.fillRect(0, 0, W, bottom);
  g.globalCompositeOperation = "source-over";
  pillarCache = { w: W, h: H, canvas: c };
  return c;
}

/* ---- Đấu trường tối huyền bí v2 (chỉ khi có ảnh Tàn Ảnh): nền gần đen,
   cột sáng trung tâm + hào quang sau lưng boss làm boss nổi bật, sương và
   hạt sáng tiết chế, tối góc (vignette), vòng ma thuật. ---- */
function drawBossArena(now, W, H, cx) {
  const bg = ctx2d.createLinearGradient(0, 0, 0, H);
  bg.addColorStop(0, "#030110"); bg.addColorStop(0.45, "#0d0733"); bg.addColorStop(1, "#020108");
  ctx2d.fillStyle = bg; ctx2d.fillRect(0, 0, W, H);
  // cột sáng trung tâm sau lưng boss (nhấp nháy alpha rất nhẹ)
  ctx2d.save();
  ctx2d.globalAlpha = 0.93 + 0.07 * Math.sin(now / 2600);
  ctx2d.drawImage(getPillarCanvas(W, H), 0, 0);
  ctx2d.restore();
  // hào quang tím mềm sau lưng boss
  const glow = ctx2d.createRadialGradient(cx, H * 0.34, H * 0.05, cx, H * 0.34, H * 0.46);
  glow.addColorStop(0, "rgba(124, 77, 255, .34)");
  glow.addColorStop(0.55, "rgba(94, 53, 200, .16)");
  glow.addColorStop(1, "rgba(94, 53, 200, 0)");
  ctx2d.fillStyle = glow; ctx2d.fillRect(0, 0, W, H);
  // sương mù: mấy quầng trắng-tím rất nhạt trôi ngang lưng chừng + sát chân boss
  for (let i = 0; i < 6; i++) {
    const my = H * (i % 2 ? 0.60 : 0.40) + (i % 3) * H * 0.012;
    const mx = cx + Math.sin(now / (5200 + i * 900) + i * 1.9) * W * 0.30 + (i - 2.5) * W * 0.09;
    const mr = W * (0.30 + (i % 3) * 0.07);
    const mist = ctx2d.createRadialGradient(mx, my, 0, mx, my, mr);
    mist.addColorStop(0, "rgba(196, 178, 255, .052)");
    mist.addColorStop(1, "rgba(196, 178, 255, 0)");
    ctx2d.save();
    ctx2d.translate(mx, my); ctx2d.scale(1, 0.32); ctx2d.translate(-mx, -my);
    ctx2d.fillStyle = mist;
    ctx2d.beginPath(); ctx2d.arc(mx, my, mr, 0, Math.PI * 2); ctx2d.fill();
    ctx2d.restore();
  }
  // hạt sáng tím/vàng thưa, mờ — bay lên chậm
  for (let i = 0; i < 16; i++) {
    const speed = 0.014 + (i % 4) * 0.004;
    const px = (i * 379.7) % W;
    const py = H - ((now * speed + i * 173.3) % (H * 0.92)) - H * 0.03;
    const tw = 0.35 + 0.65 * Math.abs(Math.sin(now / 700 + i * 2.3));
    ctx2d.fillStyle = i % 3 === 0 ? `rgba(255, 205, 96, ${0.34 * tw})` : `rgba(178, 148, 255, ${0.38 * tw})`;
    ctx2d.beginPath(); ctx2d.arc(px, py, i % 3 === 0 ? 2.4 : 1.8, 0, Math.PI * 2); ctx2d.fill();
  }
  // tối góc: giữa khung trong suốt -> mép chìm vào đen (vẽ trên nền, dưới boss/mèo)
  const vig = ctx2d.createRadialGradient(cx, H * 0.46, H * 0.28, cx, H * 0.46, H * 0.74);
  vig.addColorStop(0, "rgba(0, 0, 0, 0)");
  vig.addColorStop(0.62, "rgba(0, 0, 0, .14)");
  vig.addColorStop(1, "rgba(0, 0, 0, .55)");
  ctx2d.fillStyle = vig; ctx2d.fillRect(0, 0, W, H);
}

/* ---- Vòng ma thuật dưới chân boss: vẽ SAU ảnh để quầng mép ảnh không che mất.
   Quầng sáng tím + 2 vòng ellipse (vàng, tím) + vạch rune xoay chậm. ---- */
function drawMagicCircle(now, W, H, cx, baseY) {
  const rx = W * 0.335, ry = rx * 0.30;
  ctx2d.save();
  ctx2d.translate(cx, baseY);
  // quầng sáng sàn rộng và rất mờ loang ra dưới vòng
  const floor = ctx2d.createRadialGradient(0, 0, 0, 0, 0, rx * 1.45);
  floor.addColorStop(0, "rgba(120, 100, 255, .13)"); floor.addColorStop(1, "rgba(120, 100, 255, 0)");
  ctx2d.fillStyle = floor;
  ctx2d.beginPath(); ctx2d.ellipse(0, 0, rx * 1.45, ry * 1.45, 0, 0, Math.PI * 2); ctx2d.fill();
  const under = ctx2d.createRadialGradient(0, 0, 0, 0, 0, rx);
  under.addColorStop(0, "rgba(140, 95, 255, .28)"); under.addColorStop(1, "rgba(140, 95, 255, 0)");
  ctx2d.fillStyle = under;
  ctx2d.beginPath(); ctx2d.ellipse(0, 0, rx, ry, 0, 0, Math.PI * 2); ctx2d.fill();
  ctx2d.lineWidth = 3; ctx2d.strokeStyle = "rgba(217, 164, 65, .95)";
  ctx2d.beginPath(); ctx2d.ellipse(0, 0, rx, ry, 0, 0, Math.PI * 2); ctx2d.stroke();
  ctx2d.lineWidth = 2; ctx2d.strokeStyle = "rgba(150, 110, 255, .65)";
  ctx2d.beginPath(); ctx2d.ellipse(0, 0, rx * 0.82, ry * 0.82, 0, 0, Math.PI * 2); ctx2d.stroke();
  const rot = now / 4500;
  ctx2d.strokeStyle = "rgba(255, 215, 130, .8)"; ctx2d.lineWidth = 2.5;
  for (let i = 0; i < 24; i++) {
    const a = rot + (i / 24) * Math.PI * 2;
    ctx2d.beginPath();
    ctx2d.moveTo(Math.cos(a) * rx * 0.90, Math.sin(a) * ry * 0.90);
    ctx2d.lineTo(Math.cos(a) * rx * 0.97, Math.sin(a) * ry * 0.97);
    ctx2d.stroke();
  }
  ctx2d.restore();
}

/* ---- 2 sợi xích vàng từ 2 góc trên chéo xuống sau vai boss ---- */
function drawBossChains(W, H) {
  ctx2d.save();
  ctx2d.globalAlpha = 0.9; // xích hơi chìm vào nền tối, không tranh sáng với boss
  const runs = [
    { x0: -W * 0.01, y0: -H * 0.005, x1: W * 0.315, y1: H * 0.315 },
    { x0: W * 1.01, y0: -H * 0.005, x1: W * 0.685, y1: H * 0.315 },
  ];
  for (const r of runs) {
    const dx = r.x1 - r.x0, dy = r.y1 - r.y0;
    const step = H * 0.0175;
    const ang = Math.atan2(dy, dx);
    const n = Math.max(1, Math.floor(Math.hypot(dx, dy) / step));
    for (let i = 0; i <= n; i++) {
      const x = r.x0 + dx * (i / n), y = r.y0 + dy * (i / n);
      ctx2d.save();
      ctx2d.translate(x, y);
      ctx2d.rotate(ang + (i % 2 ? Math.PI / 2 : 0));
      ctx2d.lineWidth = 2.6; ctx2d.strokeStyle = "#d9a441";
      ctx2d.beginPath(); ctx2d.ellipse(0, 0, step * 0.42, step * 0.24, 0, 0, Math.PI * 2); ctx2d.stroke();
      ctx2d.lineWidth = 1.1; ctx2d.strokeStyle = "rgba(255, 226, 150, .65)";
      ctx2d.beginPath(); ctx2d.ellipse(-step * 0.08, -step * 0.06, step * 0.30, step * 0.15, 0, 0, Math.PI * 2); ctx2d.stroke();
      ctx2d.restore();
    }
  }
  ctx2d.restore();
}

/* ---- Vẽ ảnh Tàn Ảnh + làm mờ 4 mép hoà vào nền đấu trường (không lộ cạnh vuông) ---- */
function drawBossArt(img, x, y, size) {
  ctx2d.drawImage(img, x, y, size, size);
  let g;
  const fyT = size * 0.15, fyB = size * 0.24, fx = size * 0.13;
  g = ctx2d.createLinearGradient(0, y, 0, y + fyT);
  g.addColorStop(0, "rgba(4, 2, 18, .96)"); g.addColorStop(1, "rgba(4, 2, 18, 0)");
  ctx2d.fillStyle = g; ctx2d.fillRect(x, y, size, fyT);
  g = ctx2d.createLinearGradient(0, y + size - fyB, 0, y + size);
  g.addColorStop(0, "rgba(2, 1, 8, 0)"); g.addColorStop(1, "rgba(2, 1, 8, .97)");
  ctx2d.fillStyle = g; ctx2d.fillRect(x, y + size - fyB, size, fyB);
  g = ctx2d.createLinearGradient(x, 0, x + fx, 0);
  g.addColorStop(0, "rgba(5, 3, 20, .94)"); g.addColorStop(1, "rgba(5, 3, 20, 0)");
  ctx2d.fillStyle = g; ctx2d.fillRect(x, y, fx, size);
  g = ctx2d.createLinearGradient(x + size - fx, 0, x + size, 0);
  g.addColorStop(0, "rgba(5, 3, 20, 0)"); g.addColorStop(1, "rgba(5, 3, 20, .94)");
  ctx2d.fillStyle = g; ctx2d.fillRect(x + size - fx, y, fx, size);
}

/* ================= canvas: cảnh Đánh Boss ================= */
function drawBossScene(now, W, H, dt) {
  const b = bossState || { hp: 0, max_hp: 1, round: 1, alive: true, rage: 0, rage_max: 200, stun_left: 0 };
  const cx = W * 0.5;
  // giai đoạn biến hình theo tỉ lệ máu (khớp game.py): 0 thường, 1 rụng ăng-ten/hút khói,
  // 2 khói + 💢 + mắt đỏ, 3 nứt vỏ + 2 mắt đỏ + run rẩy
  const frac = Math.max(0, Math.min(1, b.hp / Math.max(1, b.max_hp)));
  const formStage = !b.alive ? 0 : frac > 0.75 ? 0 : frac > 0.5 ? 1 : frac > 0.25 ? 2 : 3;

  // Tàn Ảnh hiện tại; ảnh chưa nạp xong / thiếu file -> fallback vòng cổng + emoji
  const skinKey = b.skin || "tu";
  const artImg = bossArtImages[skinKey];
  const useArt = !!(artImg && artImg.complete && artImg.naturalWidth > 0);
  const artSize = W * 0.94;

  let bossX = cx;
  if (now < bossFx.shakeUntil) bossX += (Math.random() - 0.5) * W * 0.012;
  if (formStage === 3) bossX += (Math.random() - 0.5) * W * 0.005;  // mốc cuối: run lẩy bẩy
  let bossY;   // tâm thân boss (đuôi hàm dùng để canh số sát thương / đòn bay)
  let bossR;   // bán kính tham chiếu cho các lớp phủ quanh thân boss

  if (useArt) {
    bossY = H * 0.085 + artSize / 2 + Math.sin(now / 620) * H * 0.006;
    bossR = artSize / 2;
    // đấu trường tối + xích vàng nằm sau lưng boss; vòng ma thuật vẽ sau ảnh
    drawBossArena(now, W, H, cx);
    drawBossChains(W, H);
    // thân boss: ảnh Tàn Ảnh lớn hoà mép vào nền, vẫn bob / rung / nghiêng như cũ
    ctx2d.save();
    ctx2d.translate(bossX, bossY);
    if (!b.alive) { ctx2d.globalAlpha = 0.5; ctx2d.rotate(0.16); }
    else if (formStage >= 2) ctx2d.rotate(0.02);
    // quầng sáng (halo) tím-trắng nhạt ôm sau lưng ảnh: tách boss khỏi nền tối
    const haloR = artSize * 0.62;
    const halo = ctx2d.createRadialGradient(0, 0, 0, 0, 0, haloR);
    halo.addColorStop(0, "rgba(208, 202, 255, .24)");
    halo.addColorStop(0.55, "rgba(182, 172, 255, .10)");
    halo.addColorStop(1, "rgba(182, 172, 255, 0)");
    ctx2d.fillStyle = halo;
    ctx2d.fillRect(-haloR, -haloR, haloR * 2, haloR * 2);
    drawBossArt(artImg, -bossR, -bossR, artSize);
    // mốc 3: vết nứt vỏ chạy ngang thân boss (vẽ đè lên ảnh)
    if (formStage === 3 && b.alive) {
      ctx2d.strokeStyle = "rgba(8,4,18,.5)"; ctx2d.lineWidth = 2.5; ctx2d.lineCap = "round";
      const cracks = [
        [-0.78, -0.28, -0.34, 0.04, -0.56, 0.46],
        [0.22, -0.82, 0.44, -0.3, 0.3, 0.18],
        [0.52, 0.34, 0.86, 0.6],
      ];
      for (const c of cracks) {
        ctx2d.beginPath();
        ctx2d.moveTo(c[0] * bossR, c[1] * bossR);
        ctx2d.lineTo(c[2] * bossR, c[3] * bossR);
        if (c.length > 4) ctx2d.lineTo(c[4] * bossR, c[5] * bossR);
        ctx2d.stroke();
      }
    }
    // bánh răng tiến hóa theo vòng (2 -> tối đa 5) viền mép trên của ảnh;
    // mốc 1 rụng còn đúng 1 chiếc (cơ chế "rụng răng" giữ nguyên trên ảnh)
    let gearCount = Math.min(2 + Math.floor((b.round || 1) / 2), 5);
    if (formStage === 1) gearCount = 1;
    if (!b.alive) gearCount = Math.min(gearCount, 2);
    ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
    for (let i = 0; i < gearCount; i++) {
      const ang = -Math.PI / 2 + (i - (gearCount - 1) / 2) * 0.42;
      ctx2d.save();
      ctx2d.translate(Math.cos(ang) * bossR * 0.93, Math.sin(ang) * bossR * 0.93);
      ctx2d.rotate((now / 900) * (i % 2 ? -1 : 1));
      ctx2d.font = `${H * (0.036 + (i % 2) * 0.008)}px serif`;
      ctx2d.fillText("⚙️", 0, 0);
      ctx2d.restore();
    }
    // mắt đỏ phát sáng mốc >= 2: quầng đỏ mềm đúng vị trí mắt trong ảnh
    if (b.alive && formStage >= 2) {
      const eyes = BOSS_ART_EYES[skinKey] || BOSS_ART_EYES.tu;
      for (const [ex, ey] of eyes) {
        const gx = (ex - 0.5) * artSize, gy = (ey - 0.5) * artSize, gr = artSize * 0.085;
        const eg = ctx2d.createRadialGradient(gx, gy, 0, gx, gy, gr);
        eg.addColorStop(0, "rgba(255,64,54,.5)");
        eg.addColorStop(0.45, "rgba(255,45,45,.22)");
        eg.addColorStop(1, "rgba(255,45,45,0)");
        ctx2d.fillStyle = eg;
        ctx2d.beginPath(); ctx2d.arc(gx, gy, gr, 0, Math.PI * 2); ctx2d.fill();
      }
    }
    ctx2d.restore();
    // vòng ma thuật ôm chân ảnh (vẽ trên quầng mép dưới của ảnh mới rõ)
    drawMagicCircle(now, W, H, cx, H * 0.085 + artSize + H * 0.014);
  } else {
    // ===== fallback khi không có ảnh: sân cỏ + vòng cổng + emoji như bản cũ =====
    const gnd = ctx2d.createLinearGradient(0, H * 0.55, 0, H);
    gnd.addColorStop(0, "#9ed07e"); gnd.addColorStop(1, "#67a24b");
    ctx2d.fillStyle = gnd; ctx2d.fillRect(0, H * 0.55, W, H * 0.45);
    ctx2d.fillStyle = "rgba(146, 104, 58, .45)";
    ctx2d.beginPath(); ctx2d.ellipse(W * 0.5, H * 0.81, W * 0.47, H * 0.125, 0, 0, Math.PI * 2); ctx2d.fill();

    bossY = H * 0.46 + Math.sin(now / 620) * H * 0.006;
    const portalR = H * 0.165;
    bossR = portalR;
    ctx2d.save();
    ctx2d.translate(bossX, bossY);
    if (!b.alive) { ctx2d.globalAlpha = 0.5; ctx2d.rotate(0.16); }
    else if (formStage >= 2) ctx2d.rotate(0.03);
    // vòng cổng đấu trường tím đậm + viền vàng sau lưng boss:
    // emoji chuột vốn xám nhạt, không có vòng này là boss chìm vào nền trời
    const portal = ctx2d.createRadialGradient(0, 0, portalR * 0.15, 0, 0, portalR);
    portal.addColorStop(0, "rgba(74, 42, 128, .95)");
    portal.addColorStop(0.8, "rgba(46, 24, 84, .94)");
    portal.addColorStop(1, "rgba(32, 16, 60, .92)");
    ctx2d.fillStyle = portal;
    ctx2d.beginPath(); ctx2d.arc(0, 0, portalR, 0, Math.PI * 2); ctx2d.fill();
    ctx2d.lineWidth = H * 0.0055; ctx2d.strokeStyle = "rgba(255, 211, 77, .95)";
    ctx2d.beginPath(); ctx2d.arc(0, 0, portalR, 0, Math.PI * 2); ctx2d.stroke();
    ctx2d.lineWidth = H * 0.002; ctx2d.strokeStyle = "rgba(255, 211, 77, .35)";
    ctx2d.beginPath(); ctx2d.arc(0, 0, portalR * 1.1, 0, Math.PI * 2); ctx2d.stroke();
    // mốc 3: vết nứt vỏ chạy ngang vòng cổng
    if (formStage === 3 && b.alive) {
      ctx2d.strokeStyle = "rgba(8,4,18,.55)"; ctx2d.lineWidth = 2.5; ctx2d.lineCap = "round";
      const cracks = [
        [-0.78, -0.28, -0.34, 0.04, -0.56, 0.46],
        [0.22, -0.82, 0.44, -0.3, 0.3, 0.18],
        [0.52, 0.34, 0.86, 0.6],
      ];
      for (const c of cracks) {
        ctx2d.beginPath();
        ctx2d.moveTo(c[0] * portalR, c[1] * portalR);
        ctx2d.lineTo(c[2] * portalR, c[3] * portalR);
        if (c.length > 4) ctx2d.lineTo(c[4] * portalR, c[5] * portalR);
        ctx2d.stroke();
      }
    }
    // bánh răng tiến hóa theo vòng (2 -> tối đa 5); mốc 1 rụng còn đúng 1 chiếc
    let gearCount = Math.min(2 + Math.floor((b.round || 1) / 2), 5);
    if (formStage === 1) gearCount = 1;
    if (!b.alive) gearCount = Math.min(gearCount, 2);
    ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
    for (let i = 0; i < gearCount; i++) {
      const ang = -Math.PI / 2 + (i - (gearCount - 1) / 2) * 0.46;
      ctx2d.save();
      ctx2d.translate(Math.cos(ang) * portalR * 0.84, Math.sin(ang) * portalR * 0.84);
      ctx2d.rotate((now / 900) * (i % 2 ? -1 : 1));
      ctx2d.font = `${H * (0.036 + (i % 2) * 0.008)}px serif`;
      ctx2d.fillText("⚙️", 0, 0);
      ctx2d.restore();
    }
    ctx2d.font = `${H * 0.29}px serif`;
    ctx2d.fillText("🐭", 0, portalR * 0.06);
    // mắt đỏ phát sáng: mốc 2 = 1 mắt trái, mốc 3 = cả 2 mắt
    if (b.alive && formStage >= 2) {
      ctx2d.save();
      ctx2d.fillStyle = "rgba(255,45,45,.9)";
      ctx2d.shadowColor = "#ff2d2d"; ctx2d.shadowBlur = 14;
      const eyeY = -H * 0.052, eyeDx = H * 0.029, eyeR = H * 0.0075;
      ctx2d.beginPath(); ctx2d.arc(-eyeDx, eyeY, eyeR, 0, Math.PI * 2); ctx2d.fill();
      if (formStage >= 3) {
        ctx2d.beginPath(); ctx2d.arc(eyeDx, eyeY, eyeR, 0, Math.PI * 2); ctx2d.fill();
      }
      ctx2d.restore();
    }
    ctx2d.restore();
  }
  ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
  // tiến hóa qua vòng: vòng >= 3 đội vương miện, vòng >= 5 thêm chỏm đỏ
  if (b.alive && (b.round || 1) >= 3) {
    ctx2d.font = `${H * 0.05}px serif`;
    ctx2d.fillText("👑", bossX, bossY - bossR - H * 0.032);
  }
  if (b.alive && (b.round || 1) >= 5) {
    ctx2d.font = `${H * 0.03}px serif`;
    ctx2d.fillText("🔴", bossX + H * 0.052, bossY - bossR - H * 0.02);
  }
  // khói bốc theo mốc: mốc 1 thưa thớt, mốc 2 vừa, mốc 3 dày đặc
  if (b.alive && formStage >= 1) {
    const puffs = formStage === 1 ? 1 : formStage === 2 ? 2 : 3;
    ctx2d.font = `${H * 0.04}px serif`;
    for (let i = 0; i < puffs; i++) {
      const ph = ((now / (formStage === 3 ? 620 : 1050)) + i * 0.37) % 1;
      ctx2d.save();
      ctx2d.globalAlpha = 0.7 * (1 - ph);
      if (useArt) {
        // có ảnh: khói bốc từ chân ảnh, bay lên dọc thân boss
        ctx2d.fillText("💨", bossX + artSize * 0.30 + i * H * 0.022, bossY + artSize * 0.30 - ph * H * 0.07);
      } else {
        ctx2d.fillText("💨", bossX + bossR * 0.42 + i * H * 0.022, bossY - bossR * (0.72 + ph * 0.5));
      }
      ctx2d.restore();
    }
  }
  if (b.alive && formStage >= 2) {
    ctx2d.font = `${H * 0.045}px serif`;
    if (useArt) ctx2d.fillText("💢", bossX - artSize * 0.42, bossY - artSize * 0.40);
    else ctx2d.fillText("💢", bossX - bossR * 0.8, bossY - bossR * 0.84);
  }
  // chớp sáng trắng-tím khi boss đổi Tàn Ảnh (hồi sinh vòng mới / đổi tuỳ chọn)
  if (now < (bossFx.skinFlashUntil || 0) && b.alive) {
    const k = Math.max(0, (bossFx.skinFlashUntil - now) / 300);
    const sg = ctx2d.createRadialGradient(bossX, bossY, 0, bossX, bossY, bossR * 1.08);
    sg.addColorStop(0, `rgba(238, 230, 255, ${0.5 * k})`);
    sg.addColorStop(1, "rgba(180, 140, 255, 0)");
    ctx2d.fillStyle = sg;
    ctx2d.beginPath(); ctx2d.arc(bossX, bossY, bossR * 1.08, 0, Math.PI * 2); ctx2d.fill();
  }
  // chớp đỏ phủ lên boss khi trúng đòn (vẽ sau thân boss mới thấy được)
  if (now < bossFx.flashUntil && b.alive) {
    ctx2d.save();
    ctx2d.globalAlpha = 0.30 * Math.max(0, (bossFx.flashUntil - now) / 220);
    ctx2d.fillStyle = "#ff3b30";
    if (useArt) {
      // có ảnh: chớp mềm hình tròn giữa ảnh, tan dần ra mép
      const fg = ctx2d.createRadialGradient(bossX, bossY, 0, bossX, bossY, bossR * 0.98);
      fg.addColorStop(0, "rgba(255,59,48,.85)");
      fg.addColorStop(1, "rgba(255,59,48,0)");
      ctx2d.fillStyle = fg;
    }
    ctx2d.beginPath(); ctx2d.arc(bossX, bossY, bossR * 0.95, 0, Math.PI * 2); ctx2d.fill();
    ctx2d.restore();
  }
  if (!b.alive) {
    ctx2d.font = `${H * 0.05}px serif`;
    ctx2d.fillText("💫", bossX, bossY - bossR * 0.95);
  } else if ((b.stun_left || 0) > 0) {
    const a = now / 300;
    ctx2d.font = `${H * 0.045}px serif`;
    ctx2d.fillText("💫", bossX + Math.cos(a) * bossR * 0.55, bossY - bossR * 0.98 + Math.sin(a) * H * 0.012);
    ctx2d.fillStyle = "#fff";
    ctx2d.font = `800 ${H * 0.016}px sans-serif`;
    ctx2d.fillText(`CHOÁNG ${b.stun_left}s — cào đau x2!`, bossX, bossY - bossR - H * 0.038);
  }

  // dọn hiệu ứng đã cũ
  bossFx.attacks = bossFx.attacks.filter((a) => now - a.t0 < 600);
  bossFx.numbers = bossFx.numbers.filter((n) => now - n.t0 < 1100);

  // đoàn mèo trợ trận (quà >= 100 kim cương): bầy mèo vây quanh boss
  if (now < bossFx.swarmUntil && b.alive) {
    ctx2d.font = `${H * 0.05}px serif`;
    for (let i = 0; i < 7; i++) {
      const a = (i / 7) * Math.PI * 2 + now / 240;
      const rx = bossX + Math.cos(a) * bossR * (useArt ? 1.06 : 0.88);
      const ry = bossY + Math.sin(a) * bossR * (useArt ? 0.62 : 0.5) + Math.sin(now / 130 + i) * 4;
      ctx2d.fillText("🐱", rx, ry);
    }
  }

  // phản đòn quét đuôi: vệt cong quét ngang hàng mèo đầu + câu thoại
  const counterOn = now < bossFx.counterUntil && b.alive;
  const counterProg = counterOn ? 1 - (bossFx.counterUntil - now) / 1200 : 0;
  if (counterOn) {
    ctx2d.save();
    ctx2d.translate(bossX, bossY);
    ctx2d.strokeStyle = "rgba(146, 104, 58, .85)";
    ctx2d.lineWidth = H * 0.016; ctx2d.lineCap = "round";
    const a0 = Math.PI * (0.08 + counterProg * 0.35);
    ctx2d.beginPath(); ctx2d.arc(0, 0, bossR * (useArt ? 1.18 : 1.5), a0, a0 + Math.PI * 0.34); ctx2d.stroke();
    ctx2d.fillStyle = "#fff";
    ctx2d.font = `800 ${H * 0.016}px sans-serif`; ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
    ctx2d.fillText("Quét đuôi nè!", 0, bossR * (useArt ? 1.04 : 1.32));
    ctx2d.restore();
  }

  // mèo người xem: 2 hàng vòng cung trên sân cỏ, hướng lên boss
  const syncOn = (b.sync_left || 0) > 0 && b.alive;
  const all = [...players.values()].slice(0, 12);
  const s = H * 0.042;
  all.forEach((rec, idx) => {
    const row = Math.floor(idx / 6), col = idx % 6;
    let x = W * (0.16 + col * 0.136) + Math.sin(now / 1300 + rec.hue) * 3;
    let y = H * (0.675 + row * 0.10);
    const atk = bossFx.attacks.find((a) => a.uid === rec.data.unique_id);
    let lunge = 0;
    if (atk && atk.kind === "cao") {
      const prog = (now - atk.t0) / 480;
      if (prog >= 0 && prog <= 1) lunge = Math.sin(prog * Math.PI) * 0.55;
    }
    const drawX = x + (bossX - x) * lunge;
    let drawY = y + (bossY + H * 0.07 - y) * lunge;
    // bị quét đuôi: hàng đầu rung lắc choáng váng (chỉ hiệu ứng)
    if (counterOn && row === 0 && lunge === 0) {
      drawY += Math.sin((now - bossFx.counterT0) / 55 + col * 1.3) * H * 0.006 * (1 - counterProg);
    }
    const scale = (spotlight.uid === rec.data.unique_id && spotlight.until > now) ? 1.4 : 1;
    const dmg = bossDmgByUid.get(rec.data.unique_id);
    const rank = bossRankByUid.get(rec.data.unique_id);
    // đồng loạt đang bật: cả đội mèo phát hào quang vàng
    if (syncOn) {
      ctx2d.save();
      ctx2d.fillStyle = `rgba(255, 211, 77, ${0.3 + 0.14 * Math.sin(now / 160 + col)})`;
      ctx2d.beginPath(); ctx2d.ellipse(drawX, drawY + s * 0.12, s * 0.98, s * 0.52, 0, 0, Math.PI * 2); ctx2d.fill();
      ctx2d.restore();
    }
    drawCat(drawX, drawY, s, rec, now, scale, `${rank ? rank.icon + " " : ""}${rec.data.nickname}${dmg ? ` • ⚔️${dmg}` : ""}`);
    if (counterOn && row === 0 && counterProg < 0.85) {
      ctx2d.font = `${H * 0.028}px serif`; ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
      ctx2d.fillText("😵", drawX + s * 0.55, drawY - s * 1.8);
    }
    // tát cá: con cá bay từ mèo này lên boss
    if (atk && atk.kind === "tatca") {
      const prog = (now - atk.t0) / 480;
      if (prog >= 0 && prog <= 1) {
        const fx = x + (bossX - x) * prog;
        const fy = y + (bossY - y) * prog - Math.sin(prog * Math.PI) * H * 0.05;
        ctx2d.font = `${H * 0.05}px serif`;
        ctx2d.fillText("🐟", fx, fy);
      }
    }
    // vết cào khi mèo lao tới đỉnh điểm
    if (lunge > 0.82) {
      ctx2d.font = `${H * 0.055}px serif`;
      ctx2d.fillText("💥", bossX + (Math.random() - 0.5) * H * 0.05, bossY - H * 0.03);
    }
  });

  // đòn không cần vị trí người đánh: chân mèo vả + mưa cá dội boss
  for (const atk of bossFx.attacks) {
    const prog = (now - atk.t0) / 480;
    if (prog < 0 || prog > 1) continue;
    if (atk.kind === "va") {
      ctx2d.save();
      ctx2d.translate(bossX, bossY - H * 0.02);
      const sc = 1 + Math.sin(prog * Math.PI) * 0.7;
      ctx2d.scale(sc, sc);
      ctx2d.font = `${H * 0.115}px serif`;
      ctx2d.fillText("🐾", 0, 0);
      ctx2d.restore();
    } else if (atk.kind === "mua_ca") {
      ctx2d.font = `${H * 0.045}px serif`;
      for (let i = 0; i < 6; i++) {
        const fx = bossX + (((i * 67) % 170) - 85) / 1000 * H;
        const fy = bossY - H * 0.17 + prog * H * 0.17 + (i % 3) * 9;
        ctx2d.fillText("🐟", fx, fy);
      }
    }
  }

  // số sát thương bay lên khỏi boss
  ctx2d.save();
  ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
  for (const n of bossFx.numbers) {
    const prog = (now - n.t0) / 1100;
    ctx2d.globalAlpha = 1 - prog;
    ctx2d.font = `900 ${H * (n.big ? 0.034 : 0.024)}px sans-serif`;
    ctx2d.fillStyle = n.big ? "#ffd34d" : "#ff5252";
    ctx2d.strokeStyle = "rgba(20,10,0,.6)"; ctx2d.lineWidth = 3;
    const nx = bossX + n.dx * W, ny = bossY - H * 0.1 - prog * H * 0.07;
    ctx2d.strokeText(`-${n.val}`, nx, ny);
    ctx2d.fillText(`-${n.val}`, nx, ny);
  }
  ctx2d.restore();

  // chó đuổi theo khi có follow (giữ như bản chạy)
  ctx2d.font = `${H * 0.045}px serif`;
  for (let i = dogs.length - 1; i >= 0; i--) {
    const dog = dogs[i];
    dog.x += dt * 0.16;
    if (dog.x > 1.1 || dog.until < now) { dogs.splice(i, 1); continue; }
    ctx2d.fillText("🐕", dog.x * W, H * 0.79);
  }
}

let lastFrame = performance.now();
function draw(now) {
  const dt = Math.min(0.05, (now - lastFrame) / 1000);
  lastFrame = now;
  const W = canvas.width, H = canvas.height;
  worldOffset += dt * 55;

  // trời + mây + đồi
  const sky = ctx2d.createLinearGradient(0, 0, 0, H * 0.55);
  sky.addColorStop(0, "#7ecbf2"); sky.addColorStop(1, "#dff6ff");
  ctx2d.fillStyle = sky; ctx2d.fillRect(0, 0, W, H * 0.56);
  ctx2d.fillStyle = "rgba(255,255,255,.9)";
  for (let i = 0; i < 5; i++) {
    const cx = ((i * 0.23 + 0.08) * W - (worldOffset * 0.12) % (W * 1.3) + W * 1.3) % (W * 1.3) - W * 0.15;
    const cy = H * (0.05 + (i % 3) * 0.045);
    ctx2d.beginPath();
    ctx2d.ellipse(cx, cy, W * 0.055, H * 0.016, 0, 0, Math.PI * 2);
    ctx2d.ellipse(cx + W * 0.035, cy + 3, W * 0.04, H * 0.012, 0, 0, Math.PI * 2);
    ctx2d.fill();
  }
  ctx2d.fillStyle = "#a8d89a";
  ctx2d.beginPath();
  ctx2d.ellipse(W * 0.15 - (worldOffset * 0.25) % (W * 0.9), H * 0.575, W * 0.34, H * 0.075, 0, Math.PI, 0);
  ctx2d.ellipse(W * 0.85 - (worldOffset * 0.25) % (W * 0.9), H * 0.575, W * 0.3, H * 0.06, 0, Math.PI, 0);
  ctx2d.fill();

  // chế độ Đánh Boss dùng cảnh riêng (trời/mây/đồi dùng chung ở trên)
  if (stageMode === "boss") {
    drawBossScene(now, W, H, dt);
    requestAnimationFrame(draw);
    return;
  }

  // hồ sen (phong cách ảnh Kitzy)
  ctx2d.fillStyle = "#57b7e8"; ctx2d.fillRect(0, H * 0.575, W, H * 0.07);
  ctx2d.fillStyle = "#3f9e63";
  for (let i = 0; i < 9; i++) {
    const lx = ((i * 0.14 + 0.04) * W - worldOffset % (W * 0.14) + W * 0.14) % (W * 1.1) - W * 0.05;
    ctx2d.beginPath(); ctx2d.ellipse(lx, H * 0.605 + (i % 3) * H * 0.014, W * 0.045, H * 0.011, 0, 0, Math.PI * 2); ctx2d.fill();
  }

  // đường chạy
  const trackTop = H * 0.645, trackH = H * 0.22;
  ctx2d.fillStyle = "#e07850"; ctx2d.fillRect(0, trackTop, W, trackH);
  ctx2d.strokeStyle = "rgba(255,255,255,.55)"; ctx2d.lineWidth = 2; ctx2d.setLineDash([26, 30]);
  ctx2d.lineDashOffset = -worldOffset * 1.6;
  for (let lane = 1; lane < 4; lane++) {
    ctx2d.beginPath(); ctx2d.moveTo(0, trackTop + (trackH / 4) * lane); ctx2d.lineTo(W, trackTop + (trackH / 4) * lane); ctx2d.stroke();
  }
  ctx2d.setLineDash([]);

  // đường xe phía dưới
  const roadTop = H * 0.865;
  ctx2d.fillStyle = "#4b4f57"; ctx2d.fillRect(0, roadTop, W, H - roadTop);
  ctx2d.strokeStyle = "#ffd34d"; ctx2d.lineWidth = 4; ctx2d.setLineDash([40, 34]);
  ctx2d.lineDashOffset = worldOffset * 2.2;
  ctx2d.beginPath(); ctx2d.moveTo(0, roadTop + (H - roadTop) / 2); ctx2d.lineTo(W, roadTop + (H - roadTop) / 2); ctx2d.stroke();
  ctx2d.setLineDash([]);
  ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
  for (const car of cars) {
    car.x -= car.speed * dt;
    if (car.x < -0.08) { car.x = 1.05; car.row = Math.floor(Math.random() * 2); }
    ctx2d.font = `${H * 0.042}px serif`;
    ctx2d.fillText(car.emoji, car.x * W, roadTop + (H - roadTop) * (car.row === 0 ? 0.28 : 0.74));
  }

  // chó đuổi theo (follow)
  ctx2d.font = `${H * 0.045}px serif`;
  for (let i = dogs.length - 1; i >= 0; i--) {
    const dog = dogs[i];
    dog.x += dt * 0.16;
    if (dog.x > 1.1 || dog.until < now) { dogs.splice(i, 1); continue; }
    ctx2d.fillText("🐕", dog.x * W, trackTop + trackH * 0.86);
  }

  // mèo: tối đa 24 bé hiện trên đường (ưu tiên đang chạy + nhiều km)
  const all = [...players.values()];
  const visible = all
    .sort((a, b) => Number(b.data.in_team) - Number(a.data.in_team) || (b.data.distance_km || 0) - (a.data.distance_km || 0))
    .slice(0, 18);
  const s = H * 0.05;
  let waitIdx = 0;
  visible.forEach((rec, idx) => {
    const p = rec.data;
    if (spotlight.uid === p.unique_id && spotlight.until > now) return; // vẽ riêng ở spotlight
    const lane = (p.seat || idx) % 4;
    const y = trackTop + (trackH / 4) * lane + trackH * 0.17;
    let x;
    if (p.in_team) {
      x = W * (0.38 + ((p.seat * 23) % 54) / 100) + Math.sin(now / 1100 + rec.hue) * 5;
      if (p.speed_mode === "boost") x += W * 0.03;
    } else {
      // Khu chờ: xếp hàng ngang ở nửa phải đường chạy, không chui sau panel
      x = W * (0.42 + (waitIdx % 6) * 0.088);
      waitIdx++;
    }
    drawCat(x, y, s, rec, now, 1);
  });

  // spotlight quà: mèo được tặng quà lên giữa sân khấu, vòng sáng (kiểu Chùa An Lạc)
  if (spotlight.uid && spotlight.until > now) {
    const rec = players.get(spotlight.uid);
    if (rec) {
      const cx = W * 0.55, cy = trackTop + trackH * 0.52;
      ctx2d.save();
      ctx2d.strokeStyle = "#ffd34d"; ctx2d.lineWidth = 5;
      ctx2d.shadowColor = "#ffd34d"; ctx2d.shadowBlur = 26;
      ctx2d.beginPath(); ctx2d.ellipse(cx, cy + s * 0.5, s * 1.35, s * 0.42, 0, 0, Math.PI * 2); ctx2d.stroke();
      ctx2d.restore();
      drawCat(cx, cy, s, rec, now, 1.65);
    }
  }

  requestAnimationFrame(draw);
}
requestAnimationFrame(draw);

/* ================= xử lý sự kiện ================= */
function handle(msg) {
  if (msg.speak) {
    if (msg.speak_priority === 0) tts.speakNow(msg.speak);
    else tts.push(msg.speak, msg.speak_priority ?? 4);
  }
  switch (msg.type) {
    case "config":
      // Tên kênh không còn hiện trên sân khấu theo yêu cầu chủ kênh (chỉ dùng cho giọng đọc)
      if (msg.stage_mode) setStageMode(msg.stage_mode);
      if (msg.tts_voice) tts.voice = msg.tts_voice;
      if (msg.tts_engine) tts.engine = msg.tts_engine;
      if (typeof msg.tts_rate === "number") tts.rate = msg.tts_rate;
      if (typeof msg.tts_pitch === "number") tts.pitch = msg.tts_pitch;
      if (typeof msg.meow_enabled === "boolean") meow.enabled = msg.meow_enabled;
      break;
    case "snapshot": renderSnapshot(msg); break;
    case "welcome_audio": tts.pushFile(msg.url, 1); break;
    case "speak": tts.speakNow(msg.text); break;
    case "spawn": {
      const rec = upsertPlayer(msg.player);
      ticker(`🐱 ${msg.player.nickname} vừa nhận một bé mèo! Gõ "chạy" để vào đội nha`);
      logEvent(`🐱 ${msg.player.nickname} vào nhà Bug`);
      meow.playSpawn();
      break;
    }
    case "chat": { const rec = upsertPlayer(msg.player); setBubble(rec, msg.bubble); break; }
    case "pet": {
      const rec = upsertPlayer(msg.player);
      rec.jumpUntil = performance.now() + 650;
      setBubble(rec, msg.bubble || "Meow! 🐾");
      meow.play("normal");
      break;
    }
    case "jump": { const rec = upsertPlayer(msg.player); rec.jumpUntil = performance.now() + 650; break; }
    case "run_join":
      upsertPlayer(msg.player);
      ticker(msg.message); logEvent(msg.message);
      break;
    case "run_boost": {
      const rec = upsertPlayer(msg.player);
      setBubble(rec, "⚡ Chạy nhanh!");
      ticker(msg.message); logEvent(msg.message);
      break;
    }
    case "run_slow": ticker(msg.message); logEvent(msg.message); break;
    case "run_surge": upsertPlayer(msg.player); break;
    case "rank": {
      const rec = upsertPlayer(msg.player);
      setBubble(rec, `🏆 Hạng ${msg.rank} • ${(msg.player.distance_km || 0).toFixed(2)}km`, 5000);
      break;
    }
    case "feed": {
      const rec = upsertPlayer(msg.player);
      setBubble(rec, "🥣 Ngon quá!");
      ticker(`🥣 ${msg.player.nickname} cho Bug ăn (+5⭐)`);
      logEvent(`🥣 ${msg.player.nickname} cho Bug ăn`);
      meow.play("happy");
      if (typeof msg.bug_satiety === "number") renderSnapshot({ bug_satiety: msg.bug_satiety });
      break;
    }
    case "feed_blocked": ticker("⏳ " + msg.message); break;
    case "likes": renderSnapshot(msg); break;
    case "rain": rain(msg.kind, msg.seconds || 30); ticker("🌧️🐟 MƯA CÁ! Cả nhà hứng cá nào!"); logEvent("🌧️🐟 Mưa cá!"); break;
    case "gift": {
      const rec = upsertPlayer(msg.player);
      const d = msg.diamond_count || 1;
      rec.mount = d >= 50 ? "🦖" : d >= 10 ? "🛵" : "🛒";
      rec.mountUntil = performance.now() + 20000;
      spotlight = { uid: msg.player.unique_id, until: performance.now() + 6000 };
      ticker(`🎁 ${msg.player.nickname} tặng ${msg.gift_name} — lên sân khấu & cưỡi ${rec.mount}!`);
      logEvent(`🎁 ${msg.player.nickname} tặng ${msg.gift_name}`);
      meow.play("happy");
      rain("fish", 6);
      break;
    }
    case "follow":
      upsertPlayer(msg.player);
      dogs.push({ x: -0.06, until: performance.now() + 12000 });
      ticker(`🐕 ${msg.player.nickname} vừa follow — Bug đuổi theo đội chạy!`);
      logEvent(`🔔 ${msg.player.nickname} follow`);
      break;
    case "share": logEvent(`🔁 ${msg.player.nickname} chia sẻ live`); break;
    case "race_join": ticker(`🏁 ${msg.player.nickname} vào sảnh đua!`); break;
    case "race_info": ticker(msg.message || ""); break;
    case "race_finish":
      ticker(`🏆 ${msg.winner.nickname} THẮNG CUỘC ĐUA MÈO!`);
      meow.play("chorus");
      rain("fish", 8);
      break;
    case "status": ticker(msg.connected ? "✅ " + msg.message : "ℹ️ " + msg.message); break;
    case "boss_spawn":
      ticker("🐭 Chuột Trùm Răng Sắt mò tới trộm kho cá! Gõ CÀO để tấn công!");
      logEvent("🐭 Boss xuất hiện!");
      break;
    case "boss_taunt": {
      // Boss chửi lại: bong bóng thoại trên đầu boss ~4 giây (câu đọc do handle() xử lý qua msg.speak)
      const elT = $("bossTaunt");
      elT.textContent = "💬 " + msg.text;
      elT.classList.remove("hidden");
      clearTimeout(bossTauntTimer);
      bossTauntTimer = setTimeout(() => elT.classList.add("hidden"), 4000);
      break;
    }
    case "boss_sync": {
      const elS = $("bossSyncFlash");
      elS.classList.remove("hidden");
      clearTimeout(bossSyncTimer);
      bossSyncTimer = setTimeout(() => elS.classList.add("hidden"), 2500);
      ticker(`⚡ ĐÒN ĐỒNG LOẠT ×2 — ${msg.count} mèo cùng cào một lúc!`);
      logEvent(`⚡ Đồng loạt ×2 (${msg.count} mèo)`);
      meow.play("chorus");
      break;
    }
    case "boss_counter": {
      const nowC = performance.now();
      bossFx.counterT0 = nowC;
      bossFx.counterUntil = nowC + 1200;
      ticker("🐭💨 Răng Sắt quét đuôi phản đòn!");
      break;
    }
    case "rank_up": {
      const recR = msg.user ? players.get(msg.user) : null;
      if (recR) setBubble(recR, `⬆ ${msg.rank_title}!`, 4200);
      ticker(`🏅 ${msg.name} thăng hạng ${msg.rank_title}!`);
      logEvent(`🏅 ${msg.name} → ${msg.rank_title}`);
      meow.play("excited");
      break;
    }
    case "boss_attack": {
      const nowA = performance.now();
      if (msg.player) upsertPlayer(msg.player);
      bossFx.attacks.push({
        uid: msg.user || (msg.player && msg.player.unique_id) || "",
        kind: msg.kind, t0: nowA, damage: msg.damage || 0,
      });
      bossFx.numbers.push({
        val: msg.damage || 0, t0: nowA,
        dx: (Math.random() - 0.5) * 0.16,
        big: msg.kind === "doan" || msg.kind === "mua_ca",
      });
      bossFx.flashUntil = nowA + 220;
      bossFx.shakeUntil = nowA + 260;
      if (msg.kind === "doan") {
        bossFx.swarmUntil = nowA + 1500;
        ticker(`🐾 Đoàn mèo trợ trận của ${msg.name} xông lên! (-${msg.damage})`);
        logEvent(`🐾 ${msg.name} gọi đoàn mèo trợ trận (-${msg.damage})`);
        meow.play("chorus");
      } else if (msg.kind === "mua_ca") {
        ticker(`🌧️🐟 Mưa cá trút xuống boss! (-${msg.damage})`);
        logEvent(`🌧️🐟 Mưa cá dội boss (-${msg.damage})`);
      } else if (msg.kind === "va") {
        ticker(`🐾 ${msg.name} vả boss một phát! (-${msg.damage})`);
      }
      break;
    }
    case "boss_down":
      showBossDown(msg);
      ticker(`🎉 HẠ GỤC BOSS! Đòn cuối: ${msg.final_blow ? msg.final_blow.name : ""}`);
      logEvent(`🎉 Boss gục vòng ${msg.round}! Đòn cuối: ${msg.final_blow ? msg.final_blow.name : ""}`);
      meow.play("chorus");
      rain("fish", 8);
      break;
    case "boss_respawn":
      bossBannerMode = "";
      $("bossBanner").classList.add("hidden");
      ticker(`🐭 Boss hồi sinh vòng ${msg.round}${msg.skin_name ? ` — hiện hình ${msg.skin_name}` : ""} — máu ${msg.max_hp}!`);
      logEvent(`🐭 Boss hồi sinh vòng ${msg.round}${msg.skin_name ? ` (${msg.skin_name})` : ""}`);
      break;
  }
}

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onmessage = (ev) => { try { handle(JSON.parse(ev.data)); } catch (e) { /* bỏ qua gói lỗi */ } };
  ws.onclose = () => setTimeout(connect, 2000);
}
connect();
