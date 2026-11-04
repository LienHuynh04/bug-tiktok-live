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
/* ================= nhạc nền: giai điệu "đào vàng" tổng hợp bằng Web Audio =================
   Nhạc gốc soạn trong code (không dùng file / không vay giai điệu game nào):
   điệu pluck vui nhộn tông C major ~112 BPM — lead triangle + bass square +
   hat noise. Chạy khi âm thanh đã mở khoá VÀ music_enabled; giọng đọc cất
   lên thì nhạc tự nhỏ xuống 30% (ducking), đọc xong lại to như cũ. */
const music = {
  enabled: true, volume: 50, playing: false, ducked: false,
  ctx: null, bus: null, timer: null, nextTime: 0, step: 0,
  STEP_DUR: 60 / 112 / 2, // 1 nốt móc đơn ở 112 BPM
  // 8 ô nhịp x 8 nốt móc đơn (số MIDI, 0 = nghỉ) — giai điệu gốc vui tươi
  MELODY: [
    72, 76, 79, 76, 81, 79, 76, 72, // C
    74, 79, 74, 79, 83, 79, 74, 71, // G
    69, 72, 76, 72, 81, 76, 72, 69, // Am
    77, 81, 77, 81, 79, 76, 74, 72, // F
    72, 76, 79, 76, 81, 79, 81, 84, // C
    83, 79, 74, 79, 81, 79, 74, 71, // G
    77, 81, 84, 81, 79, 76, 74, 71, // F
    72, 76, 79, 84, 79, 76, 72, 0,  // C
  ],
  BASS_ROOTS: [48, 43, 45, 41, 48, 43, 41, 48], // C G Am F C G F C (MIDI)
  _freq(midi) { return 440 * Math.pow(2, (midi - 69) / 12); },
  _level() { return (this.volume / 100) * 0.24 * (this.ducked ? 0.3 : 1); },
  _applyGain() {
    if (!this.bus || !this.ctx) return;
    this.bus.gain.setTargetAtTime(this.playing ? this._level() : 0, this.ctx.currentTime, 0.09);
  },
  _ensureGraph() {
    const ctx = this.ctx;
    if (!ctx || this.bus) return;
    this.bus = ctx.createGain();
    this.bus.gain.value = 0;
    this.bus.connect(ctx.destination);
    // bộ đệm noise dùng chung cho tiếng hat
    const len = Math.floor(ctx.sampleRate * 0.06);
    this._noiseBuf = ctx.createBuffer(1, len, ctx.sampleRate);
    const data = this._noiseBuf.getChannelData(0);
    for (let i = 0; i < len; i++) data[i] = Math.random() * 2 - 1;
  },
  _pluck(midi, t, vol) {
    const ctx = this.ctx;
    const osc = ctx.createOscillator();
    const g = ctx.createGain();
    const flt = ctx.createBiquadFilter();
    osc.type = "triangle";
    osc.frequency.value = this._freq(midi);
    flt.type = "lowpass"; flt.frequency.value = 2600;
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(vol, t + 0.012);
    g.gain.exponentialRampToValueAtTime(0.0001, t + this.STEP_DUR * 0.95);
    osc.connect(flt); flt.connect(g); g.connect(this.bus);
    osc.start(t); osc.stop(t + this.STEP_DUR + 0.05);
  },
  _bass(midi, t, vol) {
    const ctx = this.ctx;
    const osc = ctx.createOscillator();
    const g = ctx.createGain();
    const flt = ctx.createBiquadFilter();
    osc.type = "square";
    osc.frequency.value = this._freq(midi);
    flt.type = "lowpass"; flt.frequency.value = 480;
    const dur = this.STEP_DUR * 1.9;
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(vol, t + 0.015);
    g.gain.setValueAtTime(vol, t + dur * 0.6);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    osc.connect(flt); flt.connect(g); g.connect(this.bus);
    osc.start(t); osc.stop(t + dur + 0.05);
  },
  _hat(t, vol) {
    const ctx = this.ctx;
    const src = ctx.createBufferSource();
    src.buffer = this._noiseBuf;
    const bp = ctx.createBiquadFilter();
    bp.type = "bandpass"; bp.frequency.value = 7200; bp.Q.value = 0.8;
    const g = ctx.createGain();
    g.gain.setValueAtTime(vol, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.05);
    src.connect(bp); bp.connect(g); g.connect(this.bus);
    src.start(t); src.stop(t + 0.07);
  },
  _scheduleStep(step, t) {
    const mel = this.MELODY[step];
    if (mel) this._pluck(mel, t, 0.5);
    const bar = Math.floor(step / 8), inBar = step % 8;
    if (inBar === 0 || inBar === 4) this._bass(this.BASS_ROOTS[bar], t, 0.30);
    if (inBar === 6) this._bass(this.BASS_ROOTS[bar] + 7, t, 0.20);
    if (inBar % 2 === 1) this._hat(t, 0.10);
    else if (inBar === 0) this._hat(t, 0.05);
  },
  start() {
    if (this.playing || !this.enabled || !audioGate.unlocked) return;
    const ctx = meow.ctx;
    if (!ctx || ctx.state !== "running") return;
    this.ctx = ctx;
    this._ensureGraph();
    this.playing = true;
    this.step = 0;
    this.nextTime = ctx.currentTime + 0.08;
    this._applyGain();
    this.timer = setInterval(() => {
      if (!this.playing) return;
      while (this.nextTime < this.ctx.currentTime + 0.28) {
        this._scheduleStep(this.step, this.nextTime);
        this.step = (this.step + 1) % this.MELODY.length;
        this.nextTime += this.STEP_DUR;
      }
    }, 90);
  },
  stop() {
    this.playing = false;
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
    this._applyGain();
  },
  setEnabled(v) {
    this.enabled = !!v;
    if (this.enabled) this.start();
    else this.stop();
  },
  setVolume(v) {
    this.volume = Math.max(0, Math.min(100, Number(v) || 0));
    this._applyGain();
  },
};
// ducking: giọng đọc đang phát thì nhạc lùi về 30%
setInterval(() => {
  const d = !!tts.speaking;
  if (d !== music.ducked) { music.ducked = d; music._applyGain(); }
}, 150);

/* ================= cổng âm thanh: tự mở khoá, không cần bấm nút =================
   Trình duyệt chặn autoplay có tiếng cho tới khi có tương tác — nên sân khấu
   tự thử mở khoá liên tục (load / quay lại tab / mỗi 3s / chạm phím đầu tiên).
   Mở được là: bật giọng đọc + chạy nhạc nền + ẩn pill cảnh báo mỏng. */
const audioGate = {
  unlocked: false,
  tryUnlock() {
    meow.unlock();
    const ctx = meow.ctx;
    if (!ctx) { this._pill(); return; }
    ctx.onstatechange = () => { if (ctx.state === "running") this.onUnlocked(); };
    try {
      // "tick" buffer im lặng để đánh thức pipeline âm thanh
      const src = ctx.createBufferSource();
      src.buffer = ctx.createBuffer(1, 1, ctx.sampleRate);
      src.connect(ctx.destination);
      src.start(0);
    } catch { /* bỏ qua */ }
    if (ctx.state === "running") this.onUnlocked();
    else if (ctx.resume) ctx.resume().then(() => { if (ctx.state === "running") this.onUnlocked(); }).catch(() => {});
    this._pill();
  },
  onUnlocked() {
    if (this.unlocked) return;
    this.unlocked = true;
    tts.enabled = true;
    this._pill();
    music.start();
  },
  _pill() {
    const pill = $("audioPill");
    if (pill) pill.classList.toggle("hidden", this.unlocked);
  },
};
window.addEventListener("load", () => audioGate.tryUnlock());
document.addEventListener("visibilitychange", () => { if (!document.hidden) audioGate.tryUnlock(); });
document.addEventListener("pointerdown", () => audioGate.tryUnlock());
document.addEventListener("keydown", () => audioGate.tryUnlock());
const audioRetryTimer = setInterval(() => {
  if (audioGate.unlocked) { clearInterval(audioRetryTimer); return; }
  audioGate.tryUnlock();
}, 3000);
audioGate._pill();

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
  if (mode !== "run" && mode !== "boss" && mode !== "garden" && mode !== "miner") return;
  stageMode = mode;
  $("stage").classList.toggle("boss-mode", mode === "boss");
  $("stage").classList.toggle("garden-mode", mode === "garden");
  $("stage").classList.toggle("miner-mode", mode === "miner");
  // nền boss tối sâu -> panel chuyển kính tối cho khỏi "nổi" lạc tông (chỉ boss)
  $("stage").classList.toggle("boss-dark", mode === "boss");
  // Banner hướng dẫn đổi ngay theo chế độ (không chờ vòng xoay 6s)
  guideIdx = 0;
  $("guideBanner").textContent = guideTextsFor(mode)[0];
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
function logEvent(text, hl = false) {
  const li = document.createElement("li");
  if (hl) li.className = "hl";
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

/* ================= chế độ Vườn Mèo ================= */
let gardenState = null;            // snapshot "garden" mới nhất từ server
let prevGardenHearts = 0;          // tim vườn ở snapshot trước (để bắn tim bay)
const gardenFx = {
  hearts: [],        // {x, y, t0} tim bay lên khi tim vườn tăng
  hopUntil: 0,       // cả đàn nhảy mừng (khi có share)
  scatterUntil: 0,   // cả đàn tản ra né (Bug cáu)
};

function updateGarden(s) {
  const g = s.garden;
  if (!g) return;
  // Tim vườn tăng -> bắn vài trái tim bay lên từ vị trí mèo ngẫu nhiên
  if (typeof g.hearts === "number" && g.hearts > prevGardenHearts && stageMode === "garden") {
    const recs = [...players.values()];
    const n = Math.min(6, Math.max(1, Math.round((g.hearts - prevGardenHearts) / 10)));
    for (let i = 0; i < n && recs.length; i++) {
      const rec = recs[Math.floor(Math.random() * recs.length)];
      if (rec.gx !== undefined) {
        gardenFx.hearts.push({ x: rec.gx, y: rec.gy - 60, t0: performance.now() });
      }
    }
  }
  if (typeof g.hearts === "number") prevGardenHearts = g.hearts;
  gardenState = g;
  const flags = [
    g.golden_hour_active ? "🌇 GIỜ VÀNG" : "",
    g.feast_active ? "🎉 BỮA TIỆC" : "",
    g.golden_present ? "👑 có Mèo Vàng" : "",
  ].filter(Boolean).join(" • ");
  $("gardenProgress").textContent =
    `❤️ ${g.hearts} / ${g.hearts_goal}${flags ? " — " + flags : ""}`;
  const top = s.garden_top || [];
  $("gardenTopList").innerHTML = top.length
    ? top.map((t, i) => `<li><span class="rname">${i + 1}. ${escapeHtml(t.name)} · ${escapeHtml(t.personality_name || "")}</span><span class="rkm">❤️ ${t.hearts}</span></li>`).join("")
    : `<li><span class="rname">Chưa có tim nào — thả tim nha!</span></li>`;
}

/* ================= chế độ Đào Vàng PK ================= */
let minerState = null;             // snapshot "miner" mới nhất từ server
let minerRoundEnd = null;          // sự kiện miner_round_end gần nhất (cho banner podium)
const MINER_TEAM_NAMES = { meo: "Mèo", chuot: "Chuột" };
const MINER_KIND_NAMES = {
  gold_s: "vàng nhỏ", gold_m: "vàng vừa", gold_l: "VÀNG TO", diamond: "KIM CƯƠNG",
  rock: "cục đá", bag: "TÚI VÀNG", bone: "cục xương",
};
// bán kính vật phẩm (khớp MINER_ITEMS ở game.py) — để vẽ vật đang được kéo ở đầu móc
const MINER_KIND_R = { gold_s: 0.028, gold_m: 0.042, gold_l: 0.060, diamond: 0.034, rock: 0.040, bag: 0.036, bone: 0.030 };
const MINER_PIVOTS = { meo: { x: 0.20, y: 0.145 }, chuot: { x: 0.80, y: 0.145 } }; // khớp MINER_PIVOTS
const MINER_REACH = 0.825; // khớp MINER_HOOK_REACH ở game.py
const minerFx = {
  floats: [],       // {team, val, t0} số "+vàng" bay lên ở giàn tời khi giật trúng
  bursts: [],       // {x, y, ang, spd, t0} tia lửa ở đầu móc khi móc chạm vật
  rocks: [],        // {x, y, vx, vy, rot, vr, t0} đá văng khi nổ mìn
  confetti: [],     // {x, y, vx, vy, rot, vr, col, t0} pháo giấy mừng đội thắng hiệp
  shakeUntil: 0,    // rung màn hình khi nổ mìn
  flashUntil: 0,    // chớp sáng ấm khi nổ mìn
  goldenGlow: { meo: false, chuot: false }, // dây móc phát sáng vàng khi Móc Vàng
};

// Đầu móc theo đúng công thức server: tip = pivot + len * 0.825 * (sin, cos)(góc)
function minerTipPx(team, W, H) {
  const piv = MINER_PIVOTS[team];
  const h = minerState && minerState.hooks ? minerState.hooks[team] : null;
  const rad = ((h ? h.angle || 0 : 0) * Math.PI) / 180;
  const reach = (h ? h.len || 0 : 0) * MINER_REACH;
  return {
    px: piv.x * W, py: piv.y * H,
    tx: (piv.x + reach * Math.sin(rad)) * W,
    ty: (piv.y + reach * Math.cos(rad)) * H,
  };
}

function minerHookText(h) {
  if (!h) return "đang đu…";
  if (h.state === "drop") return "đang thả móc!";
  if (h.state === "pull") return h.carrying_kind
    ? `đang kéo ${MINER_KIND_NAMES[h.carrying_kind] || "vật phẩm"}!`
    : "đang kéo tay không…";
  return "đang đu…";
}

function updateMiner(s) {
  minerState = s.miner;
  const m = minerState;
  if (!m) return;
  for (const team of ["meo", "chuot"]) {
    const h = m.hooks ? m.hooks[team] : null;
    // móc quay lại trạng thái đu = đợt kéo (kể cả Móc Vàng) đã xong -> tắt hào quang
    if (h && h.state === "swing") minerFx.goldenGlow[team] = false;
    const buff = m.buffs ? m.buffs[team] : null;
    const buffTxt = buff && buff.until > Date.now() / 1000 ? ` • ⚡ kéo ×${buff.mult}` : "";
    $(team === "meo" ? "minerStatusMeo" : "minerStatusChuot").textContent =
      `${team === "meo" ? "🐱" : "🐭"} Đội ${MINER_TEAM_NAMES[team]}: ${(m.members || {})[team] || 0} thợ • móc ${minerHookText(h)}${buffTxt}`;
  }
  const bp = m.blast_progress || { likes: 0, goal: 500 };
  $("minerBlast").textContent = `💥 Nổ mìn: ${bp.likes} / ${bp.goal}`;
  $("minerBlastGoal").textContent = bp.goal;
  $("minerBlastFill").style.width = Math.min(100, (bp.likes / Math.max(1, bp.goal)) * 100) + "%";
  const top = s.miner_top || [];
  $("minerTopList").innerHTML = top.length
    ? top.map((t, i) => `<li><span class="rname">${i + 1}. ${t.team === "chuot" ? "🐭" : "🐱"} ${escapeHtml(t.name)}</span><span class="rkm">${t.gold} 💰</span></li>`).join("")
    : `<li><span class="rname">Chưa có thợ nào — gõ "mèo"/"chuột" vào đội!</span></li>`;
  // banner chỉ hiện trong pha nghỉ giữa hiệp (podium)
  if (m.phase === "podium") {
    const e = minerRoundEnd;
    if (e && e.round === m.round) {
      $("minerBannerTitle").textContent = e.winner
        ? `🏆 ĐỘI ${MINER_TEAM_NAMES[e.winner].toUpperCase()} THẮNG HIỆP ${e.round}!`
        : `🤝 HIỆP ${e.round} HOÀ!`;
      $("minerBannerSub").innerHTML =
        `Tỉ số hiệp: 🐱 ${e.score_meo} — ${e.score_chuot} 🐭<br>` +
        (e.mvp_name ? `👑 Vua Đào Vàng: ${escapeHtml(e.mvp_name)} — ${e.mvp_gold} vàng`
          : "Chưa có ai đào được vàng hiệp này");
    } else {
      $("minerBannerTitle").textContent = `⏸️ HẾT HIỆP ${m.round}`;
      $("minerBannerSub").textContent = "Nghỉ giữa hiệp — hiệp mới sắp bắt đầu!";
    }
    $("minerBanner").classList.remove("hidden");
  } else {
    $("minerBanner").classList.add("hidden");
  }
}

function renderSnapshot(s) {
  if (s.stage_mode) setStageMode(s.stage_mode);
  if (s.boss) updateBoss(s.boss);
  if (s.garden) updateGarden(s);
  if (s.miner) updateMiner(s);
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
    $("bugFaceEmoji").textContent = hungry ? "😿" : "🐱";
    $("bugMood").textContent = hungry ? "đang đói — cả đội chậm 30%!" : s.bug_satiety > 70 ? "no căng, đang vui vẻ" : "đang vui vẻ";
    $("bugSub").textContent = hungry ? "⚠️ Bug đói rồi — gõ HẠT cho Bug ăn mau!" : "Độ no của Bug — gõ HẠT để cho ăn";
  }
  if (s.bug) applyBugMood(s.bug);
}

