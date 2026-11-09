# StarWave Phase 4A — 汽水音乐 QishuiProvider 接线报告

- 日期：2026-11-09（CST 21:30 左右）
- 执行人：Phase 4A 执行员（子代理）
- 范围：只动 `~/workspace/mineradio-next/`；未碰 Folia、AURORA、CINEMA ONE、NEON MUSIC
  和其他项目。未提交、未推送、未做 gh 操作。未登录任何账号、未代扫码、未获取/保存
  Cookie、未创建 API 密钥、未产生费用、未部署后端。
- **总体状态：接线代码已完成并构建通过；Tier A 验证 9 项中 8 项通过，试听真实播放
  未通过（见 §六）；Tier B 与 Phase 1/2/3 回归未跑完——一次长时浏览器调试被明确拒
  绝后按要求停下，不再重试。协调员需决定下一步（见 §九）。**

## 一、改动文件清单

| 文件 | 性质 | 说明 |
|---|---|---|
| `web/public/starwave-phase4a-qishui.js`（新建，约 28KB） | 新增 | Phase 4A 包装文件：包装已有全局函数接汽水（与 Phase 2 wrapPlayback 同手法），try/catch 包裹，失败只降级 |
| `web/public/index.html`（29249–29250 行） | 2 行 | 在 `starwave-phase3.js` 之后加 `<script src="starwave-qishui.js"></script>` 与 `<script src="starwave-phase4a-qishui.js"></script>`；其余未动 |
| `scripts/verify-phase4a-qishui.py`（新建） | 新增 | Playwright 验证脚本：Tier A（后端已配置）+ Tier B（后端未配置） |
| `PHASE4A_QISHUI_REPORT.md` | 新增 | 本报告 |

未改动：`starwave-phase2.js`、`starwave-phase3.js`、`starwave-netease.js`、
`starwave-qishui.js`（未发现需修的 bug）、品牌、PWA 缓存名（`starwave-pwa-v1`）。

## 二、§九逐项完成情况

1. **引入 `starwave-qishui.js`**：完成。index.html:29249 引入 `starwave-qishui.js`，
   :29250 引入包装文件 `starwave-phase4a-qishui.js`（在 `starwave-phase3.js` 之后）。
2. **搜索聚合**：完成。包装 `fetchMusicSearchResults`：并行调 `searchQishuiSongs` +
   `searchQishuiPlaylists`；汽水歌曲（当前恒 0 首）经 `mergeSongSearchResults`，
   `playable:false` 按现有规则自动 −120 降权；歌单记入
   `window.starwavePhase4a.lastSearch.playlists`，`doSearch` 包装在结果渲染后用
   `showSourceFallbackNotice` 诚实提示（歌单数 + 前 3 标题；歌曲搜索不可用时说明原因）。
   实测“周杰伦”：`song_reason='song_search_unavailable'`，歌单 3 条以上（首条
   “周杰伦歌曲合集精选”，id `qishui:7661483391803523099`，41 首）。
3. **发现页**：完成（有 1 个竞态见 §七）。包装 `loadHomeDiscover`：完成后调
   `fetchQishuiDiscoverPlaylists(6)`，成功后并入 `homeDiscoverState.playlists`
   （经 `normalizePlaylistRecord`，provider `qishui-import`，去重），再
   `renderHomeDiscover()`；失败且后端已配置时显示“汽水推荐暂不可用”（每会话一次，
   不阻塞其他来源）。实测：推荐歌单返回 8–10 条（首条“长久的陪伴抵不过她的怦然心动”）。
4. **歌单详情**：完成。包装 `openPlaylistPanelDetail`（汽水分支走
   `fetchQishuiPlaylistDetail`，复用原切换/关闭/渲染逻辑）、`loadPlaylistIntoQueueById`
  （`qishui:` 前缀分支，复用原队列载入逻辑）、`playPlaylistPanelDetail`（汽水详情
   直接进队列播放）；歌曲进队列保持 `provider:'qishui'`。实测：歌单详情返回 11 首
   （`count=20` 请求，上游只给 11 首媒体资源），全部 `provider:'qishui'`、
   `playable:false`；面板 UI 打开同一歌单同样 11 首。
