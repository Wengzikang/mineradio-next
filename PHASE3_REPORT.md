# StarWave（星澜音乐）Phase 3 完成报告

**日期：** 2026-11-09（CST）
**范围：** 仅 `~/workspace/mineradio-next/`；未碰 Folia、AURORA、CINEMA ONE、NEON MUSIC 及其他项目
**验证环境：** Playwright（Chromium 无头）+ 本地测试中继 127.0.0.1:18082 + Range 服务器 127.0.0.1:4174；本机出口代理 MITM TLS，Chromium 带 `--ignore-certificate-errors`
**最终验证：** `scripts/verify-phase3.py` 第 7 轮，exit 0，**console 错误 0、page 错误 0、失败请求 0**；`npm run build:web` 通过；`scripts/verify-phase1.py` / `scripts/verify-phase2.py` 回归已跑（见 §九）

---

## 一、逐项完成情况与实测证据

### 1. 真实音频播放链路 ✅（部分受上游逐曲限制，见 1c）

| 子项 | 结果 | 证据（第 7 轮，除注明外） |
|---|---|---|
| 演示曲目 | ✅ 播放 | 樱花 `paused=false, currentTime=3.05, duration=209.25`，`src=http://127.0.0.1:4174/demo/sakura.mp3`，队列 6 首 |
| 本地文件导入 | ✅ 播放 | `sw-local-test.mp3`（sakura 副本）`paused=false, currentTime=1.49`，blob URL，队列 9 首、`currentIdx=8` |
| 网易云免费曲 | ⚠️ 链路通，逐曲受限 | 见下：5 个 fee=0 候选全部返回空 URL（诚实报 login_required）；**288820 兜底探针可播**（`paused=false, ct=5.7, duration=416.9`，m701 源）；第 2/3 轮同一曲目 `ct=5.94/6.05` 播过 |
| iTunes 30s 试听 | ✅ 播放 | Patient Zero（Taylor Swift）`paused=false, currentTime=5.06, duration=30.01`，`audio-ssl.itunes.apple.com` 预览源；analyser 为 `synthetic`（预期，跨域无 CORS） |
| 私人电台队列 | ✅ | 13 首，`next` 后 `currentIdx 0→1`（樱花 → 千与千寻主题曲），`paused=false` |
| VIP 曲诚实失败 | ✅ | 练习（刘德华，fee=1）/ 富士山下（陈奕迅，fee=1）：`paused=true`，toast「该曲目需登录网易云账号才能播放（当前未登录）」，无假播 |

**1c 逐曲限制的直接证据（curl 直测上游 `api-enhanced`，不经中继）：**
- `288820` 结尾曲-友谊地久天长(Live)：返回真实 m701 URL，可播。
- `110740` 忘情水(Live)、`110191` 暗里着迷：返回 `url:null, code:404`，尽管搜索结果 `fee=0`。
- 结论：**搜索 `fee=0` 不等于可播**，`/song/url/v1` 对部分曲目逐曲返回空 URL（上游侧限制）。应用对此处理正确：有 URL 则播，无 URL 则明确提示，不静默、不假播。

### 2. 播放队列 ✅

实现：`web/public/starwave-phase3.js:562` `queueState()`、`572` `moveQueueItem()`、`583` `addToQueue()`、`593` `setPlayMode()`；队列面板 ↑/↓ 按钮接 `moveQueueItem`（`web/public/index.html` `renderQueuePanel` 内 `.qi-act`）。

| 操作 | 证据（第 7 轮） |
|---|---|
| 加歌 / 插队 | 队列 6→7（`added_idx=6`，插队 `added_next_idx=1`） |
| 移歌 | `moved=true`，[樱花, Clair de Lune, 茉莉花…] → [樱花, 茉莉花, Clair de Lune…]；越界 `move_out_of_range=false` |
| 删歌 | 7→6 |
| 循环模式 | `loop → shuffle → single → loop` 完整循环 |
| 上/下一首 | next：樱花→茉莉花；prev：回到樱花 |
| 队列面板渲染 | DOM 行数 6 = 队列长度 6 |
| 清空 | 长度 0，`currentIdx=-1` |

