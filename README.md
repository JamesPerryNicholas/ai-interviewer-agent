# AI Interview Agent

## 前端语言选择器

Vue前端界面默认为英语模式，并在右上角的边框处提供了一项语言选择器。支持的语言有英语、简体中文、日语和
西班牙语。所选语言会保存在localstorage中，而Element Plus 控件也会遵循相同的语言设置

非认证业务页面在当前阶段仍为模拟状态;认证功能现在调用后端。

## 前端和后端认证集成

前端现在使用FastAPl认证服务，而不是模拟登录数据。

- 前端API基础URL:http://localhost:8000
  登录:POST/api/auth/login
  注册: POST/api/auth/register
  个人资料:GET/api/user/profile
  JWT存储在localStorage中，并自动作为Bearer令牌发送。
  后端允许来自http://localhost:5173和http://127.0.0.1:5173的cORS请求。

## 第三阶段：简历上传与 PDF 解析

本阶段已完成基础简历业务流程，不包含 Agent 或 LLM：

- `POST /api/resume/upload`：必须携带 JWT，只允许上传 PDF 文件。
- 文件保存到 `storage/resumes/`，文件名格式为 `user_id_timestamp.pdf`。
- 使用 PyMuPDF 提取 PDF 纯文本。
- 保存 `resumes` 数据库记录，`extracted_info` 当前预留为空。

上传测试：

```powershell
curl.exe -X POST http://localhost:8000/api/resume/upload `
  -H "Authorization: Bearer <access_token>" `
  -F "file=@resume.pdf;type=application/pdf"
```

接口文档：<http://localhost:8000/docs>

当前迁移文件：

`backend/alembic/versions/8a009e56fd00_create_resumes_table.py`

基于大模型的智能面试官系统。

当前已完成：

- 第一阶段：FastAPI、PostgreSQL、Redis、Docker 基础架构
- 第二阶段：用户注册、登录、bcrypt 密码哈希、JWT 身份认证

当前不包含 Agent、LLM、RAG、MCP 或面试业务流程。

## 技术栈

- 后端：Python 3.12、FastAPI、SQLAlchemy 2.0 异步模式、asyncpg、Alembic、Pydantic v2、uv
- 认证：bcrypt、python-jose、JWT Bearer Token
- 数据服务：PostgreSQL 16、Redis 7
- 前端：Vue 3、TypeScript、Vite、Pinia、Vue Router

## 项目结构

```text
ai-interviewer-agent/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   └── dependencies.py
│   │   ├── core/
│   │   │   └── security.py
│   │   ├── database/
│   │   │   ├── base.py
│   │   │   └── session.py
│   │   ├── models/
│   │   │   └── user.py
│   │   ├── schemas/
│   │   │   └── user.py
│   │   ├── config.py
│   │   └── main.py
│   ├── alembic/
│   │   └── versions/
│   │       ├── 0001_initial.py
│   │       └── 5683c053d963_create_users_table.py
│   ├── alembic.ini
│   ├── main.py
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/
├── .env.example
├── docker-compose.yml
└── README.md
```

## 1. 配置环境变量

在项目根目录执行：

```powershell
Copy-Item .env.example .env
```

重点配置：

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_interviewer
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=change-this-development-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
```

生产环境必须替换 `JWT_SECRET_KEY`，不要使用示例密钥。

## 2. 使用 Docker 启动完整前后端

确保 Docker Desktop 已启动，在项目根目录执行：

```powershell
docker compose up -d --build
docker compose ps
```

服务说明：

- `frontend`：Vue 3 前端，宿主机访问 `http://localhost:5173`
- `backend`：FastAPI 后端，宿主机访问 `http://localhost:8000`
- `postgres`：PostgreSQL 数据库，默认宿主机端口 `5432`
- `redis`：Redis 缓存，默认宿主机端口 `6379`

`backend` 容器启动时会自动执行 `alembic upgrade head`，然后启动 FastAPI；`frontend` 容器会先构建 Vue 项目，再由 Nginx 托管构建产物。

只启动基础设施：

```powershell
docker compose up -d postgres redis
```

停止服务：

```powershell
docker compose down
```

