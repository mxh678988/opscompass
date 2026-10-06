---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 350ab7144af9618434cdce7bfa6d84e8_815392aec11f11f1887c525400de85a5
    ReservedCode1: yGaFfbtR68xa+cnzERx6sa8rejdExA5umIl0J/UoEFE7PPHKpUuLHl4wdfACTFK34rQTIt9GuCeDPAKK47j7Jt6K9KPRk8/CksBZYGxQnaeJo5bWNc9QiSIJ21gb1Dji/CXf/jL/OjYOXGm5R6CgZUjkbqRHiopsy6V3pLELDmh/ehukEseJpOidwYM=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 350ab7144af9618434cdce7bfa6d84e8_815392aec11f11f1887c525400de85a5
    ReservedCode2: yGaFfbtR68xa+cnzERx6sa8rejdExA5umIl0J/UoEFE7PPHKpUuLHl4wdfACTFK34rQTIt9GuCeDPAKK47j7Jt6K9KPRk8/CksBZYGxQnaeJo5bWNc9QiSIJ21gb1Dji/CXf/jL/OjYOXGm5R6CgZUjkbqRHiopsy6V3pLELDmh/ehukEseJpOidwYM=
---

# 运营智脑 OpsCompass v0.10.1 开源版发布说明（草稿）

> 版本：v0.10.1 ｜ 发布类型：首个开源版本 ｜ 状态：草稿，待仓库公开后发布
> 许可证：Apache License 2.0 ｜ 版权：BY LAOMENG 网络工作室（孟祥辉）

## 一、版本概述

运营智脑是一体化的运营数据智能分析与决策平台：数据接入 → 指标计算 → 运营洞察 → 决策执行，形成可闭环的运营决策链路。

v0.10.1 是首个开源版本，聚焦**可交付、可自部署**：提供免构建的生产编排、离线镜像打包/载入链路、五源版本一致性校验，并修复数据源方言与依赖可复现性问题。

## 二、开源范围

| 类别 | 内容 |
|---|---|
| 前端 | Vue 3 + TypeScript + Vite + Pinia 源码、构建脚本、配置 |
| 后端 | Python 3.11 + FastAPI + SQLAlchemy 2.x 源码、ORM 模型、REST 接口 |
| 部署 | Dockerfile、Docker Compose（开发 / 生产 / HTTPS 叠加）、Nginx 配置、部署脚本 |
| 文档 | 架构、接口、数据模型、数据字典、部署手册、运维手册、产品手册、快速上手、安全白皮书、测试报告 |
| 测试 | 单元测试与接口测试、测试数据 |

**暂不开源**：商业化模块、数字人模块、高级功能与未落地的社区插件体系。

## 三、技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.11 + FastAPI + SQLAlchemy 2.x |
| 前端 | Vue 3 + Vite + TypeScript + Pinia |
| 数据库 | PostgreSQL 16 |
| 缓存 | Redis 7 |
| 部署 | Docker Compose（四容器编排） |

## 四、快速开始

```bash
git clone https://github.com/mxh678988/opscompass.git
cd opscompass
cp .env.example .env          # 按需修改数据库密码、端口
docker compose up -d --build  # 前端 http://localhost ｜ 接口 http://localhost:8000/docs
```

本地原生开发与生产部署方式见 `README.md`、`docs/quick-start.md` 与 `docs/deployment-manual.md`。

## 五、系统要求

| 项 | 要求 |
|---|---|
| 操作系统 | Windows 10/11（64 位）、macOS 11+、Linux x86_64 |
| 运行时 | Docker Desktop 4.0+（Windows/macOS）或 Docker Engine 20.10+（Linux） |
| 磁盘 | ≥ 5 GB（含镜像） |
| 浏览器 | Chrome / Edge / Firefox 近两年版本 |

## 六、已知限制

- 开源版为**基础功能 + 社区插件**形态，商业化与数字人相关能力不在本仓库范围
- 开源版按季度更新节奏发布，商业版为月度更新
- Hive 数据源在本机无 HiveServer2 实例条件下仅验证驱动可用性与失败降级，真实源端到端落库待具备实例后补验
- AI 生成内容与建议需人工复核，不作为唯一决策依据

## 七、路线图（规划中）

| 版本 | 计划时间 | 主要方向 |
|---|---|---|
| v0.11.0 | 2026-12-01 | 社区插件支持 |
| v0.12.0 | 2027-02-01 | 高级分析功能 |
| v1.0.0 | 2027-06-01 | 稳定版 |

以上时间为规划，非发布承诺，以实际 Release 为准。

## 八、发布产物

- `Source code (zip)` / `Source code (tar.gz)`：GitHub 自动生成
- 离线镜像包与三平台安装包见 `docs/deploy/RELEASE_NOTES_v0.10.1.md`（商业分发渠道）

## 九、参与贡献

详见 `CONTRIBUTING.md` 与 `CODE_OF_CONDUCT.md`。安全问题请按 `SECURITY.md` 私下报告，勿开公开 Issue。

## 十、许可与版权

本项目采用 [Apache License 2.0](LICENSE)，版权归属见 [NOTICE](NOTICE)。

---

BY LAOMENG 网络工作室 · 老孟（孟祥辉）｜ 联系：mxh6789@live.cn
*（内容由AI生成，仅供参考）*
