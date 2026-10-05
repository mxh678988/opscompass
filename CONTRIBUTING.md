# 贡献指南 · Contributing to OpsCompass

感谢你有兴趣为「运营智脑 OpsCompass」贡献代码、文档或想法。本指南说明参与方式与协作规范，请在提交 Issue / Pull Request 前阅读。

## 一、行为准则

- 尊重他人，友善交流，禁止人身攻击与恶意行为
- 就事论事，讨论技术问题，不夹带商业推广
- 遵守开源许可证与本仓库规范

## 二、可以贡献什么

| 类型 | 入口 | 说明 |
|---|---|---|
| Bug 报告 | GitHub Issue | 附复现步骤、期望结果、实际结果、环境信息 |
| 功能建议 | GitHub Issue | 说明使用场景与价值，而非仅给方案 |
| 代码贡献 | Pull Request | 见下文流程 |
| 文档改进 | Pull Request | 错别字、示例、教程、API 说明 |
| 翻译 | Pull Request | 多语言文档 |

## 三、开发环境

```bash
git clone https://github.com/mxh678988/opscompass.git
cd opscompass

# 后端（Python / FastAPI）
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 前端（Vue / TypeScript）
cd ../frontend
npm install
npm run dev
```

部署方式见 `deploy/README.md`，接口说明见 `docs/api.md` 与 `docs/openapi.json`。

## 四、分支与提交规范

- 从 `main` 切分支：`feat/xxx`、`fix/xxx`、`docs/xxx`、`refactor/xxx`
- 提交信息建议采用约定式提交：
  - `feat: 新增采集任务批量导入`
  - `fix: 修复指标聚合时区偏移`
  - `docs: 补充部署手册 HTTPS 章节`
- 一次提交只做一件事，避免混入无关改动
- 禁止提交密钥、凭据、个人数据、构建产物、本地数据文件

## 五、Pull Request 流程

1. Fork 本仓库并创建特性分支
2. 完成开发，本地自测通过（含相关单元/集成测试）
3. 同步上游 `main`，解决冲突
4. 提交 PR，填写：变更目的、影响范围、验证方式、关联 Issue
5. 通过代码审查后由维护者合并

PR 应尽量小而聚焦，便于审查；关联 Issue 的 PR 会优先处理。

## 六、代码风格

- Python：PEP 8，类型注解优先，公共函数需 docstring
- TypeScript / Vue：遵循仓库内 ESLint 配置，组件保持单一职责
- 数据库变更：迁移脚本放 `backend/migrations/`，不得直接改历史迁移
- 新增功能需附测试；修复缺陷需附回归用例

## 七、贡献者许可协议（CLA）

为保障项目与贡献者的权益，贡献者需确认：

- 你拥有所提交代码的版权，或已获得权利人授权
- 你同意将贡献内容按 Apache License 2.0 授权给本项目及下游使用者
- 你的贡献不包含第三方受限代码

提交 PR 即视为同意上述条款。

## 八、许可证

本项目采用 [Apache License 2.0](LICENSE)。提交贡献即表示你同意在本许可证下发布你的贡献。

---

BY LAOMENG 网络工作室 · 老孟（孟祥辉）
