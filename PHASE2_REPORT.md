# StarWave（星澜音乐）Phase 2 交付报告

> 工作目录：`~/workspace/mineradio-next/`（MrChenyh/Mineradio-Web v0.1.0 单文件基线）
> 日期：2026-11-09（CST）。报告给父代理，不发给用户；未部署、未 gh 操作、未登录任何音乐平台。
> 验证方法：本地 http 服务（127.0.0.1:4173）+ Playwright（`~/workspace/.venv-playwright/bin/python`），经测试中继 `scripts/verify-relay-proxy.py`（127.0.0.1:18082，仅验证时运行，不进构建产物）。

---

## 一、任务完成情况（逐项）

### A. Phase 1 验收遗留 ✅ 全部完成

| # | 内容 | 位置 |
|---|------|------|
| A1 | 搜索结果 meta 标注「网易云（非官方社区服务，仅免费曲）· 未登录」 | `web/public/index.html:18553`、`18566`（`searchResultMetaText` 与 `searchResultMetaHtml` 两处）；设置/关于页音源状态行同样标注 |
| A2 | 设置/关于页：源码链接 https://github.com/Wengzikang/starwave-music（仓库稍后创建；链接先行公示）+ 注明「基于 MrChenyh/Mineradio-Web v0.1.0 修改，GPL-3.0，与 Mineradio 官方无关」 | `web/public/starwave-phase2.js` 约 60–110 行（`aboutModalHtml` / `starwaveOpenAbout`）；入口为 `#top-right` 齿轮按钮 `#starwave-about-btn` |
| A3 | VIP 徽标：`fee===1` → `fee>0` 都标 VIP | `web/public/index.html:19333`（一行改动） |

### B. 界面审计与补全 ✅ 完成（发现并修了一个真实的栈溢出 Bug，见 §三）

审计脚本 `scripts/audit-phase2.py`：8 个视图枚举全部按钮，核查 onclick 处理函数存在性，对可见按钮逐个强制点按，记录页面错误与 toast。结果（运行 5，最终 0 错）：

| 视图 | 按钮总数 | 实点 | 死按钮（处理函数缺失） |
|---|---|---|---|
| 首页 | 20 | 19 | 0 |
| 搜索 | 75 | 16 | 0 |
| 歌词舞台 | 34 | 1 | 0 |
| 3D 歌单架 | 45 | 10 | 0 |
| 歌单详情 | 45 | 0 | 0 |
| DIY 控制台 | 144 | 15 | 0 |
| 听歌画像 | 1 | 0 | 0 |
| 设置 | 11 | 1 | 0 |

- **死按钮：0。** 所有被枚举到的按钮都有真实处理函数；点按后无未捕获错误。
- 点按数少于总数的原因：大量按钮在当时视图状态下不可见/被覆盖（例如首页隐藏时、DIY 面板折叠时），审计只点可见的；未被点击的按钮均已通过「处理函数存在性」核查（`fn_exists`），不属于假入口。
- 审计中发现的 2 个非死按钮但值得说明的现象（均为基线行为，非 Phase 2 引入）：
  1. 首页卡片在播放时会被 `#canvas-container`/`.visual-guide-scrim` 遮挡指针——因为播放时首页隐藏、视觉引导层覆盖页面直至关闭；不是缺陷。
  2. 开发中锁定的特效开关（`wallpaperMode`、桌面歌词系列）点按后诚实提示「开发中，暂不可用」，不是假按钮。
- 听歌画像在 0 播放时显示 toast「播放几首歌后会生成听歌画像」，`summary={recent:null, topSong:null, topArtist:null, totalPlays:0}`——空态诚实，无伪造数据。

### C. Spotify（官方 PKCE + Web Playback SDK，复用已有应用 "Music"）✅ 接线通过（未完成真人登录，见 §四）

实现位置：`web/public/starwave-phase2.js` 约 230–560 行（`window.starwaveSpotify`）。

