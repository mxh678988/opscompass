---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 350ab7144af9618434cdce7bfa6d84e8_269dd171b59f11f183e7525400de85a5
    ReservedCode1: zNtnUxIpuKHpKPb2oNnLID2zSjknPFG3gVOv49rUTfA4t6OxS6VmW8SOj61AwQFEuNku+/bjbRPhJjJDKg+tQFRFwGIUn0K3jfAPqpzzSxNqatmK/MjGEF/oDO7N2h1c+rfxPIbjqeso03gfAVo0xylnR711lkoVlpMNoNk1HAcu8b4ylFacihH+mk0=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 350ab7144af9618434cdce7bfa6d84e8_269dd171b59f11f183e7525400de85a5
    ReservedCode2: zNtnUxIpuKHpKPb2oNnLID2zSjknPFG3gVOv49rUTfA4t6OxS6VmW8SOj61AwQFEuNku+/bjbRPhJjJDKg+tQFRFwGIUn0K3jfAPqpzzSxNqatmK/MjGEF/oDO7N2h1c+rfxPIbjqeso03gfAVo0xylnR711lkoVlpMNoNk1HAcu8b4ylFacihH+mk0=
---

# 运营智脑

> 让数据自动做出最优决策

运营智脑是一体化的运营数据智能分析与决策平台。项目采用**单根目录**开发模式，所有代码、数据、文档、脚本与部署配置均收敛在 `D:\OpsCompass` 下（`OpsCompass` 为技术目录名，对外品牌统一为「运营智脑」），便于备份、迁移与统一运维。

## 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 后端 | Python 3.11 + FastAPI + SQLAlchemy 2.x | 提供 REST API、指标计算与数据服务 |
| 前端 | Vue 3 + Vite + TypeScript + Pinia | 运营看板与交互界面 |
| 数据库 | PostgreSQL 16 | 主数据存储 |
| 缓存 | Redis 7 | 缓存、会话与任务队列 |
| 部署 | Docker Compose | 一键拉起本地/测试环境 |

## 目录结构

```
OpsCompass/                # 项目根目录（对外产品名：运营智脑）
├── backend/            后端服务（FastAPI）
│   ├── app/
│   │   ├── api/v1/     接口路由（endpoints 按业务域拆分）
│   │   ├── core/       配置、日志、安全等基础设施
│   │   ├── models/     ORM 数据模型
│   │   ├── schemas/    Pydantic 请求/响应模型
│   │   ├── crud/       数据访问层
│   │   ├── services/   业务逻辑层
│   │   └── utils/      通用工具
│   ├── tests/          单元测试与接口测试
│   └── requirements.txt
├── frontend/           前端应用（Vue 3 + Vite）
│   ├── src/
│   │   ├── api/        接口封装
│   │   ├── components/ 通用组件
│   │   ├── composables/组合式函数
│   │   ├── router/     路由
│   │   ├── store/      状态管理
│   │   ├── styles/     全局样式
│   │   └── views/      页面视图
│   └── package.json
├── data/               数据目录（不入库）
│   ├── raw/            原始数据
│   ├── processed/      清洗/加工后数据
│   ├── exports/        导出结果
│   ├── postgres/       PostgreSQL 数据卷
│   └── redis/          Redis 持久化卷
├── docs/               项目文档
├── scripts/            开发与运维脚本
├── deploy/             部署配置（Docker / Nginx）
├── logs/               运行日志
├── backups/            备份归档
├── .env.example        环境变量模板
├── .gitignore
└── docker-compose.yml
```

## 快速开始

### 1. 准备环境变量

```powershell
Copy-Item .env.example .env
# 按需修改 .env 中的数据库密码、端口等
```

### 2. 方式一：Docker Compose 一键启动（推荐）

```powershell
docker compose up -d --build
# 前端  http://localhost
# 后端  http://localhost:8000/docs
```

### 3. 方式二：本地原生开发

```powershell
# 后端
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 前端（另开终端）
cd frontend
npm install
npm run dev
```

或直接使用脚本：

```powershell
.\scripts\start_dev.ps1
```

## 常用脚本

| 脚本 | 用途 |
|---|---|
| `scripts/start_dev.ps1` | 本地启动后端 + 前端开发服务 |
| `scripts/init_db.py` | 初始化数据库（建库、建表） |
| `scripts/backup.ps1` | 备份数据目录与环境配置 |

## 配置说明

所有环境变量统一从根目录 `.env` 读取，模板见 `.env.example`。**严禁将 `.env` 及任何密钥文件提交到版本库**（已在 `.gitignore` 中屏蔽）。

## 开发约定

- 后端接口统一挂在 `/api/v1` 前缀下，新增业务域请在 `backend/app/api/v1/endpoints/` 下新建模块并在 `router.py` 注册。
- 前端接口调用统一走 `src/api/request.ts`，禁止在组件内硬编码后端地址。
- 数据文件一律放在 `data/` 下，禁止写入系统盘或其他目录。
- 提交前请确认 `.gitignore` 覆盖新增的本地文件类型。

## 开源说明

本项目采用 [Apache License 2.0](LICENSE) 开源。以下说明**仅限开源版**内容。

---

| 项目 | 开源版 | 商业版 |
|---|---|---|
| 功能范围 | 基础功能 + 社区插件 | 全部功能 + 高级功能 |
| 技术支持 | 社区支持 | 技术支持 + 定制开发 |
| 更新频率 | 季度更新 | 月度更新 |
| 价格 | 免费 | 付费订阅 |

- 开源方案：[docs/OPEN_SOURCE_PLAN.md](docs/OPEN_SOURCE_PLAN.md)
- 贡献指南：[CONTRIBUTING.md](CONTRIBUTING.md)
- 行为准则：[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- 安全策略：[SECURITY.md](SECURITY.md)
- 版权归属：[NOTICE](NOTICE)

---

## 文档

- [架构设计](docs/architecture.md)
- [接口说明](docs/api.md)
- [更新日志](docs/changelog.md)
- [开源方案](docs/OPEN_SOURCE_PLAN.md)
- [贡献指南](CONTRIBUTING.md)
*（内容由AI生成，仅供参考）*
