# MINERADIO NEXT（星澜音乐 StarWave）Phase 6 线上验证报告

**结论先行：验证已跑完。桌面 10/10 通过；手机 5/6 通过，1 项失败、1 项判定修正。**
线上站点本身健康：加载 0 console 错误、0 page 错误、0 失败请求；演示曲、搜索、AI DJ、混合推荐、Spotify 授权 URL 格式全部通过；两轮运行零汽水/抖音请求断言通过。
唯一的问题在手机端 Phase 4B 手势：**双击喜欢与长按菜单在 390px 竖屏下真实不可达**——两个手势目标元素都被 CSS 藏起来了（详见第 5 节）。这是 Phase 4B 代码既有问题，不是部署导致；桌面端手势目标可见，不受影响。

- 线上地址：https://wengzikang.github.io/mineradio-next/
- 验证日期：2026-11-09（CST，约 23:30–23:40）
- 验证员：Phase 6 线上验证员（第二次派单，subagent）
- 验证脚本：`~/workspace/mineradio-next/scripts/verify-live.py`（新建；Playwright Chromium + 中继 18082 代理 + console/pageerror/requestfailed 收集；BASE_URL 为线上地址，未起本地静态服务器）
- 报告文件：`~/workspace/mineradio-next/LIVE_VERIFY_REPORT.md`（本文件，覆盖上一轮“未验证”版本）
- 运行 JSON 日志：`/tmp/sw-live-desktop.json`、`/tmp/sw-live-mobile.json`、`/tmp/sw-live-mobile-gesture-probe.json`

## 1. 前置检查结果

任务指定的检查：`curl -x http://127.0.0.1:18082 https://wengzikang.github.io/mineradio-next/`。

| 探针 | 结果 |
|---|---|
| curl 经中继 → github.io | **HTTP 200，1,481,555 字节，1.24s**，`<title>StarWave</title>` |
| 中继进程 | PID 20571（重启后的新中继），存活，未动 |
| Range 服务器 | PID 5439（4174），存活，未动 |

前置检查一次通过，直接进入两遍浏览器验证。中继与 Range 服务器全程未重启、未触碰。

## 2. 桌面验证结果（1280×800）

| 检查项 | 结果 | 证据 |
|---|---|---|
| 页面加载（console 错误 / page 错误 / 失败请求） | ✅ 通过 | title=StarWave；console 错误 0、page 错误 0、失败请求 0；页面共 56 个请求 |
| window.starwavePhase4b 存在且 available | ✅ 通过 | version `0.4.0-phase4b`，available=true |
| window.starwavePhase3 存在 / window.starwavePhase4a 不存在 | ✅ 通过 | phase3=true，phase4a=false（汽水已移除） |
| 演示曲樱花真实播放前进 | ✅ 通过 | `demo/sakura.mp3`，dur 209.25s；currentTime 2.73→4.53，**前进 1.8s**，paused=false |
| 搜索“周杰伦”返回条数 | ✅ 通过 | **共 14 条：网易云 10 条 + Audius 4 条**（见下） |
| Phase 4B 面板：规则 AI DJ 生成 6 首并真实播放 | ✅ 通过 | 生成 **6 首**，`规则生成，非大模型`，line“午后好天气，适合慵懒一点的旋律。”；播放 currentTime 2.64→4.58，**前进 1.94s**，paused=false |
| 混合推荐有结果 | ✅ 通过 | **20 首**，platform=34，platformReason=""，local=0，coldStart=false |
| Spotify 授权 URL 格式（仅格式，不登录） | ✅ 通过 | 见第 3 节 |
| 本次运行经中继的外发请求中 *qishui* / *douyin* / *douyinvod* 为 0 条 | ✅ 通过 | 中继日志增量 97 行，0 条；页面 56 个请求，0 条 |

搜索“周杰伦”明细（14 条）：Audius 4 条（`周杰伦-七里香AUDIUS`、`周杰伦-断了的弦AUDIUS`、`周杰伦-七里香AUDIUS`、`周杰伦 - 完 美主 义AUDIUS`，tag `AUDIUS`）；网易云 10 条（`屋顶`、`布拉格广场`、`刀马旦`、`骑士精神`等，tag `网易云`，meta 注明“网易云（非官方社区服务，仅免费曲）· 未登录”）。观察（非失败）：网易云结果标题带“网易云VIP”后缀，属搜索元数据展示，本次未测试其播放——按既有边界，未登录免费曲之外不作断言。