**断点续播（实测刷新）：** `starwave-phase3.js:633` `resumeState()`、`641` `restoreResume()`，localStorage 键 `starwave-resume-v1`（:46），每 5 秒 + 切歌 + `beforeunload` 保存。
- 保存时：樱花 `idx=0, time=33.81s, playing=true, queueLen=6, lastTrackLocal=false`
- 刷新后自动恢复：`resumeAt=38.00`（保存点 + 恢复延迟），`paused=false, currentTime=40.14`，队列 6 首完整恢复。
- 本地文件不可跨刷新恢复（blob URL 失效）：队列恢复但本地曲跳过并明确 toast「本地文件需重新导入」（第 2 轮验证 `lastTrackLocal: true`）。

### 3. 歌词同步 ✅（行级；逐词为降级说明）

实现：`starwave-phase3.js:668` `setLyricOffsetMs()`、`675` `nudgeLyricOffset(±500)`、`676` `lyricState()`；偏移持久化 `starwave-lyric-offset-ms-v1`（±3000ms 钳制）；`index.html:9475` `tickLyricsParticles` 使用 `audio.currentTime + window.__starwaveLyricOffsetSec`。

| 检查 | 证据（第 7 轮） |
|---|---|
| seek 20s | `currentIdx=1`「樱花 樱花」，`expectedIdx=1`，`match=true` |
| seek 40s | `currentIdx=2`「野山も里も」，`expectedIdx=2`，`match=true` |
| 偏移 +500ms | 第 2/4 轮：t=33.0 时期望行 1→2，live `match=true` |
| 逐词高亮 | `hasWords=false`；演示 LRC 无词级时间戳，**仅行级高亮**（YRC 源才有词时间戳）；行内逐词进度按行内匀速估算，报告如实说明 |

### 4. 频谱与节拍 ✅（同源真实频谱；跨域为合成，已标注）

实现：`starwave-phase3.js:174` `p3Attach()`（MediaElementSource → 3 段 EQ → analyser → gain → destination，另接 beatAnalyser）、`385` `spectrumSample()`、`409` `beatInfo()`（含 `gaps` 数组）、`426` `sampleBeat()`。

| 检查 | 证据（第 7 轮，90 BPM 敲击测试文件 `sw-kick90.wav`，55Hz 正弦突发） |
|---|---|
| 真实频谱 | `analyser_mode=native`，`max=210–255`，`low=0.54–0.68`，随音频变化，非零 |
| BPM | 实测 BPM 55，`onsets=15`，`gaps=[0.96–1.3]` 紧密成簇，`max_kick=1.0` |
| 音频时钟归一化 | `speed_ratio=0.608`，**归一化 BPM = 90.5 ≈ 真实 90**（第 4 轮 90.6，第 5 轮 89.3，第 6 轮 85.6） |
| 稀疏曲目 | 樱花等慢速稀疏曲 BPM 诚实为 0（onsets < 5），kick 能量仍输出 |

**关键发现：** 无头 VM 的音频时钟以约 0.56–0.65× 墙钟速度运行，导致墙钟 BPM 被等比拉伸；归一化后 85.6–90.6 ≈ 90，证明估计算法正确。真实设备 60fps 下的 BPM 尚未验证（无真机）。

### 5. 音效 ✅（真实 Web Audio 三段 EQ，analyser 数据验证）

实现：`starwave-phase3.js:134` `setBand()`、`141` `resetEq()`、`148` `eqState()`；三段 Biquad（lowshelf 200Hz / peaking 1kHz Q0.9 / highshelf 4kHz），增益 ±12dB，持久化 `starwave-eq-v1`；`index.html:19454` `initAudio` 内建 EQ 节点并暴露 `window.starwaveEqNodes`，analyser 位于 EQ 之后（采样即所听频谱）。

