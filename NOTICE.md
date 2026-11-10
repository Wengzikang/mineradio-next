# NOTICE

StarWave（星澜音乐）使用了以下第三方项目、库或服务。各项目版权归其原作者所有。

## 第三方库

- Three.js（MIT）
- GSAP
- music-tempo（见 `web/public/vendor/music-tempo.LICENCE`）

## 第三方服务

- iTunes Search API：用于首页试听和试听兜底。
- LRCLIB：用于可直接访问的歌词兜底。
- 网易云音乐公开 API 服务（NeteaseCloudMusicApiEnhanced 的公开部署，
  `https://api-enhanced-pied-rho.vercel.app`）：用于网易云搜索、歌曲详情、歌词与播放地址查询，
  无登录、无 Cookie。本项目不隶属于该服务。
- Open-Meteo：用于天气电台（官方免费 API，无需 key）。

StarWave 不是任何音乐平台的官方客户端，也不隶属于网易云音乐、QQ 音乐、腾讯音乐娱乐、酷狗音乐、
Apple Music 或其它第三方音乐服务。用户应自行遵守对应平台的服务协议、版权规则和会员权益规则。

## 原始设计与致谢

本项目基于 [MrChenyh/Mineradio-Web v0.1.0](https://github.com/MrChenyh/Mineradio-Web) 二次开发，
其本身基于 [XxHuberrr/Mineradio](https://github.com/XxHuberrr/Mineradio) 的视觉方向。
Copyright (C) 2026 XxHuberrr。Mineradio 名称、MR Logo、界面视觉设计、启动动画方向、粒子视觉体验
和电影镜头系统的产品表达来自原项目，归原作者所有；本项目已改名换标为 StarWave，不冒充官方。

本仓库继续保留 GPL-3.0 授权、上游 README（`UPSTREAM_README.md`）、隐私说明和安全说明。
原项目致谢名单见上游 README：emily、小天才e宝、应春日、锋将军、軌跡、林中、骊、风痕、花椰菜🥦。

## 修改说明（GPL-3.0 第 5 条 a 款）

2026-11-09，StarWave Phase 1：改名换标；删除桌面专属文件与全部浏览器扩展代码
（含硬编码平台密钥，已清除）；删除油猴脚本；去掉 Google Fonts 外链（改用系统字体）；
PWA 缓存名改为 `starwave-pwa-v1`；新增网易云公开 API 直连接入与 6 首公有领域/CC 演示曲目。

2026-11-10，StarWave Phase 5A：搜索分页（P6，starwave-netease.js + index.html：
fetchNeteaseWebSearchResults 支持 offset、[data-search-load-more] 逐页追加）；
6 个新视觉预设（P1，starwave-phase5.js：声波丘陵、霓光涟漪、曜环、霓雨、光蝶、
潮汐荧光，全部免费）；小工具（P9，starwave-phase5.js：存储统计与 Cache Storage
清理、性能探针）；Phase 5A review fixes：取页失败保留“加载更多”供重试、新搜索/
切换模式丢弃旧分页状态、清理缓存排除离线外壳缓存 starwave-pwa-v1。