DJ 生成的 6 首：樱花、茉莉花、Greensleeves、Amazing Grace、Clair de Lune、Daisy Bell。

## 3. Spotify 授权 URL 格式检查（仅格式，未登录）

未点登录按钮、未开弹窗、未跳转、未输入任何账号密码、未走授权码交换。
直接调用页面已暴露的 `window.starwaveSpotify.buildAuthUrl()` 取回 URL 字符串做格式校验：

| 字段 | 实际值 | 预期 | 结果 |
|---|---|---|---|
| host + path | `accounts.spotify.com/authorize` | 同左 | ✅ |
| client_id | `35e5a591884f42d398ab298ab79f16cb` | 同左 | ✅ |
| redirect_uri | `https://wengzikang.github.io/mineradio-next/` | 同左 | ✅ |
| response_type | `code` | `code` | ✅ |
| code_challenge_method | `S256` | `S256` | ✅ |
| code_challenge / state | 均存在 | 均存在 | ✅ |

不记为 bug 的已知事项：Ma 尚未在 Spotify Dashboard 注册这个新 redirect URI，真实登录本来就会失败——本次未尝试登录，不作登录结论。

## 4. 手机验证结果（390×844，竖屏，is_mobile + touch）

| 检查项 | 结果 | 证据 |
|---|---|---|
| 页面加载无 page 错误 | ✅ 通过 | title=StarWave；console 错误 0、page 错误 0、失败请求 0；页面共 28 个请求 |
| 竖屏 portrait=true、歌单架 side | ✅ 通过 | `portrait=true, shelf="side", reason="checked"` |
| 演示曲真实播放前进 | ✅ 通过 | `demo/sakura.mp3`，currentTime 2.51→4.41，**前进 1.9s**，paused=false |
| 双击喜欢 0→1 | ❌ **失败** | 收藏数 0→0（见第 5 节） |
| 长按菜单弹出 | ⚠️ **判定修正为失败** | 见第 5 节 |
| 本次运行经中继的外发请求中 *qishui* / *douyin* / *douyinvod* 为 0 条 | ✅ 通过 | 中继日志增量 39 行，0 条；页面 28 个请求，0 条 |

## 5. 失败项定性：手机手势不可达（线上代码既有问题，非部署导致）

### 现象

- **双击喜欢**：真实触屏双击 `#control-cover` 无反应；Playwright `dblclick` 回退超时 5s——元素不可见（`element is not visible`）。收藏数始终 0→0。
- **长按菜单**：主运行脚本用 JS 合成 `TouchEvent` 直接派发到 `#control-cover`，菜单显示，JSON 里记为 PASS。但随后探针证明该结果**不能代表真实用户手势**，应修正为失败，原因如下。

### 根因（均在已部署代码中，本地同款代码同样复现，与部署方式无关）

1. `#control-cover`：`docs/index.html:763` 有 `@media (max-width:720px){ .control-cover{display:none} }`。390px 宽下该元素 `display:none`，0×0，不可点。
2. `#thumb-cover`（另一手势目标，`bindCoverGestures` 同时绑这两个元素，`docs/starwave-phase4b.js:1055`）：父容器 `#thumb-wrap` 基础样式就是 `display:none`（`docs/index.html:570`），而 `.visible` 规则只改透明度与 pointer-events（`:571`），**全站没有任何规则把 `#thumb-wrap.visible` 的 display 改回 flex/block**。播放后实测：`#thumb-wrap` 已带 `visible` class，但仍 `display:none`，`#thumb-cover` 0×0。也就是说左下小封面在任何模式下都不显示——疑似缺了一条 display 规则。
3. 探针复核（播放状态下重测，排除时序因素）：`control-cover display:none 0×0`；`thumb-cover 0×0`；`thumb-wrap class=visible 但 display:none 0×0`；音频正常播放中（ct 3.1）。CDP 真实触摸长按（touchStart → 保持 700ms → touchEnd）在 `#thumb-cover` 上同样无反应。
4. 探针同时确认：手机首页视图内**没有其他可见的喜欢按钮**（按 喜欢/like/favorite/收藏 文本与 aria-label 扫描，可见按钮 0 个）。

### 定性

