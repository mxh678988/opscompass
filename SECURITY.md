---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 350ab7144af9618434cdce7bfa6d84e8_7ff3ae1cc11f11f1887c525400de85a5
    ReservedCode1: huIYhn8vd1otsa1RUS17ITAz0TfPkGAV/6AqCL/mp3RJghioYRdKJCzvdUcH74QRWeSTc6MTMYhowkSlr1r8JqU6F0j2jKaZS3OTRVUcxR4A0CmHy4rDIozI/Qr0GGxoSiT8U3f+hS0kO3TjpQHgjHrPI+WOpYXNOvZr3/RzSIPqaniA+73H4h82Sl4=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 350ab7144af9618434cdce7bfa6d84e8_7ff3ae1cc11f11f1887c525400de85a5
    ReservedCode2: huIYhn8vd1otsa1RUS17ITAz0TfPkGAV/6AqCL/mp3RJghioYRdKJCzvdUcH74QRWeSTc6MTMYhowkSlr1r8JqU6F0j2jKaZS3OTRVUcxR4A0CmHy4rDIozI/Qr0GGxoSiT8U3f+hS0kO3TjpQHgjHrPI+WOpYXNOvZr3/RzSIPqaniA+73H4h82Sl4=
---

# 安全策略 · Security Policy

## 支持的版本

安全修复仅面向当前主线小版本及其后续补丁版本提供。

| 版本 | 支持状态 |
|---|---|
| v0.10.x | 支持 |
| < v0.10 | 不再支持，建议升级 |

## 报告安全问题

如发现安全漏洞，请**不要**通过公开 Issue 披露。请邮件至：

**mxh6789@live.cn**

建议在邮件中提供：

- 漏洞类型与影响范围（涉及模块、接口、是否需认证）
- 复现步骤或概念验证（PoC）
- 受影响的版本与部署方式
- 是否已公开、是否计划公开

## 处理流程

1. 收到报告后确认并初步评估（通常 3 个工作日内首次回复）
2. 复现并定位问题，必要时与报告者协同验证
3. 修复并在后续补丁版本中发布，同步更新 `docs/changelog.md`
4. 视情况在发布说明中致谢报告者（需征得同意）

请给予合理的修复时间后再公开披露。

## 部署安全建议

- 首次部署务必修改 `.env` 中的数据库密码、`SECRET_KEY` 等默认值
- 生产环境不要使用 `DEBUG` 模式，不要对外暴露 `postgres` / `redis` 端口
- 启用 HTTPS（参考 `deploy/docker/docker-compose.prod.https.yml`）
- 定期备份 `data/` 目录，并校验备份可恢复
- 数据源账号遵循最小权限原则，只授予只读或必要的查询权限
- 不要在 Issue、日志或截图中粘贴密钥、Token、真实业务数据

## 已知边界

- 本产品包含 AI 辅助生成内容与建议，输出需人工复核，不得作为唯一决策依据
- 开源版按 Apache License 2.0 提供，不附带任何明示或默示担保

---

BY LAOMENG 网络工作室 · 老孟（孟祥辉）
*（内容由AI生成，仅供参考）*
