# AI Interview Agent

基于 Vue 3、FastAPI、PostgreSQL、Redis 和 DeepSeek 的智能 AI 面试系统。

项目面向求职者，提供从简历上传、PDF 解析、岗位管理、面试题生成，到 AI 模拟面试、回答评估和 PDF 面试报告的一体化流程。同时提供独立的管理员后台，用于查看 LLM 调用量、Token 消耗、响应延迟和普通用户账号。

## 一、项目能力

### 用户端

- 用户注册、登录、退出登录和 JWT 身份认证
- 用户资料、头像和职业状态管理
- PDF 简历上传、原始文件名保存和文本提取
- 简历 AI 分析，生成技能、项目经历、工作经历、能力等级和改进建议
- 岗位 JD 创建、查看和删除
- 参考面试题生成
- 基于简历、岗位和用户职业状态生成模拟面试题
- 多轮 AI 模拟面试
- SSE 流式接收 AI 面试官回复
- 面试消息持久化
- 面试回答分析和最终评分
- 面试报告查看和 PDF 下载
- 历史面试记录
- 登录记录、密码修改和账号删除
- 登录、上传、AI 调用等操作的限流和并发控制

### 管理员端

- 独立管理员登录入口：`/login_Admin`
- Token 消耗总览
- LLM 调用次数和功能分布
- P50、P90、P99 和平均响应延迟
- 最近调用记录，支持分页
- 创建普通用户账号，可手动输入或随机生成账号和密码
- 查看普通用户列表
- 删除普通用户账号
- 管理员退出登录

## 二、技术架构

```text
浏览器
  │
  ├── Vue 3 + TypeScript + Vite
  ├── Vue Router
  ├── Pinia
  ├── Element Plus
  └── Axios
          │ HTTP / SSE
          ▼
Nginx（前端生产容器）
          │ /api 反向代理
          ▼
FastAPI（后端）
  ├── JWT 认证与权限控制
  ├── AsyncSession + SQLAlchemy 2.0
  ├── 简历和面试业务 Service
  ├── DeepSeek LLM Service
  ├── Redis 限流、分布式锁和上下文缓存
  └── Alembic 数据库迁移
          │
          ├── PostgreSQL：业务数据
          ├── Redis：缓存、限流和临时状态
          └── storage volume：简历和头像文件
```

## 三、技术栈

### 后端

- Python 3.12
- FastAPI
- Uvicorn
- SQLAlchemy 2.0 Async ORM
- AsyncSession
- asyncpg
- PostgreSQL 16
- Alembic
- Pydantic v2 / pydantic-settings
- Redis 7
- bcrypt
- python-jose JWT
- PyMuPDF
- ReportLab
- uv

### 前端

- Vue 3
- TypeScript
- Vite
- Vue Router
- Pinia
- Axios
- Element Plus
- ECharts
- vue-i18n

## 四、目录结构

```text
ai-interviewer-agent/
├── backend/
│   ├── app/
│   │   ├── api/                    # FastAPI 路由
│   │   │   ├── admin.py             # 管理员登录、账号和用量接口
│   │   │   ├── auth.py              # 注册、登录、退出、当前用户
│   │   │   ├── interview.py         # 开始面试、聊天、SSE、结束面试
│   │   │   ├── job.py               # 岗位 JD 管理
│   │   │   ├── report.py            # 报告和 PDF 下载
│   │   │   ├── resume.py            # 简历上传、下载和分析
│   │   │   └── user.py              # 个人资料和账号设置
│   │   ├── core/
│   │   │   ├── security.py          # 密码哈希和 JWT
│   │   │   ├── rate_limit.py        # Redis 限流
│   │   │   └── distributed_lock.py  # Redis 分布式锁
│   │   ├── database/
│   │   │   ├── base.py              # DeclarativeBase
│   │   │   └── session.py           # AsyncEngine 和 AsyncSession
│   │   ├── llm/
│   │   │   └── deepseek.py          # DeepSeek 客户端封装
│   │   ├── models/                  # SQLAlchemy ORM 模型
│   │   ├── prompts/                 # 简历、面试和评分 Prompt
│   │   ├── schemas/                 # Pydantic 请求和响应模型
│   │   ├── services/                # 业务服务层
│   │   ├── config.py                # 环境变量配置
│   │   └── main.py                  # FastAPI 应用入口
│   ├── alembic/                    # 数据库迁移
│   ├── tests/                      # 自动化测试
│   ├── Dockerfile
│   ├── main.py                     # 本地开发入口
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/
│   ├── src/
│   │   ├── api/                    # Axios API 封装
│   │   ├── layouts/                # 用户端和管理员端布局
│   │   ├── router/                 # 路由和导航守卫
│   │   ├── stores/                 # Pinia 状态管理
│   │   ├── views/                  # 页面组件
│   │   ├── i18n/                   # 多语言配置
│   │   └── style.css               # 全局样式
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   └── package-lock.json
├── storage/
│   └── resumes/                    # 本地开发时的文件存储目录
├── docker-compose.yml
├── .env.example
└── README.md
```

