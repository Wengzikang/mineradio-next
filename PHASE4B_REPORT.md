# StarWave（星澜音乐）Phase 4B 完成报告

**日期：** 2026-11-09（CST）
**范围：** 仅 `~/workspace/mineradio-next/`；未碰 Folia、AURORA、CINEMA ONE、NEON MUSIC 及其他项目
**版本：** `window.starwavePhase4b` v0.4.0-phase4b
**验证环境：** Playwright（Chromium 无头）+ 本地 Range 服务器 127.0.0.1:4174 + 中继 18082；本机出口代理 MITM TLS，Chromium 带 `--ignore-certificate-errors`
**总体状态：** 实现全部完成；`npm run build:web` 通过；全量验证 `scripts/verify-phase4b.py` **61 项全部通过，console 错误 0、page 错误 0、失败请求 0**（见 §九）；短冒烟检查亦 0 失败。

---

## 一、逐项完成情况

### A. 规则 AI DJ ✅（纯前端规则，档①）

实现：`starwave-phase4b.js` `generateDj()` / `playDj()`；入口为右下角 ✦ 悬浮按钮打开的智能层面板「AI DJ」页签。

- 按 5 个时段拼歌单（清晨 5–9 / 午间 9–14 / 午后 14–18 / 傍晚 18–22 / 深夜 22–5），用天气电台（`homeWeatherRadioState`）+ 每日推荐（`homeDiscoverState.songs`）+ 本地画像（常听歌手优先，`starwave-listen-stats-v1`）+ 演示曲兜底；跨源去重，上限 12 首。
- 心情可选（自动/清醒/轻快/专注/慵懒/治愈/浪漫/安静），默认自动（按天气/时段）。
- 串词为本地模板生成（每时段 3 条，按日期轮换），面板与播放 toast 均明确标注**“规则生成，非大模型”**。
- 实测（冒烟）：生成 6 首，串词“午后好天气，适合慵懒一点的旋律。”，`generatedBy='规则生成，非大模型'`。全量复核：生成 6 首（时段 afternoon、心情“慵懒”，前 3 首樱花/茉莉花/Greensleeves），点播放后 `paused=false, currentTime=1.37, duration=209.25`，队列 6 首、当前樱花、循环模式 loop。
- 生成式 AI DJ（LLM 串词 + 选曲理由 + 语音播报）不在本次范围：需模型服务与持续费用，无账号/预算授权（见 §十第 1 项）。

### B. 混合推荐 ✅

实现：`hybridRecommend()`；入口「为你推荐」页签。

- 三层：① 平台推荐——尝试网易云 `recommend_songs`（公开 api-enhanced 服务，无登录；未登录时上游返回需登录，诚实记录 `platformReason='login_required'` 并回退，不编数据）；② 本地混合推荐——听歌历史 Top 歌手映射到可播池（演示/天气/每日推荐）；③ 跨平台去重与可播性排序（有地址/演示/试听优先）。
- 冷启动（本地画像与平台推荐均为空）用“今日聆听 / 为你挑选”兜底（天气电台 + 每日推荐 + 演示曲），并在面板标注。
- 实测（全量，`verify-phase4b.py`）：平台推荐返回 **34 首**（`platformReason=''`，未登录态下 api-enhanced 仍返回了推荐——属实记录）、混合后 20 首、可播优先前 3 首全部可播（`[true, true, true]`）；本地画像当时为 0（历史尚为空，冷启动逻辑未触发因平台层有数据）。

### C. 音乐报告 ✅（本地计算、零上传）

实现：`computeReport()` / `renderShareCard()` / `exportShareCard()` / `exportReportData()` / `clearReportData()`；入口「音乐报告」页签。