5. **播放**：完成（代码），**真实播放未验证通过（见 §六）**。包装
   `songProviderKey`（汽水 → `'qishui'`）与 `isPublicSourceProviderKey`（含
   `'qishui'`），使 `playQueueAt` 把汽水走 `fetchPublicSourcePlayback`；包装后者：
   调 `fetchQishuiPlayback`，仅 trial 时设 `song.publicAudioUrl=url`、
   `song.trial=true`，返回 `{trial:true, level:'preview', quality:'汽水音乐'}`，
   复用现有 trial-banner（文案“汽水音乐返回试听片段”）；`protected_audio` /
   `url_unavailable` 时返回对应 reason + 文案“完整版请去汽水音乐官方 App 收听”。
   `songSourceTagHtml` 包装：汽水显示 `QS` 标签。
6. **歌词**：完成（代码 + 接口实测，播放中歌词源未确认——因试听未播起，见 §六）。
   包装 `fetchLyric`：汽水歌曲调 `fetchQishuiLyric`，返回的标准 LRC 喂给现有
   `parseLyricText`，`format:'krc'` 时 timingSource 记为 `'qishui-krc'`（逐字 KRC
   转制）；无歌词时回退 LRCLIB（与公共源分支同一做法）。实测示例曲：歌词
   `format='krc'`，LRC 长 1208 字符，53 行，首行 t=0.06“不敢回看”。
7. **电台**：完成。`window.starwavePhase4a.radio()` 调 `fetchQishuiRadioList`，
   实测返回 0 电台（`reason='no_radios_returned'`），返回文案恒为“汽水电台暂无内容”；
   未编任何电台入口。设置页另有一行“汽水电台：汽水电台暂无内容（未登录态无电台）”。
8. **登录 UI 不接**：完成（刻意不接）。本文件不调用 `startQishuiLoginQr`，不加任何
   汽水登录入口；设置页明示一行“汽水登录：未接（需服务端会话桥建成后才接）”。
   `window.starwavePhase4a.loginNotWired=true`。
9. **状态页**：完成。包装 `window.starwaveOpenAbout`：原弹窗渲染后追加汽水行并异步
   刷新 `getQishuiStatus()`。未配置显示“汽水音乐后端未部署”；已配置且 `/health`
   通显示“已连接 · 仅元数据 + 30 秒试听”；已配置不可达显示“后端不可达”。
10. **发布前确认后端地址未填入任何真实值**：完成。`web/public` 内没有任何代码
    给 `window.STARWAVE_QISHUI_API_BASE` 赋值；默认留空。grep 见 §八（有 1 处例外说明）。

## 三、验证环境

- 本地测试后端：`/tmp/qishui-api-verify`，重新 clone 自 guowenye/qishui-api，
  HEAD `e409c10fe7441a10d370da7da61d62bbc1e5126c`（MIT），`npm install` 66 个包，
  `HOST=127.0.0.1 PORT=3300 QISHUI_ENABLE_DECRYPT=false node app.js`。
  `/health` 200 `{status:'ok'}`。**验证结束后已停掉（`ps` 无残留，3300 不再响应）。**
- 验证脚本：`scripts/verify-phase4a-qishui.py`（Range 静态服务器 4174 + 中继
  18082 + Playwright Chromium，仿 `verify-phase3.py` 写法）。完整报告 JSON 在
  `/tmp/sw-phase4a-verify-report.json`。
- Tier A 运行一次（约 11 分钟），Tier B 未跑，回归（verify-phase1/2/3）未跑。

## 四、Tier A 实测数字（后端已配置 → 127.0.0.1:3300）