- **是否线上导致：否。** 是 Phase 4B 手势绑定目标与响应式 CSS 冲突的既有代码问题；本地 390px 同样复现（规则在源码里，不依赖部署）。
- **是否已知/既有：半已知。** Phase 4B 本地验证的双击/长按用的是桌面页（1280px 下 `#control-cover` 可见，通过）；390px 页当时只测了 portrait shelf，未测手势。手机手势不可达是本次线上验证首次抓到。
- **影响面：** 仅手机竖屏（≤720px 宽）默认视图；桌面端手势目标可见，不受影响。长按菜单的处理器代码本身是好的（合成事件能弹出菜单），缺的是一个真实可触的目标。
- **JSON 与报告口径说明：** `/tmp/sw-live-mobile.json` 中 `mobile.longpress_menu` 仍为合成事件下的 PASS（`menuShown: true`）；本报告以探针结论为准，将该项修正为失败。探针结果见 `/tmp/sw-live-mobile-gesture-probe.json`。

## 6. 零汽水请求断言

| 运行 | 中继日志窗口 | 增量行数 | 含 *qishui* / *douyin* / *douyinvod* | 页面请求数 | 页面请求中违禁 |
|---|---|---|---|---|---|
| 桌面 | 行 795→892 | 97 | **0 条** | 56 | **0 条** |
| 手机 | 行 892→931 | 39 | **0 条** | 28 | **0 条** |
| 合计 | — | 136 | **0 条** | 84 | **0 条** |

桌面请求 host 清单：`wengzikang.github.io`、`api-enhanced-pied-rho.vercel.app`（网易云）、`discoveryprovider.audius.co`、`audius-discovery-1.altego.net`、`audius-content-2.figment.io`、`itunes.apple.com`、`p3.music.126.net`、`p4.music.126.net`、`v.monophonic.digital`、`val002.open-audio-validator.com`。无任何 *qishui* / *douyin* / *douyinvod* host。手机请求 host 仅 `wengzikang.github.io` 与 `itunes.apple.com`。

## 7. 与干净树基线的对照

| 基线项（CLEAN_TREE_VERIFY_REPORT.md） | 本次线上对照 |
|---|---|
| Phase 1/2/3 exit 0；Phase 4B 修掉过期断言后重跑 exit 0、61/61 | 未受影响；本次只验证、未改代码、未跑本地测试 |
| 树上无汽水代码；130 条外发请求 0 条汽水/抖音 | 线上新增 136 行中继日志 + 84 个页面请求，同样 **0 条**；结论一致 |
| 线上 curl 已验证 HTTP 200、1,481,555 字节、标题 StarWave、各脚本 200、0 汽水脚本引用 | 本次前置 curl 复核：HTTP 200、1,481,555 字节、标题 StarWave；其余脚本项为上一轮已核实结果，本次未重复 curl |
| git 树：main 在 commit 1a3cbea，已推送 | 未提交、未推送、未做 gh 操作；`git status` 仅有未跟踪文件（本报告、`scripts/verify-live.py`、此前已存在的 `PHASE5_REPORT.md`），无已跟踪文件改动 |

## 8. 本次实际改动

- 新建：`scripts/verify-live.py`（验证脚本，唯一新增代码文件）、本报告 `LIVE_VERIFY_REPORT.md`（覆盖上一轮“未验证”版本）。
- 未改动：项目代码、git 树（无提交/推送）、Folia / AURORA / CINEMA ONE / NEON MUSIC 及其他项目（均未碰）。
- 未启动 / 未停止任何进程：4174（PID 5439）与 18082（PID 20571）原样保留，未动；浏览器进程随脚本结束已退出。
- 未做任何真实登录、未扫码、未输入账号密码；未调用解密/下载接口；未造 mock 数据冒充通过——失败项如实记为失败。

## 9. 未验证项清单

**无。** 任务列出的桌面 9 项 + 手机 6 项全部跑完，无“未验证”项。唯一需要说明的是：Spotify 只做了授权 URL 格式检查（任务明确要求不走登录流程），真实登录流程本身未验证——这是任务红线要求，不是遗漏。

## 10. 需要协调员决定的事

1. **手机手势修复**（建议修 Phase 4B）：两个手势目标在 ≤720px 下均不可见。可能修法（二选一或并行）：(a) 给 `#thumb-wrap.visible` 补一条 `display:flex` 规则，让左下小封面真正显示出来，手势随之可用；(b) 在手机竖屏默认视图另给一个可见的喜欢入口（如底栏爱心按钮）。修完后需在 390px 真机/移动端视口重测双击喜欢与真实长按。
2. 本报告的手机长按项判定以探针为准（失败），与 `/tmp/sw-live-mobile.json` 中合成事件 PASS 口径不同——如需 JSON 与报告完全一致，可由后续修复验证时重跑覆盖。
3. 除第 1 条外，线上站其余功能均已验证通过，无需其他动作。
