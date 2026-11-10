/* StarWave Phase 5A (2026-11-10) — Mineradio v2.2.0 可移植项 P1 + P9
 * 移植来源：Mineradio v2.2.0（XxHuberrr/Mineradio-paused，GPL-3.0-only），
 *   public/js/modules/07-fx/00-preset-archive-data.js（presetMeta / presetIcons /
 *   presetDisplayOrder）、04-preset-grid-uniforms.js（accent 卡片样式）、
 *   00-state/09-performance-probe.js（性能探针）、07-fx/08-cache-storage-settings.js
 *   （缓存设置页，桌面版专属——仅思路改写为网页版存储统计，见下）。
 * 修改者：StarWave Phase 5A 实施（2026-11-10）。GPL-3.0-only。
 *
 * 改名（全部已重命名，无上游名称/英文副标/作者残留）：
 *   上游 7–12 号预设（两个同名变体 + 四个付费标记预设）→ 六个新名：
 *   声波丘陵、霓光涟漪、曜环、霓雨、光蝶、潮汐荧光（新名与新描述均为原创措辞）。
 *   付费门控已删除——全部预设免费。计数说明：上游 13 个预设，StarWave
 *   原有 7 个，缺 6 个（报告 §4/§8 的“5 个 / 7→12”是把“同名变体×2”算成了一项，
 *   实际新增 6 个，预设选择器 7 → 13）。
 * 丢弃（schema 对照 spike 结论）：
 *   - nameHtml/descHtml：含英文副标与作者署名 span，不带入；
 *   - 付费标记字段：无付费墙，删除；
 *   - 上游地形预设模块（1,081 行第三方移植）：独立地形/涟漪系统，不是预设数据，
 *     5A 不搬；预设 7–8 在 StarWave 与上游着色器行为一致（壁纸分支），仅缺地形叠加层；
 *   - Sonic Workshop：许可证未核实（REPORT §5.3），不碰；
 *   - lyricColorPresets：StarWave DIY 控制台已有相同列表且已接线，跳过；
 *   - ColorLab 自定义背景：StarWave 已有完整 ColorLab 拾色器，跳过；
 *   - 帧调度器（10-frame-scheduler.js）：无接入点，不改主循环，跳过；
 *     性能总督（Phase 2）已覆盖按帧率自动降档；
 *   - 实时音频监视器（06-sonic-audio-monitor.js）：与 Phase 3 频谱/kick/BPM 重叠，跳过；
 *   - 缓存存储设置 UI：上游是桌面版专属（desktopWindow IPC + 本地路径 + 重启），
 *     网页版改写为 navigator.storage.estimate() 只读统计 + 只清 Cache Storage
 *     （保留离线外壳缓存 starwave-pwa-v1，见下）。
 * 本文件只做加法：向 presetMeta/presetIcons 追加数据并重建预设网格；GLSL 分支、
 *   相机基线、搜索分页按钮接线在 index.html / starwave-netease.js 内完成。
 * 登录 untouched；不含任何红线内容（无解密器 / 硬编码签名盐 / 安全 SDK /
 *   汽水会话端点 / QQ 逆向签名 / cookie 写入 / 硬编码密码）。
 */