| 检查 | 结果 |
|---|---|
| 模块加载 | `starwaveQishui: object`，`starwavePhase4a.available: true`，`loginNotWired: true`，`api_base: http://127.0.0.1:3300` |
| 搜索“周杰伦” | 共 14 首（汽水歌曲 0 首）；`song_reason='song_search_unavailable'`；歌单 ≥3 条，首条“周杰伦歌曲合集精选”41 首 |
| 发现页 | `fetchQishuiDiscoverPlaylists` 返回 10 条（首条“长久的陪伴抵不过她的怦然心动”），`reason=''` |
| 歌单详情（API） | 标题“周杰伦歌曲合集精选”，11 首，全 `provider:'qishui'`，`playable:false`；首 3 首：默（李荣浩 / 周杰伦）、tusemde sen、龙卷风（G.E.M. 邓紫棋） |
| 歌单详情（面板 UI） | `key='qishui-import:qishui:7661483391803523099'`，`loading:false`，tracks 11 首 |
| 歌曲详情（示例曲 7079108541549643812） | 小半 / 陈粒 / 小梦大半 / duration 297 秒 / provider qishui |
| 歌词（示例曲） | `format='krc'`，LRC 1208 字符，53 行，首行 t=0.06“不敢回看” |
| 试听播放 | **未通过**（见 §六） |
| 电台 | 0 个，`reason='no_radios_returned'`，文案“汽水电台暂无内容” |
| 状态（已配置） | `configured:true, backendReachable:true`，文案“已连接 · 仅元数据 + 30 秒试听” |
| 关于页（已配置） | 汽水行“已连接 · 仅元数据 + 30 秒试听”；电台行、登录行文案如 §二第 7/8 项 |
| 后端请求总数 | 14 次（search/mixed、search/playlist、recommend/playlist、playlist/detail、song/detail、lyric、audio/info、radio/list、health×2，及试听回退触发的 2 次搜索） |
| 红线请求 | **0 次**命中 `/decrypt/spade`、`/audio/decrypt`、`/download/file`、`/download/url` |
| pageerror | 0 |
| console error / failed request | 21 条 console error、25 条 failed request，**全部是 douyinpic 封面图 CORS/ORB 拦截**（`p3-luna.douyinpic.com` 无 `Access-Control-Allow-Origin`）**与 1 次 douyinvod 音频请求失败**；与接线代码无关（见 §六） |

## 五、Tier B（后端未配置，出货状态）

**未跑。** 验证脚本已写好 Tier B（状态行“汽水音乐后端未部署”、关于页三行文案、
搜索零后端请求、无伪造数据），但因 §九的停止决定未执行。需协调员决定后补跑。

## 六、未通过项：试听真实播放（重点）

现象（两次独立浏览器运行一致）：

- `fetchQishuiPlayback` 本身成功：`{playable:true, trial:true, reason:'trial'}`，
  返回 douyinvod 签名地址（如 `v5-ex-luna.douyinvod.com`、`v26-luna.douyinvod.com`）；
  `playQueueAt` 正常走到试听分支：队列歌曲已设 `trial:true`、`publicAudioUrl` 有值，
  trial-banner 正常显示“汽水音乐返回试听片段”。
- 但 `<audio>` 元素始终拿不到数据：`paused=false`、`currentTime=0`、`duration=NaN`、
  `readyState=0`、`networkState=2`（加载中）、`error=null`，20 秒无进展；第一次运行
  音频请求直接失败 `net::ERR_EMPTY_RESPONSE`；裸 `<audio>` 元素 60 秒对照同样
  `readyState=0`，最终 `play()` 报 `NotSupportedError: Failed to load because no
  supported source was found.`。
- 对照：同一签名地址用 curl 经 egress 代理 Range 取 64KB 成功（HTTP 206，65,536 字节，
  3.7 秒，文件类型 ISO Media M4A）；经中继 18082 的 curl 同样 206 成功；中继日志显示
  Chromium 的 `CONNECT v5-ex-luna.douyinvod.com:443` 得到了 `200 Connection Established`。
  即：**地址真实有效、隧道已建立，但 headless Chromium 的媒体元素经此中继就是拉不到
  数据**（fetch 层面的对照因停止决定未做完，未能区分是媒体元素问题还是该宿主问题）。