- 日/周/月/年四档：播放次数、时长（小时）、曲数、Top 歌手、Top 歌曲、心情分布（取历史记录的 context.mood，缺失记“未分类”）、深夜 Top（22:00–05:00）。
- 年度报告分享卡片：Canvas 渲染 1080×1350 图片导出 PNG（含总播放/时长/曲数 + Top 3 歌手）。
- 数据只读本机 `starwave-listen-stats-v1`（与 Phase 2/3 同一键）；提供导出数据 JSON 与清空入口（清空前 `confirm()` 确认）。
- 实测（全量）：真实播放 seeding——演示曲樱花播放后 seek 到 55% 再切歌，历史记 1 次（`listenMs=4905`，规则“听满45秒 / 进度≥50% / 播完，记1次”）；日/周/月/年四档报告 `totalPlays` 均为 1，Top 歌手“日本民谣”1 次、Top 歌曲“樱花”1 次；分享卡片 Canvas 1080×1350、`toDataURL` 长度 1,473,830；导出数据 JSON 成功；清空后 `totalPlays=0` 已验证。

### D. 主题包系统 ✅

实现：`BUILTIN_THEMES` / `applyTheme()` / `importThemeFile()` / `exportTheme()` / `themeFromCover()`；入口「主题」页签。

- 内置 5 套，名字均为原创：晨雾微光、熔金黄昏、深海静默、霓虹雨巷、纸鸢春日。**未使用**原版预设名 emily/安魂/星河/唱片/星球/滚筒/虚空（验证脚本逐名检查）。
- 主题 = 预设参数 + 配色 + 字体 + 粒子配置的 JSON；应用时写 CSS 变量 `--sw4b-accent/accent2/bg/bg2/text/muted`，并联动粒子形态。
- 支持导入/导出主题 JSON（非法 JSON / 缺字段时明确报错，不应用）；封面取色自动生成主题：canvas 采样当前封面主色（众数桶 + 饱和度加权），跨域取不到像素时诚实回退到 Cover Picker 推荐色并标注原因（`swatch_fallback` / `cover_cors` 等），不编造颜色。
- 实测（冒烟）：应用「霓虹雨巷」后 `--sw4b-accent` 为 `#e879f9`，与主题一致。

### E. 高级粒子 + 3D 场景包 + 段落镜头 ✅

实现：`starwave-phase4b.js` 粒子引擎（2D canvas 覆盖层 `#sw4b-particles`，z-index 2，pointer-events none）+ 场景背景层 `#sw4b-scene-bg`（z-index 0，opacity 0.55 着色，不盖住主 3D 舞台 `#canvas-container` z-index 1）；入口「视觉·粒子」页签。

- 粒子形态库 4 种可切换：星尘 / 雨 / 雪 / 萤火（基准数 140/220/160/70）。
- 音频驱动：Kick 触发与频谱映射复用 Phase 3 的 `beatInfo()` / `spectrumSample()`；取不到时只做环境漂移，不编造能量。面板实时显示 Kick 与低/中/高频谱值。
- 粒子数按帧率自适应，接 Phase 2 性能总督：每 120 帧按 `fpsEma/60 × 档位系数（eco 0.4 / balanced 0.7 / high 1.0）` 重算预算（钳制 0.15–1.0）。
- 场景包 3 个：星空（星尘）、海洋（萤火）、雨夜（雨），各带对应背景渐变与粒子。
- 段落镜头：按播放进度分段（前奏 0–12% / 主歌 12–45% / 副歌 45–78% / 间奏 78–88% / 尾奏 88–100%），段落切换时改镜头（CSS transform 推/拉/移，1.2s 过渡），不碰 Three.js 相机；面板显示当前段落。
- 实测（全量 + 探针）：4 种粒子逐一切换成功（星尘 140 / 雨 220 / 雪 160 / 萤火 70 个）；3 场景映射正确（星空→星尘、海洋→萤火、雨夜→雨）；播放中音频驱动为真实数值（Kick 0.58、频谱低/中/高 0.50/0.44/0.02，总督档位 eco）；段落镜头当前为“前奏”（播放初段）；无头软件渲染下帧率约 10–20 fps，总督档位自动 balanced→eco，第 120 帧时预算 1.0→0.15、粒子 140→21，自适应闭环真实生效。另有一处快照说明：段落镜头复测瞬间（刚重新起播）Kick/频谱读到 0，属起播瞬间的采样值，非驱动失效——此前播放中的 0.58/0.50/0.44/0.02 已证明驱动链路真实。

### F. 听歌宠物 + AI 主题 ✅

