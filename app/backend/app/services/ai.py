"""AI 辅助建模（设计文档 §14 / 实现决策清单 §5）。
Tripo AI SDK 生成 3D 模型（按点数计费）；无 API Key 时用内置程序化模型模拟。
生成 → 就地打印体检（与 Val1 同源）→ 下载 / 自动填充到上传（照走全部审核）。
"""
from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from ..core.config import settings
from .cost import record_api_usage
from .val1 import run_val1

# 内置程序化模型规格（模拟 Tripo 输出；无 key 时用）
BUILTIN_KINDS = [
    {"key": "花瓶", "kind": "vase", "name": "AI 生成 · 桌面花瓶", "bbox": [55, 55, 110], "volumeCm3": 38, "surfaceCm2": 150, "minWall": 1.8, "overhangPct": 6},
    {"key": "机器人", "kind": "robot", "name": "AI 生成 · 机甲小人", "bbox": [70, 50, 120], "volumeCm3": 74, "surfaceCm2": 260, "minWall": 1.4, "overhangPct": 24},
    {"key": "支架", "kind": "stand", "name": "AI 生成 · 手机支架", "bbox": [90, 70, 40], "volumeCm3": 22, "surfaceCm2": 110, "minWall": 2.0, "overhangPct": 14},
    {"key": "笔筒", "kind": "penholder", "name": "AI 生成 · 六边笔筒", "bbox": [75, 75, 95], "volumeCm3": 52, "surfaceCm2": 230, "minWall": 1.7, "overhangPct": 5},
    {"key": "陀螺", "kind": "spinner", "name": "AI 生成 · 指尖陀螺", "bbox": [90, 90, 7], "volumeCm3": 26, "surfaceCm2": 190, "minWall": 1.5, "overhangPct": 8},
]


def ai_generate(db: Session, description: str, size_cm: float, cfg: dict) -> dict:
    """返回 {kind, name, stats, report, usage}。"""
    if settings.tripo_api_key:
        try:
            r = httpx.post(
                f"{settings.tripo_base_url}/tasks",
                headers={"Authorization": f"Bearer {settings.tripo_api_key}"},
                json={"type": "text_to_model", "prompt": description, "face_limit": 30000},
                timeout=60,
            )
            r.raise_for_status()
            task_id = r.json()["data"]["task_id"]
            usage = record_api_usage(db, "ai_model", "tripo", cfg, points=10, detail=f"tripo task {task_id}")
            return {"kind": "tripo", "name": "AI 生成 · Tripo 3D", "stats": None, "report": None,
                    "usage": {"points": usage.points, "amount": usage.amount}, "taskId": task_id,
                    "note": "Tripo 任务已提交，请在 Tripo 侧查看模型；Demo 阶段建议配置 TRIPO_API_KEY 后联调。"}
        except Exception as e:
            return {"kind": "tripo", "name": "AI 生成 · Tripo 3D", "stats": None, "report": None,
                    "usage": None, "error": f"Tripo 调用失败：{e}"}

    hit = next((k for k in BUILTIN_KINDS if k["key"] in description), None)
    if hit is None:
        hit = {"key": "", "kind": "generic", "name": "AI 生成 · 自定义模型",
               "bbox": [size_cm * 10] * 2 + [size_cm * 12], "volumeCm3": size_cm ** 3 * 0.9,
               "surfaceCm2": size_cm ** 2 * 8, "minWall": 1.6, "overhangPct": 10}
    bbox = [round(v, 1) for v in hit["bbox"]]
    report = run_val1({"closed": True, "manifold": True, "selfIntersect": False, "minWall": hit["minWall"],
                       "overhangPct": hit["overhangPct"], "bbox": bbox,
                       "volumeCm3": hit["volumeCm3"], "surfaceCm2": hit["surfaceCm2"]}, cfg)
    stats = {"volumeCm3": hit["volumeCm3"], "surfaceCm2": hit["surfaceCm2"], "bbox": bbox}
    usage = record_api_usage(db, "ai_model", "tripo", cfg, points=1, detail="内置模拟生成")
    return {"kind": hit["kind"], "name": hit["name"], "stats": stats, "report": report,
            "usage": {"points": usage.points, "amount": usage.amount}}