## 五、环境准备

建议环境：

- Windows 10/11 或 Linux
- Docker Desktop 24+
- Docker Compose v2+
- Node.js 22+（仅本地前端开发需要）
- Python 3.12（仅本地后端开发需要）
- uv

检查版本：

```powershell
docker --version
docker compose version
node --version
python --version
uv --version
```

## 六、环境变量配置

在项目根目录创建 `.env`：

```powershell
Copy-Item .env.example .env
```

生产环境至少需要修改以下配置：

```dotenv
APP_ENV=production

# 必须使用随机强密钥，不能使用示例值
JWT_SECRET_KEY=请填写至少32位随机字符串
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=120

# DeepSeek API
DEEPSEEK_API_KEY=你的DeepSeek_API_Key
DEEPSEEK_MODEL=deepseek-chat

# 管理员初始化账号
ADMIN_USERNAME=admin
ADMIN_PASSWORD=请填写强密码

# 数据库和 Redis 密码
POSTGRES_DB=ai_interviewer
POSTGRES_USER=postgres
POSTGRES_PASSWORD=请填写数据库强密码
REDIS_PASSWORD=请填写Redis强密码

# 前端访问来源
CORS_ORIGINS=http://localhost:5173
```

生产环境要求：

- 不要使用 `admin`、`admin@123`、`password` 等弱密码
- `JWT_SECRET_KEY` 至少 32 个字符
- 不要把 `.env` 提交到 Git
- 不要把 `DEEPSEEK_API_KEY` 写入前端代码
- 不要把 PostgreSQL 和 Redis 端口映射到公网

生成 JWT 密钥示例：

```powershell
$bytes = New-Object byte[] 48
[Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
[Convert]::ToBase64String($bytes)
```

## 七、Docker 启动方式

### 1. 启动全部服务

在项目根目录执行：

```powershell
docker compose up -d --build
```

查看服务状态：

```powershell
docker compose ps
```

正常情况下包含：

| 服务 | 作用 | 地址 |
|---|---|---|
| `frontend` | Vue 生产前端和 Nginx | http://localhost:5173 |
| `backend` | FastAPI 后端 | http://localhost:8000 |
| `postgres` | PostgreSQL 数据库 | 仅 Docker 内部访问 |
| `redis` | Redis 缓存和限流 | 仅 Docker 内部访问 |

### 2. 只启动数据库和 Redis

适合本地启动后端和前端：

```powershell
docker compose up -d postgres redis
```

### 3. 停止服务

```powershell
docker compose down
```

不要随意执行下面的命令：

```powershell
docker compose down -v
```

该命令会删除 PostgreSQL、Redis 和文件存储卷中的数据。

### 4. 更新代码后重新构建

只更新前端：

```powershell
docker compose build frontend
docker compose up -d --no-deps frontend
```

只更新后端：

```powershell
docker compose build backend
docker compose up -d --no-deps backend
```

全部重新构建：

```powershell
docker compose build --no-cache
docker compose up -d
```

如果只是修改前端源码，通常不需要 `--no-cache`，否则构建时间会明显增加。

## 八、本地开发启动

### 后端

```powershell
Set-Location .\backend
uv sync
uv run alembic upgrade head
uv run main.py
```

后端地址：

- API：<http://localhost:8000>
- Swagger：<http://localhost:8000/docs>
- OpenAPI：<http://localhost:8000/openapi.json>

### 前端

新开一个终端：

```powershell
Set-Location .\frontend
npm ci
npm run dev
```

前端地址：<http://localhost:5173>

## 九、核心业务流程

```text
注册 / 登录
    │
    ▼
上传 PDF 简历
    │
    ▼
PyMuPDF 提取文本
    │
    ▼
DeepSeek 分析简历，保存 extracted_info
    │
    ▼
创建岗位并保存 JD
    │
    ▼
生成参考面试题
    │
    ▼
开始模拟面试，生成本场专属问题
    │
    ▼
用户回答 ←→ AI 面试官 SSE 流式追问
    │
    ▼
完成全部问题或主动结束
    │
    ▼
DeepSeek 评估回答并生成报告
    │
    ├── 页面查看评分详情
    └── 下载「岗位名称-面试评估报告.pdf」
```

## 十、主要页面和路由

### 用户端

| 路由 | 页面 |
|---|---|
| `/login` | 用户登录 |
| `/register` | 用户注册 |
| `/dashboard` | 用户总览 |
| `/profile` | 个人资料 |
| `/resume` | 简历上传和 AI 分析 |
| `/job` | 岗位管理 |
| `/interview` | 开始模拟面试 |
| `/interview/:id` | 面试聊天 |
| `/history` | 历史面试 |
| `/report/:id` | 面试报告 |
| `/settings` | 账号设置 |