| 检查 | 证据（第 7 轮） |
|---|---|
| 音量 | 目标 0.5 → `audioVolume=0.5` |
| EQ 低频 +12dB | 低频段均值 0.805 |
| EQ 低频 −12dB | 低频段均值 0.520 |
| 比值 | **1.55**（第 2 轮 1.49）——增益可听/可测，真实生效 |

**限制：** EQ 仅对同源（演示/本地）音频保证生效；跨域（网易云/iTunes）无 CORS，MediaElementSource 会静默输出，故保持合成频谱且 EQ 不接入（`beatInfo()`/`spectrumSample()` 标注 `synthetic`）。

### 6. 收藏（本地优先）✅——Phase 2 缺口已修复

实现：`starwave-phase3.js:44` `starwave-local-favorites-v1`，`705` `isFavorite()`、`710` `toggleFavorite()`、`725` `removeFavorite()`、`732` `listFavorites()`；包裹 `toggleLikeSong`（:746，非云端曲走本地收藏）和 `openCollectModal`（非云端曲打开曲库弹窗「收藏」页，不再拒收）；曲库弹窗 `1208` `openLibraryModal()`，右上角 ★ 按钮 `#starwave-phase3-btn`，页签：收藏 / 历史 / 本地歌单 / 收藏到歌单 / 音效·歌词。

| 检查 | 证据（第 7 轮） |
|---|---|
| 演示曲收藏 | 樱花、茉莉花收藏成功，`count=1→2` |
| 网易云免费曲收藏 | 忘情水(Live) 收藏成功，`count=3`（第 6 轮因刷新后单关键词查不到免费曲曾为 2；已改为多关键词轮询，第 7 轮为 3） |
| 列表 | `list_len=3`：[忘情水(Live)\|netease-web, 茉莉花\|demo, 樱花\|demo] |
| 收藏弹窗 | demo 曲打开 `modal_shown=true, body_has_collect=true`（不再出现「须登录后收藏云端曲」） |
| 点赞入口 | `toggleLike` 3→4，toast「已收藏到本地：Greensleeves」 |
| 弹窗行数 | 4 |
| 取消收藏 | `favorited=false, count=3` |

数据只存本机 localStorage；任何情况下均不以「须登录」挡本地收藏。

### 7. 历史记录 ✅

实现：`starwave-phase3.js:767` `historyState()`、`783` `clearHistory()`、`796` `playHistoryEntry()`；读取基线 `listenStatsState`（键 `starwave-listen-stats-v1`，上限 180 条）；计数规则沿用基线：**听满 45 秒 / 进度 ≥50% / 播完，记 1 次**。

| 检查 | 证据（第 7 轮） |
|---|---|
| 记录 | 樱花 `listenMs=5295, totalPlays=1, topSong=樱花`（播至 55% 后切歌） |
| 幽灵条目 | `phantom_moli=[]`，`names=['樱花']`——Phase 2 遗留的 0ms 幽灵记录已修复（见 §二第 4 条） |
| 视图 | 历史弹窗行数 1 |
| 清空 | `entries=[], totalPlays=0, totalSongs=0` |

只存本机。

### 8. 歌单 ✅（本地歌单；网易云公开歌单导入诚实提示）

实现：`starwave-phase3.js:45` `starwave-local-playlists-v1`，`853` `createLocalPlaylist()`、`869` `renameLocalPlaylist()`、`883` `deleteLocalPlaylist()`、`901` `addToLocalPlaylist()`、`920` `removeFromLocalPlaylist()`、`941` `openLocalPlaylist()`；包裹 `refreshUserPlaylists`（重建后合并本地歌单）、`openPlaylistPanelDetail`（provider `local` / id `local:*` 走本地详情）、`loadPlaylistIntoQueueById`；`index.html:15491` `playlistProviderKey` 修正（`local` 不再被误映射为 `netease`），`renderUserPlaylistsList` 增加「本地歌单」分组。

