/* StarWave 网易云模块 (Phase 2 拆移至独立文件)
 * 原 index.html 第 2790-2971 行。网易云走公开 api-enhanced 社区服务；未登录仅免费曲，
 * 登录后（扫码，见 starwave-netease-login.js）可用账号权限内曲目。
 * 演示曲目已于 2026-11-10 按 Ma 的要求全部删除。GPL-3.0。 */
/* StarWave 网易云公开 API（与 Folia Web 相同方式：公开 api-enhanced 服务；登录见 starwave-netease-login.js） */
var STARWAVE_NETEASE_API_BASE = 'https://api-enhanced-pied-rho.vercel.app';

/* StarWave 网易云 Web 接入（Phase 1）：与 Folia Web 相同方式，走公开 api-enhanced 服务，无扩展；登录态见 starwave-netease-login.js */
var neteaseWebSearchError = '';
function neteaseWebFetchJson(url, timeoutMs) {
  var controller = (typeof AbortController !== 'undefined') ? new AbortController() : null;
  var timer = null;
  if (controller) timer = setTimeout(function(){ controller.abort(); }, timeoutMs || 12000);
  var p = fetchPublicJson(url, controller ? { signal: controller.signal } : {});
  return p.then(function(data){ if (timer) clearTimeout(timer); return data; }, function(err){ if (timer) clearTimeout(timer); throw err; });
}
function neteaseWebSongFromRecord(record, index) {
  record = record || {};
  var artists = Array.isArray(record.ar) ? record.ar : (Array.isArray(record.artists) ? record.artists : []);
  var artistNames = artists.map(function(a){ return a && a.name; }).filter(Boolean);
  var album = record.al || {};
  return {
    provider: 'netease-web',
    source: 'netease-web',
    type: 'netease-web',
    id: record.id,
    neteaseId: record.id,
    name: record.name || '',
    artist: artistNames.join(' / '),
    album: album.name || '',
    cover: album.picUrl || '',
    duration: Math.round((Number(record.dt) || 0) / 1000),
    fee: record.fee,
    playable: true,
    publicSourceLabel: '网易云',
    raw: record
  };
}
async function fillNeteaseWebCovers(songs) {
  var ids = (songs || []).filter(function(s){ return s && s.neteaseId && !s.cover; }).map(function(s){ return s.neteaseId; });
  if (!ids.length) return;
  try {
    var data = await neteaseWebFetchJson(STARWAVE_NETEASE_API_BASE + '/song/detail?ids=' + ids.join(','), 10000);
    var coverMap = {};
    (data && data.songs || []).forEach(function(rec){
      if (rec && rec.id && rec.al && rec.al.picUrl) coverMap[rec.id] = rec.al.picUrl;
    });
    (songs || []).forEach(function(s){
      if (s && !s.cover && coverMap[s.neteaseId]) s.cover = coverMap[s.neteaseId];
    });
  } catch (err) {
    console.warn('[NeteaseWebCover]', err);
  }
}
async function fetchNeteaseWebSearchResults(q) {
  neteaseWebSearchError = '';
  var data;
  try {
    data = await neteaseWebFetchJson(STARWAVE_NETEASE_API_BASE + '/search?keywords=' + encodeURIComponent(q) + '&limit=10', 12000);
  } catch (err) {
    neteaseWebSearchError = publicSourceErrorText(err);
    console.warn('[NeteaseWebSearch]', err);
    return [];
  }
  var list = (data && data.result && Array.isArray(data.result.songs)) ? data.result.songs : [];
  if (data && data.code && data.code !== 200 && !list.length) {
    neteaseWebSearchError = '网易云搜索返回异常（code ' + data.code + '）';
    return [];
  }
  var songs = list.map(neteaseWebSongFromRecord).filter(function(song){ return song && song.name && song.id; });
  await fillNeteaseWebCovers(songs);
  return songs;
}
async function findNeteaseWebTrialPreview(song) {
  try {
    var q = [song && song.name, song && song.artist].filter(Boolean).join(' ').trim();
    if (!q) return '';
    var results = await fetchItunesPublicSearchResults(q);
    var target = simpleSearchNorm(song.name || '');
    for (var i = 0; i < results.length; i++) {
      var cand = simpleSearchNorm(results[i].name || '');
      if (target && (cand === target || cand.indexOf(target) >= 0 || target.indexOf(cand) >= 0) && results[i].publicAudioUrl) return results[i].publicAudioUrl;
    }
    return '';
  } catch (err) {
    return '';
  }
}
async function fetchNeteaseWebPlayback(song) {
  var id = song && (song.neteaseId || song.id);
  if (song && song.publicAudioUrl) {
    return { provider: 'netease-web', url: song.publicAudioUrl, level: 'standard', quality: '网易云', trial: !!song.trial, playable: true };
  }
  if (!id) return { provider: 'netease-web', url: '', playable: false, reason: 'url_unavailable', message: '网易云没有可用歌曲 ID' };
  var data;
  try {
    data = await neteaseWebFetchJson(STARWAVE_NETEASE_API_BASE + '/song/url/v1?id=' + encodeURIComponent(id) + '&level=standard' + (typeof neteaseWebAuthQuery === 'function' ? neteaseWebAuthQuery() : ''), 12000);
  } catch (err) {
    return { provider: 'netease-web', url: '', playable: false, reason: 'netease_web_failed', message: '网易云播放地址请求失败：' + publicSourceErrorText(err) };
  }
  var item = (data && Array.isArray(data.data)) ? data.data[0] : null;
  var url = (item && item.url) || '';
  if (url) {
    song.publicAudioUrl = url;
    return { provider: 'netease-web', url: url, level: 'standard', quality: '网易云', trial: false, playable: true };
  }
  var trialUrl = await findNeteaseWebTrialPreview(song);
  var result = { provider: 'netease-web', url: '', playable: false, reason: 'login_required', message: '该曲目需登录网易云账号才能播放（当前未登录）' };
  if (trialUrl) {
    song.neteaseTrialPreviewUrl = trialUrl;
    result.trialPreviewUrl = trialUrl;
  }
  return result;
}
async function fetchNeteaseWebLyric(song) {
  var id = song && (song.neteaseId || song.id);
  if (!id) return '';
  try {
    var data = await neteaseWebFetchJson(STARWAVE_NETEASE_API_BASE + '/lyric?id=' + encodeURIComponent(id), 10000);
    var text = (data && data.lrc && data.lrc.lyric) || '';
    return isNoLyricText(text) ? '' : text;
  } catch (err) {
    console.warn('[NeteaseWebLyric]', err);
    return '';
  }
}
function showNeteaseWebTrialOffer(song, idx, token) {
  var banner = document.getElementById('trial-banner');
  var textEl = document.getElementById('trial-text');
  var btn = document.getElementById('trial-login-btn');
  if (!banner || !textEl || !btn) return;
  textEl.textContent = '该曲目需登录网易云账号才能播放（当前未登录） · 有 30 秒试听片段';
  btn.style.display = '';
  btn.textContent = '播放 30 秒试听';
  btn.onclick = function(){
    banner.classList.remove('show');
    playNeteaseWebTrial(song, idx, token);
  };
  banner.classList.add('show');
}
function playNeteaseWebTrial(song, idx, token) {
  if (!song || !song.neteaseTrialPreviewUrl) return;
  if (typeof token === 'number' && token !== trackSwitchToken) return;
  song.publicAudioUrl = song.neteaseTrialPreviewUrl;
  song.trial = true;
  playQueueAt(idx, { allowTrialFallback: true, manual: true });
}
/* 登录态判断（登录模块加载后可用；未加载时按未登录处理）：
 * 登录后首页/电台/DJ/推荐改用歌单里的歌；未登录时用公共源（网易云免费曲 + iTunes 试听）。 */
function starwaveNetEaseLoggedIn() {
  try {
    if (typeof neteaseWebHasSession === 'function' && neteaseWebHasSession()) return true;
  } catch (e) {}
  try {
    if (typeof loginStatus !== 'undefined' && loginStatus && loginStatus.loggedIn && loginStatus.provider === 'netease') return true;
  } catch (e) {}
  return false;
}
/* 演示曲目已于 2026-11-10 按 Ma 的要求全部删除（曲目定义与 demo/ 音频文件均已移除，
 * 旧文件见 git 历史）。保留本函数作兼容壳：各处调用者（首页/电台/DJ/推荐/历史）
 * 仍可调用，恒返回 []，不展示任何演示曲目。 */
async function buildStarwaveDemoSongs() {
  return [];
}
