# Agno AI Chat Service

基于 [Agno](https://github.com/agno-agi/agno) 框架的 AI 聊天服务，集成智谱 AI GLM-4-Flash 模型，支持知识库检索增强（RAG）和对话历史持久化。

## 功能特性

- **AI 聊天** — 基于智谱 AI GLM-4-Flash 的智能对话
- **知识库（RAG）** — 上传文档作为知识库，聊天时自动检索相关内容增强回答
- **对话历史** — SQLite 持久化存储对话历史，支持多轮对话
- **AgentOS UI** — 内置 Web 管理界面，可直接上传、管理、搜索知识库
- **交互式 CLI** — 命令行聊天工具，支持知识库管理命令
- **REST API** — 标准化 API 接口，方便集成

## 项目结构

```
agno_demo/
├── main.py                 # 主入口（python main.py 启动）
├── knowledge_base.py       # 知识库管理模块（向量检索）
├── test_agno_agent.py      # 单元测试
├── api_examples.py         # API 调用示例
├── benchmark.py            # 性能基准测试
├── pyproject.toml          # 项目依赖配置
├── .env                    # 环境变量（API Key 等）
├── static/
│   └── index.html          # Web 聊天界面（含语音录音）
├── app/
│   ├── agent.py            # Agent 创建与工具注册
│   └── cli.py              # CLI 入口
├── api/
│   └── routes.py           # API 路由（chat、stream、stt）
├── core/
│   ├── config.py           # 统一配置管理
│   └── knowledge.py        # 知识库模块
├── tools/
│   └── speech/
│       └── iflytek.py      # 讯飞语音听写 Toolkit
└── data/                   # 运行时数据（已 gitignore）
    ├── chromadb/           # 向量数据库（ChromaDB）
    ├── uploads/            # 上传文件暂存
    └── agent.db            # 对话历史数据库（SQLite）
```

## 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 配置环境变量

编辑 `.env` 文件，设置智谱 AI API Key：

```env
ZHIPUAI_API_KEY=your-api-key-here
```

API Key 获取地址：https://open.bigmodel.cn/

### 3. 启动服务

**API 服务（默认）：**

```bash
uv run python main.py
```

启动后：
- http://localhost:7777/ui — Web 聊天界面（含语音录音）
- http://localhost:7777 — AgentOS API 信息

**交互式命令行聊天：**

```bash
uv run python main.py --chat
```

## API 接口

### 聊天接口

```bash
curl -X POST http://localhost:7777/api/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "你好", "user_id": "user123"}'
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| message | string | 是 | 用户消息 |
| user_id | string | 否 | 用户 ID，默认 "default_user" |
| session_id | string | 否 | 会话 ID，传入可延续对话 |

**响应示例：**

```json
{
  "success": true,
  "message": "你好！有什么我可以帮助你的吗？",
  "session_id": "abc-123",
  "run_id": "run-456",
  "knowledge_sources": ["灯会知识库.md"]
}
```

聊天时会自动检索知识库：如果知识库中有相关内容，会作为上下文提供给 AI；没有相关内容则正常回答。

### 健康检查

```bash
curl http://localhost:7777/api/health
```

### Web UI

启动服务后访问 http://localhost:7777/ui：
- 与 AI 对话（流式逐 token 返回）
- 麦克风语音输入（自动识别并填入聊天框）
- 知识库自动检索增强

AgentOS API 信息：http://localhost:7777

## 知识库功能

### 支持的文件格式

- `.txt` — 纯文本
- `.md` — Markdown
- `.pdf` — PDF 文档
- `.docx` — Word 文档
- `.csv` — CSV 表格

### 上传方式

**1. AgentOS UI 上传（推荐）**

访问 http://localhost:7777，在界面中直接上传。

**2. CLI 命令上传**

```bash
uv run python main.py --chat
> /upload /path/to/document.md
```

### CLI 知识库命令

| 命令 | 说明 |
|------|------|
| `/upload <文件路径>` | 上传文件到知识库 |
| `/search <关键词>` | 搜索知识库内容 |
| `/list` | 查看知识库文档数量 |

### 工作原理

1. 文档上传后被分块处理
2. 使用 FastEmbed（ONNX 运行时）生成向量嵌入
3. 存储到 ChromaDB 向量数据库
4. 聊天时自动检索最相关的文档片段
5. 将检索到的内容作为上下文传递给 AI

### Embedding 模型

使用 `BAAI/bge-small-zh-v1.5`（中文优化），基于 FastEmbed 库（ONNX 运行时），特点：
- 无需 PyTorch，体积小（约 100MB）
- 无需任何 API 厂商依赖，纯本地运行
- 首次使用时自动下载模型（国内网络需配置代理）

**首次下载配置代理（可选）：**

在 `.env` 中添加：
```env
http_proxy=http://127.0.0.1:7890
https_proxy=http://127.0.0.1:7890
```

模型下载完成后可注释掉代理配置。

**服务器部署（无网络环境）：**

本地下载后，将 `~/.cache/fastembed/` 目录打包上传到服务器：

```bash
# 本地打包
tar czf fastembed-cache.tar.gz -C ~/.cache fastembed/

# 上传到服务器
scp fastembed-cache.tar.gz user@server:~/

# 服务器解压
ssh user@server "mkdir -p ~/.cache && tar xzf fastembed-cache.tar.gz -C ~/.cache/"
```

## 对话历史

对话历史通过 SQLite 数据库持久化存储在 `data/agent.db`。配置如下：

```python
from agno.db.sqlite import SqliteDb

sqlite_db = SqliteDb(db_file="data/agent.db")

agent = Agent(
    model=...,
    db=sqlite_db,
    add_history_to_context=True,
)
```

- 传入 `session_id` 可延续之前的对话
- 不传 `session_id` 则创建新会话

## 运行测试

```bash
uv run pytest
```

## 技术栈

| 组件 | 说明 |
|------|------|
| Agno | AI Agent 框架 |
| FastAPI | Web 服务框架 |
| 智谱 AI GLM-4-Flash | 大语言模型 |
| ChromaDB | 向量数据库 |
| FastEmbed | 本地 Embedding（ONNX） |
| SQLite | 对话历史存储 |
| AgentOS | Agno 内置 Web 管理界面 |