| 检查 | 证据（第 7 轮） |
|---|---|
| 创建/加歌 | `adds=[true, true, true]`（樱花、茉莉花、忘情水），重复加歌被拒 `dup_rejected=true` |
| 重命名 | `Phase3测试歌单 → Phase3改名歌单`，`renamed=true` |
| 详情页 | **3 首，DOM 行数 3**，面板含歌单名——Phase 2 遗留「详情页 tracks: [] / 未找到歌单」已解决（本地歌单） |
| 播放歌单 | 队列 3 首，`paused=false, currentTime=2.53`，首曲樱花 |
| 删歌/删单 | 删歌后剩 2 首；删单 `list_len=0, in_user_playlists=false` |
| 网易云公开歌单导入（3778678） | 明确提示：`notice_shown=true`，标题「需要更新 StarWave Connector」，正文「网易云 / QQ 外链歌单导入需要 0.5.0 或更新版本的浏览器扩展。」；`has_3778678=false`，**无假数据** |

### 9. 回归 ✅

- `npm run build:web`：通过。`web/dist/index.html` 1,481,511 B，`web/dist/starwave-phase3.js` 67,543 B。
- `scripts/verify-phase3.py`（801 行，覆盖 1–8 项，实测数字）：第 7 轮 exit 0，0/0/0 错误。
- `scripts/verify-phase1.py`：exit 0，console 0 / page 0，失败请求 1（Audius 封面图被 ORB 拦截，与音频无关，Phase 3 之前已存在）。
- `scripts/verify-phase2.py`：exit 0，page 错误 0；实质检查通过（demo 播放、radio 14 首、Spotify drain TTL 600000、Cookie 面板隐藏、secret 扫描仅命中未动过的 `starwave-qishui.js` 内 `spade_a` 字串）。7 个 console 错误为**测试夹具产物**：api-enhanced 的 CORS 头回显了上一个 origin（4174），导致 4173 origin 的搜索被挡；应用代码在两个 origin 上完全相同，Phase 3 在 4174 上为 0 错误，生产 origin（GitHub Pages）不受此影响。
- 约束回归（第 7 轮 §9）：Spotify TTL 600000；Apple `pending_auth`（「需 Apple Developer 会员 + 服务端签发 Token」）；粘贴 Cookie 登录仍禁用，toast「已停用：为保护账号安全，StarWave 不再支持粘贴 Cookie 登录……」；汽水模块未动。

---

## 二、Phase 3 修复的 Bug 清单