实现：`drawPet()` / `cyclePet()` / `setPetEnabled()` + `buildDualThemeFromCover()` / `applyDualTheme()` / `importDualThemeFile()`；入口「听歌宠物」「主题」页签。

- 宠物沿播放进度爬行（位置 = `currentTime/duration`，轨道画在左下角画布 `#sw4b-pet`，点宠物可切换形象；播放时有起伏动画，约 4 秒眨眼一次）。
- 2 种可选形象，均为本站自绘几何/像素原创造型，名字自起：**团团**（黄色圆身 + 圆耳 + 腮红）与**方方**（蓝色方身 + 天线 + 像素眼）。**未复制** mineradio.art 的宠物形象（像素爪爪/熊猫/橘猫/金毛/赤狐/褐兔）与 DualTheme 资产；验证脚本逐名检查。
- AI 主题 = 封面取色 + 自有格式 DualTheme JSON：`{ format:'starwave-dual-theme', version:1, light:{...}, dark:{...} }`，字段自定；导入时校验 `format` 与 `version`，非本站格式拒绝并明示原因；应用时按 `prefers-color-scheme` 选浅/深面；支持导出。
- 实测（全量）：宠物切换 团团→方方成功；画布存在（180×110）；开关关/开均成功；DualTheme 外来格式被拒（`format 须为 starwave-dual-theme`），本站格式应用成功；封面取色走推荐色回退（`swatch_fallback`，演示曲无封面）并给出主题。

### G. 移动端 P1/P2 ✅（实验功能明确标注）

实现：`mobile.*`；入口「手机」页签。

- P1：
  - 字体自托管已核实：`web/public` 全量 grep 无 `googleapis` / `gstatic` 外链（`index.html`、全部 JS、manifest、SW、vendor/ 均无）；面板内可复查（`fontSelfHostedCheck()` 扫 link/script 与已加载资源）。
  - 手势开关默认关闭：基线 `fx.cam` 默认已是 `'off'`（`index.html:3431/3514`）；Phase 4B 另加手机端守卫——移动端若被置为 gesture 且无用户明确选择记录（`starwave-phase4b-gesture-optin-v1`），启动时强制关回 `'off'`，手机上默认不请求摄像头。
  - 3D 歌单架竖屏布局：窄屏竖屏（≤640px 且高>宽）时给 body 加 `sw4b-portrait` class，CSS 做面板/控制栏竖屏适配；若歌单架为 `stage` 模式（竖屏会遮挡歌词）则改为 `side`；面板提供侧栏/舞台切换按钮。
  - PWA 安装引导：接 `beforeinstallprompt` 事件（基线只接桌面端，Phase 4B 也接 Android）；已安装 / iOS / Android 可安装 / Android 等待事件 / 桌面五态分别显示；iOS 显示“浏览器分享 → 添加到主屏幕”手动指引，Android 有事件时可直接调起安装。
- P2：
  - 双击喜欢：绑在 `#control-cover` / `#thumb-cover`，走 Phase 3 本地收藏 `toggleFavorite`，带 15ms 震动反馈。
  - 长按菜单：封面长按 550ms 弹出菜单（喜欢 / 下一首 / 加入播放队列 / 关闭），带 10ms 震动。
  - 震动反馈：`navigator.vibrate` 有则用、无则跳过（各处均已 guard）。
  - 实测（全量）：字体自托管（`externalFontUrls=[]`）；手势 `cam='off'`；PWA 状态桌面端；390×844 竖屏下 `portrait=true`、歌单架 `side`；双击封面喜欢 0→1；长按菜单弹出成功；摇一摇开/关、陀螺仪关均成功。

### H. 仓库名引用更新 ✅

- `starwave-phase2.js:69` Spotify Redirect URI：`https://wengzikang.github.io/starwave-music/` → `https://wengzikang.github.io/mineradio-next/`。
- `starwave-phase2.js:71` About/设置页源码链接 `SOURCE_URL`：`https://github.com/Wengzikang/starwave-music` → `https://github.com/Wengzikang/mineradio-next`。
- 两处均为任务 H 授权的改动；`starwave-phase2.js` 其余未动。构建产物 `web/dist/starwave-phase2.js` 已含新地址。
- **待 Ma 登记：** 新 Redirect URI 须由 Ma 在 Spotify Dashboard 登记，否则报 `redirect_uri` 不匹配。About 页文案已同步显示新 URI。