/* ---- Tâm trạng Bug: ngủ / khó chịu — huy hiệu + chữ trạng thái + hiệu ứng ----
   Ưu tiên hiển thị: đang ngủ > đang khó chịu > trạng thái theo độ no ở trên. */
let bugMoodState = "";
function applyBugMood(b) {
  const bar = $("bugBar"), badge = $("bugBadge"), face = $("bugFace");
  const state = b.sleeping ? "sleeping" : (b.annoyed ? "annoyed" : "");
  bar.classList.toggle("sleeping", state === "sleeping");
  bar.classList.toggle("annoyed", state === "annoyed");
  if (state === "sleeping") {
    badge.textContent = "💤";
    badge.classList.remove("hidden");
    $("bugMood").textContent = "đang ngủ 😴";
  } else if (state === "annoyed") {
    badge.textContent = "💢";
    badge.classList.remove("hidden");
    $("bugMood").textContent = "đang khó chịu 💢";
  } else {
    badge.classList.add("hidden");
  }
  if (state !== bugMoodState) {
    // Đổi trạng thái: khó chịu thì rung ảnh, còn lại thì nảy pop nhẹ
    const cls = state === "annoyed" ? "shake" : "pop";
    face.classList.remove("shake", "pop");
    void face.offsetWidth;
    face.classList.add(cls);
    setTimeout(() => face.classList.remove(cls), 650);
    bugMoodState = state;
  }
}

