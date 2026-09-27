#!/usr/bin/env bash
# ==============================================================
# 运营智脑（OpsCompass）· 云服务器一键部署脚本
# Slogan：让数据自动做出最优决策
# 版权：BY LAOMENG 网络工作室
# --------------------------------------------------------------
# 适用：Ubuntu 20.04+ / Debian 11+ / Rocky 8+ / CentOS Stream 8+（x86_64 / arm64）
# 前置：Docker Engine 20.10+ 与 Docker Compose v2（docker compose）
# 用法：
#   sudo bash deploy/deploy.sh                                   # 自动生成 .env 并部署
#   sudo bash deploy/deploy.sh -y --domain ops.example.com
#   sudo bash deploy/deploy.sh --https --domain ops.example.com  # 叠加自签 HTTPS
#   sudo bash deploy/deploy.sh --skip-build                      # 不重建镜像，仅重启
#   sudo bash deploy/deploy.sh --down                            # 停止并移除容器（保留数据）
# ==============================================================
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# ------------------------------------------------------------ 默认参数
DOMAIN=""
HTTP_PORT="80"
HTTPS_PORT="443"
BACKEND_PORT="8000"
ENABLE_HTTPS="false"
SKIP_BUILD="false"
ASSUME_YES="false"
ACTION="up"
HEALTH_TIMEOUT=180
ENV_FILE=".env"
CERT_DIR="deploy/nginx/certs"
HTTPS_OVERLAY="deploy/docker/docker-compose.https.yml"

# ------------------------------------------------------------ 输出helper
c_reset="\033[0m"; c_red="\033[31m"; c_green="\033[32m"; c_yellow="\033[33m"; c_blue="\033[36m"
info() { printf "${c_blue}[信息]${c_reset} %s\n" "$*"; }
ok()   { printf "${c_green}[成功]${c_reset} %s\n" "$*"; }
warn() { printf "${c_yellow}[警告]${c_reset} %s\n" "$*"; }
err()  { printf "${c_red}[失败]${c_reset} %s\n" "$*" >&2; }
die()  { err "$*"; exit 1; }

usage() {
  sed -n '2,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 0
}

# ------------------------------------------------------------ 命令行解析
parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --domain) DOMAIN="${2:-}"; shift 2 ;;
      --http-port) HTTP_PORT="${2:-80}"; shift 2 ;;
      --https-port) HTTPS_PORT="${2:-443}"; shift 2 ;;
      --backend-port) BACKEND_PORT="${2:-8000}"; shift 2 ;;
      --https) ENABLE_HTTPS="true"; shift ;;
      --skip-build) SKIP_BUILD="true"; shift ;;
      -y|--yes) ASSUME_YES="true"; shift ;;
      --down) ACTION="down"; shift ;;
      --timeout) HEALTH_TIMEOUT="${2:-180}"; shift 2 ;;
      -h|--help) usage ;;
      *) die "未知参数：$1（使用 --help 查看用法）" ;;
    esac
  done
}

# ------------------------------------------------------------ 随机串
random_string() {
  local len="${1:-32}"
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex $(( (len + 1) / 2 )) | cut -c1-"$len"
  else
    LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "$len"
  fi
}

# ------------------------------------------------------------ compose 封装
COMPOSE_FILES=(-f docker-compose.yml)

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "${COMPOSE_FILES[@]}" "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "${COMPOSE_FILES[@]}" "$@"
  else
    die "未检测到 Docker Compose，请先安装 Docker Engine 与 Compose 插件"
  fi
}

require_docker() {
  command -v docker >/dev/null 2>&1 || die "未检测到 docker 命令，请先安装 Docker Engine：https://docs.docker.com/engine/install/"
  docker info >/dev/null 2>&1 || die "Docker 守护进程未运行（或当前用户无权限），请执行 systemctl start docker 或使用 sudo"
  if ! docker compose version >/dev/null 2>&1 && ! command -v docker-compose >/dev/null 2>&1; then
    die "未检测到 Docker Compose v2，请安装 docker-compose-plugin"
  fi
  command -v curl >/dev/null 2>&1 || die "未检测到 curl（健康检查依赖），请先安装：apt install curl / yum install curl"
}

# ------------------------------------------------------------ .env 准备
patch_env() {
  local key="$1" value="$2" file="$3"
  if grep -qE "^${key}=" "$file"; then
    # 密码可能含特殊字符，使用 | 作为分隔符
    sed -i -E "s|^${key}=.*$|${key}=${value}|" "$file"
  else
    printf '%s=%s\n' "$key" "$value" >> "$file"
  fi
}

env_value() {
  local key="$1" file="$2"
  grep -E "^${key}=" "$file" | tail -n1 | cut -d'=' -f2-
}

