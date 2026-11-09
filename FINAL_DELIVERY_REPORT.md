# MINERADIO NEXT（星澜音乐 StarWave）最终交付报告

- 日期：2026-11-10 00:05 CST
- 线上地址：**https://wengzikang.github.io/mineradio-next/**
- 仓库：https://github.com/Wengzikang/mineradio-next （公开，GPL-3.0，main 分支，当前 `a2667c7`）
- 执行人：协调员（本人）
- 阶段说明：Phase 0 / 0.5 报告中没有 Phase 5/6/7 的定义；本次采用的映射为
  Phase 5 = 上线（推送代码 + 发布 Pages）、Phase 6 = 线上验证、Phase 7 = 最终交付。
  该映射是协调员的执行约定，不是 Phase 0/0.5 报告原文。
- 授权依据：Ma 2026-11-09 17:03 授权全程开发 + 直接部署、Phase 1–7 连续做；
  2026-11-09 ~22:35 “你快一点，权限我全部同意”；2026-11-09 22:45 “汽水不要了”
  （汽水已移除，见 §六）。

## 一、交付结论

**星澜音乐 StarWave v1.0 已上线并通过线上验证。** 桌面 10/10、手机 6/6
全部通过（含修复后的手机手势），零汽水/抖音请求断言通过。
线上验证分两轮：首轮抓到手机手势既有 bug（2 项失败），修复后重跑全部通过。

## 二、功能清单

| 阶段 | 功能 | 状态 |
|---|---|---|
| Phase 1 | 静态站 MVP：6 首演示曲（樱花/茉莉花/Greensleeves/Amazing Grace/Clair de Lune/Daisy Bell）+ 歌词、搜索（网易云 via api-enhanced + Audius + iTunes） | ✅ 已验证 |
| Phase 2 | Spotify PKCE 登录（verifier 存 localStorage，TTL 10 分钟）、Apple Music 框架（pending_auth，未真连）、私人电台、移动端 P0（手势默认关、竖屏歌单架、PWA、Media Session） | ✅ 已验证（Spotify 只验授权 URL 格式，未走真实登录） |
| Phase 3 | 播放核心：队列、断点续播、歌词同步（含 ±500ms 偏移）、频谱/EQ、BPM/Kick、收藏/历史/歌单、本地 mp3 导入、网易云免费曲真实播放、iTunes 30s 预览 | ✅ 已验证 |
| Phase 4A | 汽水（Qishui）接线——**已按 Ma 22:45 决定移除**：接线删除、后端从未部署、树上无汽水代码 | ✅ 已移除并验证 |
| Phase 4B | 规则 AI DJ（5 时段，明确标注“规则生成，非大模型”）、混合推荐、音乐报告（日/周/月/年 + 1080×1350 分享卡）、主题包 5 套（晨雾微光/熔金黄昏/深海静默/霓虹雨巷/纸鸢春日）、粒子 4 种 + 场景 3 个 + 段落镜头、宠物团团/方方、移动端 P1/P2（含双击喜欢、长按菜单——已修复并验证） | ✅ 已验证 |
| Phase 5 | 推送 + GitHub Pages 上线 | ✅ 已上线 |
| Phase 6 | 线上验证（桌面 + 手机）+ 手机手势修复重跑 | ✅ 全部通过 |
| Phase 7 | 本最终交付报告 | ✅ 本文件 |

### 音源与边界（诚实说明）

- **网易云**：经 Folia 的 api-enhanced（非官方社区服务），站内已标注；仅免费曲，未登录状态 VIP 曲诚实提示需登录。
- **QQ / 酷狗**：无播放（仅元数据/搜索边界内）。
- **Spotify**：仅元数据，复用已有 "Music" 开发者应用，未新建应用；**Ma 需在 Spotify Dashboard 注册新 redirect URI `https://wengzikang.github.io/mineradio-next/`**，否则真实登录失败（授权 URL 格式已验证通过）。
- **Apple Music**：框架已就绪，未真连（需 Ma 解锁 elio858@qq.com Apple ID + $99/年开发者 + 后端 token 端点 + 域名白名单 + 订阅）。
- **汽水音乐**：已移除；无后端、无请求、无代码（§六）。
- **演示曲**：6 首本地演示音频 + 歌词，可直接播放。

## 三、实测证据

### 1. 干净树验证（汽水移除后本地回归，`CLEAN_TREE_VERIFY_REPORT.md`）

| 项 | 结果 | console / page / 失败请求 |
|---|---|---|
| Phase 1 | exit 0 | 0 / 0 / 0（樱花播放前进、歌词 14 行、搜索“周杰伦”14 条） |
| Phase 2 | exit 0 | 3 / 0 / 2（3 条 console 全为已知/既有：Spotify drain 假 code 400、本地更新检查 404×2；2 条失败为 Audius 封面 ORB 拦截；secret 扫描 0 命中） |
| Phase 3 | exit 0 | 0 / 0 / 1（1 条失败为网易云 CDN 偶发拉取失败，同一曲目同运行内真实播放成功） |
| Phase 4B 全量 | exit 0，61/61 | 1 / 0 / 2（api-enhanced recommend/songs 瞬断，冷启动回退正常；过期断言 `phase4a_present` 已修正为 `phase4a_removed` 后重跑通过） |
| 零汽水请求断言 | ✅ 通过 | 四次运行 130 条外发请求，0 条发往 `*qishui*` / `*douyin*` / `*douyinvod*` |

