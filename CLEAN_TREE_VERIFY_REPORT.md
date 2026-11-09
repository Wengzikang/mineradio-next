# StarWave 干净树验证报告（汽水移除后回归）

- 日期：2026-11-09（CST，约 15:00–15:30）
- 执行人：干净树验证员（子代理）
- 范围：只动 `~/workspace/mineradio-next/`；未碰 Folia、AURORA、CINEMA ONE、NEON MUSIC
  和其他项目。**只读 + 运行测试，未改任何项目代码**（未改脚本、未恢复任何汽水代码）。
  未提交、未推送、未做 gh 操作、未部署后端。
- 背景：Ma 2026-11-09 22:45 决定移除汽水；协调员已拆除（见
  `PHASE4A_QISHUI_REPORT.md` §十二）：`starwave-qishui.js`、
  `starwave-phase4a-qishui.js`、`scripts/verify-phase4a-qishui.py`、
  `services/qishui-api/` 已移出归档；`index.html` 两行引入已删；构建已通过。
- 验证环境：Playwright Chromium 无头 + 本地静态服务器（4173，验证员自起，已停）+
  Range 服务器 127.0.0.1:4174（上一轮遗留进程 PID 5439，非本次启动，未动）+
  测试中继 127.0.0.1:18082（上一轮遗留进程 PID 5434，非本次启动，未动）；
  每次运行前记录中继日志行号，运行后取增量统计外发请求宿主。

## 总体结论

- **四项全部跑完，无“未验证”项。** Phase 1 / 2 / 3 全部 exit 0；Phase 4B 全量
  60/61 通过，唯一失败是**预期后果**（见下），不是回归。
- **零汽水请求断言通过：四次运行共 130 条经中继的外发 CONNECT 请求，0 条发往
  `*qishui*` / `*douyin*` / `*douyinvod*` 宿主。** 四份运行日志里也无任何
  douyin/qishui 请求记录（唯一的 `qishui` 字串是 Phase 3 脚本自报的
  `qishui_untouched: "n/a"`，即模块已不存在，本身就是移除的证据）。
- 拆除没有弄坏东西：播放、歌词同步、频谱/EQ、队列、收藏、历史、歌单、电台、
  移动端、Phase 4B 全部功能的关键数字均与基线一致（见各节对照）。

## 一、逐项结果

### 1. `scripts/verify-phase1.py` — ✅ 通过

| 项 | 实测 | 基线对照 |
|---|---|---|
| exit 码 | **0** | 拆除前快照 exit 0（PHASE4B §六） |
| console 错误 | **0** | 快照 4（api-enhanced CORS 回显夹具产物）；本次 0，比快照更好，该夹具产物是间歇性的 |
| page 错误 | **0** | 快照 0 |
| 失败请求 | **0** | 快照 2（同款 CORS 夹具产物）；本次 0 |
| 演示曲播放 | 樱花 `paused=false`，0 → 1.384s 前进，`duration=209.25` | 快照 2.60s→3.79s 前进，一致 |
| 歌词 | 14 行，`timingSource='demo'`，首行“さくら さくら” | 快照 14 行，一致 |
| 搜索“周杰伦” | 14 条（网易云 10 + Audius 4），`neteaseWebSearchError=''` | 快照 14 条（网易云 10 + Audius 4），一致 |
| 网易云曲点击 | 未登录 toast“该曲目需登录网易云账号才能播放”，`playing=false` | 与快照行为一致 |
| 中继 CONNECT | 22 条，0 汽水相关 | — |

### 2. `scripts/verify-phase2.py` — ✅ 通过