- 影响：任务要求的“示例曲试听真实播放（paused=false、currentTime 前进、duration≈30）”
  **未达成**。接线代码本身（地址解析、trial 标记、banner）已按真实链路走通并有证据，
  失败点在 headless Chromium + 中继环境下的媒体拉流，不在 StarWave 代码内——但按
  oauth_redirect_login_verification 纪律，**不宣称试听播放可用**。
- 歌词联动也因此未确认：试听未播起时 `lyricsTimingSource='fallback'`、`lyricsLines=1`；
  接口层面的 KRC→LRC 转换已实测（§四歌词行）。

## 七、已发现但未修的 bug：发现页合并竞态

- 现象：Tier A 首次运行中，`lastDiscover` 有 10 条推荐歌单，但同一时刻读
  `homeDiscoverState.playlists` 里的汽水歌单为 0 条；单独调试复跑同一流程则合并成功
  （20 条，全为 `qishui-import`）。
- 原因推测：页面加载时 `loadHomeDiscover` 已在后台进行中（`loading=true`），此时再调
  `loadHomeDiscover(true)`，原函数直接 early-return，我的包装随即合并，但随后先行的那次
  加载完成时把 `homeDiscoverState.playlists` 重置为连接器歌单（空），覆盖了合并结果。
  属时序竞态，非每次复现。
- 修复方向（未实施）：包装的 `afterLoad` 里先等 `homeDiscoverState.loading===false`
  再合并（合并本身已去重，可安全重入）。需协调员决定后实施并重测。

## 八、grep 证明（后端地址）

- `grep -rn "127.0.0.1" web/public/`：仅 1 处命中——`web/public/starwave-qishui.js:3`
  的注释“对接的上游：guowenye/qishui-api（MIT），独立 Node/Express 服务，默认
  127.0.0.1:3300。”这是 Provider 交付时已有的注释（描述上游默认监听地址），不是配置值；
  按任务要求未改该文件。**除此注释外，`web/public` 内无任何 `127.0.0.1` 或真实后端地址，
  `STARWAVE_QISHUI_API_BASE` 在 `web/public` 内无任何赋值。**
- `127.0.0.1:3300` 只出现在测试脚本 `scripts/verify-phase4a-qishui.py`（及调试用的
  `/tmp` 临时脚本）与本报告中。
- 构建：`npm run build:web` 通过；`node --check` 通过两个新/相关 JS 文件；
  `web/dist/index.html` 含 `starwave-qishui.js` 与 `starwave-phase4a-qishui.js` 各 1 处引用。

## 九、未完成 / 待协调员决定

1. **试听真实播放未通过**（§六）：需决定——(a) 在真机/其他网络环境重测（最可能只是
   headless + 中继环境的媒体拉流问题）；(b) 或接受“试听链路代码已通、播放待真机验证”
   的降级结论。不要在未验证的情况下宣称试听可用。
2. **Tier B 未跑**：脚本已就绪，跑一次约数分钟。
3. **回归未跑**：`verify-phase1.py`、`verify-phase2.py`、`verify-phase3.py` 未重跑。
   Phase 4A 只包装新增分支，理论上不影响旧链路，但未实测证明。
4. **发现页合并竞态修复未实施**（§七）：约 10 行改动 + 重测。
5. **停止原因**：一次长时浏览器调试（裸 `<audio>` 60 秒对照）在执行中被明确拒绝，
   按要求立即停下，不再重试该类调试。以上第 1–4 项均涉及再次运行浏览器验证，
   需协调员明确授权后再继续。
6. 歌单详情只返回 11 首（请求 `count=20`，上游媒体资源仅 11 条）：上游行为，非 bug。
7. `protected_audio` 分支（有 spade_a 的曲）未实测：没有已知的带 spade_a 曲目 ID，
   代码路径与文案已就绪。
8. 汽水封面图在浏览器内大面积 CORS/ORB 拦截（douyinpic 无 ACAO 头）：属上游
   宿主行为，封面加载失败时页面有降级（`onerror` 透明），不阻塞功能；生产上可考虑
   封面代理，但不在本次任务范围内。

## 十、报告人声明

