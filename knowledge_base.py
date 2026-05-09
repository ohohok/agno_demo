"""
知识库管理模块
- 使用 agno 内置 Knowledge 类，集成到 AgentOS UI
- 提供聊天时的知识库检索增强功能
"""
import os
from pathlib import Path
from typing import Dict, Any, List

from dotenv import load_dotenv
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.embedder.fastembed import FastEmbedEmbedder
from agno.vectordb.chroma import ChromaDb

load_dotenv()

# 配置
CHROMA_DIR = "data/chromadb"
UPLOAD_DIR = Path("data/uploads")

# 本地 Embedding 模型（不依赖任何 API 厂商）
# FastEmbed 使用 ONNX 运行时，体积小（约 100MB），无需 PyTorch
# BAAI/bge-small-zh-v1.5: 中文优化模型，512 维
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
EMBEDDING_DIMENSIONS = 512


def _create_embedder() -> FastEmbedEmbedder:
    """创建本地 FastEmbed embedder"""
    return FastEmbedEmbedder(
        id=EMBEDDING_MODEL,
        dimensions=EMBEDDING_DIMENSIONS,
    )


def _create_vector_db(embedder: FastEmbedEmbedder) -> ChromaDb:
    """创建 ChromaDB 向量数据库实例"""
    return ChromaDb(
        collection="knowledge_base",
        embedder=embedder,
        path=CHROMA_DIR,
        persistent_client=True,
    )


def create_knowledge() -> Knowledge:
    """
    创建 agno Knowledge 实例
    这个实例会被 AgentOS 自动注册到 /knowledge/* 路由，
    可以在 AgentOS UI 中直接操作
    """
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    Path(CHROMA_DIR).mkdir(parents=True, exist_ok=True)

    embedder = _create_embedder()
    vector_db = _create_vector_db(embedder)

    return Knowledge(
        name="项目知识库",
        description="上传文档作为 AI 对话的知识库，支持 TXT、MD、PDF、DOCX、CSV 等格式",
        vector_db=vector_db,
    )


class KnowledgeRetriever:
    """
    知识库检索器 - 用于聊天时从知识库中检索相关上下文
    与 AgentOS 共享同一个 Knowledge 实例和向量数据库
    """

    def __init__(self, knowledge: Knowledge):
        self.knowledge = knowledge

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """在知识库中搜索相关内容"""
        try:
            results = self.knowledge.vector_db.search(query=query, limit=limit)
            if not results:
                return []
            docs = []
            for doc in results:
                if not doc or not doc.content:
                    continue
                meta = doc.meta_data or {}
                docs.append({
                    "content": doc.content,
                    "source": doc.name or meta.get("source", "未知"),
                    "chunk_index": meta.get("chunk_index", 0),
                })
            return docs
        except Exception:
            return []

    def get_context_for_query(self, query: str, limit: int = 5) -> str:
        """获取与查询相关的知识库内容，拼接为上下文字符串"""
        results = self.search(query, limit)
        if not results:
            return ""

        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(
                f"[知识库片段 {i}] (来源: {result['source']})\n{result['content']}"
            )
        return "\n\n".join(context_parts)


# ============ 全局实例 ============
knowledge = create_knowledge()
knowledge_retriever = KnowledgeRetriever(knowledge)
