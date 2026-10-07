# 知芽（Kids Mind 育儿多智能体）

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?style=flat&logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat&logo=typescript&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-4-06B6D4?style=flat&logo=tailwindcss&logoColor=white)
![DeepSeek](https://img.shields.io/badge/DeepSeek-4D6BFE?style=flat)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat)

> 0-3 岁新手父母的育儿助手：育儿问答 + 成长档案 + 提醒 + 数字绘本。

## 当前进度
- ✅ 阶段 0 PRD 体检（通过）
- ✅ 阶段 1 技术适配（通过）
- ✅ 阶段 2 后端 MVP（儿童档案、育儿问答、成长记录、提醒、故事工坊已通过）
- ✅ 阶段 3 正式前端 第 1 阶段：首页代表页（视觉方向已确认）
- ✅ 阶段 3 正式前端 第 2 阶段：问育儿页（SSE 流式 + CARE 答案 + 会话历史）
- ✅ 阶段 3 正式前端 第 3 阶段：成长页（六类记录 + 时间线 + 四类提醒）
- ✅ 阶段 3 正式前端 第 4 阶段：App 封装 + 到点响铃提醒（安卓内测包，真机响铃待验）
- ✅ 阶段 3 正式前端 第 5 阶段：故事工坊页（书架 + 生成流程 + 阅读器）
- ✅ 阶段 3 正式前端 第 6 阶段：我的页（儿童档案 + 隐私 + 关于）
- ✅ 正式前端五个页面（首页/问育儿/成长/故事/我的）全部完成，下一步阶段 4 上线

## 启动方法（本地）

**推荐：一键启动**（在项目文件夹下执行，起好后自动打开浏览器）

```bash
./start.sh     # 后端 8001 + 前端 3001，已在运行就跳过，不用等
./stop.sh      # 不用了就停掉
```

> 第一次启动会慢一点（Next.js 首次编译页面，约 20-40 秒）；之后再次启动或刷新页面都是秒开。

手动分步启动（想单独控制时用）：

```bash
cd backend
python3.12 -m venv .venv          # 首次才需要
.venv/bin/pip install -r requirements.txt
cp .env.example .env              # 把 DEEPSEEK_API_KEY 填进 .env（不要提交）
.venv/bin/python -m app.seed      # 导入知识库（39 条《3岁以下婴幼儿健康养育照护指南》问答）
.venv/bin/uvicorn app.main:app --port 8001
```

后端验收界面：**http://localhost:8001**（8000 被其他项目占用，本项用 8001）。

**正式前端（另开一个终端）**
```bash
cd frontend
npm install                    # 首次才需要
npm run dev -- --port 3001
```

浏览器打开：**http://localhost:3001**（`127.0.0.1:3001` 也可）。前端通过同源代理连接 `127.0.0.1:8001` 后端。

**安卓 App（内测）**：安装包在 `evidence/阶段3-第4阶段/kidsmind-v1.0-android-debug.apk`。App 加载电脑上的开发服务器，需手机与电脑同一 WiFi、且 `./start.sh` 已启动；安装与「到点响铃」验证步骤见 `evidence/阶段3-第4阶段/README.md`。重新打包：`cd frontend/android && ./gradlew assembleDebug`（需 JDK21 + Android SDK）。

## 验证方法

**mock 自动化测试（离线可跑）**
```bash
cd backend && .venv/bin/python -m pytest -q
```
应看到 `36 passed`。

**前端自动检查**
```bash
cd frontend
npm run lint
npm run typecheck
npm run test
npm run build
```

**真实模型冒烟（需要 Key）**
- 建一个儿童档案，问一个常规问题（如"8 个月辅食加什么"），看 CARE 结构化答案 + 来源；
- 问一个危急问题（如"宝宝突然抽搐怎么办"），应立即出急救提示（不调模型）；
- 详细步骤见 `evidence/阶段2/README.md`。

## 目录
- `backend/`：FastAPI 后端（档案、问答 SSE、风险分级、RAG 关键词检索、DeepSeek 调用）
- `frontend/`：Next.js 正式前端（移动优先，同时适配桌面浏览器）
- `阶段文档/`：技术适配声明、分阶段技术开发文档
- `PRD/`：PRD 源文件与整理版
- `evidence/`：各阶段证据包
- `项目状态.md`：进度与决策台账