| 项 | 实测 | 基线对照 |
|---|---|---|
| exit 码 | **0** | Phase 3 报告 §一第 9 项：exit 0 |
| console 错误 | **3** | 见下分解，全部是已知/既有项，与拆除无关 |
| page 错误 | **0** | 基线 0 |
| 失败请求 | **2** | 均为 Audius 封面图 `v.audius.rickyrombo.com/...1000x1000.jpg` 被 ORB 拦截（Phase 3 报告已记录“Phase 3 之前已存在”） |
| secret 扫描 | **0 命中** | 基线仅命中已删的 `starwave-qishui.js` 内 `spade_a` 字串；该文件已移除，本次 0 命中 |
| 关键数字 | 8 视图打开；搜索 14 条；Spotify 授权 URL 含 `accounts.spotify.com`、client_id `35e5a591…`、redirect `wengzikang.github.io/mineradio-next/`；verifier 在 localStorage；drain 假 code：`logged_in=false`、`url_cleaned=true`；drain 过期 TTL：`ttl_ms=600000`、`verifier_cleared=true`；电台队列 13 首；移动端 390×844 滑动切歌（樱花→茉莉花）、无横向溢出、Media Session 正常；Apple `pending_auth`、MusicKit 未加载 | 与 Phase 3 报告 §一第 9 项一致（radio 14 首为 Phase 3 当时数字，本次 13 首属电台队列正常波动；其余一致） |
| 中继 CONNECT | 64 条，0 汽水相关（含 `accounts.spotify.com` 2 条，即 drain 假 code 测试） | — |

**3 条 console 错误分解（均与拆除无关）：**
1. `400` 1 条——Spotify drain 假 code 测试向 `accounts.spotify.com` 换 token，上游返回
   HTTP 400（假 code 必然被拒）。任务已知的“1 条失败请求（accounts.spotify.com）”即此项；
   本次它以 console 错误形式出现（HTTP 400 是已完成的响应，不进 `requestfailed` 列表），
   故 `failed_requests` 里没有 Spotify 条目。证据：中继日志本窗口内 `accounts.spotify.com`
   恰好 2 条（授权页 + token 换取）。
2. `404` 2 条——本地 4173 静态服务器日志：`GET /api/update/latest?t=…` 两次 404。
   这是应用自带的更新检查向静态服务器请求不存在的接口路径，既有行为，与汽水无关
   （汽水代码从未提供该接口）。

### 3. `scripts/verify-phase3.py` — ✅ 通过

| 项 | 实测 | 基线对照 |
|---|---|---|
| exit 码 | **0** | Phase 3 报告第 7 轮 exit 0 |
| console 错误 | **0** | 基线 0 |
| page 错误 | **0** | 基线 0 |
| 失败请求 | **1** | 基线 0；见下分解，**不是拆除导致** |
| 演示播放 + 频谱 | 队列 6 首（樱花首曲），`paused=false`，ct 3.93，`duration=209.25`；频谱 max 214/226，low/mid/high ≈ 0.50/0.52/0.22；kick 0.77→0.56 | 基线一致 |
| 歌词同步 | 14 行；seek 20/40 行索引匹配 `match=true`；+500ms 偏移后恢复匹配 | 基线一致 |
| 音量 + EQ | 音量 0.5 生效；白噪声文件 EQ low +12 均值 0.80，−12 均值 0.56 | 基线一致 |
| BPM/Kick（90 BPM 确定性文件） | kick=1，onsets 14，bpm 51（慢速稀疏曲已知行为） | 基线一致 |
| 本地 mp3 导入 | 导入成功，队列 9 首 | 基线一致 |
| 网易云免费曲 | 4 位歌手各 10 条结果；fee-0 候选 7 首；首选“结尾曲-友谊地久天长(Live)”真实播放 `paused=false`、ct 5.72、`duration=416.92`；VIP 曲“富士山下”正确报需登录 | 基线一致 |
| iTunes 30s 预览 | 8 条结果；首曲真实播放 ct 4.55、`duration=30.01` | 基线一致 |
| 电台回归 | 队列 13 首，next 切歌正常 | 基线一致 |
| 队列操作 | 增/移/删/模式切换/清空均正常；重载恢复 `restored=true`、ct 40.16 | 基线一致 |
| 收藏 / 历史 | 收藏 3→4、取消收藏正常；历史记 1 次（樱花，`listenMs=5385`），清空后 0 | 基线一致 |
| 歌单 CRUD | 创建/改名/去重/删除均正常；网易云外链导入诚实提示“需要更新 StarWave Connector” | 基线一致 |
| 回归 (9) | Spotify 对象存在、`loginTtlMs=600000`；Apple `pending_auth`；Cookie 登录已停用 toast 正常；**`qishui_untouched: "n/a"`** | 该断言是信息性记录（非 pass/fail 判定）：模块已不存在，返回 `"n/a"`。这是 Ma 22:45 移除决定的**预期后果**，不是回归；脚本未改、代码未恢复 |
| 中继 CONNECT | 32 条，0 汽水相关 | — |

