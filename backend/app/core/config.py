"""全局配置：统一从项目根目录 .env 读取。"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

def _resolve_base_dir() -> Path:
    """定位项目根目录，兼容两种代码布局。

    - 源码/宿主机：<root>/backend/app/core/config.py，上溯三层即 <root>
    - 容器：`./backend` 直接挂载为 `/app`（即 /app/app/core/config.py），
      此时上溯三层会落到 `/`，会让 data/logs 写入容器可写层而非挂载卷，
      因此回退到同时包含 backend/frontend 的目录，再回退到工作目录。
    """
    here = Path(__file__).resolve()
    for candidate in (here.parents[2], here.parents[1]):
        if (candidate / "backend").is_dir() and (candidate / "frontend").is_dir():
            return candidate
    for candidate in (here.parents[2], here.parents[3], here.parents[1]):
        if (candidate / "backend").is_dir():
            return candidate
    cwd = Path.cwd()
    if (cwd / "app").is_dir():
        return cwd
    return here.parents[3]


# 项目根目录（宿主机为仓库根目录；容器内为 /app 挂载点）
BASE_DIR = _resolve_base_dir()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # 项目（PROJECT_NAME 为对外展示品牌名；目录名/容器名/包名等技术标识保持不变）
    PROJECT_NAME: str = "运营智脑"
    PROJECT_SLOGAN: str = "让数据自动做出最优决策"
    # 版本唯一来源：升版只改此处；FastAPI 文档与 /system/info 均引用本字段
    APP_VERSION: str = "0.10.1"
    ENV: str = "development"
    DEBUG: bool = True
    TIMEZONE: str = "Asia/Shanghai"

    API_V1_PREFIX: str = "/api/v1"

    # 后端
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    BACKEND_CORS_ORIGINS: str = "http://localhost:5173"
    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    LOG_LEVEL: str = "INFO"

    # 数据库
    DATABASE_URL: str = (
        "postgresql+psycopg://opscompass:opscompass_dev_pwd@localhost:5432/opscompass"
    )

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    # AI（双模式：api 云端 API / local 本地模型）
    AI_ENABLED: bool = True
    AI_MODE: str = "local"
    # api 模式：OpenAI 兼容接口
    AI_API_BASE_URL: str = "https://api.deepseek.com/v1"
    AI_API_KEY: str = ""
    AI_API_MODEL: str = "deepseek-chat"
    # local 模式：本地模型（Ollama 兼容接口；容器内经 host.docker.internal 访问宿主机）
    AI_LOCAL_BASE_URL: str = "http://host.docker.internal:11434"
    AI_LOCAL_MODEL: str = "qwen2.5:3b"
    # 通用
    AI_PROXY: str = ""
    AI_TIMEOUT: int = 120
    AI_MAX_TOKENS: int = 2048
    AI_TEMPERATURE: float = 0.3

    # ---------- 安全与权限 ----------
    # IP 白名单（默认关闭；开启后仅白名单内来源可访问）
    SECURITY_IP_ALLOWLIST_ENABLED: bool = False
    SECURITY_IP_ALLOWLIST: str = "127.0.0.1,::1"
    # 是否信任反向代理透传的 X-Forwarded-For（前置 Nginx 时才应开启）
    SECURITY_TRUST_FORWARDED_HEADERS: bool = False
    # 安全审计日志
    SECURITY_AUDIT_ENABLED: bool = True
    SECURITY_AUDIT_WRITE_OPERATIONS: bool = True
    SECURITY_AUDIT_RETENTION_DAYS: int = 180
    # 登录失败锁定
    SECURITY_LOGIN_MAX_FAILURES: int = 5
    SECURITY_LOGIN_LOCK_MINUTES: int = 15
    SECURITY_PASSWORD_MIN_LENGTH: int = 8
    # 初始化管理员（首次执行 seed_auth 时使用，登录后请立即修改密码）
    SECURITY_ADMIN_USERNAME: str = "admin"
    SECURITY_ADMIN_PASSWORD: str = "OpsCompass@2026"
    # 安全日志分级：独立文件通道（默认 logs/security.log），支持级别过滤与高危告警镜像
    SECURITY_LOG_ENABLED: bool = True
    # 低于该级别不写入安全日志文件：INFO / WARNING / CRITICAL
    SECURITY_LOG_MIN_LEVEL: str = "INFO"
    SECURITY_LOG_FILE: str = "security.log"
    SECURITY_LOG_MAX_BYTES: int = 5242880  # 5MB 轮转
    SECURITY_LOG_BACKUP_COUNT: int = 5
    # 达到该级别时镜像到主日志（app.log/控制台），供外部告警系统抓取
    SECURITY_LOG_ALERT_LEVEL: str = "CRITICAL"
    # 是否把 WARNING 及以上一并镜像到主日志（便于本地排查）
    SECURITY_LOG_MIRROR_TO_MAIN: bool = True

    # 目录
    DATA_DIR: str = "./data"
    EXPORT_DIR: str = "./data/exports"
    LOG_DIR: str = "./logs"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.BACKEND_CORS_ORIGINS.split(",") if o.strip()]

    # ------------------------------------------------------- 安全相关
    @property
    def ip_allowlist(self) -> list[str]:
        """IP 白名单条目（IP 或 CIDR）。"""
        return [i.strip() for i in (self.SECURITY_IP_ALLOWLIST or "").split(",") if i.strip()]

    @property
    def ip_allowlist_active(self) -> bool:
        """白名单是否真正生效：开关打开且列表非空。"""
        return bool(self.SECURITY_IP_ALLOWLIST_ENABLED and self.ip_allowlist)

    @property
    def security_overview(self) -> dict:
        """安全配置概览，供接口/运维自查。"""
        return {
            "listen": {"host": self.BACKEND_HOST, "port": self.BACKEND_PORT},
            "cors_origins": self.cors_origins,
            "ip_allowlist": {
                "enabled": self.SECURITY_IP_ALLOWLIST_ENABLED,
                "effective": self.ip_allowlist_active,
                "entries": self.ip_allowlist,
            },
            "auth": {
                "algorithm": "HS256",
                "access_token_expire_minutes": self.ACCESS_TOKEN_EXPIRE_MINUTES,
                "login_max_failures": self.SECURITY_LOGIN_MAX_FAILURES,
                "login_lock_minutes": self.SECURITY_LOGIN_LOCK_MINUTES,
                "password_min_length": self.SECURITY_PASSWORD_MIN_LENGTH,
                "secret_key_is_default": self.SECRET_KEY.startswith("change-me"),
            },
            "audit": {
                "enabled": self.SECURITY_AUDIT_ENABLED,
                "record_write_operations": self.SECURITY_AUDIT_WRITE_OPERATIONS,
                "retention_days": self.SECURITY_AUDIT_RETENTION_DAYS,
            },
            "security_log": {
                "enabled": self.SECURITY_LOG_ENABLED,
                "min_level": self.SECURITY_LOG_MIN_LEVEL,
                "alert_level": self.SECURITY_LOG_ALERT_LEVEL,
                "mirror_to_main": self.SECURITY_LOG_MIRROR_TO_MAIN,
                "file": self.SECURITY_LOG_FILE,
                "max_bytes": self.SECURITY_LOG_MAX_BYTES,
                "backup_count": self.SECURITY_LOG_BACKUP_COUNT,
            },
        }

    @property
    def redis_url(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ---------- 数据存储适配层（P2） ----------
    # 按接入数据类型路由到不同存储引擎实现；当前在 PostgreSQL 16 + Redis 7 环境内落地
    STORAGE_ROUTING_ENABLED: bool = True
    # 缓存：热点数据走 Redis，不可用时自动降级为直连数据库
    STORAGE_CACHE_ENABLED: bool = True
    STORAGE_CACHE_TTL_SECONDS: int = 60
    STORAGE_CACHE_PREFIX: str = "oc:cache"
    STORAGE_CACHE_FAILURE_THRESHOLD: int = 3
    STORAGE_CACHE_RECOVER_SECONDS: int = 30
    # 全文检索：PostgreSQL 全文索引（tsvector + GIN），pg_trgm 可用时启用模糊匹配
    STORAGE_SEARCH_ENABLED: bool = True
    STORAGE_SEARCH_LIMIT: int = 20
    # 时序指标：分区表（按 stat_time 范围分区）+ 时间索引
    STORAGE_TS_PARTITION_AHEAD_MONTHS: int = 6
    STORAGE_TS_PARTITION_BEHIND_MONTHS: int = 1
    STORAGE_TS_AUTO_PARTITION: bool = True
    # 分区边界所属时区偏移（小时）：月分区按本地业务日切分，默认东八区
    STORAGE_TS_PARTITION_UTC_OFFSET_HOURS: int = 8
    # 指标值镜像写入时序表（跨存储数据一致性对账的数据基础）
    STORAGE_MIRROR_ENABLED: bool = True
    STORAGE_MIRROR_STRICT: bool = False
    # 启动时回填存量指标值到时序分区表（幂等，只补缺失项）
    STORAGE_BACKFILL_ENABLED: bool = True
    STORAGE_BACKFILL_BATCH_SIZE: int = 2000
    # 一致性对账
    STORAGE_CONSISTENCY_SAMPLE_LIMIT: int = 20

    # ---------- 硬件探测与模型中心（P9） ----------
    # 硬件探测：单条子探测命令超时（秒）；Windows 走 WMI（PowerShell）与 nvidia-smi
    HARDWARE_PROBE_TIMEOUT_SECONDS: int = 8
    # 网络出口探测（公网连通性 / DNS / 代理），关闭后跳过该子项
    HARDWARE_NETWORK_PROBE_ENABLED: bool = True
    # 宿主机硬件快照有效期（小时）：容器内无法透视宿主机时，使用宿主机落盘快照兜底
    HARDWARE_HOST_SNAPSHOT_MAX_AGE_HOURS: int = 24
    # 模型中心：一键接入默认地址（留空则复用 AI_LOCAL_BASE_URL / AI_API_BASE_URL）
    MODEL_HUB_LOCAL_DEFAULT_URL: str = ""
    MODEL_HUB_CLOUD_DEFAULT_URL: str = ""

    # ------------------------------------------------------------ AI 相关
    @property
    def ai_mode(self) -> str:
        """规范化后的 AI 模式：api / local。"""
        mode = (self.AI_MODE or "local").strip().lower()
        return mode if mode in ("api", "local") else "local"

    @property
    def ai_base_url(self) -> str:
        """当前模式的接口基址。"""
        return (self.AI_API_BASE_URL if self.ai_mode == "api" else self.AI_LOCAL_BASE_URL).rstrip("/")

    @property
    def ai_model(self) -> str:
        """当前模式使用的模型名。"""
        return self.AI_API_MODEL if self.ai_mode == "api" else self.AI_LOCAL_MODEL

    @property
    def ai_mode_meta(self) -> dict:
        """双模式元信息，供接口与前端展示。"""
        return {
            "api": {
                "label": "API 模式（云端大模型）",
                "base_url": self.AI_API_BASE_URL,
                "model": self.AI_API_MODEL,
                "ready": bool(self.AI_API_KEY),
                "hint": "需在 .env 配置 AI_API_KEY",
            },
            "local": {
                "label": "本地模型模式（Ollama）",
                "base_url": self.AI_LOCAL_BASE_URL,
                "model": self.AI_LOCAL_MODEL,
                "ready": bool(self.AI_LOCAL_BASE_URL),
                "hint": "容器内经 host.docker.internal 访问宿主机 Ollama",
            },
        }

    @property
    def ai_ready(self) -> bool:
        """当前模式是否具备调用条件。"""
        if not self.AI_ENABLED:
            return False
        return bool(self.ai_mode_meta[self.ai_mode]["ready"])


settings = Settings()
