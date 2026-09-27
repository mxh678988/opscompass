"""初始化数据库：创建数据库（如不存在）并建表。

用法：
    python scripts/init_db.py
"""

import sys
from pathlib import Path

# 允许直接以脚本方式运行
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.models import Base  # noqa: E402
from app.models.base import engine  # noqa: E402


def main() -> None:
    print("[init_db] 目标数据库:", settings.DATABASE_URL.split("@")[-1])

    # 建表（模型新增后需同步完善 Alembic 迁移）
    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        version = conn.execute(text("SELECT version();")).scalar_one()
    print("[init_db] 连接成功:", str(version).split(",")[0])
    print("[init_db] 建表完成，共", len(Base.metadata.tables), "张表")


if __name__ == "__main__":
    main()
