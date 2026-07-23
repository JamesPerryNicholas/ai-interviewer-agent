# AI Interview Agent

## 当前能力

- Vue 3 用户端与管理员后台，支持主题、个人资料、岗位和面试历史管理。
- FastAPI JWT 登录、服务端 Token 失效、登录审计和管理员账号管理。
- PDF 简历上传、PyMuPDF 文本解析、DeepSeek 结构化分析。
- 岗位 JD、个性化面试问题、SSE 模拟面试和评分报告 PDF。
- PostgreSQL 持久化，Redis 承担限流、分布式锁和面试上下文缓存。
- 前端开发环境直连 `http://localhost:8000`，生产镜像通过 Nginx 同源代理 `/api`。

## 简历上传与受保护下载

- `POST /api/resume/upload`：必须携带 JWT，只允许上传符合限制的 PDF。
- 文件保存在持久化卷 `storage/resumes/`，不提供公开静态目录。
- `GET /api/resume/{resume_id}/download`：校验 JWT 和简历所有权后下载。

上传测试：

```powershell
curl.exe -X POST http://localhost:8000/api/resume/upload `
  -H "Authorization: Bearer <access_token>" `
  -F "file=@resume.pdf;type=application/pdf"
```

接口文档：<http://localhost:8000/docs>

最新迁移：`backend/alembic/versions/m9n0o1p2q3r4_add_token_versions_and_idempotency.py`。

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

生产部署必须配置以下值，配置为空或仍使用弱口令时后端会拒绝启动：

```dotenv
APP_ENV=production
POSTGRES_PASSWORD=<数据库强密码>
REDIS_PASSWORD=<Redis强密码>
JWT_SECRET_KEY=<至少32字符的随机密钥>
ADMIN_PASSWORD=<至少12字符的管理员强密码>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=120
```

可使用 PowerShell 生成随机 JWT 密钥：

```powershell
$bytes = New-Object byte[] 48
[Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
[Convert]::ToBase64String($bytes)
```

不要提交根目录 `.env`。`.env.example` 只保留变量名，不保存任何真实密码或 API Key。

## 生产安全能力

- JWT 包含签发方、受众、签发时间、唯一 ID 和服务端版本号；退出登录或修改密码后旧 Token 立即失效。
- 登录、简历上传、简历分析、生成面试题、面试聊天和报告生成均使用 Redis 限流。
- 面试开始、回答提交、简历分析、问题生成和报告生成使用 Redis 分布式锁；回答请求带幂等 ID。
- 简历文件不再公开挂载，必须通过 `GET /api/resume/{id}/download` 并校验 JWT 与文件所有权。
- PDF 最大 10 MB、50 页、提取文本 80000 字符；岗位 JD 最大 20000 字符。
- 删除用户账号时同步删除业务数据、简历文件和头像文件。
- PostgreSQL、Redis、后端端口仅绑定到宿主机回环地址。

运行自动化检查：

```powershell
Set-Location .\backend
uv sync --group dev
uv run ruff check app tests
uv run pytest -q

Set-Location ..\frontend
npm ci
npm run build
```

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

后续新增模型时使用：

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