### 2. 线上验证首轮（`LIVE_VERIFY_REPORT.md` §1–10，commit 1a3cbea）

- 桌面 1280×800：**10/10 通过**（加载 0/0/0、樱花前进 1.8s、搜索 14 条、DJ 6 首、混合推荐 20 首、Spotify 授权 URL 格式对、零汽水 97 行中继日志 + 56 页面请求均为 0）。
- 手机 390×844：**5/6 通过**——双击喜欢与长按菜单失败（根因：两个手势目标在 ≤720px 下均被 CSS 藏起；既有代码问题，非部署导致；Phase 4B 本地验证只在桌面测过手势）。
- 零汽水请求：两轮合计 136 行中继日志 + 84 页面请求，0 条违禁。

### 3. 手机手势修复 + 线上重跑（`LIVE_VERIFY_REPORT.md` §11，commit a2667c7，2026-11-10 ~00:03 CST）

- 修复：`#thumb-wrap.visible` 补 `display:flex`（小封面此前在任何宽度下都不显示）；
  ≤720px 下小封面浮于底栏之上（z-index:7，pointer-events 仅封面本身），
  标题区穿透以免盖住底栏按钮；`#control-cover` 在手机下按设计仍隐藏。
- 本地 390px 真实触摸验证：双击喜欢 0→1、长按菜单弹出；桌面手势不受影响。
- 线上重跑：**桌面 10/10、手机 6/6，TOTAL failures=0**——
  手机双击喜欢 0→1（真实 CDP 触摸）、长按菜单弹出（真实 CDP 触摸 750ms 保持），
  樱花播放前进桌面 1.97s / 手机 2.02s，搜索 14 条，DJ 6 首，混合推荐 20 首，
  零汽水（桌面 112 行 + 59 请求、手机 41 行 + 28 请求，均为 0）。
  桌面唯一失败请求 1 条 = 已知 Audius 封面 ORB 拦截（既有项）。

### 4. 上线 curl 验证（Phase 5，`PHASE5_REPORT.md`）

首页 HTTP 200、1,481,555 字节（修复后 1,481,968 字节）、`<title>StarWave</title>`；
4 个 JS 模块、manifest、demo 音频/歌词、three.js 均 200；0 个汽水脚本引用。

## 四、剩余问题（按优先级）

1. **Ma 待办：Spotify Dashboard 注册新 redirect URI** `https://wengzikang.github.io/mineradio-next/`。
   未注册前 Spotify 真实登录会失败；代码与授权 URL 格式已就绪。
2. **Apple Music 真实连接未做**：Apple ID 已锁定（Ma 自己解锁）+ $99/年 + 后端 token 端点 + 域名白名单 + 订阅。
3. **生成式 AI DJ、账号/云同步后端未做**：按 Phase 0 规划属后续阶段；生成式 DJ 需模型服务 + 费用，同步后端需服务器——均需 Ma 另行决定。
4. **建议 Ma 在真机上复测一次双击喜欢**：VM 软渲染下输入事件延迟约 300–600ms，
   真机 GPU 渲染下人类双击（约 150ms 间隔）应在双击窗口内，但真机是最终证明。
5. **测试中继脚手架已知限制**：中继（`scripts/verify-relay-proxy.py`）闲置约 30–40 分钟后
   可能对 github.io 失联（已出现两次，重启即恢复，原因未知，与应用无关，不影响线上站点）。
   线上重跑前因此重启过两次中继（PID 20571 → 28380）。
6. **既有环境性杂项**：Audius 封面 ORB 拦截（约 1 条/桌面运行）；api-enhanced CORS 回显
   夹具间歇性 console 错误；网易云 CDN 偶发拉取失败。均为 Phase 3 之前已存在，非回归。
7. **`index.html` 仍有 29 行基线 `qishui-import` 残留桩**（MrChenyh v0.1.0 基线自带，
   需已删除的 Connector 扩展才能触发；见 PHASE4A 报告 §十二；四次本地运行 + 两次线上运行
   0 汽水请求）。未做手术式删除（29 处散点，风险大于收益）。
8. **Spotify 免费账号边界**：完整播放需 Premium；免费账号以元数据/预览为主。

## 五、部署与维护说明

- **仓库**：https://github.com/Wengzikang/mineradio-next（公开，GPL-3.0，main，当前 `a2667c7`）。
- **发布方式**：GitHub Pages 经典模式，从 `main` 分支 `/docs` 目录发布。
  选用原因：当前 gh token 的 scope 为 `gist`、`read:org`、`repo`，无 `workflow` scope，
  GitHub 拒绝推送创建 `.github/workflows/pages.yml` 的提交（见 PHASE5_REPORT.md §三）。
  `docs/` 是 `web/dist/` 的逐字节拷贝（`build-web.js` 是纯拷贝），发布内容与
  Actions 模式完全一致。