- Client ID `35e5a591884f42d398ab298ab79f16cb`（公开 ID）；Redirect URI `https://wengzikang.github.io/starwave-music/`；Scope `streaming user-read-email user-read-private user-modify-playback-state`；无 Client Secret（全仓 grep 无 `client_secret`）。
- **Folia 三条 PKCE 血泪经验全部落实**（本任务补充要求）：
  1. **verifier 存 localStorage**，不存 sessionStorage——`storeSet(SPOTIFY_KEYS.verifier, …)`（行 269 附近有注释说明 iOS Safari 新标签页看不到原标签页 sessionStorage）；实测 `sessionStorage` 中无 verifier（`false`），`localStorage` 中有（`true`）。代码中 `sessionStorage` 仅出现在该注释里，无实际使用。
  2. **drain 先换码、后清 PKCE**——`drainSpotifyRedirect()`（行 436）：换码成功后先 `saveSpotifyToken(data)` 再 `storeDel(verifier/state/startedAt)`；换码失败也在 catch（交换已落定）后才清。交换进行中无任何代码会清 PKCE。URL 的 `?code=` 用 `history.replaceState` 在换码前清除（防刷新重试，与 PKCE 清除无关）。
  3. **登录 TTL 10 分钟**——`SPOTIFY_LOGIN_TTL_MS = 10 * 60 * 1000`（行 241）；登录发起时存 `starwave.spotify.auth_started_at`；drain 超时直接作废并提示「Spotify 登录已过期（授权码仅 10 分钟有效），请重新登录」；对外暴露 `starwaveSpotify.loginTtlMs` 与 `pendingLogin()`（含 `remainingMs`）。
- 授权 URL 实测（直接调用 `buildAuthUrl()`，见 §二说明）：`https://accounts.spotify.com/authorize?response_type=code&client_id=35e5a591884f42d398ab298ab79f16cb&scope=streaming+user-read-email+user-read-private+user-modify-playback-state&redirect_uri=https%3A%2F%2Fwengzikang.github.io%2Fstarwave-music%2F&state=<24 字符>&code_challenge_method=S256&code_challenge=<43 字符>`——参数齐全。
- 登录后：用用户 token 调 Web API 搜索（未登录时搜索结果只做元数据展示，显示「待授权」）；Web Playback SDK 懒加载，`playQueueAt`/`nextTrack`/`prevTrack` 已包裹，Spotify 曲目走 SDK 而非 `<audio>`；免费账号只给提示，不伪造播放；不依赖 `preview_url`。
- 登录按钮已注入登录弹窗 `.btn-row`（`#starwave-spotify-login-btn`）。

### D. Apple Music（仅框架）✅ 完成

实现位置：`web/public/starwave-phase2.js` 约 640–700 行（`window.starwaveAppleMusic`）。

- MusicKit JS v3 懒加载（`js-cdn.music.apple.com/musickit/v3/musickit.js`）；`searchCatalog(q)` 恒返回 `{status:'pending_auth', results:[], message:'Apple Music 待授权：需 Apple Developer 会员 + 服务端签发 Token'}`；界面（设置/关于页）明确显示「待授权（需 Apple Developer 会员 + 服务端签发 Token，待 Ma 解锁 Apple ID 后办理）」。
- **无任何 token/密钥，无任何从 music.apple.com 提取 developer token 的逻辑。**
- 实测：`searchCatalog('周杰伦')` → `pending_auth`，结果 0 条；`load()` 返回 `true`，`window.MusicKit` 已加载，状态文本正确。注：首轮验证中 `musicKitLoaded` 曾为 false，原因是懒加载的 15 秒超时 Promise 在步骤 (j) 时尚未 resolve；后续单独 await `load()` 确认加载成功——框架状态与 `searchCatalog` 不依赖它。

### E. 私人电台（新建，真实可用）✅ 完成

实现位置：`web/public/starwave-phase2.js` 约 700–880 行（`window.starwaveRadio`）。

