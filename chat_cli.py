"""
Interactive chat mode for Agno Agent with Zhipu AI (GLM) - 带知识库支持
Run this file to start a conversation with the agent in your terminal
"""
import os
import time
import logging
from pathlib import Path

from dotenv import load_dotenv
from pypdf import PdfReader
from docx import Document as DocxDocument

from agno.agent import Agent
from agno.models.openai import OpenAIChat

from knowledge_base import knowledge, knowledge_retriever, sanitize_text, upload_reader

load_dotenv()

# 性能日志
perf_logger = logging.getLogger("perf")
_perf_handler = logging.StreamHandler()
_perf_handler.setFormatter(logging.Formatter("[PERF] %(message)s"))
perf_logger.addHandler(_perf_handler)
perf_logger.setLevel(logging.INFO)
perf_logger.propagate = False


def create_chat_agent():
    """Create an agent configured for chat with Zhipu AI"""
    api_key = os.getenv("ZHIPUAI_API_KEY")
    if not api_key:
        print("⚠️  Warning: ZHIPUAI_API_KEY environment variable not set!")
        print("   Please set it before running: export ZHIPUAI_API_KEY='your-api-key'")
        print("   Or get your API key from: https://open.bigmodel.cn/")
        api_key = input("\n🔑 Enter your Zhipu AI API key: ").strip()

    return Agent(
        model=OpenAIChat(
            id="glm-4-flash",
            base_url="https://open.bigmodel.cn/api/paas/v4/",
            api_key=api_key,
            temperature=0.7,
            max_tokens=2048,
        )
    )


def interactive_chat():
    """Start an interactive chat session with knowledge base support"""
    print("=" * 60)
    print("🤖 Agno AI Assistant - 交互式聊天模式 (支持知识库)")
    print("=" * 60)
    print("\n💡 命令说明:")
    print("   - 直接输入消息开始聊天（自动检索知识库）")
    print("   - /upload <文件路径>  : 上传文件到知识库（同名文件会自动覆盖旧数据）")
    print("   - /delete <文档名>    : 从知识库删除指定文档")
    print("   - /search <关键词>    : 搜索知识库")
    print("   - /list              : 查看知识库内容")
    print("   - clear              : 清除对话历史")
    print("   - exit / quit / q    : 退出")
    print("   - 使用智谱 AI GLM 模型 (glm-4-flash)")
    print("\n" + "=" * 60)

    agent = create_chat_agent()

    while True:
        try:
            user_input = input("\n👤 You: ").strip()

            if user_input.lower() in ['exit', 'quit', 'q']:
                print("\n👋 再见！祝你愉快！")
                break

            if user_input.lower() == 'clear':
                agent.session_state = {}
                print("\n🗑️ 对话历史已清除！")
                continue

            if user_input.startswith("/"):
                handle_kb_command(user_input)
                continue

            if not user_input:
                continue

            # 自动检索知识库，有结果就用，没结果就正常回答
            t_total = time.perf_counter()
            message = sanitize_text(user_input)
            knowledge_sources = []
            kb_results = knowledge_retriever.search(message, limit=10, threshold=0.4)
            if kb_results:
                context_parts = []
                for i, result in enumerate(kb_results, 1):
                    clean_content = sanitize_text(result['content'])
                    context_parts.append(
                        f"[知识库片段 {i}] (来源: {result['source']})\n{clean_content}"
                    )
                kb_context = "\n\n".join(context_parts)
                message = (
                    f"请优先根据以下知识库内容来回答用户的问题。"
                    f"即使知识库内容只是部分相关，也请结合这些内容给出有帮助的回答。"
                    f"只有当知识库内容确实与问题完全无关时，再基于你自己的知识回答。\n\n"
                    f"=== 知识库内容 ===\n{kb_context}\n=== 知识库内容结束 ===\n\n"
                    f"用户问题: {message}"
                )
                knowledge_sources = list(set(r["source"] for r in kb_results))

            print("\n🤖 Agent is thinking...")
            t_llm = time.perf_counter()
            response = agent.run(message)
            llm_elapsed = (time.perf_counter() - t_llm) * 1000
            total_elapsed = (time.perf_counter() - t_total) * 1000
            perf_logger.info(f"llm_call: {llm_elapsed:.1f}ms | total_chat: {total_elapsed:.1f}ms | kb_used: {bool(kb_results)}")

            if response and response.content:
                print(f"\n🤖 Agent:\n{response.content}")
                if knowledge_sources:
                    print(f"\n📚 参考来源: {', '.join(knowledge_sources)}")
            else:
                print("\n⚠️ Sorry, I couldn't generate a response.")

        except KeyboardInterrupt:
            print("\n\n👋 Interrupted! Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")