(function () {
  'use strict';

  function $(id) { return document.getElementById(id); }
  function toast(msg) {
    try { if (typeof showToast === 'function') showToast(msg); } catch (e) { /* ignore */ }
  }

  /* ---------- Phase 5A 注入样式 ---------- */
  var css = document.createElement('style');
  css.id = 'starwave-phase5-css';
  css.textContent = [
    '.search-load-more{width:calc(100% - 24px);margin:10px 12px 12px;display:flex;align-items:center;justify-content:center}',
    '.search-load-more:disabled{opacity:.55;cursor:default}',
    /* 预设 accent 卡片样式（移植自上游 .preset-card-premium，已改名、无付费含义） */
    '.preset-card-accent{border-color:color-mix(in srgb,var(--preset-accent) 26%,rgba(255,255,255,.08));background:radial-gradient(circle at 84% 18%,color-mix(in srgb,var(--preset-accent) 18%,transparent),transparent 36%),radial-gradient(circle at 10% 100%,color-mix(in srgb,var(--preset-accent-2) 12%,transparent),transparent 48%),rgba(255,255,255,.025)}',
    '.preset-card-accent:hover{border-color:color-mix(in srgb,var(--preset-accent) 52%,rgba(255,255,255,.15))}',
    '.preset-card-accent .pc-icon{color:var(--preset-accent)}',
    '.preset-card-accent.active .pc-icon{color:var(--preset-accent)}',
    /* 存储占用行 */
    '.sw5-storage{padding:10px 11px;border-radius:12px;border:1px solid rgba(255,255,255,.055);background:rgba(255,255,255,.026)}',
    '.sw5-storage-text{font-size:12px;color:rgba(255,255,255,.85)}',
    '.sw5-storage-text span{color:rgba(255,255,255,.62)}',
    '.sw5-storage-note{font-size:10.5px;line-height:1.5;color:rgba(255,255,255,.42);margin-top:5px}',
    '.sw5-storage-btns{display:flex;gap:8px;margin-top:9px}'
  ].join('\n');
  document.head.appendChild(css);

  /* ---------- P1：6 个新视觉预设（数据移植，已改名） ---------- */
  var PHASE5_PRESETS = [
    { name: '声波丘陵', desc: '层叠声波 · 地形起伏' },
    { name: '霓光涟漪', desc: '流光波纹 · 律动涟漪' },
    { name: '曜环', desc: '金色日冕 · 暗夜轨道', accent: '#e8c98d', accent2: '#8fd8ff' },
    { name: '霓雨', desc: '雨夜霓光 · 城市残影', accent: '#67efff', accent2: '#ff6bb5' },
    { name: '光蝶', desc: '纸翼蝶群 · 流光迁徙', accent: '#f0d7ff', accent2: '#75e6d1' },
    { name: '潮汐荧光', desc: '深海荧光 · 潮汐绽放', accent: '#75f0d0', accent2: '#8178ff' }
  ];
  /* 图标：上游 presetIcons[7..12] 原样移植（通用几何图形，无品牌/文字）。 */
  var PHASE5_PRESET_ICONS = [
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18c2-3 4-3 6 0s4 3 6 0 4-3 6 0"/><path d="M3 12c2-2.5 4-2.5 6 0s4 2.5 6 0 4-2.5 6 0"/><path d="M3 6c2-2 4-2 6 0s4 2 6 0 4-2 6 0"/><circle cx="18" cy="5" r="1.2" fill="currentColor"/></svg>',
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18h18"/><path d="M5 15c1.4-4 2.8-4 4.2 0s2.8 4 4.2 0 2.8-4 4.6 0"/><path d="M4 10c2-2 4-2 6 0s4 2 6 0 3-2 4 0"/><path d="M7 6h10"/><circle cx="18.2" cy="5.8" r="1.35" fill="currentColor"/></svg>',
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.45"><ellipse cx="12" cy="12" rx="9" ry="3.8" transform="rotate(-18 12 12)"/><ellipse cx="12" cy="12" rx="6.3" ry="2.2" transform="rotate(24 12 12)"/><circle cx="12" cy="12" r="2.2" fill="currentColor" stroke="none"/></svg>',
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.45" stroke-linecap="round"><path d="M5 3v8M9 2v15M13 5v8M17 2v18M21 6v9"/><path d="M4 19c4-3 8 3 16-1" opacity=".7"/></svg>',
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.35" stroke-linejoin="round"><path d="M12 12 3 6l3 9 6-3 6 3 3-9-9 6Z"/><path d="M12 12V4M6 15l3 4 3-7 3 7 3-4"/></svg>',
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.35" stroke-linecap="round"><path d="M12 20c-1-5-7-5-7-10 4 0 6 2 7 5 1-3 3-5 7-5 0 5-6 5-7 10Z"/><path d="M12 15c-3-3-2-7 0-11 2 4 3 8 0 11Z"/><circle cx="12" cy="15" r="1.2" fill="currentColor" stroke="none"/></svg>'
  ];
  /* 展示顺序：沿用上游 presetDisplayOrder（索引与上游一致：新预设为 7–12）。 */
  var PHASE5_DISPLAY_ORDER = [0, 9, 10, 11, 12, 6, 7, 8, 5, 4, 2, 1, 3];

  var presetsRegistered = false;
  try {
    if (typeof presetMeta !== 'undefined' && Array.isArray(presetMeta) &&
        typeof presetIcons !== 'undefined' && Array.isArray(presetIcons)) {
      /* 幂等：重复加载不重复追加（以新预设名判断）。 */
      var already = presetMeta.some(function (p) { return p && p.name === '声波丘陵'; });
      if (!already) {
        PHASE5_PRESETS.forEach(function (p) { presetMeta.push({ name: p.name, desc: p.desc, accent: p.accent, accent2: p.accent2 }); });
        PHASE5_PRESET_ICONS.forEach(function (ic) { presetIcons.push(ic); });
      }
      if (typeof presetDisplayOrder !== 'undefined') presetDisplayOrder = PHASE5_DISPLAY_ORDER.slice();
      if (typeof buildPresetGrid === 'function') buildPresetGrid();
      presetsRegistered = true;
    }
  } catch (e) { /* 预设注册失败不阻塞页面 */ }

  /* ---------- P9(d)：性能探针（移植改写自上游 09-performance-probe.js） ----------
   * 命名计时 API（mark / measure / count / summary），只做诊断、不改渲染行为。
   * 与 Phase 2 总督的区别：总督按帧率自动降档；探针记录各环节耗时，供调试查看。
   * 上游的 renderState 克隆耦合已去掉；snapshot 附加 StarWave 总督的 fps/档位。 */
  var PERF_PROBE_VERSION = 'starwave-phase5a';
  var MAX_SAMPLES_PER_METRIC = 90;
  var MAX_TOP_METRICS = 24;

  function probeNow() {
    return (typeof performance !== 'undefined' && performance && performance.now) ? performance.now() : Date.now();
  }
  function probeRound(value, digits) {
    var scale = Math.pow(10, digits || 0);
    return Math.round((Number(value) || 0) * scale) / scale;
  }
  var probeState = {
    version: PERF_PROBE_VERSION,
    enabled: true,
    startedAt: probeNow(),
    lastResetAt: probeNow(),
    metrics: {},
    counters: {}
  };
  function probeMetricFor(name) {
    var key = String(name || 'unknown');
    if (!probeState.metrics[key]) {
      probeState.metrics[key] = { name: key, count: 0, totalMs: 0, avgMs: 0, maxMs: 0, lastMs: 0, samples: [] };
    }
    return probeState.metrics[key];
  }
  function probeMark(name, costMs) {
    if (!probeState.enabled) return null;
    var cost = Number(costMs);
    if (!isFinite(cost) || cost < 0) return null;
    var metric = probeMetricFor(name);
    metric.count += 1;
    metric.totalMs += cost;
    metric.lastMs = cost;
    if (cost > metric.maxMs) metric.maxMs = cost;
    metric.avgMs = metric.totalMs / Math.max(1, metric.count);
    metric.samples.push(probeRound(cost, 3));
    if (metric.samples.length > MAX_SAMPLES_PER_METRIC) metric.samples.shift();
    return metric;
  }
  function probeMarkSince(name, start) { return probeMark(name, probeNow() - Number(start || 0)); }
  function probeBegin(name) {
    var start = probeNow();
    return function finishMetric() { return probeMarkSince(name, start); };
  }
  function probeMeasure(name, fn) {
    var start = probeNow();
    try { return fn(); } finally { probeMarkSince(name, start); }
  }
  function probeCount(name, amount) {
    if (!probeState.enabled) return 0;
    var key = String(name || 'unknown');
    var delta = Number(amount);
    if (!isFinite(delta)) delta = 1;
    probeState.counters[key] = (probeState.counters[key] || 0) + delta;
    return probeState.counters[key];
  }
  function probeMetricSummary(metric) {
    return { count: metric.count, totalMs: probeRound(metric.totalMs, 3), avgMs: probeRound(metric.avgMs, 3), maxMs: probeRound(metric.maxMs, 3), lastMs: probeRound(metric.lastMs, 3), samples: metric.samples.slice(-18) };
  }
  function probeSummary() {
    var metrics = {};
    Object.keys(probeState.metrics).forEach(function (key) { metrics[key] = probeMetricSummary(probeState.metrics[key]); });
    var top = Object.keys(probeState.metrics).map(function (key) { return probeState.metrics[key]; })
      .sort(function (a, b) { return b.totalMs - a.totalMs; })
      .slice(0, MAX_TOP_METRICS)
      .map(function (m) { return { name: m.name, count: m.count, totalMs: probeRound(m.totalMs, 3), avgMs: probeRound(m.avgMs, 3), maxMs: probeRound(m.maxMs, 3), lastMs: probeRound(m.lastMs, 3) }; });
    var gov = null;
    try {
      if (window.starwavePerfGovernor) gov = { fps: window.starwavePerfGovernor.fps, tier: window.starwavePerfGovernor.tier, mode: window.starwavePerfGovernor.mode };
      else if (window.__starwavePerf) gov = { fps: window.__starwavePerf.fps || 0 };
    } catch (e) { /* ignore */ }
    return { version: probeState.version, enabled: probeState.enabled, uptimeMs: probeRound(probeNow() - probeState.startedAt, 1), sinceResetMs: probeRound(probeNow() - probeState.lastResetAt, 1), governor: gov, counters: probeState.counters, topByTotal: top, metrics: metrics };
  }
  function probeReset() {
    probeState.metrics = {};
    probeState.counters = {};
    probeState.lastResetAt = probeNow();
    return probeSummary();
  }
  var perfProbe = {
    version: PERF_PROBE_VERSION,
    now: probeNow,
    mark: probeMark,
    markSince: probeMarkSince,
    begin: probeBegin,
    measure: probeMeasure,
    count: probeCount,
    summary: probeSummary,
    snapshot: probeSummary,
    reset: probeReset
  };
  window.starwavePerfProbe = perfProbe;

  /* ---------- P9(a)：浏览器存储占用（网页版改写） ----------
   * 上游 08-cache-storage-settings.js 是桌面版专属（desktopWindow IPC + 本地
   * 缓存路径 + 重启生效），静态站无对应物。这里只做两件网页上安全的事：
   *   ① navigator.storage.estimate() 只读统计；
   *   ② 清理 Cache Storage（Service Worker / 网页缓存），绝不动 localStorage、
   *      IndexedDB（歌单/自定义背景/节拍缓存都在里面），也绝不动离线外壳缓存
   *      starwave-pwa-v1（见 pwa-service-worker.js，删掉会断离线打开直到重新缓存）。
   * Phase 5A review fix (2026-11-10)：clearCaches 排除 starwave-pwa-v1。 */
  function formatStorageBytes(value) {
    var bytes = Math.max(0, Number(value) || 0);
    if (bytes < 1024) return bytes + ' B';
    var units = ['KB', 'MB', 'GB', 'TB'];
    var index = -1;
    do { bytes /= 1024; index += 1; } while (bytes >= 1024 && index < units.length - 1);
    return (bytes >= 100 || index === 0 ? bytes.toFixed(0) : bytes.toFixed(1)) + ' ' + units[index];
  }
  function refreshStorage() {
    var el = $('sw5-storage-value');
    if (!el) return Promise.resolve(null);
    if (!navigator.storage || typeof navigator.storage.estimate !== 'function') {
      el.textContent = '当前浏览器不支持统计';
      return Promise.resolve(null);
    }
    return navigator.storage.estimate().then(function (est) {
      var used = formatStorageBytes(est.usage || 0);
      var quota = est.quota ? formatStorageBytes(est.quota) : '未知';
      el.textContent = '已用 ' + used + ' / 可用 ' + quota;
      return { usage: est.usage || 0, quota: est.quota || 0 };
    }).catch(function () {
      el.textContent = '统计失败';
      return null;
    });
  }
  /* 离线外壳缓存名，必须与 pwa-service-worker.js 的 CACHE_NAME 一致；清理时排除。 */
  var STARWAVE_PWA_CACHE_NAME = 'starwave-pwa-v1';
  function clearCaches() {
    if (!('caches' in window) || !window.caches.keys) {
      toast('当前浏览器不支持清理网页缓存');
      return Promise.resolve(0);
    }
    return window.caches.keys().then(function (keys) {
      var deletable = keys.filter(function (k) { return k !== STARWAVE_PWA_CACHE_NAME; });
      return Promise.all(deletable.map(function (k) { return window.caches.delete(k); })).then(function () { return deletable.length; });
    }).then(function (n) {
      toast(n ? ('已清理 ' + n + ' 个网页缓存') : '没有可清理的网页缓存');
      refreshStorage();
      return n;
    }).catch(function () {
      toast('清理网页缓存失败');
      return 0;
    });
  }
  (function wireStorageUi() {
    var refreshBtn = $('sw5-storage-refresh');
    if (refreshBtn) refreshBtn.addEventListener('click', function () { refreshStorage(); });
    var clearBtn = $('sw5-storage-clear');
    if (clearBtn) clearBtn.addEventListener('click', function () { clearCaches(); });
    setTimeout(refreshStorage, 600);
  })();

  /* ---------- 对外接口（供验证脚本与后续阶段使用） ---------- */
  window.starwavePhase5 = {
    version: '5a',
    available: true,
    presetsRegistered: presetsRegistered,
    presets: {
      list: function () {
        try { return presetMeta.map(function (p, i) { return { index: i, name: p.name, desc: p.desc, accent: p.accent || null }; }); } catch (e) { return []; }
      },
      count: function () { try { return presetMeta.length; } catch (e) { return 0; } },
      select: function (i) { if (typeof setPreset === 'function') setPreset(i); }
    },
    probe: perfProbe,
    storage: { refresh: refreshStorage, clearCaches: clearCaches, formatBytes: formatStorageBytes }
  };
})();
