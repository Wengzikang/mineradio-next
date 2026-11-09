# 星澜音乐 StarWave

> 工作名“星澜音乐 / StarWave”为占位名，可随时改名（见 `web/public/index.html` 顶部的 `STARWAVE_BRAND` 配置常量与本 README 末尾）。

StarWave 是一个本地优先的视觉音乐播放器（纯静态网站，无后端、无账号、无 Cookie 收集）。

- **本地音乐**：导入本地音频文件（file input / 拖放）直接播放。
- **演示曲目**：内置 6 首公有领域 / CC 授权曲目（`web/public/demo/`，均标注“演示”），打开即播。
- **网易云搜索**：通过公开 API 服务直连（与 Folia Web 相同的方式），无登录、无 Cookie、无扩展：
  `https://api-enhanced-pied-rho.vercel.app`（NeteaseCloudMusicApiEnhanced 的公开部署）。
  搜索、歌曲详情、歌词走该服务；播放地址按服务返回结果为准——个别曲目未登录时返回空地址，
  此时页面会明确提示“需登录网易云账号才能播放”，不伪造播放。
- **视觉核心**：粒子歌词、歌词舞台、3D 歌单架、DIY 视觉控制台、节拍分析（均继承自上游 Web 版）。
- **PWA**：可安装到主屏幕，离线缓存核心静态资源（缓存名 `starwave-pwa-v1`）。
- **字体**：全部使用系统字体，无 Google Fonts 等外部字体依赖。

## 来源与许可证

本项目基于 [MrChenyh/Mineradio-Web v0.1.0](https://github.com/MrChenyh/Mineradio-Web)
（其本身基于 [XxHuberrr/Mineradio](https://github.com/XxHuberrr/Mineradio) 的视觉方向）二次开发，
采用 **GPL-3.0** 许可证（见 `LICENSE`）。原作者版权声明见 `NOTICE.md`。

**改名换标说明**：原项目名称、Logo 与原创视觉设计归原作者所有，本项目已改名换标为“星澜音乐 StarWave”，
不使用 Mineradio 字样、MR Logo 或原版品牌元素，也不冒充官方产品。视觉预设的参数值属于代码实现
（GPL-3.0 覆盖），但预设显示名已改写（emily → 星澜封面，安魂 → 星骸）。

**已删除**：桌面专属文件（桌面歌词、壁纸窗口）、全部浏览器扩展代码（含硬编码的酷狗签名密钥与
酷我 secret Cookie，已彻底删除，无残留）、油猴辅助脚本、扩展打包脚本。

## 本地开发

```bash
npm run build:web    # 把 web/public 拷贝到 web/dist
npm run preview:web  # 本地预览
npm run check        # 语法检查
```

## 部署

GitHub Pages（经典模式，从 `main` 分支 `/docs` 目录发布）：改动 `web/public/` 后，
先跑 `npm run build:web`，再把 `web/dist/` 同步到 `docs/`（`rm -rf docs && cp -r web/dist docs`），
提交并推送到 `main`，Pages 随后自动发布。
线上地址：https://wengzikang.github.io/mineradio-next/

注：原 `.github/workflows/pages.yml`（Actions 模式）因当前 gh token 缺少 `workflow` scope
无法推送，已暂时移出仓库（内容见 git 历史 `366563b`）；以后执行 `gh auth refresh -s workflow`
补齐 scope 后，可恢复该文件并把 Pages 切回 Actions 模式。

## 合规与限制（诚实说明）

- 网易云 / QQ / 酷狗等平台接口均为非官方接入，**未获官方授权**；本项目只做搜索与播放地址透传，
  不下载、不转存、不二次分发音频，不绕过会员与付费墙。
- 不内置任何平台账号、Cookie、Token 或 API 密钥；不收集用户数据（见 `PRIVACY.md`）。
- 汽水音乐、Apple Music 官方接入不在 Phase 1 范围内（见 Phase 0 报告 §12）。

## 改名

如需改名：改 `web/public/index.html` 顶部的 `STARWAVE_BRAND` 配置常量与 `manifest.webmanifest`
中的 `name` / `short_name`，重新构建并发布即可。仓库名同步改名需在 GitHub 仓库设置中操作。
