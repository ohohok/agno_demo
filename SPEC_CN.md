# Agno AI 聊天服务 - 规格文档

**项目**: Agno AI Chat Service
**版本**: 2.0.0
**状态**: 进行中
**最后更新**: 2026-05-10

---

## 📊 当前状态

### ✅ 已完成的规格

#### 规格 1: 核心聊天服务
**状态**: ✅ 已完成
**优先级**: P0 (关键)

**需求**:
- [x] 通过 OpenAI 兼容 API 集成智谱 AI GLM 模型
- [x] 实现基于 FastAPI 的 REST 服务
- [x] 支持带消息处理的聊天端点
- [x] 处理多轮对话的会话管理
- [x] 实现适当的错误处理和验证
- [x] SQLite 对话历史持久化
- [x] 聊天中集成知识库检索增强（RAG）

**实现细节**:
```python
# 文件: agno_agent.py
- 使用 OpenAIChat (GLM-4-Flash) 配置 Agent
- 基础 URL: https://open.bigmodel.cn/api/paas/v4/
- 温度: 0.7, 最大 Token: 2048
- SQLite 持久化存储 (data/agent.db)
- add_history_to_context=True 实现多轮对话连续性
- 每次聊天请求自动检索知识库
- AgentOS 初始化时传入 knowledge=[knowledge] 以支持 UI 管理
```

**已实现的 API 端点**:
- `POST /api/chat` - 主聊天端点（支持 RAG）
- `GET /api/health` - 健康检查
- `GET /docs` - Swagger/OpenAPI 文档
- `GET /` - AgentOS Web UI
- `POST /knowledge/content` - 上传文档到知识库 (AgentOS)
- `GET /knowledge/content` - 列出知识库文档 (AgentOS)
- `POST /knowledge/search` - 搜索知识库 (AgentOS)

**测试覆盖率**: 18/18 测试通过 (100%)
- 所有端点的单元测试
- 基于 Mock 的测试（无需真实 API 调用）
- 请求/响应模型验证
- 知识库检索集成测试

---

#### 规格 2: 环境配置
**状态**: ✅ 已完成
**优先级**: P0 (关键)

**需求**:
- [x] 支持 `.env` 文件的环境变量
- [x] 启动时自动加载环境变量
- [x] 安全的 API Key 管理
- [x] Git 忽略敏感文件

**实现细节**:
```
创建的文件:
- .env (包含 ZHIPUAI_API_KEY)
- .gitignore (排除 .env, .env.local, data/)

依赖:
- 安装并配置 python-dotenv

代码变更:
- agno_agent.py: 添加 load_dotenv()
- chat_cli.py: 添加 load_dotenv()
- knowledge_base.py: 添加 load_dotenv()
```

**安全措施**:
- ✅ `.env` 已排除在版本控制之外
- ✅ API key 从环境变量加载（非硬编码）
- ✅ 支持多种 env 文件模式 (.env.local, .env.*.local)
- ✅ `data/` 目录已排除在版本控制之外（包含数据库和向量数据）

---

#### 规格 3: 测试基础设施
**状态**: ✅ 已完成
**优先级**: P1 (高)

**需求**:
- [x] API 端点的单元测试
- [x] 数据模型的单元测试
- [x] Agent 配置的单元测试
- [x] 基于 Mock 的测试策略
- [x] 知识库自动检索测试

**测试套件**:
```
文件: test_agno_agent.py
总测试数: 18
通过: 18
跳过: 0 (集成测试在无真实 key 时自动跳过)
失败: 0

测试分类:
- TestHealthEndpoint (1 个测试)
- TestChatEndpoint (8 个测试，含知识库检索)
- TestChatRequestModel (3 个测试)
- TestChatResponseModel (2 个测试)
- TestAgentConfiguration (4 个测试)
```

**测试命令**:
```bash
# 运行所有测试
uv run pytest

# 带覆盖率运行（未来增强）
uv run pytest --cov=agno_agent
```

---

#### 规格 4: 开发者体验
**状态**: ✅ 已完成
**优先级**: P1 (高)