ensure_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    [[ -f .env.example ]] || die "缺少 .env.example，无法生成配置文件"
    info "未发现 .env，正在从 .env.example 生成生产配置…"
    cp .env.example "$ENV_FILE"

    local secret db_pwd user db_name
    secret="$(random_string 64)"
    db_pwd="$(random_string 24)"
    user="$(env_value POSTGRES_USER "$ENV_FILE")"; user="${user:-opscompass}"
    db_name="$(env_value POSTGRES_DB "$ENV_FILE")"; db_name="${db_name:-opscompass}"

    patch_env SECRET_KEY "$secret" "$ENV_FILE"
    patch_env POSTGRES_PASSWORD "$db_pwd" "$ENV_FILE"
    patch_env DATABASE_URL "postgresql+psycopg://${user}:${db_pwd}@postgres:5432/${db_name}" "$ENV_FILE"
    ok "已生成随机 SECRET_KEY 与数据库密码（仅存于 .env，请勿外泄）"
  else
    info ".env 已存在，保留现有密钥与数据库密码"
  fi

  # 生产基础项与端口对齐
  patch_env ENV "production" "$ENV_FILE"
  patch_env DEBUG "false" "$ENV_FILE"
  patch_env HTTP_PORT "$HTTP_PORT" "$ENV_FILE"
  patch_env HTTPS_PORT "$HTTPS_PORT" "$ENV_FILE"
  patch_env BACKEND_PORT "$BACKEND_PORT" "$ENV_FILE"
  patch_env FRONTEND_PORT "$HTTP_PORT" "$ENV_FILE"

  # CORS 白名单：仅放行实际访问来源
  local ip origins
  ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  ip="${ip:-127.0.0.1}"
  origins="http://localhost,http://localhost:5173,http://${ip}"
  if [[ -n "$DOMAIN" ]]; then
    origins="http://${DOMAIN},https://${DOMAIN},${origins}"
  fi
  if [[ "$ENABLE_HTTPS" == "true" ]]; then
    patch_env SECURITY_TRUST_FORWARDED_HEADERS "true" "$ENV_FILE"
  fi
  patch_env BACKEND_CORS_ORIGINS "$origins" "$ENV_FILE"

  # 关键项校验
  local secret_key
  secret_key="$(env_value SECRET_KEY "$ENV_FILE")"
  if [[ -z "$secret_key" || "$secret_key" == change-me* ]]; then
    warn "SECRET_KEY 仍为默认值，已自动替换为随机串"
    patch_env SECRET_KEY "$(random_string 64)" "$ENV_FILE"
  fi
  ok ".env 就绪（ENV=production / DEBUG=false / CORS=${origins}）"
}

# ------------------------------------------------------------ 端口占用提示（不阻断）
check_ports() {
  local check_tool=""
  if command -v ss >/dev/null 2>&1; then
    check_tool="ss"
  elif command -v netstat >/dev/null 2>&1; then
    check_tool="netstat"
  else
    warn "未找到 ss/netstat，跳过端口占用检查"
    return 0
  fi

  local port pid_info
  for port in "$HTTP_PORT" "$BACKEND_PORT" "$HTTPS_PORT"; do
    if [[ "$check_tool" == "ss" ]]; then
      pid_info="$(ss -lntp 2>/dev/null | awk -v p=":$port" '$4 ~ p {print $NF; exit}')"
    else
      pid_info="$(netstat -lntp 2>/dev/null | awk -v p=":$port" '$4 ~ p {print $NF; exit}')"
    fi
    if [[ -n "$pid_info" && "$pid_info" != *docker* ]]; then
      warn "端口 ${port} 已被占用（${pid_info}），若非本项目的容器请先释放或改用 --http-port 指定其他端口"
    fi
  done
}

# ------------------------------------------------------------ HTTPS 自签证书
prepare_https() {
  [[ "$ENABLE_HTTPS" == "true" ]] || return 0
  [[ -f "$HTTPS_OVERLAY" ]] || die "缺少 HTTPS 覆盖编排：${HTTPS_OVERLAY}"
  command -v openssl >/dev/null 2>&1 || die "启用 HTTPS 需要 openssl，请先安装（apt install openssl / yum install openssl）"

  mkdir -p "$CERT_DIR"
  if [[ -f "$CERT_DIR/server.crt" && -f "$CERT_DIR/server.key" ]]; then
    info "检测到已有证书，复用 ${CERT_DIR}/server.crt"
  else
    local cn
    cn="${DOMAIN:-$(hostname -f 2>/dev/null || echo opscompass.local)}"
    info "生成自签证书（CN=${cn}，有效期 825 天）…"
    openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
      -keyout "$CERT_DIR/server.key" \
      -out "$CERT_DIR/server.crt" \
      -subj "/C=CN/O=LAOMENG/CN=${cn}" \
      -addext "subjectAltName=DNS:${cn}" >/dev/null 2>&1 \
      || die "自签证书生成失败（请检查 openssl 版本是否支持 -addext）"
    chmod 600 "$CERT_DIR/server.key"
    ok "自签证书已生成：${CERT_DIR}/（浏览器会提示不受信任，生产建议替换为正式证书）"
  fi

  COMPOSE_FILES+=(-f "$HTTPS_OVERLAY")
  info "已叠加 HTTPS 编排：${HTTPS_OVERLAY}"
}