- 心情：清晨 / 午后 / 夜晚 / 专注 / 运动 / 放松，按小时默认（6–10 清晨、11–16 午后、17–22 夜晚、23–5 放松）；`buildRadioQueue` 交错拼装演示曲目 + 网易云免费曲（`fee===0`，上限 8）+ iTunes 试听（上限 6），去重后上限 20 首，设为真实 `playQueue` 并 `playQueueAt(0, {context:{radio:'starwave'}})`，上一首/下一首正常工作。
- 浮动芯片 `#starwave-radio-chip` 显示心情 + 当前曲目 + 来源（点击 = 下一首）；首页卡片 `#starwave-radio-card`（「私人电台」）；心情按钮与开始/停止在设置/关于页。
- 实测（心情「放松」）：队列 13 首，来源分布 demo 6 + netease-web 1 + itunes 6；首曲「樱花」（演示，正在播放），下一首切为「千与千寻 主题曲《いつも何度でも》」（网易云免费曲）；芯片显示「私人电台 · 放松 · 樱花 · 演示」，`playing: true`。
- 修复过两个问题：① `updateRadioChip` 原先在芯片不存在时直接 return，芯片永不创建——已改为调用 `radioChip()` 确保创建；② iTunes 搜索中文心情词在 `country=CN` 下返回 0 条（实测「轻音乐」「钢琴」「民谣」「夜曲」均为 0），改为每心情配英文 iTunes 查询词（`relaxing piano`、`piano focus` 等，US 区实测各返回 8 条），此后放松队列含 6 首 iTunes 试听。

### F. 移动端 P0 ✅ 完成

实现位置：`web/public/starwave-phase2.js` 约 780–910 行（注入 CSS + 触摸 + Media Session + 性能总督）。

- `html,body` 高 `100dvh`（带 `100vh` 回退）；`#bottom-bar` 下 padding 用 `env(safe-area-inset-bottom)`；`#empty-home` 底部计算含安全区；`#top-right` 顶部安全区 padding；小屏搜索预览顶部含安全区。
- 触摸左右滑切歌：横向 >70px、纵向 <60px、<800ms，排除输入框/面板/弹窗/搜索结果/底部栏。
- Media Session API：元数据标题/艺人/专辑/封面 + previoustrack/nexttrack/play/pause 处理，在 `playQueueAt` 包裹与 SDK 状态变化时更新。
- 性能总督 `window.starwavePerfGovernor`：每 2 秒读 `window.__starwavePerf.fps`，连续 3 次 <25fps 自动降一档（ultra→high→balanced→eco），永不自动升级；设置页可手动选档。
- 实测（390×844）：`scrollW=390=innerW`，无横向溢出；`dvh=844px`；滑动后曲目「樱花」→「茉莉花」，`swipe_changed_track: true`；Media Session `title: 茉莉花 / artist: 中国民歌 / playbackState: playing`；总督手动设 eco 后 `modeAfter: auto`（注：手动选档后 `setMode` 内部仍保持 auto？——实测 `afterEco: eco`，档位已生效；`mode` 字段显示 auto 是因为手动选择后下一次自动采样会继续按 fps 调整，见 §五）。

### G. 小步拆模块 ✅ 完成（step 1）

- Phase 1 的网易云模块 + `STARWAVE_DEMO_SONGS`（原 `index.html` 约 2790–2971 行）已移出为 `web/public/starwave-netease.js`（185 行，GPL 头注释），`index.html:2776` 只留 `<script src="starwave-netease.js">`；`node --check` 通过。
- 新文件 `web/public/starwave-phase2.js`（914 行），`index.html:29176` 引用。均为加法式改动：Phase 2 文件用 try/catch 包裹已有全局，功能失败不影响页面加载。
- 回归：拆分后 `scripts/verify-phase1.py` 退出 0、0 页面错误；最终全量回归（见 §二）同样 0 错。
- `npm run build:web` 已跑，`web/dist/` 包含 `starwave-netease.js` 与 `starwave-phase2.js`（构建脚本 `scripts/build-web.js`）。
- **v2.2.0 模块化基线未动**，只按任务要求把收益/成本写进报告（见 §六）。

### H. 约束遵守 ✅

- QQ/酷狗/酷我/汽水：不接播放，仅元数据展示 + 跳转官方；未接任何社区逆向服务。
- 未恢复扩展、未碰桌面代码、未产生费用、未改品牌/PWA 缓存名。
- **⚠️ 一处行为变更需父代理知晓（可回滚）：粘贴 Cookie 登录已禁用。** `submitCookieLogin`/`toggleQQCookiePanel` 被包裹为提示「粘贴 Cookie 登录已禁用（账号安全原因，Phase 0.5 排-11）」，且 `#qq-cookie-panel{display:none!important}`。这是按 Phase 0.5 排除项做的，但它改变了 Phase 1 的既有行为——如需恢复，请告诉我。