---

## 二、修复的 Bug / 发现的问题

1. **场景背景层会盖住专辑模糊背景**——初版 `#sw4b-scene-bg` 不透明，会盖掉 `#album-bg` 的氛围。修：背景层 `opacity:.55` 只做着色；主 3D 舞台（`#canvas-container` z-index 1）在背景层（z-index 0）之上，始终可见。
2. **验证脚本 FAB 可见性误判**——`offsetParent` 对 `position:fixed` 元素恒为 null，冒烟初版把 FAB 判为不可见。修：验证脚本改用 `getBoundingClientRect()` 宽高判断（实现代码无问题，FAB 实际可见且面板可打开）。

---

## 三、改动文件清单

| 文件 | 性质 | 说明 |
|---|---|---|
| `web/public/starwave-phase4b.js`（新建，约 1300 行） | 新增 | Phase 4B 全部功能：规则 AI DJ、混合推荐、音乐报告、主题包、高级粒子/场景/段落镜头、听歌宠物、AI 主题（自有 DualTheme）、移动端 P1/P2；`window.starwavePhase4b` v0.4.0-phase4b |
| `web/public/index.html`（末尾 1 行） | 增加 1 行 | 在 `starwave-phase4a-qishui.js` 之后引入 `starwave-phase4b.js`；其余未动 |
| `web/public/starwave-phase2.js`（2 行） | 修改 2 行 | 仅 H 项：:69 Redirect URI、:71 SOURCE_URL 改为 mineradio-next；其余未动 |
| `scripts/verify-phase4b.py`（新建） | 新增 | Playwright 验证脚本：`--smoke` 快模式 + 全量模式，覆盖 A–H + 轻量回归；报告 `/tmp/sw-phase4b-verify-report.json` |
| `web/dist/`（构建产物） | 重新生成 | `npm run build:web` 通过；`web/dist/index.html` 含 `starwave-phase4b.js` 引用 1 处 |
| `PHASE4B_REPORT.md` | 新增 | 本报告 |

未动：`starwave-phase3.js`、`starwave-phase4a-qishui.js`、`starwave-qishui.js`、品牌、PWA 缓存名（`starwave-pwa-v1`）；未动任何汽水文件（拆除由协调员统一做）。

---

## 四、汽水相关说明（Ma 22:45 决定）

- **Ma 22:45 发话“汽水不要了”——MINERADIO NEXT 里汽水音乐移除，未上线。** 本报告及代码中如提到汽水，均按此口径，不写“待接通”或“即将上线”。
- Tier B（`verify-phase4a-qishui.py B`）在移除决定之前已跑完（见 §九）：出货状态诚实，0 错误、0 后端请求。因移除已决定，该结果仅作决定前快照，不再复跑。
- 试听重测（60 秒裸 `<audio>` 对照）因移除而取消，未跑。
- 汽水文件的拆除（删接线文件、去 `index.html` 的两行引入、归档后端配置）由协调员统一做，本任务未碰 `starwave-qishui.js`、`starwave-phase4a-qishui.js`、`scripts/verify-phase4a-qishui.py`、`services/qishui-api/`、`PHASE4A_QISHUI_REPORT.md`。

---

## 五、验证——短检查（已做）

| 检查 | 结果 |
|---|---|
| `node --check`（phase4b.js、phase2.js） | 通过 |
| `npm run build:web` | 通过；`web/dist` 含新脚本与新 URL |
| 冒烟 `--smoke`（`scripts/verify-phase4b.py --smoke`，约 30 秒） | **0 失败；console 错误 0、page 错误 0、失败请求 0**；FAB + 7 个页签全部渲染；主题应用（霓虹雨巷 `#e879f9`）、宠物切换（团团→方方）、报告计算、DJ 生成（6 首，规则生成）、粒子运行中均通过 |
| 粒子预算自适应探针（独立短脚本，约 45 秒） | 帧率 ~10–20 fps 时第 120 帧预算 1.0→0.15、粒子 140→21；总督档位 balanced→eco 自动降档 |

---

