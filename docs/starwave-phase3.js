/* StarWave Phase 3 (2026-11-09)
 * 核心功能全部真实可用：真实音频播放链路回归、播放队列（含断点续播）、
 * 歌词同步（含时间偏移调节）、双 Analyser 真实频谱 + BPM/Kick 检测、
 * 三段均衡器、本地收藏、播放历史、本地歌单（解决 Phase 2 歌单详情空数据问题）。
 * 约束：只存本机（localStorage），不登录、不取 Cookie、不接 QQ/酷狗/酷我播放，
 * 汽水已移除（Ma 2026-11-09 22:45 决定，Phase 4A 接线已拆），不改品牌/PWA 缓存名，不碰 Spotify/Apple 接线。
 * 实现方式：新文件做加法（包装已有全局函数）+ index.html 仅 8 处小手术
 * （歌词偏移钩子、本地歌单 provider、队列移歌按钮、三段 EQ 接入、引用本文件）。
 * 任何一步失败只降级提示，不抛错、不阻塞页面加载。
 */
(function () {
  'use strict';

  /* ---------- 小工具 ---------- */
  function $(id) { return document.getElementById(id); }
  function toast(msg) { try { if (typeof showToast === 'function') showToast(msg); } catch (e) { /* ignore */ } }
  function storeGet(k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } }
  function storeSet(k, v) { try { window.localStorage.setItem(k, v); } catch (e) { /* ignore */ } }
  function storeDel(k) { try { window.localStorage.removeItem(k); } catch (e) { /* ignore */ } }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function clamp(v, lo, hi) { v = Number(v); if (!isFinite(v)) v = 0; return Math.max(lo, Math.min(hi, v)); }
  function fmtTime(sec) {
    if (typeof formatProgramTime === 'function') { try { return formatProgramTime(Math.max(0, Math.round(sec || 0))); } catch (e) { /* ignore */ } }
    sec = Math.max(0, Math.floor(sec || 0));
    var m = Math.floor(sec / 60), s = sec % 60;
    return m + ':' + String(s).padStart(2, '0');
  }
  function fmtDate(ts) {
    try { var d = new Date(ts); return d.toLocaleString('zh-CN', { hour12: false }); } catch (e) { return ''; }
  }
  function songKey(song) {
    try { if (typeof queueItemKey === 'function') return queueItemKey(song) || ''; } catch (e) { /* ignore */ }
    return String((song && song.name) || '') + '|' + String((song && song.artist) || '');
  }
  function isCloudSong(song) {
    try { if (typeof isCloudSong === 'function') return isCloudSong(song); } catch (e) { /* ignore */ }
    return false;
  }

  var FAV_KEY = 'starwave-local-favorites-v1';
  var PL_KEY = 'starwave-local-playlists-v1';
  var RESUME_KEY = 'starwave-resume-v1';
  var EQ_KEY = 'starwave-eq-v1';
  var LYRIC_OFFSET_KEY = 'starwave-lyric-offset-ms-v1';

  /* 歌曲最小可序列化快照（不含 blob URL、不含 raw 大对象）。 */
  function songSnapshot(song) {
    song = song || {};
    return {
      key: songKey(song),
      provider: song.provider || song.source || '',
      source: song.source || song.provider || '',
      type: song.type || '',
      id: song.id != null ? String(song.id) : '',
      neteaseId: song.neteaseId || song.id || '',
      name: song.name || '',
      artist: song.artist || '',
      album: song.album || '',
      cover: song.cover || '',
      duration: Number(song.duration) || 0,
      fee: song.fee,
      publicAudioUrl: song.publicAudioUrl || '',
      previewUrl: song.previewUrl || '',
      demoLrcUrl: song.demoLrcUrl || '',
      publicLyric: song.publicLyric || '',
      trial: !!song.trial,
      localKey: song.localKey || ''
    };
  }
  /* 快照还原为可播歌曲对象。fresh=true 时丢弃网易云已取地址（跨刷新重取）。 */
  function snapshotToSong(snap, fresh) {
    snap = snap || {};
    var song = {
      provider: snap.provider || snap.source || '',
      source: snap.source || snap.provider || '',
      type: snap.type || '',
      id: snap.id || '',
      neteaseId: snap.neteaseId || snap.id || '',
      name: snap.name || '',
      artist: snap.artist || '',
      album: snap.album || '',
      cover: snap.cover || '',
      duration: Number(snap.duration) || 0,
      fee: snap.fee,
      publicAudioUrl: snap.publicAudioUrl || snap.previewUrl || '',
      previewUrl: snap.previewUrl || '',
      demoLrcUrl: snap.demoLrcUrl || '',
      publicLyric: snap.publicLyric || '',
      trial: !!snap.trial,
      localKey: snap.localKey || '',
      publicSourceLabel: snap.provider === 'demo' ? '演示' : (snap.provider === 'itunes' ? '试听' : (snap.provider === 'netease-web' ? '网易云' : ''))
    };
    if (fresh && (song.provider === 'netease-web' || song.source === 'netease-web')) song.publicAudioUrl = '';
    if (song.localKey && !song.localUrl) song.unrestorable = true; /* 本地文件：刷新后 blob 链接失效，需重新导入 */
    if (song.provider === 'demo') song.unrestorable = true; /* 演示曲目已于 2026-11-10 全部删除，音频文件不存在 */
    return song;
  }
  function demoSongById(id) {
    return null; /* 演示曲目已于 2026-11-10 全部删除；旧历史记录走搜索兜底（见 playHistoryEntry）。 */
  }

  /* ---------- 均衡器：三段（低架 200Hz / 中峰 1kHz / 高架 4kHz） ---------- */
  var eq = { low: 0, mid: 0, high: 0 };
  try {
    var savedEq = JSON.parse(storeGet(EQ_KEY) || 'null') || {};
    if (isFinite(savedEq.low)) eq.low = clamp(savedEq.low, -12, 12);
    if (isFinite(savedEq.mid)) eq.mid = clamp(savedEq.mid, -12, 12);
    if (isFinite(savedEq.high)) eq.high = clamp(savedEq.high, -12, 12);
  } catch (e) { /* ignore */ }
  function applyEqToNodes(nodes) {
    if (!nodes) return;
    try { if (nodes.low) nodes.low.gain.value = eq.low; } catch (e) { /* ignore */ }
    try { if (nodes.mid) nodes.mid.gain.value = eq.mid; } catch (e) { /* ignore */ }
    try { if (nodes.high) nodes.high.gain.value = eq.high; } catch (e) { /* ignore */ }
  }
  function applyEq() {
    applyEqToNodes(window.starwaveEqNodes); /* initAudio 原生链路（本地文件等） */
    applyEqToNodes(p3.eq); /* Phase 3 直连链路（同源） */
    storeSet(EQ_KEY, JSON.stringify(eq));
  }
  function setBand(band, db) {
    if (band !== 'low' && band !== 'mid' && band !== 'high') return null;
    eq[band] = clamp(db, -12, 12);
    applyEq();
    syncEqUi();
    return { band: band, db: eq[band], bands: { low: eq.low, mid: eq.mid, high: eq.high } };
  }
  function resetEq() {
    eq.low = 0; eq.mid = 0; eq.high = 0;
    applyEq();
    syncEqUi();
    toast('均衡器已复位');
    return { low: 0, mid: 0, high: 0 };
  }
  function eqState() {
    return {
      bands: { low: eq.low, mid: eq.mid, high: eq.high },
      nativeNodes: !!window.starwaveEqNodes,
      directNodes: !!(p3.eq),
      analyserMode: analyserMode()
    };
  }

  /* ---------- 真实频谱：Phase 3 直连分析链路 ---------- */
  /* 背景：基线对网易云/iTunes 走 audioDirectMode，不建 AudioContext，
   * 全局 analyser 恒为 null，频谱是 updateDirectAudioPulse 合成的“假脉冲”。
   * 本模块只对同源音频与 blob（本地文件）建真实 MediaElementSource；
   * 跨域（网易云/iTunes）无 CORS 会静音，保留合成脉冲并如实标注 synthetic。 */
  var p3 = {
    ctx: null, eq: null, analyser: null, beatAnalyser: null, gain: null,
    sourceNode: null, element: null, lastAttachError: '',
    zeroFrames: 0, lastKick: 0, lastOnsetAt: 0, onsets: [], bpm: 0, bpmConfidence: 0,
    beatSrc: '', lastTdRms: 0,
    realMode: 'none', lastSampleAt: 0
  };
  function p3Detach() {
    if (p3.sourceNode) { try { p3.sourceNode.disconnect(); } catch (e) { /* ignore */ } }
    p3.sourceNode = null;
    p3.element = null;
  }
  function p3Attach() {
    var a = window.audio;
    if (!a || !a.src) return false;
    if (p3.element === a && p3.sourceNode) return true;
    try {
      var AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) { p3.lastAttachError = '无 AudioContext'; return false; }
      if (!p3.ctx) p3.ctx = new AC();
      if (p3.ctx.state === 'suspended') p3.ctx.resume().catch(function () { /* ignore */ });
      p3Detach();
      var srcNode = p3.ctx.createMediaElementSource(a);
      if (!p3.eq) {
        var low = p3.ctx.createBiquadFilter(); low.type = 'lowshelf'; low.frequency.value = 200;
        var mid = p3.ctx.createBiquadFilter(); mid.type = 'peaking'; mid.frequency.value = 1000; mid.Q.value = 0.9;
        var high = p3.ctx.createBiquadFilter(); high.type = 'highshelf'; high.frequency.value = 4000;
        p3.eq = { low: low, mid: mid, high: high };
        p3.analyser = p3.ctx.createAnalyser();
        p3.analyser.fftSize = 2048; p3.analyser.smoothingTimeConstant = 0.58;
        p3.beatAnalyser = p3.ctx.createAnalyser();
        p3.beatAnalyser.fftSize = 2048; p3.beatAnalyser.smoothingTimeConstant = 0.10;
        p3.gain = p3.ctx.createGain(); p3.gain.gain.value = 1;
        applyEqToNodes(p3.eq);
      }
      srcNode.connect(p3.eq.low);
      p3.eq.low.connect(p3.eq.mid);
      p3.eq.mid.connect(p3.eq.high);
      p3.eq.high.connect(p3.analyser);
      p3.analyser.connect(p3.gain);
      p3.gain.connect(p3.ctx.destination);
      srcNode.connect(p3.beatAnalyser);
      p3.sourceNode = srcNode;
      p3.element = a;
      a.__sw3P3Attached = true; /* 标记：该元素已接 Phase 3 直连图，initAudio 不可再绑它（否则抛错） */
      p3.lastAttachError = '';
      return true;
    } catch (e) {
      p3.lastAttachError = String((e && e.message) || e);
      return false;
    }
  }
  function isSameOriginSrc(src) {
    try {
      var u = new URL(src, window.location.href);
      return u.origin === window.location.origin || u.protocol === 'blob:';
    } catch (e) { return false; }
  }
  /* 选当前可用的真实 analyser：优先 Phase 3 直连，其次原生 initAudio 链路。 */
  function activeRealAnalyser() {
    var a = window.audio;
    if (!a || !a.src || a.paused) return null;
    if (p3.element === a && p3.analyser) return { node: p3.analyser, beat: p3.beatAnalyser, mode: 'p3' };
    if (!window.audioDirectMode && window.analyser && window.audioCtx) {
      return { node: window.analyser, beat: window.beatAnalyser, mode: 'native' };
    }
    if (window.audioDirectMode && isSameOriginSrc(a.src)) {
      if (p3Attach()) return { node: p3.analyser, beat: p3.beatAnalyser, mode: 'p3' };
    }
    return null;
  }
  function analyserMode() {
    var a = window.audio;
    if (!a || !a.src) return 'none';
    if (p3.element === a && p3.analyser) return 'p3';
    if (!window.audioDirectMode && window.analyser) return 'native';
    if (window.audioDirectMode) return isSameOriginSrc(a.src) ? 'p3-pending' : 'synthetic';
    return 'none';
  }
  function bandRms(data, sampleRate, fftSize, hz0, hz1) {
    var binHz = sampleRate / fftSize;
    var lo = Math.max(1, Math.floor(hz0 / binHz));
    var hi = Math.min(data.length - 1, Math.ceil(hz1 / binHz));
    var sum = 0, n = 0;
    for (var i = lo; i <= hi; i++) { var v = data[i] / 255; sum += v * v; n++; }
    return n ? Math.sqrt(sum / n) : 0;
  }
  /* 频段峰值（最大 bin）：kick 检测用。RMS 会被频段内近乎空的 bin 稀释
     （55Hz kick 只占 bin2–3，6 个 bin 的 RMS 峰值仅 0.4 左右、底噪 0.3，
     上升沿不够锐利会漏检）；峰值在 kick 处约 0.78、间隙约 0.06，对比 13 倍。 */
  function bandPeak(data, sampleRate, fftSize, hz0, hz1) {
    var binHz = sampleRate / fftSize;
    var lo = Math.max(1, Math.floor(hz0 / binHz));
    var hi = Math.min(data.length - 1, Math.ceil(hz1 / binHz));
    var peak = 0;
    for (var i = lo; i <= hi; i++) { if (data[i] / 255 > peak) peak = data[i] / 255; }
    return peak;
  }
  /* 用真实频谱驱动与原生分支相同的视觉变量；返回 true 表示已接管本帧。 */
  function sampleRealAnalyser(dt) {
    var act = activeRealAnalyser();
    if (!act) return false;
    var a = window.audio;
    /* Phase 3 修复：换曲时清空 onset 历史。旧代码把上一首歌的 onset 时间戳
       留在数组里，跨曲目的巨大间隔（几秒~几十秒）会污染中位间隔，BPM 恒为 0。 */
    var srcNow = a.src || '';
    if (p3.beatSrc !== srcNow) {
      p3.beatSrc = srcNow;
      p3.onsets = []; p3.bpm = 0; p3.bpmConfidence = 0; p3.lastOnsetAt = 0;
    }
    try {
      if (act.node) act.node.getByteFrequencyData(window.frequencyData);
      if (act.node) act.node.getByteTimeDomainData(window.timeDomainData);
    } catch (e) { return false; }
    var freq = window.frequencyData;
    var max = 0, sum = 0;
    for (var i = 0; i < freq.length; i++) { if (freq[i] > max) max = freq[i]; sum += freq[i]; }
    /* 时域能量（onset 检测用）：频域数据会被 AnalyserNode 的平滑拖出
       持续底噪（同节点实测：kick 间隙频域 bin2 最低 142，时域 RMS 仅 0.005），
       故 kick 检测改用未平滑的时域 RMS；频域仍用于视觉频谱。 */
    var td = window.timeDomainData;
    var tdSum = 0;
    for (var ti = 0; ti < td.length; ti++) { var dv = (td[ti] - 128) / 128; tdSum += dv * dv; }
    var tdRms = td.length ? Math.sqrt(tdSum / td.length) : 0;
    if (max <= 0) {
      p3.zeroFrames++;
      p3.lastTdRms = tdRms;
      /* 原生链路若长期零数据（元素被换过、source 绑定旧元素），改走 Phase 3 直连补救 */
      if (act.mode === 'native' && p3.zeroFrames > 90 && !window.audioDirectMode) {
        if (p3Attach()) { p3.zeroFrames = 0; return sampleRealAnalyser(dt); }
      }
      return true; /* 已采样（静音段也可能全零），不回退到合成脉冲 */
    }
    p3.zeroFrames = 0;
    var sr = (act.mode === 'p3' ? (p3.ctx && p3.ctx.sampleRate) : (window.audioCtx && window.audioCtx.sampleRate)) || 44100;
    var fft = act.node.fftSize || 2048;
    /* Kick 从 beatAnalyser 读：它的 smoothingTimeConstant 是 0.10（主 analyser
       为 0.58，能量衰减慢，相邻 kick 之间涨不到 22% 触发阈值，会漏检约 1/3
       的 kick，中位间隔被拉到 ~1.0s，90 BPM 只能估出 ~56）。 */
    var beatArr = null;
    if (act.beat) {
      try {
        if (!p3._beatArr || p3._beatArr.length !== (act.beat.frequencyBinCount || 1024)) {
          p3._beatArr = new Uint8Array(act.beat.frequencyBinCount || 1024);
        }
        act.beat.getByteFrequencyData(p3._beatArr);
        beatArr = p3._beatArr;
      } catch (e) { beatArr = null; }
    }
    var kick = bandRms(beatArr || freq, sr, fft, 52, 165);
    /* onset 检测用频段峰值（见 bandPeak 注释），视觉平滑仍用 RMS kick。 */
    var kickPeak = bandPeak(beatArr || freq, sr, fft, 52, 165);
    var body = bandRms(freq, sr, fft, 165, 420);
    var vocal = bandRms(freq, sr, fft, 420, 2600);
    var treble = bandRms(freq, sr, fft, 6000, 16000);
    var energy = (kick + body + vocal) / 3;
    dt = Math.max(0.001, Math.min(0.08, dt || 0.016));
    function follow(cur, next, up, down) {
      var tau = next > cur ? up : down;
      return cur + (next - cur) * (1 - Math.exp(-dt / Math.max(0.001, tau)));
    }
    try {
      window.smoothBass = follow(window.smoothBass || 0, kick, 0.02, 0.09);
      window.smoothMid = follow(window.smoothMid || 0, vocal, 0.025, 0.10);
      window.smoothTreb = follow(window.smoothTreb || 0, treble, 0.02, 0.09);
      window.smoothEnergy = follow(window.smoothEnergy || 0, energy, 0.02, 0.10);
      window.bass = window.smoothBass; window.mid = window.smoothMid; window.treble = window.smoothTreb;
      window.audioEnergy = window.smoothEnergy;
      window.bassPeak = Math.max((window.bassPeak || 0.12) * 0.994, kick, 0.03);
      window.midPeak = Math.max((window.midPeak || 0.10) * 0.993, vocal, 0.026);
      window.treblePeak = Math.max((window.treblePeak || 0.08) * 0.993, treble, 0.02);
      window.energyPeak = Math.max((window.energyPeak || 0.10) * 0.994, energy, 0.03);
      /* Kick 上升沿 → beatPulse + BPM 估计。门限用时域 RMS 上穿 0.03：
         kick 文件实测：burst 内时域 RMS 0.06–0.41（采样相位不同），间隙仅
         0.005–0.01；0.03 既在间隙之上，又让每次 kick 后 ~0.3s 的窗口都能
         被 2–4Hz 的无头采样抓到（0.08 的窗口仅 ~0.15s，漏检近 2/3）。 */
      var now = performance.now() / 1000;
      var prevTd = p3.lastTdRms;
      p3.lastTdRms = tdRms;
      var prevKick = p3.lastKick;
      p3.lastKick = kickPeak;
      if (tdRms > 0.03 && prevTd <= 0.03 && (now - p3.lastOnsetAt) > 0.24) {
        window.beatPulse = Math.max(window.beatPulse || 0, Math.min(1, kickPeak * 1.6));
        window.beatOnsetFlag = true;
        p3.lastOnsetAt = now;
        p3.onsets.push(now);
        if (p3.onsets.length > 16) p3.onsets.shift();
        if (p3.onsets.length >= 5) {
          /* 只取合理拍间隔（0.25–2.0s，即 30–240 BPM 区间）；丢弃漏检/卡顿
             造成的超长间隔，避免中位数被拉出 0.3–1.2s 的有效窗口。 */
          var gaps = [];
          for (var g = 1; g < p3.onsets.length; g++) {
            var gap = p3.onsets[g] - p3.onsets[g - 1];
            if (gap >= 0.25 && gap <= 2.0) gaps.push(gap);
          }
          if (gaps.length >= 4) {
            gaps.sort(function (x, y) { return x - y; });
            var med = gaps[Math.floor(gaps.length / 2)];
            if (med >= 0.3 && med <= 1.2) {
              p3.bpm = Math.round(60 / med);
              var spread = gaps[gaps.length - 1] - gaps[0];
              p3.bpmConfidence = Math.max(0, Math.min(1, 1 - spread / 0.6)) * Math.min(1, p3.onsets.length / 8);
            }
          }
        }
      } else {
        window.beatPulse = Math.max(0, (window.beatPulse || 0) * Math.pow(0.5, dt * 6));
      }
      window.lyricSunTarget = Math.max((window.lyricSunTarget || 0) * 0.94, Math.max(0, (window.smoothMid || 0) - 0.14) * 0.45);
    } catch (e) { /* ignore */ }
    p3.realMode = act.mode;
    p3.lastSampleAt = Date.now();
    return true;
  }
  /* 包裹基线 updateDirectAudioPulse：有真实频谱时接管，否则走原合成脉冲。 */
  (function wrapDirectPulse() {
    if (typeof updateDirectAudioPulse !== 'function') return;
    var orig = updateDirectAudioPulse;
    updateDirectAudioPulse = function (dt) {
      try { if (sampleRealAnalyser(dt)) return true; } catch (e) { /* ignore */ }
      return orig(dt);
    };
  })();
  function spectrumSample() {
    var a = window.audio;
    var out = {
      mode: analyserMode(), playing: !!(a && !a.paused),
      audioDirectMode: !!window.audioDirectMode,
      max: 0, mean: 0, low: 0, mid: 0, high: 0, bins: [], attachError: p3.lastAttachError
    };
    var act = null;
    try { act = activeRealAnalyser(); } catch (e) { /* ignore */ }
    if (!act || !act.node || !a || a.paused) return out;
    var arr = new Uint8Array(act.node.frequencyBinCount || 1024);
    try { act.node.getByteFrequencyData(arr); } catch (e) { return out; }
    var sum = 0, max = 0;
    for (var i = 0; i < arr.length; i++) { sum += arr[i]; if (arr[i] > max) max = arr[i]; }
    out.max = max;
    out.mean = arr.length ? sum / arr.length : 0;
    out.bins = Array.prototype.slice.call(arr.slice(0, 24));
    var sr = (act.mode === 'p3' ? (p3.ctx && p3.ctx.sampleRate) : (window.audioCtx && window.audioCtx.sampleRate)) || 44100;
    var fft = act.node.fftSize || 2048;
    out.low = bandRms(arr, sr, fft, 52, 165);
    out.mid = bandRms(arr, sr, fft, 420, 2600);
    out.high = bandRms(arr, sr, fft, 6000, 16000);
    return out;
  }
  function beatInfo() {
    var s = spectrumSample();
    var gaps = [];
    for (var gi = 1; gi < p3.onsets.length; gi++) {
      gaps.push(Math.round((p3.onsets[gi] - p3.onsets[gi - 1]) * 100) / 100);
    }
    return {
      mode: s.mode, playing: s.playing,
      kick: p3.lastKick, bpm: p3.bpm, bpmConfidence: Math.round(p3.bpmConfidence * 100) / 100,
      onsets: p3.onsets.length, lastOnsetAt: p3.lastOnsetAt, gaps: gaps,
      low: s.low, mid: s.mid, high: s.high, max: s.max,
      note: s.mode === 'synthetic' ? '跨域音频无 CORS，频谱为合成脉冲，BPM/Kick 仅同源/本地曲可用' : ''
    };
  }
  /* 手动驱动一次真实频谱 + 节拍采样（供定时器/验证调用；正常由 rAF 包裹
     updateDirectAudioPulse 驱动。无头环境 rAF 只有 1–5fps，onset 时间会被
     量化到帧间隔，BPM 无法收敛；10Hz 手动采样可恢复真实节拍分辨率。） */
  function sampleBeat() {
    try { sampleRealAnalyser(0.1); } catch (e) { /* ignore */ }
    return beatInfo();
  }
  function tryAttachAnalyser() {
    try {
      var a = window.audio;
      if (!a || !a.src || a.paused) return;
      if (window.audioDirectMode && isSameOriginSrc(a.src)) p3Attach();
    } catch (e) { /* ignore */ }
  }

  /* ---------- 本地文件进队列：基线 handleFiles 只直播不进队列 ---------- */
  function isLocalQueueSong(song) {
    if (!song) return false;
    if (song.localUrl || song.type === 'local') return true;
    try { if (typeof songProviderKey === 'function') return songProviderKey(song) === 'local'; } catch (e) { /* ignore */ }
    return false;
  }
  function playLocalQueueSong(idx, opts) {
    opts = opts || {};
    var song = (window.playQueue || [])[idx];
    if (!song || !song.localUrl) {
      toast('本地文件需重新导入：刷新页面后本地文件链接失效');
      return Promise.resolve(false);
    }
    try { if (typeof finalizeListenSession === 'function') finalizeListenSession(false); } catch (e) { /* ignore */ }
    try { if (window.audio && !window.audio.paused) window.audio.pause(); } catch (e) { /* ignore */ }
    window.trackSwitchToken = (window.trackSwitchToken || 0) + 1;
    var token = window.trackSwitchToken;
    window.currentIdx = idx;
    window.audioDirectMode = false;
    /* 该元素若已被 Phase 3 直连图接管（同源音频），initAudio 无法再绑它：换新元素。
     * （createMediaElementSource 对同一元素只允许一次，跨 AudioContext 会抛错。） */
    if (window.audio && window.audio.__sw3P3Attached) {
      try { if (!window.audio.paused) window.audio.pause(); } catch (e) { /* ignore */ }
      window.audio = null;
    }
    /* 复用同一个 audio 元素：initAudio 的 MediaElementSource 只绑定首次出现的元素，
     * 反复 new Audio 会让均衡/频谱链路失效（基线 handleFiles 的旧坑）。 */
    var boundEl = window.__sw3BoundAudio;
    if (boundEl && boundEl !== window.audio) {
      try { if (window.audio && !window.audio.paused) window.audio.pause(); } catch (e) { /* ignore */ }
      window.audio = boundEl;
    }
    if (!window.audio) window.audio = new Audio();
    var a = window.audio;
    try { a.crossOrigin = 'anonymous'; } catch (e) { /* ignore */ }
    try { if (typeof bindPlaybackProgressEvents === 'function') bindPlaybackProgressEvents(a); } catch (e) { /* ignore */ }
    try { if (typeof applyVolumeToAudio === 'function') applyVolumeToAudio(); } catch (e) { /* ignore */ }
    a.src = song.localUrl;
    try {
      var t1 = $('thumb-title'); if (t1) t1.textContent = song.name || '';
      var t2 = $('thumb-artist'); if (t2) t2.textContent = song.artist || '';
      var tw = $('thumb-wrap'); if (tw) tw.classList.add('visible');
      if (typeof updateControlTrackInfo === 'function') updateControlTrackInfo(song);
      if (typeof updateLikeButtons === 'function') updateLikeButtons(song);
      var hint = $('hint'); if (hint) hint.classList.add('hidden');
    } catch (e) { /* ignore */ }
    try {
      if (typeof setOriginalLyricsState === 'function') setOriginalLyricsState(withLyricFallback([]), false, 'fallback');
      if (typeof applyPreferredLyricsForCurrent === 'function') applyPreferredLyricsForCurrent(true);
    } catch (e) { /* ignore */ }
    try { if (typeof safeRenderQueuePanel === 'function') safeRenderQueuePanel('play-local-queue'); } catch (e) { /* ignore */ }
    a.onended = function () {
      if (token !== window.trackSwitchToken) return;
      try { if (typeof finalizeListenSession === 'function') finalizeListenSession(true); } catch (e) { /* ignore */ }
      if (window.playMode === 'single') { playQueueAt(window.currentIdx, { autoRepeat: true }); }
      else if (typeof nextTrack === 'function') nextTrack();
    };
    a.onerror = function () {
      if (token !== window.trackSwitchToken) return;
      toast('本地文件加载失败：' + (song.name || ''));
    };
    try { if (typeof scheduleAudioResumePosition === 'function') scheduleAudioResumePosition(a, opts.resumeAt, token); } catch (e) { /* ignore */ }
    try { a.load(); } catch (e) { /* ignore */ }
    var started = (typeof playAudio === 'function') ? playAudio() : Promise.resolve(false);
    return Promise.resolve(started).then(function (ok) {
      if (ok) {
        window.__sw3BoundAudio = window.audio;
        try { if (typeof beginListenSession === 'function') beginListenSession(song, null); } catch (e) { /* ignore */ }
      } else {
        toast('播放启动失败，请重新选择歌曲');
      }
      tryAttachAnalyser();
      saveResume(true);
      return !!ok;
    });
  }
  (function wrapPlayQueueAt() {
    if (typeof playQueueAt !== 'function') return;
    var orig = playQueueAt;
    playQueueAt = function (idx, opts) {
      var song = (typeof playQueue !== 'undefined' && playQueue[idx]) || null;
      if (song && isLocalQueueSong(song)) return playLocalQueueSong(idx, opts);
      var r = orig(idx, opts);
      if (r && typeof r.then === 'function') {
        return r.then(function (v) { tryAttachAnalyser(); saveResume(true); return v; });
      }
      tryAttachAnalyser();
      saveResume(true);
      return r;
    };
  })();
  (function wrapHandleFiles() {
    if (typeof handleFiles !== 'function') return;
    var orig = handleFiles;
    handleFiles = function (files) {
      /* 与 playLocalQueueSong 同理：被 Phase 3 直连图接管过的元素不能再给 initAudio，
       * 否则 createMediaElementSource 抛错导致本地导入播不起来（Phase 3 回归，2026-11-09 实测）。 */
      if (window.audio && window.audio.__sw3P3Attached) {
        try { if (!window.audio.paused) window.audio.pause(); } catch (e) { /* ignore */ }
        window.audio = null;
      }
      var r = orig(files);
      try {
        var s = window.currentLocalSong;
        if (s && s.localUrl) {
          var key = songKey(s);
          var existing = -1;
          for (var i = 0; i < (window.playQueue || []).length; i++) {
            if (songKey(window.playQueue[i]) === key) { existing = i; break; }
          }
          if (existing >= 0) { window.currentIdx = existing; }
          else {
            window.playQueue.push(Object.assign({}, s));
            window.currentIdx = window.playQueue.length - 1;
          }
          if (typeof safeRenderQueuePanel === 'function') safeRenderQueuePanel('local-file-queue');
        }
      } catch (e) { /* ignore */ }
      return r;
    };
  })();

  /* ---------- 播放队列操作 ---------- */
  function queueState() {
    var q = window.playQueue || [];
    return {
      length: q.length,
      currentIdx: window.currentIdx,
      current: (q[window.currentIdx] || null) ? { name: q[window.currentIdx].name, artist: q[window.currentIdx].artist, provider: q[window.currentIdx].provider || q[window.currentIdx].source } : null,
      mode: window.playMode,
      items: q.map(function (s) { return (s && s.name) || ''; })
    };
  }
  function moveQueueItem(i, dir) {
    i = Number(i); dir = Number(dir) || 0;
    var q = window.playQueue || [];
    var j = i + dir;
    if (!isFinite(i) || i < 0 || i >= q.length || j < 0 || j >= q.length || dir === 0) return false;
    var tmp = q[i]; q[i] = q[j]; q[j] = tmp;
    if (window.currentIdx === i) window.currentIdx = j;
    else if (window.currentIdx === j) window.currentIdx = i;
    try { if (typeof safeRenderQueuePanel === 'function') safeRenderQueuePanel('move-queue'); } catch (e) { /* ignore */ }
    return true;
  }
  function addToQueue(song, position) {
    if (!song) return -1;
    try {
      if (position === 'next' && typeof queueSongNext === 'function') return queueSongNext(song);
      if (typeof queueSong === 'function') return queueSong(song, {});
    } catch (e) { /* ignore */ }
    window.playQueue.push(Object.assign({}, song));
    try { if (typeof safeRenderQueuePanel === 'function') safeRenderQueuePanel('add-queue'); } catch (e) { /* ignore */ }
    return window.playQueue.length - 1;
  }
  function setPlayMode(m) {
    if (['loop', 'shuffle', 'single'].indexOf(m) < 0) return false;
    window.playMode = m;
    try { if (typeof updatePlayModeButton === 'function') updatePlayModeButton(true); } catch (e) { /* ignore */ }
    try { toast('播放模式: ' + (typeof playModeLabel === 'function' ? playModeLabel(m) : m)); } catch (e) { /* ignore */ }
    return true;
  }

  /* ---------- 断点续播：队列 + 曲目 + 进度存本机 ---------- */
  var resumeSaveTimer = null;
  function snapshotQueueForResume() {
    return (window.playQueue || []).map(function (s) {
      var snap = songSnapshot(s);
      if (snap.localKey) return null; /* 本地文件 blob 链接跨刷新失效，不存 */
      if (snap.provider === 'netease-web' || snap.source === 'netease-web') delete snap.publicAudioUrl;
      return snap;
    }).filter(Boolean);
  }
  function saveResume(force) {
    try {
      var a = window.audio;
      if (!a || !a.src || !(window.playQueue || []).length || window.currentIdx < 0) return null;
      var t = a.currentTime || 0;
      if (!force && t < 1) return null;
      var q = snapshotQueueForResume();
      if (!q.length) return null;
      var cur = (window.playQueue || [])[window.currentIdx] || {};
      var curLocal = !!(cur.localKey || cur.localUrl);
      var idx = Math.min(window.currentIdx, q.length - 1);
      if (curLocal) idx = q.length - 1; /* 当前是本地文件（跨刷新失效）：断点落在队尾可播曲，不冒充在播它 */
      var data = {
        queue: q, idx: idx, time: curLocal ? 0 : t, playing: curLocal ? false : !a.paused,
        name: (window.playQueue[idx] && window.playQueue[idx].name) || '',
        lastTrackLocal: curLocal,
        savedAt: Date.now()
      };
      storeSet(RESUME_KEY, JSON.stringify(data));
      return data;
    } catch (e) { return null; }
  }
  function resumeState() {
    try {
      var raw = storeGet(RESUME_KEY);
      if (!raw) return { saved: false };
      var d = JSON.parse(raw);
      return { saved: true, name: d.name || '', idx: d.idx, time: d.time, playing: d.playing, queueLen: (d.queue || []).length, savedAt: d.savedAt, lastTrackLocal: !!d.lastTrackLocal };
    } catch (e) { return { saved: false, error: String(e) }; }
  }
  function restoreResume(opts) {
    opts = opts || {};
    var st = resumeState();
    if (!st.saved || !st.queueLen) return { restored: false, reason: 'no_saved_resume' };
    var data;
    try { data = JSON.parse(storeGet(RESUME_KEY)); } catch (e) { return { restored: false, reason: 'parse_failed' }; }
    var idx = Math.min(data.idx || 0, data.queue.length - 1);
    window.playQueue = data.queue.map(function (s) { return snapshotToSong(s, true); });
    window.currentIdx = idx;
    try { if (typeof safeRenderQueuePanel === 'function') safeRenderQueuePanel('resume-restore'); } catch (e) { /* ignore */ }
    if (data.lastTrackLocal) {
      toast('上次在播本地文件（刷新后链接失效，需重新导入），已恢复队列');
      return { restored: true, name: window.playQueue[idx].name || '', idx: idx, resumeAt: 0, queueLen: window.playQueue.length, localTrackSkipped: true };
    }
    var target = Number(data.time) || 0;
    toast('已恢复上次播放：' + (window.playQueue[idx].name || '') + ' · ' + fmtTime(target));
    if (typeof playQueueAt === 'function') {
      playQueueAt(idx, { resumeAt: target, manual: !!opts.manual });
    }
    return { restored: true, name: window.playQueue[idx].name || '', idx: idx, resumeAt: target, queueLen: window.playQueue.length };
  }
  resumeSaveTimer = setInterval(function () { saveResume(false); }, 5000);
  window.addEventListener('beforeunload', function () { saveResume(true); });

  /* ---------- 歌词：时间偏移 ±0.5s 步进 ---------- */
  window.__starwaveLyricOffsetSec = (Number(storeGet(LYRIC_OFFSET_KEY)) || 0) / 1000;
  function lyricOffsetMs() { return Math.round((window.__starwaveLyricOffsetSec || 0) * 1000); }
  function setLyricOffsetMs(ms) {
    ms = clamp(Math.round(Number(ms) || 0), -3000, 3000);
    storeSet(LYRIC_OFFSET_KEY, String(ms));
    window.__starwaveLyricOffsetSec = ms / 1000;
    syncLyricUi();
    return ms;
  }
  function nudgeLyricOffset(deltaMs) { return setLyricOffsetMs(lyricOffsetMs() + (Number(deltaMs) || 0)); }
  function lyricState() {
    var lines = window.lyricsLines || [];
    var cur = window.audio ? (window.audio.currentTime || 0) : 0;
    var t = cur + (window.__starwaveLyricOffsetSec || 0);
    var expected = -1;
    for (var i = 0; i < lines.length; i++) { if (lines[i].t <= t + 0.05) expected = i; else break; }
    var sl = window.stageLyrics || {};
    var hasWords = lines.some(function (l) { return l.words && l.words.length; });
    return {
      offsetMs: lyricOffsetMs(),
      currentTime: Math.round(cur * 100) / 100,
      effectiveTime: Math.round(t * 100) / 100,
      lines: lines.length,
      timingSource: window.lyricsTimingSource || '',
      currentIdx: (sl.currentIdx == null ? null : sl.currentIdx),
      currentText: sl.currentText || '',
      expectedIdx: expected,
      expectedText: expected >= 0 ? (lines[expected].text || '') : '',
      match: expected === sl.currentIdx,
      hasWords: hasWords,
      note: hasWords ? '逐词高亮可用（YRC 词级时间戳）' : '该歌词无词级时间戳，仅行级高亮；逐词进度按行内匀速估算'
    };
  }

  /* ---------- 本地收藏（localStorage，只存本机） ---------- */
  function loadFavorites() {
    try { var raw = JSON.parse(storeGet(FAV_KEY) || '[]'); return Array.isArray(raw) ? raw : []; } catch (e) { return []; }
  }
  function saveFavorites(list) { storeSet(FAV_KEY, JSON.stringify((list || []).slice(0, 200))); }
  function isFavorite(song) {
    var key = songKey(song);
    if (!key) return false;
    return loadFavorites().some(function (f) { return f.key === key; });
  }
  function toggleFavorite(song) {
    if (!song || !song.name) return null;
    var key = songKey(song);
    var list = loadFavorites();
    var idx = -1;
    for (var i = 0; i < list.length; i++) if (list[i].key === key) { idx = i; break; }
    var favorited;
    if (idx >= 0) { list.splice(idx, 1); favorited = false; }
    else { list.unshift({ key: key, song: songSnapshot(song), addedAt: Date.now() }); favorited = true; }
    saveFavorites(list);
    toast(favorited ? '已收藏到本地：' + song.name : '已取消本地收藏：' + song.name);
    refreshFavButtons();
    renderLibraryModal();
    return { favorited: favorited, count: list.length };
  }
  function removeFavorite(key) {
    var list = loadFavorites().filter(function (f) { return f.key !== key; });
    saveFavorites(list);
    refreshFavButtons();
    renderLibraryModal();
    return list.length;
  }
  function listFavorites() { return loadFavorites(); }
  function refreshFavButtons() {
    try {
      var song = (typeof currentCoverSong === 'function') ? currentCoverSong() : ((window.playQueue || [])[window.currentIdx] || null);
      var liked = false;
      if (song) {
        try { liked = (typeof isSongLiked === 'function' && isSongLiked(song)) || isFavorite(song); } catch (e) { liked = isFavorite(song); }
      }
      var btn = $('heart-btn');
      if (btn) { btn.classList.toggle('liked', !!liked); btn.title = liked ? '取消红心' : '红心喜欢'; }
    } catch (e) { /* ignore */ }
  }
  /* Phase 2 缺口修复：红心/收藏不再以“须登录”挡住本地/网易云免费曲——非云端曲走本地收藏。 */
  (function wrapToggleLike() {
    if (typeof toggleLikeSong !== 'function') return;
    var orig = toggleLikeSong;
    toggleLikeSong = function (song) {
      if (song && !isCloudSong(song)) { toggleFavorite(song); return; }
      return orig(song);
    };
  })();
  function playFavorite(i) {
    var list = loadFavorites();
    var fav = list[i];
    if (!fav) return false;
    var song = snapshotToSong(fav.song, true);
    if (song.unrestorable) { toast(song.provider === 'demo' ? '演示曲目已删除' : '本地文件需重新导入：刷新页面后本地文件链接失效'); return false; }
    window.playQueue = [song];
    window.currentIdx = 0;
    try { if (typeof safeRenderQueuePanel === 'function') safeRenderQueuePanel('play-favorite'); } catch (e) { /* ignore */ }
    if (typeof playQueueAt === 'function') playQueueAt(0, { manual: true });
    return true;
  }

  /* ---------- 播放历史（基线 listenStatsState，只存本机） ---------- */
  function historyState() {
    var st = window.listenStatsState || { history: [], songs: {}, artists: {} };
    var songs = st.songs || {};
    var totalPlays = 0;
    Object.keys(songs).forEach(function (k) { totalPlays += (songs[k] && songs[k].plays) || 0; });
    var top = null;
    try { if (typeof mostPlayedSong === 'function') top = mostPlayedSong(); } catch (e) { /* ignore */ }
    return {
      entries: (st.history || []).slice(),
      totalPlays: totalPlays,
      totalSongs: Object.keys(songs).length,
      topSong: top ? { name: top.name, artist: top.artist, plays: top.plays } : null,
      /* 计入规则（基线）：一次会话听满 45 秒，或进度 ≥50%，或播完，才记 1 次 */
      rule: '听满45秒 / 进度≥50% / 播完，记1次'
    };
  }
  function clearHistory() {
    try {
      if (window.listenStatsState) {
        window.listenStatsState.history = [];
        window.listenStatsState.songs = {};
        window.listenStatsState.artists = {};
      }
      if (typeof saveListenStatsState === 'function') saveListenStatsState();
    } catch (e) { /* ignore */ }
    toast('播放历史已清空（只清本机）');
    renderLibraryModal();
    return historyState();
  }
  function playHistoryEntry(i) {
    var st = historyState();
    var rec = st.entries[i];
    if (!rec) return false;
    var key = (rec.sourceKey || rec.provider || '').toLowerCase();
    var song = null;
    if (key === 'demo' && rec.id) song = demoSongById(String(rec.id));
    if (!song && (key === 'netease-web' || key === 'netease')) {
      song = { provider: 'netease-web', source: 'netease-web', type: 'netease-web', id: rec.id, neteaseId: rec.id, name: rec.name, artist: rec.artist, album: '', cover: rec.cover || '', duration: rec.duration || 0, publicSourceLabel: '网易云' };
    }
    if (!song) {
      toast('该历史记录无可播地址，已改为搜索同名歌曲');
      try { if (typeof runHomeSearch === 'function') runHomeSearch(rec.name || ''); } catch (e) { /* ignore */ }
      return false;
    }
    window.playQueue = [song];
    window.currentIdx = 0;
    try { if (typeof safeRenderQueuePanel === 'function') safeRenderQueuePanel('play-history'); } catch (e) { /* ignore */ }
    if (typeof playQueueAt === 'function') playQueueAt(0, { manual: true });
    return true;
  }

  /* ---------- 本地歌单（localStorage，只存本机） ---------- */
  function loadLocalPlaylists() {
    try { var raw = JSON.parse(storeGet(PL_KEY) || '[]'); return Array.isArray(raw) ? raw : []; } catch (e) { return []; }
  }
  function saveLocalPlaylists(list) { storeSet(PL_KEY, JSON.stringify((list || []).slice(0, 50))); }
  function findLocalPlaylist(id) {
    id = String(id || '');
    var list = loadLocalPlaylists();
    for (var i = 0; i < list.length; i++) if (String(list[i].id) === id) return list[i];
    return null;
  }
  function localPlaylistRecord(pl) {
    return {
      id: pl.id, provider: 'local', source: 'local', type: 'playlist',
      name: pl.name, cover: (pl.tracks && pl.tracks[0] && pl.tracks[0].cover) || '',
      trackCount: (pl.tracks || []).length, creator: '本地',
      imported: false, importedAt: pl.createdAt || 0
    };
  }
  function mergeIntoUserPlaylists() {
    try {
      var locals = loadLocalPlaylists();
      if (!window.userPlaylists) window.userPlaylists = [];
      locals.forEach(function (pl) {
        var rec = localPlaylistRecord(pl);
        var found = false;
        for (var i = 0; i < window.userPlaylists.length; i++) {
          if (String(window.userPlaylists[i].id) === String(rec.id)) { window.userPlaylists[i] = rec; found = true; break; }
        }
        if (!found) window.userPlaylists.push(rec);
      });
      if (typeof renderUserPlaylistsList === 'function') renderUserPlaylistsList({});
    } catch (e) { /* ignore */ }
  }
  function listLocalPlaylists() { return loadLocalPlaylists(); }
  function createLocalPlaylist(name, song) {
    name = String(name || '').trim();
    if (!name) { toast('先输入歌单名称'); return null; }
    var list = loadLocalPlaylists();
    var pl = {
      id: 'local:' + Date.now().toString(36) + Math.floor(Math.random() * 1296).toString(36),
      provider: 'local', name: name, tracks: [], createdAt: Date.now(), updatedAt: Date.now()
    };
    if (song) pl.tracks.push(songSnapshot(song));
    list.unshift(pl);
    saveLocalPlaylists(list);
    mergeIntoUserPlaylists();
    toast('本地歌单已创建：' + name);
    renderLibraryModal();
    return pl;
  }
  function renameLocalPlaylist(id, name) {
    name = String(name || '').trim();
    if (!name) return false;
    var list = loadLocalPlaylists();
    for (var i = 0; i < list.length; i++) {
      if (String(list[i].id) === String(id)) {
        list[i].name = name; list[i].updatedAt = Date.now();
        saveLocalPlaylists(list); mergeIntoUserPlaylists(); renderLibraryModal();
        toast('歌单已重命名：' + name);
        return true;
      }
    }
    return false;
  }
  function deleteLocalPlaylist(id) {
    var before = loadLocalPlaylists().length;
    var list = loadLocalPlaylists().filter(function (pl) { return String(pl.id) !== String(id); });
    if (list.length === before) return false;
    saveLocalPlaylists(list);
    try {
      window.userPlaylists = (window.userPlaylists || []).filter(function (pl) { return String(pl.id) !== String(id); });
      if (window.playlistPanelDetailState && String(window.playlistPanelDetailState.key || '').indexOf(String(id)) >= 0) {
        window.playlistPanelDetailState.key = '';
        window.playlistPanelDetailState.tracks = [];
        window.playlistPanelDetailState.playlist = null;
      }
      if (typeof renderUserPlaylistsList === 'function') renderUserPlaylistsList({});
    } catch (e) { /* ignore */ }
    toast('本地歌单已删除');
    renderLibraryModal();
    return true;
  }
  function addToLocalPlaylist(id, song) {
    if (!song || !song.name) return false;
    var list = loadLocalPlaylists();
    for (var i = 0; i < list.length; i++) {
      if (String(list[i].id) === String(id)) {
        var key = songKey(song);
        var exists = (list[i].tracks || []).some(function (t) { return t.key === key; });
        if (exists) { toast('歌曲已在歌单中：' + list[i].name); return false; }
        list[i].tracks.push(songSnapshot(song));
        list[i].updatedAt = Date.now();
        saveLocalPlaylists(list);
        mergeIntoUserPlaylists();
        toast('已加入本地歌单：' + list[i].name);
        renderLibraryModal();
        return true;
      }
    }
    return false;
  }
  function removeFromLocalPlaylist(id, key) {
    var list = loadLocalPlaylists();
    for (var i = 0; i < list.length; i++) {
      if (String(list[i].id) === String(id)) {
        var before = (list[i].tracks || []).length;
        list[i].tracks = (list[i].tracks || []).filter(function (t) { return t.key !== key; });
        if (list[i].tracks.length === before) return false;
        list[i].updatedAt = Date.now();
        saveLocalPlaylists(list);
        mergeIntoUserPlaylists();
        if (window.playlistPanelDetailState && window.playlistPanelDetailState.playlist &&
          String(window.playlistPanelDetailState.playlist.id) === String(id)) {
          window.playlistPanelDetailState.tracks = list[i].tracks.map(function (s) { return snapshotToSong(s); });
          if (typeof renderPlaylistPanelDetailState === 'function') renderPlaylistPanelDetailState();
        }
        renderLibraryModal();
        return true;
      }
    }
    return false;
  }
  function openLocalPlaylist(id) {
    try { if (typeof togglePlaylistPanel === 'function') togglePlaylistPanel(true); } catch (e) { /* ignore */ }
    try { if (typeof switchPlaylistTab === 'function') switchPlaylistTab('playlists'); } catch (e) { /* ignore */ }
    if (typeof openPlaylistPanelDetail === 'function') openPlaylistPanelDetail('local', id, '');
  }
  /* Phase 2 遗留修复：本地歌单详情必须能打开并列出歌曲。 */
  (function wrapOpenPlaylistDetail() {
    if (typeof openPlaylistPanelDetail !== 'function') return;
    var orig = openPlaylistPanelDetail;
    openPlaylistPanelDetail = function (provider, pid, title) {
      var prov = provider;
      try { if (typeof playlistProviderKey === 'function') prov = playlistProviderKey(provider); } catch (e) { /* ignore */ }
      var id = String(pid || '');
      if (prov === 'local' || id.indexOf('local:') === 0) {
        var pl = findLocalPlaylist(id);
        if (!pl) { toast('未找到本地歌单'); return; }
        var key = '';
        try { key = playlistPanelKey('local', pl.id); } catch (e) { key = 'local:' + pl.id; }
        var st = window.playlistPanelDetailState || {};
        if (st.key === key && !st.loading && (st.tracks || []).length) {
          window.playlistPanelDetailState.key = '';
          window.playlistPanelDetailState.tracks = [];
          window.playlistPanelDetailState.playlist = null;
          if (typeof renderPlaylistPanelDetailState === 'function') renderPlaylistPanelDetailState();
          return;
        }
        var token = (st.token || 0) + 1;
        window.playlistPanelDetailState = {
          key: key, loading: false, playlist: localPlaylistRecord(pl),
          tracks: (pl.tracks || []).map(function (s) { return snapshotToSong(s); }),
          token: token, renderLimit: (typeof PLAYLIST_DETAIL_INITIAL_RENDER !== 'undefined' ? PLAYLIST_DETAIL_INITIAL_RENDER : 64)
        };
        if (typeof renderPlaylistPanelDetailState === 'function') renderPlaylistPanelDetailState();
        try { if (typeof scrollPlaylistPanelDetailIntoView === 'function') scrollPlaylistPanelDetailIntoView(key); } catch (e) { /* ignore */ }
        return;
      }
      return orig(provider, pid, title);
    };
  })();
  (function wrapLoadPlaylistIntoQueue() {
    if (typeof loadPlaylistIntoQueueById !== 'function') return;
    var orig = loadPlaylistIntoQueueById;
    loadPlaylistIntoQueueById = async function (id, autoplay, title) {
      id = String(id || '');
      if (id.indexOf('local:') === 0) {
        var pl = findLocalPlaylist(id);
        if (!pl) { toast('未找到本地歌单'); return false; }
        var all = (pl.tracks || []).map(function (s) { return snapshotToSong(s); });
        var tracks = all.filter(function (s) { return !s.unrestorable; });
        var skipped = all.length - tracks.length;
        if (!tracks.length) { toast('本地歌单暂无可播放歌曲' + (skipped ? '（' + skipped + ' 首本地文件需重新导入）' : '')); return false; }
        if (skipped) toast('已跳过 ' + skipped + ' 首需重新导入的本地文件');
        window.playQueue = tracks.map(function (s) { try { return cloneSong(s); } catch (e) { return s; } });
        window.currentIdx = 0;
        try { if (typeof safeRenderQueuePanel === 'function') safeRenderQueuePanel('local-playlist-play'); } catch (e) { /* ignore */ }
        try { if (typeof safeShelfRebuild === 'function') safeShelfRebuild('local-playlist-play', true); } catch (e) { /* ignore */ }
        try { if (typeof forcePlaybackControlsInteractive === 'function') forcePlaybackControlsInteractive(); } catch (e) { /* ignore */ }
        if (autoplay && typeof playQueueAt === 'function') playQueueAt(0, { manual: true });
        return true;
      }
      return orig(id, autoplay, title);
    };
  })();
  (function wrapRefreshUserPlaylists() {
    if (typeof refreshUserPlaylists !== 'function') return;
    var orig = refreshUserPlaylists;
    refreshUserPlaylists = function (force) {
      var r = orig(force);
      if (r && typeof r.then === 'function') {
        return r.then(function (v) { mergeIntoUserPlaylists(); return v; });
      }
      mergeIntoUserPlaylists();
      return r;
    };
  })();
  /* 收藏到歌单：非云端曲走本地歌单，不再弹“本地文件暂不支持收藏”。 */
  var collectTarget = null;
  (function wrapOpenCollectModal() {
    if (typeof openCollectModal !== 'function') return;
    var orig = openCollectModal;
    openCollectModal = function (song) {
      if (song && !isCloudSong(song)) { openLibraryModal('collect', song); return; }
      return orig(song);
    };
  })();
  function addCollectTargetToPlaylist(id) {
    if (!collectTarget) { toast('没有待收藏的歌曲'); return false; }
    var ok = addToLocalPlaylist(id, collectTarget);
    if (ok) { collectTarget = null; }
    return ok;
  }

  /* ---------- 音量 ---------- */
  function volumeState() {
    return {
      target: (typeof targetVolume !== 'undefined') ? targetVolume : null,
      audioVolume: window.audio ? window.audio.volume : null,
      gainNode: window.gainNode ? window.gainNode.gain.value : null,
      audioDirectMode: !!window.audioDirectMode
    };
  }

  /* ---------- 本地曲库弹窗：收藏 / 历史 / 本地歌单 / 音效·歌词 ---------- */
  var libTab = 'favorites';
  var modalCssInjected = false;
  function injectModalCss() {
    if (modalCssInjected) return;
    modalCssInjected = true;
    var st = document.createElement('style');
    st.id = 'starwave-phase3-css';
    st.textContent = [
      '#starwave-phase3-modal .modal{width:min(680px,94vw);max-height:min(820px,calc(100dvh - 64px));overflow:auto;text-align:left}',
      '.sw3-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}',
      '.sw3-tab{padding:7px 14px;border-radius:999px;border:1px solid rgba(255,255,255,.16);background:rgba(255,255,255,.05);color:#fff;font-size:12.5px;cursor:pointer}',
      '.sw3-tab.active{border-color:#00f5d4;color:#00f5d4}',
      '.sw3-row{display:flex;align-items:center;gap:10px;padding:9px 2px;border-bottom:1px solid rgba(255,255,255,.07);font-size:12.5px}',
      '.sw3-row .t{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:rgba(255,255,255,.9)}',
      '.sw3-row .s{color:rgba(255,255,255,.5);font-size:11.5px;white-space:nowrap}',
      '.sw3-row button{background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.14);color:#fff;border-radius:8px;padding:5px 10px;font-size:12px;cursor:pointer;white-space:nowrap}',
      '.sw3-row button.primary{border-color:#00f5d4;color:#00f5d4}',
      '.sw3-empty{padding:22px 0;text-align:center;color:rgba(255,255,255,.4);font-size:12.5px}',
      '.sw3-note{font-size:12px;line-height:1.7;color:rgba(255,255,255,.5);margin:10px 0}',
      '.sw3-note b{color:rgba(255,255,255,.8)}',
      '.sw3-ctl{display:flex;align-items:center;gap:10px;padding:8px 0;font-size:12.5px}',
      '.sw3-ctl label{width:64px;color:rgba(255,255,255,.75);flex-shrink:0}',
      '.sw3-ctl input[type=range]{flex:1;accent-color:#00f5d4}',
      '.sw3-ctl output{width:64px;text-align:right;color:rgba(255,255,255,.8)}',
      '.sw3-ctl button{background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.14);color:#fff;border-radius:8px;padding:5px 10px;font-size:12px;cursor:pointer}',
      '#starwave-phase3-btn{font-size:15px;line-height:1}'
    ].join('\n');
    document.head.appendChild(st);
  }
  function ensureLibraryModal() {
    injectModalCss();
    var m = $('starwave-phase3-modal');
    if (m) return m;
    m = document.createElement('div');
    m.id = 'starwave-phase3-modal';
    m.className = 'modal-mask';
    m.innerHTML = '<div class="modal" role="dialog" aria-modal="true" aria-label="本地曲库">' +
      '<h2>本地曲库</h2>' +
      '<p class="sw3-note">收藏、历史、歌单只存本机（localStorage），不上传、不登录。网易云公开歌单导入需 StarWave Connector 浏览器扩展（当前未检测到），本站不伪造歌单数据。</p>' +
      '<div class="sw3-tabs" id="sw3-tabs"></div>' +
      '<div id="sw3-body"></div>' +
      '<div class="btn-row"><button class="modal-btn" type="button" onclick="window.starwavePhase3.closeLibraryModal()">关闭</button></div>' +
      '</div>';
    document.body.appendChild(m);
    return m;
  }
  function libTabHtml() {
    var tabs = [
      ['favorites', '收藏'], ['history', '历史'], ['playlists', '本地歌单'],
      ['collect', '收藏到歌单'], ['effects', '音效 · 歌词']
    ];
    return tabs.map(function (t) {
      return '<button class="sw3-tab' + (libTab === t[0] ? ' active' : '') + '" type="button" onclick="window.starwavePhase3.openLibraryModal(\'' + t[0] + '\')">' + t[1] + '</button>';
    }).join('');
  }
  function favRowsHtml() {
    var list = loadFavorites();
    if (!list.length) return '<div class="sw3-empty">还没有本地收藏。点歌曲的 ♥ 即可收藏本地 / 网易云免费曲。</div>';
    return list.map(function (f, i) {
      var s = f.song || {};
      return '<div class="sw3-row"><div class="t">' + esc(s.name) + '</div><div class="s">' + esc(s.artist || '') + ' · ' + esc(s.provider || '') + '</div>' +
        '<button type="button" onclick="window.starwavePhase3.playFavorite(' + i + ')">播放</button>' +
        '<button type="button" onclick="window.starwavePhase3.removeFavorite(\'' + esc(f.key) + '\')">取消</button></div>';
    }).join('');
  }
  function historyRowsHtml() {
    var hs = historyState();
    var head = '<div class="sw3-note">共 <b>' + hs.totalPlays + '</b> 次播放 · <b>' + hs.totalSongs + '</b> 首歌' +
      (hs.topSong ? ' · 常听：<b>' + esc(hs.topSong.name) + '</b>（' + hs.topSong.plays + ' 次）' : '') +
      '<br>计入规则：' + esc(hs.rule) + '</div>';
    if (!hs.entries.length) return head + '<div class="sw3-empty">还没有播放历史。播一首歌（听满 45 秒或进度过半）后这里会出现记录。</div>';
    var rows = hs.entries.map(function (r, i) {
      var plays = '';
      try { var songs = (window.listenStatsState && window.listenStatsState.songs) || {}; var st = songs[r.key]; if (st) plays = ' · ' + st.plays + ' 次'; } catch (e) { /* ignore */ }
      return '<div class="sw3-row"><div class="t">' + esc(r.name || '') + '</div><div class="s">' + esc(r.artist || '') + ' · ' + esc(r.source || '') + plays + '<br>' + esc(fmtDate(r.playedAt)) + ' · 听了 ' + esc(fmtTime(Math.round((r.listenMs || 0) / 1000))) + '</div>' +
        '<button type="button" onclick="window.starwavePhase3.playHistoryEntry(' + i + ')">播放</button></div>';
    }).join('');
    return head + rows + '<div style="margin-top:12px"><button class="sw3-tab" type="button" onclick="window.starwavePhase3.clearHistory()">清空历史</button></div>';
  }
  function playlistRowsHtml() {
    var list = loadLocalPlaylists();
    var html = '<div style="display:flex;gap:8px;margin:6px 0 12px"><input id="sw3-new-pl-name" type="text" placeholder="新歌单名称" style="flex:1;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.16);border-radius:8px;color:#fff;padding:8px 10px;font-size:12.5px">' +
      '<button class="sw3-tab" type="button" onclick="window.starwavePhase3.createLocalPlaylistFromInput()">新建歌单</button></div>';
    if (!list.length) return html + '<div class="sw3-empty">还没有本地歌单。新建后，用歌曲的“收藏到歌单”按钮加歌。</div>';
    return html + list.map(function (pl) {
      var n = (pl.tracks || []).length;
      return '<div class="sw3-row"><div class="t">' + esc(pl.name) + '</div><div class="s">' + n + ' 首</div>' +
        '<button type="button" class="primary" onclick="window.starwavePhase3.openLocalPlaylist(\'' + esc(pl.id) + '\')">打开</button>' +
        '<button type="button" onclick="window.starwavePhase3.playLocalPlaylist(\'' + esc(pl.id) + '\')">播放</button>' +
        '<button type="button" onclick="window.starwavePhase3.renameLocalPlaylistPrompt(\'' + esc(pl.id) + '\')">重命名</button>' +
        '<button type="button" onclick="window.starwavePhase3.deleteLocalPlaylist(\'' + esc(pl.id) + '\')">删除</button></div>';
    }).join('') + '<div class="sw3-note">本地歌单详情在左侧“歌单 / 队列 → 本地列表”里打开，列出全部歌曲、可逐首播放。</div>';
  }
  function collectRowsHtml() {
    if (!collectTarget) return '<div class="sw3-empty">没有待收藏的歌曲。先在队列或搜索结果里点“收藏到歌单”。</div>';
    var list = loadLocalPlaylists();
    var head = '<div class="sw3-note">正在收藏：<b>' + esc(collectTarget.name || '') + '</b> · ' + esc(collectTarget.artist || '') + '（本地收藏，不登录网易云）</div>';
    if (!list.length) return head + '<div class="sw3-empty">还没有本地歌单，先在“本地歌单”页新建一个。</div>';
    return head + list.map(function (pl) {
      return '<div class="sw3-row"><div class="t">' + esc(pl.name) + '</div><div class="s">' + (pl.tracks || []).length + ' 首</div>' +
        '<button type="button" class="primary" onclick="window.starwavePhase3.addCollectTargetToPlaylist(\'' + esc(pl.id) + '\')">加入</button></div>';
    }).join('');
  }
  function effectsRowsHtml() {
    var ls = lyricState();
    return '<div class="sw3-ctl"><label>音量</label><input id="sw3-vol" type="range" min="0" max="100" step="1" value="' + Math.round(((typeof targetVolume !== 'undefined' ? targetVolume : 0.8)) * 100) + '"><output id="sw3-vol-out">' + Math.round(((typeof targetVolume !== 'undefined' ? targetVolume : 0.8)) * 100) + '%</output></div>' +
      '<div class="sw3-ctl"><label>低音</label><input id="sw3-eq-low" type="range" min="-12" max="12" step="0.5" value="' + eq.low + '"><output id="sw3-eq-low-out">' + (eq.low > 0 ? '+' : '') + eq.low + ' dB</output></div>' +
      '<div class="sw3-ctl"><label>中音</label><input id="sw3-eq-mid" type="range" min="-12" max="12" step="0.5" value="' + eq.mid + '"><output id="sw3-eq-mid-out">' + (eq.mid > 0 ? '+' : '') + eq.mid + ' dB</output></div>' +
      '<div class="sw3-ctl"><label>高音</label><input id="sw3-eq-high" type="range" min="-12" max="12" step="0.5" value="' + eq.high + '"><output id="sw3-eq-high-out">' + (eq.high > 0 ? '+' : '') + eq.high + ' dB</output></div>' +
      '<div style="margin:4px 0 10px"><button class="sw3-tab" type="button" onclick="window.starwavePhase3.resetEq()">复位均衡器</button></div>' +
      '<div class="sw3-ctl"><label>歌词偏移</label>' +
      '<button type="button" onclick="window.starwavePhase3.nudgeLyricOffset(-500)">−0.5s</button>' +
      '<button type="button" onclick="window.starwavePhase3.nudgeLyricOffset(500)">+0.5s</button>' +
      '<button type="button" onclick="window.starwavePhase3.setLyricOffsetMs(0)">复位</button>' +
      '<output id="sw3-lyric-offset-out">' + (ls.offsetMs > 0 ? '+' : '') + (ls.offsetMs / 1000).toFixed(1) + 's</output></div>' +
      '<div class="sw3-note">当前歌词：' + (ls.currentText ? '“' + esc(ls.currentText) + '”' : '（无）') + ' · 第 ' + (ls.currentIdx == null ? '–' : (ls.currentIdx + 1)) + ' / ' + ls.lines + ' 行 · ' + esc(ls.timingSource || '无歌词') +
      '<br>' + esc(ls.note) + '</div>' +
      '<div class="sw3-note">均衡器走 Web Audio 三段滤波（低架 200Hz / 中峰 1kHz / 高架 4kHz），对本地文件实时生效；网易云/iTunes 跨域音频无 CORS，均衡与频谱均为合成链路，不承诺生效。</div>';
  }
  function renderLibraryModal() {
    var m = $('starwave-phase3-modal');
    if (!m || !m.classList.contains('show')) return;
    var tabs = $('sw3-tabs');
    if (tabs) tabs.innerHTML = libTabHtml();
    var body = $('sw3-body');
    if (!body) return;
    if (libTab === 'favorites') body.innerHTML = favRowsHtml();
    else if (libTab === 'history') body.innerHTML = historyRowsHtml();
    else if (libTab === 'playlists') body.innerHTML = playlistRowsHtml();
    else if (libTab === 'collect') body.innerHTML = collectRowsHtml();
    else if (libTab === 'effects') {
      body.innerHTML = effectsRowsHtml();
      bindEffectsUi();
    }
  }
  function bindEffectsUi() {
    var vol = $('sw3-vol');
    if (vol) vol.addEventListener('input', function () {
      var v = Number(vol.value) / 100;
      try { if (typeof setVolume === 'function') setVolume(v, true); } catch (e) { /* ignore */ }
      var out = $('sw3-vol-out'); if (out) out.textContent = vol.value + '%';
    });
    [['low', 'sw3-eq-low', 'sw3-eq-low-out'], ['mid', 'sw3-eq-mid', 'sw3-eq-mid-out'], ['high', 'sw3-eq-high', 'sw3-eq-high-out']].forEach(function (cfg) {
      var el = $(cfg[1]);
      if (!el) return;
      el.addEventListener('input', function () {
        var v = Number(el.value);
        setBand(cfg[0], v);
        var out = $(cfg[2]); if (out) out.textContent = (v > 0 ? '+' : '') + v + ' dB';
      });
    });
  }
  function syncEqUi() {
    [['low', 'sw3-eq-low', 'sw3-eq-low-out'], ['mid', 'sw3-eq-mid', 'sw3-eq-mid-out'], ['high', 'sw3-eq-high', 'sw3-eq-high-out']].forEach(function (cfg) {
      var el = $(cfg[1]);
      if (el) el.value = eq[cfg[0]];
      var out = $(cfg[2]);
      if (out) out.textContent = (eq[cfg[0]] > 0 ? '+' : '') + eq[cfg[0]] + ' dB';
    });
  }
  function syncLyricUi() {
    var out = $('sw3-lyric-offset-out');
    if (out) out.textContent = (lyricOffsetMs() > 0 ? '+' : '') + (lyricOffsetMs() / 1000).toFixed(1) + 's';
  }
  function openLibraryModal(tab, song) {
    if (tab) libTab = tab;
    if (song) collectTarget = songSnapshot(song);
    ensureLibraryModal();
    renderLibraryModal();
    var m = $('starwave-phase3-modal');
    if (typeof openGsapModal === 'function') openGsapModal(m);
    else m.classList.add('show');
    renderLibraryModal();
  }
  function closeLibraryModal() {
    var m = $('starwave-phase3-modal');
    if (!m) return;
    if (typeof closeGsapModal === 'function') closeGsapModal(m);
    else m.classList.remove('show');
    collectTarget = null;
  }
  (function addLibraryButton() {
    var topRight = $('top-right');
    var userBtn = $('user-btn');
    if (!topRight || !userBtn || $('starwave-phase3-btn')) return;
    var b = document.createElement('button');
    b.id = 'starwave-phase3-btn';
    b.className = 'icon-btn';
    b.type = 'button';
    b.title = '本地曲库（收藏 / 历史 / 歌单 / 音效）';
    b.setAttribute('aria-label', '本地曲库');
    b.textContent = '★';
    b.addEventListener('click', function () { openLibraryModal('favorites'); });
    topRight.insertBefore(b, userBtn);
  })();

  /* ---------- 对外 API（供验证与界面调用） ---------- */
  window.starwavePhase3 = {
    version: '0.3.0-phase3',
    /* 播放链路 / 队列 */
    queueState: queueState,
    moveQueueItem: moveQueueItem,
    addToQueue: addToQueue,
    setPlayMode: setPlayMode,
    playMode: function () { return window.playMode; },
    next: function () { if (typeof nextTrack === 'function') nextTrack(); },
    prev: function () { if (typeof prevTrack === 'function') prevTrack(); },
    clearQueue: function () { if (typeof clearQueue === 'function') clearQueue(); },
    demoSongs: function () {
      try { if (typeof buildStarwaveDemoSongs === 'function') return buildStarwaveDemoSongs(); } catch (e) { /* ignore */ }
      return Promise.resolve([]);
    },
    /* 断点续播 */
    saveResume: saveResume,
    restoreResume: restoreResume,
    resumeState: resumeState,
    /* 歌词 */
    lyricOffsetMs: lyricOffsetMs,
    setLyricOffsetMs: setLyricOffsetMs,
    nudgeLyricOffset: nudgeLyricOffset,
    lyricState: lyricState,
    /* 频谱 / 节拍 / 音效 */
    spectrumSample: spectrumSample,
    beatInfo: beatInfo,
    sampleBeat: sampleBeat,
    analyserMode: analyserMode,
    eqState: eqState,
    setBand: setBand,
    resetEq: resetEq,
    volumeState: volumeState,
    setVolume: function (v) { try { if (typeof setVolume === 'function') setVolume(v, false); } catch (e) { /* ignore */ } return volumeState(); },
    /* 收藏 */
    toggleFavorite: toggleFavorite,
    isFavorite: isFavorite,
    listFavorites: listFavorites,
    removeFavorite: removeFavorite,
    playFavorite: playFavorite,
    /* 历史 */
    historyState: historyState,
    clearHistory: clearHistory,
    playHistoryEntry: playHistoryEntry,
    /* 本地歌单 */
    listLocalPlaylists: listLocalPlaylists,
    createLocalPlaylist: createLocalPlaylist,
    createLocalPlaylistFromInput: function () {
      var input = $('sw3-new-pl-name');
      var name = input ? input.value.trim() : '';
      var pl = createLocalPlaylist(name, collectTarget);
      if (pl && input) input.value = '';
      return pl;
    },
    renameLocalPlaylist: renameLocalPlaylist,
    renameLocalPlaylistPrompt: function (id) {
      var name = window.prompt ? window.prompt('歌单新名称：', '') : '';
      if (name) renameLocalPlaylist(id, name);
    },
    deleteLocalPlaylist: deleteLocalPlaylist,
    addToLocalPlaylist: addToLocalPlaylist,
    removeFromLocalPlaylist: removeFromLocalPlaylist,
    openLocalPlaylist: openLocalPlaylist,
    playLocalPlaylist: function (id) {
      if (typeof loadPlaylistIntoQueueById === 'function') loadPlaylistIntoQueueById(id, true, '');
    },
    addCollectTargetToPlaylist: addCollectTargetToPlaylist,
    /* 界面 */
    openLibraryModal: openLibraryModal,
    closeLibraryModal: closeLibraryModal,
    status: function () {
      return {
        version: '0.3.0-phase3',
        queue: queueState(),
        favorites: loadFavorites().length,
        history: historyState(),
        playlists: loadLocalPlaylists().map(function (pl) { return { id: pl.id, name: pl.name, tracks: (pl.tracks || []).length }; }),
        eq: eqState(),
        lyricOffsetMs: lyricOffsetMs(),
        analyserMode: analyserMode(),
        resume: resumeState(),
        volume: volumeState()
      };
    }
  };

  /* 启动：并入已有本地歌单；若上次在播，恢复断点（只恢复，不强求自动播放成功）。 */
  try { mergeIntoUserPlaylists(); } catch (e) { /* ignore */ }
  setTimeout(function () {
    try {
      var st = resumeState();
      if (st.saved && st.playing && st.queueLen > 0 && !window.__sw3Restored) {
        window.__sw3Restored = true;
        restoreResume();
      }
    } catch (e) { /* ignore */ }
  }, 1500);
})();