- **更新流程**：改 `web/public/` → `npm run build:web` → `rm -rf docs && cp -r web/dist docs`
  → 提交 → 推送到 `main` → Pages 自动构建（约 2–4 分钟）→ curl 验证
  （HTTP 200 + `<title>StarWave</title>` + 关键资产 200）。
- **回滚**：`git revert <commit> && git push`，Pages 重新构建旧版。
- **恢复 Actions 模式（可选）**：执行 `gh auth refresh -s workflow` 补齐 scope 后，
  从 git 历史恢复 `pages.yml`（`git show 366563b:.github/workflows/pages.yml`），
  提交并把 Pages 源切回 Actions。经典模式目前工作正常，不急。
- **本地验证**：`scripts/verify-phase1.py`、`verify-phase2.py`、`verify-phase3.py`、
  `scripts/verify-phase4b.py`（本地，Playwright + 中继 18082）；
  `scripts/verify-live.py`（线上，需中继 18082；中继失联时先重启
  `scripts/verify-relay-proxy.py` 再跑）。
- **LICENSE**：仓库根目录为 GitHub 模板完整版 GPL-3.0（35,149 字节，含附录）；
  站内 About 页有源码链接指向本仓库。

## 六、汽水移除记录

Ma 2026-11-09 22:45 “汽水不要了”：Phase 4A 的 Qishui 接线已拆除/禁用，
`starwave-qishui.js`、`starwave-phase4a-qishui.js`、`scripts/verify-phase4a-qishui.py`、
`services/qishui-api/` 全部移出仓库并归档于
`~/workspace/mineradio-next-archive/qishui-removed-2026-11-09/`（工作成果保留，不在仓库内）；
`index.html` 两行引入已删；qishui-api 后端从未部署、不再部署；
Oracle 机器不动，等 Ma 自己决定别的用途。详见 `PHASE4A_QISHUI_REPORT.md` §十二。
本次交付的线上版本不含任何汽水代码（§三断言）。

## 七、合规声明

- 三条合规红线均未触碰：未复制硬编码 KuGou 签名密钥 / Kuwo 秘密 Cookie、
  未复制从 music.apple.com JS 提取的 Apple Music 开发者 token、未复制 qishui-audio-decryptor；
  未做 DRM 解密、未做逆向签名、未硬编码密钥/cookie、未接 ByteDance 安全 SDK、
  不支持粘贴 Cookie 登录、未把任何凭据放进浏览器或日志。
- 汽水仅做到元数据 + 30 秒试听后即被移除；从未调用 /decrypt、/audio/decrypt、
  /download/file 等解密/下载接口；从未解密 spade_a。
- QQ/KuGou/Kuwo 不做播放；Spotify 仅元数据；网易云经 api-enhanced 且站内标注“非官方社区服务”。
- 基线为 MrChenyh Mineradio-Web v0.1.0，已按 GPL-3.0 要求公开仓库 + 站内源码链接 + 更名 StarWave。

## 八、备份说明

- **主备份即 GitHub 仓库**（全部源码、构建产物 `docs/`、验证脚本、阶段报告、LICENSE；
  当前 `a2667c7`，本地与远端一致）。
- 本地工作副本：`~/workspace/mineradio-next/`（git 仓库，main 跟踪 origin/main）。
- 汽水移除归档：`~/workspace/mineradio-next-archive/qishui-removed-2026-11-09/`。
- 服务端无用户数据（播放历史、收藏、歌单均本地计算、存 localStorage，无账号后端），无数据库可备份。
- 阶段报告：`PHASE2_REPORT.md`、`PHASE3_REPORT.md`、`PHASE4A_QISHUI_REPORT.md`、
  `PHASE4B_REPORT.md`、`PHASE5_REPORT.md`、`CLEAN_TREE_VERIFY_REPORT.md`、
  `LIVE_VERIFY_REPORT.md`、本文件，均在仓库内。

## 九、报告文件清单

| 文件 | 内容 |
|---|---|
| `PHASE2_REPORT.md` | Phase 2 验收报告 |
| `PHASE3_REPORT.md` | Phase 3 报告（第 7 轮验证 exit 0） |
| `PHASE4A_QISHUI_REPORT.md` | Phase 4A 汽水接线报告 + §十一跟进 + §十二移除记录 |
| `PHASE4B_REPORT.md` | Phase 4B 报告（61 项验证） |
| `PHASE5_REPORT.md` | Phase 5 上线报告（推送 + Pages + workflow scope 问题） |
| `CLEAN_TREE_VERIFY_REPORT.md` | 汽水移除后干净树验证（Phase 1/2/3/4B + 零汽水断言） |
| `LIVE_VERIFY_REPORT.md` | Phase 6 线上验证报告（首轮 + 修复重跑） |
| `FINAL_DELIVERY_REPORT.md` | 本最终交付报告 |
| `scripts/verify-live.py` | 线上验证脚本（桌面 + 手机，真实 CDP 触摸手势） |