---

## 二、实测证据汇总（数字）

验证脚本：`scripts/verify-phase2.py`（主验证）、`scripts/verify-phase2-followup.py` / `-followup2.py` / `-followup3.py`（跟进：授权 URL 直测、电台/芯片、歌单详情、MusicKit 加载）、`scripts/audit-phase2.py`（界面审计）、`scripts/regression-listen-recursion.py`（栈溢出回归）。证据文件：`/tmp/sw-phase2-verify-report.json`、`/tmp/sw-phase2-followup*.json`、`/tmp/sw-phase2-audit.json`、`/tmp/sw-audit-stacks.json`、截图 `/tmp/sw-v2-*.png`。

| 检查项 | 结果 |
|---|---|
| 页面加载 | **0 页面错误**（最终回归 `verify-phase1.py`：0 console 错误、0 页面错误、0 失败请求） |
| 8 视图逐个打开 | 首页/搜索/歌词舞台/3D 歌单架/歌单详情/DIY/画像/设置均可打开（歌单详情见 §四限制）；搜索「周杰伦」返回 14 条 |
| 演示曲目播放 | 「樱花」播放中（`paused: false`，`duration: 209.25s`） |
| 网易云搜索 + 免费曲播放 | 搜索可用；meta 标注正确（`netease_label_ok: true`）；电台中免费曲「千与千寻 主题曲」可切入播放 |
| Spotify 授权 URL | 参数齐全（见 §一 C：client_id / redirect_uri / scope / S256 / code_challenge 43 字符 / state 24 字符）；verifier 在 localStorage，sessionStorage 无 |
| Spotify drain（假 code） | toast「Spotify 登录换码失败：Failed to fetch（Redirect URI 须已在 Dashboard 登记）」，`logged_in: false`，URL 已清 `?code=` |
| Spotify drain（TTL 过期） | 人为把 `auth_started_at` 置为 11 分钟前 → toast「Spotify 登录已过期（授权码仅 10 分钟有效），请重新登录」，verifier 已清，`ttl_ms: 600000`，`pendingLogin().pending: false` |
| 私人电台 | 13 首队列（demo 6 + 网易云免费 1 + iTunes 6），可播可切歌，芯片可见 |
| 移动端 390×844 | 无横向溢出；滑动切歌生效；Media Session 已设置（标题/艺人/播放状态） |
| 性能总督 | 手动设 eco 生效；headless 下 fps 1–5（软件渲染，非真实设备），自动降至 eco |
| Apple Music | `searchCatalog` → `pending_auth`；`load()` → `true`，MusicKit 已加载 |
| 密钥扫描 | 0 命中（`client_secret`、`github_pat_`、`spade_a`、酷狗盐、KuWo 密钥、解密器、Apple developer token 均无） |
| 界面审计（运行 5） | **0 页面错误、0 console 错误**，8 视图，死按钮 0 |

**关于 Spotify 授权弹窗的说明：** `verify-phase2.py` 的 (e) 步用 `expect_popup` 捕获的弹窗 URL 是 `chromewebdata`（本 VM 的出口中继连不上 `accounts.spotify.com`，Chromium 显示错误页）。因此授权 URL 参数改由直接调用 `buildAuthUrl()` 验证（followup 脚本，参数全部正确，见上表）。登录按钮本身确实调用了 `window.open`（popup 事件已触发、verifier 已写入 localStorage）。真机/真实网络下弹窗应正常打开 Spotify 授权页——但这仍需 Ma 的真机验证。

**关于一次失败请求的说明：** 主验证结束时有 1 条 console 错误 `Failed to load resource: net::ERR_EMPTY_RESPONSE` 与 1 条失败请求 `https://accounts.spotify.com/api/token`——即假 code 换码那次：中继层面的空响应，应用层已正确处理为 toast、无崩溃、0 页面错误。另 2 条失败请求为 Audius 封面被 ORB 拦截（Phase 1 已存在的与验证无关的问题）。

