# ACLClouds 自动续期

基于 GitHub Actions 的 ACLClouds 服务自动续期脚本，每天定时检测到期时间，剩余不足 3 天时自动续期，并通过 Telegram 或 wxpusher 推送通知。

---

## 功能

- 自动登录 ACLClouds 控制台（含 captcha 模拟）
- 检测所有项目的到期时间，剩余 ≤ 3 天时触发续期
- 续期成功后重新获取并打印新的到期时间
- 支持 Telegram、wxpusher 双渠道推送
- 每次运行后自动清理旧的 workflow 记录，只保留最近 2 条
- 运行日志中 Token 等敏感信息自动脱敏

---

## 使用方法

### 1. Fork 本仓库

点击右上角 **Fork**，将仓库复制到你的账号下。

### 2. 配置 Secrets

进入仓库 **Settings → Secrets and variables → Actions**，添加以下 Secret：

| Secret 名称 | 必填 | 说明 |
|---|---|---|
| `ACLCLOUDS_EMAIL` | ✅ | ACLClouds 登录邮箱 |
| `ACLCLOUDS_PASSWORD` | ✅ | ACLClouds 登录密码 |
| `TG_BOT_TOKEN` | 可选 | Telegram Bot Token |
| `TG_CHAT_ID` | 可选 | Telegram 接收通知的 Chat ID |
| `WXPUSHER_APPTOKEN` | 可选 | wxpusher 应用 Token |
| `WXPUSHER_UID` | 可选 | wxpusher 接收用户 UID |

推送通知至少配置一种，两种都不配置则仅在 Actions 日志中记录结果。

### 3. 启用 Actions

进入仓库 **Actions** 页面，若提示 workflow 未启用，点击 **Enable** 即可。

---

## 运行时机

| 触发方式 | 说明 |
|---|---|
| 定时触发 | 每天 UTC 02:00（北京时间 10:00）自动运行 |
| 手动触发 | 在 Actions 页面点击 **Run workflow** |

---

## 推送通知

**续期成功时**推送包含成功项目名称及失败项目（如有）。

**续期失败时**推送错误信息。

剩余天数充足、无需续期时不发送推送。

---

## 文件结构

```
.
├── renew.py                        # 主脚本
└── .github/
    └── workflows/
        └── ACLClouds_Renew.yml     # GitHub Actions workflow
```


感谢代码提供者：https://github.com/ssd000012345/ACLClouds_Renew
---

## 注意事项

- 续期阈值默认为剩余 **3 天**，如需修改可编辑 `renew.py` 中的 `RENEW_THRESHOLD_DAYS`。
- workflow 运行记录默认只保留最近 **2 条**，自动删除更早的记录。
- 脚本运行日志中的 xsrf-token、captcha token 等敏感字段已自动脱敏，可安全分享日志。
