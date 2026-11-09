# Security Policy

## Supported Versions

当前只维护最新公开版本。

## 密钥与凭据

- 本仓库不得包含任何平台账号、Cookie、Token、API 密钥、签名密钥或 secret。
  上游扩展中硬编码的酷狗签名密钥与酷我 secret Cookie 已在 Phase 1 随扩展代码一并删除，
  并经密钥扫描确认无残留。
- 如在代码或 Issue 中发现疑似密钥，请立即删除并通过 GitHub Issues 报告。

## Reporting a Vulnerability

如果你发现安全问题，请通过 GitHub Issues 或仓库作者主页联系作者。

请不要在公开 Issue 中直接贴出 Cookie、Token、账号信息、私密链接或可复现的敏感数据。

## Sensitive Data

StarWave 不收集或上传用户 Cookie。用户数据只保存在本机浏览器中。

如果你要提交问题反馈，请先确认没有附带：

- 本地音乐文件
- 用户账号截图
- 调试日志中的 Cookie、Token 或隐私路径
