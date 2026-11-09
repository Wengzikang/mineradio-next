/* StarWave Phase 4B (2026-11-09)
 * 纯前端智能层 + 主题 + 高级视觉 + 听歌宠物 + 移动端 P1/P2。
 * 只做加法：新文件 + index.html 一行 <script> 引入；不改 phase2/phase3/
 * brand/PWA 缓存名（除任务 H 指定的 phase2.js 两行 URL）。
 * 汽水已移除（Ma 2026-11-09 22:45 决定，Phase 4A 接线已拆，qishui 文件已归档）。
 * 任何一步失败只降级提示，不抛错、不阻塞页面加载。
 * 诚实边界：
 *  - AI DJ 是纯前端规则拼歌单（时间/天气/心情/BPM），串词为本地模板生成，
 *    明确标注“规则生成，非大模型”；不接任何大模型服务、不产生费用。
 *  - 汽水已移除（Ma 2026-11-09 22:45 决定），本文件不含任何汽水代码。
 *  - 宠物形象为自绘几何/像素原创造型（团团/方方），不复制 mineradio.art 的
 *    宠物形象与 DualTheme 资产；DualTheme JSON 为自有格式 starwave-dual-theme。
 *  - 数据只存本机 localStorage；无账号、无密钥、无凭据、无后端地址。
 * GPL-3.0。
 */