**需求**:
- [x] API 使用示例
- [x] 快速开始指南
- [x] 配置文档
- [x] CLI 聊天界面
- [x] CLI 知识库管理命令

**交付物**:
```
创建的文件:
- api_examples.py (6 个综合示例)
- QUICKSTART.md (设置和使用指南)
- ZHIPU_SETUP.md (智谱 AI 配置)
- chat_cli.py (交互式 CLI，支持知识库命令)
- README.md (全面的项目文档)

CLI 命令:
- /upload <file>  : 上传文件到知识库
- /search <query> : 搜索知识库内容
- /list           : 查看知识库文档数量
- clear           : 清除对话历史
- exit/quit/q     : 退出
```

---

#### 规格 5: 依赖管理
**状态**: ✅ 已完成
**优先级**: P1 (高)

**当前依赖**:
```toml
[project.dependencies]
- agno>=2.2.3
- fastapi[standard]>=0.120.2
- openai>=2.32.0
- pydantic>=2.0.0
- python-dotenv>=1.2.2
- chromadb>=0.4.0          # 知识库向量数据库
- fastembed>=0.2.0         # 本地 Embedding（ONNX，不依赖 PyTorch）
- pypdf>=3.0.0             # PDF 文本提取
- python-docx>=1.0.0       # DOCX 文本提取
- sqlalchemy>=2.0.0        # agno 的数据库依赖

[project.optional-dependencies.test]
- pytest>=7.4.0
- pytest-asyncio>=0.21.0
- httpx>=0.25.0
- requests>=2.31.0
```

---

#### 规格 6: 知识库（RAG）
**状态**: ✅ 已完成
**优先级**: P1 (高)

**需求**:
- [x] 文档上传与索引（支持 TXT、MD、PDF、DOCX、CSV）
- [x] 本地 Embedding 模型（不依赖外部 API）
- [x] ChromaDB 向量数据库持久化存储
- [x] 聊天时自动检索知识库
- [x] 通过 AgentOS UI 管理知识库
- [x] CLI 知识库操作命令
- [x] 响应中包含知识来源引用

**实现细节**:
```python
# 文件: knowledge_base.py
- Knowledge 类（来自 agno.knowledge.knowledge）
- FastEmbedEmbedder，使用 BAAI/bge-small-zh-v1.5（中文优化）
- ChromaDb 向量数据库 (data/chromadb/)
- KnowledgeRetriever 类，用于聊天时检索
- 512 维向量嵌入
- 使用 persistent_client=True 持久化存储
```

**架构**:
```
文档上传 → 文本提取 → 分块 → 向量嵌入 → ChromaDB
                                            ↓
聊天请求 → KnowledgeRetriever.search() → 上下文注入 → Agent → 响应
```

**支持的文件格式**:
| 格式 | 处理方式 | 说明 |
|------|----------|------|
| .txt | 直接读取 | 自动检测 UTF-8/GBK 编码 |
| .md | 直接读取 | 同 txt |
| .csv | 直接读取 | 同 txt |
| .pdf | pypdf | 逐页提取文本 |
| .docx | python-docx | 段落级提取 |

**Embedding 模型**:
- 模型: `BAAI/bge-small-zh-v1.5`（中文优化）
- 引擎: FastEmbed（ONNX Runtime，约 100MB）
- 维度: 512
- 无需 PyTorch，无需外部 API

---

#### 规格 7: 对话持久化
**状态**: ✅ 已完成
**优先级**: P1 (高)

**需求**:
- [x] SQLite 数据库存储对话历史
- [x] 基于会话的多轮对话支持
- [x] 自动将历史注入上下文

**实现细节**:
```python
# 文件: agno_agent.py
from agno.db.sqlite import SqliteDb

sqlite_db = SqliteDb(db_file="data/agent.db")

agent = Agent(
    model=...,
    db=sqlite_db,
    add_history_to_context=True,  # 将历史注入上下文
)
```