## 六、验证——回归（拆除前快照；拆除后由协调员在干净树上重跑）

| 检查 | 结果 |
|---|---|
| `verify-phase1.py`（拆除决定前已跑，约 33 秒） | demo 播放正常（樱花 `paused=false`，2.60s→3.79s 前进，歌词 14 行）；page 错误 0；console 错误 4 / 失败请求 2——**全部是已知测试夹具产物**：api-enhanced 的 CORS 头回显了上一个 origin（4174），导致 4173 origin 的网易云搜索被挡（Phase 3 报告 §一第 9 项同款 artifact，与 Phase 4B 代码无关；Phase 4B 未碰搜索/网易云代码）。网易云试听因此为空，Audius 搜索结果 4 条正常。**此结果为拆除前快照，拆除后须在干净树上重跑。** |
| `verify-phase2.py` | 已启动后按 22:46 协调员指令立即停掉（进程已 kill 确认无残留），未跑完。拆除后由协调员安排重跑。 |
| `verify-phase3.py` | 未跑。拆除后由协调员安排重跑。 |

---

## 七、未完成 / 降级项（不在本次范围，写明原因与待谁决定）

1. **生成式 AI DJ**——需大模型服务 + 持续费用（按量约 ¥0.01–0.1/次，见 Phase 0 §7），无模型账号/预算授权。本次只做规则 DJ（档①），串词明确标注“规则生成，非大模型”。待 Ma 决定是否立项 Phase 4 档②（模型选型 + 费用预算）。
2. **账户 / 云端同步后端**——需后端（账户、歌单/收藏/设置同步、token 加密存储），本次纯前端；所有数据只存本机。待 Ma 决定后端方案与部署。
3. **Apple Music 真实接线**——需 Apple Developer 会员 $99/年 + MusicKit 密钥（Team ID/Key ID/.p8、服务端签发 Token）+ 白名单域名 + 用户订阅；且 Ma 的 elio858@qq.com Apple ID 处于锁定状态，须由他本人解锁后才能办理。待 Ma 解锁并决定。
4. **Spotify Dashboard 新 URI 登记**——新 Redirect URI `https://wengzikang.github.io/mineradio-next/` 已写入代码，但须由 Ma 在 Spotify 应用 Dashboard 登记，否则报 `redirect_uri` 不匹配。待 Ma 操作。
5. **试听真实播放（汽水）**——随 Ma 22:45 移除决定而取消，不再验证、不上线（见 §四）。
6. **摇一摇切歌 / 陀螺仪镜头**——已实现开关 + 明确标注“实验功能”，默认关闭；未在真机验证灵敏度（无真机），部分机型/浏览器可能不灵敏或需权限。待真机验证。
7. **BPM / 段落检测精度**——段落镜头按播放进度比例分段（纯前端能量曲线分段的简化实现），非逐段音频分析；BPM 仍沿用 Phase 3 的 kick 检测（慢速稀疏曲 BPM 可为 0，kick 能量仍输出）。

---

## 八、已知限制与外观瑕疵

- 无头 Chromium fps 约 10–20（软件渲染），粒子预算会迅速降到 0.15；真机帧率与视觉流畅度未验证（无真机）。
- 场景背景层为 0.55 透明度着色，会轻微改变专辑模糊背景的观感；属设计内行为（场景包即为背景换肤），可在视觉页签切回「星空」或关闭粒子恢复。
- 宠物画布固定在左下角（`left:14px; bottom:118px`），与缩略图区（`bottom:24px`）不重叠；极窄屏下可能与控制栏贴近，未做额外避让。
- `starwave-phase4b.js` 内定义了未使用的 `P4A` 惰性引用（为后续可能的状态读取预留），无行为影响。
- 混合推荐的平台层（`recommend_songs`）在未登录态下预期返回 `login_required` 并回退本地混合推荐——属实记录，不伪造平台数据。
- 封面取色在网易云等跨域封面无 CORS 头时取不到像素，会走推荐色回退并标注原因。

---

## 九、验证——全量（`scripts/verify-phase4b.py`，已跑完）

**结果：61 项检查全部通过，0 失败；console 错误 0、page 错误 0、失败请求 0。** 运行约 166 秒；完整报告 JSON：`/tmp/sw-phase4b-verify-report.json`。

