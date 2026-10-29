# E3DP backend — 打印服务模块（决策清单 §12：独立、可扩展）
# Order → PrintJob → PrintQueue → Provider(Printer)；订单侧只依赖 PrintService 接口
#
# 2026-10：打印机改为**配置中心可配**（活动配置 `print.printers`，可增删/启用禁用），
# 本模块只维护"运行时状态"（忙/闲、当前任务），不再写死设备清单。

from __future__ import annotations

from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

from ..models import PrintJob


class PrintProvider(ABC):
    """打印执行 Provider 接口：未来接入拓竹 LAN 协议（POC 后），多厂商可扩展"""

    name: str = "abstract"

    @abstractmethod
    def submit(self, job: PrintJob) -> None: ...

    @abstractmethod
    def cancel(self, job: PrintJob) -> None: ...

    @abstractmethod
    def status(self, job: PrintJob) -> str: ...


class MockPrintProvider(PrintProvider):
    """首版模拟实现：状态机驱动（排队/打印中/完成/异常重排），进度按时间推算"""

    name = "mock"

    def submit(self, job: PrintJob) -> None:
        job.status = "queued"

    def cancel(self, job: PrintJob) -> None:
        job.status = "queued"

    def status(self, job: PrintJob) -> str:
        return job.status


# 未配置时的兜底设备（配置中心 `print.printers` 存在时以配置为准）
DEFAULT_PRINTERS = [
    {"id": "x1c-01", "name": "X1C-01", "model": "Bambu Lab X1-Carbon", "enabled": True},
    {"id": "x1c-02", "name": "X1C-02", "model": "Bambu Lab X1-Carbon", "enabled": True},
]

# 运行时状态（进程内存）：printer_id → {"status": "idle"|"busy", "job_id": int|None}
# 注意：这里只存"当下占用情况"，设备清单本身在配置中心，重启后自动重新读配置。
_state: dict[str, dict] = {}

# 当前激活 Provider（可配置切换）
_provider: PrintProvider = MockPrintProvider()


def get_provider() -> PrintProvider:
    return _provider


def configured_printers(cfg: dict | None) -> list[dict]:
    """从活动配置读取启用的打印机（id/name/model）；未配置则用兜底清单。"""
    raw = ((cfg or {}).get("print") or {}).get("printers")
    if not raw:
        raw = DEFAULT_PRINTERS
    out = []
    for p in raw:
        if not isinstance(p, dict):
            continue
        if p.get("enabled") is False:
            continue
        pid = (p.get("id") or "").strip()
        if not pid:
            continue
        out.append({"id": pid, "name": (p.get("name") or pid).strip(), "model": p.get("model") or ""})
    return out


def printer_snapshot(cfg: dict | None = None) -> list[dict]:
    """设备清单 + 运行时状态 + 打印范围（供 /admin/queues、/api/printers、meta 使用）。"""
    bv = ((cfg or {}).get("val1") or {}).get("build_volume") or {"x": 256, "y": 256, "z": 256}
    out = []
    for p in configured_printers(cfg):
        st = _state.get(p["id"], {"status": "idle", "job_id": None})
        out.append({**p, "status": st["status"], "job_id": st["job_id"], "build_volume": bv})
    return out


def find_idle_printer(cfg: dict | None = None) -> dict | None:
    return next((p for p in printer_snapshot(cfg) if p["status"] == "idle"), None)


def progress(job: PrintJob) -> float | None:
    """打印进度 0-1（由开始时间与预计时长推算，模拟实现）"""
    if job.status != "printing" or not job.started_at:
        return None
    from datetime import datetime
    import time
    try:
        start = datetime.fromisoformat(job.started_at).timestamp()
    except ValueError:
        return None
    elapsed = time.time() - start
    return min(0.99, elapsed / job.est_time_sec) if job.est_time_sec else None


def allocate(job: PrintJob, printer: dict) -> None:
    _state[printer["id"]] = {"status": "busy", "job_id": job.id}
    job.printer_id = printer["id"]
    from datetime import datetime
    job.started_at = datetime.utcnow().isoformat(timespec="seconds")


def release(printer_id: str) -> None:
    if printer_id in _state:
        _state[printer_id] = {"status": "idle", "job_id": None}
