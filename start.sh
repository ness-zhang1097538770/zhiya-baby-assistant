#!/bin/bash
# Kids Mind 本地一键启动：后端 8001 + 前端 3001，起好后自动打开浏览器
set -e
cd "$(dirname "$0")"

BACKEND_PORT=8001
FRONTEND_PORT=3001
ROOT="$(pwd)"
mkdir -p /tmp

wait_port() { # $1=端口 $2=名称
  for i in $(seq 1 60); do
    if curl -s -o /dev/null "http://127.0.0.1:$1/"; then
      echo "✅ $2 已就绪：http://127.0.0.1:$1"
      return 0
    fi
    sleep 1
  done
  echo "❌ $2 启动超时，看日志：tail -50 $3"
  return 1
}

# 后端（已在跑就跳过）
if curl -s -o /dev/null "http://127.0.0.1:$BACKEND_PORT/"; then
  echo "✅ 后端已在运行：8001"
else
  echo "▶ 启动后端..."
  (cd backend && nohup "$ROOT/backend/.venv/bin/python" -m uvicorn app.main:app --port 8001 \
    > /tmp/kidsmind-backend.log 2>&1 &)
  wait_port $BACKEND_PORT "后端" /tmp/kidsmind-backend.log
fi

# 前端（已在跑就跳过）
if curl -s -o /dev/null "http://127.0.0.1:$FRONTEND_PORT/"; then
  echo "✅ 前端已在运行：3001"
else
  echo "▶ 启动前端..."
  (cd frontend && nohup npm run dev -- --port 3001 > /tmp/kidsmind-frontend.log 2>&1 &)
  wait_port $FRONTEND_PORT "前端" /tmp/kidsmind-frontend.log
fi

open "http://127.0.0.1:$FRONTEND_PORT" 2>/dev/null || true
echo "🎉 全部就绪：http://127.0.0.1:$FRONTEND_PORT"
echo "   停止服务：./stop.sh"