### 管理员端

| 路由 | 页面 |
|---|---|
| `/login_Admin` | 管理员登录 |
| `/admin/usage` | 用量和成本看板 |
| `/admin/users` | 普通用户账号管理 |

## 十一、主要 API

所有需要登录的用户接口都要携带：

```http
Authorization: Bearer <access_token>
```

### 用户认证

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/register` | 注册用户 |
| POST | `/api/auth/login` | 用户登录，支持账号登录 |
| POST | `/api/auth/logout` | 用户退出 |
| GET | `/api/auth/me` | 获取当前用户 |

### 用户资料

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/user/profile` | 获取个人资料 |
| PATCH | `/api/user/profile` | 修改个人资料 |
| PATCH | `/api/user/password` | 修改密码 |
| GET | `/api/user/login-records` | 获取登录记录 |
| DELETE | `/api/user/account` | 删除当前账号及相关数据 |

### 简历

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/resume/upload` | 上传 PDF 简历 |
| GET | `/api/resume/latest` | 获取最近简历 |
| GET | `/api/resume/{id}/download` | 鉴权后下载自己的简历 |
| POST | `/api/resume/{id}/analyze` | AI 分析简历 |

### 岗位和面试题

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/job/create` | 创建岗位 JD |
| GET | `/api/job/list` | 获取当前用户岗位 |
| DELETE | `/api/job/{id}` | 删除自己的岗位 |
| POST | `/api/interview/generate` | 生成参考面试题 |

### 模拟面试

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/interview/start` | 创建本场面试并返回第一题 |
| POST | `/api/interview/chat` | 普通聊天接口 |
| POST | `/api/interview/stream` | SSE 流式面试回复 |
| GET | `/api/interview/history/{id}` | 获取面试和聊天记录 |
| GET | `/api/interview/list` | 获取历史面试列表 |
| POST | `/api/interview/{id}/finish` | 结束面试并生成报告 |
| POST | `/api/interview/{id}/end` | 主动结束面试 |
| DELETE | `/api/interview/{id}/messages/{message_id}` | 撤回自己的消息 |

### 报告

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/report/{interview_id}` | 获取面试评估报告 |
| GET | `/api/report/{interview_id}/pdf` | 下载 PDF 报告 |

## 十二、接口测试示例

### 1. 注册用户

```powershell
$body = @{
  username = "demo_user"
  email = "demo@example.com"
  password = "StrongPass123!"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/auth/register `
  -ContentType "application/json" `
  -Body $body
```

### 2. 登录并保存 Token

```powershell
$body = @{
  account = "demo_user"
  password = "StrongPass123!"
} | ConvertTo-Json

$login = Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/auth/login `
  -ContentType "application/json" `
  -Body $body

$token = $login.access_token
$headers = @{ Authorization = "Bearer $token" }
```

### 3. 获取用户资料

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri http://localhost:8000/api/user/profile `
  -Headers $headers
```

### 4. 上传 PDF 简历

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/resume/upload `
  -Headers $headers `
  -Form @{ file = Get-Item "C:\path\to\resume.pdf" }
```

### 5. 查看接口文档

打开：<http://localhost:8000/docs>

## 十三、数据库迁移

后端容器启动时会自动执行：

```powershell
alembic upgrade head
```

本地创建迁移：

```powershell
Set-Location .\backend
uv run alembic revision --autogenerate -m "describe the change"
uv run alembic upgrade head
```

查看当前版本：

```powershell
uv run alembic current
```

查看迁移历史：

```powershell
uv run alembic history
```

不要直接修改已经执行过的迁移文件；模型变更应新增迁移文件。

## 十四、数据持久化

Docker 使用以下命名卷：

| Volume | 内容 |
|---|---|
| `postgres_data` | 用户、简历、岗位、面试、报告等业务数据 |
| `redis_data` | Redis 持久化数据 |
| `resume_storage` | 简历文件和头像文件 |

头像同时保存数据库备份，后端启动时会在文件缺失时恢复头像文件。重新构建镜像不会删除这些卷中的数据。

需要注意：

- `docker compose down` 不会删除数据卷
- `docker compose down -v` 会删除数据卷
- 生产环境应额外配置 PostgreSQL 和文件存储备份
- `tmp/pdfs` 等临时 PDF 渲染目录可以定期清理，但删除前应确认不是当前正在生成的报告

## 十五、安全策略

项目已包含以下基础安全措施：

