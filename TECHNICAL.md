# Agno AI Chat Service — Technical Documentation

> Version 2.0.0 | Last Updated: 2026-05-10

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Module Reference](#2-module-reference)
3. [Data Flow](#3-data-flow)
4. [Knowledge Base RAG Pipeline](#4-knowledge-base-rag-pipeline)
5. [API Reference](#5-api-reference)
6. [Data Models](#6-data-models)
7. [Database Schema](#7-database-schema)
8. [Configuration Reference](#8-configuration-reference)
9. [Embedding & Vector Search](#9-embedding--vector-search)
10. [Error Handling](#10-error-handling)
11. [Testing Architecture](#11-testing-architecture)
12. [Deployment Guide](#12-deployment-guide)

---

## 1. Architecture Overview

### 1.1 System Context

```
┌──────────────────────────────────────────────────────────┐
│                      Client Layer                        │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  Web UI   │  │  REST Client │  │   CLI (chat_cli)  │  │
│  │(AgentOS)  │  │ (api_examples)│  │                   │  │
│  └─────┬─────┘  └──────┬───────┘  └────────┬──────────┘  │
└────────┼───────────────┼────────────────────┼─────────────┘
         │               │                    │
         ▼               ▼                    ▼
┌──────────────────────────────────────────────────────────┐
│                   FastAPI Application                    │
│                   (agno_agent.py)                        │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              AgentOS (agno.os.AgentOS)            │   │
│  │  - Serves AgentOS UI at /                        │   │
│  │  - Manages /knowledge/* routes                   │   │
│  │  - Provides /docs (Swagger UI)                   │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │         Custom API Endpoints                      │   │
│  │  POST /api/chat  — Chat with RAG                  │   │
│  │  GET  /api/health — Health check                  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────┐  ┌────────────────────────────┐   │
│  │   Agent (agno)   │  │   KnowledgeRetriever       │   │
│  │  - OpenAIChat    │  │  - ChromaDB search         │   │
│  │  - GLM-4-Flash   │  │  - Context assembly        │   │
│  │  - SQLite history│  │                            │   │
│  └────────┬─────────┘  └──────────┬─────────────────┘   │
└───────────┼───────────────────────┼──────────────────────┘
            │                       │
            ▼                       ▼
┌──────────────────────┐  ┌────────────────────────┐
│   Zhipu AI GLM API   │  │   Local Storage Layer  │
│   (OpenAI-compatible) │  │                        │
│                      │  │  ┌──────────────────┐  │
│  chat completions    │  │  │ SQLite (agent.db) │  │
│                      │  │  │ conversation      │  │
│                      │  │  │ history           │  │
│                      │  │  └──────────────────┘  │
│                      │  │                        │
│                      │  │  ┌──────────────────┐  │
│                      │  │  │ ChromaDB          │  │
│                      │  │  │ (data/chromadb/)  │  │
│                      │  │  │ vector index      │  │
│                      │  │  └──────────────────┘  │
│                      │  │                        │
│                      │  │  ┌──────────────────┐  │
│                      │  │  │ FastEmbed ONNX    │  │
│                      │  │  │ (local, ~100MB)   │  │
│                      │  │  └──────────────────┘  │
└──────────────────────┘  └────────────────────────┘
```

### 1.2 Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Web Framework | FastAPI | >=0.120.2 | REST API + routing |
| Agent Framework | Agno | >=2.2.3 | Agent orchestration, session, memory |
| LLM Provider | Zhipu AI GLM-4-Flash | — | Chat completions (OpenAI-compatible) |
| Vector Database | ChromaDB | >=0.4.0 | Embedding storage & similarity search |
| Embedding Engine | FastEmbed (ONNX) | >=0.2.0 | Local text embedding generation |
| Embedding Model | BAAI/bge-small-zh-v1.5 | — | Chinese-optimized 512-dim embeddings |
| Conversation DB | SQLite | — (via agno) | Persistent conversation history |
| PDF Processing | pypdf | >=3.0.0 | PDF text extraction |
| DOCX Processing | python-docx | >=1.0.0 | Word document text extraction |
| Data Validation | Pydantic | >=2.0.0 | Request/response schema validation |
| Env Management | python-dotenv | >=1.2.2 | `.env` file loading |

---

## 2. Module Reference

### 2.1 `agno_agent.py` — Service Entry Point

**Role**: Main application module. Configures the Agent, AgentOS, and custom API endpoints.

**Key Components**:

- **Agent**: Configured with `OpenAIChat(id="glm-4-Flash")` pointing to Zhipu AI's OpenAI-compatible endpoint. Uses SQLite for history persistence with `add_history_to_context=True`.

- **AgentOS**: Wraps the Agent and Knowledge instances to provide the built-in Web UI at `/` and knowledge management routes at `/knowledge/*`.

- **Custom Endpoints**: `POST /api/chat` and `GET /api/health` are registered on the FastAPI `app` obtained from AgentOS.

**Initialization Sequence**:
1. Load `.env` → read `ZHIPUAI_API_KEY`
2. Initialize `SqliteDb(db_file="data/agent.db")`
3. Create `Agent(model=OpenAIChat(...), db=sqlite_db, ...)`
4. Import `knowledge` and `knowledge_retriever` from `knowledge_base`
5. Create `AgentOS(agents=[agno_agent], knowledge=[knowledge])`
6. Register custom routes on `app`
7. Start server via `agent_os.serve()`

### 2.2 `knowledge_base.py` — Knowledge Base Module

**Role**: Manages document indexing, vector storage, and retrieval for RAG.

**Key Components**:

- **`create_knowledge()`**: Factory function that creates an `Knowledge` instance with:
  - `FastEmbedEmbedder(id="BAAI/bge-small-zh-v1.5", dimensions=512)`
  - `ChromaDb(collection="knowledge_base", path="data/chromadb/", persistent_client=True)`

- **`KnowledgeRetriever`**: Wrapper class that provides:
  - `search(query, limit=5)` → `List[Dict]` with `content`, `source`, `chunk_index`
  - `get_context_for_query(query, limit=5)` → concatenated context string

**Global Instances** (module-level):
```python
knowledge = create_knowledge()           # Used by AgentOS for UI management
knowledge_retriever = KnowledgeRetriever(knowledge)  # Used by chat endpoint for RAG
```

Both `agno_agent.py` and `chat_cli.py` import these shared instances, ensuring the CLI and API operate on the same vector database.

### 2.3 `chat_cli.py` — Interactive CLI

**Role**: Terminal-based chat interface with knowledge base management.

**Key Functions**:

- `create_chat_agent()`: Creates an Agent instance (separate from the API agent, no SQLite persistence)
- `interactive_chat()`: Main loop — reads input, performs knowledge retrieval, calls agent
- `handle_kb_command(input)`: Dispatches `/upload`, `/search`, `/list` commands
- `read_file_safe(path)`: Multi-encoding file reader (UTF-8 → GBK → Latin-1 fallback)
- `sanitize_text(text)`: Strips surrogate characters that cause encoding errors

**Supported File Formats** (for `/upload`):

| Extension | Handler |
|-----------|---------|
| `.txt`, `.md`, `.csv` | `read_file_safe()` → `sanitize_text()` → `knowledge.insert()` |
| `.pdf` | `pypdf.PdfReader` → extract text per page → sanitize → insert |
| `.docx` | `python-docx.Document` → extract paragraph text → sanitize → insert |

All uploads create a temporary `.clean.*` file for sanitized content, insert into knowledge base, then delete the temp file.

### 2.4 `test_agno_agent.py` — Test Suite

**Role**: Unit and integration tests for the API layer.

**Test Classes**:
- `TestHealthEndpoint` — Verifies `/api/health` returns correct status
- `TestChatEndpoint` — Tests chat with message, user_id, session_id, knowledge, errors
- `TestChatRequestModel` — Validates Pydantic request model constraints
- `TestChatResponseModel` — Validates Pydantic response model fields
- `TestAgentConfiguration` — Checks agent model, markdown, DB, tools config

**Mocking Strategy**: Uses `unittest.mock.patch.object(agno_agent, 'run')` to mock the Agent's `run()` method, avoiding real API calls during testing.

### 2.5 `api_examples.py` — Usage Examples

**Role**: Demonstrates API usage patterns with the `requests` library.

**Examples**:
1. Simple chat message
2. Chat with custom user_id
3. Multi-turn conversation using session_id
4. Health check
5. cURL command equivalents
6. Persistent session with `requests.Session`

---

## 3. Data Flow

### 3.1 Chat Request Flow (with RAG)

```
Client POST /api/chat {"message": "...", "user_id": "...", "session_id": "..."}
   │
   ▼
chat_endpoint(request: ChatRequest)
   │
   ├──► knowledge_retriever.search(request.message)
   │       │
   │       ├── ChromaDB.vector_db.search(query, limit=5)
   │       │       │
   │       │       ├──► FastEmbedEmbedder.embed(query) → 512-dim vector
   │       │       ├──► ChromaDB cosine similarity search
   │       │       └──► Return matching Document objects
   │       │
   │       └── Format results → List[{content, source, chunk_index}]
   │
   ├── IF results found:
   │       │
   │       ├── Assemble context string from snippets
   │       ├── Wrap in prompt: "请基于以下知识库内容回答..."
   │       └── knowledge_sources = deduplicated source names
   │
   ├── ELSE:
   │       │
   │       └── user_message = original message (no modification)
   │
   ├──► agno_agent.run(user_message, user_id=..., session_id=...)
   │       │
   │       ├── SqliteDb loads prior conversation (if session_id exists)
   │       ├── History injected into model context
   │       ├── OpenAIChat → Zhipu AI GLM API (chat completions)
   │       ├── Response received and stored in SQLite
   │       └── Return RunResponse(content, session_id, run_id)
   │
   └──► Return ChatResponse(success, message, session_id, run_id, knowledge_sources)
```

### 3.2 Document Upload Flow

```
Client uploads file (via AgentOS UI or CLI /upload)
   │
   ▼
File type detection (.txt/.md/.csv/.pdf/.docx)
   │
   ├── .txt/.md/.csv → read_file_safe() → sanitize_text()
   ├── .pdf → PdfReader → per-page extract_text() → sanitize
   └── .docx → DocxDocument → per-paragraph text → sanitize
   │
   ▼
Write sanitized text to temporary .clean.* file
   │
   ▼
knowledge.insert(path=clean_file, name=original_filename)
   │
   ├── Text chunking (handled by agno Knowledge)
   ├── FastEmbed embedding per chunk → 512-dim vectors
   ├── Store in ChromaDB (collection: "knowledge_base")
   └── Include metadata: {source: filename, chunk_index: N}
   │
   ▼
Delete temporary clean file
   │
   ▼
Return success to client
```

---

## 4. Knowledge Base RAG Pipeline

### 4.1 Embedding Details

| Parameter | Value |
|-----------|-------|
| Model | `BAAI/bge-small-zh-v1.5` |
| Dimensions | 512 |
| Max Input Tokens | 512 (model limit) |
| Engine | FastEmbed (ONNX Runtime) |
| Model Size | ~100MB (auto-downloaded) |
| Language | Chinese-optimized (also supports English) |

The model is downloaded automatically on first use to `~/.cache/fastembed/`. For offline deployment, pre-populate this directory.

### 4.2 Retrieval Strategy

**Query Processing**:
1. User message is used as the search query (no query rewriting)
2. FastEmbed converts query to 512-dim vector
3. ChromaDB performs cosine similarity search against stored document vectors
4. Top 5 results returned (configurable via `limit` parameter)

**Context Assembly**:
```
请基于以下知识库内容回答用户的问题。如果知识库中没有相关信息，请如实说明。

=== 知识库内容 ===
[知识库片段 1] (来源: document_name.md)
... content ...

[知识库片段 2] (来源: another_doc.pdf)
... content ...
=== 知识库内容结束 ===

用户问题: <original user message>
```

**Fallback Behavior**: If `knowledge_retriever.search()` returns empty results, the original user message is sent to the agent without modification. This makes RAG transparent — knowledge base presence is optional.

### 4.3 Vector Database Configuration

```python
ChromaDb(
    collection="knowledge_base",   # Collection name
    embedder=FastEmbedEmbedder(    # Embedding function
        id="BAAI/bge-small-zh-v1.5",
        dimensions=512,
    ),
    path="data/chromadb/",         # Persistent storage directory
    persistent_client=True,        # Survives process restarts
)
```

**Storage Layout**:
```
data/chromadb/
├── chroma.sqlite3        # ChromaDB metadata
└── [uuid directories]/   # Vector index files
```

---

## 5. API Reference

### 5.1 `POST /api/chat`

**Description**: Send a message to the AI agent. Automatically retrieves relevant knowledge base content if available.

**Request Body** (JSON):

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `message` | string | Yes | — | User's message to the AI |
| `user_id` | string | No | `"default_user"` | Identifier for the user |
| `session_id` | string | No | `null` | Session ID for conversation continuity |

**Request Example**:
```json
{
  "message": "什么是灯会？",
  "user_id": "user123",
  "session_id": "abc-def-456"
}
```

**Response** (200 OK):

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether the request succeeded |
| `message` | string | AI-generated response text |
| `session_id` | string | Session ID (new or existing) |
| `run_id` | string | Unique identifier for this run |
| `knowledge_sources` | string[] | List of knowledge base sources used (null if none) |

**Response Example**:
```json
{
  "success": true,
  "message": "灯会是中国传统的民俗文化活动...",
  "session_id": "abc-def-456",
  "run_id": "run-789",
  "knowledge_sources": ["灯会知识库.md"]
}
```

**Error Response** (500):
```json
{
  "detail": "Error message string"
}
```

**Validation Error** (422):
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "message"],
      "msg": "Field required"
    }
  ]
}
```

### 5.2 `GET /api/health`

**Description**: Service health check.

**Response** (200 OK):
```json
{
  "status": "healthy",
  "service": "Agno AI Chat"
}
```

### 5.3 AgentOS Endpoints (Built-in)

These endpoints are provided by the Agno AgentOS framework:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | AgentOS Web UI |
| `GET` | `/docs` | Swagger/OpenAPI documentation |
| `POST` | `/knowledge/content` | Upload document to knowledge base |
| `GET` | `/knowledge/content` | List knowledge base documents |
| `POST` | `/knowledge/search` | Search knowledge base |

---

## 6. Data Models

### 6.1 ChatRequest

```python
class ChatRequest(BaseModel):
    message: str                           # Required. User message content.
    user_id: Optional[str] = "default_user"  # Optional. User identifier.
    session_id: Optional[str] = None       # Optional. Session ID for continuity.
```

**Validation Rules**:
- `message` is required (Pydantic will return 422 if missing)
- Empty string for `message` is accepted (processed normally)
- `user_id` defaults to `"default_user"` if not provided
- `session_id` is `None` for new sessions, string for existing sessions

### 6.2 ChatResponse

```python
class ChatResponse(BaseModel):
    success: bool                          # Request success indicator
    message: str                           # AI response content
    session_id: Optional[str] = None       # Session ID for this conversation
    run_id: Optional[str] = None           # Unique run identifier
    knowledge_sources: Optional[List[str]] = None  # Knowledge base sources used
```

### 6.3 KnowledgeRetriever Result Format

```python
# Internal representation returned by KnowledgeRetriever.search()
{
    "content": str,           # Text content of the matched chunk
    "source": str,            # Original document filename
    "chunk_index": int,       # Index of the chunk within the document
}
```

---

## 7. Database Schema

### 7.1 SQLite — Conversation History

**File**: `data/agent.db`

The schema is managed by the Agno framework's `SqliteDb` class. The database stores:

- **Sessions**: Conversation session metadata
- **Messages**: Individual messages within sessions (user + assistant)
- **Runs**: Agent execution records

The exact schema is defined by the agno framework and may evolve with framework updates. The database is created automatically on first run.

**Key Behaviors**:
- `session_id` is auto-generated when not provided by the client
- Passing an existing `session_id` loads prior messages into context
- `add_history_to_context=True` causes the agent to include conversation history in the LLM prompt

### 7.2 ChromaDB — Vector Index

**Path**: `data/chromadb/`

**Collection**: `"knowledge_base"`

**Document Schema** (managed by agno Knowledge + ChromaDB):

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique document chunk ID |
| `embedding` | float[512] | Vector embedding |
| `document` | string | Text content of the chunk |
| `metadata` | JSON | `{source: filename, chunk_index: N, ...}` |

---

## 8. Configuration Reference

### 8.1 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ZHIPUAI_API_KEY` | Yes | — | Zhipu AI API key. Get from https://open.bigmodel.cn/ |
| `http_proxy` | No | — | HTTP proxy for model download (first run only) |
| `https_proxy` | No | — | HTTPS proxy for model download (first run only) |

### 8.2 File-based Configuration

| File | Purpose | Git-tracked |
|------|---------|-------------|
| `.env` | Environment variables (API key, proxy) | No (gitignored) |
| `pyproject.toml` | Python project metadata and dependencies | Yes |
| `data/agent.db` | SQLite conversation history | No (gitignored) |
| `data/chromadb/` | ChromaDB vector index | No (gitignored) |
| `data/uploads/` | Temporary upload staging | No (gitignored) |

### 8.3 Agent Configuration

```python
Agent(
    model=OpenAIChat(
        id="glm-4-flash",                                    # Model identifier
        base_url="https://open.bigmodel.cn/api/paas/v4/",    # API endpoint
        api_key=api_key,                                     # From env var
        temperature=0.7,                                     # Creativity (0-1)
        max_tokens=2048,                                     # Max response length
    ),
    db=sqlite_db,                    # SQLite persistence
    markdown=True,                   # Enable markdown rendering
    add_history_to_context=True,     # Include conversation history in prompts
)
```

---

## 9. Embedding & Vector Search

### 9.1 How Embedding Works

1. **Document Ingestion**: When a document is uploaded, agno's `Knowledge` class splits it into chunks
2. **Embedding Generation**: Each chunk is passed to `FastEmbedEmbedder`, which runs inference locally via ONNX Runtime
3. **Vector Storage**: The 512-dimensional vector + original text + metadata are stored in ChromaDB

### 9.2 How Search Works

1. **Query Embedding**: The user's message is embedded using the same `FastEmbedEmbedder`
2. **Similarity Search**: ChromaDB computes cosine similarity between the query vector and all stored vectors
3. **Top-K Retrieval**: The 5 most similar chunks are returned
4. **Threshold**: No explicit similarity threshold — top-k results are always returned (even if low relevance)

### 9.3 Offline Model Deployment

For servers without internet access:

```bash
# On a machine with internet access
pip install fastembed
python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-zh-v1.5')"

# Archive the downloaded model
tar czf fastembed-cache.tar.gz -C ~/.cache fastembed/

# Transfer and extract on target server
scp fastembed-cache.tar.gz user@server:~/
ssh user@server "mkdir -p ~/.cache && tar xzf fastembed-cache.tar.gz -C ~/.cache/"
```

---

## 10. Error Handling

### 10.1 Error Response Patterns

| Scenario | HTTP Status | Response |
|----------|-------------|----------|
| Missing `message` field | 422 | Pydantic validation error detail |
| Agent exception (API error, timeout) | 500 | `{"detail": "error message"}` |
| Knowledge retrieval failure | — | Silently ignored, falls back to normal chat |
| Invalid session_id | — | Creates new session (graceful handling by agno) |

### 10.2 Knowledge Retrieval Error Handling

The `KnowledgeRetriever.search()` method wraps all operations in a try-except block and returns an empty list on any failure. This ensures that knowledge base errors never prevent the chat from functioning — the system degrades gracefully to non-RAG chat.

```python
def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    try:
        results = self.knowledge.vector_db.search(query=query, limit=limit)
        # ... process results ...
        return docs
    except Exception:
        return []  # Silent fallback
```

### 10.3 File Upload Error Handling

The CLI's `/upload` command handles:
- File not found → user-friendly error message
- Unsupported file type → lists supported formats
- Encoding errors → multi-encoding fallback chain (UTF-8 → GBK → Latin-1)
- Surrogate characters → stripped via `sanitize_text()`
- Upload failure → caught and displayed

---

## 11. Testing Architecture

### 11.1 Test Structure

```
test_agno_agent.py
├── fixtures
│   ├── client()           → TestClient(app)
│   └── mock_agent_response() → Mock(content, session_id, run_id)
│
├── TestHealthEndpoint
│   └── test_health_check
│
├── TestChatEndpoint
│   ├── test_chat_with_message          (mock agent.run)
│   ├── test_chat_with_user_id          (mock agent.run)
│   ├── test_chat_with_session_id       (mock agent.run)
│   ├── test_chat_missing_message       (validation test)
│   ├── test_chat_empty_message         (mock agent.run)
│   ├── test_chat_long_message          (mock agent.run)
│   ├── test_chat_error_handling        (mock agent.run → exception)
│   └── test_chat_auto_knowledge        (mock agent.run, knowledge path)
│
├── TestChatRequestModel
│   ├── test_chat_request_valid
│   ├── test_chat_request_with_optional_fields
│   └── test_chat_request_missing_message
│
├── TestChatResponseModel
│   ├── test_chat_response_valid
│   └── test_chat_response_minimal
│
└── TestAgentConfiguration
    ├── test_agent_has_correct_model
    ├── test_agent_markdown_enabled
    ├── test_agent_has_database
    └── test_agent_no_tools
```

### 11.2 Mocking Strategy

All tests that call `agno_agent.run()` use `@patch.object(agno_agent, 'run')` to intercept the agent call. This:
- Avoids real API calls to Zhipu AI
- Makes tests fast (< 1 second)
- Works without a valid API key
- Tests request/response flow and parameter passing

---

## 12. Deployment Guide

### 12.1 Local Development

```bash
# 1. Clone and install
git clone <repo> && cd agno_demo
uv sync

# 2. Configure
echo "ZHIPUAI_API_KEY=your-key" > .env

# 3. Run
uv run python agno_agent.py        # API server on :7777
uv run python chat_cli.py          # CLI mode
```

### 12.2 Production Considerations

**Current Limitations** (address in future specs):
- No authentication — deploy behind VPN or reverse proxy with auth
- No rate limiting — add nginx rate limiting or implement middleware
- Single-instance only — SQLite does not support concurrent writers
- No HTTPS — add TLS termination at reverse proxy level
- No process management — use systemd, supervisor, or Docker

**Minimal Production Setup**:
```
[Client] → [nginx (TLS + auth + rate limit)] → [uvicorn (agno_agent:app)]
```

**Recommended Directory Permissions**:
```
data/              → 700 (contains DB and vector data)
.env               → 600 (contains API key)
```

### 12.3 Resource Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 1 core | 2+ cores |
| RAM | 512MB | 1GB+ |
| Disk | 500MB | 2GB+ (grows with knowledge base) |
| Network | Internet for GLM API | Internet for GLM API |
| Python | 3.11+ | 3.11+ |

**Note**: The first startup will download the FastEmbed model (~100MB). Subsequent starts use the cached model.
