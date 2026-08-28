# E3DP backend — 打印服务模块（决策清单 §12：独立、可扩展）
# Order → PrintJob → PrintQueue → Provider(Printer)；订单侧只依赖 PrintService 接口

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


# 设备注册表（demo：2 台 X1C；拓竹 Provider 接入后在此扩展）
PRINTERS = [
    {"id": "x1c-01", "name": "X1C-01", "model": "Bambu Lab X1-Carbon", "status": "idle", "job_id": None,
     "build_volume": {"x": 256, "y": 256, "z": 256}},
    {"id": "x1c-02", "name": "X1C-02", "model": "Bambu Lab X1-Carbon", "status": "idle", "job_id": None,
     "build_volume": {"x": 256, "y": 256, "z": 256}},
]

# 当前激活 Provider（可配置切换）
_provider: PrintProvider = MockPrintProvider()


def get_provider() -> PrintProvider:
    return _provider


def progress(job: PrintJob) -> float | None:
    """打印进度 0-1（由开始时间推算，模拟实现）"""
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


def find_idle_printer() -> dict | None:
    return next((p for p in PRINTERS if p["status"] == "idle"), None)


def allocate(job: PrintJob, printer: dict) -> None:
    printer["status"] = "busy"
    printer["job_id"] = job.id
    job.printer_id = printer["id"]
    from datetime import datetime
    job.started_at = datetime.utcnow().isoformat(timespec="seconds")


def release(printer_id: str) -> None:
    for p in PRINTERS:
        if p["id"] == printer_id:
            p["status"] = "idle"
            p["job_id"] = None