- 密码使用 bcrypt 哈希，不保存明文密码
- 普通用户和管理员使用独立 JWT 认证
- JWT 支持 issuer、audience、过期时间和 token version 校验
- 退出登录和修改密码会使旧 Token 失效
- 简历下载校验登录身份和资源所有权
- PostgreSQL、Redis 默认不映射到宿主机公网端口
- PDF 类型、大小、页数和文本长度限制
- 岗位 JD、头像和聊天输入长度限制
- 登录、上传和 AI 调用使用 Redis 限流
- 面试开始、回答提交和 AI 生成使用幂等键与分布式锁
- CORS 只允许配置的前端来源
- Nginx 添加 CSP、X-Frame-Options、Referrer-Policy 等安全响应头
- 用户删除时清理关联业务数据、简历文件和头像文件

上线前还应完成：

1. 使用正式域名和 HTTPS
2. 将 `CORS_ORIGINS` 改为正式前端域名
3. 使用独立的密钥管理服务保存 API Key 和数据库密码
4. 配置数据库、Redis、文件和日志备份
5. 增加监控、告警和集中式日志
6. 对公网入口增加 WAF 或反向代理限流

## 十六、自动化测试和代码检查

运行后端测试：

```powershell
Set-Location .\backend
uv sync --group dev
uv run pytest -q
```

运行 Ruff：

```powershell
uv run ruff check app tests
```

运行前端类型检查和构建：

```powershell
Set-Location ..\frontend
npm ci
npm run type-check
npm run build
```

推荐提交代码前执行：

```powershell
Set-Location ..
Set-Location .\backend
uv run ruff check app tests
uv run pytest -q

Set-Location ..\frontend
npm run type-check
npm run build
```

## 十七、常见问题

### 1. `REDIS_PASSWORD must be set`

说明 `.env` 没有配置 `REDIS_PASSWORD`。请填写 Redis 密码后重新执行：

```powershell
docker compose up -d --build
```

### 2. `POSTGRES_PASSWORD must be set`

说明 `.env` 没有配置 `POSTGRES_PASSWORD`。配置后重新启动 PostgreSQL。

### 3. 前端出现 502

依次检查：

```powershell
docker compose ps
docker compose logs --tail 100 backend
docker compose logs --tail 100 frontend
```

常见原因：

- 后端容器没有启动成功
- DeepSeek API Key 无效或接口超时
- Redis 不可用，触发安全失败策略
- 数据库迁移失败

### 4. 返回 409 Conflict

通常表示同一个面试或 AI 操作正在进行中，或者前一次请求还没有释放分布式锁。等待几秒后重试，并检查后端日志。不要连续点击提交按钮。

### 5. 返回 429 Too Many Requests

表示触发了 Redis 限流。等待限流窗口结束后再试；开发测试时也不要循环快速调用 AI 接口。

### 6. 修改代码后浏览器仍显示旧页面

重新构建前端并强制刷新：

```powershell
docker compose build frontend
docker compose up -d --no-deps frontend
```

浏览器按 `Ctrl + F5`。

### 7. AI 分析或报告生成较慢

延迟主要来自模型网络和生成时间。可以通过以下方式优化：

- 缩短简历和聊天上下文
- 限制模型输出 Token 数
- 使用更快的模型
- 使用 SSE 降低首字节等待感
- 缓存简历分析结果
- 将报告生成放入异步任务

## 十八、开发约定

- 数据库访问统一使用 `AsyncSession`
- 新业务优先按 `api -> service -> model` 分层
- 请求和响应统一使用 Pydantic v2 Schema
- 不在 API 路由中堆积复杂业务逻辑
- 不在前端写死后端数据库字段以外的业务状态
- 新增模型后必须生成 Alembic 迁移
- 修改环境变量时同步更新 `.env.example`
- 不提交 `.env`、API Key、密码、Token 和用户上传文件
- 生产环境变更后必须执行构建、迁移和回归测试

## 十九、当前项目边界

当前项目使用普通 Service 调用 DeepSeek，没有使用 LangGraph。当前重点是完成可运行的 AI 面试业务闭环，后续可以继续完善：

- 后台任务队列和报告异步生成
- 更细粒度的模型 Token 成本统计
- 对话上下文摘要和长期记忆
- 音频面试和语音识别
- 多租户和组织权限
- 对象存储替代本地文件卷
- 生产级日志、监控和告警

## 二十、快速开始

```powershell
Set-Location "D:\项目\AI workflow\ai-interviewer-agent"
Copy-Item .env.example .env
# 编辑 .env，填写数据库密码、Redis 密码、JWT 密钥和 DeepSeek API Key
服务器里不能让前后端同时构建，否则卡死
docker compose build backend
docker compose build frontend
docker compose up -d
docker compose ps
```

然后访问：

- 用户端：<http://localhost:5173>
- 管理员登录：<http://localhost:5173/login_Admin>
- 后端接口文档：<http://localhost:8000/docs>