**行为说明**:
- 提供 `session_id` → 继续已有对话
- 省略 `session_id` → 创建新会话
- 历史记录自动注入模型上下文以保持连续性
- SQLite 文件存储在 `data/agent.db`

---

### 📋 待完成的规格

#### 规格 8: 生产就绪
**状态**: ⏳ 待完成
**优先级**: P2 (中)

**待办事项**:
- [ ] 添加请求速率限制
- [ ] 实现日志中间件
- [ ] 添加请求/响应日志记录
- [ ] 配置 CORS 以支持 Web 访问
- [ ] 添加 API 认证（API keys/tokens）
- [ ] 实现优雅关闭
- [ ] 添加健康检查指标（响应时间、错误率）
- [ ] Docker 容器化
- [ ] CI/CD 流水线设置

---

#### 规格 9: 高级功能
**状态**: ⏳ 待完成
**优先级**: P3 (低)

**待办事项**:
- [ ] 添加对多个模型的支持（在 GLM 变体之间切换）
- [ ] 实现流式响应 (SSE)
- [ ] 添加文件/图片上传支持（用于 GLM-4V）
- [ ] 实现工具集成（搜索、计算器等）
- [ ] 添加对话导出（JSON、Markdown）
- [ ] 实现用户偏好/设置
- [ ] 添加分析和使用跟踪
- [ ] 支持批处理

---

## 🎯 下一步计划（按优先级）

### 立即执行（本周）
1. ✅ ~~完成核心聊天服务~~ 已完成
2. ✅ ~~设置环境配置~~ 已完成
3. ✅ ~~编写全面的测试~~ 已完成
4. ✅ ~~实现知识库（RAG）~~ 已完成
5. ✅ ~~添加对话持久化（SQLite）~~ 已完成
6. ⏳ 部署到暂存环境
7. ⏳ 使用真实 API 进行端到端测试

### 短期（接下来 2 周）
1. 添加生产就绪功能（日志、速率限制）
2. 创建部署文档
3. 设置监控和告警
4. 性能测试和优化

### 中期（接下来 1 个月）
1. 添加高级功能（流式、多模型）
2. 实现认证和授权
3. 创建管理仪表板
4. 编写用户文档

---

## 📈 指标

### 代码质量
- **测试覆盖率**: ~90% (估算)
- **类型覆盖**: 100% (所有函数都有类型提示)
- **代码检查**: 通过（无语法错误）
- **文档**: 全面（内联文档 + 外部指南）

### 性能
- **启动时间**: < 3 秒（包含 ChromaDB 初始化）
- **API 响应时间**: 取决于 GLM API（通常 1-3 秒）
- **内存使用**: ~150MB（ChromaDB + FastEmbed 模型已加载）
- **并发请求**: 未测试（FastAPI 支持异步）
- **向量嵌入生成**: ~50ms/查询（本地 ONNX）

### 可靠性
- **错误处理**: 全面（try-except 块）
- **输入验证**: Pydantic 模型强制执行 schema
- **优雅降级**: 失败时返回错误消息；无知识库结果时正常聊天

---

## 🔧 技术决策

### 决策 1: 使用 SQLite 实现持久化
**理由**:
- 轻量级、零配置数据库
- Agno 框架内置 SqliteDb 支持
- 足以满足单实例部署
- 基于文件，易于备份

**权衡**:
- ✅ 优点: 简单、无需服务器、可移植
- ❌ 缺点: 单写入限制，不适合多实例部署

---

### 决策 2: OpenAI 兼容接口
**理由**:
- 智谱 AI 提供 OpenAI 兼容的 API
- 利用现有的 OpenAI SDK
- 易于在提供商之间切换
- 文档完善且经过测试

**权衡**:
- ✅ 优点: 灵活、良好支持、易于集成
- ❌ 缺点: 需要 `openai` 包依赖

---

### 决策 3: 使用 FastEmbed 本地 Embedding
**理由**:
- 无需外部 API 依赖
- ONNX Runtime 轻量级（约 100MB 模型）
- 中文优化模型（BAAI/bge-small-zh-v1.5）
- 无需 PyTorch，推理更快