(function () {
  'use strict';

  /* ---------- 小工具 ---------- */
  function $(id) { return document.getElementById(id); }
  function toast(msg) { try { if (typeof showToast === 'function') showToast(msg); } catch (e) { /* ignore */ } }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function clamp(v, lo, hi) { v = Number(v); if (!isFinite(v)) v = 0; return Math.max(lo, Math.min(hi, v)); }
  function storeGet(k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } }
  function storeSet(k, v) { try { window.localStorage.setItem(k, v); } catch (e) { /* ignore */ } }
  function storeDel(k) { try { window.localStorage.removeItem(k); } catch (e) { /* ignore */ } }
  function fmtTime(sec) {
    sec = Math.max(0, Math.floor(sec || 0));
    return Math.floor(sec / 60) + ':' + String(sec % 60).padStart(2, '0');
  }
  function fmtDate(ts) {
    try { var d = new Date(ts); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); } catch (e) { return ''; }
  }
  function songKeyOf(song) {
    try { if (typeof queueItemKey === 'function') { var k = queueItemKey(song); if (k) return k; } } catch (e) { /* ignore */ }
    return String((song && song.name) || '') + '|' + String((song && song.artist) || '');
  }
  function cloneSongOf(song) {
    try { if (typeof cloneSong === 'function') return cloneSong(song); } catch (e) { /* ignore */ }
    return Object.assign({}, song || {});
  }
  function dedupeSongs(songs) {
    var seen = {}, out = [];
    (songs || []).forEach(function (s) {
      if (!s || !s.name) return;
      var k = songKeyOf(s);
      if (seen[k]) return;
      seen[k] = true; out.push(s);
    });
    return out;
  }
  function downloadText(filename, text, mime) {
    try {
      var blob = new Blob([text], { type: mime || 'application/json;charset=utf-8' });
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url; a.download = filename;
      document.body.appendChild(a); a.click();
      setTimeout(function () { try { document.body.removeChild(a); URL.revokeObjectURL(url); } catch (e) { /* ignore */ } }, 500);
      return true;
    } catch (e) { return false; }
  }
  function vibrate(ms) {
    try { if (navigator.vibrate) navigator.vibrate(ms); return true; } catch (e) { return false; }
  }
  function isMobileUA() { return /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || ''); }
  function isIOS() { return /iPhone|iPad|iPod/i.test(navigator.userAgent || '') || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1); }

  var P3 = function () { try { return window.starwavePhase3 || null; } catch (e) { return null; } };
  var P4A = function () { try { return window.starwavePhase4a || null; } catch (e) { return null; } };

  /* ---------- 设置（只存本机） ---------- */
  var SETTINGS_KEY = 'starwave-phase4b-v1';
  var GESTURE_OPTIN_KEY = 'starwave-phase4b-gesture-optin-v1';
  var settings = {
    themeId: '',               /* 空 = 未选主题，用默认 */
    particleType: 'stardust',
    sceneId: 'starry',
    petEnabled: true,
    petId: 'tuantuan',
    shakeEnabled: false,      /* 实验功能，默认关 */
    gyroEnabled: false,       /* 实验功能，默认关 */
    djMood: 'auto',
    reportRange: 'year'
  };
  try {
    var saved = JSON.parse(storeGet(SETTINGS_KEY) || 'null') || {};
    Object.keys(settings).forEach(function (k) { if (saved[k] !== undefined) settings[k] = saved[k]; });
  } catch (e) { /* ignore */ }
  function saveSettings() { storeSet(SETTINGS_KEY, JSON.stringify(settings)); }

  /* ---------- D. 主题包系统 ---------- */
  /* 主题 = 预设参数 + 配色 + 字体 + 粒子配置的 JSON。名字均为原创，
     不用原版预设名 emily/安魂/星河/唱片/星球/滚筒/虚空。 */
  var BUILTIN_THEMES = [
    { id: 'mist', name: '晨雾微光', colors: { accent: '#7dd3fc', accent2: '#a5b4fc', bg: '#0b1220', bg2: '#1e293b', text: '#f1f5f9', muted: '#94a3b8' }, font: 'system-ui', particle: { type: 'stardust', density: 1.0, speed: 1.0 } },
    { id: 'ember', name: '熔金黄昏', colors: { accent: '#fbbf24', accent2: '#f97316', bg: '#1c1005', bg2: '#451a03', text: '#fef3c7', muted: '#d6a05a' }, font: 'system-ui', particle: { type: 'firefly', density: 0.9, speed: 0.9 } },
    { id: 'abyss', name: '深海静默', colors: { accent: '#2dd4bf', accent2: '#38bdf8', bg: '#04202b', bg2: '#083344', text: '#ecfeff', muted: '#67e8f9' }, font: 'system-ui', particle: { type: 'snow', density: 0.8, speed: 0.7 } },
    { id: 'neonrain', name: '霓虹雨巷', colors: { accent: '#e879f9', accent2: '#22d3ee', bg: '#12041f', bg2: '#2e1065', text: '#faf5ff', muted: '#c4b5fd' }, font: 'system-ui', particle: { type: 'rain', density: 1.0, speed: 1.1 } },
    { id: 'kite', name: '纸鸢春日', colors: { accent: '#4ade80', accent2: '#f472b6', bg: '#0c1a12', bg2: '#14532d', text: '#f0fdf4', muted: '#86efac' }, font: 'system-ui', particle: { type: 'firefly', density: 1.0, speed: 1.2 } }
  ];
  function themeById(id) {
    for (var i = 0; i < BUILTIN_THEMES.length; i++) if (BUILTIN_THEMES[i].id === id) return BUILTIN_THEMES[i];
    return null;
  }
  function validateTheme(obj) {
    if (!obj || typeof obj !== 'object') return '不是有效的 JSON 对象';
    if (!obj.name || typeof obj.name !== 'string') return '缺少 name';
    if (!obj.colors || typeof obj.colors !== 'object') return '缺少 colors';
    var need = ['accent', 'bg', 'text'];
    for (var i = 0; i < need.length; i++) if (!obj.colors[need[i]]) return 'colors 缺少 ' + need[i];
    return '';
  }
  function applyTheme(theme) {
    if (!theme) return false;
    var err = validateTheme(theme);
    if (err) { toast('主题无效：' + err); return false; }
    try {
      var root = document.documentElement;
      var c = theme.colors;
      root.style.setProperty('--sw4b-accent', c.accent);
      root.style.setProperty('--sw4b-accent2', c.accent2 || c.accent);
      root.style.setProperty('--sw4b-bg', c.bg);
      root.style.setProperty('--sw4b-bg2', c.bg2 || c.bg);
      root.style.setProperty('--sw4b-text', c.text);
      root.style.setProperty('--sw4b-muted', c.muted || c.text);
      if (theme.font) root.style.setProperty('--sw4b-font', theme.font);
      document.body.setAttribute('data-sw4b-theme', theme.id || theme.name || '');
      if (theme.particle && theme.particle.type) setParticleType(theme.particle.type, true);
      settings.themeId = theme.id || '';
      saveSettings();
      renderThemeList();
      return true;
    } catch (e) { return false; }
  }
  function currentTheme() {
    return themeById(settings.themeId) || null;
  }
  /* 封面取色自动生成主题：复用思路与 Cover Picker 一致（canvas 采样），
     跨域封面取不到像素时诚实回退到推荐色，不编造颜色。 */
  function themeFromCover() {
    return new Promise(function (resolve) {
      var song = null;
      try { song = (typeof currentCoverSong === 'function') ? currentCoverSong() : null; } catch (e) { /* ignore */ }
      var cover = song && song.cover;
      function fallback(reason) { resolve({ theme: null, reason: reason || 'cover_unavailable' }); }
      if (!cover) {
        try {
          var sw = (typeof coverPickerSwatchColors === 'function') ? coverPickerSwatchColors() : [];
          if (sw && sw.length) {
            var t = themeFromPalette(sw, '封面推荐色');
            resolve({ theme: t, reason: 'swatch_fallback' });
            return;
          }
        } catch (e) { /* ignore */ }
        fallback('no_cover');
        return;
      }
      var img = new Image();
      img.crossOrigin = 'anonymous';
      var done = false;
      var timer = setTimeout(function () { if (!done) { done = true; fallback('cover_timeout'); } }, 6000);
      img.onload = function () {
        if (done) return; done = true; clearTimeout(timer);
        try {
          var cv = document.createElement('canvas');
          cv.width = 48; cv.height = 48;
          var ctx = cv.getContext('2d');
          ctx.drawImage(img, 0, 0, 48, 48);
          var data = ctx.getImageData(0, 0, 48, 48).data;
          var r = 0, g = 0, b = 0, n = 0, best = null, bestScore = -1;
          var buckets = {};
          for (var i = 0; i < data.length; i += 16) {
            var pr = data[i], pg = data[i + 1], pb = data[i + 2], pa = data[i + 3];
            if (pa < 200) continue;
            r += pr; g += pg; b += pb; n++;
            var key = Math.floor(pr / 32) + ',' + Math.floor(pg / 32) + ',' + Math.floor(pb / 32);
            buckets[key] = (buckets[key] || 0) + 1;
          }
          if (!n) { fallback('cover_empty'); return; }
          Object.keys(buckets).forEach(function (k) {
            var parts = k.split(',');
            var br = +parts[0] * 32 + 16, bg2 = +parts[1] * 32 + 16, bb = +parts[2] * 32 + 16;
            var sat = Math.max(br, bg2, bb) - Math.min(br, bg2, bb);
            var score = buckets[k] * (1 + sat / 255);
            if (score > bestScore) { bestScore = score; best = [br, bg2, bb]; }
          });
          var avg = [Math.round(r / n), Math.round(g / n), Math.round(b / n)];
          var accent = best || avg;
          var hex = function (v) { return '#' + v.map(function (x) { return clamp(Math.round(x), 0, 255).toString(16).padStart(2, '0'); }).join(''); };
          var dark = function (v, f) { return v.map(function (x) { return x * f; }); };
          var t2 = {
            id: 'cover-auto', name: '封面取色 · ' + (song.name || '当前歌曲'),
            colors: { accent: hex(accent), accent2: hex(avg), bg: hex(dark(accent, 0.12)), bg2: hex(dark(avg, 0.22)), text: '#f8fafc', muted: hex(avg) },
            font: 'system-ui', particle: { type: settings.particleType || 'stardust', density: 1.0, speed: 1.0 }
          };
          resolve({ theme: t2, reason: '' });
        } catch (e) { fallback('cover_cors'); }
      };
      img.onerror = function () { if (!done) { done = true; clearTimeout(timer); fallback('cover_load_failed'); } };
      img.src = cover;
    });
  }
  function themeFromPalette(colors, name) {
    var accent = colors[0] || '#7dd3fc';
    var avg = colors[1] || accent;
    return {
      id: 'cover-auto', name: name || '封面取色',
      colors: { accent: accent, accent2: avg, bg: '#0b1220', bg2: '#1e293b', text: '#f1f5f9', muted: avg },
      font: 'system-ui', particle: { type: settings.particleType || 'stardust', density: 1.0, speed: 1.0 }
    };
  }
  function exportTheme(theme) {
    theme = theme || currentTheme();
    if (!theme) { toast('请先选择一个主题'); return false; }
    var ok = downloadText('starwave-theme-' + (theme.id || 'custom') + '.json', JSON.stringify(theme, null, 2));
    if (ok) toast('主题 JSON 已导出');
    return ok;
  }
  function importThemeFile(file) {
    if (!file) return Promise.resolve({ ok: false, reason: 'no_file' });
    return new Promise(function (resolve) {
      var reader = new FileReader();
      reader.onload = function () {
        try {
          var obj = JSON.parse(String(reader.result || ''));
          var err = validateTheme(obj);
          if (err) { toast('主题无效：' + err); resolve({ ok: false, reason: err }); return; }
          if (!obj.id) obj.id = 'imported-' + Date.now();
          var ok = applyTheme(obj);
          if (ok) toast('已应用导入的主题：' + obj.name);
          resolve({ ok: ok, theme: obj });
        } catch (e) { toast('主题 JSON 解析失败'); resolve({ ok: false, reason: 'parse_failed' }); }
      };
      reader.onerror = function () { resolve({ ok: false, reason: 'read_failed' }); };
      reader.readAsText(file);
    });
  }

  /* ---------- F. AI 主题（自有 DualTheme 格式） ---------- */
  /* 格式：{ format:'starwave-dual-theme', version:1, light:{...}, dark:{...} }。
     字段自定，不抄 mineradio.art 的 DualTheme 格式；只做封面取色 + JSON 导入。 */
  function buildDualThemeFromCover() {
    return themeFromCover().then(function (res) {
      if (!res.theme) return { ok: false, reason: res.reason };
      var c = res.theme.colors;
      function lighten(hex, f) {
        var n = parseInt(hex.slice(1), 16);
        var r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
        r = Math.round(r + (255 - r) * f); g = Math.round(g + (255 - g) * f); b = Math.round(b + (255 - b) * f);
        return '#' + [r, g, b].map(function (x) { return x.toString(16).padStart(2, '0'); }).join('');
      }
      var dual = {
        format: 'starwave-dual-theme', version: 1, name: res.theme.name || '封面双主题',
        light: { accent: c.accent, accent2: c.accent2, bg: lighten(c.accent, 0.88), bg2: lighten(c.accent2, 0.8), text: '#0f172a', muted: '#475569' },
        dark: { accent: c.accent, accent2: c.accent2, bg: c.bg, bg2: c.bg2, text: c.text, muted: c.muted }
      };
      return { ok: true, dual: dual, reason: res.reason };
    });
  }
  function validateDualTheme(obj) {
    if (!obj || typeof obj !== 'object') return '不是有效的 JSON 对象';
    if (obj.format !== 'starwave-dual-theme') return 'format 须为 starwave-dual-theme（本站自有格式）';
    if (obj.version !== 1) return 'version 须为 1';
    if (!obj.light || !obj.dark) return '缺少 light / dark';
    return '';
  }
  function applyDualTheme(dual) {
    var err = validateDualTheme(dual);
    if (err) { toast('DualTheme 无效：' + err); return false; }
    var preferLight = false;
    try { preferLight = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches; } catch (e) { /* ignore */ }
    var side = preferLight ? dual.light : dual.dark;
    var theme = { id: 'dual-' + (dual.name || 'custom'), name: dual.name || 'DualTheme', colors: side, font: 'system-ui', particle: { type: settings.particleType || 'stardust', density: 1.0, speed: 1.0 } };
    var ok = applyTheme(theme);
    if (ok) toast('已应用 DualTheme（' + (preferLight ? '浅色' : '深色') + '面）：' + (dual.name || ''));
    return ok;
  }
  function importDualThemeFile(file) {
    if (!file) return Promise.resolve({ ok: false, reason: 'no_file' });
    return new Promise(function (resolve) {
      var reader = new FileReader();
      reader.onload = function () {
        try {
          var obj = JSON.parse(String(reader.result || ''));
          var err = validateDualTheme(obj);
          if (err) { toast('DualTheme 无效：' + err); resolve({ ok: false, reason: err }); return; }
          var ok = applyDualTheme(obj);
          resolve({ ok: ok, dual: obj });
        } catch (e) { toast('DualTheme JSON 解析失败'); resolve({ ok: false, reason: 'parse_failed' }); }
      };
      reader.onerror = function () { resolve({ ok: false, reason: 'read_failed' }); };
      reader.readAsText(file);
    });
  }

  /* ---------- A. 规则 AI DJ（档①；串词为本地模板，明确标注“规则生成，非大模型”） ---------- */
  var DJ_SLOTS = [
    { id: 'morning', label: '清晨', from: 5, to: 9, moods: ['清醒', '轻快'], lines: ['早上好，{weather}的{city}，先来一首提神的。', '清晨的第一首歌，留给{mood}的你。', '天刚亮，音乐先醒——这是为清晨准备的歌单。'] },
    { id: 'noon', label: '午间', from: 9, to: 14, moods: ['专注', '轻快'], lines: ['午间时分，{weather}正好，配点{mood}的歌。', '吃完午饭，来几首不打扰思绪的歌。', '中午的歌单，节奏刚刚好，不急不慢。'] },
    { id: 'afternoon', label: '午后', from: 14, to: 18, moods: ['慵懒', '治愈'], lines: ['午后{weather}，适合{mood}一点的旋律。', '下午的阳光有点懒，歌也跟着慢下来。', '午后电台时间到，先播一首{mood}的。'] },
    { id: 'evening', label: '傍晚', from: 18, to: 22, moods: ['治愈', '浪漫'], lines: ['傍晚了，{weather}的{city}很适合听{mood}的歌。', '华灯初上，这首歌送给正在回家的你。', '傍晚歌单：把一天的疲惫，交给旋律。'] },
    { id: 'night', label: '深夜', from: 22, to: 29, moods: ['安静', '治愈'], lines: ['深夜了，声音放轻一点，陪你到睡前。', '夜深人静，这几首歌只给还没睡的你。', '{weather}的夜晚，适合{mood}地听完这张歌单。'] }
  ];
  function djTimeSlot(hour) {
    if (hour == null) hour = new Date().getHours();
    for (var i = 0; i < DJ_SLOTS.length; i++) {
      var s = DJ_SLOTS[i];
      var h = hour < 5 ? hour + 24 : hour;
      if (h >= s.from && h < s.to) return s;
    }
    return DJ_SLOTS[4];
  }
  function djWeatherInfo() {
    try {
      var st = (typeof homeWeatherRadioState !== 'undefined') ? homeWeatherRadioState : null;
      if (!st) return { label: '', city: '', mood: '' };
      var w = st.weather || {};
      return { label: w.label || '', city: (w.location && w.location.name) || st.city || '', mood: (w.mood && w.mood.key) || '' };
    } catch (e) { return { label: '', city: '', mood: '' }; }
  }
  function djTopArtists(limit) {
    try {
      var stats = null;
      try { stats = (typeof listenStatsState !== 'undefined') ? listenStatsState : JSON.parse(storeGet('starwave-listen-stats-v1') || 'null'); } catch (e) { stats = null; }
      var songs = (stats && stats.songs) || {};
      var arr = Object.keys(songs).map(function (k) { return songs[k]; });
      arr.sort(function (a, b) { return ((b.plays || 0) * 60000 + (b.listenMs || 0)) - ((a.plays || 0) * 60000 + (a.listenMs || 0)); });
      var artists = [];
      arr.forEach(function (s) { if (s && s.artist && artists.indexOf(s.artist) < 0) artists.push(s.artist); });
      return artists.slice(0, limit || 3);
    } catch (e) { return []; }
  }
  function djPoolSongs() {
    var pool = [];
    try {
      var wr = (typeof homeWeatherRadioState !== 'undefined') ? homeWeatherRadioState : null;
      if (wr && wr.radio && wr.radio.songs) pool = pool.concat(wr.radio.songs.map(cloneSongOf));
    } catch (e) { /* ignore */ }
    try {
      var hd = (typeof homeDiscoverState !== 'undefined') ? homeDiscoverState : null;
      if (hd && hd.songs) pool = pool.concat(hd.songs.map(cloneSongOf));
    } catch (e) { /* ignore */ }
    return dedupeSongs(pool);
  }
  function djLine(slot, mood, weather) {
    var day = new Date().getDate();
    var line = slot.lines[day % slot.lines.length];
    return line.replace('{weather}', weather.label || '好天气').replace('{city}', weather.city || '这里').replace('{mood}', mood || '放松');
  }
  /* 生成 DJ 歌单：天气电台 + 每日推荐 + 本地画像（常听歌手优先）+ 演示曲兜底。
     全程本地规则，不调用任何模型服务。 */
  function generateDj(opts) {
    opts = opts || {};
    var now = new Date();
    var slot = djTimeSlot(opts.hour != null ? opts.hour : now.getHours());
    var weather = djWeatherInfo();
    var mood = opts.mood && opts.mood !== 'auto' ? opts.mood : (weather.mood || slot.moods[0]);
    var pool = djPoolSongs();
    var artists = djTopArtists(3);
    var picked = [];
    function take(list, n) {
      var c = 0;
      list.forEach(function (s) {
        if (c >= n) return;
        if (picked.indexOf(s) < 0) { picked.push(s); c++; }
      });
    }
    /* 常听歌手优先 */
    if (artists.length) {
      artists.forEach(function (a) {
        take(pool.filter(function (s) { return String(s.artist || '').indexOf(a) >= 0 || String(a).indexOf(s.artist || '') >= 0; }), 2);
      });
    }
    /* 天气电台优先，其次每日推荐 */
    take(pool, 12 - picked.length);
    var p3 = P3();
    var demoPromise = null;
    function finish(demos) {
      if (picked.length < 6 && demos && demos.length) take(demos, 12 - picked.length);
      if (picked.length < 3 && demos && demos.length) take(demos, 12 - picked.length);
      picked = dedupeSongs(picked).slice(0, 12);
      var dj = {
        slot: slot.id, slotLabel: slot.label, mood: mood,
        weather: weather.label, city: weather.city,
        line: djLine(slot, mood, weather),
        generatedBy: '规则生成，非大模型',
        songs: picked, createdAt: Date.now()
      };
      state.lastDj = dj;
      return dj;
    }
    try {
      demoPromise = p3 ? p3.demoSongs() : (typeof buildStarwaveDemoSongs === 'function' ? buildStarwaveDemoSongs() : Promise.resolve([]));
    } catch (e) { demoPromise = Promise.resolve([]); }
    return Promise.resolve(demoPromise).then(finish).catch(function () { return finish([]); });
  }
  function playDj(dj) {
    dj = dj || state.lastDj;
    if (!dj || !dj.songs || !dj.songs.length) { toast('DJ 歌单还是空的，先等天气电台加载完'); return false; }
    try {
      playQueue = dj.songs.map(cloneSongOf);
      currentIdx = 0;
      if (typeof playQueueAt === 'function') playQueueAt(0);
      if (typeof safeRenderQueuePanel === 'function') safeRenderQueuePanel('sw4b-dj');
      toast('AI DJ 开始播放（规则生成，非大模型）：' + dj.line);
      return true;
    } catch (e) { toast('DJ 播放失败'); return false; }
  }

  /* ---------- B. 混合推荐 ---------- */
  function neteaseRecommendSongs() {
    /* 平台推荐：网易云 recommend_songs（公开 api-enhanced 服务，无登录）。
       未登录时上游通常返回需登录，属实记录原因并回退本地混合推荐，不编数据。 */
    try {
      if (typeof neteaseWebFetchJson !== 'function' || typeof STARWAVE_NETEASE_API_BASE === 'undefined') {
        return Promise.resolve({ songs: [], reason: 'netease_api_unavailable' });
      }
      return Promise.race([
        neteaseWebFetchJson(STARWAVE_NETEASE_API_BASE + '/recommend/songs', 9000),
        new Promise(function (res) { setTimeout(function () { res(null); }, 9500); })
      ]).then(function (data) {
        if (!data || !data.data || !data.data.dailySongs || !data.data.dailySongs.length) {
          return { songs: [], reason: (data && data.code === 301) ? 'login_required' : 'recommend_empty' };
        }
        var songs = data.data.dailySongs.map(function (r) {
          return { provider: 'netease-web', source: 'netease-web', type: 'song', id: String(r.id || ''), neteaseId: r.id, name: r.name || '', artist: (r.ar || []).map(function (a) { return a.name; }).join(' / '), album: (r.al && r.al.name) || '', cover: (r.al && r.al.picUrl) || '', duration: Math.round(((r.dt || 0) / 1000)), fee: (r.fee != null ? r.fee : 0), publicAudioUrl: '', publicSourceLabel: '网易云' };
        });
        return { songs: songs, reason: '' };
      }).catch(function () { return { songs: [], reason: 'recommend_failed' }; });
    } catch (e) { return Promise.resolve({ songs: [], reason: 'recommend_failed' }); }
  }
  function localTopSongs(limit) {
    /* 本地画像：常听歌曲（按播放次数/时长）映射到可播池（演示/天气/每日推荐） */
    try {
      var stats = null;
      try { stats = (typeof listenStatsState !== 'undefined') ? listenStatsState : JSON.parse(storeGet('starwave-listen-stats-v1') || 'null'); } catch (e) { stats = null; }
      var songs = (stats && stats.songs) || {};
      var arr = Object.keys(songs).map(function (k) { return songs[k]; });
      arr.sort(function (a, b) { return ((b.plays || 0) * 60000 + (b.listenMs || 0)) - ((a.plays || 0) * 60000 + (a.listenMs || 0)); });
      var pool = djPoolSongs();
      var out = [];
      arr.slice(0, limit || 8).forEach(function (top) {
        pool.forEach(function (s) {
          if (String(s.name || '') === String(top.name || '') || (top.artist && String(s.artist || '').indexOf(top.artist) >= 0)) {
            if (out.indexOf(s) < 0) out.push(s);
          }
        });
      });
      return out.slice(0, limit || 8);
    } catch (e) { return []; }
  }
  function hybridRecommend(opts) {
    opts = opts || {};
    var platformP = neteaseRecommendSongs();
    var local = localTopSongs(8);
    var pool = djPoolSongs();
    var p3 = P3();
    var demoP = null;
    try { demoP = p3 ? p3.demoSongs() : (typeof buildStarwaveDemoSongs === 'function' ? buildStarwaveDemoSongs() : Promise.resolve([])); } catch (e) { demoP = Promise.resolve([]); }
    return Promise.all([platformP, Promise.resolve(demoP)]).then(function (res) {
      var platform = res[0] || { songs: [], reason: 'recommend_failed' };
      var demos = res[1] || [];
      var coldStart = local.length === 0 && platform.songs.length === 0;
      var merged = [];
      /* 跨平台去重与可播性排序：可播（有地址/演示/试听）优先，其次平台推荐，其次本地画像 */
      var playable = function (s) { return !!(s.publicAudioUrl || s.previewUrl || s.provider === 'demo' || s.trial); };
      var buckets = [
        pool.filter(playable),
        platform.songs,
        local,
        demos
      ];
      buckets.forEach(function (list) { (list || []).forEach(function (s) { if (merged.indexOf(s) < 0) merged.push(s); }); });
      merged = dedupeSongs(merged);
      merged.sort(function (a, b) { return (playable(b) ? 1 : 0) - (playable(a) ? 1 : 0); });
      merged = merged.slice(0, 20);
      var rec = {
        songs: merged,
        platformCount: platform.songs.length,
        platformReason: platform.reason,
        localCount: local.length,
        coldStart: coldStart,
        fallbackLabel: coldStart ? '今日聆听 / 为你挑选（冷启动兜底）' : '',
        createdAt: Date.now()
      };
      state.lastRecommend = rec;
      return rec;
    });
  }
  function playRecommend(rec, idx) {
    rec = rec || state.lastRecommend;
    if (!rec || !rec.songs || !rec.songs.length) { toast('推荐还是空的'); return false; }
    try {
      playQueue = rec.songs.map(cloneSongOf);
      currentIdx = idx || 0;
      if (typeof playQueueAt === 'function') playQueueAt(currentIdx);
      if (typeof safeRenderQueuePanel === 'function') safeRenderQueuePanel('sw4b-rec');
      return true;
    } catch (e) { return false; }
  }

  /* ---------- C. 音乐报告（本地计算、零上传） ---------- */
  function reportSource() {
    try {
      if (typeof listenStatsState !== 'undefined' && listenStatsState) return listenStatsState;
    } catch (e) { /* ignore */ }
    try { return JSON.parse(storeGet('starwave-listen-stats-v1') || 'null') || { history: [], songs: {} }; } catch (e) { return { history: [], songs: {} }; }
  }
  function reportRangeBounds(range, now) {
    now = now || Date.now();
    var d = new Date(now);
    var start;
    if (range === 'day') { start = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime(); }
    else if (range === 'week') { var wd = (d.getDay() + 6) % 7; start = new Date(d.getFullYear(), d.getMonth(), d.getDate() - wd).getTime(); }
    else if (range === 'month') { start = new Date(d.getFullYear(), d.getMonth(), 1).getTime(); }
    else { start = new Date(d.getFullYear(), 0, 1).getTime(); }
    return { start: start, end: now };
  }
  function computeReport(range) {
    var src = reportSource();
    var history = (src.history || []).filter(function (h) { return h && h.playedAt; });
    var b = reportRangeBounds(range || 'year');
    var inRange = history.filter(function (h) { return h.playedAt >= b.start && h.playedAt <= b.end; });
    var totalMs = 0, artists = {}, songs = {}, moods = {}, lateNight = {};
    inRange.forEach(function (h) {
      totalMs += Number(h.listenMs) || 0;
      var a = h.artist || '未知歌手';
      artists[a] = (artists[a] || 0) + 1;
      var sk = h.name || '未知歌曲';
      songs[sk] = songs[sk] || { name: sk, artist: a, plays: 0, listenMs: 0 };
      songs[sk].plays += 1; songs[sk].listenMs += Number(h.listenMs) || 0;
      var mood = (h.context && h.context.mood) || (h.context && h.context.type === 'weather-radio' ? '天气电台' : '') || '未分类';
      moods[mood] = (moods[mood] || 0) + 1;
      var hr = new Date(h.playedAt).getHours();
      if (hr >= 22 || hr < 5) lateNight[sk] = (lateNight[sk] || 0) + 1;
    });
    function topOf(map, n) {
      return Object.keys(map).map(function (k) { return { name: k, count: map[k] }; })
        .sort(function (x, y) { return y.count - x.count; }).slice(0, n || 5);
    }
    var topSongs = Object.keys(songs).map(function (k) { return songs[k]; })
      .sort(function (x, y) { return y.plays - x.plays || y.listenMs - x.listenMs; }).slice(0, 5);
    return {
      range: range || 'year', start: b.start, end: b.end,
      totalPlays: inRange.length,
      totalMinutes: Math.round(totalMs / 60000),
      totalHours: (totalMs / 3600000).toFixed(1),
      uniqueSongs: Object.keys(songs).length,
      topArtists: topOf(artists, 5),
      topSongs: topSongs,
      moods: moods,
      lateNightTop: topOf(lateNight, 5),
      generatedAt: Date.now(),
      source: '本地计算，零上传'
    };
  }
  function renderShareCard(report) {
    /* 年度报告分享卡片：Canvas 渲染导出图片（1080×1350）。 */
    var cv = document.createElement('canvas');
    cv.width = 1080; cv.height = 1350;
    var ctx = cv.getContext('2d');
    var theme = currentTheme();
    var accent = (theme && theme.colors.accent) || '#7dd3fc';
    var accent2 = (theme && theme.colors.accent2) || '#a5b4fc';
    var bg = (theme && theme.colors.bg) || '#0b1220';
    var g = ctx.createLinearGradient(0, 0, 1080, 1350);
    g.addColorStop(0, bg); g.addColorStop(1, '#1e293b');
    ctx.fillStyle = g; ctx.fillRect(0, 0, 1080, 1350);
    ctx.fillStyle = accent;
    ctx.beginPath(); ctx.arc(540, 300, 150, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#0b1220';
    ctx.font = 'bold 120px system-ui'; ctx.textAlign = 'center';
    ctx.fillText('♪', 540, 345);
    ctx.fillStyle = '#f8fafc';
    ctx.font = 'bold 64px system-ui';
    ctx.fillText('我的年度音乐报告', 540, 560);
    ctx.fillStyle = accent2;
    ctx.font = '36px system-ui';
    ctx.fillText(new Date().getFullYear() + ' · 星澜音乐 StarWave', 540, 625);
    ctx.fillStyle = '#f8fafc';
    ctx.font = 'bold 84px system-ui';
    ctx.fillText(String(report.totalPlays), 540, 790);
    ctx.font = '32px system-ui'; ctx.fillStyle = '#cbd5e1';
    ctx.fillText('播放次数 · ' + report.totalHours + ' 小时 · ' + report.uniqueSongs + ' 首歌', 540, 850);
    ctx.textAlign = 'left';
    ctx.font = 'bold 40px system-ui'; ctx.fillStyle = accent;
    ctx.fillText('TOP 歌手', 120, 960);
    ctx.fillStyle = '#f8fafc'; ctx.font = '36px system-ui';
    (report.topArtists || []).slice(0, 3).forEach(function (a, i) {
      ctx.fillText((i + 1) + '. ' + a.name + '  ·  ' + a.count + ' 次', 120, 1020 + i * 55);
    });
    ctx.fillStyle = '#94a3b8'; ctx.font = '28px system-ui'; ctx.textAlign = 'center';
    ctx.fillText('本地计算 · 零上传 · StarWave', 540, 1290);
    return cv;
  }
  function exportShareCard(report) {
    report = report || computeReport('year');
    try {
      var cv = renderShareCard(report);
      var url = cv.toDataURL('image/png');
      var a = document.createElement('a');
      a.href = url; a.download = 'starwave-year-report-' + new Date().getFullYear() + '.png';
      document.body.appendChild(a); a.click();
      setTimeout(function () { try { document.body.removeChild(a); } catch (e) { /* ignore */ } }, 500);
      toast('年度报告卡片已导出为图片');
      return true;
    } catch (e) { toast('卡片导出失败'); return false; }
  }
  function exportReportData() {
    var src = reportSource();
    var ok = downloadText('starwave-listen-data.json', JSON.stringify({ exportedAt: new Date().toISOString(), history: src.history || [], songs: src.songs || {} }, null, 2));
    if (ok) toast('听歌数据已导出（JSON，仅本机数据）');
    return ok;
  }
  function clearReportData() {
    try {
      storeDel('starwave-listen-stats-v1');
      try { if (typeof listenStatsState !== 'undefined') { listenStatsState.history = []; listenStatsState.songs = {}; } } catch (e) { /* ignore */ }
      toast('听歌统计已清空（仅本机）');
      return true;
    } catch (e) { return false; }
  }

  /* ---------- E. 高级粒子 + 3D 场景包 + 段落镜头 ---------- */
  var SCENES = [
    { id: 'starry', name: '星空', particle: 'stardust', bg: 'radial-gradient(120% 100% at 50% 0%, #1e293b 0%, #0b1220 55%, #020617 100%)' },
    { id: 'ocean', name: '海洋', particle: 'firefly', bg: 'linear-gradient(180deg, #083344 0%, #04202b 55%, #01161f 100%)' },
    { id: 'rainy', name: '雨夜', particle: 'rain', bg: 'linear-gradient(180deg, #1e1b4b 0%, #12041f 60%, #020617 100%)' }
  ];
  var PARTICLE_BASE = { stardust: 140, rain: 220, snow: 160, firefly: 70 };
  var SHOTS = [
    { id: 'intro', label: '前奏', from: 0, to: 0.12, transform: 'scale(1.02) translateY(0px)' },
    { id: 'verse', label: '主歌', from: 0.12, to: 0.45, transform: 'scale(1.0) translateX(-6px)' },
    { id: 'chorus', label: '副歌', from: 0.45, to: 0.78, transform: 'scale(1.08) translateY(-8px)' },
    { id: 'bridge', label: '间奏', from: 0.78, to: 0.88, transform: 'scale(1.04) translateX(6px)' },
    { id: 'outro', label: '尾奏', from: 0.88, to: 1.01, transform: 'scale(1.0) translateY(4px)' }
  ];
  var particle = {
    canvas: null, ctx: null, bg: null, parts: [], type: 'stardust',
    running: false, raf: 0, lastT: 0, fpsEma: 60, budget: 1, kick: 0, spectrum: { low: 0, mid: 0, high: 0 },
    sceneId: 'starry', shotId: '', shotLabel: '', frame: 0
  };
  function sceneById(id) {
    for (var i = 0; i < SCENES.length; i++) if (SCENES[i].id === id) return SCENES[i];
    return SCENES[0];
  }
  function ensureParticleDom() {
    if (particle.canvas) return true;
    try {
      var bg = document.createElement('div');
      bg.id = 'sw4b-scene-bg';
      bg.style.cssText = 'position:fixed;inset:0;z-index:0;pointer-events:none;opacity:.55;transition:transform 1.2s ease,background 0.8s ease;';
      document.body.appendChild(bg);
      particle.bg = bg;
      var cv = document.createElement('canvas');
      cv.id = 'sw4b-particles';
      cv.style.cssText = 'position:fixed;inset:0;z-index:2;pointer-events:none;transition:transform 1.2s ease;';
      document.body.appendChild(cv);
      particle.canvas = cv;
      particle.ctx = cv.getContext('2d');
      resizeParticles();
      window.addEventListener('resize', resizeParticles);
      return true;
    } catch (e) { return false; }
  }
  function resizeParticles() {
    try {
      if (!particle.canvas) return;
      var dpr = Math.min(window.devicePixelRatio || 1, 2);
      particle.canvas.width = Math.floor(window.innerWidth * dpr);
      particle.canvas.height = Math.floor(window.innerHeight * dpr);
      particle.canvas.style.width = window.innerWidth + 'px';
      particle.canvas.style.height = window.innerHeight + 'px';
      particle.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    } catch (e) { /* ignore */ }
  }
  function spawnParticle() {
    var w = window.innerWidth, h = window.innerHeight, t = particle.type;
    var p = { x: Math.random() * w, y: Math.random() * h, r: 1 + Math.random() * 2.2, a: 0.25 + Math.random() * 0.6, vx: 0, vy: 0, hue: 200 + Math.random() * 60, tw: Math.random() * Math.PI * 2 };
    if (t === 'stardust') { p.vx = (Math.random() - 0.5) * 0.12; p.vy = (Math.random() - 0.5) * 0.12; p.r = 0.6 + Math.random() * 1.8; }
    else if (t === 'rain') { p.x = Math.random() * (w + 100); p.y = -20 - Math.random() * h; p.vx = -1.2; p.vy = 9 + Math.random() * 7; p.r = 0.8 + Math.random() * 0.8; p.len = 12 + Math.random() * 14; }
    else if (t === 'snow') { p.y = -10 - Math.random() * h; p.vx = (Math.random() - 0.5) * 0.5; p.vy = 0.6 + Math.random() * 1.1; p.r = 1 + Math.random() * 2.4; p.sway = Math.random() * Math.PI * 2; }
    else if (t === 'firefly') { p.vx = (Math.random() - 0.5) * 0.5; p.vy = (Math.random() - 0.5) * 0.4; p.r = 1.2 + Math.random() * 2.2; p.hue = 50 + Math.random() * 40; }
    return p;
  }
  function rebuildParticles() {
    var base = PARTICLE_BASE[particle.type] || 120;
    var n = Math.round(base * particle.budget);
    particle.parts = [];
    for (var i = 0; i < n; i++) particle.parts.push(spawnParticle());
  }
  function governorTierFactor() {
    try {
      var gov = window.starwavePerfGovernor;
      if (!gov) return 1;
      var tier = gov.tier || 'high';
      if (tier === 'eco') return 0.4;
      if (tier === 'balanced') return 0.7;
      if (tier === 'ultra') return 1.0;
      return 1.0;
    } catch (e) { return 1; }
  }
  function readAudioDrive() {
    /* 音频驱动：Kick 触发 + 频谱映射，复用 Phase 3 的 beatInfo/spectrumSample；
       取不到时粒子只做环境漂移，不编造能量。 */
    var kick = 0, spec = { low: 0, mid: 0, high: 0 };
    try {
      var p3 = P3();
      if (p3 && typeof p3.beatInfo === 'function') {
        var b = p3.beatInfo() || {};
        kick = clamp(Number(b.kickLevel != null ? b.kickLevel : (b.kick != null ? b.kick : (b.max_kick != null ? b.max_kick : 0))), 0, 1);
      }
      if (p3 && typeof p3.spectrumSample === 'function') {
        var s = p3.spectrumSample() || {};
        if (Array.isArray(s)) {
          spec.low = s[0] || 0; spec.mid = s[1] || 0; spec.high = s[2] || 0;
        } else {
          spec.low = clamp(Number(s.low || s.bass || 0), 0, 1);
          spec.mid = clamp(Number(s.mid || s.mids || 0), 0, 1);
          spec.high = clamp(Number(s.high || s.treble || 0), 0, 1);
        }
      }
    } catch (e) { /* ignore */ }
    particle.kick = kick;
    particle.spectrum = spec;
  }
  function segmentShot() {
    /* 段落镜头：按播放进度分段（前奏/主歌/副歌/间奏/尾奏），纯前端能量曲线分段；
       段落切换时改镜头（CSS transform 推/拉/移），不碰 Three.js 相机。 */
    var shot = SHOTS[0];
    try {
      var a = (typeof audio !== 'undefined') ? audio : window.audio;
      if (a && a.duration && isFinite(a.duration) && a.duration > 0) {
        var prog = clamp(a.currentTime / a.duration, 0, 1);
        for (var i = 0; i < SHOTS.length; i++) {
          if (prog >= SHOTS[i].from && prog < SHOTS[i].to) { shot = SHOTS[i]; break; }
        }
      }
    } catch (e) { /* ignore */ }
    if (shot.id !== particle.shotId) {
      particle.shotId = shot.id;
      particle.shotLabel = shot.label;
      try {
        if (particle.canvas) particle.canvas.style.transform = shot.transform;
        if (particle.bg) particle.bg.style.transform = shot.transform;
      } catch (e) { /* ignore */ }
      var el = $('sw4b-shot-label');
      if (el) el.textContent = '段落：' + shot.label + '（镜头已切换）';
    }
    return shot;
  }
  function particleTick(ts) {
    if (!particle.running) return;
    particle.raf = requestAnimationFrame(particleTick);
    if (document.hidden) { particle.lastT = ts; return; }
    var dt = particle.lastT ? Math.min(100, ts - particle.lastT) : 16;
    particle.lastT = ts;
    if (dt > 0) {
      var fps = 1000 / dt;
      particle.fpsEma = particle.fpsEma * 0.95 + fps * 0.05;
    }
    particle.frame++;
    /* 粒子数按帧率自适应（接 Phase 2 性能总督档位）：每 120 帧重算一次预算 */
    if (particle.frame % 120 === 0) {
      var fpsFactor = clamp(particle.fpsEma / 60, 0.3, 1);
      var nb = clamp(fpsFactor * governorTierFactor(), 0.15, 1);
      if (Math.abs(nb - particle.budget) > 0.15) {
        particle.budget = nb;
        rebuildParticles();
      }
    }
    if (particle.frame % 10 === 0) readAudioDrive();
    if (particle.frame % 30 === 0) segmentShot();
    var ctx = particle.ctx;
    if (!ctx) return;
    var w = window.innerWidth, h = window.innerHeight;
    ctx.clearRect(0, 0, w, h);
    var kick = particle.kick, spec = particle.spectrum;
    var speedMul = 1 + kick * 1.6 + spec.low * 0.8;
    for (var i = 0; i < particle.parts.length; i++) {
      var p = particle.parts[i];
      p.tw += 0.02 * speedMul;
      if (particle.type === 'snow') { p.x += p.vx + Math.sin(p.sway + particle.frame * 0.01) * 0.4; p.y += p.vy * speedMul; }
      else if (particle.type === 'rain') { p.x += p.vx * speedMul; p.y += p.vy * speedMul; }
      else if (particle.type === 'firefly') {
        p.x += p.vx * (0.5 + spec.mid) + Math.sin(p.tw * 0.7) * 0.3;
        p.y += p.vy * (0.5 + spec.high) + Math.cos(p.tw * 0.5) * 0.3;
      } else { p.x += p.vx * speedMul; p.y += p.vy * speedMul; }
      if (p.y > h + 30) { p.y = -20; if (particle.type === 'rain') p.x = Math.random() * (w + 100); }
      if (p.y < -30) p.y = h + 20;
      if (p.x > w + 30) p.x = -20;
      if (p.x < -30) p.x = w + 20;
      var alpha = clamp(p.a * (0.6 + 0.4 * Math.sin(p.tw)) * (1 + kick * 0.8), 0, 1);
      if (particle.type === 'rain') {
        ctx.strokeStyle = 'hsla(' + Math.round(p.hue) + ',80%,75%,' + alpha.toFixed(2) + ')';
        ctx.lineWidth = p.r;
        ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x + 2, p.y + (p.len || 14)); ctx.stroke();
      } else {
        ctx.fillStyle = 'hsla(' + Math.round(p.hue) + ',85%,' + (particle.type === 'firefly' ? '70%' : '82%') + ',' + alpha.toFixed(2) + ')';
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r * (1 + kick * 0.5 + spec.high * 0.4), 0, Math.PI * 2); ctx.fill();
      }
    }
    if (particle.frame % 60 === 0) drawPet();
  }
  function startParticles() {
    if (!ensureParticleDom()) return false;
    if (particle.running) return true;
    particle.running = true;
    particle.lastT = 0;
    rebuildParticles();
    particle.raf = requestAnimationFrame(particleTick);
    return true;
  }
  function stopParticles() {
    particle.running = false;
    try { cancelAnimationFrame(particle.raf); } catch (e) { /* ignore */ }
    try { if (particle.ctx) particle.ctx.clearRect(0, 0, window.innerWidth, window.innerHeight); } catch (e) { /* ignore */ }
  }
  function setParticleType(type, silent) {
    if (!PARTICLE_BASE[type]) return false;
    particle.type = type;
    settings.particleType = type;
    saveSettings();
    rebuildParticles();
    if (!silent) toast('粒子已切换：' + ({ stardust: '星尘', rain: '雨', snow: '雪', firefly: '萤火' }[type] || type));
    var sel = $('sw4b-particle-type');
    if (sel) sel.value = type;
    return true;
  }
  function applyScene(id, silent) {
    var sc = sceneById(id);
    settings.sceneId = sc.id;
    saveSettings();
    particle.sceneId = sc.id;
    if (ensureParticleDom() && particle.bg) particle.bg.style.background = sc.bg;
    setParticleType(sc.particle, true);
    if (!silent) toast('场景已切换：' + sc.name + '（粒子：' + ({ stardust: '星尘', rain: '雨', snow: '雪', firefly: '萤火' }[sc.particle] || sc.particle) + '）');
    var sel = $('sw4b-scene');
    if (sel) sel.value = sc.id;
    return sc;
  }
  function particleState() {
    return {
      type: particle.type, sceneId: particle.sceneId, running: particle.running,
      count: particle.parts.length, budget: +particle.budget.toFixed(2), frame: particle.frame,
      fpsEma: Math.round(particle.fpsEma), kick: +particle.kick.toFixed(2),
      spectrum: particle.spectrum, shotId: particle.shotId, shotLabel: particle.shotLabel,
      governorTier: (function () { try { return window.starwavePerfGovernor ? window.starwavePerfGovernor.tier : 'unknown'; } catch (e) { return 'unknown'; } })()
    };
  }

  /* ---------- F. 听歌宠物（自绘原创造型，不复制 mineradio.art 形象） ---------- */
  var PETS = [
    { id: 'tuantuan', name: '团团', desc: '圆滚滚的黄色小团子，爱跟着节拍晃' },
    { id: 'fangfang', name: '方方', desc: '方形像素小家伙，头顶一根小天线' }
  ];
  var petCv = null, petCtx = null;
  function ensurePetDom() {
    if (petCv) return true;
    try {
      var cv = document.createElement('canvas');
      cv.id = 'sw4b-pet';
      cv.width = 180; cv.height = 110;
      cv.style.cssText = 'position:fixed;left:14px;bottom:118px;z-index:6;pointer-events:auto;cursor:pointer;';
      cv.title = '听歌宠物：点击切换形象';
      cv.addEventListener('click', function () { cyclePet(); });
      document.body.appendChild(cv);
      petCv = cv;
      petCtx = cv.getContext('2d');
      return true;
    } catch (e) { return false; }
  }
  function petById(id) {
    for (var i = 0; i < PETS.length; i++) if (PETS[i].id === id) return PETS[i];
    return PETS[0];
  }
  function drawPet() {
    if (!settings.petEnabled || !petCv || !petCtx) return;
    var ctx = petCtx;
    ctx.clearRect(0, 0, 180, 110);
    /* 沿播放进度爬行：x = 进度 × 轨道宽 */
    var prog = 0, playing = false;
    try {
      var a = (typeof audio !== 'undefined') ? audio : window.audio;
      if (a && a.duration && isFinite(a.duration) && a.duration > 0) prog = clamp(a.currentTime / a.duration, 0, 1);
      playing = !!(a && !a.paused);
    } catch (e) { /* ignore */ }
    var trackY = 96;
    ctx.strokeStyle = 'rgba(255,255,255,0.25)';
    ctx.lineWidth = 3; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(12, trackY); ctx.lineTo(168, trackY); ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,0.35)';
    ctx.beginPath(); ctx.arc(12 + prog * 156, trackY, 3, 0, Math.PI * 2); ctx.fill();
    var x = 12 + prog * 156;
    var bob = playing ? Math.sin(Date.now() / 180) * 3 : Math.sin(Date.now() / 600) * 1;
    var blink = (Date.now() % 4000) < 150;
    var pet = petById(settings.petId);
    ctx.save();
    ctx.translate(x, trackY - 26 + bob);
    if (pet.id === 'tuantuan') {
      /* 团团：黄色圆身 + 两只圆耳 + 腮红（几何自绘） */
      ctx.fillStyle = '#fbbf24';
      ctx.beginPath(); ctx.arc(-14, -16, 9, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.arc(14, -16, 9, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.arc(0, 0, 22, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#f59e0b';
      ctx.beginPath(); ctx.arc(-14, -16, 4, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.arc(14, -16, 4, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#78350f';
      if (blink) { ctx.fillRect(-11, -4, 7, 2); ctx.fillRect(4, -4, 7, 2); }
      else { ctx.beginPath(); ctx.arc(-8, -4, 2.6, 0, Math.PI * 2); ctx.fill(); ctx.beginPath(); ctx.arc(8, -4, 2.6, 0, Math.PI * 2); ctx.fill(); }
      ctx.fillStyle = 'rgba(244,114,182,0.7)';
      ctx.beginPath(); ctx.arc(-15, 3, 3.4, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.arc(15, 3, 3.4, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = '#78350f'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(0, 3, 5, 0.15 * Math.PI, 0.85 * Math.PI); ctx.stroke();
      ctx.fillStyle = '#fbbf24';
      ctx.beginPath(); ctx.ellipse(-12, 20, 7, 4, 0, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.ellipse(12, 20, 7, 4, 0, 0, Math.PI * 2); ctx.fill();
    } else {
      /* 方方：蓝色方身 + 天线 + 像素风眼睛（矩形自绘） */
      ctx.fillStyle = '#38bdf8';
      ctx.fillRect(-4, -34, 3, 12);
      ctx.beginPath(); ctx.arc(-2.5, -36, 4, 0, Math.PI * 2); ctx.fillStyle = '#f472b6'; ctx.fill();
      ctx.fillStyle = '#38bdf8';
      ctx.fillRect(-20, -22, 40, 40);
      ctx.fillStyle = '#0c4a6e';
      ctx.fillRect(-20, -22, 40, 6);
      ctx.fillStyle = '#082f49';
      if (blink) { ctx.fillRect(-12, -8, 8, 2); ctx.fillRect(5, -8, 8, 2); }
      else { ctx.fillRect(-12, -10, 7, 7); ctx.fillRect(5, -10, 7, 7); }
      ctx.fillStyle = '#082f49';
      ctx.fillRect(-4, 2, 9, 3);
      ctx.fillStyle = '#7dd3fc';
      ctx.fillRect(-20, 14, 8, 4); ctx.fillRect(12, 14, 8, 4);
    }
    ctx.restore();
    ctx.fillStyle = 'rgba(255,255,255,0.65)';
    ctx.font = '11px system-ui'; ctx.textAlign = 'center';
    ctx.fillText(pet.name + ' · ' + Math.round(prog * 100) + '%', 90, 12);
  }
  function cyclePet() {
    var idx = PETS.findIndex(function (p) { return p.id === settings.petId; });
    var next = PETS[(idx + 1) % PETS.length];
    settings.petId = next.id;
    saveSettings();
    toast('听歌宠物：' + next.name + '（' + next.desc + '）');
    renderPetRow();
    drawPet();
    return next;
  }
  function setPetEnabled(on) {
    settings.petEnabled = !!on;
    saveSettings();
    if (on) { ensurePetDom(); drawPet(); }
    else if (petCv) { try { petCtx.clearRect(0, 0, 180, 110); } catch (e) { /* ignore */ } }
    renderPetRow();
    return settings.petEnabled;
  }

  /* ---------- G. 移动端 P1/P2 ---------- */
  var pwaPromptEvent = null;
  var longPressTimer = null, longPressTarget = null;
  var shakeLast = 0, shakeLastAccel = null;

  function fontSelfHostedCheck() {
    /* P1 核实：无 Google Fonts 外链。检查 link/script 与已加载资源。 */
    var bad = [];
    try {
      document.querySelectorAll('link[href],script[src]').forEach(function (el) {
        var u = el.href || el.src || '';
        if (/fonts\.googleapis\.com|fonts\.gstatic\.com/i.test(u)) bad.push(u);
      });
    } catch (e) { /* ignore */ }
    try {
      var entries = (performance.getEntriesByType ? performance.getEntriesByType('resource') : []) || [];
      entries.forEach(function (en) {
        if (/fonts\.googleapis\.com|fonts\.gstatic\.com/i.test(en.name || '')) bad.push(en.name);
      });
    } catch (e) { /* ignore */ }
    return { selfHosted: bad.length === 0, externalFontUrls: bad.slice(0, 5) };
  }
  function gestureStatus() {
    var cam = 'unknown';
    try { cam = (typeof fx !== 'undefined' && fx) ? String(fx.cam || 'off') : 'off'; } catch (e) { cam = 'off'; }
    return { cam: cam, defaultOff: true, mobile: isMobileUA(), optInStored: !!storeGet(GESTURE_OPTIN_KEY) };
  }
  function gestureGuard() {
    /* P1：手势开关默认关闭；手机上默认不请求摄像头。基线 fx.cam 默认已是 'off'，
       这里只做一道手机端守卫：若移动端被置为 gesture 且无用户明确选择记录，则关掉。 */
    try {
      if (!isMobileUA()) return { guarded: false, reason: 'not_mobile' };
      if (typeof fx === 'undefined' || !fx) return { guarded: false, reason: 'fx_unavailable' };
      if (fx.cam === 'gesture' && !storeGet(GESTURE_OPTIN_KEY)) {
        if (typeof setCamMode === 'function') setCamMode('off');
        return { guarded: true, reason: 'mobile_default_off' };
      }
      return { guarded: false, reason: 'already_off_or_opted_in', cam: fx.cam };
    } catch (e) { return { guarded: false, reason: 'error' }; }
  }
  function pwaInstallStatus() {
    var standalone = false;
    try {
      standalone = (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) || window.navigator.standalone === true;
    } catch (e) { /* ignore */ }
    var kind = standalone ? 'installed' : (isIOS() ? 'ios' : (pwaPromptEvent ? 'android_ready' : (/Android/i.test(navigator.userAgent || '') ? 'android_waiting' : 'desktop')));
    return { standalone: standalone, kind: kind, hasPromptEvent: !!pwaPromptEvent, isIOS: isIOS() };
  }
  function installPwa() {
    var st = pwaInstallStatus();
    if (st.standalone) { toast('StarWave 已安装，正在独立窗口中运行'); return Promise.resolve({ ok: false, reason: 'installed' }); }
    if (st.kind === 'ios') {
      toast('iOS 请点浏览器分享按钮 →“添加到主屏幕”');
      return Promise.resolve({ ok: false, reason: 'ios_manual', hint: '分享 → 添加到主屏幕' });
    }
    if (pwaPromptEvent) {
      try {
        pwaPromptEvent.prompt();
        return pwaPromptEvent.userChoice.then(function (choice) {
          if (choice && choice.outcome === 'accepted') toast('StarWave 正在安装');
          else toast('已取消安装');
          pwaPromptEvent = null;
          return { ok: !!(choice && choice.outcome === 'accepted'), reason: (choice && choice.outcome) || 'dismissed' };
        }).catch(function () { return { ok: false, reason: 'prompt_failed' }; });
      } catch (e) { return Promise.resolve({ ok: false, reason: 'prompt_failed' }); }
    }
    if (typeof installStarWavePwa === 'function') {
      try { installStarWavePwa(); return Promise.resolve({ ok: true, reason: 'desktop_path' }); } catch (e) { /* ignore */ }
    }
    toast('浏览器还没有开放安装入口，请稍后刷新再试');
    return Promise.resolve({ ok: false, reason: 'no_prompt_event' });
  }
  function likeCurrentSong() {
    try {
      var song = (typeof currentCoverSong === 'function') ? currentCoverSong() : null;
      if (!song) return { ok: false, reason: 'no_song' };
      var p3 = P3();
      if (!p3 || typeof p3.toggleFavorite !== 'function') return { ok: false, reason: 'favorites_unavailable' };
      var liked = p3.toggleFavorite(song);
      vibrate(15);
      toast(liked ? '已喜欢：' + (song.name || '') : '已取消喜欢');
      return { ok: true, liked: !!liked };
    } catch (e) { return { ok: false, reason: 'error' }; }
  }
  function bindCoverGestures() {
    /* P2：双击喜欢、长按菜单（绑在封面元素上；桌面双击同样可用）。 */
    var targets = [];
    ['control-cover', 'thumb-cover'].forEach(function (id) {
      var el = $(id);
      if (el) targets.push(el);
    });
    targets.forEach(function (el) {
      if (el.__sw4bBound) return;
      el.__sw4bBound = true;
      el.addEventListener('dblclick', function (e) { e.preventDefault(); likeCurrentSong(); });
      el.addEventListener('touchstart', function (e) {
        longPressTarget = el;
        clearTimeout(longPressTimer);
        longPressTimer = setTimeout(function () { showLongPressMenu(e); }, 550);
      }, { passive: true });
      el.addEventListener('touchend', function () { clearTimeout(longPressTimer); });
      el.addEventListener('touchmove', function () { clearTimeout(longPressTimer); });
    });
  }
  function showLongPressMenu(e) {
    try {
      var song = (typeof currentCoverSong === 'function') ? currentCoverSong() : null;
      var menu = $('sw4b-lp-menu');
      if (!menu) return;
      var x = 20, y = 120;
      try {
        if (e && e.touches && e.touches[0]) { x = e.touches[0].clientX; y = e.touches[0].clientY; }
      } catch (err) { /* ignore */ }
      menu.style.left = clamp(x, 8, window.innerWidth - 190) + 'px';
      menu.style.top = clamp(y, 8, window.innerHeight - 190) + 'px';
      menu.style.display = 'block';
      var nameEl = $('sw4b-lp-song');
      if (nameEl) nameEl.textContent = song ? (song.name || '') + ' — ' + (song.artist || '') : '当前无歌曲';
      vibrate(10);
    } catch (err) { /* ignore */ }
  }
  function hideLongPressMenu() {
    var menu = $('sw4b-lp-menu');
    if (menu) menu.style.display = 'none';
  }
  function onDeviceMotion(e) {
    if (!settings.shakeEnabled) return;
    try {
      var acc = e.accelerationIncludingGravity || e.acceleration;
      if (!acc) return;
      var mag = Math.sqrt(Math.pow(acc.x || 0, 2) + Math.pow(acc.y || 0, 2) + Math.pow(acc.z || 0, 2));
      var now = Date.now();
      if (shakeLastAccel != null && Math.abs(mag - shakeLastAccel) > 14 && now - shakeLast > 1500) {
        shakeLast = now;
        if (typeof nextTrack === 'function') { nextTrack(); vibrate(12); toast('摇一摇切歌（实验功能）'); }
      }
      shakeLastAccel = mag;
    } catch (err) { /* ignore */ }
  }
  function onDeviceOrientation(e) {
    if (!settings.gyroEnabled) return;
    try {
      var gamma = clamp(Number(e.gamma) || 0, -30, 30);
      var beta = clamp(Number(e.beta) || 0, -30, 30);
      if (particle.bg) particle.bg.style.transform = 'translate(' + (gamma * 0.3).toFixed(1) + 'px,' + (beta * 0.2).toFixed(1) + 'px) ' + (particle.canvas ? particle.canvas.style.transform || '' : '');
    } catch (err) { /* ignore */ }
  }
  function setShakeEnabled(on) {
    settings.shakeEnabled = !!on;
    saveSettings();
    try {
      if (on) window.addEventListener('devicemotion', onDeviceMotion);
      else window.removeEventListener('devicemotion', onDeviceMotion);
    } catch (e) { /* ignore */ }
    toast(on ? '摇一摇切歌已开启（实验功能，可能不灵敏）' : '摇一摇切歌已关闭');
    renderMobileRow();
    return settings.shakeEnabled;
  }
  function setGyroEnabled(on) {
    /* 陀螺仪镜头：实验功能；iOS 需在用户手势内申请权限，失败则只提示、不硬上。 */
    if (on && typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function') {
      DeviceOrientationEvent.requestPermission().then(function (res) {
        if (res === 'granted') { settings.gyroEnabled = true; saveSettings(); window.addEventListener('deviceorientation', onDeviceOrientation); toast('陀螺仪镜头已开启（实验功能）'); }
        else { settings.gyroEnabled = false; saveSettings(); toast('陀螺仪权限未授予，已保持关闭'); }
        renderMobileRow();
      }).catch(function () { settings.gyroEnabled = false; saveSettings(); toast('陀螺仪权限申请失败，已保持关闭'); renderMobileRow(); });
      return settings.gyroEnabled;
    }
    settings.gyroEnabled = !!on;
    saveSettings();
    try {
      if (on) window.addEventListener('deviceorientation', onDeviceOrientation);
      else window.removeEventListener('deviceorientation', onDeviceOrientation);
    } catch (e) { /* ignore */ }
    toast(on ? '陀螺仪镜头已开启（实验功能）' : '陀螺仪镜头已关闭');
    renderMobileRow();
    return settings.gyroEnabled;
  }
  function applyPortraitShelf() {
    /* P1：3D 歌单架竖屏布局。窄屏竖屏时舞台模式歌单架会遮挡歌词，改为侧栏模式；
       同时给 body 加竖屏 class，CSS 做控制台/控制栏的竖屏适配。 */
    try {
      var portrait = window.innerHeight > window.innerWidth && window.innerWidth <= 640;
      document.body.classList.toggle('sw4b-portrait', portrait);
      if (portrait && typeof fx !== 'undefined' && fx && fx.shelf === 'stage' && typeof setShelfMode === 'function') {
        setShelfMode('side');
        return { portrait: true, shelf: 'side', reason: 'stage_to_side' };
      }
      return { portrait: portrait, shelf: (typeof fx !== 'undefined' && fx) ? fx.shelf : 'unknown', reason: 'checked' };
    } catch (e) { return { portrait: false, reason: 'error' }; }
  }

  /* ---------- 状态 ---------- */
  var state = { lastDj: null, lastRecommend: null, panelTab: 'dj' };

  /* ---------- 界面：悬浮入口 + 面板 ---------- */
  var TABS = [
    { id: 'dj', label: 'AI DJ' }, { id: 'rec', label: '为你推荐' }, { id: 'report', label: '音乐报告' },
    { id: 'theme', label: '主题' }, { id: 'visual', label: '视觉·粒子' }, { id: 'pet', label: '听歌宠物' },
    { id: 'mobile', label: '手机' }
  ];
  function injectCss() {
    if ($('sw4b-style')) return;
    var css = [
      '#sw4b-fab{position:fixed;right:16px;bottom:calc(96px + env(safe-area-inset-bottom,0px));z-index:40;width:52px;height:52px;border-radius:50%;border:1px solid rgba(255,255,255,.25);background:linear-gradient(135deg,var(--sw4b-accent,#7dd3fc),var(--sw4b-accent2,#a5b4fc));color:#0b1220;font-size:22px;cursor:pointer;box-shadow:0 6px 24px rgba(0,0,0,.45)}',
      '#sw4b-panel{position:fixed;z-index:41;right:12px;bottom:calc(160px + env(safe-area-inset-bottom,0px));width:min(430px,calc(100vw - 24px));max-height:min(72vh,640px);overflow:auto;background:rgba(10,14,22,.96);border:1px solid rgba(255,255,255,.16);border-radius:16px;color:#f1f5f9;font-family:var(--sw4b-font,system-ui);box-shadow:0 12px 48px rgba(0,0,0,.55);display:none}',
      '#sw4b-panel.open{display:block}',
      '#sw4b-panel h2{font-size:16px;margin:14px 16px 4px}',
      '#sw4b-panel h3{font-size:13px;margin:12px 0 6px;color:var(--sw4b-accent,#7dd3fc)}',
      '.sw4b-tabs{display:flex;flex-wrap:wrap;gap:6px;padding:10px 12px 0}',
      '.sw4b-tabs button{background:rgba(255,255,255,.07);color:#e2e8f0;border:1px solid rgba(255,255,255,.12);border-radius:999px;padding:6px 10px;font-size:12px;cursor:pointer}',
      '.sw4b-tabs button.active{background:var(--sw4b-accent,#7dd3fc);color:#0b1220;border-color:transparent}',
      '.sw4b-body{padding:6px 16px 16px;font-size:13px;line-height:1.6}',
      '.sw4b-body button{background:rgba(255,255,255,.09);color:#f1f5f9;border:1px solid rgba(255,255,255,.16);border-radius:9px;padding:7px 12px;font-size:12.5px;cursor:pointer;margin:3px 4px 3px 0}',
      '.sw4b-body button.primary{background:var(--sw4b-accent,#7dd3fc);color:#0b1220;border-color:transparent}',
      '.sw4b-body select,.sw4b-body input[type=text]{background:#14161c;color:#fff;border:1px solid rgba(255,255,255,.16);border-radius:8px;padding:6px 8px;font-size:12.5px;max-width:100%}',
      '.sw4b-note{color:#94a3b8;font-size:12px}',
      '.sw4b-song{display:flex;justify-content:space-between;gap:8px;padding:5px 0;border-bottom:1px solid rgba(255,255,255,.06);cursor:pointer}',
      '.sw4b-song:hover{background:rgba(255,255,255,.05)}',
      '.sw4b-row{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.06)}',
      '.sw4b-theme-chip{display:inline-block;width:14px;height:14px;border-radius:50%;margin-right:6px;vertical-align:-2px}',
      '#sw4b-lp-menu{position:fixed;z-index:60;display:none;width:180px;background:rgba(10,14,22,.97);border:1px solid rgba(255,255,255,.18);border-radius:12px;color:#f1f5f9;padding:8px;box-shadow:0 10px 32px rgba(0,0,0,.5);font-size:13px}',
      '#sw4b-lp-menu button{display:block;width:100%;text-align:left;background:none;border:0;color:#f1f5f9;padding:8px;border-radius:8px;cursor:pointer}',
      '#sw4b-lp-menu button:hover{background:rgba(255,255,255,.08)}',
      '@media (max-width:640px) and (orientation:portrait){body.sw4b-portrait #sw4b-panel{right:8px;left:8px;width:auto;bottom:calc(150px + env(safe-area-inset-bottom,0px));max-height:62vh}}',
      '@media (max-width:640px){#sw4b-fab{right:12px;bottom:calc(88px + env(safe-area-inset-bottom,0px))}}'
    ].join('\n');
    var st = document.createElement('style');
    st.id = 'sw4b-style';
    st.textContent = css;
    document.head.appendChild(st);
  }
  function ensurePanelDom() {
    if ($('sw4b-panel')) return true;
    try {
      injectCss();
      var fab = document.createElement('button');
      fab.id = 'sw4b-fab';
      fab.title = 'StarWave 智能层（AI DJ / 推荐 / 报告 / 主题 / 视觉 / 宠物 / 手机）';
      fab.setAttribute('aria-label', '打开智能层面板');
      fab.textContent = '✦';
      fab.addEventListener('click', function () { togglePanel(); });
      document.body.appendChild(fab);
      var panel = document.createElement('div');
      panel.id = 'sw4b-panel';
      panel.setAttribute('role', 'dialog');
      panel.setAttribute('aria-label', 'StarWave 智能层');
      panel.innerHTML = '<h2>✦ 智能层 <span style="float:right;cursor:pointer" id="sw4b-close" title="关闭">✕</span></h2>' +
        '<div class="sw4b-tabs">' + TABS.map(function (t) { return '<button data-tab="' + t.id + '">' + t.label + '</button>'; }).join('') + '</div>' +
        '<div class="sw4b-body" id="sw4b-body"></div>';
      document.body.appendChild(panel);
      panel.querySelectorAll('[data-tab]').forEach(function (b) {
        b.addEventListener('click', function () { showTab(b.getAttribute('data-tab')); });
      });
      $('sw4b-close').addEventListener('click', function () { togglePanel(false); });
      var lp = document.createElement('div');
      lp.id = 'sw4b-lp-menu';
      lp.innerHTML = '<div id="sw4b-lp-song" style="padding:4px 8px;color:#94a3b8;font-size:12px"></div>' +
        '<button data-lp="like">♥ 喜欢 / 取消喜欢</button>' +
        '<button data-lp="next">⏭ 下一首播放</button>' +
        '<button data-lp="queue">＋ 加入播放队列</button>' +
        '<button data-lp="close">关闭</button>';
      document.body.appendChild(lp);
      lp.querySelectorAll('[data-lp]').forEach(function (b) {
        b.addEventListener('click', function () {
          var act = b.getAttribute('data-lp');
          hideLongPressMenu();
          if (act === 'like') likeCurrentSong();
          else if (act === 'next') { try { if (typeof nextTrack === 'function') nextTrack(); vibrate(12); } catch (e) { /* ignore */ } }
          else if (act === 'queue') {
            try {
              var song = (typeof currentCoverSong === 'function') ? currentCoverSong() : null;
              var p3 = P3();
              if (song && p3 && typeof p3.addToQueue === 'function') { p3.addToQueue(song, false); toast('已加入播放队列'); }
              else toast('当前无可加入的歌曲');
            } catch (e) { /* ignore */ }
          }
        });
      });
      document.addEventListener('click', function (e) {
        var menu = $('sw4b-lp-menu');
        if (menu && menu.style.display === 'block' && !menu.contains(e.target)) hideLongPressMenu();
      });
      return true;
    } catch (e) { return false; }
  }
  function togglePanel(force) {
    if (!ensurePanelDom()) return false;
    var panel = $('sw4b-panel');
    var open = force != null ? force : !panel.classList.contains('open');
    panel.classList.toggle('open', open);
    if (open) showTab(state.panelTab || 'dj');
    return open;
  }
  function showTab(tab) {
    state.panelTab = tab;
    try {
      document.querySelectorAll('#sw4b-panel [data-tab]').forEach(function (b) {
        b.classList.toggle('active', b.getAttribute('data-tab') === tab);
      });
    } catch (e) { /* ignore */ }
    var body = $('sw4b-body');
    if (!body) return;
    if (tab === 'dj') renderDjTab(body);
    else if (tab === 'rec') renderRecTab(body);
    else if (tab === 'report') renderReportTab(body);
    else if (tab === 'theme') renderThemeTab(body);
    else if (tab === 'visual') renderVisualTab(body);
    else if (tab === 'pet') renderPetTab(body);
    else if (tab === 'mobile') renderMobileTab(body);
  }
  function songRows(songs, onPlay) {
    return (songs || []).map(function (s, i) {
      return '<div class="sw4b-song" data-i="' + i + '"><span>' + esc(s.name || '未知') + ' — ' + esc(s.artist || '') + '</span><span class="sw4b-note">' + esc(s.publicSourceLabel || s.provider || '') + '</span></div>';
    }).join('');
  }
  function bindSongRows(body, songs, onPlay) {
    body.querySelectorAll('.sw4b-song').forEach(function (el) {
      el.addEventListener('click', function () { onPlay(parseInt(el.getAttribute('data-i'), 10) || 0); });
    });
  }
  function renderDjTab(body) {
    var dj = state.lastDj;
    var slot = djTimeSlot();
    var weather = djWeatherInfo();
    body.innerHTML = '<h3>规则 AI DJ</h3>' +
      '<p class="sw4b-note">按时间 / 天气 / 心情 / 本地画像拼歌单，用天气电台 + 每日推荐 + 演示曲的现成积木。串词为本地模板生成，<b>规则生成，非大模型</b>；不接任何模型服务、不产生费用。</p>' +
      '<p>当前时段：' + slot.label + ' · 天气：' + esc(weather.label || '未知') + ' ' + esc(weather.city || '') + ' · 常听歌手：' + esc(djTopArtists(3).join('、') || '暂无（冷启动）') + '</p>' +
      '<label>心情 <select id="sw4b-dj-mood">' +
      '<option value="auto">自动（按天气/时段）</option>' +
      ['清醒', '轻快', '专注', '慵懒', '治愈', '浪漫', '安静'].map(function (m) { return '<option value="' + m + '"' + (settings.djMood === m ? ' selected' : '') + '>' + m + '</option>'; }).join('') +
      '</select></label> ' +
      '<button class="primary" id="sw4b-dj-gen">生成今日 DJ 歌单</button> ' +
      '<button id="sw4b-dj-play">▶ 开始播放</button>' +
      '<div id="sw4b-dj-out">' + (dj ? '<p>🎙 ' + esc(dj.line) + ' <span class="sw4b-note">（' + esc(dj.generatedBy) + ' · ' + esc(dj.slotLabel) + ' · ' + esc(dj.mood) + '）</span></p>' + songRows(dj.songs) : '<p class="sw4b-note">还没有 DJ 歌单，点“生成”试试。</p>') + '</div>';
    var moodSel = $('sw4b-dj-mood');
    if (moodSel) moodSel.addEventListener('change', function () { settings.djMood = moodSel.value; saveSettings(); });
    $('sw4b-dj-gen').addEventListener('click', function () {
      generateDj({ mood: settings.djMood }).then(function (d) {
        showTab('dj');
        toast('DJ 歌单已生成：' + d.songs.length + ' 首（规则生成，非大模型）');
      });
    });
    $('sw4b-dj-play').addEventListener('click', function () {
      if (!state.lastDj) {
        generateDj({ mood: settings.djMood }).then(function () { playDj(); showTab('dj'); });
      } else playDj();
    });
    if (dj) bindSongRows(body, dj.songs, function (i) { playDj(); try { if (typeof playQueueAt === 'function') playQueueAt(i); } catch (e) { /* ignore */ } });
  }
  function renderRecTab(body) {
    var rec = state.lastRecommend;
    body.innerHTML = '<h3>混合推荐</h3>' +
      '<p class="sw4b-note">平台推荐（网易云 recommend_songs，未登录会诚实回退）+ 本地混合推荐（听歌历史 + 画像）+ 跨平台去重与可播性排序。冷启动用“今日聆听 / 为你挑选”兜底。</p>' +
      '<button class="primary" id="sw4b-rec-gen">生成混合推荐</button> ' +
      '<button id="sw4b-rec-play">▶ 播放推荐</button>' +
      '<div id="sw4b-rec-out">' + (rec ?
        '<p>平台推荐 ' + rec.platformCount + ' 首' + (rec.platformReason ? '（' + esc(rec.platformReason) + '）' : '') + ' · 本地画像 ' + rec.localCount + ' 首' + (rec.coldStart ? ' · ' + esc(rec.fallbackLabel) : '') + '</p>' + songRows(rec.songs)
        : '<p class="sw4b-note">还没有推荐，点“生成”试试。</p>') + '</div>';
    $('sw4b-rec-gen').addEventListener('click', function () {
      hybridRecommend().then(function (r) { showTab('rec'); toast('混合推荐已生成：' + r.songs.length + ' 首'); });
    });
    $('sw4b-rec-play').addEventListener('click', function () {
      if (!state.lastRecommend) hybridRecommend().then(function () { playRecommend(); showTab('rec'); });
      else playRecommend();
    });
    if (rec) bindSongRows(body, rec.songs, function (i) { playRecommend(state.lastRecommend, i); });
  }
  function renderReportTab(body) {
    var range = settings.reportRange || 'year';
    var rep = computeReport(range);
    function rangeBtn(r, label) { return '<button data-range="' + r + '"' + (range === r ? ' class="primary"' : '') + '>' + label + '</button>'; }
    body.innerHTML = '<h3>音乐报告 · 本地计算，零上传</h3>' +
      '<p class="sw4b-note">数据只存本机（localStorage），不上传、不留云端副本。可导出 / 清空。</p>' +
      rangeBtn('day', '今日') + rangeBtn('week', '本周') + rangeBtn('month', '本月') + rangeBtn('year', '今年') +
      '<div style="margin-top:8px">' +
      '<p>播放 <b>' + rep.totalPlays + '</b> 次 · 时长 <b>' + rep.totalHours + '</b> 小时 · <b>' + rep.uniqueSongs + '</b> 首歌</p>' +
      '<p>Top 歌手：' + (rep.topArtists.map(function (a) { return esc(a.name) + ' ' + a.count + '次'; }).join('、') || '暂无') + '</p>' +
      '<p>Top 歌曲：' + (rep.topSongs.map(function (s) { return esc(s.name) + ' ' + s.plays + '次'; }).join('、') || '暂无') + '</p>' +
      '<p>心情分布：' + (Object.keys(rep.moods).map(function (k) { return esc(k) + ' ' + rep.moods[k] + '次'; }).join('、') || '暂无') + '</p>' +
      '<p>深夜 Top（22:00–05:00）：' + (rep.lateNightTop.map(function (a) { return esc(a.name) + ' ' + a.count + '次'; }).join('、') || '暂无') + '</p></div>' +
      '<button class="primary" id="sw4b-rep-card">导出年度分享卡片（图片）</button> ' +
      '<button id="sw4b-rep-export">导出数据 JSON</button> ' +
      '<button id="sw4b-rep-clear">清空本机统计</button>';
    body.querySelectorAll('[data-range]').forEach(function (b) {
      b.addEventListener('click', function () { settings.reportRange = b.getAttribute('data-range'); saveSettings(); showTab('report'); });
    });
    $('sw4b-rep-card').addEventListener('click', function () { exportShareCard(computeReport('year')); });
    $('sw4b-rep-export').addEventListener('click', function () { exportReportData(); });
    $('sw4b-rep-clear').addEventListener('click', function () {
      if (window.confirm ? window.confirm('确定清空本机听歌统计吗？此操作不可恢复。') : true) { clearReportData(); showTab('report'); }
    });
  }
  function renderThemeList() {
    var list = $('sw4b-theme-list');
    if (!list) return;
    list.innerHTML = BUILTIN_THEMES.map(function (t) {
      return '<div class="sw4b-row"><span><span class="sw4b-theme-chip" style="background:' + t.colors.accent + '"></span>' + esc(t.name) + ' <span class="sw4b-note">粒子：' + esc(t.particle.type) + '</span></span><span><button data-theme="' + t.id + '"' + (settings.themeId === t.id ? ' class="primary"' : '') + '>应用</button></span></div>';
    }).join('');
    list.querySelectorAll('[data-theme]').forEach(function (b) {
      b.addEventListener('click', function () {
        var t = themeById(b.getAttribute('data-theme'));
        if (t && applyTheme(t)) toast('主题已应用：' + t.name);
      });
    });
  }
  function renderThemeTab(body) {
    body.innerHTML = '<h3>主题包</h3>' +
      '<p class="sw4b-note">主题 = 预设参数 + 配色 + 字体 + 粒子配置的 JSON。支持导入 / 导出；封面取色可自动生成主题。</p>' +
      '<div id="sw4b-theme-list"></div>' +
      '<h3>封面取色 / AI 主题</h3>' +
      '<button class="primary" id="sw4b-theme-cover">从当前封面生成主题</button> ' +
      '<button id="sw4b-theme-dual">生成 DualTheme（自有格式）</button>' +
      '<h3>导入 / 导出</h3>' +
      '<button id="sw4b-theme-export">导出当前主题 JSON</button> ' +
      '<button id="sw4b-dual-export">导出 DualTheme JSON</button><br>' +
      '<label>导入主题 JSON <input type="file" id="sw4b-theme-import" accept="application/json,.json"></label><br>' +
      '<label>导入 DualTheme JSON <input type="file" id="sw4b-dual-import" accept="application/json,.json"></label>' +
      '<p class="sw4b-note" id="sw4b-theme-status">当前主题：' + esc((currentTheme() && currentTheme().name) || '默认') + '。DualTheme 为本站自有格式 starwave-dual-theme，不复制 mineradio.art 的 DualTheme 格式与资产。</p>';
    renderThemeList();
    $('sw4b-theme-cover').addEventListener('click', function () {
      themeFromCover().then(function (res) {
        if (!res.theme) { toast('封面取色失败：' + res.reason + '（已回退默认主题）'); return; }
        if (applyTheme(res.theme)) toast('已应用封面取色主题' + (res.reason ? '（' + res.reason + '）' : ''));
      });
    });
    $('sw4b-theme-dual').addEventListener('click', function () {
      buildDualThemeFromCover().then(function (res) {
        if (!res.ok) { toast('DualTheme 生成失败：' + res.reason); return; }
        if (applyDualTheme(res.dual)) { state.lastDual = res.dual; }
      });
    });
    $('sw4b-theme-export').addEventListener('click', function () { exportTheme(); });
    $('sw4b-dual-export').addEventListener('click', function () {
      if (state.lastDual) { downloadText('starwave-dual-theme.json', JSON.stringify(state.lastDual, null, 2)); toast('DualTheme JSON 已导出'); }
      else {
        buildDualThemeFromCover().then(function (res) {
          if (!res.ok) { toast('DualTheme 生成失败：' + res.reason); return; }
          state.lastDual = res.dual;
          downloadText('starwave-dual-theme.json', JSON.stringify(res.dual, null, 2));
          toast('DualTheme JSON 已导出');
        });
      }
    });
    var ti = $('sw4b-theme-import');
    if (ti) ti.addEventListener('change', function () { if (ti.files && ti.files[0]) importThemeFile(ti.files[0]).then(function () { showTab('theme'); }); });
    var di = $('sw4b-dual-import');
    if (di) di.addEventListener('change', function () { if (di.files && di.files[0]) importDualThemeFile(di.files[0]).then(function (r) { if (r.ok) state.lastDual = r.dual; showTab('theme'); }); });
  }
  function renderVisualTab(body) {
    var ps = particleState();
    body.innerHTML = '<h3>高级粒子 · 3D 场景 · 段落镜头</h3>' +
      '<p class="sw4b-note">粒子数按帧率自适应（接 Phase 2 性能总督：当前档位 ' + esc(ps.governorTier) + '）；Kick 触发与频谱映射复用 Phase 3 的节拍/频谱数据；镜头按歌曲段落自动切换。</p>' +
      '<div class="sw4b-row"><span>粒子形态</span><span><select id="sw4b-particle-type">' +
      [['stardust', '星尘'], ['rain', '雨'], ['snow', '雪'], ['firefly', '萤火']].map(function (o) { return '<option value="' + o[0] + '"' + (settings.particleType === o[0] ? ' selected' : '') + '>' + o[1] + '</option>'; }).join('') +
      '</select></span></div>' +
      '<div class="sw4b-row"><span>场景包</span><span><select id="sw4b-scene">' +
      SCENES.map(function (s) { return '<option value="' + s.id + '"' + (settings.sceneId === s.id ? ' selected' : '') + '>' + s.name + '</option>'; }).join('') +
      '</select></span></div>' +
      '<div class="sw4b-row"><span>粒子开关</span><span><button id="sw4b-p-toggle">' + (ps.running ? '关闭粒子' : '开启粒子') + '</button></span></div>' +
      '<p id="sw4b-shot-label">段落：' + esc(ps.shotLabel || '未开始') + '（镜头已切换）</p>' +
      '<p class="sw4b-note">实时：帧率约 ' + ps.fpsEma + ' fps · 粒子 ' + ps.count + ' 个 · 预算 ' + Math.round(ps.budget * 100) + '% · Kick ' + ps.kick + ' · 频谱低/中/高 ' + ps.spectrum.low.toFixed(2) + '/' + ps.spectrum.mid.toFixed(2) + '/' + ps.spectrum.high.toFixed(2) + '</p>' +
      '<button id="sw4b-p-refresh">刷新实时状态</button>';
    $('sw4b-particle-type').addEventListener('change', function (e) { setParticleType(e.target.value); });
    $('sw4b-scene').addEventListener('change', function (e) { applyScene(e.target.value); });
    $('sw4b-p-toggle').addEventListener('click', function () {
      if (particle.running) stopParticles(); else startParticles();
      showTab('visual');
    });
    $('sw4b-p-refresh').addEventListener('click', function () { showTab('visual'); });
  }
  function renderPetRow() {
    var row = $('sw4b-pet-row');
    if (!row) return;
    var pet = petById(settings.petId);
    row.innerHTML = '<span>' + esc(pet.name) + ' · ' + esc(pet.desc) + '</span><span><button id="sw4b-pet-cycle">换个形象</button> <button id="sw4b-pet-toggle">' + (settings.petEnabled ? '隐藏宠物' : '显示宠物') + '</button></span>';
    $('sw4b-pet-cycle').addEventListener('click', function () { cyclePet(); });
    $('sw4b-pet-toggle').addEventListener('click', function () { setPetEnabled(!settings.petEnabled); });
  }
  function renderPetTab(body) {
    body.innerHTML = '<h3>听歌宠物</h3>' +
      '<p class="sw4b-note">宠物沿播放进度爬行（位置 = 当前播放进度）。形象为本站自绘原创造型，<b>不复制 mineradio.art 的宠物形象</b>（像素爪爪 / 熊猫 / 橘猫 / 金毛 / 赤狐 / 褐兔）。点左下角的宠物可切换形象。</p>' +
      '<div class="sw4b-row" id="sw4b-pet-row"></div>' +
      '<p>可选形象：' + PETS.map(function (p) { return esc(p.name) + '（' + esc(p.desc) + '）'; }).join('；') + '</p>';
    renderPetRow();
  }
  function renderMobileRow() {
    var row = $('sw4b-mobile-rows');
    if (!row) return;
    var font = fontSelfHostedCheck();
    var gest = gestureStatus();
    var pwa = pwaInstallStatus();
    var shelf = 'unknown';
    try { shelf = (typeof fx !== 'undefined' && fx) ? String(fx.shelf || '') : 'unknown'; } catch (e) { /* ignore */ }
    row.innerHTML =
      '<div class="sw4b-row"><span>字体自托管</span><span>' + (font.selfHosted ? '✅ 无外部字体' : '⚠️ 发现外部字体') + '</span></div>' +
      '<div class="sw4b-row"><span>手势（摄像头）</span><span>' + esc(gest.cam) + ' · 默认关闭' + (gest.mobile ? ' · 手机端已守卫' : '') + '</span></div>' +
      '<div class="sw4b-row"><span>3D 歌单架（竖屏）</span><span>' + esc(shelf) + ' <button id="sw4b-shelf-side">侧栏</button> <button id="sw4b-shelf-stage">舞台</button></span></div>' +
      '<div class="sw4b-row"><span>PWA 安装</span><span>' + (pwa.standalone ? '已安装' : pwa.kind === 'ios' ? 'iOS：需手动添加到主屏幕' : pwa.kind === 'android_ready' ? 'Android：可安装' : pwa.kind === 'android_waiting' ? 'Android：等待浏览器安装事件' : '桌面端') + ' <button id="sw4b-pwa-install">安装 / 指引</button></span></div>' +
      '<div class="sw4b-row"><span>双击喜欢 / 长按菜单</span><span>已开启（封面处）</span></div>' +
      '<div class="sw4b-row"><span>摇一摇切歌（实验功能）</span><span><button id="sw4b-shake-toggle">' + (settings.shakeEnabled ? '关闭' : '开启') + '</button></span></div>' +
      '<div class="sw4b-row"><span>陀螺仪镜头（实验功能）</span><span><button id="sw4b-gyro-toggle">' + (settings.gyroEnabled ? '关闭' : '开启') + '</button></span></div>' +
      '<p class="sw4b-note">实验功能说明：摇一摇与陀螺仪依赖设备传感器，在部分机型/浏览器上可能不灵敏或需权限；未授权时保持关闭，不硬上。震动反馈（navigator.vibrate）有则用、无则跳过。</p>';
    $('sw4b-shelf-side').addEventListener('click', function () { try { if (typeof setShelfMode === 'function') setShelfMode('side'); toast('歌单架：侧栏'); } catch (e) { /* ignore */ } renderMobileRow(); });
    $('sw4b-shelf-stage').addEventListener('click', function () { try { if (typeof setShelfMode === 'function') setShelfMode('stage'); toast('歌单架：舞台'); } catch (e) { /* ignore */ } renderMobileRow(); });
    $('sw4b-pwa-install').addEventListener('click', function () { installPwa().then(function () { renderMobileRow(); }); });
    $('sw4b-shake-toggle').addEventListener('click', function () { setShakeEnabled(!settings.shakeEnabled); });
    $('sw4b-gyro-toggle').addEventListener('click', function () { setGyroEnabled(!settings.gyroEnabled); });
  }
  function renderMobileTab(body) {
    body.innerHTML = '<h3>移动端 P1 / P2</h3>' +
      '<p class="sw4b-note">P1：字体自托管、手势默认关闭、3D 歌单架竖屏布局、PWA 安装引导。P2：双击喜欢、长按菜单、震动反馈；摇一摇切歌与陀螺仪镜头为实验功能。</p>' +
      '<div id="sw4b-mobile-rows"></div>';
    renderMobileRow();
  }

  /* ---------- 对外 API ---------- */
  window.starwavePhase4b = {
    version: '0.4.0-phase4b',
    available: true,
    settings: settings,
    /* A */ dj: { generate: generateDj, play: playDj, timeSlot: djTimeSlot, topArtists: djTopArtists, last: function () { return state.lastDj; } },
    /* B */ recommend: { hybrid: hybridRecommend, play: playRecommend, localTop: localTopSongs, platform: neteaseRecommendSongs, last: function () { return state.lastRecommend; } },
    /* C */ report: { compute: computeReport, shareCard: renderShareCard, exportCard: exportShareCard, exportData: exportReportData, clear: clearReportData, source: reportSource },
    /* D */ themes: { list: function () { return BUILTIN_THEMES.slice(); }, get: themeById, apply: applyTheme, current: currentTheme, fromCover: themeFromCover, export: exportTheme, importFile: importThemeFile, validate: validateTheme },
    dualTheme: { buildFromCover: buildDualThemeFromCover, apply: applyDualTheme, importFile: importDualThemeFile, validate: validateDualTheme, last: function () { return state.lastDual || null; } },
    /* E */ particles: { start: startParticles, stop: stopParticles, setType: setParticleType, state: particleState },
    scenes: { list: function () { return SCENES.slice(); }, apply: applyScene, current: function () { return sceneById(settings.sceneId); }, shot: segmentShot },
    /* F */ pet: { list: function () { return PETS.slice(); }, current: function () { return petById(settings.petId); }, cycle: cyclePet, setEnabled: setPetEnabled, draw: drawPet },
    /* G */ mobile: { fonts: fontSelfHostedCheck, gesture: gestureStatus, guard: gestureGuard, pwa: pwaInstallStatus, installPwa: installPwa, portraitShelf: applyPortraitShelf, likeCurrent: likeCurrentSong, shake: setShakeEnabled, gyro: setGyroEnabled, vibrate: vibrate },
    /* UI */ openPanel: function (tab) { togglePanel(true); if (tab) showTab(tab); return true; },
    closePanel: function () { togglePanel(false); return true; },
    status: function () {
      return {
        version: '0.4.0-phase4b',
        theme: (currentTheme() && currentTheme().name) || '默认',
        particle: particleState(),
        pet: { enabled: settings.petEnabled, id: settings.petId },
        fonts: fontSelfHostedCheck(),
        gesture: gestureStatus(),
        pwa: pwaInstallStatus(),
        dj: state.lastDj ? { slot: state.lastDj.slot, songs: state.lastDj.songs.length } : null,
        recommend: state.lastRecommend ? { songs: state.lastRecommend.songs.length, coldStart: state.lastRecommend.coldStart } : null
      };
    }
  };

  /* ---------- 启动 ---------- */
  try {
    /* PWA 安装事件：Android 也接住（基线只接桌面端）；iOS 无事件，走手动指引。 */
    window.addEventListener('beforeinstallprompt', function (e) {
      try {
        if (isIOS()) return;
        if (!pwaPromptEvent) pwaPromptEvent = e;
      } catch (err) { /* ignore */ }
    });
    window.addEventListener('appinstalled', function () { pwaPromptEvent = null; });
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', initPhase4b);
    } else {
      initPhase4b();
    }
  } catch (e) { /* ignore */ }
  function initPhase4b() {
    try { ensurePanelDom(); } catch (e) { /* ignore */ }
    try { gestureGuard(); } catch (e) { /* ignore */ }
    try { applyPortraitShelf(); } catch (e) { /* ignore */ }
    try { window.addEventListener('resize', function () { applyPortraitShelf(); }); } catch (e) { /* ignore */ }
    try { bindCoverGestures(); } catch (e) { /* ignore */ }
    try {
      /* 恢复主题与场景（不覆盖用户已选的歌单架/手势设置）。 */
      var t = currentTheme();
      if (t) applyTheme(t);
      applyScene(settings.sceneId || 'starry', true);
      if (settings.petEnabled) { ensurePetDom(); drawPet(); }
      startParticles();
    } catch (e) { /* ignore */ }
    try {
      if (settings.shakeEnabled) window.addEventListener('devicemotion', onDeviceMotion);
      if (settings.gyroEnabled) window.addEventListener('deviceorientation', onDeviceOrientation);
    } catch (e) { /* ignore */ }
  }
})();
