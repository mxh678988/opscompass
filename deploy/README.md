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

- `docker/`：镜像构建文件（后端、前端多阶段构建）
- `nginx/`：前端容器内的 Nginx 站点配置（静态托管 + `/api` 反向代理）

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

## 常用命令

```powershell
docker compose ps            # 查看状态
docker compose restart backend
docker compose down          # 停止并移除容器（保留数据卷目录）
docker compose up -d --build # 重新构建并启动
```
*（内容由AI生成，仅供参考）*