def read_file_safe(file_path: Path) -> str:
    """安全读取文件，自动处理编码问题"""
    raw = file_path.read_bytes()
    # 尝试 UTF-8
    try:
        text = raw.decode("utf-8")
        # 检查是否有 surrogate 字符
        if any(0xD800 <= ord(c) <= 0xDFFF for c in text):
            raise UnicodeDecodeError("utf-8", b"", 0, 0, "surrogate found")
        return text
    except UnicodeDecodeError:
        pass
    # 尝试 GBK（中文 Windows 常见编码）
    try:
        return raw.decode("gbk")
    except UnicodeDecodeError:
        pass
    # 兜底：Latin-1 永远不会失败，用 replace 处理无效字节
    return raw.decode("utf-8", errors="replace")


def handle_kb_command(user_input: str):
    """处理知识库相关命令"""
    parts = user_input.split(maxsplit=1)
    cmd = parts[0].lower()

    if cmd == "/upload":
        if len(parts) < 2:
            print("❌ 用法: /upload <文件路径>")
            return
        file_path = Path(parts[1].strip())
        if not file_path.exists():
            print(f"❌ 文件不存在: {file_path}")
            return
        print(f"📤 正在上传并索引: {file_path.name}...")
        try:
            ext = file_path.suffix.lower()
            if ext in (".txt", ".md", ".csv"):
                text = read_file_safe(file_path)
                text = sanitize_text(text)
                # 写入清理后的临时文件
                clean_path = file_path.with_suffix(".clean" + ext)
                clean_path.write_text(text, encoding="utf-8")
                knowledge.insert(path=str(clean_path), name=file_path.name, reader=upload_reader)
                clean_path.unlink()
            elif ext == ".pdf":
                reader = PdfReader(str(file_path))
                text = "\n\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
                text = sanitize_text(text)
                clean_path = file_path.with_suffix(".clean.txt")
                clean_path.write_text(text, encoding="utf-8")
                knowledge.insert(path=str(clean_path), name=file_path.name, reader=upload_reader)
                clean_path.unlink()
            elif ext == ".docx":
                doc = DocxDocument(str(file_path))
                text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
                text = sanitize_text(text)
                clean_path = file_path.with_suffix(".clean.txt")
                clean_path.write_text(text, encoding="utf-8")
                knowledge.insert(path=str(clean_path), name=file_path.name, reader=upload_reader)
                clean_path.unlink()
            else:
                print(f"❌ 不支持的文件类型: {ext}")
                return

            print(f"✅ 文件已上传到知识库")
        except Exception as e:
            print(f"❌ 上传失败: {e}")

    elif cmd == "/search":
        if len(parts) < 2:
            print("❌ 用法: /search <关键词>")
            return
        query = parts[1].strip()
        print(f"🔍 搜索: {query}")
        results = knowledge_retriever.search(query, limit=15, threshold=0.0)  # 搜索时不过滤，显示所有结果
        if results:
            for i, r in enumerate(results, 1):
                score_str = f" [相似度: {r['score']:.3f}]" if r.get('score') is not None else ""
                print(f"\n--- 结果 {i} (来源: {r['source']}){score_str} ---")
                print(r["content"][:200] + ("..." if len(r["content"]) > 200 else ""))
        else:
            print("📭 没有找到相关内容")

    elif cmd == "/delete":
        if len(parts) < 2:
            print("❌ 用法: /delete <文档名>")
            print("   示例: /delete 灯会知识库.md")
            return
        doc_name = parts[1].strip()
        try:
            success = knowledge.remove_vectors_by_name(doc_name)
            if success:
                print(f"✅ 已删除文档: {doc_name}")
            else:
                print(f"❌ 删除失败，未找到文档: {doc_name}")
        except Exception as e:
            print(f"❌ 删除失败: {e}")

    elif cmd == "/list":
        try:
            count = knowledge.vector_db.get_count()
            print(f"📚 知识库信息:")
            print(f"   向量文档块总数: {count}")
        except Exception:
            print("📚 知识库为空或未初始化")

    else:
        print(f"❌ 未知命令: {cmd}")
        print("可用命令: /upload, /delete, /search, /list")


if __name__ == "__main__":
    interactive_chat()
