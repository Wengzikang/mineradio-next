/* StarWave 网易云扫码登录（Web 版，直连公开 api-enhanced 服务）
 * 流程：/login/qr/key → /login/qr/create?qrimg=true → 轮询 /login/qr/check
 *   801 等待扫码 / 802 已扫码待确认 / 803 成功（返回 cookie）/ 800 过期
 * 登录态只存在当前浏览器的 localStorage；不粘贴 Cookie、不解密、不碰 spade_a；
 * 不使用 music.163.com 的浏览器会话 Cookie；扫码由用户自己在网易云音乐 App 里完成。
 * GPL-3.0。 */
var STARWAVE_NETEASE_COOKIE_KEY = 'starwave.netease.cookie';
var STARWAVE_NETEASE_PROFILE_KEY = 'starwave.netease.profile';
var neteaseWebQrTimer = null;
var neteaseWebQrKey = null;
var neteaseWebQrPolls = 0;

function neteaseWebLoginApiBase() {
  return (typeof STARWAVE_NETEASE_API_BASE !== 'undefined' && STARWAVE_NETEASE_API_BASE)
    ? STARWAVE_NETEASE_API_BASE
    : 'https://api-enhanced-pied-rho.vercel.app';
}
/* 注意：出错只记端点名，绝不记完整 URL（URL 里可能带登录态）。 */
function neteaseWebApiJson(path, timeoutMs, label) {
  var controller = (typeof AbortController !== 'undefined') ? new AbortController() : null;
  var timer = null;
  if (controller) timer = setTimeout(function(){ controller.abort(); }, timeoutMs || 12000);
  var p = fetch(neteaseWebLoginApiBase() + path, controller ? { signal: controller.signal } : {})
    .then(function(res){ return res.json(); });
  return p.then(function(data){ if (timer) clearTimeout(timer); return data; }, function(err){
    if (timer) clearTimeout(timer);
    console.warn('[NeteaseWebLogin:' + (label || 'request') + ']', err && err.message ? err.message : err);
    throw err;
  });
}
function neteaseWebApiAuthed(path, timeoutMs, label) {
  var cookie = neteaseWebReadCookie();
  var sep = path.indexOf('?') >= 0 ? '&' : '?';
  return neteaseWebApiJson(path + (cookie ? sep + 'cookie=' + encodeURIComponent(cookie) : ''), timeoutMs, label);
}
function neteaseWebReadCookie() {
  try { return window.localStorage.getItem(STARWAVE_NETEASE_COOKIE_KEY) || ''; } catch (e) { return ''; }
}
function neteaseWebHasSession() { return !!neteaseWebReadCookie(); }
function neteaseWebAuthQuery() {
  var c = neteaseWebReadCookie();
  return c ? '&cookie=' + encodeURIComponent(c) : '';
}
function neteaseWebClearSession() {
  try {
    window.localStorage.removeItem(STARWAVE_NETEASE_COOKIE_KEY);
    window.localStorage.removeItem(STARWAVE_NETEASE_PROFILE_KEY);
  } catch (e) {}
}
function neteaseWebReadProfile() {
  try {
    var raw = window.localStorage.getItem(STARWAVE_NETEASE_PROFILE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) { return null; }
}
function neteaseWebQrSetStatus(text, cls) {
  var st = document.getElementById('qr-status');
  if (st) { st.textContent = text; st.className = cls || ''; }
}
function neteaseWebQrStop() {
  if (neteaseWebQrTimer) { clearInterval(neteaseWebQrTimer); neteaseWebQrTimer = null; }
  neteaseWebQrKey = null;
  neteaseWebQrPolls = 0;
}
async function neteaseWebFetchProfile(cookie) {
  var data;
  try {
    data = await neteaseWebApiJson('/user/account?cookie=' + encodeURIComponent(cookie), 12000, 'user/account');
  } catch (e) { return null; }
  var p = data && data.profile;
  if (!p || !p.userId) return null;
  return {
    userId: p.userId,
    nickname: p.nickname || '',
    avatarUrl: p.avatarUrl || '',
    vipType: (data.account && Number(data.account.vipType)) || 0
  };
}
function neteaseWebApplyProfile(profile) {
  var vipType = Number(profile.vipType || 0) || 0;
  loginStatus = {
    provider: 'netease', loggedIn: true,
    nickname: profile.nickname || '网易云用户',
    userId: profile.userId || '',
    avatar: profile.avatarUrl || '',
    vipType: vipType,
    vipLevel: vipType === 11 ? 'svip' : (vipType > 0 ? 'vip' : 'none'),
    isVip: vipType > 0, isSvip: vipType === 11,
    vipLabel: vipType === 11 ? 'SVIP' : (vipType > 0 ? 'VIP' : 'NO_VIP')
  };
  activeAccountProvider = 'netease';
  try { renderUserBtn(); } catch (e) {}
  try { refreshUserPlaylists(true); } catch (e) {}
}
async function neteaseWebApplyCookie(cookie) {
  var profile = await neteaseWebFetchProfile(cookie);
  if (!profile) { neteaseWebClearSession(); return false; }
  try {
    window.localStorage.setItem(STARWAVE_NETEASE_COOKIE_KEY, cookie);
    window.localStorage.setItem(STARWAVE_NETEASE_PROFILE_KEY, JSON.stringify(profile));
  } catch (e) {}
  neteaseWebApplyProfile(profile);
  return true;
}
async function neteaseWebRestoreSession() {
  var cookie = neteaseWebReadCookie();
  if (!cookie) return false;
  var profile = await neteaseWebFetchProfile(cookie);
  if (!profile) { neteaseWebClearSession(); return false; }
  try { window.localStorage.setItem(STARWAVE_NETEASE_PROFILE_KEY, JSON.stringify(profile)); } catch (e) {}
  neteaseWebApplyProfile(profile);
  return true;
}
async function neteaseWebQrStart() {
  neteaseWebQrStop();
  if (neteaseWebHasSession()) {
    var ok = await neteaseWebRestoreSession();
    if (ok) neteaseWebQrSetStatus('已登录 · ' + (loginStatus.nickname || '网易云音乐'), 'scan');
    else neteaseWebQrSetStatus('登录已失效，请重新扫码', 'fail');
    return;
  }
  var img = document.getElementById('qr-img');
  var shell = document.getElementById('qr-shell');
  if (shell) shell.classList.remove('web-login-preview');
  if (img) img.src = '';
  neteaseWebQrSetStatus('正在生成二维码…', '');
  try {
    var k = await neteaseWebApiJson('/login/qr/key', 12000, 'login/qr/key');
    var unikey = k && k.data && k.data.unikey;
    if (!unikey) throw new Error('获取 key 失败');
    neteaseWebQrKey = unikey;
    var q = await neteaseWebApiJson('/login/qr/create?key=' + encodeURIComponent(unikey) + '&qrimg=true', 15000, 'login/qr/create');
    var qrimg = q && q.data && q.data.qrimg;
    if (!qrimg) throw new Error('生成二维码失败');
    if (img) img.src = qrimg;
    neteaseWebQrSetStatus('请使用网易云音乐 App 扫码', '');
    neteaseWebQrPolls = 0;
    neteaseWebQrTimer = setInterval(neteaseWebQrCheck, 2000);
  } catch (e) {
    neteaseWebQrSetStatus('二维码生成失败：' + (e && e.message ? e.message : '网络异常') + '，请点“刷新二维码”重试', 'fail');
  }
}
async function neteaseWebQrCheck() {
  if (!neteaseWebQrKey) return;
  neteaseWebQrPolls++;
  if (neteaseWebQrPolls > 100) {
    neteaseWebQrStop();
    neteaseWebQrSetStatus('二维码已过期，请刷新', 'fail');
    return;
  }
  var r;
  try {
    r = await neteaseWebApiJson('/login/qr/check?key=' + encodeURIComponent(neteaseWebQrKey), 12000, 'login/qr/check');
  } catch (e) { return; }
  if (!r) return;
  if (r.code === 800) {
    neteaseWebQrStop();
    neteaseWebQrSetStatus('二维码已过期，请刷新', 'fail');
  } else if (r.code === 801) {
    neteaseWebQrSetStatus('请在 App 中扫码', '');
  } else if (r.code === 802) {
    neteaseWebQrSetStatus('已扫码，请在手机上确认…', 'scan');
  } else if (r.code === 803) {
    if (!r.cookie) {
      neteaseWebQrStop();
      neteaseWebQrSetStatus('扫码已确认，但没有拿到登录凭证，请刷新二维码重试', 'fail');
      return;
    }
    neteaseWebQrStop();
    neteaseWebQrSetStatus('登录成功，正在同步账号资料…', 'scan');
    var applied = await neteaseWebApplyCookie(r.cookie);
    if (!applied) {
      neteaseWebQrSetStatus('登录凭证无效，请刷新二维码重试', 'fail');
      return;
    }
    setTimeout(function(){
      try { closeLoginModal(); } catch (e) {}
      try { showToast('欢迎 ' + (loginStatus.nickname || '')); } catch (e) {}
    }, 600);
  }
}
async function neteaseWebFetchMyPlaylists() {
  var profile = neteaseWebReadProfile();
  var uid = profile && profile.userId;
  if (!uid) {
    var fresh = await neteaseWebFetchProfile(neteaseWebReadCookie());
    if (!fresh) return [];
    uid = fresh.userId;
  }
  var out = [];
  var offset = 0;
  for (var page = 0; page < 4; page++) {
    var data = await neteaseWebApiAuthed('/user/playlist?uid=' + encodeURIComponent(uid) + '&limit=100&offset=' + offset, 15000, 'user/playlist');
    var list = (data && data.playlist) || [];
    list.forEach(function(pl){
      out.push({
        id: String(pl.id), name: pl.name || '网易云歌单',
        cover: pl.coverImgUrl || '', trackCount: Number(pl.trackCount || 0) || 0,
        playCount: Number(pl.playCount || 0) || 0,
        subscribed: !!pl.subscribed,
        creator: (pl.creator && pl.creator.nickname) || '',
        provider: 'netease', source: 'netease-web',
        specialType: Number(pl.specialType || 0) || 0
      });
    });
    if (!data || !data.more || !list.length) break;
    offset += list.length;
  }
  return out;
}
async function neteaseWebFetchPlaylistTracks(pid) {
  pid = String(pid || '').trim();
  if (!pid) throw new Error('Missing playlist id');
  var data = await neteaseWebApiAuthed('/playlist/track/all?id=' + encodeURIComponent(pid) + '&limit=1000', 20000, 'playlist/track/all');
  if (!data || data.code !== 200) throw new Error('歌单曲目加载失败');
  var songs = (data.songs || []).map(neteaseWebSongFromRecord).filter(function(s){ return s && s.name && s.id; });
  return { tracks: songs };
}
/* 三处歌单曲目加载点共用的守门函数：未登录或非网易云时返回 null，走原有逻辑。 */
function neteaseWebPlaylistTracksFor(provider, pid) {
  try {
    if (String(provider || '') !== 'netease') return Promise.resolve(null);
    if (!neteaseWebHasSession()) return Promise.resolve(null);
    return neteaseWebFetchPlaylistTracks(pid).then(function(r){ return r; }, function(){ return null; });
  } catch (e) { return Promise.resolve(null); }
}
/* 启动时静默恢复会话：有过期 Cookie 则清除，恢复失败不打断启动。 */
if (typeof document !== 'undefined' && document.addEventListener) {
  document.addEventListener('DOMContentLoaded', function(){
    setTimeout(function(){ neteaseWebRestoreSession(); }, 1200);
  });
}