1. **p3 与 initAudio 双重绑定（本地导入播不出，第 1 轮）**——同一 `<audio>` 被两个 AudioContext `createMediaElementSource`，后绑定的静默。修：`__sw3P3Attached` 标志 + initAudio 可重入（`index.html:19473` 按元素变化解绑旧 source 重绑）。
2. **initAudio 不可重入（第 2 个起的本地文件丢音量/EQ/频谱）**——基线 `handleFiles` 每次 `new Audio()`，旧图绑在 stale 元素上。修：`index.html:20567` 附近 `attemptAudioPlay` 改为无条件调用 `initAudio()`（原 `!audioReady` 守卫跳过重绑）。
3. **歌词 seek 后重播（第 1 轮）**——`python -m http.server` 不支持 Range，Chromium seek 长 mp3 从头重播。修：新增测试专用 `scripts/range-http-server.py`（71 行，206 + Content-Range），**不进构建产物**。
4. **历史 0ms 幽灵记录（第 2 轮：茉莉花 listenMs=0）**——tick 在 `currentIdx` 已切新歌、音频元素仍播旧歌时运行，新歌会话带着旧歌 55% 进度出生，立即被记 1 次。修：`index.html:15769` `updateListenStatsTick` 在 key 不匹配时先 `finalizeListenSession` 再返回；`15809` `finalizeListenSession` 先分离旧会话、按其自身计数器内联结算（第 3 轮起 `phantom_moli=[]`）。
5. **iTunes 试听被静默丢弃（第 2/3 轮）**——iTunes 曲自带 `trial: true`，播放时先去网易云找完整版，失败后旧代码无条件返回 true，可播的 30s 预览被丢掉。修：`index.html:20165` `tryAutoPlaybackFallback`（递归后若用户未切歌且音频未在播，恢复原曲并提示「暂用试听片段」）；`20423` 试听分支在 fallback 失败后重新同步 token（递归调用会 bump token，旧检查会误判）。第 4 轮起 iTunes 可播（ct 4.89–5.06，30.01s）。
6. **BPM 长期为 0 / 中位数被污染（第 1–3 轮）**——(a) 跨曲 onset 残留污染中位数：切歌时重置 onset 历史，gap 过滤到 [0.25, 2.0]s；(b) kick 频段 RMS 被近空 bin 稀释：改用 `bandPeak()` 取最大 bin；(c) 乘性上升门限在峰值饱和 1.0 时失效：改用**时域 RMS 阈值穿越**（`tdRms > 0.03 && prevTdRms <= 0.03`，0.24s 不应期）；(d) kick 改从 beatAnalyser（smoothing 0.10）读取而非主 analyser（0.58）。探针证实：频域 kick 频段在静音时仍有 ~0.55 底噪（bin2 不低于 142），同时域 RMS 脉冲干净（间隙 0.005–0.01，突发 0.19–0.41）。第 4 轮起 BPM 50–55、归一化 85.6–90.6。
7. **收藏拒收演示/本地曲（Phase 2 缺口）**——`isCloudSong` 对 demo/local/netease-web/itunes 返回 false，`openCollectModal`/`toggleLikeSong` 直接拒收。修：非云端曲走本地收藏（§一第 6 项）。
8. **本地歌单详情打不开（Phase 2 遗留 tracks: []）**——`playlistProviderKey` 把未知 provider 一律映射为 `netease`，`local` 被误归类；详情加载无本地分支。修：`index.html:15491` 映射修正 + Phase 3 本地详情包裹（§一第 8 项）。
9. **本地文件不进队列**——基线 `handleFiles` 只直播不进队列（`currentIdx=-1`），`playQueueAt` 对本地曲会走不存在的 `/api/song/url`。修：`starwave-phase3.js:445` `playLocalQueueSong()` + `533` `handleFiles` 包裹（导入即入队并置 `currentIdx`）。
10. **无歌词偏移、无 EQ**——新增（§一第 3、5 项）。

---

## 三、新增 / 修改的文件

| 文件 | 说明 |
|---|---|
| `web/public/starwave-phase3.js`（新建，1338 行） | Phase 3 全部功能：真实 analyser 图、3 段 EQ、本地文件进队列、队列操作、断点续播、歌词偏移、本地收藏、历史、本地歌单、曲库弹窗；`window.starwavePhase3` v0.3.0-phase3 |
| `web/public/index.html`（手术式修改，约 10 处） | 引入 phase3 脚本；歌词偏移注入（:9475）；initAudio 内建 EQ + 可重入（:19454、:19473）；`attemptAudioPlay` 重绑（~:20567）；`playlistProviderKey` 本地修正（:15491）及本地分组/标签；队列面板 ↑/↓（`renderQueuePanel`）；历史幽灵记录修复（:15769、:15809）；iTunes 试听 fallback 修复（:20165、:20423） |
| `scripts/verify-phase3.py`（新建，801 行） | 覆盖 1–8 项的 Playwright 验证，输出实测数字与 `/tmp/sw-phase3-verify-report.json`；含中继健康检查与自动重启、测试音频自动生成（/tmp，VM 重启后重建） |
| `scripts/range-http-server.py`（新建，71 行，仅测试用） | 支持 Range 的静态服务器（4174），不进构建产物 |
| `scripts/probe-*.py`（诊断用） | `probe-phase3.py`、`probe-itunes.py`、`probe-bpm-import.py`、`probe-kick-envelope.py`、`probe-kick-direct.py`、`probe-kick-timedomain.py`、`probe-kick-hires.py` |
| `web/dist/`（构建产物） | `npm run build:web` 重新生成 |