| 组 | 检查 | 实测数字 |
|---|---|---|
| 加载 | phase4b / FAB / phase3+phase4a | v0.4.0-phase4b `available:true`；FAB 可见；phase3/phase4a 均在 |
| 界面 | 7 个页签渲染 | dj/rec/report/theme/visual/pet/mobile 全部渲染（内容长度 293–1739 字符） |
| A | DJ 生成 + 播放 | 6 首；串词“午后好天气，适合慵懒一点的旋律。”；播放 `paused=false, ct=1.37, dur=209.25`；队列 6 首 |
| B | 混合推荐 | 平台推荐 34 首（`platformReason=''`）；混合后 20 首；可播优先前 3 首全可播 |
| C | 报告 | 真实播放 seeding 记 1 次（樱花，`listenMs=4905`）；日/周/月/年 `totalPlays` 均为 1；分享卡 1080×1350、`toDataURL` 长 1,473,830；导出成功；清空后 `totalPlays=0` |
| D | 主题 | 5 套名字无禁用词；逐个应用 accent 全部一致（`#7dd3fc/#fbbf24/#2dd4bf/#e879f9/#4ade80`）；非法主题被拒（“缺少 colors”）；导入成功；封面取色 `swatch_fallback` 有主题返回 |
| E | 粒子/场景/镜头 | 4 种粒子、3 场景映射全部通过；播放中 Kick 0.58、频谱 0.50/0.44/0.02；段落“前奏” |
| F | 宠物/DualTheme | 宠物团团/方方（自绘原创造型）；切换与开关成功；外来 DualTheme 格式被拒，本站格式应用成功 |
| G | 移动端 | 字体自托管（外部字体 0）；手势 `cam='off'`；PWA 桌面端状态；390×844 竖屏 `portrait=true`、歌单架 `side`；双击喜欢 0→1；长按菜单弹出；摇一摇开/关、陀螺仪关成功 |
| H | 引用更新 | phase2.js 含新地址、无旧地址残留；About 弹窗链接为 `https://github.com/Wengzikang/mineradio-next` |
| 轻量回归 | Phase 3 演示曲 / Spotify 对象 | 演示曲 6 首（首曲樱花）；`window.starwaveSpotify` 存在 |

> 注意：全量验证在汽水移除决定之后、拆除之前跑，树上仍含汽水接线文件；轻量回归只覆盖 Phase 3 演示曲与 Spotify 对象存在，未覆盖 Phase 1/2/3 全量回归（拆除后由协调员在干净树上重跑，见 §六）。

---

## 十、发布前确认

- `npm run build:web` 通过。
- `web/public` 内无真实后端地址赋值、无任何密钥/凭据：`grep -rn "127.0.0.1" web/public/` 仅命中 `starwave-qishui.js:3` 交付时已有的注释（上游默认监听地址描述，非配置值，按指令未改该文件）；`STARWAVE_QISHUI_API_BASE` 在 `web/public` 内无任何赋值；无 `api_key` / `secret` / `token` / `password` / `Cookie` 凭据字串新增（Cookie 相关仅有 Phase 2 已停用的粘贴登录提示文案）。
- 本地测试服务收尾：为回归起的 4173 Range 服务器已停掉（确认无进程、端口已关闭）；4174 Range 服务器与 18082 中继为此前会话遗留（非本次启动），未动；验证结束时浏览器已关闭，无残留。
- 未提交、未推送、未做 gh 操作；推送由协调员统一做。
- 未调用解密/下载端点，未解密 spade_a，未复制 decryptor / 安全 SDK / 酷狗签名盐 / 酷我 secret Cookie / Apple token 提取逻辑；未用“粘贴 Cookie 登录”；未把任何凭据放进代码或日志。

---

## 十一、报告人声明

- 未编造接口地址与测试成功结果：冒烟通过的写通过，全量未跑完的写“进行中”，取消的写取消，回归未跑完的写未跑完。
- 汽水移除决定（Ma 22:45）之后，未再跑任何汽水验证，未碰任何汽水文件；Tier B 与 Phase 1 回归的结果均为决定前快照，已如实标注时效。