- 未调用 `/decrypt/spade`、`/audio/decrypt`、`/download/file`、`/download/url`
  （全程请求计数 14 次，红线 0 次）；未解密 spade_a；未复制 decryptor / 安全 SDK；
  未硬编码密钥/Cookie；未用“粘贴 Cookie 登录”；未把 sessionid/token/完整音频 URL
  写进日志或 localStorage（音频 URL 仅出现在浏览器内存与本次报告的失败请求行里，
  该 URL 为已过期的签名地址，报告 JSON 在 /tmp，不进仓库）。
- 未提交、未推送、未动 git 历史；未动线上部署；本地测试后端已停止。
- 未编造接口地址与测试成功结果：试听未通过、Tier B 未跑、回归未跑、竞态未修，
  均如实写明。

## 十一、跟进补记（2026-11-09 约 22:35 CST，协调员代记）

跟进员因一次验证运行被明确拒绝而停下，未能把本节写回报告；以下由协调员按跟进员的汇报原文 + 自己的核验代记。

### 1. 发现页合并竞态：已修 + 已重测通过 ✅

- 修了一个比原报告更深的 bug：初版修复的自执行函数写成了 `(function waitThenMerge(){...});`，漏了末尾的 `()`——语法合法、`node --check` 通过，但永不执行，合并从未发生。上一轮 Tier A 里“单独调试复跑合并成功（20 条）”是直接调合并逻辑走通的，不是这条包装路径。已改为 `(...)()`，并顺带修了同函数内的旧问题：未配置分支重设 `state.lastDiscover` 后不同步 `window.starwavePhase4a.lastDiscover`（暴露的是旧对象引用）。
- 重测数字（后端 HEAD e409c10，健康正常）：
  - 1a 真实竞态（连续两次 `loadHomeDiscover(true)`）：t+5s / t+10s / t+20s 三次采样完全稳定——`home_total=22、home_qishui=22、last_discover_n=10、reason=''`，未被覆盖。
  - 1b 强制等待（人为 holding `loading=true` 2 秒）：t+1s 时 0 条合并（等待中，正确）；释放后 t+10s：`home_qishui=10、last_discover_n=10`，首条“祝我们在生命中的夏日永远年轻ε٩(๑> ₃ <)۶з！”。
- 调试插桩已全部清除（协调员核验：`grep __p4a` 为 0）；`node --check` 通过；`npm run build:web` 通过。
- 中间插曲：重跑时发现 /tmp 清理删掉了上一轮的 clone 目录与日志，后端已死，导致一轮 `discover_failed` / `song_detail_failed`；已重新 clone 到 `/tmp/qishui-api-followup2`（HEAD e409c10，66 个包）后重跑通过。教训：以后后端不要只放 /tmp，或每轮现 clone 现用。

### 2. 试听有界检查：已做，未超 15 秒，无长时调试 ✅（降级结论不变）

- 2a 页内 `fetch()` 带 Range 头请求 trial 地址：20 秒上限内 0 字节，AbortError（宿主 `v11-luna.douyinvod.com`）。结合上一轮“中继 CONNECT 得 200、curl 经中继取 64KB 得 206”，结论收窄：不是单纯媒体元素问题——headless Chromium 经此中继在 HTTP 层就拿不到该宿主的字节。
- 2b 唯一一次短 `<audio>` 尝试（走 `playQueueAt` 真实链路，上限 15 秒）：19 个采样（0–14.8 秒）全部 `readyState=0、networkState=2、currentTime=0、duration=null、paused=false、error=null`；`playQueueAt` 5 秒内未 resolve（超时竞态触发）；`reached_data=false、current_time_advanced=false`。但试听链路本身用真实数据走通：队列歌曲 `trial=true`、有真实 `publicAudioUrl`、trial-banner 正常显示。
- **降级结论：trial 地址解析 + 试听分支 + banner 已用真实数据验证；douyinvod 音频在 headless + 中继环境下的 `<audio>` 实际解码未验证，需真机验证。绝不宣称试听播放可用。** 全程未记录完整音频 URL（只记宿主 + 状态 + 字节数）；红线请求 0 次。

### 3. 未做的事（因验证运行被明确拒绝而停下，未重试）