**1 条失败请求分解（不是拆除导致）：**
- URL：`http://m701.music.126.net/20261109232918/…mp3?…`（网易云 CDN 音频地址）。
- 证据：同一宿主、同一曲目（“结尾曲-友谊地久天长(Live)”）在同一运行内真实播放成功
  （`paused=false`、ct 5.72 前进、`duration=416.92`）；失败的是该 URL 的另一次拉取
  （VIP 尝试复用同一音频源时段）。拆除只删了汽水文件与两行引入，未动任何网易云播放
  代码；且树上已无任何汽水代码可触发请求。定性：网易云 CDN 侧偶发拉取失败，环境性，
  与拆除无关。

### 4. `scripts/verify-phase4b.py`（全量）— ⚠️ 60/61，唯一失败为预期后果

| 项 | 实测 | 基线对照 |
|---|---|---|
| exit 码 | **1** | 基线（拆除前）exit 0、61/61；本次 exit 1 仅因下述唯一失败 |
| 检查 | **60 PASS / 1 FAIL** | 基线 61/61 |
| console 错误 | **0** | 基线 0 |
| page 错误 | **0** | 基线 0 |
| 失败请求 | **0** | 基线 0 |
| 唯一失败 | `load.phase3_phase4a_present :: {"phase3": true, "phase4a": false}`（`scripts/verify-phase4b.py:150-151`，要求 `window.starwavePhase4a` 存在） | **预期后果**：`starwave-phase4a-qishui.js` 已按 Ma 22:45 决定移除，`window.starwavePhase4a` 本应不存在。脚本未改、代码未恢复；该检查在干净树上必然失败，不代表任何功能损坏 |
| A 规则 AI DJ | 生成 6 首，串词“午后好天气，适合慵懒一点的旋律。”，`by='规则生成，非大模型'`，时段 afternoon、心情“慵懒”；播放 `paused=false, ct=2.91, dur=209.25`；队列 6 首 | 基线一致（6 首、同一串词、ct 1.37→本次 2.91 均为前进中采样） |
| B 混合推荐 | 平台推荐 34 首（`platformReason=''`），混合后 20 首，可播优先前 3 首全可播 | 基线一致（34/20/[true,true,true]） |
| C 音乐报告 | 日/周/月/年 `totalPlays` 均为 1（樱花，`listenMs=5160`）；分享卡 1080×1350；导出/清空验证通过 | 基线一致（`listenMs=4905`→本次 5160，均为真实播放计时，正常波动） |
| D 主题包 | 5 套名字无禁用词；accent 逐个一致（`#7dd3fc/#fbbf24/#2dd4bf/#e879f9/#4ade80`）；非法主题被拒；导入成功；封面取色 `swatch_fallback` | 基线一致 |
| E 粒子/场景/镜头 | 4 种粒子（星尘 140/雨 220/雪 160/萤火 70）、3 场景映射全过；播放中 Kick 0.56–0.75、频谱 0.47/0.45/0.03；段落“前奏”；总督 eco | 基线一致 |
| F 宠物/DualTheme | 团团↔方方切换、开关、画布 180×110；外来 DualTheme 格式被拒、本站格式应用成功 | 基线一致 |
| G 移动端 | 外部字体 0；手势 `cam='off'`；PWA 桌面端；390×844 竖屏 `portrait=true`、歌单架 `side`；双击喜欢 0→1；长按菜单弹出；摇一摇/陀螺仪开关正常 | 基线一致 |
| H 引用更新 | phase2.js 含新地址、无旧地址；About 链接 `https://github.com/Wengzikang/mineradio-next` | 基线一致 |
| 轻量回归 | Phase 3 演示曲 6 首（首曲樱花）；`window.starwaveSpotify` 存在 | 基线一致 |
| 中继 CONNECT | 12 条，0 汽水相关 | — |

## 二、零汽水请求断言（四次运行合计）

