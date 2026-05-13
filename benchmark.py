"""
性能基准测试脚本
用法:
  1. 启动服务: uv run python main.py
  2. 运行测试: uv run python benchmark.py

输出结果到 benchmark_results/ 目录，方便优化前后对比。
"""
import json
import time
import statistics
from datetime import datetime
from pathlib import Path

import requests

BASE_URL = "http://localhost:7777"
OUTPUT_DIR = Path("benchmark_results")

# 测试用例：覆盖不同场景
TEST_QUERIES = [
    # 简单闲聊（不应触发知识库）
    {"query": "你好", "category": "chitchat", "desc": "简单问候"},
    {"query": "今天天气怎么样", "category": "chitchat", "desc": "闲聊问题"},
    {"query": "谢谢你的帮助", "category": "chitchat", "desc": "感谢回复"},

    # 知识性问题（可能触发知识库，也可能不触发）
    {"query": "什么是人工智能", "category": "knowledge", "desc": "通用知识"},
    {"query": "Python 和 Java 有什么区别", "category": "knowledge", "desc": "技术对比"},

    # 长问题（测试 token 处理速度）
    {"query": "请详细解释一下机器学习中的监督学习、无监督学习和强化学习的区别，"
              "包括它们的典型算法、应用场景和优缺点",
     "category": "long_query", "desc": "长问题"},

    # 多轮对话（测试历史上下文影响）
    {"query": "我叫小明", "category": "multi_turn", "desc": "多轮-第1轮", "session_turn": 1},
    {"query": "我今年25岁", "category": "multi_turn", "desc": "多轮-第2轮", "session_turn": 2},
    {"query": "你还记得我叫什么吗", "category": "multi_turn", "desc": "多轮-第3轮", "session_turn": 3},
    {"query": "我多大了", "category": "multi_turn", "desc": "多轮-第4轮", "session_turn": 4},
]


def wait_for_server(url: str, timeout: int = 30) -> bool:
    """等待服务启动"""
    print(f"⏳ 等待服务启动 ({url})...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{url}/api/health", timeout=3)
            if r.status_code == 200:
                print("✅ 服务已就绪")
                return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(1)
    print("❌ 服务未在超时时间内启动")
    return False