**权衡**:
- ✅ 优点: 免费、隐私、快速、无 API 速率限制
- ❌ 缺点: 首次运行需下载模型，仅限单一模型

---

### 决策 4: ChromaDB 作为向量存储
**理由**:
- 简单的嵌入式向量数据库
- Python 原生，与 agno 集成良好
- 单个配置标志即可持久化存储
- 无需独立的服务器进程

**权衡**:
- ✅ 优点: 易于设置、嵌入式、持久化
- ❌ 缺点: 不适合大规模分布式部署

---

### 决策 5: 每次聊天自动检索
**理由**:
- 简化客户端代码——无需单独的检索步骤
- 透明的 RAG——用户无需了解知识库
- 优雅降级——无结果时正常聊天

**权衡**:
- ✅ 优点: API 简单、透明、始终启用 RAG
- ❌ 缺点: 非知识库查询也有额外延迟，可能产生噪声

---

## 🐛 已知问题

### 问题 1: 无限速保护
**严重程度**: 中
**描述**: 没有防止 API 滥用的保护
**临时方案**: 使用反向代理（nginx）进行速率限制
**修复**: 实现中间件（规格 8）

### 问题 2: 无身份验证
**严重程度**: 高（生产环境）
**描述**: API 对知道端点的任何人开放
**临时方案**: 部署在 VPN 或内部网络后面
**修复**: 添加 API key 认证（规格 8）

### 问题 3: 首次运行需下载模型
**严重程度**: 低
**描述**: FastEmbed 模型（约 100MB）在首次使用时下载
**临时方案**: 预先下载或在 `.env` 中配置代理
**修复**: 将模型打包到部署中或使用 init 容器

### 问题 4: SQLite 单实例限制
**严重程度**: 中（扩展时）
**描述**: SQLite 不支持多进程并发写入
**临时方案**: 仅运行单实例
**修复**: 如需多实例部署，迁移到 PostgreSQL

---

## 📚 参考资料

- [Agno 框架文档](https://docs.agno.com/)
- [智谱 AI API 文档](https://open.bigmodel.cn/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [ChromaDB 文档](https://docs.trychroma.com/)
- [FastEmbed 文档](https://qdrant.tech/fastembed/)
- [BGE 模型卡片](https://huggingface.co/BAAI/bge-small-zh-v1.5)

---

## 📝 变更日志

### v2.0.0 (2026-05-10)
- ✅ 添加知识库（RAG），使用 ChromaDB + FastEmbed
- ✅ 添加 SQLite 对话持久化
- ✅ AgentOS UI 集成知识库管理
- ✅ CLI 知识库命令（/upload、/search、/list）
- ✅ 聊天响应中包含知识来源引用
- ✅ 支持 TXT、MD、PDF、DOCX、CSV 文件格式
- ✅ 本地 Embedding 模型（BAAI/bge-small-zh-v1.5）
- ✅ 全面的 README 文档
- ✅ 更新测试套件（18/18 通过）
- ✅ 更新依赖（chromadb、fastembed、pypdf、python-docx、sqlalchemy）

### v1.0.0 (2026-04-18)
- ✅ 初始实现
- ✅ 带智谱 AI 的核心聊天服务
- ✅ RESTful API 端点
- ✅ 完整的测试套件
- ✅ 环境配置
- ✅ 开发者文档

---

## 👥 团队说明

### 给开发者
- 提交前始终运行测试: `uv run pytest`
- 保持 `.env` 文件安全，永远不要提交它
- 为新代码使用类型提示
- 遵循现有的代码风格和模式
- 知识库数据在 `data/` 目录——已在 gitignore 中

### 给 AI 助手
- 参考此规格文档获取上下文
- 查看"待完成的规格"以获取下一个任务
- 添加功能时保持向后兼容性
- 完成规格时更新此文档

---

**文档维护者**: AI 助手 + 开发团队
**审查周期**: 每周
**下次审查日期**: 2026-05-17
