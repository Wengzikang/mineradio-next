# MINERADIO NEXT Phase 5 报告 — 上线（推送 + GitHub Pages）

- 日期：2026-11-09（CST，约 23:20–23:35）
- 执行人：协调员（本人）
- 阶段定义：Phase 0 / 0.5 报告中没有 Phase 5/6/7 的定义；本次采用的映射为
  Phase 5 = 上线（推送代码 + 发布 Pages）、Phase 6 = 线上验证、Phase 7 = 最终交付。
  该映射是协调员的执行约定，不是 Phase 0/0.5 报告原文。
- 范围：只动 `~/workspace/mineradio-next/`；未碰 Folia、AURORA、CINEMA ONE、NEON MUSIC
  和其他项目。未部署任何后端（qishui-api 后端已取消，Oracle 机器不动）。

## 一、结论

- **代码已推送，站点已上线。**
- 仓库：https://github.com/Wengzikang/mineradio-next （公开，GPL-3.0，main 分支）
- 线上地址：**https://wengzikang.github.io/mineradio-next/**
- Pages 构建状态 built；curl 验证 HTTP 200、1,481,555 字节、`<title>StarWave</title>`，
  4 个 JS 模块全 200，0 个汽水脚本引用。

## 二、提交记录

| 提交 | 内容 |
|---|---|
| `366563b` | StarWave v1.0 — Phase 1–4，Soda 已移除；67 个文件，39,668 行新增 |
| `ba59931` | Merge GitHub initial commit（GPL-3.0 LICENSE） |
| `1a3cbea` | Deploy via classic Pages (/docs)：见 §三；28 个文件变动 |

- 远端初始提交 `26ecb3b`（gh 建库时带 `--license gpl-3.0` 生成）只含一个 LICENSE 文件。
  本地 LICENSE（28,529 字节）在 "END OF TERMS AND CONDITIONS" 处结束，缺 "How to Apply
  These Terms" 附录；合并时取用了远端 GitHub 模板完整版（35,149 字节），GPL 合规更完整。
- git 身份为本仓库本地配置：Wengzikang <elio858@qq.com>（未改全局配置）。
- `__pycache__/`、`*.pyc` 补进 `.gitignore`，已删 `scripts/__pycache__/`。
- 推送前密钥扫描：无真实凭据命中（仅 verify-phase2.py 自身的扫描正则字面量与
  PHASE4B 报告里“未做 X”的叙述句）。

## 三、推送被拒与部署方式变更（唯一波折）

首次推送被 GitHub 拒绝：

```
! [remote rejected] main -> main (refusing to allow an OAuth App to create or update
  workflow `.github/workflows/pages.yml` without `workflow` scope)
```

原因：`gh auth status` 显示当前 token 的 scope 只有 `gist`、`read:org`、`repo`，
**没有 `workflow` scope**，GitHub 不允许该 OAuth App token 创建/更新 workflow 文件。
本地提交与合并本身均成功，只有推送失败。

处理（按 Ma“快一点、继续推进能上线的部分”执行，未停下等授权）：

1. 放弃 Actions 模式，改用 **GitHub Pages 经典模式（main 分支 `/docs` 目录）**：
   `docs/` 是 `web/dist/` 的逐字节拷贝——`scripts/build-web.js` 是纯拷贝
   （`diff -r web/dist web/public` 无差异），所以经典模式发布的内容与 workflow
   本应发布的内容完全一致。
2. `.github/workflows/pages.yml` 从仓库移出（`git rm`，见提交 `1a3cbea`），
   内容可从 git 历史恢复：`git show 366563b:.github/workflows/pages.yml`。
3. `README.md` “部署”一节已更新为经典模式的操作说明（改 `web/public/` 后
   `npm run build:web` → 同步到 `docs/` → 提交推送）。
4. 恢复 Actions 模式的路径（留待以后，见 §六）：`gh auth refresh -s workflow`
   补齐 scope 后，恢复 pages.yml 并把 Pages 源切回 Actions。

## 四、Pages 启用与构建

- 启用：`gh api -X POST repos/Wengzikang/mineradio-next/pages`
  `-f source[branch]=main -f source[path]=/docs`
  → `html_url: https://wengzikang.github.io/mineradio-next/`，
  `build_type: legacy`，`source: main:/docs`，`https_enforced: true`。
- 首次构建：commit `1a3cbea`，`created 2026-11-09T15:16:42Z`，状态 `building` → `built`，
  无错误。构建期间前 12 次 curl 均为 404（GitHub Pages "Site not found" 页），
  构建完成后即 200——404 只是构建未完成，不是配置错误。

## 五、线上 curl 验证（构建完成后）

| 检查 | 结果 |
|---|---|
| 首页 HTTP 状态 / 大小 | 200 / 1,481,555 字节 |
| `<title>` | `StarWave` |
| 脚本引用 | starwave-netease.js、starwave-phase2.js、starwave-phase3.js、starwave-phase4b.js 各 1 次 |
| 汽水脚本引用（starwave-qishui / starwave-phase4a-qishui） | 0 |
| 关键资产 | starwave-phase2.js、starwave-phase3.js、starwave-phase4b.js、starwave-netease.js、manifest.webmanifest、demo/sakura.mp3、demo/sakura.lrc、vendor/three.r128.min.js —— 8/8 均为 200 |

## 六、剩余事项

1. **Phase 6 线上浏览器验证进行中**（已派工）：桌面 1280×800 + 手机 390×844，
   真实播放链路、搜索、DJ、推荐、零汽水请求断言；报告 `LIVE_VERIFY_REPORT.md`。
2. **恢复 Actions 模式（可选，非阻塞）**：需 `gh auth refresh -s workflow`
   （浏览器授权流程，由父代理或 Ma 在浏览器里完成）；完成后恢复 pages.yml、
   把 Pages 源切回 Actions。经典模式目前工作正常，不急。
3. **Ma 需在 Spotify Dashboard 注册新 redirect URI**
   `https://wengzikang.github.io/mineradio-next/`（Phase 4B 已改代码，Dashboard
   操作是 Ma 的；未注册前 Spotify 登录会失败，这是已知待办，不是 bug）。
4. 汽水已移除（Ma 2026-11-09 22:45）：本次推送的树不含任何汽水代码；
   `index.html` 内 29 行基线 `qishui-import` 残留桩仍在（见 PHASE4A 报告 §十二，
   需已删除的 Connector 扩展才能触发；干净树验证四次运行 0 汽水请求）。

## 七、收尾确认

- 本地 main 与远端 main 一致（`1a3cbea`，`branch 'main' set up to track 'origin/main'`）。
- 无后端在运行；qishui 后端从未部署，本次亦未启动。
- `npm run build:web` 通过；`docs/` 与 `web/dist/` 一致。