---

## 三、审计中发现并修复的 Bug：听歌统计无限递归（栈溢出）

- 现象：审计运行 1–4 中 `Maximum call stack size exceeded` 页面错误数在 26 / 215 / 213 / 38 之间波动，与点按无关（刻意放慢点按、150 秒空闲播放、逐个点 16 个特效开关 + 23 个分段按钮、开关弹窗均 0 错误）。
- 根因（**基线既有问题，非 Phase 2 引入**）：`index.html` 约 15745–15798 行听歌统计代码互递归——`beginListenSession`（key 变化 → 调 `finalizeListenSession`）→ `finalizeListenSession`（会话仍在时调 `updateListenStatsTick(true)`）→ `updateListenStatsTick`（当前曲 key 已变 → 调 `beginListenSession`）→ 无限循环。触发条件：快速切歌时旧音频仍在播、而 `currentCoverSong()` 已指向新曲。正常慢速使用不触发，所以 Phase 1 验证（0 错误）没发现。
- 修复：`index.html:15778` 起在 `updateListenStatsTick` 加重入守卫 `var listenStatsTicking = false;`——已在 tick 时直接返回，try/finally 复位。语义保留：内层 finalize 完成，外层 `beginListenSession` 再建新会话。
- 回归：`scripts/regression-listen-recursion.py`——6 次快速点演示曲 + 12 次快速上一首/下一首，0 错误，仍在播放（当前曲「Amazing Grace」）；审计运行 5 全量 8 视图 0 页面错误、0 console 错误。

---

## 四、未完成 / 降级项

1. **Spotify 真人登录未完成（按任务设计如此）。** 需 Ma 在 Spotify 应用 Dashboard 把 `https://wengzikang.github.io/starwave-music/` 加为 Redirect URI，否则登录报 `redirect_uri` 不匹配；完整播放需 Ma 的 Premium 账号登录后真机验证。当前只验证到授权 URL 参数齐全与 drain 失败/过期路径。
2. **Apple Music 待 Ma 的事项：** 解锁 Apple ID（`elio858@qq.com` 目前锁定）→ 办理 Apple Developer 会员（$99/年）→ 服务端签发 MusicKit Token 的后端端点 → 域名白名单 → 用户订阅（否则仅 30 秒预览）。框架已搭好，真实播放不在本 Phase 范围。
3. **歌单详情视图：Web 未登录态下无真实数据可开。** 已查明两条基线限制：① `openCollectModal` 对演示/本地曲拒收（toast「本地文件暂不支持收藏到网易云歌单」），新建歌单须登录后收藏云端曲；② 粘贴公开网易云歌单链接导入（`runPlaylistImportFromSearch`，歌单 id 3778678）后 `userPlaylists` 仍为空、面板显示「未找到歌单」。直接调用 `openPlaylistPanelDetail('netease-web', '3778678', '测试歌单')` 可打开视图（`key: netease:3778678`，`playlist` 对象已建），但 `tracks: []`、面板显示「未找到歌单」，0 页面错误。结论：详情视图本身可打开、无崩溃，但 Web 未登录态拉不到曲目——基线限制，非 Phase 2 引入；需登录/连接器后才能用真实歌单验证。
4. **歌词舞台 DOM 断言：** `#stage-lyrics` 在检查时 0 子节点、`display:none`，无独立 `#lyrics-panel` DOM——但歌词本身已加载（`lyricLines: 14`），3D 舞台容器存在。这是基线渲染方式（歌词走 3D 场景/画布），不是 Phase 2 问题。
5. **电台曲源偏瘦（诚实说明）：** 「放松」心情 13 首中网易云免费曲仅 1 首——因为「轻音乐」搜索前 10 首里仅 1 首 `fee=0`（其余 `fee=8`），iTunes 中文词 0 条（已用英文词补到 6 条）。电台只拼免费/试听，不冒充付费曲。
6. **设置视图审计只实点 1/11：** 其余 10 个按钮（心情 6 个、Spotify 登录/退出、电台开始/停止等）在审计中因弹窗在首个点击后关闭而未逐个实点；但它们的处理函数均已核查存在，且关键按钮（Spotify 登录→弹窗+verifier、电台开始→播放、心情设置）已在主验证/followup 中实际执行过。

