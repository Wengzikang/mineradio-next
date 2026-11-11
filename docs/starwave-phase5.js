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
 *     （保留离线外壳缓存 starwave-pwa-*，见下）。
 * 本文件只做加法：向 presetMeta/presetIcons 追加数据并重建预设网格；GLSL 分支、
 *   相机基线、搜索分页按钮接线在 index.html / starwave-netease.js 内完成。
 * 登录 untouched；不含任何红线内容（无解密器 / 硬编码签名盐 / 安全 SDK /
 *   汽水会话端点 / QQ 逆向签名 / cookie 写入 / 硬编码密码）。
 *
 * Phase 5B / P3（2026-11-10）— 舞台歌词预热（单行预热缓存；设计 spike 结论：降级）。
 * 移植来源：Mineradio v2.2.0（XxHuberrr/Mineradio-paused，GPL-3.0-only），
 *   public/js/modules/02-visual/14-stage-lyrics-rendering.js（预热调度思想）。
 * 修改者：StarWave Phase 5B 实施（2026-11-10）。GPL-3.0-only。
 * Spike 映射证据（上游钩子 → StarWave 全局变量）：
 *   - stageLyricPrewarmBuildGuardKey（样式键）→ prewarmStyleKey()：
 *     stageLyrics.palette 四色 + fx.lyricColorMode/lyricColor/lyricLineHeight/
 *     lyricScale/preset/lyricGlow + lyricFont/lyricWeight/lyricLetterSpacing
 *     （字体/字重/字距同样烘焙进画布纹理；Round-2 评审 Minor 1 后补入）；
 *     上游的 display/translation 模式 StarWave 没有，不在键里（StarWave 舞台渲染器无此分支）。
 *   - stageLyricRenderSignatureForCurrentState（需上游 00-state 存储）→ 改写为
 *     trackSwitchToken + 归一化歌词文本 + prewarmStyleKey()；StarWave 无状态存储，
 *     签名即缓存键，消费时再校验 token/style 双字段。
 *   - markStageLyricsPlaybackResume → audio 元素 'play' 事件钩子 + 恢复时预热
 *     当前行与下一行（prewarmOnResume）；'seeked' 事件同理预热跳转目标行。
 *   - stageLyricSingleLinePrewarm（单行缓存，上限 10）→ 本文件单行缓存，
 *     上限按 Phase 2 总督档位缩放（eco 0 / balanced 2 / high 4 / ultra 6），
 *     触发点：切歌（wrap applyLyricsState）、恢复（audio 'play' + 暂停期间
 *     轮询保温恢复行）、接近下一行（500ms 轮询，下一行 8 秒内到达即预热）。
 *   - stageLyricFullTrackWarmup（整轨预热）→ 丢弃：依赖上游 payload/trackEntries
 *     体系（buildStageLyricDisplayPayload），StarWave 没有；且 buildLyricMesh
 *     每行分配一整套 canvas 纹理 + 着色器 + 132 个 spark 点，整轨预热会让
 *     30–60 行网格常驻显存而渲染器又无逐出策略，搬它等于重构渲染器。
 *     单行缓存覆盖真正会卡顿的热路径（下一行切换帧）。
 *   - stageLyricResidentBuild / stageLyricResidentDemand（常驻构建）→ 丢弃：
 *     同样 payload 耦合；单行缓存 + 恢复预热已覆盖其需求。
 *   - stageLyricRestoreWarmup（恢复后预热）→ 见 markStageLyricsPlaybackResume 映射。
 *   - 桌面渲染功率 / 系统内存分支 → 丢弃（静态站无此概念）；低端机保护改用
 *     Phase 2 性能总督档位（eco 档预热完全关闭并清空缓存）。
 * 实现方式：只包装（wrap）index.html 的 showStageLine / applyLyricsState，
 *   不改 index.html 任何一行；buildLyricMesh 本身是 (文本, 调色板, fx) 的纯函数，
 *   与行号无关，离线预建的网格与切换帧现场建的网格完全相同（age/state 在消费
 *   时重置为 0/'in'）。行时间、偏移（__starwaveLyricOffsetSec）、歌词行内容
 *   均不改动——预热只移动“建网格”发生的时刻。
 * P2 已暂停（api-enhanced /lyric 不返回 yrc/ytlrc），本文件不碰任何 YRC 相关逻辑。
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
   *      starwave-pwa-*（见 pwa-service-worker.js，删掉会断离线打开直到重新缓存）。
   * Phase 5A review fix (2026-11-10)：clearCaches 排除 starwave-pwa-v1；2026-11-11 SW 升版为
   *   v2 后改为按前缀 starwave-pwa- 排除，今后 CACHE_NAME 升版无需同步改这里。 */
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
  /* 离线外壳缓存按前缀 starwave-pwa- 排除（与 pwa-service-worker.js 的 CACHE_NAME 同前缀）；
   * 清理时排除，今后 CACHE_NAME 升版无需同步改这里。 */
  var STARWAVE_PWA_CACHE_PREFIX = 'starwave-pwa-';
  function clearCaches() {
    if (!('caches' in window) || !window.caches.keys) {
      toast('当前浏览器不支持清理网页缓存');
      return Promise.resolve(0);
    }
    return window.caches.keys().then(function (keys) {
      var deletable = keys.filter(function (k) { return k.indexOf(STARWAVE_PWA_CACHE_PREFIX) !== 0; });
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

  /* ---------- P3：舞台歌词预热（单行预热缓存） ----------
   * 上游 14-stage-lyrics-rendering.js 的预热调度思想，回填进 StarWave 现有渲染器。
   * 只做加法 + 包装：wrap showStageLine（消费缓存）与 applyLyricsState（切歌触发），
   * 不改 index.html；不改行时间/偏移/歌词行内容；不碰 YRC（P2 已暂停）。
   * 全部失败路径都回退到原有现场构建（wrapper 任何异常都调原函数）。 */
  var PREWARM_MAX_TEXT_LEN = 160; /* 过长行不缓存 */
  var PREWARM_WINDOW_SEC = 8;     /* 下一行 8 秒内到达即预热 */
  var PREWARM_POLL_MS = 500;
  var PREWARM_TIER_CAP = { eco: 0, balanced: 2, high: 4, ultra: 6 };
  var PREWARM_DEFAULT_CAP = 4;

  var prewarmState = {
    items: {},      /* key -> { mesh, key, text, token, styleKey, reason, builtAt } */
    order: [],      /* FIFO 逐出顺序 */
    scheduled: {},  /* key -> setTimeout 句柄（已排队未建） */
    lastTrackToken: null,
    audioWired: false,
    stats: {
      builds: 0, hits: 0, misses: 0, evictions: 0, staleDiscards: 0,
      buildErrors: 0, lastBuildMs: 0,
      triggers: { 'track-switch': 0, resume: 0, 'next-line': 0, seek: 0 }
    }
  };

  function prewarmNow() {
    return (typeof performance !== 'undefined' && performance && performance.now) ? performance.now() : Date.now();
  }
  function prewarmNormalizeText(text) {
    return String(text || '').replace(/\s+/g, ' ').trim();
  }
  /* 样式键：上游 stageLyricPrewarmBuildGuardKey 的 StarWave 改写（见文件头映射）。
   * 字体/字重/字距与 lyricFontCss()/lyricFontWeightValue()/lyricLetterSpacingPx()
   * 同口径：stone-song 恒 900；字重 clamp 500–900 后按 50 取整；字距 clamp -0.04–0.18。 */
  function prewarmStyleKey() {
    try {
      var pal = (typeof stageLyrics !== 'undefined' && stageLyrics && stageLyrics.palette) || {};
      var f = (typeof fx !== 'undefined' && fx) || {};
      var fontKey = '';
      try { fontKey = (typeof normalizeLyricFontKey === 'function') ? normalizeLyricFontKey(f.lyricFont) : String(f.lyricFont || ''); } catch (e) { fontKey = String(f.lyricFont || ''); }
      var weight = 900;
      try {
        if (fontKey !== 'stone-song') {
          var w = Number(f.lyricWeight) || 900;
          weight = Math.round(Math.min(900, Math.max(500, w)) / 50) * 50;
        }
      } catch (e) { weight = 900; }
      var spacing = 0;
      try { spacing = Math.min(0.18, Math.max(-0.04, Number(f.lyricLetterSpacing) || 0)); } catch (e) { spacing = 0; }
      return [
        f.lyricColorMode || '', f.lyricColor || '',
        Number(f.lyricLineHeight) || 1, Number(f.lyricScale) || 1,
        (f.preset == null ? '' : f.preset), f.lyricGlow ? 'glow' : 'noglow',
        pal.primary || '', pal.secondary || '', pal.highlight || '', pal.glowColor || pal.glow || '',
        fontKey, weight, spacing
      ].join('|');
    } catch (e) { return 'unknown'; }
  }
  function prewarmTrackToken() {
    try { return (typeof trackSwitchToken !== 'undefined') ? trackSwitchToken : -1; } catch (e) { return -1; }
  }
  function prewarmCacheKey(text) {
    return prewarmTrackToken() + '::' + prewarmNormalizeText(text) + '::' + prewarmStyleKey();
  }
  function prewarmGovernorTier() {
    try {
      if (window.starwavePerfGovernor && window.starwavePerfGovernor.tier) return window.starwavePerfGovernor.tier;
    } catch (e) { /* ignore */ }
    try {
      if (typeof normalizePerformanceQuality === 'function') return normalizePerformanceQuality(window.fx && window.fx.performanceQuality);
    } catch (e) { /* ignore */ }
    return 'high';
  }
  function prewarmCapForTier(tier) {
    var cap = PREWARM_TIER_CAP[String(tier || '').toLowerCase()];
    return (typeof cap === 'number') ? cap : PREWARM_DEFAULT_CAP;
  }
  function prewarmCap() { return prewarmCapForTier(prewarmGovernorTier()); }
  function prewarmEligible() {
    try {
      if (typeof fx === 'undefined' || !fx || !fx.particleLyrics) return false;
      if (typeof stageLyrics === 'undefined' || !stageLyrics || !stageLyrics.group) return false;
      if (typeof lyricsLines === 'undefined' || !lyricsLines || !lyricsLines.length) return false;
      if (prewarmCap() <= 0) return false; /* eco 档：预热完全关闭 */
      return true;
    } catch (e) { return false; }
  }
  function prewarmDisposeItem(key) {
    var item = prewarmState.items[key];
    if (!item) return;
    if (item.mesh) { try { if (typeof disposeLyricMesh === 'function') disposeLyricMesh(item.mesh); } catch (e) { /* ignore */ } }
    delete prewarmState.items[key];
  }
  function prewarmClear() {
    Object.keys(prewarmState.scheduled).forEach(function (k) {
      try { clearTimeout(prewarmState.scheduled[k]); } catch (e) { /* ignore */ }
    });
    prewarmState.scheduled = {};
    Object.keys(prewarmState.items).forEach(prewarmDisposeItem);
    prewarmState.items = {};
    prewarmState.order = [];
  }
  function prewarmEvictOldest() {
    var cap = prewarmCap();
    while (prewarmState.order.length > 0 && Object.keys(prewarmState.items).length >= cap) {
      var oldest = prewarmState.order.shift();
      if (prewarmState.items[oldest]) {
        prewarmDisposeItem(oldest);
        prewarmState.stats.evictions++;
      }
    }
  }
  function prewarmAudioTime() {
    try {
      if (typeof audio !== 'undefined' && audio) return Number(audio.currentTime || 0) + (window.__starwaveLyricOffsetSec || 0);
    } catch (e) { /* ignore */ }
    return 0;
  }
  /* 与 tickLyricsParticles 同一的行定位逻辑（t + 0.05 容差），只读不改。 */
  function prewarmIndexAtTime() {
    try {
      if (typeof lyricsLines === 'undefined' || !lyricsLines || !lyricsLines.length) return -1;
      var t = prewarmAudioTime();
      var idx = -1;
      for (var i = 0; i < lyricsLines.length; i++) {
        if (Number(lyricsLines[i].t || 0) <= t + 0.05) idx = i; else break;
      }
      return idx;
    } catch (e) { return -1; }
  }
  /* 上游 stageLyricSingleLinePrewarmDelay 的改写：离目标行越近，建得越早。 */
  function prewarmDelayForLine(index) {
    try {
      var line = lyricsLines[index];
      var until = line && isFinite(Number(line.t)) ? Math.max(0, Number(line.t) - prewarmAudioTime()) : 0;
      if (until > 2.0) return 32;
      if (until > 1.0) return 8;
      return 0;
    } catch (e) { return 0; }
  }
  function prewarmBuildLine(key, text, tokenAtSchedule, styleAtSchedule, reason) {
    try {
      if (!prewarmEligible()) return false;
      if (prewarmTrackToken() !== tokenAtSchedule) return false; /* 切歌了 */
      if (prewarmStyleKey() !== styleAtSchedule) return false;   /* 样式变了 */
      if (prewarmState.items[key] && prewarmState.items[key].mesh) return true;
      if (typeof buildLyricMesh !== 'function') return false;
      var t0 = prewarmNow();
      var finish = (typeof probeBegin === 'function') ? probeBegin('prewarm.build') : null;
      var mesh = null;
      try { mesh = buildLyricMesh(text); } finally { if (finish) finish(); }
      var costMs = prewarmNow() - t0;
      if (!mesh) return false;
      prewarmEvictOldest();
      if (Object.keys(prewarmState.items).length >= prewarmCap()) {
        try { if (typeof disposeLyricMesh === 'function') disposeLyricMesh(mesh); } catch (e) { /* ignore */ }
        return false;
      }
      prewarmState.items[key] = {
        mesh: mesh, key: key, text: text,
        token: tokenAtSchedule, styleKey: styleAtSchedule,
        reason: reason, builtAt: Date.now()
      };
      prewarmState.order.push(key);
      prewarmState.stats.builds++;
      prewarmState.stats.lastBuildMs = Math.round(costMs * 100) / 100;
      return true;
    } catch (e) {
      prewarmState.stats.buildErrors++;
      return false;
    }
  }
  /* 返回 'scheduled'（新排队）/ 'cached'（已有）/ false（拒绝）。 */
  function prewarmScheduleLine(index, reason) {
    try {
      if (!prewarmEligible()) return false;
      if (typeof lyricsLines === 'undefined' || !lyricsLines || index < 0 || index >= lyricsLines.length) return false;
      var text = prewarmNormalizeText(lyricsLines[index] && lyricsLines[index].text);
      if (!text || text.length > PREWARM_MAX_TEXT_LEN) return false;
      var key = prewarmCacheKey(text);
      if (prewarmState.items[key] && prewarmState.items[key].mesh) return 'cached';
      if (prewarmState.scheduled[key]) return 'scheduled'; /* 仅排队未建：不是 cached */
      var tokenAtSchedule = prewarmTrackToken();
      var styleAtSchedule = prewarmStyleKey();
      var r = reason || 'next-line';
      prewarmState.scheduled[key] = setTimeout(function () {
        delete prewarmState.scheduled[key];
        prewarmBuildLine(key, text, tokenAtSchedule, styleAtSchedule, r);
      }, prewarmDelayForLine(index));
      if (prewarmState.stats.triggers[r] != null) prewarmState.stats.triggers[r]++;
      return 'scheduled';
    } catch (e) { return false; }
  }
  /* 消费：签名（token + styleKey）不符即视为过期，销毁后回退现场构建。 */
  function prewarmTakeMesh(text) {
    var norm = prewarmNormalizeText(text);
    if (!norm) return null;
    var key = prewarmCacheKey(norm);
    var item = prewarmState.items[key];
    if (!item || !item.mesh) { prewarmState.stats.misses++; return null; }
    delete prewarmState.items[key];
    prewarmState.order = prewarmState.order.filter(function (k) { return k !== key; });
    if (item.token !== prewarmTrackToken() || item.styleKey !== prewarmStyleKey()) {
      try { if (typeof disposeLyricMesh === 'function') disposeLyricMesh(item.mesh); } catch (e) { /* ignore */ }
      prewarmState.stats.staleDiscards++;
      prewarmState.stats.misses++;
      return null;
    }
    prewarmState.stats.hits++;
    return item.mesh;
  }
  var prewarmLastLyricsFingerprint = '';
  function prewarmLyricsFingerprint() {
    try {
      if (typeof lyricsLines === 'undefined' || !lyricsLines || !lyricsLines.length) return '';
      var first = lyricsLines[0], last = lyricsLines[lyricsLines.length - 1];
      return lyricsLines.length + '::' + (first.t || 0) + '::' + (first.text || '') +
        '::' + (last.t || 0) + '::' + (last.text || '');
    } catch (e) { return ''; }
  }
  function prewarmOnLyricsApplied(reason) {
    var fp = prewarmLyricsFingerprint();
    var tokenNow = prewarmTrackToken();
    /* 同一曲目同一份歌词重复应用：不清缓存，只补调度，避免重复建网格。
       token 变了（真切歌，即使同一首歌重播）一定走全清路径——旧 token 的
       缓存键永远不再命中，留着只占显存。 */
    if (fp && fp === prewarmLastLyricsFingerprint && tokenNow === prewarmState.lastTrackToken) {
      var idx0 = prewarmIndexAtTime();
      if (idx0 < 0) idx0 = 0;
      prewarmScheduleLine(idx0, reason || 'track-switch');
      if (idx0 + 1 < (lyricsLines || []).length) prewarmScheduleLine(idx0 + 1, reason || 'track-switch');
      return;
    }
    prewarmLastLyricsFingerprint = fp;
    prewarmState.lastTrackToken = tokenNow;
    prewarmClear(); /* 新歌词 = 旧缓存全部过期 */
    var idx = prewarmIndexAtTime();
    if (idx < 0) idx = 0;
    prewarmScheduleLine(idx, reason || 'track-switch');
    if (idx + 1 < (lyricsLines || []).length) prewarmScheduleLine(idx + 1, reason || 'track-switch');
  }
  function prewarmOnResume(reason) {
    var idx = prewarmIndexAtTime();
    if (idx < 0) idx = 0;
    /* 暂停时当前行已被移入 outgoing，恢复时它要重建——提前建好。 */
    prewarmScheduleLine(idx, reason || 'resume');
    if (idx + 1 < (lyricsLines || []).length) prewarmScheduleLine(idx + 1, reason || 'resume');
  }
  function prewarmOnSeek() {
    var idx = prewarmIndexAtTime();
    if (idx < 0) idx = 0;
    prewarmScheduleLine(idx, 'seek');
    if (idx + 1 < (lyricsLines || []).length) prewarmScheduleLine(idx + 1, 'seek');
  }
  function prewarmWireAudio() {
    try {
      if (prewarmState.audioWired) return true;
      if (typeof audio === 'undefined' || !audio || typeof audio.addEventListener !== 'function') return false;
      audio.addEventListener('play', function () { try { prewarmOnResume('resume'); } catch (e) { /* ignore */ } });
      audio.addEventListener('seeked', function () { try { prewarmOnSeek(); } catch (e) { /* ignore */ } });
      prewarmState.audioWired = true;
      return true;
    } catch (e) { return false; }
  }
  function prewarmPoll() {
    try {
      prewarmWireAudio();
      if (prewarmCap() <= 0) {
        /* eco 档：清空缓存，预热保持关闭（低端机不劣化）。 */
        if (Object.keys(prewarmState.items).length || Object.keys(prewarmState.scheduled).length) prewarmClear();
        return;
      }
      if (!prewarmEligible()) return;
      var token = prewarmTrackToken();
      if (prewarmState.lastTrackToken !== null && token !== prewarmState.lastTrackToken) prewarmClear();
      prewarmState.lastTrackToken = token;
      var idx = prewarmIndexAtTime();
      if (idx < 0) idx = 0;
      if (typeof audio !== 'undefined' && audio && audio.paused) {
        /* 暂停期间把恢复行保温在缓存里：恢复那一帧 tick 会立刻重显当前行，
           若等 'play' 事件才开始建，几乎一定赶不上——所以暂停时就提前建好。 */
        prewarmScheduleLine(idx, 'resume');
      }
      var next = idx + 1;
      if (next < lyricsLines.length) {
        var until = Number(lyricsLines[next].t || 0) - prewarmAudioTime();
        if (until <= PREWARM_WINDOW_SEC) prewarmScheduleLine(next, 'next-line');
      }
    } catch (e) { /* 轮询永不抛错 */ }
  }
  setInterval(prewarmPoll, PREWARM_POLL_MS);

  /* wrap showStageLine：缓存命中时用预建网格，否则原样现场构建。 */
  var prewarmOrigShowStageLine = (typeof showStageLine === 'function') ? showStageLine : null;
  var prewarmShowStageLineWrapped = false;
  if (prewarmOrigShowStageLine) {
    try {
      window.showStageLine = function (text, redrawOnly) {
        try {
          if (!redrawOnly && prewarmEligible()) {
            var cached = prewarmTakeMesh(text);
            if (cached) {
              try { if (typeof createLyricsParticles === 'function') createLyricsParticles(); } catch (e) { /* ignore */ }
              if (stageLyrics.group && text) {
                if (stageLyrics.current) {
                  stageLyrics.current.userData.state = 'out';
                  stageLyrics.current.userData.age = 0;
                  stageLyrics.outgoing.push(stageLyrics.current);
                }
                cached.userData = cached.userData || {};
                cached.userData.age = 0;
                cached.userData.state = 'in';
                stageLyrics.currentText = String(text);
                stageLyrics.group.add(cached);
                stageLyrics.current = cached;
                return;
              }
              /* group 消失或空文本：把已取出的网格放回销毁，走原函数。 */
              try { if (typeof disposeLyricMesh === 'function') disposeLyricMesh(cached); } catch (e) { /* ignore */ }
            }
          }
        } catch (e) { /* wrapper 任何异常都回退原函数 */ }
        return prewarmOrigShowStageLine(text, redrawOnly);
      };
      prewarmShowStageLineWrapped = true;
    } catch (e) { prewarmShowStageLineWrapped = false; }
  }
  /* wrap applyLyricsState：切歌 / 换歌词源时预热首行与下一行。 */
  var prewarmOrigApplyLyricsState = (typeof applyLyricsState === 'function') ? applyLyricsState : null;
  var prewarmApplyLyricsWrapped = false;
  if (prewarmOrigApplyLyricsState) {
    try {
      window.applyLyricsState = function (lines, hasNativeKaraoke, timingSource) {
        var ret = prewarmOrigApplyLyricsState(lines, hasNativeKaraoke, timingSource);
        try { prewarmOnLyricsApplied('track-switch'); } catch (e) { /* ignore */ }
        return ret;
      };
      prewarmApplyLyricsWrapped = true;
    } catch (e) { prewarmApplyLyricsWrapped = false; }
  }
  function prewarmSnapshot() {
    var items = [];
    prewarmState.order.forEach(function (k) {
      var it = prewarmState.items[k];
      if (it) items.push({ key: k, text: it.text, token: it.token, reason: it.reason, builtAt: it.builtAt });
    });
    return {
      version: '5b-p3',
      wrapped: { showStageLine: prewarmShowStageLineWrapped, applyLyricsState: prewarmApplyLyricsWrapped },
      audioWired: prewarmState.audioWired,
      enabled: prewarmEligible(),
      tier: prewarmGovernorTier(),
      cap: prewarmCap(),
      cacheSize: Object.keys(prewarmState.items).length,
      scheduledCount: Object.keys(prewarmState.scheduled).length,
      items: items,
      stats: JSON.parse(JSON.stringify(prewarmState.stats)),
      currentIdx: (typeof stageLyrics !== 'undefined' && stageLyrics) ? stageLyrics.currentIdx : -1,
      lyricsLines: (typeof lyricsLines !== 'undefined' && lyricsLines) ? lyricsLines.length : 0,
      trackToken: prewarmTrackToken()
    };
  }
  var lyricPrewarm = {
    version: '5b-p3',
    snapshot: prewarmSnapshot,
    schedule: prewarmScheduleLine,
    clear: prewarmClear,
    capForTier: prewarmCapForTier,
    styleKey: prewarmStyleKey,
    indexAtTime: prewarmIndexAtTime
  };
  window.starwaveLyricPrewarm = lyricPrewarm;

  /* ---------- 对外接口（供验证脚本与后续阶段使用） ---------- */
  window.starwavePhase5 = {
    version: '5b',
    available: true,
    presetsRegistered: presetsRegistered,
    prewarm: lyricPrewarm,
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