/* Bong bóng thoại nhỏ ngay trên thanh Bug cho các sự kiện tâm trạng */
let bugBubbleTimer = null;
function showBugBubble(text) {
  const el = $("bugBubble");
  el.textContent = text;
  el.classList.add("show");
  clearTimeout(bugBubbleTimer);
  bugBubbleTimer = setTimeout(() => el.classList.remove("show"), 3500);
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
  "🐾 Gõ CÀO để tấn công boss!",
  "5 mèo cùng \"cào\" trong 3 giây → ĐÒN ĐỒNG LOẠT x2! ⚡",
  "🔥 Thả tim nạp Nộ → mưa cá dội boss",
  "Boss choáng là lúc cào đau gấp đôi đó! 💫",
  "Gõ \"hạt\" cho Bug ăn lấy sức 🥣",
  "🏆 Đánh nhiều lên hạng mèo: Săn → Chiến → Tướng → Vương",
];
const GARDEN_GUIDE_TEXTS = [
  "🌿 Mỗi bé mèo một tính cách — chiều đúng ý là mèo vui!",
  "🍚 Gõ \"hạt\" gọi mèo ăn — Ham Ăn lao tới bát đầu tiên",
  "🧶 Gõ \"chơi\" rủ hội Tăng Động đuổi bóng",
  "💅 Khen \"xinh quá\" là Chảnh tạo dáng liền",
  "🐟 Gõ \"cá\" — Mê Cá chầu kho cá ngay",
  "❤️ Thả tim gom tim vườn — đủ 500 mở Bữa Tiệc Vườn!",
];
const MINER_GUIDE_TEXTS = [
  "⛏️ Gõ \"mèo\" hoặc \"chuột\" để vào đội đào vàng!",
  "🎯 Canh móc quét qua cục vàng to rồi gõ \"đào\"!",
  "💎 Kim cương 150 vàng — thấy là phải giật ngay!",
  "❤️ Thả tim đủ là NỔ MÌN phá đá, lộ vàng!",
  "🏆 Đào nhiều vàng nhất hiệp = Vua Đào Vàng!",
];
function guideTextsFor(mode) {
  return mode === "boss" ? BOSS_GUIDE_TEXTS
    : mode === "garden" ? GARDEN_GUIDE_TEXTS
    : mode === "miner" ? MINER_GUIDE_TEXTS : GUIDE_TEXTS;
}
let guideIdx = 0;
setInterval(() => {
  const arr = guideTextsFor(stageMode);
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

/* ---- Ảnh chân dung Bug: nạp từ window.BUG_PHOTO (static/bug-photo.js).
   Thiếu file / nạp lỗi -> giữ emoji 🐱 trong khung như cũ. ---- */
if (typeof window !== "undefined" && window.BUG_PHOTO) {
  const bpImg = $("bugPhoto");
  bpImg.onload = () => { bpImg.style.display = ""; };
  bpImg.src = window.BUG_PHOTO;
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

/* ================= canvas: cảnh Vườn Mèo =================
   Vườn ấm cúng vẽ hoàn toàn bằng code: trời mềm, hàng rào, sàn gỗ, bãi cỏ,
   bụi hoa, kho cá, hàng bát ăn. Mèo là mèo hoạt hình vẽ tay (không dùng
   asset của game nào khác), mỗi tính cách một bộ lông riêng. */
let bugPhotoImg = null;
if (typeof window !== "undefined" && window.BUG_PHOTO) {
  bugPhotoImg = new Image();
  bugPhotoImg.src = window.BUG_PHOTO;
}

const COATS = {
  tabby: { base: "#f2a54a", dark: "#d97f26", belly: "#ffe3b3", ear: "#ffb84d" },
  grey: { base: "#9aa3ad", dark: "#7c8791", belly: "#d7dde3", ear: "#c3ccd4" },
  calico: { base: "#fdf6ec", dark: "#e8dcc8", belly: "#ffffff", ear: "#ffd9c2" },
  white: { base: "#ffffff", dark: "#e3e3e3", belly: "#ffffff", ear: "#ffc7d6" },
  cream: { base: "#f3e3c2", dark: "#d9bd8a", belly: "#fdf3da", ear: "#ffd9a8" },
  brownwhite: { base: "#8a5a36", dark: "#6f4525", belly: "#fdf6ec", ear: "#c98d5f" },
  gold: { base: "#ffd94d", dark: "#e6ae1f", belly: "#ffedb0", ear: "#ffe27a" },
};

function gardenLayout(W, H) {
  return {
    deckTop: H * 0.335, deckBot: H * 0.52,
    bowls: [0, 1, 2, 3, 4].map((i) => ({ x: W * (0.22 + i * 0.135), y: H * 0.60 })),
    cushions: [{ x: W * 0.30, y: H * 0.665 }, { x: W * 0.70, y: H * 0.665 }],
    bushes: [{ x: W * 0.055, y: H * 0.615 }, { x: W * 0.945, y: H * 0.615 },
             { x: W * 0.05, y: H * 0.80 }, { x: W * 0.95, y: H * 0.80 }],
    store: { x: W * 0.875, y: H * 0.465 },
    bugPos: { x: W * 0.5, y: H * 0.44 },
  };
}

function gardenTargetFor(rec, state, L, W, H, now) {
  const seat = rec.data.seat || 0;
  switch (state) {
    case "eat": case "feast": {
      const b = L.bowls[seat % L.bowls.length];
      // nhiều mèo chung 1 bát: hàng sau đứng lệch xuống dưới cho khỏi chồng thẻ tên
      const row = Math.floor(seat / L.bowls.length) % 2;
      return { x: b.x + (row ? W * 0.04 : -W * 0.008), y: b.y - H * 0.028 + row * H * 0.038 };
    }
    case "sleep": {
      const c = L.cushions[seat % L.cushions.length];
      return { x: c.x + ((seat % 3) - 1) * W * 0.03, y: c.y };
    }
    case "play": {
      const a = (seat % 8) / 8 * Math.PI * 2;
      return { x: L.ballX + Math.cos(a) * W * 0.075, y: L.ballY + Math.sin(a) * H * 0.03 };
    }
    case "pose":
      return { x: W * 0.5 + ((seat % 5) - 2) * W * 0.062, y: H * 0.50 };
    case "hide": case "peek": {
      const b = L.bushes[seat % L.bushes.length];
      return { x: b.x, y: b.y + (state === "peek" ? -H * 0.012 : H * 0.008) };
    }
    case "hoard":
      return { x: L.store.x - W * 0.085 + (seat % 3) * W * 0.028, y: H * 0.578 };
    case "scatter":
      return { x: seat % 2 ? W * 0.045 : W * 0.955, y: H * (0.62 + (seat % 3) * 0.09) };
    default:
      return null; // idle: tự đi dạo (đích lưu trong rec)
  }
}

function drawGardenCat(x, y, s, rec, now) {
  const p = rec.data;
  const coat = COATS[p.coat] || COATS.tabby;
  const state = p.state || "idle";
  const sleeping = state === "sleep";
  let hopY = 0;
  if (state === "play") hopY = -Math.abs(Math.sin(now / 230 + rec.hue)) * s * 0.5;
  else if (now < gardenFx.hopUntil) hopY = -Math.abs(Math.sin(now / 210 + rec.hue)) * s * 0.3;

  ctx2d.save();
  ctx2d.translate(x, y + hopY);
  // Mèo Vàng: hào quang vàng sau lưng
  if (p.golden) {
    const aura = ctx2d.createRadialGradient(0, -s * 0.2, 0, 0, -s * 0.2, s * 1.5);
    aura.addColorStop(0, "rgba(255, 215, 64, .5)");
    aura.addColorStop(1, "rgba(255, 215, 64, 0)");
    ctx2d.fillStyle = aura;
    ctx2d.fillRect(-s * 1.5, -s * 1.7, s * 3, s * 3);
  }
  // bóng đất
  ctx2d.fillStyle = "rgba(30,50,20,.22)";
  ctx2d.beginPath(); ctx2d.ellipse(0, s * 0.46 - hopY * 0.5, s * 0.66, s * 0.13, 0, 0, Math.PI * 2); ctx2d.fill();
  ctx2d.scale(1, sleeping ? 0.8 : 1);
  // đuôi vẫy sau thân
  const wag = Math.sin(now / (sleeping ? 900 : 340) + rec.hue) * s * 0.16;
  ctx2d.strokeStyle = coat.dark; ctx2d.lineWidth = s * 0.13; ctx2d.lineCap = "round";
  ctx2d.beginPath(); ctx2d.moveTo(-s * 0.52, s * 0.08);
  ctx2d.quadraticCurveTo(-s * 0.92, -s * 0.12, -s * 0.78, -s * 0.5 + wag); ctx2d.stroke();
  // thân
  ctx2d.fillStyle = coat.base;
  ctx2d.beginPath(); ctx2d.ellipse(0, 0, s * 0.58, s * 0.42, 0, 0, Math.PI * 2); ctx2d.fill();
  // hoa văn lông theo tính cách
  ctx2d.save();
  ctx2d.beginPath(); ctx2d.ellipse(0, 0, s * 0.58, s * 0.42, 0, 0, Math.PI * 2); ctx2d.clip();
  if (p.coat === "tabby") {
    ctx2d.strokeStyle = coat.dark; ctx2d.lineWidth = s * 0.07;
    for (let i = -1; i <= 1; i++) {
      ctx2d.beginPath();
      ctx2d.moveTo(i * s * 0.26 - s * 0.1, -s * 0.42);
      ctx2d.quadraticCurveTo(i * s * 0.26, -s * 0.1, i * s * 0.26 - s * 0.06, s * 0.14);
      ctx2d.stroke();
    }
  } else if (p.coat === "calico") {
    ctx2d.fillStyle = "#f2a54a";
    ctx2d.beginPath(); ctx2d.ellipse(-s * 0.3, -s * 0.18, s * 0.24, s * 0.17, 0.4, 0, Math.PI * 2); ctx2d.fill();
    ctx2d.fillStyle = "#6b4a2f";
    ctx2d.beginPath(); ctx2d.ellipse(s * 0.28, s * 0.1, s * 0.2, s * 0.15, -0.3, 0, Math.PI * 2); ctx2d.fill();
  } else if (p.coat === "cream") {
    ctx2d.fillStyle = "#a9743f";
    ctx2d.beginPath(); ctx2d.ellipse(-s * 0.26, -s * 0.2, s * 0.22, s * 0.15, 0.3, 0, Math.PI * 2); ctx2d.fill();
    ctx2d.beginPath(); ctx2d.ellipse(s * 0.34, s * 0.16, s * 0.16, s * 0.12, 0, 0, Math.PI * 2); ctx2d.fill();
  }
  // bụng sáng
  ctx2d.fillStyle = coat.belly;
  ctx2d.beginPath(); ctx2d.ellipse(s * 0.08, s * 0.16, s * 0.34, s * 0.22, 0, 0, Math.PI * 2); ctx2d.fill();
  ctx2d.restore();
  // chân
  if (!sleeping) {
    ctx2d.fillStyle = coat.dark;
    for (const dir of [-1, 1]) {
      ctx2d.beginPath(); ctx2d.ellipse(dir * s * 0.3, s * 0.4, s * 0.13, s * 0.08, 0, 0, Math.PI * 2); ctx2d.fill();
    }
  }
  // đầu (ăn thì cúi gập xuống bát)
  let hx = s * 0.36, hy = -s * 0.44;
  if (state === "eat" || state === "feast") hy += s * 0.13 + Math.sin(now / 170 + rec.hue) * s * 0.05;
  if (state === "pose") hy -= s * 0.07;
  const hr = s * 0.38;
  ctx2d.fillStyle = coat.ear;
  for (const dir of [-1, 1]) {
    ctx2d.beginPath();
    ctx2d.moveTo(hx + dir * hr * 0.7, hy - hr * 0.5);
    ctx2d.lineTo(hx + dir * hr * 0.22, hy - hr * 1.16);
    ctx2d.lineTo(hx + dir * hr * 1.02, hy - hr * 0.88);
    ctx2d.closePath(); ctx2d.fill();
    ctx2d.fillStyle = "#ff9db8";
    ctx2d.beginPath();
    ctx2d.moveTo(hx + dir * hr * 0.55, hy - hr * 0.58);
    ctx2d.lineTo(hx + dir * hr * 0.34, hy - hr * 0.94);
    ctx2d.lineTo(hx + dir * hr * 0.8, hy - hr * 0.82);
    ctx2d.closePath(); ctx2d.fill();
    ctx2d.fillStyle = coat.ear;
  }
  ctx2d.fillStyle = coat.base;
  ctx2d.beginPath(); ctx2d.arc(hx, hy, hr, 0, Math.PI * 2); ctx2d.fill();
  if (p.coat === "cream") { // mảng nâu che một bên mặt của Nhút Nhát
    ctx2d.save();
    ctx2d.beginPath(); ctx2d.arc(hx, hy, hr, 0, Math.PI * 2); ctx2d.clip();
    ctx2d.fillStyle = "#a9743f";
    ctx2d.beginPath(); ctx2d.ellipse(hx - hr * 0.5, hy - hr * 0.3, hr * 0.5, hr * 0.42, 0.3, 0, Math.PI * 2); ctx2d.fill();
    ctx2d.restore();
  }
  // mặt: mắt theo tâm trạng
  const mood = p.mood_face || "🙂";
  ctx2d.strokeStyle = "#3a2a20"; ctx2d.fillStyle = "#3a2a20"; ctx2d.lineCap = "round";
  const eyeY = hy - hr * 0.05, eyeDx = hr * 0.38, eyeR = hr * 0.09;
  if (sleeping || mood === "😊" || mood === "😴") {
    ctx2d.lineWidth = 2.2;
    for (const dir of [-1, 1]) {
      ctx2d.beginPath(); ctx2d.arc(hx + dir * eyeDx, eyeY, eyeR * 1.25, Math.PI * 1.12, Math.PI * 1.88); ctx2d.stroke();
    }
  } else if (mood === "😾") {
    ctx2d.lineWidth = 2.4;
    for (const dir of [-1, 1]) {
      ctx2d.beginPath();
      ctx2d.moveTo(hx + dir * eyeDx - eyeR, eyeY - eyeR * 2.1);
      ctx2d.lineTo(hx + dir * eyeDx + eyeR, eyeY - eyeR * 1.2);
      ctx2d.stroke();
      ctx2d.beginPath(); ctx2d.arc(hx + dir * eyeDx, eyeY, eyeR * 0.8, 0, Math.PI * 2); ctx2d.fill();
    }
  } else {
    for (const dir of [-1, 1]) {
      ctx2d.beginPath(); ctx2d.arc(hx + dir * eyeDx, eyeY, eyeR, 0, Math.PI * 2); ctx2d.fill();
    }
  }
  // mũi + miệng + râu
  ctx2d.fillStyle = "#ff7d9c";
  ctx2d.beginPath();
  ctx2d.moveTo(hx - hr * 0.1, hy + hr * 0.18); ctx2d.lineTo(hx + hr * 0.1, hy + hr * 0.18);
  ctx2d.lineTo(hx, hy + hr * 0.32); ctx2d.closePath(); ctx2d.fill();
  ctx2d.strokeStyle = "rgba(58,42,32,.75)"; ctx2d.lineWidth = 1.6;
  ctx2d.beginPath(); ctx2d.arc(hx - hr * 0.11, hy + hr * 0.3, hr * 0.11, 0.15 * Math.PI, 0.85 * Math.PI); ctx2d.stroke();
  ctx2d.beginPath(); ctx2d.arc(hx + hr * 0.11, hy + hr * 0.3, hr * 0.11, 0.15 * Math.PI, 0.85 * Math.PI); ctx2d.stroke();
  ctx2d.strokeStyle = "rgba(58,42,32,.4)";
  for (const dir of [-1, 1]) for (const k of [-1, 1]) {
    ctx2d.beginPath();
    ctx2d.moveTo(hx + dir * hr * 0.55, hy + hr * 0.22 + k * hr * 0.1);
    ctx2d.lineTo(hx + dir * hr * 1.05, hy + hr * 0.16 + k * hr * 0.2);
    ctx2d.stroke();
  }
  // Chảnh đeo nơ hồng
  if (p.personality === "diva") {
    ctx2d.save();
    ctx2d.translate(hx + hr * 0.62, hy - hr * 0.92);
    ctx2d.fillStyle = "#ff5e8a";
    for (const dir of [-1, 1]) {
      ctx2d.beginPath();
      ctx2d.moveTo(0, 0); ctx2d.lineTo(dir * s * 0.13, -s * 0.07); ctx2d.lineTo(dir * s * 0.13, s * 0.07);
      ctx2d.closePath(); ctx2d.fill();
    }
    ctx2d.beginPath(); ctx2d.arc(0, 0, s * 0.035, 0, Math.PI * 2); ctx2d.fill();
    ctx2d.restore();
  }
  // huy chương avatar / chữ cái đầu tên ở ngực
  const mx = s * 0.3, my = s * 0.2, mr = s * 0.17;
  ctx2d.save();
  ctx2d.beginPath(); ctx2d.arc(mx, my, mr, 0, Math.PI * 2); ctx2d.clip();
  if (rec.imgOk && rec.img) {
    ctx2d.drawImage(rec.img, mx - mr, my - mr, mr * 2, mr * 2);
  } else {
    ctx2d.fillStyle = `hsl(${rec.hue} 55% 45%)`;
    ctx2d.fillRect(mx - mr, my - mr, mr * 2, mr * 2);
    ctx2d.fillStyle = "#fff";
    ctx2d.font = `800 ${mr * 1.05}px sans-serif`;
    ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
    ctx2d.fillText((p.nickname || "?").slice(0, 1).toUpperCase(), mx, my + 1);
  }
  ctx2d.restore();
  ctx2d.strokeStyle = "#ffd34d"; ctx2d.lineWidth = 2;
  ctx2d.beginPath(); ctx2d.arc(mx, my, mr, 0, Math.PI * 2); ctx2d.stroke();
  // hiệu ứng theo trạng thái
  ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
  if (sleeping) {
    ctx2d.fillStyle = "#5b7fa6";
    for (let i = 0; i < 2; i++) {
      const ph = ((now / 1100 + rec.hue / 360 + i * 0.5) % 1);
      ctx2d.globalAlpha = 1 - ph;
      ctx2d.font = `700 ${s * (0.22 + ph * 0.14)}px sans-serif`;
      ctx2d.fillText("Z", hx + hr + ph * s * 0.3, hy - hr - ph * s * 0.55);
    }
    ctx2d.globalAlpha = 1;
  }
  if (state === "pose") {
    ctx2d.fillStyle = "#ff5e8a";
    for (let i = 0; i < 3; i++) {
      const a = now / 500 + i * 2.1;
      ctx2d.globalAlpha = 0.55 + 0.45 * Math.sin(a);
      ctx2d.font = `${s * 0.2}px serif`;
      ctx2d.fillText("✦", hx + Math.cos(a) * hr * 1.5, hy - hr * 0.6 + Math.sin(a) * hr * 0.5);
    }
    ctx2d.globalAlpha = 1;
  }
  if (state === "hoard") {
    ctx2d.font = `${s * 0.34}px serif`;
    ctx2d.fillText("🐟", s * 0.52, s * 0.3);
  }
  if (p.treat) {
    ctx2d.font = `${s * 0.22}px serif`;
    for (let i = 0; i < 3; i++) {
      const a = now / 350 + i * 2.1;
      ctx2d.fillText("✨", Math.cos(a) * s * 0.75, -s * 0.3 + Math.sin(a) * s * 0.55);
    }
  }
  if (p.golden) {
    ctx2d.font = `${s * 0.3}px serif`;
    ctx2d.fillText("👑", hx, hy - hr * 1.55);
  }
  ctx2d.restore();

  // thẻ tên: icon tính cách + tên + mặt tâm trạng (+ tim đã sinh)
  ctx2d.save();
  ctx2d.translate(x, y + hopY);
  const shortName = (p.nickname || "?").length > 10 ? (p.nickname || "?").slice(0, 10) + "…" : (p.nickname || "?");
  const label = `${p.icon || ""} ${shortName} ${p.mood_face || ""}${p.hearts ? ` ❤️${p.hearts}` : ""}`;
  ctx2d.font = `600 ${Math.max(11, s * 0.27)}px sans-serif`;
  const tw = ctx2d.measureText(label).width + 14;
  const ly = -s * 1.45;
  ctx2d.fillStyle = p.golden ? "rgba(94,66,0,.9)" : "rgba(23,40,24,.85)";
  ctx2d.beginPath(); ctx2d.roundRect(-tw / 2, ly - s * 0.2, tw, s * 0.42, 8); ctx2d.fill();
  ctx2d.fillStyle = "#fff"; ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
  ctx2d.fillText(label, 0, ly + s * 0.02);
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

function drawGardenScene(now, W, H, dt) {
  const L = gardenLayout(W, H);
  L.ballX = W * (0.5 + 0.3 * Math.sin(now / 5200));
  L.ballY = H * (0.74 + 0.07 * Math.sin(now / 3700 + 1));
  const golden = gardenState && gardenState.golden_hour_active;
  const feast = gardenState && gardenState.feast_active;

  // trời mềm + mây trôi chậm
  const sky = ctx2d.createLinearGradient(0, 0, 0, H * 0.4);
  if (golden) { sky.addColorStop(0, "#ffb45e"); sky.addColorStop(1, "#ffe6b8"); }
  else { sky.addColorStop(0, "#8ed4f7"); sky.addColorStop(1, "#e8fbff"); }
  ctx2d.fillStyle = sky; ctx2d.fillRect(0, 0, W, H * 0.42);
  ctx2d.fillStyle = golden ? "rgba(255,190,80,.85)" : "rgba(255,244,180,.9)";
  ctx2d.beginPath(); ctx2d.arc(W * 0.85, H * 0.07, H * 0.032, 0, Math.PI * 2); ctx2d.fill();
  ctx2d.fillStyle = "rgba(255,255,255,.92)";
  for (let i = 0; i < 4; i++) {
    const cx = ((i * 0.27 + 0.1) * W - (worldOffset * 0.05) % (W * 1.25) + W * 1.25) % (W * 1.25) - W * 0.12;
    const cy = H * (0.045 + (i % 3) * 0.04);
    ctx2d.beginPath();
    ctx2d.ellipse(cx, cy, W * 0.05, H * 0.014, 0, 0, Math.PI * 2);
    ctx2d.ellipse(cx + W * 0.032, cy + 3, W * 0.036, H * 0.011, 0, 0, Math.PI * 2);
    ctx2d.fill();
  }
  // hàng cây xa ở chân trời
  ctx2d.fillStyle = golden ? "#7fae56" : "#8fce6e";
  for (let i = 0; i < 7; i++) {
    const tx = W * (0.06 + i * 0.145), tr = W * (0.075 + (i % 3) * 0.012);
    ctx2d.beginPath(); ctx2d.arc(tx, L.deckTop - tr * 0.4, tr, 0, Math.PI * 2); ctx2d.fill();
  }
  // hàng rào gỗ
  ctx2d.fillStyle = "#b08954";
  ctx2d.fillRect(0, L.deckTop - H * 0.028, W, H * 0.012);
  ctx2d.fillRect(0, L.deckTop - H * 0.008, W, H * 0.012);
  for (let i = 0; i <= 11; i++) {
    ctx2d.fillRect(W * (i / 11) - W * 0.008, L.deckTop - H * 0.042, W * 0.016, H * 0.05);
  }
  // sàn gỗ (deck): ván ngang + mép trước + bóng đổ xuống cỏ
  const deck = ctx2d.createLinearGradient(0, L.deckTop, 0, L.deckBot);
  deck.addColorStop(0, "#d29a5f"); deck.addColorStop(1, "#b57e45");
  ctx2d.fillStyle = deck; ctx2d.fillRect(0, L.deckTop, W, L.deckBot - L.deckTop);
  ctx2d.strokeStyle = "rgba(120,72,30,.4)"; ctx2d.lineWidth = 2;
  for (let y = L.deckTop + H * 0.031; y < L.deckBot; y += H * 0.031) {
    ctx2d.beginPath(); ctx2d.moveTo(0, y); ctx2d.lineTo(W, y); ctx2d.stroke();
  }
  ctx2d.fillStyle = "#8a5a2b"; ctx2d.fillRect(0, L.deckBot - H * 0.008, W, H * 0.008);
  ctx2d.fillStyle = "rgba(60,40,10,.18)"; ctx2d.fillRect(0, L.deckBot, W, H * 0.014);
  // bãi cỏ
  const grass = ctx2d.createLinearGradient(0, L.deckBot, 0, H);
  if (golden) { grass.addColorStop(0, "#a8c95e"); grass.addColorStop(1, "#77983c"); }
  else { grass.addColorStop(0, "#8fce6e"); grass.addColorStop(1, "#57a047"); }
  ctx2d.fillStyle = grass; ctx2d.fillRect(0, L.deckBot, W, H - L.deckBot);
  ctx2d.strokeStyle = "rgba(40,90,30,.35)"; ctx2d.lineWidth = 2;
  for (let i = 0; i < 26; i++) {
    const tx = ((i * 613.7) % (W * 0.96)) + W * 0.02;
    const ty = L.deckBot + ((i * 389.3) % (H * 0.4)) + H * 0.03;
    ctx2d.beginPath();
    ctx2d.moveTo(tx, ty); ctx2d.lineTo(tx - 3, ty - H * 0.008);
    ctx2d.moveTo(tx + 3, ty); ctx2d.lineTo(tx + 5, ty - H * 0.009);
    ctx2d.stroke();
  }
  // lối đá giữa cỏ
  ctx2d.fillStyle = "rgba(200,200,195,.75)";
  for (let i = 0; i < 4; i++) {
    ctx2d.beginPath();
    ctx2d.ellipse(W * (0.44 + (i % 2) * 0.1), H * (0.66 + i * 0.075), W * 0.05, H * 0.013, 0, 0, Math.PI * 2);
    ctx2d.fill();
  }
  // hàng bát ăn trên cỏ trước sàn
  for (const b of L.bowls) {
    ctx2d.fillStyle = "rgba(30,50,20,.2)";
    ctx2d.beginPath(); ctx2d.ellipse(b.x, b.y + H * 0.006, W * 0.032, H * 0.006, 0, 0, Math.PI * 2); ctx2d.fill();
    ctx2d.fillStyle = "#e2574c";
    ctx2d.beginPath(); ctx2d.ellipse(b.x, b.y, W * 0.032, H * 0.011, 0, 0, Math.PI); ctx2d.fill();
    ctx2d.fillStyle = "#a9743f";
    ctx2d.beginPath(); ctx2d.ellipse(b.x, b.y - H * 0.002, W * 0.024, H * 0.007, 0, 0, Math.PI * 2); ctx2d.fill();
  }
  // đệm nằm trên sàn
  for (const [i, c] of L.cushions.entries()) {
    ctx2d.fillStyle = i ? "#7e9ff2" : "#f28bb4";
    ctx2d.beginPath(); ctx2d.ellipse(c.x, c.y, W * 0.075, H * 0.016, 0, 0, Math.PI * 2); ctx2d.fill();
    ctx2d.fillStyle = "rgba(255,255,255,.35)";
    ctx2d.beginPath(); ctx2d.ellipse(c.x, c.y - H * 0.004, W * 0.058, H * 0.011, 0, 0, Math.PI * 2); ctx2d.fill();
  }
  // kho cá: hộp gỗ + mái + biển cá
  const st = L.store;
  ctx2d.fillStyle = "#a9743f";
  ctx2d.fillRect(st.x - W * 0.065, st.y - H * 0.035, W * 0.13, H * 0.07);
  ctx2d.fillStyle = "#7c4f24";
  ctx2d.beginPath();
  ctx2d.moveTo(st.x - W * 0.08, st.y - H * 0.035); ctx2d.lineTo(st.x, st.y - H * 0.075);
  ctx2d.lineTo(st.x + W * 0.08, st.y - H * 0.035); ctx2d.closePath(); ctx2d.fill();
  ctx2d.fillStyle = "#5e3a17";
  ctx2d.fillRect(st.x - W * 0.02, st.y - H * 0.005, W * 0.04, H * 0.04);
  ctx2d.font = `${H * 0.026}px serif`; ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
  ctx2d.fillText("🐟", st.x, st.y - H * 0.048);
  // trang trí khi có quà: cờ dây ngang sàn + chong chóng cạnh kho cá
  if (gardenState && gardenState.decor_active) {
    const flagCols = ["#ff5e8a", "#ffd34d", "#5ec8ff", "#7be495", "#ff9f1a"];
    ctx2d.strokeStyle = "rgba(90,60,20,.6)"; ctx2d.lineWidth = 2;
    ctx2d.beginPath(); ctx2d.moveTo(W * 0.03, L.deckTop + H * 0.012);
    ctx2d.quadraticCurveTo(W * 0.5, L.deckTop + H * 0.045, W * 0.97, L.deckTop + H * 0.012); ctx2d.stroke();
    for (let i = 0; i < 12; i++) {
      const t = (i + 0.5) / 12;
      const fx = W * (0.03 + 0.94 * t);
      const fy = L.deckTop + H * 0.012 + Math.sin(t * Math.PI) * H * 0.03;
      ctx2d.fillStyle = flagCols[i % flagCols.length];
      ctx2d.beginPath();
      ctx2d.moveTo(fx - W * 0.014, fy); ctx2d.lineTo(fx + W * 0.014, fy); ctx2d.lineTo(fx, fy + H * 0.02);
      ctx2d.closePath(); ctx2d.fill();
    }
    ctx2d.save();
    ctx2d.translate(st.x - W * 0.1, st.y - H * 0.03);
    ctx2d.rotate(now / 300);
    ctx2d.fillStyle = "#ff5e8a";
    for (let i = 0; i < 4; i++) {
      ctx2d.rotate(Math.PI / 2);
      ctx2d.beginPath(); ctx2d.ellipse(0, -H * 0.014, W * 0.008, H * 0.014, 0, 0, Math.PI * 2); ctx2d.fill();
    }
    ctx2d.restore();
  }
  // bóng len + bướm cho hội Tăng Động rượt
  ctx2d.fillStyle = "#ff5e8a";
  ctx2d.beginPath(); ctx2d.arc(L.ballX, L.ballY, W * 0.02, 0, Math.PI * 2); ctx2d.fill();
  ctx2d.strokeStyle = "#d63d68"; ctx2d.lineWidth = 2;
  ctx2d.beginPath(); ctx2d.arc(L.ballX, L.ballY, W * 0.013, 0.4, 2.4); ctx2d.stroke();
  ctx2d.beginPath(); ctx2d.moveTo(L.ballX + W * 0.016, L.ballY + W * 0.012);
  ctx2d.quadraticCurveTo(L.ballX + W * 0.05, L.ballY + W * 0.03, L.ballX + W * 0.075, L.ballY + W * 0.008); ctx2d.stroke();
  const bfX = L.ballX + Math.cos(now / 900) * W * 0.05, bfY = L.ballY - H * 0.05 + Math.sin(now / 700) * H * 0.012;
  ctx2d.fillStyle = "#b388ff";
  const flap = 0.5 + Math.abs(Math.sin(now / 90)) * 0.7;
  for (const dir of [-1, 1]) {
    ctx2d.beginPath(); ctx2d.ellipse(bfX + dir * W * 0.011 * flap, bfY, W * 0.011 * flap, H * 0.007, dir * 0.5, 0, Math.PI * 2); ctx2d.fill();
  }

  // Bug chủ vườn: ảnh thật trong khung tròn trên đệm giữa sàn
  const bp = L.bugPos;
  ctx2d.fillStyle = "#8e6cc8";
  ctx2d.beginPath(); ctx2d.ellipse(bp.x, bp.y + H * 0.045, W * 0.085, H * 0.017, 0, 0, Math.PI * 2); ctx2d.fill();
  const br = H * 0.05;
  ctx2d.save();
  ctx2d.beginPath(); ctx2d.arc(bp.x, bp.y, br, 0, Math.PI * 2); ctx2d.clip();
  if (bugPhotoImg && bugPhotoImg.complete && bugPhotoImg.naturalWidth > 0) {
    ctx2d.drawImage(bugPhotoImg, bp.x - br, bp.y - br, br * 2, br * 2);
  } else {
    ctx2d.fillStyle = "#ffe3b3";
    ctx2d.fillRect(bp.x - br, bp.y - br, br * 2, br * 2);
    ctx2d.font = `${br * 1.1}px serif`; ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
    ctx2d.fillText("🐱", bp.x, bp.y);
  }
  ctx2d.restore();
  ctx2d.strokeStyle = "#ffd34d"; ctx2d.lineWidth = 3.5;
  ctx2d.beginPath(); ctx2d.arc(bp.x, bp.y, br, 0, Math.PI * 2); ctx2d.stroke();
  ctx2d.font = `600 ${Math.max(11, H * 0.014)}px sans-serif`;
  const bugLabel = "Bug 👑 chủ vườn";
  const btw = ctx2d.measureText(bugLabel).width + 14;
  ctx2d.fillStyle = "rgba(94,66,0,.9)";
  ctx2d.beginPath(); ctx2d.roundRect(bp.x - btw / 2, bp.y - br - H * 0.032, btw, H * 0.021, 8); ctx2d.fill();
  ctx2d.fillStyle = "#fff"; ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
  ctx2d.fillText(bugLabel, bp.x, bp.y - br - H * 0.021);

  // mèo người xem: di chuyển mượt về vùng theo trạng thái, vẽ theo thứ tự xa->gần
  const all = [...players.values()].slice(0, 16);
  const scatter = now < gardenFx.scatterUntil;
  const s = H * 0.052;
  for (const rec of all) {
    if (rec.gx === undefined) {
      rec.gx = W * (0.15 + (rec.hue % 70) / 100);
      rec.gy = H * (0.62 + (rec.hue % 25) / 100);
      rec.gtx = rec.gx; rec.gty = rec.gy; rec.gWait = 0;
    }
    const state = scatter ? "scatter" : (rec.data.state || "idle");
    let target = gardenTargetFor(rec, state, L, W, H, now);
    if (!target) {
      // đi dạo: giữ đích cũ, tới nơi thì nghỉ một lát rồi chọn đích mới
      if ((Math.hypot(rec.gtx - rec.gx, rec.gty - rec.gy) < 6 && now > rec.gWait) || !rec.gHasDest) {
        if (Math.random() < 0.22) {
          // dạo trên sàn: chỉ ở dải giữa cho khỏi chui sau 2 panel hai bên
          rec.gtx = W * (0.34 + Math.random() * 0.36);
          rec.gty = L.deckTop + H * (0.08 + Math.random() * 0.07);
        } else {
          rec.gtx = W * (0.1 + Math.random() * 0.8);
          rec.gty = H * (0.60 + Math.random() * 0.28);
        }
        rec.gHasDest = true;
        rec.gWait = now + 2500 + Math.random() * 3500;
      }
      target = { x: rec.gtx, y: rec.gty };
    } else {
      rec.gHasDest = false;
    }
    const dx = target.x - rec.gx, dy = target.y - rec.gy;
    const dist = Math.hypot(dx, dy);
    const speed = (state === "idle" ? W * 0.07 : W * 0.30) * dt;
    if (dist > 3) {
      const step = Math.min(dist, speed);
      rec.gx += (dx / dist) * step;
      rec.gy += (dy / dist) * step;
    }
  }
  all.sort((a, b) => a.gy - b.gy);
  for (const rec of all) drawGardenCat(rec.gx, rec.gy, s, rec, now);

  // bụi hoa vẽ SAU mèo: mèo núp/ngó sẽ bị bụi che đúng nghĩa
  for (const b of L.bushes) {
    ctx2d.fillStyle = "#3f7d33";
    for (const [ox, oy, r] of [[-0.035, 0.005, 0.045], [0, -0.012, 0.055], [0.038, 0.006, 0.042], [0.005, 0.014, 0.05]]) {
      ctx2d.beginPath(); ctx2d.arc(b.x + W * ox, b.y + H * oy, W * r, 0, Math.PI * 2); ctx2d.fill();
    }
    ctx2d.fillStyle = "#ff8fb3";
    for (let i = 0; i < 5; i++) {
      ctx2d.beginPath();
      ctx2d.arc(b.x + W * (((i * 37) % 60) - 30) / 1000, b.y - H * 0.01 + ((i * 23) % 20) / 1000 * H, 3.2, 0, Math.PI * 2);
      ctx2d.fill();
    }
  }

  // Giờ Vàng: phủ nắng ấm toàn cảnh; Bữa Tiệc / Giờ Vàng: băng chữ giữa vườn
  if (golden) {
    const gg = ctx2d.createLinearGradient(0, 0, 0, H);
    gg.addColorStop(0, "rgba(255,170,50,.16)"); gg.addColorStop(1, "rgba(255,120,20,.26)");
    ctx2d.fillStyle = gg; ctx2d.fillRect(0, 0, W, H);
  }
  const bannerText = golden ? "🌇 GIỜ VÀNG — CẢ VƯỜN MỞ TIỆC LỚN!" : feast ? "🎉 BỮA TIỆC VƯỜN ĐANG MỞ!" : "";
  if (bannerText) {
    ctx2d.font = `800 ${H * 0.02}px sans-serif`;
    const bw = ctx2d.measureText(bannerText).width + 36;
    ctx2d.fillStyle = golden ? "rgba(146,84,0,.88)" : "rgba(23,64,32,.88)";
    ctx2d.beginPath(); ctx2d.roundRect(W / 2 - bw / 2, H * 0.605, bw, H * 0.034, 99); ctx2d.fill();
    ctx2d.fillStyle = "#ffe9a8"; ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
    ctx2d.fillText(bannerText, W / 2, H * 0.622);
  }
  // tim bay lên khi tim vườn tăng
  gardenFx.hearts = gardenFx.hearts.filter((h) => now - h.t0 < 1500);
  ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
  for (const h of gardenFx.hearts) {
    const prog = (now - h.t0) / 1500;
    ctx2d.save();
    ctx2d.globalAlpha = 1 - prog;
    ctx2d.font = `${H * 0.02}px serif`;
    ctx2d.fillText("❤️", h.x + Math.sin(prog * 5) * 8, h.y - prog * H * 0.07);
    ctx2d.restore();
  }
}

/* ================= canvas: cảnh Đào Vàng PK =================
   Mỏ vàng vẽ hoàn toàn bằng code (nhân vật thợ mỏ là mèo/chuột hoạt hình
   gốc của kênh — không sao chép nhân vật của game Đào Vàng nào khác):
   trần hang tím, sàn gỗ với 2 giàn tời, lòng đất tầng lớp, vàng và kim
   cương phát sáng lấp lánh. Vị trí vật phẩm + góc/độ dài móc lấy thẳng từ
   snapshot server nên móc khớp đúng vật nó giật trúng. */
function detRand(seed) { const v = Math.sin(seed * 127.1 + 311.7) * 43758.5453; return v - Math.floor(v); }

function drawSparkle(x, y, size, alpha) {
  ctx2d.save();
  ctx2d.globalAlpha = Math.max(0, Math.min(1, alpha));
  ctx2d.fillStyle = "#fff7cf";
  ctx2d.beginPath();
  ctx2d.moveTo(x, y - size);
  ctx2d.quadraticCurveTo(x, y, x + size, y);
  ctx2d.quadraticCurveTo(x, y, x, y + size);
  ctx2d.quadraticCurveTo(x, y, x - size, y);
  ctx2d.quadraticCurveTo(x, y, x, y - size);
  ctx2d.fill();
  ctx2d.restore();
}

function drawMinerItem(kind, x, y, r, now, seed) {
  ctx2d.save();
  ctx2d.translate(x, y);
  if (kind === "gold_s" || kind === "gold_m" || kind === "gold_l") {
    // quầng sáng ấm quanh cục vàng
    const glow = ctx2d.createRadialGradient(0, 0, 0, 0, 0, r * 1.9);
    glow.addColorStop(0, "rgba(255, 200, 60, .30)"); glow.addColorStop(1, "rgba(255, 200, 60, 0)");
    ctx2d.fillStyle = glow; ctx2d.fillRect(-r * 1.9, -r * 1.9, r * 3.8, r * 3.8);
    // thân: đa giác khía cạnh (nugget) theo seed để mỗi cục một dáng
    ctx2d.beginPath();
    const pts = 8;
    for (let i = 0; i < pts; i++) {
      const a = (i / pts) * Math.PI * 2;
      const rr = r * (0.82 + 0.3 * detRand(seed * 7 + i * 13));
      const vx = Math.cos(a) * rr, vy = Math.sin(a) * rr * 0.86;
      if (i) ctx2d.lineTo(vx, vy); else ctx2d.moveTo(vx, vy);
    }
    ctx2d.closePath();
    const g = ctx2d.createRadialGradient(-r * 0.3, -r * 0.35, r * 0.15, 0, 0, r * 1.15);
    g.addColorStop(0, "#ffe98a"); g.addColorStop(0.55, "#ffc93c"); g.addColorStop(1, "#e08e0b");
    ctx2d.fillStyle = g; ctx2d.fill();
    ctx2d.strokeStyle = "rgba(146, 90, 0, .55)"; ctx2d.lineWidth = Math.max(1.5, r * 0.06); ctx2d.stroke();
    // mặt cắt sáng giả lập mặt phẳng của nugget
    ctx2d.beginPath();
    ctx2d.moveTo(-r * 0.45, -r * 0.08); ctx2d.lineTo(0, -r * 0.55); ctx2d.lineTo(r * 0.32, r * 0.02);
    ctx2d.closePath();
    ctx2d.fillStyle = "rgba(255, 246, 190, .5)"; ctx2d.fill();
    // tia lấp lánh nhấp nháy theo (id, thời gian)
    const tw = 0.5 + 0.5 * Math.sin(now / 280 + seed * 2.7);
    if (tw > 0.5) drawSparkle(-r * 0.18, -r * 0.3, r * 0.55 * tw, tw);
  } else if (kind === "diamond") {
    const glow = ctx2d.createRadialGradient(0, 0, 0, 0, 0, r * 1.8);
    glow.addColorStop(0, "rgba(127, 231, 255, .35)"); glow.addColorStop(1, "rgba(127, 231, 255, 0)");
    ctx2d.fillStyle = glow; ctx2d.fillRect(-r * 1.8, -r * 1.8, r * 3.6, r * 3.6);
    ctx2d.beginPath();
    ctx2d.moveTo(-r, -r * 0.32); ctx2d.lineTo(-r * 0.55, -r * 0.8); ctx2d.lineTo(r * 0.55, -r * 0.8);
    ctx2d.lineTo(r, -r * 0.32); ctx2d.lineTo(0, r);
    ctx2d.closePath();
    const g = ctx2d.createLinearGradient(0, -r, 0, r);
    g.addColorStop(0, "#c9f6ff"); g.addColorStop(0.5, "#5fd4f2"); g.addColorStop(1, "#1d8fd1");
    ctx2d.fillStyle = g; ctx2d.fill();
    ctx2d.strokeStyle = "rgba(230, 252, 255, .9)"; ctx2d.lineWidth = Math.max(1.2, r * 0.05); ctx2d.stroke();
    ctx2d.beginPath();
    ctx2d.moveTo(-r, -r * 0.32); ctx2d.lineTo(r, -r * 0.32);
    ctx2d.moveTo(-r * 0.55, -r * 0.8); ctx2d.lineTo(0, r);
    ctx2d.moveTo(r * 0.55, -r * 0.8); ctx2d.lineTo(0, r);
    ctx2d.stroke();
    const tw = 0.5 + 0.5 * Math.sin(now / 240 + seed * 3.9);
    if (tw > 0.45) drawSparkle(r * 0.3, -r * 0.5, r * 0.6 * tw, tw);
  } else if (kind === "rock") {
    ctx2d.beginPath();
    const pts = 7;
    for (let i = 0; i < pts; i++) {
      const a = (i / pts) * Math.PI * 2;
      const rr = r * (0.78 + 0.34 * detRand(seed * 11 + i * 7));
      const vx = Math.cos(a) * rr, vy = Math.sin(a) * rr * 0.85;
      if (i) ctx2d.lineTo(vx, vy); else ctx2d.moveTo(vx, vy);
    }
    ctx2d.closePath();
    const g = ctx2d.createRadialGradient(-r * 0.25, -r * 0.3, r * 0.2, 0, 0, r * 1.1);
    g.addColorStop(0, "#b9bcc4"); g.addColorStop(1, "#6d6f78");
    ctx2d.fillStyle = g; ctx2d.fill();
    ctx2d.strokeStyle = "rgba(30, 28, 38, .6)"; ctx2d.lineWidth = Math.max(1.5, r * 0.06); ctx2d.stroke();
    ctx2d.beginPath();
    ctx2d.moveTo(-r * 0.4, -r * 0.3); ctx2d.lineTo(0, r * 0.05); ctx2d.lineTo(-r * 0.15, r * 0.45);
    ctx2d.stroke();
  } else if (kind === "bag") {
    // túi bí mật: thân túi nâu buộc miệng + dấu "?"
    ctx2d.fillStyle = "#8a5a2b";
    ctx2d.beginPath(); ctx2d.ellipse(0, r * 0.16, r * 0.82, r * 0.78, 0, 0, Math.PI * 2); ctx2d.fill();
    ctx2d.fillStyle = "#6f4525";
    ctx2d.beginPath();
    ctx2d.moveTo(-r * 0.3, -r * 0.5); ctx2d.lineTo(r * 0.3, -r * 0.5);
    ctx2d.lineTo(r * 0.12, -r * 0.92); ctx2d.lineTo(-r * 0.12, -r * 0.92);
    ctx2d.closePath(); ctx2d.fill();
    ctx2d.strokeStyle = "#d9a441"; ctx2d.lineWidth = Math.max(2, r * 0.09);
    ctx2d.beginPath(); ctx2d.moveTo(-r * 0.3, -r * 0.48); ctx2d.lineTo(r * 0.3, -r * 0.48); ctx2d.stroke();
    ctx2d.fillStyle = "#ffe9a8";
    ctx2d.font = `900 ${r * 1.05}px sans-serif`;
    ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
    ctx2d.fillText("?", 0, r * 0.2);
  } else if (kind === "bone") {
    ctx2d.font = `${r * 1.9}px serif`;
    ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
    ctx2d.fillText("🦴", 0, 0);
  }
  ctx2d.restore();
}

/* Thợ vận hành giàn tời: trái = mèo cam đội mũ bảo hộ, phải = chuột xám
   đội mũ (tai tròn, mõm nhọn, đuôi dài) — cả hai đều là hình vẽ gốc. */
function drawMinerOperator(x, y, s, kind, now, facing) {
  const isCat = kind === "cat";
  const coat = isCat
    ? { base: "#f2a54a", dark: "#d97f26", belly: "#ffe3b3", ear: "#ffb84d" }
    : { base: "#9aa3ad", dark: "#7c8791", belly: "#d7dde3", ear: "#c3ccd4" };
  const bobY = Math.sin(now / 480 + (isCat ? 0 : 2.1)) * s * 0.025;
  ctx2d.save();
  ctx2d.translate(x, y + bobY);
  // bóng đất
  ctx2d.fillStyle = "rgba(20, 10, 0, .3)";
  ctx2d.beginPath(); ctx2d.ellipse(0, s * 0.46, s * 0.6, s * 0.12, 0, 0, Math.PI * 2); ctx2d.fill();
  // đuôi: mèo cong lên sau lưng; chuột dài ngoằn ngoèo thả ra sau
  ctx2d.strokeStyle = isCat ? coat.dark : "#d89a9a";
  ctx2d.lineWidth = s * (isCat ? 0.11 : 0.07); ctx2d.lineCap = "round";
  ctx2d.beginPath();
  if (isCat) {
    ctx2d.moveTo(-facing * s * 0.45, s * 0.1);
    ctx2d.quadraticCurveTo(-facing * s * 0.85, -s * 0.05, -facing * s * 0.72, -s * 0.52 + Math.sin(now / 340) * s * 0.06);
  } else {
    ctx2d.moveTo(-facing * s * 0.45, s * 0.18);
    ctx2d.quadraticCurveTo(-facing * s * 0.95, s * 0.3, -facing * s * 1.25, s * 0.12 + Math.sin(now / 300) * s * 0.05);
  }
  ctx2d.stroke();
  // thân
  ctx2d.fillStyle = coat.base;
  ctx2d.beginPath(); ctx2d.ellipse(0, 0, s * 0.56, s * 0.42, 0, 0, Math.PI * 2); ctx2d.fill();
  if (isCat) { // vằn cam trên lưng
    ctx2d.save();
    ctx2d.beginPath(); ctx2d.ellipse(0, 0, s * 0.56, s * 0.42, 0, 0, Math.PI * 2); ctx2d.clip();
    ctx2d.strokeStyle = coat.dark; ctx2d.lineWidth = s * 0.06;
    for (let i = -1; i <= 1; i++) {
      ctx2d.beginPath();
      ctx2d.moveTo(i * s * 0.24 - s * 0.3, -s * 0.4);
      ctx2d.quadraticCurveTo(i * s * 0.24 - s * 0.22, -s * 0.1, i * s * 0.24 - s * 0.28, s * 0.12);
      ctx2d.stroke();
    }
    ctx2d.restore();
  }
  ctx2d.fillStyle = coat.belly;
  ctx2d.beginPath(); ctx2d.ellipse(facing * s * 0.1, s * 0.15, s * 0.32, s * 0.21, 0, 0, Math.PI * 2); ctx2d.fill();
  // đầu
  const hx = facing * s * 0.3, hy = -s * 0.46, hr = s * 0.34;
  if (isCat) {
    ctx2d.fillStyle = coat.ear;
    for (const dir of [-1, 1]) {
      ctx2d.beginPath();
      ctx2d.moveTo(hx + dir * hr * 0.7, hy - hr * 0.45);
      ctx2d.lineTo(hx + dir * hr * 0.22, hy - hr * 1.1);
      ctx2d.lineTo(hx + dir * hr * 1.0, hy - hr * 0.82);
      ctx2d.closePath(); ctx2d.fill();
    }
  } else {
    // tai chuột: 2 vòng tròn to viền hồng
    for (const dir of [-1, 1]) {
      ctx2d.fillStyle = coat.base;
      ctx2d.beginPath(); ctx2d.arc(hx + dir * hr * 0.62, hy - hr * 0.78, hr * 0.42, 0, Math.PI * 2); ctx2d.fill();
      ctx2d.fillStyle = "#e8a2b4";
      ctx2d.beginPath(); ctx2d.arc(hx + dir * hr * 0.62, hy - hr * 0.78, hr * 0.24, 0, Math.PI * 2); ctx2d.fill();
    }
  }
  ctx2d.fillStyle = coat.base;
  ctx2d.beginPath(); ctx2d.arc(hx, hy, hr, 0, Math.PI * 2); ctx2d.fill();
  if (!isCat) { // mõm nhọn + mũi hồng + râu dài
    ctx2d.fillStyle = coat.belly;
    ctx2d.beginPath(); ctx2d.ellipse(hx + facing * hr * 0.72, hy + hr * 0.28, hr * 0.52, hr * 0.34, 0, 0, Math.PI * 2); ctx2d.fill();
    ctx2d.fillStyle = "#ff7d9c";
    ctx2d.beginPath(); ctx2d.arc(hx + facing * hr * 1.18, hy + hr * 0.22, hr * 0.13, 0, Math.PI * 2); ctx2d.fill();
    ctx2d.strokeStyle = "rgba(58,42,32,.45)"; ctx2d.lineWidth = 1.3;
    for (const k of [-1, 1]) {
      ctx2d.beginPath();
      ctx2d.moveTo(hx + facing * hr * 0.8, hy + hr * 0.3 + k * hr * 0.12);
      ctx2d.lineTo(hx + facing * hr * 1.45, hy + hr * 0.22 + k * hr * 0.3);
      ctx2d.stroke();
    }
  } else { // mũi mèo nhỏ
    ctx2d.fillStyle = "#ff7d9c";
    ctx2d.beginPath();
    ctx2d.moveTo(hx + facing * hr * 0.28 - hr * 0.1, hy + hr * 0.16);
    ctx2d.lineTo(hx + facing * hr * 0.28 + hr * 0.1, hy + hr * 0.16);
    ctx2d.lineTo(hx + facing * hr * 0.28, hy + hr * 0.3);
    ctx2d.closePath(); ctx2d.fill();
  }
  // mắt nhìn về phía trục quay
  ctx2d.fillStyle = "#3a2a20";
  ctx2d.beginPath(); ctx2d.arc(hx + facing * hr * 0.3, hy - hr * 0.05, hr * 0.1, 0, Math.PI * 2); ctx2d.fill();
  ctx2d.beginPath(); ctx2d.arc(hx - facing * hr * 0.32, hy - hr * 0.05, hr * 0.1, 0, Math.PI * 2); ctx2d.fill();
  // mũ bảo hộ vàng + đèn pha
  ctx2d.fillStyle = "#ffd23f";
  ctx2d.beginPath(); ctx2d.arc(hx, hy - hr * 0.12, hr * 1.02, Math.PI, Math.PI * 2); ctx2d.fill();
  ctx2d.fillRect(hx - hr * 1.18, hy - hr * 0.16, hr * 2.36, hr * 0.16);
  const lampGlow = ctx2d.createRadialGradient(hx, hy - hr * 0.55, 0, hx, hy - hr * 0.55, hr * 0.75);
  lampGlow.addColorStop(0, "rgba(255, 244, 180, .75)"); lampGlow.addColorStop(1, "rgba(255, 244, 180, 0)");
  ctx2d.fillStyle = lampGlow;
  ctx2d.beginPath(); ctx2d.arc(hx, hy - hr * 0.55, hr * 0.75, 0, Math.PI * 2); ctx2d.fill();
  ctx2d.fillStyle = "#fff6c9";
  ctx2d.beginPath(); ctx2d.arc(hx, hy - hr * 0.55, hr * 0.24, 0, Math.PI * 2); ctx2d.fill();
  ctx2d.strokeStyle = "#d9a441"; ctx2d.lineWidth = 1.6;
  ctx2d.beginPath(); ctx2d.arc(hx, hy - hr * 0.55, hr * 0.24, 0, Math.PI * 2); ctx2d.stroke();
  ctx2d.restore();
}

/* HUD kéo co VS: thanh tỉ lệ vàng 2 đội + huy hiệu hiệp ngay trên canvas */
function drawMinerHud(now, W, H) {
  const m = minerState;
  const sm = m ? m.scores.meo || 0 : 0;
  const sc = m ? m.scores.chuot || 0 : 0;
  const frac = sm + sc > 0 ? sm / (sm + sc) : 0.5;
  const x0 = W * 0.16, x1 = W * 0.84, y = H * 0.058, bh = H * 0.018;
  ctx2d.save();
  ctx2d.beginPath(); ctx2d.roundRect(x0, y, x1 - x0, bh, bh / 2); ctx2d.clip();
  const gr = ctx2d.createLinearGradient(x0, 0, x1, 0);
  gr.addColorStop(0, "#ff5a5a"); gr.addColorStop(1, "#b06bff");
  ctx2d.fillStyle = gr; ctx2d.fillRect(x0, y, x1 - x0, bh);
  const gl = ctx2d.createLinearGradient(x0, 0, x1, 0);
  gl.addColorStop(0, "#ffd23f"); gl.addColorStop(1, "#ff9f1a");
  ctx2d.fillStyle = gl; ctx2d.fillRect(x0, y, (x1 - x0) * frac, bh);
  ctx2d.fillStyle = "rgba(255,255,255,.35)"; ctx2d.fillRect(x0, y, x1 - x0, bh * 0.38);
  ctx2d.restore();
  ctx2d.strokeStyle = "rgba(10, 6, 20, .55)"; ctx2d.lineWidth = 2;
  ctx2d.beginPath(); ctx2d.roundRect(x0, y, x1 - x0, bh, bh / 2); ctx2d.stroke();
  // tên đội + điểm nằm trong 2 đầu thanh
  ctx2d.font = `800 ${H * 0.0145}px sans-serif`;
  ctx2d.textBaseline = "middle";
  ctx2d.fillStyle = "#3a2703"; ctx2d.textAlign = "left";
  ctx2d.fillText(`🐱 MÈO ${sm}`, x0 + 10, y + bh / 2 + 1);
  ctx2d.fillStyle = "#fff"; ctx2d.textAlign = "right";
  ctx2d.fillText(`${sc} CHUỘT 🐭`, x1 - 10, y + bh / 2 + 1);
  // huy hiệu giữa thanh: HIỆP n • thời gian còn lại
  const badge = !m ? "⛏️ ĐÀO VÀNG PK"
    : m.phase === "podium" ? `⏸️ NGHỈ • HIỆP ${m.round}`
    : `HIỆP ${m.round} • ${m.time_left}s`;
  ctx2d.font = `800 ${H * 0.0155}px sans-serif`;
  const bw = ctx2d.measureText(badge).width + 30;
  ctx2d.fillStyle = "rgba(12, 8, 26, .88)";
  ctx2d.beginPath(); ctx2d.roundRect(W / 2 - bw / 2, y - bh * 0.22, bw, bh * 1.44, 99); ctx2d.fill();
  ctx2d.strokeStyle = "#ffd34d"; ctx2d.lineWidth = 1.6;
  ctx2d.beginPath(); ctx2d.roundRect(W / 2 - bw / 2, y - bh * 0.22, bw, bh * 1.44, 99); ctx2d.stroke();
  ctx2d.fillStyle = "#ffd88a"; ctx2d.textAlign = "center";
  ctx2d.fillText(badge, W / 2, y + bh / 2 + 1);
  // số hiệp đã thắng dưới 2 đầu thanh
  if (m && (m.wins.meo > 0 || m.wins.chuot > 0)) {
    ctx2d.font = `700 ${H * 0.0125}px sans-serif`;
    ctx2d.fillStyle = "#ffd88a"; ctx2d.textAlign = "left";
    if (m.wins.meo > 0) ctx2d.fillText(`🏆 ×${m.wins.meo}`, x0 + 4, y + bh + H * 0.011);
    ctx2d.fillStyle = "#ffb3d9"; ctx2d.textAlign = "right";
    if (m.wins.chuot > 0) ctx2d.fillText(`🏆 ×${m.wins.chuot}`, x1 - 4, y + bh + H * 0.011);
  }
  ctx2d.restore();
}

function drawMinerScene(now, W, H, dt) {
  const m = minerState;
  ctx2d.save();
  // nổ mìn: rung màn hình ~400ms
  if (now < minerFx.shakeUntil) {
    const k = Math.max(0, (minerFx.shakeUntil - now) / 400);
    ctx2d.translate((Math.random() - 0.5) * W * 0.014 * k, (Math.random() - 0.5) * H * 0.009 * k);
  }
  // --- lòng đất: gradient nâu theo tầng sâu ---
  const dirt = ctx2d.createLinearGradient(0, 0, 0, H);
  dirt.addColorStop(0, "#7a4e26"); dirt.addColorStop(0.35, "#5d3a1c");
  dirt.addColorStop(0.7, "#452a13"); dirt.addColorStop(1, "#2e1c0c");
  ctx2d.fillStyle = dirt; ctx2d.fillRect(-W * 0.02, 0, W * 1.04, H);
  // vỉa đất tối lượn sóng
  ctx2d.fillStyle = "rgba(0, 0, 0, .12)";
  for (const fy of [0.38, 0.58, 0.8]) {
    ctx2d.beginPath();
    ctx2d.moveTo(0, H * fy);
    for (let x = 0; x <= W; x += W / 12) {
      ctx2d.lineTo(x, H * fy + Math.sin(x / W * 5.1 + fy * 20) * H * 0.008);
    }
    ctx2d.lineTo(W, H * (fy + 0.05)); ctx2d.lineTo(0, H * (fy + 0.05));
    ctx2d.closePath(); ctx2d.fill();
  }
  // đá ngầm chìm ở 2 mép
  ctx2d.fillStyle = "rgba(18, 10, 24, .32)";
  for (const side of [0, 1]) {
    ctx2d.beginPath();
    const bx = side ? W : 0;
    ctx2d.moveTo(bx, H * 0.2);
    for (let i = 0; i <= 5; i++) {
      const yy = H * (0.2 + i * 0.16);
      const off = W * (0.02 + detRand(i * 3 + side * 40) * 0.035);
      ctx2d.lineTo(bx + (side ? -off : off), yy);
    }
    ctx2d.lineTo(bx, H);
    ctx2d.closePath(); ctx2d.fill();
  }
  // tinh thể tím mờ trong lòng đất
  for (let i = 0; i < 7; i++) {
    const cx = detRand(i * 3 + 1) * W, cy = H * (0.32 + detRand(i * 5 + 2) * 0.55);
    const cs = H * 0.006 * (0.7 + detRand(i * 7) * 0.7);
    ctx2d.save();
    ctx2d.translate(cx, cy); ctx2d.rotate(Math.PI / 4);
    ctx2d.fillStyle = `rgba(178, 132, 255, ${0.13 + 0.06 * Math.sin(now / 800 + i)})`;
    ctx2d.fillRect(-cs, -cs, cs * 2, cs * 2);
    ctx2d.restore();
  }
  // --- trần hang tím đen + răng đá ---
  const ceil = ctx2d.createLinearGradient(0, 0, 0, H * 0.1);
  ceil.addColorStop(0, "#17102a"); ceil.addColorStop(1, "#2c1e4e");
  ctx2d.fillStyle = ceil; ctx2d.fillRect(-W * 0.02, 0, W * 1.04, H * 0.1);
  ctx2d.fillStyle = "#241839";
  for (let i = 0; i < 12; i++) {
    const sx = (i / 12) * W + detRand(i * 17) * W * 0.03;
    const sw = W * (0.02 + detRand(i * 23) * 0.025), sh = H * (0.008 + detRand(i * 29) * 0.012);
    ctx2d.beginPath();
    ctx2d.moveTo(sx, H * 0.1); ctx2d.lineTo(sx + sw, H * 0.1); ctx2d.lineTo(sx + sw / 2, H * 0.1 + sh);
    ctx2d.closePath(); ctx2d.fill();
  }
  // --- sàn gỗ: dải ván nơi đặt giàn tời ---
  const deck = ctx2d.createLinearGradient(0, H * 0.1, 0, H * 0.178);
  deck.addColorStop(0, "#a9743f"); deck.addColorStop(1, "#7c4f24");
  ctx2d.fillStyle = deck; ctx2d.fillRect(-W * 0.02, H * 0.1, W * 1.04, H * 0.078);
  ctx2d.strokeStyle = "rgba(70, 42, 12, .5)"; ctx2d.lineWidth = 2;
  for (let x = 0; x < W; x += W * 0.0625) {
    ctx2d.beginPath(); ctx2d.moveTo(x, H * 0.1); ctx2d.lineTo(x, H * 0.178); ctx2d.stroke();
  }
  ctx2d.fillStyle = "#5e3a17"; ctx2d.fillRect(-W * 0.02, H * 0.172, W * 1.04, H * 0.007);
  ctx2d.fillStyle = "rgba(0, 0, 0, .22)"; ctx2d.fillRect(-W * 0.02, H * 0.179, W * 1.04, H * 0.012);

  // --- vật phẩm trên trường mỏ ---
  if (m) {
    for (const it of m.items) drawMinerItem(it.kind, it.x * W, it.y * H, it.r * W, now, it.id);
  }

  // --- Bug chủ mỏ: ảnh thật khung vàng trên bục gỗ giữa 2 giàn ---
  const bx = W * 0.5, by = H * 0.208, br = H * 0.031;
  ctx2d.fillStyle = "#8a5a2b";
  ctx2d.beginPath(); ctx2d.roundRect(bx - br * 1.5, by + br * 0.92, br * 3, H * 0.011, 4); ctx2d.fill();
  ctx2d.save();
  ctx2d.beginPath(); ctx2d.arc(bx, by, br, 0, Math.PI * 2); ctx2d.clip();
  if (bugPhotoImg && bugPhotoImg.complete && bugPhotoImg.naturalWidth > 0) {
    ctx2d.drawImage(bugPhotoImg, bx - br, by - br, br * 2, br * 2);
  } else {
    ctx2d.fillStyle = "#ffe3b3"; ctx2d.fillRect(bx - br, by - br, br * 2, br * 2);
    ctx2d.font = `${br * 1.1}px serif`; ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
    ctx2d.fillText("🐱", bx, by);
  }
  ctx2d.restore();
  ctx2d.strokeStyle = "#ffd34d"; ctx2d.lineWidth = 3;
  ctx2d.beginPath(); ctx2d.arc(bx, by, br, 0, Math.PI * 2); ctx2d.stroke();
  ctx2d.font = `600 ${Math.max(11, H * 0.0125)}px sans-serif`;
  const bugLabel = "Bug ⚖️ chủ mỏ";
  const btw = ctx2d.measureText(bugLabel).width + 14;
  ctx2d.fillStyle = "rgba(43, 28, 8, .9)";
  ctx2d.beginPath(); ctx2d.roundRect(bx - btw / 2, by + br + H * 0.013, btw, H * 0.019, 8); ctx2d.fill();
  ctx2d.fillStyle = "#ffd88a"; ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
  ctx2d.fillText(bugLabel, bx, by + br + H * 0.0225);

  // --- 2 giàn tời + thợ + dây móc ---
  for (const team of ["meo", "chuot"]) {
    const { px, py, tx, ty } = minerTipPx(team, W, H);
    const h = m && m.hooks ? m.hooks[team] : null;
    const facing = team === "meo" ? 1 : -1;
    // khung gỗ: 2 cột + xà ngang + trục quay (tời)
    ctx2d.fillStyle = "#8a5a2b";
    ctx2d.fillRect(px - W * 0.037, H * 0.096, W * 0.011, py - H * 0.096 + H * 0.014);
    ctx2d.fillRect(px + W * 0.026, H * 0.096, W * 0.011, py - H * 0.096 + H * 0.014);
    ctx2d.fillStyle = "#a9743f";
    ctx2d.fillRect(px - W * 0.045, H * 0.092, W * 0.09, H * 0.011);
    // trục quay: ống gỗ quấn dây
    ctx2d.fillStyle = "#6f4525";
    ctx2d.beginPath(); ctx2d.arc(px, py, W * 0.017, 0, Math.PI * 2); ctx2d.fill();
    ctx2d.strokeStyle = "#d8cfc0"; ctx2d.lineWidth = 2;
    for (const rr of [0.006, 0.0105, 0.015]) {
      ctx2d.beginPath(); ctx2d.arc(px, py, W * rr, 0, Math.PI * 2); ctx2d.stroke();
    }
    ctx2d.fillStyle = "#3a2a20";
    ctx2d.beginPath(); ctx2d.arc(px, py, W * 0.004, 0, Math.PI * 2); ctx2d.fill();
    // thợ vận hành đứng cạnh trục
    drawMinerOperator(px - facing * W * 0.055, py + H * 0.006, H * 0.05, team === "meo" ? "cat" : "rat", now, facing);
    // dây móc
    const buff = m && m.buffs ? m.buffs[team] : null;
    const buffActive = !!(buff && buff.until > Date.now() / 1000);
    const golden = minerFx.goldenGlow[team];
    ctx2d.save();
    if (golden) {
      ctx2d.shadowColor = "#ffd34d"; ctx2d.shadowBlur = 15;
      ctx2d.strokeStyle = "#ffd34d"; ctx2d.lineWidth = 4;
    } else {
      ctx2d.strokeStyle = "rgba(232, 232, 238, .92)"; ctx2d.lineWidth = 3;
    }
    ctx2d.beginPath(); ctx2d.moveTo(px, py); ctx2d.lineTo(tx, ty); ctx2d.stroke();
    ctx2d.restore();
    // buff kéo nhanh: tia vàng chạy dọc dây
    if (buffActive) {
      for (let k = 0; k < 4; k++) {
        const t = (k / 4 + (now / 700) % 0.25) % 1;
        drawSparkle(px + (tx - px) * t, py + (ty - py) * t, H * 0.008, 0.85);
      }
    }
    // móc sắt ở đầu dây
    ctx2d.save();
    ctx2d.translate(tx, ty);
    ctx2d.strokeStyle = "#cfd6dd"; ctx2d.lineWidth = 3.5; ctx2d.lineCap = "round";
    ctx2d.beginPath(); ctx2d.moveTo(0, -H * 0.012); ctx2d.lineTo(0, -H * 0.002); ctx2d.stroke();
    ctx2d.beginPath(); ctx2d.arc(0, H * 0.004, H * 0.0095, Math.PI * 0.15, Math.PI * 1.5); ctx2d.stroke();
    ctx2d.restore();
    // vật đang kéo treo ngay dưới móc
    if (h && h.carrying_kind) {
      drawMinerItem(h.carrying_kind, tx, ty + H * 0.02, (MINER_KIND_R[h.carrying_kind] || 0.034) * W * 0.85, now, 777);
    }
  }

  // --- HUD kéo co ---
  drawMinerHud(now, W, H);

  // --- pháo giấy mừng đội thắng trong pha podium ---
  if (m && m.phase === "podium" && minerRoundEnd && minerRoundEnd.round === m.round && minerRoundEnd.winner) {
    const cols = minerRoundEnd.winner === "meo" ? ["#ffd23f", "#3aa0ff", "#fff3b0"] : ["#ff5a5a", "#b06bff", "#ffd3e0"];
    if (minerFx.confetti.length < 80 && Math.random() < 0.5) {
      const half = minerRoundEnd.winner === "meo" ? [0.02, 0.48] : [0.52, 0.98];
      minerFx.confetti.push({
        x: W * (half[0] + Math.random() * (half[1] - half[0])), y: -H * 0.01,
        vx: (Math.random() - 0.5) * W * 0.02, vy: H * (0.05 + Math.random() * 0.05),
        rot: Math.random() * 6.3, vr: (Math.random() - 0.5) * 6,
        col: cols[Math.floor(Math.random() * cols.length)], t0: now,
      });
    }
  }
  minerFx.confetti = minerFx.confetti.filter((c) => c.y < H * 1.02);
  for (const c of minerFx.confetti) {
    c.x += c.vx * dt + Math.sin(now / 300 + c.rot) * W * 0.008 * dt;
    c.y += c.vy * dt;
    c.rot += c.vr * dt;
    ctx2d.save();
    ctx2d.translate(c.x, c.y); ctx2d.rotate(c.rot);
    ctx2d.fillStyle = c.col;
    ctx2d.fillRect(-W * 0.006, -H * 0.0035, W * 0.012, H * 0.007);
    ctx2d.restore();
  }

  // --- tia lửa khi móc chạm vật (bắn ở đầu móc lúc có sự kiện giật) ---
  minerFx.bursts = minerFx.bursts.filter((b) => now - b.t0 < 600);
  for (const b of minerFx.bursts) {
    const prog = (now - b.t0) / 600;
    const dist = prog * H * 0.045;
    drawSparkle(b.x + Math.cos(b.ang) * dist, b.y + Math.sin(b.ang) * dist,
      H * 0.011 * (1 - prog), 1 - prog);
  }

  // --- đá văng khi nổ mìn ---
  minerFx.rocks = minerFx.rocks.filter((r) => now - r.t0 < 950);
  for (const r of minerFx.rocks) {
    const age = (now - r.t0) / 1000;
    const rx = r.x + r.vx * age;
    const ry = r.y + r.vy * age + 0.5 * H * 0.38 * age * age;
    ctx2d.save();
    ctx2d.translate(rx, ry); ctx2d.rotate(r.rot + r.vr * age);
    ctx2d.globalAlpha = Math.max(0, 1 - age / 0.95);
    ctx2d.fillStyle = "#7d7f88";
    ctx2d.beginPath();
    ctx2d.moveTo(-r.s, -r.s * 0.6); ctx2d.lineTo(r.s * 0.4, -r.s);
    ctx2d.lineTo(r.s, r.s * 0.3); ctx2d.lineTo(-r.s * 0.3, r.s * 0.8);
    ctx2d.closePath(); ctx2d.fill();
    ctx2d.restore();
  }

  // --- số "+vàng" bay lên ở giàn tời của đội vừa giật trúng ---
  minerFx.floats = minerFx.floats.filter((f) => now - f.t0 < 1500);
  ctx2d.textAlign = "center"; ctx2d.textBaseline = "middle";
  for (const f of minerFx.floats) {
    const prog = (now - f.t0) / 1500;
    const piv = MINER_PIVOTS[f.team];
    const fx = piv.x * W, fy = H * 0.115 - prog * H * 0.05;
    ctx2d.save();
    ctx2d.globalAlpha = 1 - prog;
    ctx2d.font = `900 ${H * 0.021}px sans-serif`;
    ctx2d.strokeStyle = "rgba(40, 24, 0, .75)"; ctx2d.lineWidth = 4;
    ctx2d.strokeText(`+${f.val}`, fx, fy);
    ctx2d.fillStyle = "#ffd34d";
    ctx2d.fillText(`+${f.val}`, fx, fy);
    ctx2d.restore();
  }

  // chớp sáng ấm phủ màn hình khi nổ mìn
  if (now < minerFx.flashUntil) {
    ctx2d.fillStyle = `rgba(255, 170, 60, ${0.26 * Math.max(0, (minerFx.flashUntil - now) / 350)})`;
    ctx2d.fillRect(-W * 0.02, 0, W * 1.04, H);
  }
  ctx2d.restore();
}

let lastFrame = performance.now();
function draw(now) {
  const dt = Math.min(0.05, (now - lastFrame) / 1000);
  lastFrame = now;
  const W = canvas.width, H = canvas.height;
  worldOffset += dt * 55;

  // chế độ Vườn Mèo dùng cảnh riêng hoàn toàn
  if (stageMode === "garden") {
    drawGardenScene(now, W, H, dt);
    requestAnimationFrame(draw);
    return;
  }

  // chế độ Đào Vàng PK dùng cảnh riêng hoàn toàn
  if (stageMode === "miner") {
    drawMinerScene(now, W, H, dt);
    requestAnimationFrame(draw);
    return;
  }

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
      if (typeof msg.music_enabled === "boolean") music.setEnabled(msg.music_enabled);
      if (typeof msg.music_volume === "number") music.setVolume(msg.music_volume);
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
    case "bug_sleep":
      showBugBubble("💤 Bug ngủ đây…");
      ticker("🌙 Bug đi ngủ — cả nhà nói khẽ thôi nha");
      logEvent("🌙 Bug đi ngủ");
      break;
    case "bug_wake":
      showBugBubble("🥱 ngủ dậy rồi!");
      ticker("🐱 Bug ngủ dậy rồi, khỏe re!");
      logEvent("🐱 Bug ngủ dậy");
      break;
    case "bug_overfed":
      showBugBubble("No quá rồi… 😵");
      ticker("🍗 Bug bị cho ăn quá độ — no căng bụng rồi!");
      logEvent("🍗 Bug ăn quá no, khó chịu");
      break;
    case "bug_wake_annoyed":
      showBugBubble("💢 ai phá giấc ngủ của tui!");
      ticker("💢 Bug bị phá giấc ngủ — đang khó chịu!");
      logEvent("💢 Bug thức dậy khó chịu");
      break;
    case "bug_disturbed":
      showBugBubble("🤫 suỵt…");
      break;
    case "bug_refuse":
      showBugBubble("💢 để Bug yên một lát…");
      break;
    case "likes": renderSnapshot(msg); break;
    case "rain": rain(msg.kind, msg.seconds || 30); ticker("🌧️🐟 MƯA CÁ! Cả nhà hứng cá nào!"); logEvent("🌧️🐟 Mưa cá!"); break;
    case "gift": {
      const rec = upsertPlayer(msg.player);
      if (stageMode === "miner") {
        // Đào Vàng PK: không cưỡi xe / spotlight / mưa cá — hiệu ứng quà là
        // buff kéo + Móc Vàng, do sự kiện miner_buff / miner_golden_grab báo riêng
        ticker(`🎁 ${msg.player.nickname} tặng ${msg.gift_name}!`);
        logEvent(`🎁 ${msg.player.nickname} tặng ${msg.gift_name}`);
        meow.play("happy");
        break;
      }
      if (stageMode === "garden") {
        // Vườn Mèo: không cưỡi xe / spotlight — mèo nhận bát đặc biệt, vườn thêm trang trí
        ticker(`🎁 ${msg.player.nickname} tặng ${msg.gift_name} — mèo của bạn nhận bát đặc biệt!`);
        logEvent(`🎁 ${msg.player.nickname} tặng ${msg.gift_name}`);
        meow.play("happy");
        break;
      }
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
      if (stageMode === "miner") {
        // Đào Vàng PK: không có chó đuổi — tin +10 vàng cho đội do sự kiện
        // miner_follow_bonus báo riêng ngay sau đây
        meow.play("happy");
        break;
      }
      if (stageMode === "garden") {
        // Vườn Mèo: mèo của người follow chuyển vào vườn ở luôn, không có chó đuổi
        ticker(`🌿 ${msg.player.nickname} vừa follow — một bé mèo chuyển vào vườn ở luôn!`);
        logEvent(`🔔 ${msg.player.nickname} follow — mèo vào vườn`);
        meow.play("happy");
        break;
      }
      dogs.push({ x: -0.06, until: performance.now() + 12000 });
      ticker(`🐕 ${msg.player.nickname} vừa follow — Bug đuổi theo đội chạy!`);
      logEvent(`🔔 ${msg.player.nickname} follow`);
      break;
    case "garden_feed":
      ticker(`🍚 ${msg.name} gọi ăn — hội Ham Ăn lao tới bát!`);
      logEvent(`🍚 ${msg.name} gọi mèo ăn`);
      meow.play("happy");
      break;
    case "garden_play":
      ticker(`🧶 ${msg.name} rủ chơi — hội Tăng Động đuổi bóng!`);
      logEvent(`🧶 ${msg.name} rủ mèo chơi`);
      meow.play("excited");
      break;
    case "garden_praise":
      ticker("💅 Có mèo được khen — Chảnh tạo dáng liền!");
      logEvent("💅 Khen mèo trong vườn");
      break;
    case "garden_fish":
      ticker(`🐟 ${msg.name} nhắc tới cá — hội Mê Cá chầu kho cá!`);
      logEvent(`🐟 ${msg.name} gọi cá`);
      break;
    case "garden_golden":
      ticker("✨ MÈO VÀNG xuất hiện trong vườn — tim nhân đôi!");
      logEvent("✨ Mèo Vàng xuất hiện!");
      showBugBubble("✨ Mèo Vàng kìa!");
      meow.play("chorus");
      break;
    case "garden_feast":
      ticker("🎉 BỮA TIỆC VƯỜN! Cả đàn mèo vào bàn ăn!");
      logEvent("🎉 Bữa Tiệc Vườn!");
      meow.play("chorus");
      break;
    case "garden_golden_hour":
      ticker("🌇 GIỜ VÀNG! Cả vườn mở tiệc lớn, tim bay ngập trời!");
      logEvent("🌇 Giờ Vàng!");
      meow.play("chorus");
      break;
    case "garden_scatter":
      gardenFx.scatterUntil = performance.now() + 3000;
      ticker("💢 Bug khó chịu — cả vườn tản ra né!");
      logEvent("💢 Mèo trong vườn tản ra né Bug");
      break;
    case "garden_share":
      gardenFx.hopUntil = performance.now() + 2500;
      if (msg.player) upsertPlayer(msg.player);
      ticker(`🔁 ${msg.player ? msg.player.nickname : "Một bạn"} chia sẻ live — cả vườn nhảy mừng!`);
      break;
    case "garden_treat":
      if (msg.player) upsertPlayer(msg.player);
      break;
    case "miner_join":
      if (msg.player) upsertPlayer(msg.player);
      ticker(`⛏️ ${msg.name} vào Đội ${MINER_TEAM_NAMES[msg.team] || msg.team}! Gõ "đào" để thả móc nha`);
      logEvent(`⛏️ ${msg.name} vào Đội ${MINER_TEAM_NAMES[msg.team] || msg.team}`);
      break;
    case "miner_drop":
      ticker(`⛏️ Đội ${MINER_TEAM_NAMES[msg.team] || msg.team} thả móc!`);
      break;
    case "miner_grab": {
      const nowG = performance.now();
      const tipG = minerTipPx(msg.team, canvas.width, canvas.height);
      minerFx.floats.push({ team: msg.team, val: msg.value || 0, t0: nowG });
      for (let i = 0; i < 10; i++) {
        minerFx.bursts.push({ x: tipG.tx, y: tipG.ty, ang: (i / 10) * Math.PI * 2 + Math.random() * 0.5, t0: nowG });
      }
      minerFx.goldenGlow[msg.team] = false; // móc vàng đã kéo về tới nơi
      ticker(`💰 ${msg.name} giật ${MINER_KIND_NAMES[msg.kind] || "vàng"} +${msg.value} cho Đội ${MINER_TEAM_NAMES[msg.team]}!`);
      logEvent(`💰 ${msg.name} +${msg.value} (${MINER_KIND_NAMES[msg.kind] || msg.kind})`, (msg.value || 0) >= 60);
      meow.play((msg.value || 0) >= 60 ? "excited" : "normal");
      break;
    }
    case "miner_blast": {
      const nowB = performance.now();
      minerFx.shakeUntil = nowB + 400;
      minerFx.flashUntil = nowB + 350;
      for (let i = 0; i < 26; i++) {
        minerFx.rocks.push({
          x: canvas.width * (0.12 + Math.random() * 0.76),
          y: canvas.height * (0.5 + Math.random() * 0.42),
          vx: (Math.random() - 0.5) * canvas.width * 0.09,
          vy: -canvas.height * (0.04 + Math.random() * 0.13),
          rot: Math.random() * 6.3, vr: (Math.random() - 0.5) * 9,
          s: canvas.height * (0.006 + Math.random() * 0.009), t0: nowB,
        });
      }
      ticker("💥 NỔ MÌN! Đá bay hết, vàng lộ ra rồi — ĐÀO mau!");
      logEvent("💥 NỔ MÌN phá đá, lộ vàng!", true);
      meow.play("chorus");
      break;
    }
    case "miner_round_end":
      minerRoundEnd = { ...msg };
      ticker(msg.winner
        ? `🏆 Hết hiệp ${msg.round}: Đội ${MINER_TEAM_NAMES[msg.winner]} thắng ${msg.score_meo}–${msg.score_chuot}!`
        : `🤝 Hiệp ${msg.round} hoà ${msg.score_meo}–${msg.score_chuot}!`);
      logEvent(`🏆 Hiệp ${msg.round}: ${msg.winner ? `Đội ${MINER_TEAM_NAMES[msg.winner]} thắng ` : "Hoà "}${msg.score_meo}–${msg.score_chuot}${msg.mvp_name ? ` • 👑 ${msg.mvp_name} (${msg.mvp_gold} vàng)` : ""}`, true);
      meow.play("chorus");
      break;
    case "miner_follow_bonus":
      ticker(`🔔 ${msg.name} follow — Đội ${MINER_TEAM_NAMES[msg.team]} +10 vàng!`);
      logEvent(`🔔 ${msg.name} follow (+10 vàng Đội ${MINER_TEAM_NAMES[msg.team]})`);
      break;
    case "miner_buff":
      ticker(`⚡ Đội ${MINER_TEAM_NAMES[msg.team]} được tăng tốc kéo ×${msg.mult} nhờ quà của ${msg.name}!`);
      logEvent(`⚡ Buff kéo ×${msg.mult} cho Đội ${MINER_TEAM_NAMES[msg.team]}`);
      break;
    case "miner_golden_grab":
      minerFx.goldenGlow[msg.team] = true;
      ticker(`🌟 MÓC VÀNG! Đội ${MINER_TEAM_NAMES[msg.team]} chĩa thẳng ${MINER_KIND_NAMES[msg.kind] || "vàng to"}!`);
      logEvent(`🌟 Móc Vàng — Đội ${MINER_TEAM_NAMES[msg.team]}`, true);
      meow.play("excited");
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
