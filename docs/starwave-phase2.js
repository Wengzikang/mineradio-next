/* StarWave Phase 2 (2026-11-09)
 * Spotify 官方 PKCE + Web Playback SDK（复用 Folia 应用 "Music"，不新建应用）；
 * Apple Music 仅框架（官方 MusicKit JS 方向，无 Token、无密钥）；
 * 私人电台（规则电台：网易云免费曲 + iTunes 试听）；
 * 移动端 P0（100dvh + 安全区、滑动切歌、Media Session、性能总督）；
 * 设置/关于页（源码链接、音源状态、总督手动档位）。
 * 约束：QQ/酷狗/酷我不接播放；不恢复扩展；不碰桌面代码；无费用；
 * Client Secret、Token、Cookie 绝不进代码；Spotify Client ID 是公开标识。
 * 本文件只做加法：通过包装已有的全局函数接入，不改主脚本流程。
 * 任何一步失败只降级提示，不抛错、不阻塞页面加载。
 */
(function () {
  'use strict';

  /* ---------- 小工具 ---------- */
  function $(id) { return document.getElementById(id); }
  function toast(msg) {
    try {
      if (typeof showToast === 'function') showToast(msg);
    } catch (e) { /* ignore */ }
  }
  function storeGet(k) {
    try { return window.localStorage.getItem(k); } catch (e) { return null; }
  }
  function storeSet(k, v) {
    try { window.localStorage.setItem(k, v); } catch (e) { /* ignore */ }
  }
  function storeDel(k) {
    try { window.localStorage.removeItem(k); } catch (e) { /* ignore */ }
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /* ---------- 移动端 P0：100dvh + 安全区 ---------- */
  var mobileCss = document.createElement('style');
  mobileCss.id = 'starwave-phase2-css';
  mobileCss.textContent = [
    'html,body{height:100vh;height:100dvh}',
    '#bottom-bar{padding-bottom:env(safe-area-inset-bottom,0px)}',
    '#empty-home{bottom:calc(58px + env(safe-area-inset-bottom,0px))}',
    '#top-right{padding-top:env(safe-area-inset-top,0px)}',
    /* 2026-11-10 窄屏顶部重叠修复：按钮组与搜索框上下分两行（按钮组 top:12px，
     * 搜索框 top:68px = 12 + 44 按钮高 + 12 间距，再加安全区偏移）。
     * 本注入样式后于主样式表加载，同等选择器下以这里为准；主样式表 index.html
     * 里的 68px/62px 只是注入失效时的兜底。窄屏同时隐藏“设置与关于”入口（见主样式表）。 */
    '@media (max-width:720px){#top-right,body.desktop-shell #top-right,body.desktop-shell.desktop-fullscreen #top-right{top:12px;right:12px;gap:8px;max-width:calc(100vw - 24px)}}',
    '@media (max-width:720px){body.simple-mode #search-area.peek,body.desktop-shell #search-area.peek,body.desktop-shell.simple-mode #search-area.peek{top:calc(68px + env(safe-area-inset-top,0px))}}',
    '@media (max-width:720px){#search-area.stage-mode.peek{top:calc(62px + env(safe-area-inset-top,0px))}}',
    /* 关于/设置弹窗与电台角标 */
    '#starwave-about-modal .modal{width:min(640px,94vw);max-height:min(780px,calc(100dvh - 64px));overflow:auto;text-align:left}',
    '.sw-about h3{font-size:13px;margin:18px 0 8px;color:rgba(255,255,255,.85)}',
    '.sw-about h3:first-child{margin-top:4px}',
    '.sw-about p,.sw-about li{font-size:12.5px;line-height:1.65;color:rgba(255,255,255,.62)}',
    '.sw-about a{color:#00f5d4}',
    '.sw-src-row{display:flex;justify-content:space-between;gap:10px;align-items:baseline;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.07);font-size:12.5px}',
    '.sw-src-row b{color:rgba(255,255,255,.88);font-weight:600}',
    '.sw-src-row span{color:rgba(255,255,255,.55);text-align:right}',
    '.sw-src-row .ok{color:#7dffb0}.sw-src-row .warn{color:#f4d28a}.sw-src-row .muted{color:rgba(255,255,255,.45)}',
    '.sw-mood-row{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0}',
    '.sw-mood-btn{padding:7px 14px;border-radius:999px;border:1px solid rgba(255,255,255,.16);background:rgba(255,255,255,.05);color:#fff;font-size:12.5px;cursor:pointer}',
    '.sw-mood-btn.active{border-color:#00f5d4;color:#00f5d4}',
    '.sw-gov-row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}',
    '.sw-gov-row select{background:#14161c;color:#fff;border:1px solid rgba(255,255,255,.16);border-radius:8px;padding:6px 8px;font-size:12.5px}',
    '#starwave-radio-chip{position:fixed;z-index:16;left:50%;bottom:calc(96px + env(safe-area-inset-bottom,0px));transform:translateX(-50%);max-width:calc(100vw - 32px);padding:8px 14px;border-radius:999px;background:rgba(10,12,16,.82);border:1px solid rgba(0,245,212,.28);color:rgba(255,255,255,.9);font-size:12px;cursor:pointer;backdrop-filter:blur(16px);display:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
    /* 已停用的 Cookie 粘贴登录入口：Phase 0.5 排除清单排-11 */
    '#qq-cookie-panel{display:none !important}'
  ].join('\n');
  document.head.appendChild(mobileCss);

  /* ---------- 设置/关于页 ---------- */
  var SPOTIFY_CLIENT_ID = '35e5a591884f42d398ab298ab79f16cb'; /* 公开 ID，非密钥 */
  var SPOTIFY_REDIRECT_URI = 'https://wengzikang.github.io/mineradio-next/';
  var SPOTIFY_SCOPES = 'streaming user-read-email user-read-private user-modify-playback-state';
  var SOURCE_URL = 'https://github.com/Wengzikang/mineradio-next';

  function aboutModalHtml() {
    return '' +
      '<div class="modal sw-about" role="dialog" aria-modal="true" aria-label="设置与关于">' +
      '<h2>设置与关于</h2>' +
      '<h3>关于 StarWave</h3>' +
      '<p>星澜音乐 StarWave v0.2.0-phase2 —— 本地优先的可视化音乐台。' +
      '基于 MrChenyh/Mineradio-Web v0.1.0 修改，GPL-3.0，与 Mineradio 官方无关。</p>' +
      '<p>源码：<a href="' + SOURCE_URL + '" target="_blank" rel="noopener">' + SOURCE_URL + '</a>' +
      '（仓库稍后创建；站内源码链接先行公示，代码与线上运行版本对应）。</p>' +
      '<h3>音源状态</h3>' +
      '<div id="sw-source-rows"></div>' +
      '<h3>Spotify</h3>' +
      '<p id="sw-spotify-status">未登录</p>' +
      '<div class="btn-row" style="justify-content:flex-start">' +
      '<button class="modal-btn primary" type="button" onclick="window.starwaveSpotify.login()">Spotify 登录</button>' +
      '<button class="modal-btn" type="button" onclick="window.starwaveSpotify.logout()">退出 Spotify</button>' +
      '</div>' +
      '<p>登录后可搜 Spotify 曲库并用 Web Playback SDK 播完整曲（需 Premium；免费账号仅提示，不伪造播放）。' +
      '开发模式应用限 5 名白名单用户；授权码 10 分钟内有效（PKCE verifier 存 localStorage，跨标签回跳可取回；先换码后清 PKCE）。' +
      '上线前须在 Spotify 应用 Dashboard 把 ' +
      '<code>' + SPOTIFY_REDIRECT_URI + '</code> 加为 Redirect URI，否则报 redirect_uri 不匹配。</p>' +
      '<h3>Apple Music</h3>' +
      '<p id="sw-apple-status">待授权（需 Apple Developer 会员 + 服务端签发 Token，待 Ma 解锁 Apple ID 后办理）。' +
      '本站不复制任何从 music.apple.com 提取 developer token 的做法。</p>' +
      '<h3>私人电台</h3>' +
      '<p>按时间段 / 心情拼真实播放队列：网易云免费曲 + iTunes 30 秒试听，能播、能切歌。</p>' +
      '<div class="sw-mood-row" id="sw-mood-row"></div>' +
      '<div class="btn-row" style="justify-content:flex-start">' +
      '<button class="modal-btn primary" type="button" onclick="window.starwaveRadio.start()">开始电台</button>' +
      '<button class="modal-btn" type="button" onclick="window.starwaveRadio.stop()">停止电台</button>' +
      '</div>' +
      '<p id="sw-radio-status">电台未开始</p>' +
      '<h3>画质总督</h3>' +
      '<div class="sw-gov-row"><label for="sw-gov-select">档位</label>' +
      '<select id="sw-gov-select">' +
      '<option value="auto">自动（按实测帧率降档）</option>' +
      '<option value="eco">手动 · 低</option>' +
      '<option value="balanced">手动 · 中</option>' +
      '<option value="high">手动 · 高</option>' +
      '<option value="ultra">手动 · 超高</option>' +
      '</select><span id="sw-gov-fps">帧率 -- fps</span></div>' +
      '<p>自动模式下连续低帧率会自动降一档（粒子/像素预算随档位变化），只降不自动升；手动选择后以手动为准。</p>' +
      '<h3>移动端</h3>' +
      '<p>100dvh + 安全区适配；主舞台左右滑动切歌；锁屏通过 Media Session 显示标题 / 封面 / 上一首 / 下一首。</p>' +
      '<div class="btn-row"><button class="modal-btn" type="button" onclick="window.starwaveCloseAbout()">关闭</button></div>' +
      '</div>';
  }

  function ensureAboutModal() {
    var m = $('starwave-about-modal');
    if (m) return m;
    m = document.createElement('div');
    m.id = 'starwave-about-modal';
    m.className = 'modal-mask';
    m.innerHTML = aboutModalHtml();
    document.body.appendChild(m);
    var sel = $('sw-gov-select');
    if (sel) {
      sel.addEventListener('change', function () {
        window.starwavePerfGovernor.setMode(sel.value);
      });
    }
    return m;
  }

  function renderSourceRows() {
    var el = $('sw-source-rows');
    if (!el) return;
    var sp = window.starwaveSpotify;
    var spState = sp && sp.isLoggedIn() ? '<span class="ok">已登录</span>' : '<span class="warn">待授权</span>';
    el.innerHTML =
      '<div class="sw-src-row"><b>网易云</b><span>非官方社区服务，仅免费曲 · 未登录</span></div>' +
      '<div class="sw-src-row"><b>Spotify</b><span>' + (sp && sp.isLoggedIn() ? '已登录 · 完整播放需 Premium' : '待授权 · 仅元数据展示') + '</span></div>' +
      '<div class="sw-src-row"><b>Apple Music</b><span>待授权（需 Developer 会员 + 服务端 Token）</span></div>' +
      '<div class="sw-src-row"><b>iTunes 试听</b><span class="ok">可播 · 30 秒公开预览</span></div>' +
      '<div class="sw-src-row"><b>QQ / 酷狗 / 酷我</b><span class="muted">不接播放 · 仅元数据展示 + 跳转官方</span></div>';
    var spEl = $('sw-spotify-status');
    if (spEl && sp) spEl.textContent = sp.statusText();
    var apEl = $('sw-apple-status');
    if (apEl && window.starwaveAppleMusic) apEl.textContent = window.starwaveAppleMusic.statusText();
    var govSel = $('sw-gov-select');
    if (govSel) govSel.value = window.starwavePerfGovernor.mode;
    renderMoodRow();
    void spState;
  }

  var RADIO_MOODS = [
    { id: 'morning', label: '清晨', query: '轻音乐', itunesQuery: 'morning acoustic', hours: [6, 7, 8, 9, 10] },
    { id: 'afternoon', label: '午后', query: '民谣', itunesQuery: 'folk acoustic', hours: [11, 12, 13, 14, 15, 16] },
    { id: 'evening', label: '夜晚', query: '夜曲', itunesQuery: 'nocturne piano', hours: [17, 18, 19, 20, 21, 22] },
    { id: 'focus', label: '专注', query: '钢琴', itunesQuery: 'piano focus', hours: [] },
    { id: 'energy', label: '运动', query: '动感', itunesQuery: 'workout dance', hours: [] },
    { id: 'relax', label: '放松', query: '轻音乐', itunesQuery: 'relaxing piano', hours: [23, 0, 1, 2, 3, 4, 5] }
  ];
  function moodByHour() {
    var h = new Date().getHours();
    for (var i = 0; i < RADIO_MOODS.length; i++) {
      if (RADIO_MOODS[i].hours.indexOf(h) >= 0) return RADIO_MOODS[i].id;
    }
    return 'relax';
  }
  function renderMoodRow() {
    var row = $('sw-mood-row');
    if (!row) return;
    var cur = (window.starwaveRadio && window.starwaveRadio.mood) || moodByHour();
    row.innerHTML = RADIO_MOODS.map(function (m) {
      return '<button class="sw-mood-btn' + (m.id === cur ? ' active' : '') +
        '" type="button" onclick="window.starwaveRadio.setMood(\'' + m.id + '\')">' + m.label + '</button>';
    }).join('');
  }

  window.starwaveOpenAbout = function () {
    ensureAboutModal();
    renderSourceRows();
    window.starwaveAppleMusic.load();
    var m = $('starwave-about-modal');
    if (typeof openGsapModal === 'function') openGsapModal(m);
    else m.classList.add('show');
  };
  window.starwaveCloseAbout = function () {
    var m = $('starwave-about-modal');
    if (!m) return;
    if (typeof closeGsapModal === 'function') closeGsapModal(m);
    else m.classList.remove('show');
  };

  /* 顶部加一个设置/关于入口 */
  (function addAboutButton() {
    var topRight = $('top-right');
    var userBtn = $('user-btn');
    if (!topRight || !userBtn || $('starwave-about-btn')) return;
    var b = document.createElement('button');
    b.id = 'starwave-about-btn';
    b.className = 'icon-btn';
    b.type = 'button';
    b.title = '设置与关于';
    b.setAttribute('aria-label', '设置与关于');
    b.innerHTML = '<svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.9" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3.2"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-1.11-1.55 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.6 8.89a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.55V3a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87c.26.6.86 1 1.55 1H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.51 1z"/></svg>';
    b.addEventListener('click', function () { window.starwaveOpenAbout(); });
    topRight.insertBefore(b, userBtn);
  })();

  /* 首页加一张“私人电台”卡片 */
  (function addRadioHomeCard() {
    var grid = document.querySelector('#empty-home .home-grid');
    if (!grid || $('starwave-radio-card')) return;
    var b = document.createElement('button');
    b.id = 'starwave-radio-card';
    b.className = 'home-card';
    b.setAttribute('data-home-tone', 'mix');
    b.type = 'button';
    b.innerHTML = '<div class="home-card-label">Radio</div>' +
      '<div class="home-card-title">私人电台</div>' +
      '<div class="home-card-sub">按时段 / 心情拼真实队列，点击即播</div>' +
      '<div class="home-card-art"></div>';
    b.addEventListener('click', function () { window.starwaveRadio.start(); });
    grid.appendChild(b);
  })();

  /* ---------- Spotify：官方 PKCE + Web Playback SDK ---------- */
  var SPOTIFY_KEYS = {
    verifier: 'starwave.spotify.pkce_verifier',
    state: 'starwave.spotify.auth_state',
    startedAt: 'starwave.spotify.auth_started_at',
    token: 'starwave.spotify.token'
  };
  /* Folia spotifyWeb 真机教训（2026-11-09）：登录 TTL 取 10 分钟，对齐 Spotify 授权码 10 分钟有效期，不用 5 分钟 */
  var SPOTIFY_LOGIN_TTL_MS = 10 * 60 * 1000;
  var spotifyPlayer = null;
  var spotifyDeviceId = '';
  var spotifyPlayerReady = false;
  var spotifyMe = null;

  function b64url(bytes) {
    var bin = '';
    var arr = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
    for (var i = 0; i < arr.length; i++) bin += String.fromCharCode(arr[i]);
    return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }
  function randomVerifier() {
    var arr = new Uint8Array(48);
    if (window.crypto && window.crypto.getRandomValues) window.crypto.getRandomValues(arr);
    else for (var i = 0; i < arr.length; i++) arr[i] = Math.floor(Math.random() * 256);
    return b64url(arr);
  }
  function sha256B64url(str) {
    if (window.crypto && window.crypto.subtle && window.crypto.subtle.digest) {
      var data = new TextEncoder().encode(str);
      return window.crypto.subtle.digest('SHA-256', data).then(function (buf) { return b64url(buf); });
    }
    return Promise.reject(new Error('crypto.subtle 不可用（需安全上下文）'));
  }
  function buildSpotifyAuthUrl() {
    var verifier = randomVerifier();
    var state = randomVerifier().slice(0, 24);
    /* Folia 教训 1：verifier 必须存 localStorage——iOS Safari 新标签页看不到原标签页的 sessionStorage */
    storeSet(SPOTIFY_KEYS.verifier, verifier);
    storeSet(SPOTIFY_KEYS.state, state);
    storeSet(SPOTIFY_KEYS.startedAt, String(Date.now()));
    return sha256B64url(verifier).then(function (challenge) {
      var u = new URL('https://accounts.spotify.com/authorize');
      u.searchParams.set('response_type', 'code');
      u.searchParams.set('client_id', SPOTIFY_CLIENT_ID);
      u.searchParams.set('scope', SPOTIFY_SCOPES);
      u.searchParams.set('redirect_uri', SPOTIFY_REDIRECT_URI);
      u.searchParams.set('state', state);
      u.searchParams.set('code_challenge_method', 'S256');
      u.searchParams.set('code_challenge', challenge);
      return u.toString();
    });
  }
  function readSpotifyToken() {
    try {
      var raw = storeGet(SPOTIFY_KEYS.token);
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  }
  function saveSpotifyToken(tok) {
    tok = tok || {};
    if (tok.expires_in) tok.expires_at = Date.now() + (Number(tok.expires_in) - 30) * 1000;
    storeSet(SPOTIFY_KEYS.token, JSON.stringify(tok));
  }
  function spotifyTokenExchange(body) {
    return fetch('https://accounts.spotify.com/api/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body
    }).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) throw new Error((data && data.error_description) || (data && data.error) || ('HTTP ' + res.status));
        return data;
      });
    });
  }
  function spotifyRefreshToken() {
    var tok = readSpotifyToken();
    if (!tok || !tok.refresh_token) return Promise.reject(new Error('无 refresh_token'));
    var body = new URLSearchParams();
    body.set('grant_type', 'refresh_token');
    body.set('refresh_token', tok.refresh_token);
    body.set('client_id', SPOTIFY_CLIENT_ID);
    return spotifyTokenExchange(body).then(function (data) {
      if (!data.refresh_token) data.refresh_token = tok.refresh_token;
      saveSpotifyToken(data);
      return data.access_token;
    });
  }
  function spotifyAccessToken() {
    var tok = readSpotifyToken();
    if (!tok || !tok.access_token) return Promise.reject(new Error('未登录 Spotify'));
    if (tok.expires_at && Date.now() > tok.expires_at) return spotifyRefreshToken();
    return Promise.resolve(tok.access_token);
  }
  function spotifyApi(path, opts) {
    opts = opts || {};
    return spotifyAccessToken().then(function (token) {
      var headers = { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' };
      return fetch('https://api.spotify.com/v1' + path, {
        method: opts.method || 'GET',
        headers: headers,
        body: opts.body ? JSON.stringify(opts.body) : undefined
      }).then(function (res) {
        if (res.status === 204) return null;
        return res.json().then(function (data) {
          if (!res.ok) throw new Error((data && data.error && data.error.message) || ('Spotify API HTTP ' + res.status));
          return data;
        });
      });
    });
  }
  function spotifyTrackToSong(t) {
    t = t || {};
    var artists = (t.artists || []).map(function (a) { return a && a.name; }).filter(Boolean);
    var images = (t.album && t.album.images) || [];
    return {
      provider: 'spotify-web', source: 'spotify-web', type: 'spotify-web',
      id: 'spotify:' + (t.id || ''),
      spotifyId: t.id || '', spotifyUri: t.uri || '',
      name: t.name || '', artist: artists.join(' / '),
      album: (t.album && t.album.name) || '',
      cover: images.length ? images[0].url : '',
      duration: Math.round((Number(t.duration_ms) || 0) / 1000),
      publicSourceLabel: 'Spotify',
      playable: true, trial: false
    };
  }
  function spotifySearch(q) {
    q = String(q || '').trim();
    if (!q) return Promise.resolve([]);
    return spotifyApi('/search?q=' + encodeURIComponent(q) + '&type=track&limit=10')
      .then(function (data) {
        var items = (data && data.tracks && data.tracks.items) || [];
        return items.map(spotifyTrackToSong).filter(function (s) { return s.name && s.spotifyUri; });
      })
      .catch(function (err) {
        toast('Spotify 搜索失败：' + err.message);
        return [];
      });
  }
  function ensureSpotifySdk() {
    if (window.Spotify && window.Spotify.Player) return Promise.resolve();
    if (ensureSpotifySdk._p) return ensureSpotifySdk._p;
    ensureSpotifySdk._p = new Promise(function (resolve, reject) {
      var s = document.createElement('script');
      s.src = 'https://sdk.scdn.co/spotify-player.js';
      s.async = true;
      s.onload = function () { resolve(); };
      s.onerror = function () { reject(new Error('Web Playback SDK 加载失败')); };
      document.head.appendChild(s);
      window.onSpotifyWebPlaybackSDKReady = function () { resolve(); };
      setTimeout(function () { reject(new Error('Web Playback SDK 加载超时')); }, 20000);
    });
    return ensureSpotifySdk._p;
  }
  function ensureSpotifyPlayer() {
    if (spotifyPlayer && spotifyPlayerReady) return Promise.resolve(spotifyPlayer);
    return ensureSpotifySdk().then(function () {
      if (spotifyPlayer) return spotifyPlayer;
      return new Promise(function (resolve, reject) {
        var player = new window.Spotify.Player({
          name: 'StarWave',
          getOAuthToken: function (cb) {
            spotifyAccessToken().then(cb).catch(function () { cb(''); });
          },
          volume: 0.8
        });
        player.addListener('ready', function (e) {
          spotifyDeviceId = e.device_id || '';
          spotifyPlayerReady = true;
          resolve(player);
        });
        player.addListener('not_ready', function () { spotifyPlayerReady = false; });
        player.addListener('initialization_error', function (e) { reject(new Error('播放器初始化失败：' + (e && e.message))); });
        player.addListener('authentication_error', function () { reject(new Error('Spotify 授权失效，请重新登录')); });
        player.addListener('account_error', function () { reject(new Error('Spotify 账号无 Premium，无法使用 Web 播放器')); });
        player.addListener('player_state_changed', function (state) {
          if (!state) return;
          try { window.playing = !state.paused; } catch (e) { /* ignore */ }
          var track = state.track_window && state.track_window.current_track;
          if (track) updateMediaSession({ name: track.name, artist: (track.artists || []).map(function (a) { return a.name; }).join(' / '), album: track.album && track.album.name, cover: (track.album && track.album.images && track.album.images[0] && track.album.images[0].url) || '' });
        });
        player.connect();
        spotifyPlayer = player;
        setTimeout(function () { if (!spotifyPlayerReady) reject(new Error('Web 播放器连接超时')); }, 20000);
      });
    });
  }
  function spotifyPlayUri(uri) {
    return ensureSpotifyPlayer().then(function () {
      if (!spotifyDeviceId) throw new Error('Web 播放器未就绪');
      return spotifyApi('/me/player', {
        method: 'PUT',
        body: { device_ids: [spotifyDeviceId], play: false }
      }).catch(function () { /* 转移失败不致命，继续尝试播放 */ })
        .then(function () {
          return spotifyApi('/me/player/play?device_id=' + encodeURIComponent(spotifyDeviceId), {
            method: 'PUT',
            body: { uris: [uri] }
          });
        });
    });
  }
  function drainSpotifyRedirect() {
    var params = new URLSearchParams(window.location.search);
    var code = params.get('code');
    var state = params.get('state');
    var err = params.get('error');
    if (err) {
      toast('Spotify 登录被拒绝：' + err);
      return;
    }
    if (!code) return;
    var savedState = storeGet(SPOTIFY_KEYS.state);
    var verifier = storeGet(SPOTIFY_KEYS.verifier);
    if (!verifier) { toast('Spotify 登录回跳缺少 PKCE 记录（请重新登录）'); return; }
    if (savedState && state && savedState !== state) { toast('Spotify 登录 state 不匹配，已中止'); return; }
    /* Folia 教训 3：登录 TTL 10 分钟（对齐授权码有效期）；超时直接作废，不换码 */
    var startedAt = Number(storeGet(SPOTIFY_KEYS.startedAt) || 0);
    if (!startedAt || (Date.now() - startedAt) > SPOTIFY_LOGIN_TTL_MS) {
      storeDel(SPOTIFY_KEYS.verifier);
      storeDel(SPOTIFY_KEYS.state);
      storeDel(SPOTIFY_KEYS.startedAt);
      toast('Spotify 登录已过期（授权码仅 10 分钟有效），请重新登录');
      return;
    }
    var body = new URLSearchParams();
    body.set('grant_type', 'authorization_code');
    body.set('code', code);
    body.set('redirect_uri', SPOTIFY_REDIRECT_URI);
    body.set('client_id', SPOTIFY_CLIENT_ID);
    body.set('code_verifier', verifier);
    /* 先清 URL 再换码：失败也不留 ?code=，避免每次刷新都重试 */
    try { window.history.replaceState(null, '', window.location.pathname + window.location.hash); } catch (e) { /* ignore */ }
    spotifyTokenExchange(body).then(function (data) {
      saveSpotifyToken(data);
      /* Folia 教训 2：先完成 token 交换、再清除 PKCE 记录——先清后换会让交换中的状态检查返回 'expired' */
      storeDel(SPOTIFY_KEYS.verifier);
      storeDel(SPOTIFY_KEYS.state);
      storeDel(SPOTIFY_KEYS.startedAt);
      return spotifyApi('/me').then(function (me) {
        spotifyMe = me || null;
        toast('Spotify 已登录：' + ((me && me.display_name) || (me && me.email) || ''));
        renderSourceRows();
      }).catch(function () {
        toast('Spotify 已登录');
        renderSourceRows();
      });
    }).catch(function (e) {
      /* 交换已落定（失败）才清 PKCE：授权码一次性使用，残留的 verifier 不再有效 */
      storeDel(SPOTIFY_KEYS.verifier);
      storeDel(SPOTIFY_KEYS.state);
      storeDel(SPOTIFY_KEYS.startedAt);
      toast('Spotify 登录换码失败：' + e.message + '（Redirect URI 须已在 Dashboard 登记）');
    });
  }

  window.starwaveSpotify = {
    clientId: SPOTIFY_CLIENT_ID,
    redirectUri: SPOTIFY_REDIRECT_URI,
    scopes: SPOTIFY_SCOPES,
    /* 登录 TTL 10 分钟（Folia 教训：对齐 Spotify 授权码 10 分钟有效期） */
    loginTtlMs: SPOTIFY_LOGIN_TTL_MS,
    buildAuthUrl: buildSpotifyAuthUrl,
    /* 待完成的登录：verifier/state 是否还在，距发起多久、剩多久过期 */
    pendingLogin: function () {
      var startedAt = Number(storeGet(SPOTIFY_KEYS.startedAt) || 0);
      var hasVerifier = !!storeGet(SPOTIFY_KEYS.verifier);
      if (!startedAt || !hasVerifier) return { pending: false, ageMs: 0, remainingMs: 0, ttlMs: SPOTIFY_LOGIN_TTL_MS };
      var age = Date.now() - startedAt;
      return { pending: age <= SPOTIFY_LOGIN_TTL_MS, ageMs: age,
               remainingMs: Math.max(0, SPOTIFY_LOGIN_TTL_MS - age), ttlMs: SPOTIFY_LOGIN_TTL_MS };
    },
    isLoggedIn: function () { var t = readSpotifyToken(); return !!(t && t.access_token); },
    statusText: function () {
      if (this.isLoggedIn()) {
        return '已登录' + (spotifyMe && spotifyMe.display_name ? '：' + spotifyMe.display_name : '') +
          ' · 完整播放需 Premium；开发模式限 5 名白名单用户';
      }
      return '待授权 · 未登录时仅元数据展示，不承诺播放';
    },
    login: function () {
      buildSpotifyAuthUrl().then(function (url) {
        window.open(url, '_blank', 'noopener');
        toast('已打开 Spotify 授权页，请在新标签完成授权');
      }).catch(function (e) {
        toast('Spotify 登录失败：' + e.message);
      });
    },
    logout: function () {
      storeDel(SPOTIFY_KEYS.token);
      spotifyMe = null;
      if (spotifyPlayer) { try { spotifyPlayer.disconnect(); } catch (e) { /* ignore */ } }
      spotifyPlayer = null;
      spotifyPlayerReady = false;
      spotifyDeviceId = '';
      toast('已退出 Spotify');
      renderSourceRows();
    },
    search: spotifySearch,
    playUri: spotifyPlayUri,
    drainRedirect: drainSpotifyRedirect
  };

  /* 登录弹窗里加一个 Spotify 登录入口 */
  (function addSpotifyLoginButton() {
    var row = document.querySelector('#login-modal .btn-row');
    if (!row || $('starwave-spotify-login-btn')) return;
    var b = document.createElement('button');
    b.id = 'starwave-spotify-login-btn';
    b.className = 'modal-btn';
    b.type = 'button';
    b.textContent = 'Spotify 登录';
    b.addEventListener('click', function () { window.starwaveSpotify.login(); });
    row.appendChild(b);
  })();

  /* 搜索接入：已登录时把 Spotify 结果并进搜索 */
  (function wrapSearch() {
    if (typeof fetchMusicSearchResults !== 'function') return;
    var orig = fetchMusicSearchResults;
    fetchMusicSearchResults = async function (q, mode) {
      var base = await orig(q, mode);
      if (!window.starwaveSpotify.isLoggedIn()) return base;
      try {
        var sp = await spotifySearch(q);
        return base.concat(sp);
      } catch (e) { return base; }
    };
  })();

  /* 播放接入：Spotify 曲目走 Web Playback SDK，不走 <audio> 取地址 */
  function playSpotifyQueueSong(idx) {
    var song = (typeof playQueue !== 'undefined' && playQueue[idx]) || null;
    if (!song) return Promise.resolve(false);
    try {
      if (typeof trackSwitchToken !== 'undefined') window.trackSwitchToken = (window.trackSwitchToken || 0) + 1;
      if (window.audio && !window.audio.paused) { try { window.audio.pause(); } catch (e) { /* ignore */ } }
      window.currentIdx = idx;
      var t = $('thumb-title'); if (t) t.textContent = song.name || '';
      var a = $('thumb-artist'); if (a) a.textContent = song.artist || '';
      var w = $('thumb-wrap'); if (w) w.classList.add('visible');
      if (typeof updateControlTrackInfo === 'function') { try { updateControlTrackInfo(song); } catch (e) { /* ignore */ } }
      updateMediaSession(song);
      updateRadioChip();
    } catch (e) { /* ignore */ }
    if (!window.starwaveSpotify.isLoggedIn()) {
      toast('Spotify 曲目需先登录（关于页 → Spotify 登录），免费账号也需 Premium 才能完整播放');
      return Promise.resolve(true);
    }
    return spotifyPlayUri(song.spotifyUri).then(function () {
      try { window.playing = true; } catch (e) { /* ignore */ }
      return true;
    }).catch(function (e) {
      toast('Spotify 播放失败：' + e.message);
      return true;
    });
  }
  (function wrapPlayback() {
    if (typeof playQueueAt === 'function') {
      var origPlay = playQueueAt;
      playQueueAt = function (idx, opts) {
        var song = (typeof playQueue !== 'undefined' && playQueue[idx]) || null;
        if (song && (song.provider === 'spotify-web' || song.source === 'spotify-web')) {
          return playSpotifyQueueSong(idx);
        }
        var r = origPlay(idx, opts);
        if (r && typeof r.then === 'function') {
          return r.then(function (v) {
            try {
              var s = (typeof playQueue !== 'undefined' && playQueue[window.currentIdx]) || null;
              if (s) updateMediaSession(s);
              updateRadioChip();
            } catch (e) { /* ignore */ }
            return v;
          });
        }
        return r;
      };
    }
    if (typeof nextTrack === 'function') {
      var origNext = nextTrack;
      nextTrack = function () {
        var song = (typeof playQueue !== 'undefined' && playQueue[window.currentIdx]) || null;
        if (song && (song.provider === 'spotify-web' || song.source === 'spotify-web') && spotifyPlayer && spotifyPlayerReady) {
          try { spotifyPlayer.nextTrack(); } catch (e) { origNext(); }
          return;
        }
        return origNext();
      };
    }
    if (typeof prevTrack === 'function') {
      var origPrev = prevTrack;
      prevTrack = function () {
        var song = (typeof playQueue !== 'undefined' && playQueue[window.currentIdx]) || null;
        if (song && (song.provider === 'spotify-web' || song.source === 'spotify-web') && spotifyPlayer && spotifyPlayerReady) {
          try { spotifyPlayer.previousTrack(); } catch (e) { origPrev(); }
          return;
        }
        return origPrev();
      };
    }
  })();

  /* ---------- Apple Music：仅框架 ---------- */
  var appleMusicState = { loaded: false, loadError: '' };
  function appleLoadSdk() {
    if (appleMusicState.loaded || window.MusicKit) { appleMusicState.loaded = !!window.MusicKit; return Promise.resolve(appleMusicState.loaded); }
    if (appleLoadSdk._p) return appleLoadSdk._p;
    appleLoadSdk._p = new Promise(function (resolve) {
      var s = document.createElement('script');
      s.src = 'https://js-cdn.music.apple.com/musickit/v3/musickit.js';
      s.async = true;
      s.onload = function () { appleMusicState.loaded = !!window.MusicKit; resolve(appleMusicState.loaded); };
      s.onerror = function () { appleMusicState.loadError = 'MusicKit JS 加载失败'; resolve(false); };
      document.head.appendChild(s);
      setTimeout(function () { resolve(!!window.MusicKit); }, 15000);
    });
    return appleLoadSdk._p;
  }
  window.starwaveAppleMusic = {
    status: 'pending_auth',
    load: appleLoadSdk,
    statusText: function () {
      return '待授权（需 Apple Developer 会员 + 服务端签发 Token，待 Ma 解锁 Apple ID 后办理）' +
        (appleMusicState.loaded ? ' · MusicKit JS 已加载' : ' · MusicKit JS 未加载');
    },
    /* 目录搜索：框架接口，真实接入前一律返回待授权，不返回假结果 */
    searchCatalog: function (q) {
      return Promise.resolve({ status: 'pending_auth', query: String(q || ''), results: [], message: 'Apple Music 待授权：需 Apple Developer 会员 + 服务端签发 Token' });
    }
  };

  /* ---------- 私人电台：规则电台，真实队列 ---------- */
  var radioState = { active: false, mood: moodByHour(), startedAt: 0, count: 0 };
  function radioChip() {
    var chip = $('starwave-radio-chip');
    if (!chip) {
      chip = document.createElement('div');
      chip.id = 'starwave-radio-chip';
      chip.title = '点击切到下一首';
      chip.addEventListener('click', function () { if (typeof nextTrack === 'function') nextTrack(); });
      document.body.appendChild(chip);
    }
    return chip;
  }
  function updateRadioChip() {
    var chip = radioChip();
    if (!radioState.active) { chip.style.display = 'none'; return; }
    var song = (typeof playQueue !== 'undefined' && playQueue[window.currentIdx]) || null;
    var label = song ? (song.name + ' · ' + (song.publicSourceLabel || songSourceLabelText(song))) : '电台播放中';
    chip.textContent = '私人电台 · ' + moodLabel(radioState.mood) + ' · ' + label;
    chip.style.display = 'block';
    var rs = $('sw-radio-status');
    if (rs) rs.textContent = '电台进行中 · ' + moodLabel(radioState.mood) + ' · 共 ' + radioState.count + ' 首 · 当前：' + label;
  }
  function songSourceLabelText(song) {
    try {
      if (typeof songSourceLabel === 'function') return songSourceLabel(song);
    } catch (e) { /* ignore */ }
    return (song && song.provider) || '';
  }
  function moodLabel(id) {
    for (var i = 0; i < RADIO_MOODS.length; i++) if (RADIO_MOODS[i].id === id) return RADIO_MOODS[i].label;
    return id;
  }
  function interleave(lists, cap) {
    var out = [];
    var seen = {};
    var i = 0, added = true;
    while (out.length < cap && added) {
      added = false;
      for (var k = 0; k < lists.length; k++) {
        var item = lists[k][i];
        if (item) {
          added = true;
          var key = (item.name || '') + '|' + (item.artist || '');
          if (!seen[key]) { seen[key] = true; out.push(item); }
        }
      }
      i++;
    }
    return out;
  }
  function buildRadioQueue(moodId) {
    var def = null;
    for (var i = 0; i < RADIO_MOODS.length; i++) if (RADIO_MOODS[i].id === moodId) def = RADIO_MOODS[i];
    if (!def) def = RADIO_MOODS[0];
    /* 登录后：电台队列只用歌单里的歌（洗牌取 20 首）。 */
    if (typeof starwaveNetEaseLoggedIn === 'function' && starwaveNetEaseLoggedIn() && typeof neteaseWebFetchMyPlaylistSongs === 'function') {
      return neteaseWebFetchMyPlaylistSongs(60).catch(function () { return []; }).then(function (songs) {
        var list = (songs || []).slice();
        for (var i = list.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = list[i]; list[i] = list[j]; list[j] = t; }
        var queue = list.slice(0, 20);
        return { queue: queue, def: def, counts: { neteaseFree: queue.length, itunes: 0 } };
      });
    }
    var neP = (typeof fetchNeteaseWebSearchResults === 'function')
      ? fetchNeteaseWebSearchResults(def.query).catch(function () { return []; })
      : Promise.resolve([]);
    var itP = (typeof fetchItunesPublicSearchResults === 'function')
      ? fetchItunesPublicSearchResults(def.itunesQuery || def.query).catch(function () { return []; })
      : Promise.resolve([]);
    return Promise.all([neP, itP]).then(function (parts) {
      var neList = (parts[0] || []).filter(function (s) { return s && (s.fee || 0) === 0; }).slice(0, 8);
      var itList = (parts[1] || []).slice(0, 6);
      var queue = interleave([neList, itList], 20);
      return { queue: queue, def: def, counts: { neteaseFree: neList.length, itunes: itList.length } };
    });
  }
  window.starwaveRadio = {
    mood: radioState.mood,
    setMood: function (id) {
      radioState.mood = id;
      this.mood = id;
      renderMoodRow();
      toast('电台心情：' + moodLabel(id) + '（下次开始生效）');
    },
    start: function (moodId) {
      var self = this;
      if (moodId) { radioState.mood = moodId; self.mood = moodId; }
      toast('私人电台拼队列中…（' + moodLabel(radioState.mood) + '）');
      return buildRadioQueue(radioState.mood).then(function (built) {
        if (!built.queue.length) { toast((typeof starwaveNetEaseLoggedIn === 'function' && starwaveNetEaseLoggedIn()) ? '电台队列为空：歌单里还没有可播的歌' : '电台队列为空：公共源均不可用，请先登录网易云'); return null; }
        try {
          window.playQueue = built.queue.slice();
          window.currentIdx = -1;
        } catch (e) { /* ignore */ }
        radioState.active = true;
        radioState.startedAt = Date.now();
        radioState.count = built.queue.length;
        renderMoodRow();
        updateRadioChip();
        toast('私人电台已开始：' + moodLabel(radioState.mood) + ' · ' + built.queue.length +
          ' 首（网易云免费 ' + built.counts.neteaseFree + ' / iTunes 试听 ' + built.counts.itunes + '）');
        if (typeof playQueueAt === 'function') return playQueueAt(0, { manual: true, context: { radio: 'starwave', mood: radioState.mood } });
        return built;
      }).catch(function (e) {
        toast('电台启动失败：' + e.message);
        return null;
      });
    },
    stop: function () {
      radioState.active = false;
      updateRadioChip();
      var rs = $('sw-radio-status');
      if (rs) rs.textContent = '电台已停止';
      toast('私人电台已停止（队列保留，可继续点播）');
    },
    status: function () {
      return { active: radioState.active, mood: radioState.mood, count: radioState.count };
    }
  };

  /* ---------- 移动端 P0：滑动切歌 + Media Session ---------- */
  (function initSwipe() {
    var startX = 0, startY = 0, startT = 0, tracking = false;
    function excluded(el) {
      if (!el || !el.closest) return false;
      return !!el.closest('input,textarea,select,#fx-panel,#playlist-panel,.modal-mask,#search-results,#search-box,.mini-queue-popover,#bottom-bar,#starwave-radio-chip');
    }
    document.addEventListener('touchstart', function (e) {
      if (!e.touches || e.touches.length !== 1) return;
      if (excluded(e.target)) { tracking = false; return; }
      tracking = true;
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
      startT = Date.now();
    }, { passive: true });
    document.addEventListener('touchend', function (e) {
      if (!tracking || !e.changedTouches || !e.changedTouches.length) return;
      tracking = false;
      var dx = e.changedTouches[0].clientX - startX;
      var dy = e.changedTouches[0].clientY - startY;
      if (Date.now() - startT > 800) return;
      if (Math.abs(dx) < 70 || Math.abs(dy) > 60) return;
      if (dx < 0) { if (typeof nextTrack === 'function') nextTrack(); }
      else { if (typeof prevTrack === 'function') prevTrack(); }
    }, { passive: true });
  })();

  function updateMediaSession(song) {
    try {
      if (!('mediaSession' in navigator) || !song) return;
      var artwork = [];
      if (song.cover) artwork.push({ src: song.cover, sizes: '512x512', type: 'image/jpeg' });
      navigator.mediaSession.metadata = new MediaMetadata({
        title: song.name || 'StarWave',
        artist: song.artist || '',
        album: song.album || '',
        artwork: artwork
      });
      try { navigator.mediaSession.playbackState = (window.audio && !window.audio.paused) || window.playing ? 'playing' : 'paused'; } catch (e) { /* ignore */ }
    } catch (e) { /* ignore */ }
  }
  (function initMediaSession() {
    try {
      if (!('mediaSession' in navigator)) return;
      navigator.mediaSession.setActionHandler('previoustrack', function () { if (typeof prevTrack === 'function') prevTrack(); });
      navigator.mediaSession.setActionHandler('nexttrack', function () { if (typeof nextTrack === 'function') nextTrack(); });
      navigator.mediaSession.setActionHandler('play', function () {
        if (window.audio && window.audio.paused && typeof togglePlay === 'function') togglePlay();
      });
      navigator.mediaSession.setActionHandler('pause', function () {
        if (window.audio && !window.audio.paused && typeof togglePlay === 'function') togglePlay();
      });
    } catch (e) { /* ignore */ }
    window.starwaveMediaSession = { update: updateMediaSession };
  })();

  /* ---------- 性能总督：按实测帧率自动降档 ---------- */
  var GOVERNOR_TIERS = ['eco', 'balanced', 'high', 'ultra'];
  var governor = {
    mode: 'auto',
    fps: 0,
    tier: '',
    lowStreak: 0,
    lastCheck: 0
  };
  function currentTier() {
    try {
      if (typeof normalizePerformanceQuality === 'function') return normalizePerformanceQuality(window.fx && window.fx.performanceQuality);
    } catch (e) { /* ignore */ }
    return 'high';
  }
  function governorTick() {
    var perf = window.__starwavePerf || null;
    var fps = perf ? (perf.fps || 0) : 0;
    governor.fps = fps;
    var fpsEl = $('sw-gov-fps');
    if (fpsEl) fpsEl.textContent = '帧率 ' + (fps || '--') + ' fps · 当前档位 ' + currentTier();
    if (governor.mode !== 'auto' || !fps) return;
    if (fps < 25) {
      governor.lowStreak++;
      if (governor.lowStreak >= 3) {
        governor.lowStreak = 0;
        var tier = currentTier();
        var idx = GOVERNOR_TIERS.indexOf(tier);
        if (idx > 0) {
          var next = GOVERNOR_TIERS[idx - 1];
          if (typeof setPerformanceQualityMode === 'function') setPerformanceQualityMode(next, true);
          toast('性能总督：实测 ' + fps + 'fps，已自动降至' +
            (next === 'eco' ? '低' : next === 'balanced' ? '中' : next === 'ultra' ? '超高' : '高') + '档');
        }
      }
    } else {
      governor.lowStreak = 0;
    }
  }
  setInterval(governorTick, 2000);
  window.starwavePerfGovernor = {
    get mode() { return governor.mode; },
    get fps() { return governor.fps; },
    get tier() { return currentTier(); },
    setMode: function (m) {
      if (m === 'auto') {
        governor.mode = 'auto';
        toast('性能总督：自动模式');
        return;
      }
      if (GOVERNOR_TIERS.indexOf(m) < 0) return;
      governor.mode = m;
      if (typeof setPerformanceQualityMode === 'function') setPerformanceQualityMode(m, true);
      toast('画质档位已手动设为' + (m === 'eco' ? '低' : m === 'balanced' ? '中' : m === 'ultra' ? '超高' : '高'));
    }
  };

  /* ---------- 审计修复：停用粘贴 Cookie 登录 ---------- */
  (function disableCookieLogin() {
    var msg = '已停用：为保护账号安全，StarWave 不再支持粘贴 Cookie 登录；网易云仅提供免费曲，Spotify 请用官方 OAuth 登录。';
    if (typeof submitCookieLogin === 'function') {
      var origSubmit = submitCookieLogin;
      submitCookieLogin = function () { toast(msg); return false; };
      submitCookieLogin._starwaveDisabled = true;
      void origSubmit;
    }
    if (typeof toggleQQCookiePanel === 'function') {
      toggleQQCookiePanel = function () { toast(msg); };
    }
  })();

  /* 启动时处理 Spotify 回跳 */
  try { drainSpotifyRedirect(); } catch (e) { /* ignore */ }
})();