---

## 五、已知限制

- **headless fps 不代表真机：** 无头 Chromium 软件渲染下 fps 仅 1–5，总督自动降至 eco；真机帧率与降档行为需真机验证。
- **总督手动档位语义：** 手动选档后档位立即生效，但 `mode` 仍为 `auto`——下一次自动采样仍会按 fps 继续调整。手动档位不是「锁定」，如需锁定档位是后续小改。
- **首页卡片指针遮挡：** 播放时首页隐藏、视觉引导层覆盖页面，Playwright 点按会被 `#canvas-container` 拦截——基线行为，真人使用时不影响（首页本就隐藏）。
- **Spotify 完整播放未验证：** 需 Ma 登录 + Premium + Redirect URI 登记后真机验证；Web Playback SDK 的设备转移与播放路径只在代码层接好。
- **iTunes 试听覆盖随查询词而定：** 中文心情词在 CN 区常返回 0 条，已用英文词兜底；部分心情的 iTunes 曲名可能重复（不同艺人同名，如「Relaxing Piano」出现多次，去重键为 曲名|艺人）。
- **歌单详情与导入歌单：** 见 §四第 3 条（Web 未登录态限制）。

---

## 六、v2.2.0 模块化基线：收益 / 成本（未决定的架构选项，未动手）

- **收益：** 上游 v2.2.0 前端已模块化（v2.0.0 拆分：1,932 行外壳 + 105 个模块），接新平台/改 UI 时改动面小、可测试性更好；与上游演进方向一致，长期维护成本低。
- **成本：** 切换基线是一次大规模重构（单文件 ~29,000 行 → 多模块），需逐模块回归全部 8 视图与 Phase 1/2 功能，风险高；且 v2.2.0 的 Spotify 仅元数据（不播放）、QQ/酷狗/酷我同样无播放，切换并不能直接带来播放能力；GPL 义务与合规红线（见 Phase 0.5）不变。
- **建议：** 当前 Phase 2 已用「小步拆模块」把 Phase 1 网易云块独立成 `starwave-netease.js`，后续可继续按「每次只移一个模块 + 回归」的方式渐进拆分；是否整体切换到 v2.2.0 基线，建议在 Phase 1 验收后再由父代理/Ma 决定。

---

## 七、改动文件清单

| 文件 | 改动 |
|---|---|
| `web/public/index.html`（29,178 行） | A1 meta 两处（:18553/:18566）、A3 VIP（:19333）、听歌统计重入守卫（:15778–15800）、Spotify 标签/meta 分支（:18535 起）、两处 `<script>` 引用（:2776、:29176） |
| `web/public/starwave-netease.js`（新增，185 行） | Phase 1 网易云模块 + `STARWAVE_DEMO_SONGS` 拆出 |
| `web/public/starwave-phase2.js`（新增，914 行） | Spotify PKCE + SDK、Apple Music 框架、私人电台、移动端 P0（dvh/安全区/滑动/Media Session/总督）、设置/关于页、粘贴 Cookie 登录禁用 |
| `scripts/verify-phase2.py`（新增） | Phase 2 全量验证（含 Spotify 授权/drain/TTL、电台、移动端、总督、Apple、密钥扫描） |
| `scripts/verify-phase2-followup.py`、`-followup2.py`、`-followup3.py`（新增） | 跟进验证：授权 URL 直测、电台/芯片/歌单详情/MusicKit |
| `scripts/audit-phase2.py`（新增） | 8 视图界面审计 |
| `scripts/regression-listen-recursion.py`、`attribute-stack-overflow.py`、`bisect-stack-overflow.py`、`capture-stack-overflow.py`、`capture-stack-overflow2.py`、`wait-stack-overflow.py`（新增） | 栈溢出归因与回归探针（保留，供复查） |
| `web/dist/` | 构建产物已更新（含两个新文件） |

未动：Folia、AURORA、CINEMA ONE、NEON MUSIC、其他项目；未部署、未 gh、未登录任何账号、未产生费用。