# ------------------------------------------------------------ 构建启动与健康检查
build_and_up() {
  if [[ "$SKIP_BUILD" == "true" ]]; then
    info "跳过镜像重建，直接启动容器…"
    compose up -d
  else
    info "构建镜像并启动容器（首次构建约 3-10 分钟，取决于网络与 CPU）…"
    compose up -d --build
  fi
  ok "容器已启动"
}

wait_health() {
  local name="$1" url="$2" elapsed=0
  printf "    等待 %s 就绪（%s）" "$name" "$url"
  while (( elapsed < HEALTH_TIMEOUT )); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      printf " %s\n" "OK"
      return 0
    fi
    sleep 3
    elapsed=$(( elapsed + 3 ))
    printf "."
  done
  printf "\n"
  return 1
}

run_migrations() {
  info "执行数据库结构升级（alembic upgrade head）…"
  if compose exec -T backend sh -c '[ -f /app/alembic.ini ]' >/dev/null 2>&1; then
    if compose exec -T backend alembic upgrade head; then
      ok "数据库结构已是最新"
    else
      warn "数据库升级返回非零（若为首次部署且表未初始化，可稍后重试：docker compose exec backend alembic upgrade head）"
    fi
  else
    warn "容器内未找到 alembic.ini，跳过结构升级"
  fi
}

print_summary() {
  local ip admin_user admin_pwd scheme front_url
  ip="$(hostname -I 2>/dev/null | awk '{print $1}')"; ip="${ip:-<服务器IP>}"
  admin_user="$(env_value SECURITY_ADMIN_USERNAME "$ENV_FILE")"; admin_user="${admin_user:-admin}"
  admin_pwd="$(env_value SECURITY_ADMIN_PASSWORD "$ENV_FILE")"

  scheme="http"
  front_url="http://${ip}"
  [[ "$HTTP_PORT" != "80" ]] && front_url="http://${ip}:${HTTP_PORT}"
  if [[ "$ENABLE_HTTPS" == "true" ]]; then
    scheme="https"
    front_url="https://${DOMAIN:-$ip}"
    [[ -z "$DOMAIN" && "$HTTPS_PORT" != "443" ]] && front_url="https://${ip}:${HTTPS_PORT}"
  fi

  echo
  ok "运营智脑部署完成"
  cat <<EOF

  访问入口
    前端控制台 : ${front_url}
    后端 API   : http://${ip}:${BACKEND_PORT}
    接口文档   : http://${ip}:${BACKEND_PORT}/docs

  登录账号
    用户名 : ${admin_user}
    密码   : ${admin_pwd:-（见 .env 中 SECURITY_ADMIN_PASSWORD）}
    提示   : 首次登录后请立即在「系统设置」中修改密码

  运维命令
    状态查看 : docker compose ps
    服务日志 : docker compose logs -f backend
    安全日志 : tail -f logs/security.log      # 分级安全事件（INFO/WARNING/CRITICAL）
    应用日志 : tail -f logs/app.log
    重启服务 : docker compose restart backend
    停止服务 : bash deploy/deploy.sh --down
    重新部署 : bash deploy/deploy.sh --skip-build

  安全建议
    1. 云厂商安全组仅放行 ${HTTP_PORT}${ENABLE_HTTPS:+, $HTTPS_PORT} 与必要的运维端口；
    2. 对外提供正式域名时，请用 Nginx/云负载均衡替换 ${CERT_DIR} 下的自签证书；
    3. 定期备份：docker compose exec -T postgres pg_dump -U \${POSTGRES_USER:-opscompass} \${POSTGRES_DB:-opscompass} > backup.sql
EOF
  echo
}

# ------------------------------------------------------------ 主流程
main() {
  parse_args "$@"

  echo "=============================================================="
  echo " 运营智脑（OpsCompass）· 云服务器一键部署"
  echo " 让数据自动做出最优决策"
  echo "=============================================================="

  require_docker

  if [[ "$ACTION" == "down" ]]; then
    info "停止并移除容器（数据保留在 data/ 目录）…"
    compose down
    ok "已停止"
    exit 0
  fi

  prepare_https
  ensure_env
  check_ports

  if [[ "$ENABLE_HTTPS" != "true" ]]; then
    info "提示：如需 HTTPS，可使用 --https --domain <域名> 重新执行（自动生成自签证书）"
  fi

  build_and_up
  wait_health "后端" "http://127.0.0.1:${BACKEND_PORT}/health" || {
    err "后端在 ${HEALTH_TIMEOUT}s 内未就绪，请查看日志：docker compose logs --tail=80 backend"
    exit 1
  }
  wait_health "前端" "http://127.0.0.1:${HTTP_PORT}/health" || {
    err "前端在 ${HEALTH_TIMEOUT}s 内未就绪，请查看日志：docker compose logs --tail=80 frontend"
    exit 1
  }

  run_migrations
  print_summary
}

main "$@"
