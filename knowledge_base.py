"""
知识库管理模块
- 使用 agno 内置 Knowledge 类，集成到 AgentOS UI
- 提供聊天时的知识库检索增强功能
"""
import os
import re
import time
import logging
from pathlib import Path
from typing import Dict, Any, List

from dotenv import load_dotenv
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.embedder.fastembed import FastEmbedEmbedder
from agno.knowledge.reader.text_reader import TextReader
from agno.knowledge.chunking.document import DocumentChunking
from agno.vectordb.chroma import ChromaDb

load_dotenv()

# 性能日志
perf_logger = logging.getLogger("perf")
_perf_handler = logging.StreamHandler()
_perf_handler.setFormatter(logging.Formatter("[PERF] %(message)s"))
perf_logger.addHandler(_perf_handler)
perf_logger.setLevel(logging.INFO)
perf_logger.propagate = False

# 配置
CHROMA_DIR = "data/chromadb"
UPLOAD_DIR = Path("data/uploads")


# ============ 文本净化工具 ============

def sanitize_text(text: str) -> str:
    """
    清理文本中的 surrogate 字符和无效 Unicode。
    适用场景：文档上传、LLM 上下文注入前的文本安全处理。
    """
    if not text:
        return text
    # 1. 移除 surrogate 范围的字符 (U+D800-U+DFFF)
    text = re.sub(r'[\ud800-\udfff]', '', text)
    # 2. 移除其他可能引起编码问题的控制字符（保留换行和制表符）
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text

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

    # 相似度阈值：余弦距离转相似度 = 1 - distance
    # 低于此阈值的检索结果视为不相关，不注入上下文
    # 0.4 意味着接受余弦距离 <= 0.6 的结果，稍微放宽以捕获更多相关内容
    DEFAULT_RELEVANCE_THRESHOLD = 0.4

    def __init__(self, knowledge: Knowledge, relevance_threshold: float = None):
        self.knowledge = knowledge
        self.relevance_threshold = relevance_threshold or self.DEFAULT_RELEVANCE_THRESHOLD

    def search(self, query: str, limit: int = 5, threshold: float = None) -> List[Dict[str, Any]]:
        """
        在知识库中搜索相关内容。

        Args:
            query: 搜索查询
            limit: 返回结果数量
            threshold: 相似度阈值 (0~1)，低于此值的结果会被过滤。
                       传 None 使用 self.relevance_threshold。

        Returns:
            按相似度降序排列的文档列表，每个元素包含 content, source, score 等字段。
            如果所有结果都低于阈值，返回空列表。
        """
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

                # 从 meta_data 提取余弦距离，转为相似度分数
                distance = meta.get("distances")
                similarity = round(1.0 - float(distance), 4) if distance is not None else None

                docs.append({
                    "content": doc.content,
                    "source": doc.name or meta.get("source", "未知"),
                    "chunk_index": meta.get("chunk_index", 0),
                    "score": similarity,
                })

            # 过滤低于阈值的结果
            if effective_threshold > 0:
                before_count = len(docs)
                docs = [d for d in docs if d["score"] is None or d["score"] >= effective_threshold]
                if before_count != len(docs):
                    perf_logger.info(
                        f"kb_filtered: {before_count} -> {len(docs)} results "
                        f"(threshold={effective_threshold})"
                    )

            # 按相似度降序排列
            docs.sort(key=lambda d: d.get("score") or 0, reverse=True)

            elapsed = (time.perf_counter() - t0) * 1000
            scores = [f"{d['score']:.3f}" for d in docs if d.get("score") is not None]
            perf_logger.info(
                f"kb_search: {len(docs)} results in {elapsed:.1f}ms "
                f"scores=[{', '.join(scores)}]"
            )
            return docs
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            perf_logger.info(f"kb_search: error in {elapsed:.1f}ms: {type(e).__name__}: {e}")
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


def create_upload_reader(chunk_size: int = 1500, overlap: int = 200) -> TextReader:
    """
    创建用于文档上传的自定义 Reader，使用更小的 chunk_size 和 overlap。
    默认 5000 字符的 chunk 太大，对于大文档（50KB+）会导致检索不到特定段落。
    1500 字符 ≈ 300-500 个中文字，适合语义检索的粒度。
    200 字符 overlap 防止段落边界信息丢失。
    """
    return TextReader(
        chunking_strategy=DocumentChunking(chunk_size=chunk_size, overlap=overlap),
    )


# ============ 全局实例 ============
knowledge = create_knowledge()
knowledge_retriever = KnowledgeRetriever(knowledge)
upload_reader = create_upload_reader()
