"""建表入口（容器内执行）。

用法：
    docker compose exec backend python -m app.init_db
"""

from sqlalchemy import text


def main() -> None:
    from app.core.config import settings
    from app.models import Base  # noqa: F401  触发全部模型注册
    from app.models.base import engine

    print("[init_db] 目标数据库:", settings.DATABASE_URL.split("@")[-1])
    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        version = conn.execute(text("SELECT version();")).scalar_one()

    print("[init_db] 连接成功:", str(version).split(",")[0])
    print("[init_db] 建表完成，共", len(Base.metadata.tables), "张表")
    for name in sorted(Base.metadata.tables):
        print("  -", name)


if __name__ == "__main__":
    main()
