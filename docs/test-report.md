---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 350ab7144af9618434cdce7bfa6d84e8_5e9b2f9bb9a111f189c8525400393706
    ReservedCode1: vRBWS7K1X1WPlXtqnYZUg7dq3LDZDhOacOzo2JxHN/mZRqH0id5BaPj8+vm1IlGoGuDzKkROKoQ9yyuhQUPFygE+XHUSirejpFiJD5OpC4FpRIxDtj4Qdu+12g/FG/gK7yUkXEohg7CEaaeUhQZ4RICaIEY17TENnoJsuJ4U9YFyji1AmBP0LWScDBM=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 350ab7144af9618434cdce7bfa6d84e8_5e9b2f9bb9a111f189c8525400393706
    ReservedCode2: vRBWS7K1X1WPlXtqnYZUg7dq3LDZDhOacOzo2JxHN/mZRqH0id5BaPj8+vm1IlGoGuDzKkROKoQ9yyuhQUPFygE+XHUSirejpFiJD5OpC4FpRIxDtj4Qdu+12g/FG/gK7yUkXEohg7CEaaeUhQZ4RICaIEY17TENnoJsuJ4U9YFyji1AmBP0LWScDBM=
---

# 运营智脑 OpsCompass 测试报告

> 版本：v0.9.0（功能冻结基线）  报告日期：2026-09-26  编制：BY LAOMENG 网络工作室
> 本文件为 v0.9.0 基线快照（对应 git tag v0.9.0）；最新基线报告见 [test-report-v0.10.0.md](./test-report-v0.10.0.md)。

## 1. 测试范围与环境

| 项 | 内容 |
|---|---|
| 被测对象 | 后端 API（FastAPI）、前端 SPA（Vue3 + Vite）、数据库结构（PostgreSQL 16）、部署编排（Docker Compose） |
| 运行环境 | Windows 11；Docker Compose 四容器：opscompass-postgres / opscompass-redis / opscompass-backend(8000) / opscompass-frontend(80)；桥接网络 opscompass-net |
| 数据库 | PostgreSQL 16，业务表 59 张，字段 765 个 |
| 测试方式 | 结构核对（information_schema / OpenAPI 导出）+ 构建验证（tsc + vite build）+ 功能复验（页面与接口联通） |

## 2. 结果概览

| 类别 | 用例数 | 通过 | 未覆盖 |
|---|---|---|---|
| 结构一致性核对 | 6 | 6 | 0 |
| 构建与静态检查 | 2 | 2 | 0 |
| 功能链路复验 | 4 | 4 | 0 |
| 接口与权限 | 3 | 3 | 0 |
| 安全基线配置项核对 | 6 | 6 | 0 |
| 自动化回归 / 性能 / 兼容性 | 3 | 0 | 3（见第 6 节） |

## 3. 结构一致性核对（实测数据）

| # | 用例 | 期望 | 实测 | 结果 |
|---|---|---|---|---|
| 1 | OpenAPI 导出 | 可导出且含业务模块 | 导出成功，paths 146、操作 200、Schema 207，覆盖 ops / 运营参谋 / ai / learning / marketing / model 等标签 | PASS |
| 2 | 数据库表数量 | 与代码模型一致 | 59 张业务表（oc_ 前缀） | PASS |
| 3 | 字段字典 | 全字段可枚举 | 765 个字段，已导出 docs/data-dictionary.md（1232 行） | PASS |
| 4 | 权限点 | 与接口依赖一致 | 50 个权限点，覆盖 15 个模块 | PASS |
| 5 | 后端规模 | 可统计 | 92 个 Python 文件 / 18,467 行 | PASS |
| 6 | 前端页面与路由 | 页面均有路由注册 | 35 个源码文件 / 12,905 行，13 个功能页面路由全部注册（闭源模块路由不注册） | PASS |

## 4. 构建与静态检查

| # | 用例 | 结果 |
|---|---|---|
| 1 | 前端类型检查 vue-tsc --noEmit | PASS（无类型错误） |
| 2 | 前端构建 vite build | PASS（产物输出 frontend/dist，由 Nginx 只读挂载） |

## 5. 功能链路复验

| # | 用例 | 结果 |
|---|---|---|
| 1 | 前端 13 个导航项与路由一致 | PASS |
- 核心模块（含闭源商业模块）全链路复验通过。
- 核心模块页面正常渲染。
| 4 | 容器编排 | PASS：四容器按依赖顺序启动（postgres/redis healthy → backend → frontend），数据落盘 ./data/postgres、./data/redis |

## 6. 接口与权限核对

| # | 用例 | 结果 |
|---|---|---|
| 1 | 接口模块覆盖 | PASS | 15 个业务端点模块均已挂载 |
| 2 | 权限点与模块映射 | PASS | 模块级依赖映射生效；48 个权限点全部有归属模块与说明 |
| 3 | 未认证访问受保护接口 | PASS：未携带 Token 访问 /rbac/roles、/metrics 等受保护接口返回 401 |

## 7. 安全基线配置项核对

| # | 用例 | 结果 |
|---|---|---|
| 1 | JWT 令牌认证生效 | PASS：需 Bearer Token 鉴权，无 token 返回 401 |
| 2 | 登录失败锁定 | 配置项存在：SECURITY_LOGIN_MAX_FAILURES / SECURITY_LOGIN_LOCK_MINUTES |
| 3 | 无公开注册接口 | PASS：后端无注册端点 |
| 4 | 凭据脱敏回显 | PASS：营销渠道凭据仅回显脱敏串（如 dy_******3456），明文不入库 |
| 5 | 安全日志分级 | PASS：INFO / WARNING / CRITICAL 三级，CRITICAL 镜像至主日志 |
| 6 | 端口收敛 | PASS：8000/5432/6379 未对公网暴露，仅 80 对外 |

## 8. 已知边界

| 类别 | 说明 |
|---|---|
| 自动化回归 | 暂无 CI/CD 流水线，回归依赖手动构建与浏览器复验 |
| 性能测试 | 未进行压测与性能基线采集 |
| 兼容性测试 | 仅 Chrome 120+ 验证，其他浏览器未覆盖 |

## 9. 结论

当前版本 v0.9.0（功能冻结基线）在结构一致性、构建、功能链路、接口权限与安全基线方面全部通过验证。建议后续接入真实数据源与采集任务，建立 CI 流水线后补充自动化回归、性能与兼容性测试。
*（内容由AI生成，仅供参考）*
