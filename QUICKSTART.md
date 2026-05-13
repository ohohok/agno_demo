# Agno AI Chat Service - 快速开始

## 📋 项目概述

这是一个基于 Agno 框架和智谱 AI (GLM) 的轻量级聊天服务，提供 RESTful API 接口。

### ✨ 特性

- ✅ 使用智谱 AI GLM-4-Flash 模型
- ✅ FastAPI 驱动的 RESTful API
- ✅ 无数据库依赖，轻量级设计
- ✅ 支持会话管理（多轮对话）
- ✅ 完整的单元测试覆盖
- ✅ 内置 AgentOS Web UI

---

## 🚀 快速开始

### 1. 安装依赖

```bash
uv sync
uv sync --extra test  # 如果需要运行测试
```

### 2. 配置 API Key

获取智谱 AI API Key: https://open.bigmodel.cn/

设置环境变量：
```bash
export ZHIPUAI_API_KEY='your-api-key-here'
```

### 3. 启动服务

```bash
python main.py          # API 服务（默认）
python main.py --chat   # 交互式命令行聊天
```

服务将在 `http://localhost:7777` 启动

---

## 📡 API 接口

### 健康检查

```bash
curl http://localhost:7777/api/health
```

**响应：**
```json
{
  "status": "healthy",
  "service": "Agno AI Chat"
}
```

### 聊天接口

```bash
curl -X POST http://localhost:7777/api/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "你好"}'
```

**请求参数：**
- `message` (string, required): 用户消息
- `user_id` (string, optional): 用户ID，默认 "default_user"
- `session_id` (string, optional): 会话ID，用于多轮对话

**响应：**
```json
{
  "success": true,
  "message": "你好！我是AI助手...",
  "session_id": "session-123",
  "run_id": "run-456"
}
```

### 多轮对话示例

```bash
# 第一轮对话
curl -X POST http://localhost:7777/api/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "我叫小明"}'

# 保存返回的 session_id，然后在第二轮使用
curl -X POST http://localhost:7777/api/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "你还记得我叫什么吗？", "session_id": "session-123"}'
```

---

## 🧪 运行测试

```bash
# 运行所有测试
python -m pytest test_agno_agent.py -v

# 运行测试并生成覆盖率报告
python -m pytest test_agno_agent.py -v --cov=agno_agent
```

---

## 💻 Python 代码调用示例

```python
import requests

# 简单聊天
response = requests.post(
    "http://localhost:7777/api/chat",
    json={"message": "你好"}
)
print(response.json()["message"])

# 带用户ID的聊天
response = requests.post(
    "http://localhost:7777/api/chat",
    json={
        "message": "今天天气怎么样？",
        "user_id": "user123"
    }
)

# 多轮对话
# 第一轮
response1 = requests.post(
    "http://localhost:7777/api/chat",
    json={"message": "我叫小明"}
)
session_id = response1.json()["session_id"]

# 第二轮（使用相同的 session_id）
response2 = requests.post(
    "http://localhost:7777/api/chat",
    json={
        "message": "你还记得我叫什么吗？",
        "session_id": session_id
    }
)
```

更多示例请查看 `api_examples.py` 文件。

---

## 🌐 Web UI

启动服务后，访问 http://localhost:7777/ui 可以使用 Web 聊天界面（含语音录音功能）。

---

## 📁 项目结构

```
agno_demo/
├── main.py                # 主入口（python main.py 启动）
├── test_agno_agent.py     # 单元测试
├── api_examples.py        # API 调用示例
├── static/
│   └── index.html         # Web 聊天界面（含语音录音）
├── app/                   # Agent 和 CLI 模块
├── api/                   # API 路由
├── core/                  # 配置和知识库
├── tools/                 # 工具（讯飞语音等）
├── pyproject.toml         # 项目配置和依赖
└── .env                   # 环境变量
```

---

## 🔧 配置说明

### 更换模型

在 `core/config.py` 中修改模型配置：

```python
ZHIPUAI_MODEL_ID = "glm-4-flash"  # 可选: glm-4, glm-4-plus, glm-4v
```

### 可用模型

- `glm-4-flash`: 快速响应，适合日常对话（推荐）
- `glm-4`: 标准版，平衡性能和成本
- `glm-4-plus`: 增强版，更强的推理能力
- `glm-4v`: 视觉模型，支持图片理解

---

## ❓ 常见问题

### Q: 如何查看 API 文档？

A: 启动服务后访问 http://localhost:7777/docs 查看 OpenAPI/Swagger 文档。

### Q: 如何持久化保存对话历史？

A: 当前版本使用内存存储，重启后对话历史会丢失。如需持久化，可以添加数据库支持。

### Q: 如何添加自定义工具？

A: 在 `app/agent.py` 的 `create_agent()` 中添加工具：
```python
from agno.tools.xxx import XXXTools

return Agent(
    model=...,
    tools=[IFlytekSTTToolKit(), XXXTools()],  # 添加工具
    ...
)
```

---

## 📝 许可证

MIT License

---

## 🔗 相关链接

- [智谱 AI 开放平台](https://open.bigmodel.cn/)
- [Agno 官方文档](https://docs.agno.com/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
