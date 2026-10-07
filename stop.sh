#!/bin/bash
# 停止本地后端(8001)与前端(3001)
pkill -f "uvicorn app.main:app --port 8001" 2>/dev/null && echo "已停止后端" || echo "后端未运行"
pkill -f "next dev --port 3001" 2>/dev/null; pkill -f "next-server" 2>/dev/null
pkill -f "npm run dev -- --port 3001" 2>/dev/null
sleep 1
curl -s -o /dev/null "http://127.0.0.1:3001/" && echo "前端仍在运行" || echo "已停止前端"
