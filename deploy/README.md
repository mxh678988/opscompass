---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 350ab7144af9618434cdce7bfa6d84e8_2aff6495b59f11f183e7525400de85a5
    ReservedCode1: ntUtIYjZDqOrH7aWWMkoUo/it1XgcRRfGYsXAjmvswXl5Ua/179Lt2GLRXJlFvnGIcFZ7FQR7Ao7GGejiBv3Q437poFIEP7viM3IYxgO15rBDVDCCAQXsbsVvEGKGuupKNe98LYPN/OWuTDL4yxFK8Qm4tD66+znakIKDVCdnyfHJEBe+S8VCBPzzV0=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 350ab7144af9618434cdce7bfa6d84e8_2aff6495b59f11f183e7525400de85a5
    ReservedCode2: ntUtIYjZDqOrH7aWWMkoUo/it1XgcRRfGYsXAjmvswXl5Ua/179Lt2GLRXJlFvnGIcFZ7FQR7Ao7GGejiBv3Q437poFIEP7viM3IYxgO15rBDVDCCAQXsbsVvEGKGuupKNe98LYPN/OWuTDL4yxFK8Qm4tD66+znakIKDVCdnyfHJEBe+S8VCBPzzV0=
---

# 运营智脑 · 部署说明

> 让数据自动做出最优决策

## 目录

- `docker/`：镜像构建文件（后端、前端多阶段构建）与 HTTPS 覆盖编排
- `nginx/`：前端容器内的 Nginx 站点配置（静态托管 + `/api` 反向代理）
- `scripts/`：离线镜像打包（`pack-images.ps1`）与载入校验（`load-images.sh`）
- `dist/`：离线镜像包输出目录（本地生成，已 gitignore）

## 本地/测试环境

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose logs -f backend
```

| 服务 | 地址 |
|---|---|
| 前端 | http://localhost |
| 后端 | http://localhost:8000 |
| 接口文档 | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

## 数据持久化

数据库与缓存数据分别挂载到 `data/postgres` 与 `data/redis`，删除容器不会丢失数据。

## 生产环境（镜像直用 · 免构建）

生产使用根目录 `docker-compose.prod.yml`：只运行已发布版本镜像，不挂载源码，仅前端 80 端口对外（数据库与后端仅容器网内可达）。两套编排互不叠加，同一台机器同一时刻只运行其中一套。

```powershell
# 联网服务器
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml config   # 校验编排
```

```powershell
# 无外网服务器：构建机导出 → 服务器校验载入
powershell -File deploy/scripts/pack-images.ps1                 # 生成 tar + SHA256 到 deploy/dist
# 分发 tar 与 .sha256 到服务器后：
# bash deploy/scripts/load-images.sh deploy/dist/opscompass-0.10.1-images.tar
# docker compose -f docker-compose.prod.yml up -d
```

镜像版本由 `OPS_VERSION` 控制（默认对齐应用版本）；HTTPS 叠加：

```powershell
docker compose -f docker-compose.prod.yml -f deploy/docker/docker-compose.prod.https.yml up -d
```

详见 `docs/deployment-manual.md` 形态 C / D。

## 常用命令

```powershell
docker compose ps            # 查看状态
docker compose restart backend
docker compose down          # 停止并移除容器（保留数据卷目录）
docker compose up -d --build # 重新构建并启动
```

生产编排命令请带 `-f docker-compose.prod.yml`，例如 `docker compose -f docker-compose.prod.yml ps`。
*（内容由AI生成，仅供参考）*