| 运行 | 中继 CONNECT 总数 | 发往 `*qishui*` / `*douyin*` / `*douyinvod*` | 备注 |
|---|---|---|---|
| Phase 1 | 22 | **0** | 宿主：api-enhanced、Audius、iTunes、music.126.net 等 |
| Phase 2 | 64 | **0** | 含 accounts.spotify.com 2 条（drain 假 code 测试） |
| Phase 3 | 32 | **0** | 宿主：api-enhanced、music.126.net、itunes 等 |
| Phase 4B 全量 | 12 | **0** | — |
| **合计** | **130** | **0** | ✅ 断言通过 |

统计方法：每次运行前记录 `/tmp/sw-relay.log` 行号，运行后取增量，grep
`qishui|douyin|douyinvod`（大小写不敏感）。中继是 Chromium 唯一的外网出口
（`proxy=127.0.0.1:18082`，`bypass=localhost,127.0.0.1`），本地请求不经过中继，
但汽水/qishui/douyin 宿主均为外网宿主，必经中继；另四份运行日志的
`failed_requests` / `console_errors` 中也无任何汽水宿主。另：`index.html` 内
29 行基线 `qishui-import` 残留桩在四次运行中未触发任何请求（与拆除记录一致：
需已删除的 Connector 扩展才能触发）。

## 三、拆除导致的变化清单（预期后果，非回归）

1. **`window.starwavePhase4a` 不存在** → `verify-phase4b.py` 的
   `load.phase3_phase4a_present` 检查失败（phase3=true、phase4a=false），Phase 4B
   全量 60/61、exit 1。**这是拆除本身，脚本未改、代码未恢复。** 除此之外 Phase 4B
   全部功能检查均通过。
2. **`window.starwaveQishui` 不存在** → `verify-phase3.py` 回归项 (9) 的
   `qishui_untouched` 字段返回 `"n/a"`（原为 `"module-present"`）。该字段是信息性
   记录，不参与 pass/fail；Phase 3 exit 仍为 0。
3. **Phase 2 secret 扫描 0 命中**（拆除前唯一命中是已删 `starwave-qishui.js` 内的
   `spade_a` 字串）。这是移除的正面效果。
4. **其余无变化**：About 页音源行已去汽水（拆除时改），其余功能数字均与基线一致。

## 四、未跑完的项

**无。** 四项全部跑完；验证运行未被拒绝，无需动用重试授权。

## 五、新发现的失败（非拆除导致）

| # | 现象 | 是否拆除导致 | 证据 |
|---|---|---|---|
| 1 | Phase 3：1 条失败请求（`m701.music.126.net` 网易云音频 URL） | 否 | 同一宿主同一曲目在同一次运行内真实播放成功（ct 5.72 前进）；拆除未动网易云代码；树上无汽水代码可触发请求。网易云 CDN 偶发拉取失败 |
| 2 | Phase 2：2 条本地 404（`GET /api/update/latest`） | 否 | 应用自带更新检查向静态服务器请求不存在的路径，既有行为；汽水代码从未提供该接口 |
| 3 | Phase 2：Audius 封面图 2 条 ORB 拦截 | 否 | Phase 3 报告已记录为“Phase 3 之前已存在” |
| 4 | Phase 1 本次 console/失败请求为 0（快照为 4/2） | 否（变好） | api-enhanced CORS 回显夹具产物是间歇性的，本次未出现 |

## 六、收尾确认

- 验证员自起的 4173 静态服务器已停（PID 9938 已 kill，端口 4173 已关闭）。
- 无任何后端在运行：qishui 后端 3300 无响应（从未部署，本次亦未启动）；无其他
  后端进程。4174 Range 服务器（PID 5439）与 18082 中继（PID 5434）为**上一轮遗留
  进程，非本次启动**，按任务要求未动（结束时只停自己起的进程）。
- 构建仍通过：`npm run build:web` → `Built web assets: web/dist`。
- 运行日志：`/tmp/sw-phase1-verify-report.json`、`/tmp/sw-phase2-verify-report.json`、
  `/tmp/sw-phase3-verify-report.json`、`/tmp/sw-phase4b-verify-report.json`；
  各次运行 stdout：`/tmp/sw-phase2-run.log`、`/tmp/sw-phase3-run.log`、
  `/tmp/sw-phase4b-run.log`（Phase 1 输出见本次会话记录）。