def run_single_query(query_info: dict, session_id: str = None) -> dict:
    """执行单次查询并记录耗时"""
    payload = {"message": query_info["query"]}
    if session_id:
        payload["session_id"] = session_id

    t0 = time.perf_counter()
    try:
        resp = requests.post(
            f"{BASE_URL}/api/chat",
            json=payload,
            timeout=120,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        if resp.status_code == 200:
            data = resp.json()
            return {
                "query": query_info["query"],
                "desc": query_info["desc"],
                "category": query_info["category"],
                "status": "ok",
                "elapsed_ms": round(elapsed_ms, 1),
                "response_len": len(data.get("message", "")),
                "kb_used": bool(data.get("knowledge_sources")),
                "session_id": data.get("session_id"),
                "error": None,
            }
        else:
            return {
                "query": query_info["query"],
                "desc": query_info["desc"],
                "category": query_info["category"],
                "status": "error",
                "elapsed_ms": round(elapsed_ms, 1),
                "response_len": 0,
                "kb_used": False,
                "session_id": None,
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
            }
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return {
            "query": query_info["query"],
            "desc": query_info["desc"],
            "category": query_info["category"],
            "status": "error",
            "elapsed_ms": round(elapsed_ms, 1),
            "response_len": 0,
            "kb_used": False,
            "session_id": None,
            "error": str(e),
        }


def run_benchmark() -> dict:
    """运行完整基准测试"""
    print("=" * 60)
    print("  Agno AI Chat 性能基准测试")
    print("=" * 60)

    results = []
    multi_turn_session_id = None

    for i, query_info in enumerate(TEST_QUERIES, 1):
        # 多轮对话使用同一个 session
        session_id = None
        if query_info["category"] == "multi_turn":
            session_id = multi_turn_session_id

        print(f"\n[{i}/{len(TEST_QUERIES)}] {query_info['desc']}: {query_info['query'][:40]}...")
        result = run_single_query(query_info, session_id)
        results.append(result)

        if result["status"] == "ok":
            print(f"  ✅ {result['elapsed_ms']:.0f}ms | "
                  f"回复 {result['response_len']} 字 | "
                  f"知识库: {'是' if result['kb_used'] else '否'}")
        else:
            print(f"  ❌ {result['error']}")

        # 保存多轮 session
        if query_info["category"] == "multi_turn" and result.get("session_id"):
            multi_turn_session_id = result["session_id"]

        # 请求间间隔，避免限流
        time.sleep(0.5)

    return results


def run_single_stream_query(query_info: dict, session_id: str = None) -> dict:
    """执行单次流式查询，记录 TTFT（首 token 时间）和总时间"""
    payload = {"message": query_info["query"]}
    if session_id:
        payload["session_id"] = session_id

    t0 = time.perf_counter()
    ttft_ms = None
    full_text = ""
    session_id_out = None

    try:
        resp = requests.post(
            f"{BASE_URL}/api/chat/stream",
            json=payload,
            timeout=120,
            stream=True,
        )

        if resp.status_code != 200:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return {
                "query": query_info["query"],
                "desc": query_info["desc"],
                "category": query_info["category"],
                "status": "error",
                "elapsed_ms": round(elapsed_ms, 1),
                "ttft_ms": None,
                "response_len": 0,
                "kb_used": False,
                "session_id": None,
                "error": f"HTTP {resp.status_code}",
            }

        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            data = json.loads(line[6:])

            if data["type"] == "content" and ttft_ms is None:
                ttft_ms = (time.perf_counter() - t0) * 1000

            if data["type"] == "content":
                full_text += data.get("delta", "")

            if data["type"] == "done":
                full_text = data.get("full_text", full_text)
                session_id_out = data.get("session_id")
                kb_used = bool(data.get("knowledge_sources"))

        total_ms = (time.perf_counter() - t0) * 1000

        return {
            "query": query_info["query"],
            "desc": query_info["desc"],
            "category": query_info["category"],
            "status": "ok",
            "elapsed_ms": round(total_ms, 1),
            "ttft_ms": round(ttft_ms, 1) if ttft_ms else None,
            "response_len": len(full_text),
            "kb_used": kb_used,
            "session_id": session_id_out,
            "error": None,
        }

    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return {
            "query": query_info["query"],
            "desc": query_info["desc"],
            "category": query_info["category"],
            "status": "error",
            "elapsed_ms": round(elapsed_ms, 1),
            "ttft_ms": None,
            "response_len": 0,
            "kb_used": False,
            "session_id": None,
            "error": str(e),
        }


def run_stream_benchmark() -> list:
    """运行流式接口基准测试，对比 TTFT"""
    print("\n" + "=" * 60)
    print("  流式接口基准测试 (TTFT 测量)")
    print("=" * 60)

    results = []
    multi_turn_session_id = None

    for i, query_info in enumerate(TEST_QUERIES, 1):
        session_id = None
        if query_info["category"] == "multi_turn":
            session_id = multi_turn_session_id

        print(f"\n[{i}/{len(TEST_QUERIES)}] {query_info['desc']}: {query_info['query'][:40]}...")
        result = run_single_stream_query(query_info, session_id)
        results.append(result)

        if result["status"] == "ok":
            ttft = f"{result['ttft_ms']:.0f}ms" if result.get("ttft_ms") else "N/A"
            print(f"  ✅ TTFT: {ttft} | "
                  f"总耗时: {result['elapsed_ms']:.0f}ms | "
                  f"回复 {result['response_len']} 字")
        else:
            print(f"  ❌ {result['error']}")

        if query_info["category"] == "multi_turn" and result.get("session_id"):
            multi_turn_session_id = result["session_id"]

        time.sleep(0.5)

    return results


def generate_stream_report(results: list) -> str:
    """生成流式测试报告（含 TTFT）"""
    ok_results = [r for r in results if r["status"] == "ok"]
    if not ok_results:
        return "没有成功的流式测试结果"

    ttfts = [r["ttft_ms"] for r in ok_results if r.get("ttft_ms")]
    totals = [r["elapsed_ms"] for r in ok_results]

    lines = []
    lines.append("=" * 60)
    lines.append("  流式接口测试报告 (含 TTFT)")
    lines.append("=" * 60)
    lines.append(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  总请求数: {len(results)} | 成功: {len(ok_results)}")
    lines.append("")
    if ttfts:
        lines.append("  首 Token 响应时间 TTFT (ms):")
        lines.append(f"    平均: {statistics.mean(ttfts):.0f}")
        lines.append(f"    中位: {statistics.median(ttfts):.0f}")
        lines.append(f"    最小: {min(ttfts):.0f}")
        lines.append(f"    最大: {max(ttfts):.0f}")
    lines.append("")
    lines.append("  总耗时 (ms):")
    lines.append(f"    平均: {statistics.mean(totals):.0f}")
    lines.append(f"    中位: {statistics.median(totals):.0f}")
    lines.append("")
    lines.append("  详细结果:")
    lines.append(f"  {'序号':>4}  {'类别':12}  {'TTFT(ms)':>10}  {'总耗时(ms)':>10}  {'回复字数':>8}  描述")
    lines.append("  " + "-" * 80)
    for i, r in enumerate(results, 1):
        ttft = f"{r['ttft_ms']:.0f}" if r.get("ttft_ms") else "N/A"
        lines.append(
            f"  {i:>4}  {r['category']:12}  {ttft:>10}  "
            f"{r['elapsed_ms']:>10.0f}  {r['response_len']:>8}  {r['desc']}"
        )
    lines.append("=" * 60)
    return "\n".join(lines)


def generate_report(results: list) -> str:
    """生成可读的测试报告"""
    ok_results = [r for r in results if r["status"] == "ok"]
    if not ok_results:
        return "没有成功的测试结果"

    times = [r["elapsed_ms"] for r in ok_results]
    lines = []
    lines.append("=" * 60)
    lines.append("  测试报告摘要")
    lines.append("=" * 60)
    lines.append(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  总请求数: {len(results)} | 成功: {len(ok_results)} | 失败: {len(results)-len(ok_results)}")
    lines.append("")
    lines.append("  耗时统计 (ms):")
    lines.append(f"    平均: {statistics.mean(times):.0f}")
    lines.append(f"    中位: {statistics.median(times):.0f}")
    lines.append(f"    最小: {min(times):.0f}")
    lines.append(f"    最大: {max(times):.0f}")
    if len(times) > 1:
        lines.append(f"    标准差: {statistics.stdev(times):.1f}")
    lines.append("")

    # 按类别统计
    categories = {}
    for r in ok_results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r["elapsed_ms"])

    lines.append("  按类别统计:")
    for cat, cat_times in categories.items():
        lines.append(f"    {cat:15s}  平均 {statistics.mean(cat_times):6.0f}ms  (n={len(cat_times)})")
    lines.append("")

    # 详细结果
    lines.append("  详细结果:")
    lines.append(f"  {'序号':>4}  {'类别':12}  {'耗时(ms)':>10}  {'回复字数':>8}  {'知识库':>6}  描述")
    lines.append("  " + "-" * 75)
    for i, r in enumerate(results, 1):
        status = "✅" if r["status"] == "ok" else "❌"
        kb = "是" if r["kb_used"] else "否"
        lines.append(
            f"  {i:>4}  {r['category']:12}  {r['elapsed_ms']:>10.0f}  "
            f"{r['response_len']:>8}  {kb:>6}  {r['desc']}"
        )
    lines.append("=" * 60)

    return "\n".join(lines)


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    if not wait_for_server(BASE_URL):
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1. 非流式基准测试
    results = run_benchmark()

    data_file = OUTPUT_DIR / f"benchmark_{timestamp}.json"
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump({"timestamp": timestamp, "mode": "blocking", "results": results},
                  f, ensure_ascii=False, indent=2)
    print(f"\n📁 原始数据已保存: {data_file}")

    report = generate_report(results)
    report_file = OUTPUT_DIR / f"report_{timestamp}.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"📁 测试报告已保存: {report_file}")
    print(f"\n{report}")

    # 2. 流式基准测试（TTFT）
    stream_results = run_stream_benchmark()

    stream_data_file = OUTPUT_DIR / f"benchmark_stream_{timestamp}.json"
    with open(stream_data_file, "w", encoding="utf-8") as f:
        json.dump({"timestamp": timestamp, "mode": "stream", "results": stream_results},
                  f, ensure_ascii=False, indent=2)
    print(f"\n📁 流式原始数据已保存: {stream_data_file}")

    stream_report = generate_stream_report(stream_results)
    stream_report_file = OUTPUT_DIR / f"report_stream_{timestamp}.txt"
    with open(stream_report_file, "w", encoding="utf-8") as f:
        f.write(stream_report)
    print(f"📁 流式测试报告已保存: {stream_report_file}")
    print(f"\n{stream_report}")


if __name__ == "__main__":
    main()
