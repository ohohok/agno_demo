"""知识库管理模块 — 向量检索、文档分块、文本净化"""
import re
import time
import logging
from pathlib import Path
from typing import Dict, Any, List

from agno.knowledge.knowledge import Knowledge
from agno.knowledge.embedder.fastembed import FastEmbedEmbedder
from agno.knowledge.reader.text_reader import TextReader
from agno.knowledge.chunking.document import DocumentChunking
from agno.vectordb.chroma import ChromaDb

from core.config import CHROMA_DIR, UPLOAD_DIR, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS

# 性能日志
perf_logger = logging.getLogger("perf")


# ============ 文本净化工具 ============

def sanitize_text(text: str) -> str:
    """清理文本中的 surrogate 字符和无效 Unicode。"""
    if not text:
        return text
    text = re.sub(r'[\ud800-\udfff]', '', text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text


# ============ 知识库实例创建 ============

def _create_embedder() -> FastEmbedEmbedder:
    return FastEmbedEmbedder(id=EMBEDDING_MODEL, dimensions=EMBEDDING_DIMENSIONS)


def _create_vector_db(embedder: FastEmbedEmbedder) -> ChromaDb:
    return ChromaDb(
        collection="knowledge_base",
        embedder=embedder,
        path=CHROMA_DIR,
        persistent_client=True,
    )


def create_knowledge() -> Knowledge:
    """创建 agno Knowledge 实例，同时被 AgentOS 和工具调用共享"""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    Path(CHROMA_DIR).mkdir(parents=True, exist_ok=True)

    embedder = _create_embedder()
    vector_db = _create_vector_db(embedder)

    return Knowledge(
        name="项目知识库",
        description="上传文档作为 AI 对话的知识库，支持 TXT、MD、PDF、DOCX、CSV 等格式",
        vector_db=vector_db,
    )


# ============ 检索器 ============

class KnowledgeRetriever:
    """知识库检索器 — 聊天时从知识库中检索相关上下文"""

    DEFAULT_RELEVANCE_THRESHOLD = 0.4

    def __init__(self, knowledge: Knowledge, relevance_threshold: float = None):
        self.knowledge = knowledge
        self.relevance_threshold = relevance_threshold or self.DEFAULT_RELEVANCE_THRESHOLD

    def search(self, query: str, limit: int = 5, threshold: float = None) -> List[Dict[str, Any]]:
        t0 = time.perf_counter()
        effective_threshold = threshold if threshold is not None else self.relevance_threshold

        try:
            results = self.knowledge.vector_db.search(query=query, limit=limit)
            if not results:
                perf_logger.info(f"kb_search: 0 results in {(time.perf_counter()-t0)*1000:.1f}ms")
                return []

            docs = []
            for doc in results:
                if not doc or not doc.content:
                    continue
                meta = doc.meta_data or {}
                distance = meta.get("distances")
                similarity = round(1.0 - float(distance), 4) if distance is not None else None
                docs.append({
                    "content": doc.content,
                    "source": doc.name or meta.get("source", "未知"),
                    "chunk_index": meta.get("chunk_index", 0),
                    "score": similarity,
                })

            if effective_threshold > 0:
                before_count = len(docs)
                docs = [d for d in docs if d["score"] is None or d["score"] >= effective_threshold]
                if before_count != len(docs):
                    perf_logger.info(f"kb_filtered: {before_count} -> {len(docs)} results (threshold={effective_threshold})")

            docs.sort(key=lambda d: d.get("score") or 0, reverse=True)

            elapsed = (time.perf_counter() - t0) * 1000
            scores = [f"{d['score']:.3f}" for d in docs if d.get("score") is not None]
            perf_logger.info(f"kb_search: {len(docs)} results in {elapsed:.1f}ms scores=[{', '.join(scores)}]")
            return docs
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            perf_logger.info(f"kb_search: error in {elapsed:.1f}ms: {type(e).__name__}: {e}")
            return []


def create_upload_reader(chunk_size: int = 1500, overlap: int = 200) -> TextReader:
    """创建用于文档上传的自定义 Reader（更小 chunk + overlap）"""
    return TextReader(chunking_strategy=DocumentChunking(chunk_size=chunk_size, overlap=overlap))


# ============ 全局实例 ============
knowledge = create_knowledge()
knowledge_retriever = KnowledgeRetriever(knowledge)
upload_reader = create_upload_reader()
