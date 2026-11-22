#!/usr/bin/env bash
# Violet Print — 局域网服务器一键启动
#
#   1. 缺前端构建产物时自动构建（或加 --build 强制重建）
#   2. 以 0.0.0.0 绑定启动后端（同源托管前端，学生访问 http://<本机IP>:8000）
#
# 用法：
#   ./start.sh              # 构建（必要时）+ 启动
#   ./start.sh --build      # 强制重新构建前端
#   ./start.sh --port 8080  # 换端口
#   ./start.sh --workers 1  # 默认就是 1（SQLite + 进程内状态，不要多 worker）
#
# 常驻/开机自启请用 deploy/violetprint.service（Linux systemd）或 pm2。

set -euo pipefail
cd "$(dirname "$0")"

PORT=${PORT:-8000}
HOST=${HOST:-0.0.0.0}
BUILD=0
for arg in "$@"; do
  case "$arg" in
    --build) BUILD=1 ;;
    --port) shift; PORT=${1:-$PORT} ;;
    --port=*) PORT=${arg#*=} ;;
    --host) shift; HOST=${1:-$HOST} ;;
    --host=*) HOST=${arg#*=} ;;
    --help|-h) sed -n '2,16p' "$0"; exit 0 ;;
  esac
done

# ---- 后端虚拟环境 ----
if [ ! -x backend/.venv/bin/python ]; then
  echo "==> 创建后端虚拟环境"
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install -q -r backend/requirements.txt
fi

# ---- 原生 STL 解析器（可选，缺失会自动回退 numpy）----
if [ ! -f backend/native/libstl_fast.dylib ] && [ ! -f backend/native/libstl_fast.so ]; then
  echo "==> 编译原生 STL 解析器（可选）"
  (cd backend/native && ./build.sh) || echo "    编译失败，将使用 numpy 实现"
fi

# ---- 前端构建产物 ----
if [ "$BUILD" = "1" ] || [ ! -f frontend/dist/index.html ]; then
  echo "==> 构建前端（frontend/dist）"
  (cd frontend && { [ -d node_modules ] || npm install; } && npm run build)
fi

# ---- 局域网地址提示 ----
IPS=$(backend/.venv/bin/python - <<'PY'
import socket
ips=set()
try:
    s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8",80)); ips.add(s.getsockname()[0]); s.close()
except Exception: pass
try:
    for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET): ips.add(info[4][0])
except Exception: pass
print(" ".join(sorted(i for i in ips if not i.startswith("127."))))
PY
)
echo "==> 启动 Violet Print：$(printf 'http://%s:%s  ' $IPS $PORT 2>/dev/null || echo "http://<本机IP>:$PORT")"
[ -n "$IPS" ] && for ip in $IPS; do echo "    学生访问：http://$ip:$PORT"; done

cd backend
exec .venv/bin/python -m uvicorn app.main:app --host "$HOST" --port "$PORT" --workers 1
