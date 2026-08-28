# E3DP backend — 几何分析子进程执行器
# 为什么必须子进程：trimesh 的 is_watertight / raycast 等操作持有 GIL，
# 线程池超时无法终止运行中的线程——一个病态大网格会把整个 uvicorn 进程卡死。
# 方案：spawn 独立进程执行分析，超时直接 terminate，与主进程完全隔离。

from __future__ import annotations

import multiprocessing as mp

# macOS 默认 spawn；Linux 上 spawn 也最干净（避免 fork 污染 uvicorn 状态）
_ctx = mp.get_context("spawn")


def _analyze_entry(path: str, q):
    """子进程入口：执行分析，结果经 Queue 回传（analyze_file 失败返回降级报告，不抛异常）"""
    from .val1 import analyze_file
    try:
        q.put(("ok", analyze_file(path)))
    except Exception as e:  # 兜底：任何异常都回传错误，不让子进程静默死掉
        q.put(("err", str(e)[:300]))


def analyze_with_timeout(path: str, timeout_sec: int) -> dict:
    """在独立子进程执行几何分析；超时 terminate 子进程并返回明确错误。

    每次调用一个临时进程：spawn 启动约 1-2s，换取与大网格分析完全隔离
    （GIL 被 C 扩展持有时主进程不受影响，其他请求正常响应）。
    """
    q = _ctx.Queue()
    proc = _ctx.Process(target=_analyze_entry, args=(path, q), daemon=True)
    proc.start()
    try:
        kind, payload = q.get(timeout=timeout_sec)
        proc.join(timeout=5)
        if kind == "ok":
            return payload
        return {"error": f"模型几何分析失败：{payload}"}
    except mp.queues.Empty:
        proc.terminate()
        proc.join(timeout=5)
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=5)
        return {"error": f"模型几何分析超时（>{timeout_sec}s），已强制终止，请使用面数较少的模型或稍后重试"}