**未动：** `web/public/starwave-qishui.js`（sha256 `6d1732044af9ddfed7a9b26b104c7e42a5567431fb08eb3c1bf5fe3f5d748547`，未接线）；Spotify/Apple 接线；品牌/PWA 缓存名；粘贴 Cookie 登录（保持禁用）。

---

## 四、未完成 / 降级项

1. **网易云免费曲播放逐曲受限（非应用 Bug，上游行为）**——第 7 轮 5 个 fee=0 候选（忘情水/暗里着迷/17岁/冰雨/开心的马骝，均为刘德华 Live）全部返回空 URL；curl 直测证实 110740/110191 为 `url:null, code:404`，而 288820 有真实 URL 且可播。应用处理正确（诚实提示、无假播）。验证脚本已加入 288820 作为兜底 fixture（直接按 id 构造 song 对象播放，探针已证实可播；脚本切片 `candidates[:5]` 曾切掉第 6 个候选的 bug 已修为 `[:6]`）。
2. **BPM 需 ≥5 个 kick onset**——慢速稀疏曲（如樱花）BPM 诚实为 0，kick 能量仍输出；无头归一化 BPM 85.6–90.6 ≈ 90，真实设备 60fps 下的 BPM 未验证（无真机）。
3. **跨域音频频谱/EQ 降级**——网易云/iTunes 无 CORS，真实 analyser 会静默输出，故保持合成频谱（标注 `synthetic`），EQ 仅对演示/本地保证生效。
4. **逐词高亮降级为行级**——演示 LRC 无词级时间戳；仅 YRC 源有词时间戳。
5. **本地文件不能跨刷新续播**——blob URL 失效，队列恢复、本地曲跳过并明确提示重导入。
6. **网易云公开歌单导入**——需 StarWave Connector 浏览器扩展（静态 Web 未安装），已明确提示原因，无假数据。

---

## 五、已知限制与外观瑕疵

- 无头 Chromium fps 1–5（软件渲染），视觉流畅度与逐帧采样率不代表真机；VM 音频时钟约 0.56–0.65× 墙钟速度（BPM 需归一化解读）。
- iTunes 试听 fallback 失败后，toast 会残留「该曲目需登录网易云账号才能播放」≤2.6s，同时预览已在播放（#source-fallback-notice 正确显示「暂用试听片段」）。外观问题，未修。
- 本地歌单详情内部 key 为 `local:local:<id>`（双前缀），显示不受影响。
- `snapshotToSong` 有一段空的 demo 分支死代码（无害）。
- 历史计数沿用基线规则（45 秒 / ≥50% / 播完）。
- 中继本身不稳定：验证期间中继进程曾死亡一次（探针 fetch 失败），`verify-phase3.py` 的 `ensure_relay()` 会健康检查并自动重启；本轮结束后中继（PID 12258）、Range 服务器（PID 1750，4174）、4173 静态服务器仍在运行，供复验使用，不用时可 kill。
- `verify-phase2.py` 在 4173 上复跑时出现 7 个 CORS console 错误，系 api-enhanced 的 CORS 头回显了 4174 origin 的夹具产物（见 §一第 9 项），非应用回归。

---

## 六、验证报告位置

- Phase 3 最终报告 JSON：`/tmp/sw-phase3-verify-report.json`（第 7 轮）
- Phase 1 报告：`/tmp/sw-phase1-verify-report.json`
- Phase 2 报告：`/tmp/sw-phase2-verify-report.json`
- 本报告：`~/workspace/mineradio-next/PHASE3_REPORT.md`