- 任务 2 Tier B 未跑（后端未配置的出货状态；脚本已就绪）。
- 任务 3 回归未跑（`verify-phase1.py` / `verify-phase2.py` / `verify-phase3.py` 的 exit 码与错误数）。
- 最终 grep 由协调员代补（见 §4）：`web/public` 内无真实后端地址赋值，仅 `starwave-qishui.js:3` 一处交付时已有的注释提到上游默认监听地址。

### 4. 后端收尾（协调员已处理）

- 跟进用的 `/tmp/qishui-api-followup2` 后端（`node app.js`，PID 3635）在汇报后仍在 `127.0.0.1:3300` 运行，已由协调员 kill；核验：3300 已关闭，`/health` 无响应。无残留进程。

### 5. §九待决定项状态更新

| # | 项 | 状态 |
|---|---|---|
| 1 | 试听真实播放 | 降级结论（见 §十一.2）：链路代码已通、播放待真机验证；不宣称可用 |
| 2 | Tier B | ⏳ 待父代理决定：是否重新授权验证运行（跟进员的验证运行被明确拒绝后停下，未重试） |
| 3 | 回归重跑 | ⏳ 同上 |
| 4 | 发现页合并竞态 | ✅ 已修 + 已重测通过（见 §十一.1） |
| 5 | 停止原因 | 跟进验证运行被明确拒绝；以上第 2–3 项涉及再次运行浏览器验证，需父代理明确授权后再继续 |

## 十二、汽水移除记录（2026-11-09 约 22:55 CST，协调员执行）

- **决定：** Ma 2026-11-09 22:45 发话“汽水不要了”——MINERADIO NEXT 里汽水音乐移除。
- **拆了什么：**
  - `web/public/starwave-qishui.js`、`web/public/starwave-phase4a-qishui.js`、`scripts/verify-phase4a-qishui.py`、`services/qishui-api/`（整个目录，含 Dockerfile、docker-compose、README、SECURITY_CHECKLIST、DEPLOY_DECISION.md、QISHUI_PROVIDER_REPORT.md、test-provider.js）全部移出项目，归档到 `~/workspace/mineradio-next-archive/qishui-removed-2026-11-09/`（工作留底，不进公开仓库）。
  - `web/public/index.html` 的两行引入删除（原 29249–29250 行；`starwave-phase4b.js` 引入保留，现为 29249 行）。
  - `scripts/__pycache__/verify-phase4a-qishui.cpython-312.pyc`（Soda 验证脚本的编译残留）已删。
  - `starwave-phase2.js` 的 About 页音源行去掉汽水、`starwave-phase2.js`/`starwave-phase3.js`/`starwave-phase4b.js` 的头注释更新为“汽水已移除”。
  - 本报告保留在仓库内（历史记录，非代码）。
- **构建验证（拆除后立即核验）：** `npm run build:web` 通过；`node --check` 通过（phase2/phase3/phase4b）；`web/dist` 内无 Soda 文件。
- **残留说明（诚实）：** `web/public/index.html` 内仍有 29 行基线 `qishui-import` 残留——MrChenyh v0.1.0 基线自带的外链歌单导入桩代码，与 QQ/酷狗/酷我/Apple Music 的同类桩并列；全部需已删除的 Connector 扩展（Phase 1 已删）才能触发，无扩展时只显示“Need StarWave Connector”提示，不发任何汽水请求、不产生汽水数据。未动它们的原因：散布 29 处、手术风险高于收益，且与 QQ/酷狗/酷我/Apple 的同类桩不可分；干净树回归会确认零汽水请求。另有 3 行是我方新写的“汽水已移除”注释（phase3.js:6、phase4b.js:5/10），属于移除记录本身。
- **后端：** 从未部署；qishui-api 后端不用部署了；Oracle 机器不动（Ma 还在注册，别的用途等他自己决定）。
- **验证状态：** Tier B 是拆除前快照（当时出货状态诚实）；试听重测因移除取消，未跑；Phase 1/2/3 回归与 Phase 4B 套件在干净树上重跑（见干净树验证报告与最终交付报告）。
