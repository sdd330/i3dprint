# E3DP backend — 云端切片并发门控（方案 A：信号量限流 + 排队统计）
# 同时最多 slicer_max_concurrent 个 OrcaSlicer 子进程（软件设置可配，默认 2）
# 超出者阻塞排队；队列统计供前端展示「排队前还有 N 个」

import threading

from ..core.dynamic_settings import get_setting

_cond = threading.Condition()
_active = 0
_waiters = 0


def acquire_slice_slot() -> None:
    """获取切片执行名额；并发满时阻塞排队（FIFO 由 Condition 保证）"""
    global _active, _waiters
    with _cond:
        max_c = int(get_setting("slicer_max_concurrent", 2) or 2)
        _waiters += 1
        try:
            _cond.wait_for(lambda: _active < max_c)
        finally:
            _waiters -= 1
        _active += 1


def release_slice_slot() -> None:
    global _active
    with _cond:
        _active -= 1
        _cond.notify()


def slice_queue_stats() -> dict:
    """{active 执行中, waiting 排队中, max 并发上限}"""
    with _cond:
        max_c = int(get_setting("slicer_max_concurrent", 2) or 2)
        return {"active": _active, "waiting": max(0, _waiters), "max": max_c}
