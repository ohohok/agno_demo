# Changelog

## 2026-05-12

### 性能优化

- 添加全链路性能计时日志（KB 检索、LLM 调用、总耗时）
- 聊天接口使用 `run_in_executor` 避免阻塞事件循环
- 新增流式聊天接口 `/api/chat/stream`（SSE，逐 token 返回）
- 新增 `benchmark.py` 性能基准测试脚本，支持阻塞和流式两种模式

### 知识库优化

- 知识库检索支持相似度阈值过滤（`similarity = 1 - cosine_distance`），默认阈值 0.4
- 文档分块策略从 5000 字符调整为 1500 字符，增加 200 字符 overlap，提升大文档的细粒度检索能力
- 搜索返回数量从 5 提升到 10
- 上传文件时使用自定义 `upload_reader`（更小的 chunk_size 和 overlap）
- RAG prompt 调整：鼓励 LLM 利用部分相关的知识库内容，而非保守回复"没有相关信息"

### 编码修复

- 添加 `sanitize_text()` 函数，清除 surrogate 字符（U+D800-U+DFFF）和无效控制字符
- 用户输入和知识库内容在注入 LLM 上下文前统一净化
- 文件读取支持 UTF-8 / GBK / Latin-1 多编码自动降级

### CLI 增强

- 新增 `/delete <文档名>` 命令，支持按名称删除知识库文档
- `/search` 命令 limit 从 5 提升到 15，展示更多结果
- `/upload` 命令说明更新：同名文件自动覆盖旧数据

### 测试

- 新增 `test_agno_agent.py` 单元测试，覆盖健康检查、聊天接口、请求/响应模型、Agent 配置等
- 20 个测试用例全部通过

## 2026-05-09

### 知识库功能

- 集成 agno Knowledge + ChromaDB + FastEmbed（BAAI/bge-small-zh-v1.5）
- 支持 TXT、MD、PDF、DOCX、CSV 文件上传
- AgentOS UI 集成知识库管理界面
- 聊天时自动检索知识库并注入上下文

### 基础架构

- Agno Agent + Zhipu AI GLM-4-Flash 集成
- FastAPI 服务，SQLite 存储对话历史
- AgentOS UI 提供 Web 交互界面
- CLI 交互式聊天模式