`docker compose down -v` 会删除本项目 PostgreSQL 和 Redis 数据卷，仅建议在本地开发环境使用。

## 3. 本地开发模式（可选）

```powershell
Set-Location .\backend
uv sync
uv run alembic upgrade head
uv run main.py
```

前端本地开发：

```powershell
Set-Location .\frontend
npm install
npm run dev
```

本地开发模式下，PostgreSQL 和 Redis 仍可通过 Docker 启动。

## 4. 数据库迁移

当前迁移会创建 `users` 表。后续新增模型时使用：

```powershell
uv run alembic revision --autogenerate -m "add domain models"
uv run alembic upgrade head
```

## 5. 启动 FastAPI（本地开发模式）

在 `backend` 目录执行：

```powershell
uv run main.py
```

基础接口：

```text
GET http://localhost:8000/
```

认证接口文档：<http://localhost:8000/docs>

## 6. 认证接口

### 注册

```powershell
$registerBody = @{
  username = "demo_user"
  email = "demo@example.com"
  password = "StrongPass123!"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/auth/register `
  -ContentType "application/json" `
  -Body $registerBody
```

成功返回用户公开信息，不会返回 `password_hash`。

### 登录

```powershell
$loginBody = @{
  email = "demo@example.com"
  password = "StrongPass123!"
} | ConvertTo-Json

$login = Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/auth/login `
  -ContentType "application/json" `
  -Body $loginBody

$token = $login.access_token
```

成功返回：

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

### 访问受保护接口

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri http://localhost:8000/api/auth/me `
  -Headers @{ Authorization = "Bearer $token" }
```

无 Token、Token 过期或 Token 无效时返回 HTTP 401。

## 7. Docker 文件说明

- `docker-compose.yml`：编排前端、后端、PostgreSQL 和 Redis 四个服务。
- `backend/Dockerfile`：构建 FastAPI 后端镜像，并自动执行数据库迁移。
- `frontend/Dockerfile`：构建 Vue 前端，然后使用 Nginx 托管 `dist`。
- `frontend/nginx.conf`：支持 Vue Router history 模式刷新页面。
- `backend/.dockerignore`、`frontend/.dockerignore`：排除本地依赖和构建产物。

## 8. 已新增和修改的文件

新增：

- `backend/app/models/user.py`：User SQLAlchemy 异步 ORM 模型
- `backend/app/schemas/user.py`：注册、登录、用户信息和 Token 的 Pydantic v2 Schema
- `backend/app/core/security.py`：bcrypt 密码哈希和 JWT 创建
- `backend/app/api/auth.py`：注册、登录、`/me` 路由
- `backend/app/api/dependencies.py`：JWT Bearer 和当前用户依赖
- `backend/app/core/__init__.py`
- `backend/alembic/versions/5683c053d963_create_users_table.py`：Alembic 自动生成的 users 表迁移
- `backend/Dockerfile`：后端镜像构建文件
- `backend/.dockerignore`
- `frontend/Dockerfile`：前端构建和 Nginx 镜像文件
- `frontend/nginx.conf`
- `frontend/.dockerignore`

修改：

- `backend/app/config.py`：增加 JWT 配置
- `backend/app/models/__init__.py`：导出 User 模型
- `backend/app/main.py`：注册认证 Router
- `backend/alembic/env.py`：导入模型并支持直接执行 Alembic
- `backend/pyproject.toml`、`backend/requirements.txt`：增加认证依赖
- `.env.example`：增加 JWT 环境变量
- `README.md`：增加认证阶段启动和测试说明

## 9. 验证结果

已验证：

- PostgreSQL 和 Redis 容器健康运行
- `users` 表迁移成功
- `alembic revision --autogenerate` 在结构一致时生成空迁移
- 注册接口返回 201
- 重复邮箱返回 409
- 登录接口返回 JWT
- 有效 JWT 访问 `/api/auth/me` 返回 200
- 无效 JWT 返回 401

## 10. 下一步建议

建议下一阶段开发：

1. 用户信息完善和刷新 Token 机制
2. 面试会话、岗位和简历等核心业务模型
3. 基于 JWT 的用户级数据权限控制
4. 再接入 LLM 和面试 Agent 工作流
