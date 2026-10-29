# E3DP backend — 原生 STL 解析器的 Python 绑定（ctypes）
#
# 实现：native/stl_fast.c（C99，mmap 零拷贝 + 基数排序，思路对照 OrcaSlicer/admesh）
# 绑定：本模块把 C 结构体映射为与 fast_loader/val1 相同的 stats 字典
#
# 设计约束：
#   · 库缺失时**不报错**：`analyze()` 返回 None，上层自动回退 numpy 实现（fast_loader）
#   · 首次调用时若检测到编译器，会尝试自动编译一次（约 0.3s），之后复用产物
#   · 手动编译：`cd app/backend/native && ./build.sh`

from __future__ import annotations

import ctypes
import logging
import os
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

NATIVE_DIR = Path(__file__).resolve().parents[2] / "native"  # backend/native
LIB_NAMES = ("libstl_fast.dylib", "libstl_fast.so")

FLAG_BINARY = 1 << 0
FLAG_CLOSED = 1 << 1
FLAG_MANIFOLD = 1 << 2
FLAG_TOPOLOGY_SKIPPED = 1 << 3
FLAG_NAN_SKIPPED = 1 << 4


class _Result(ctypes.Structure):
    _fields_ = [
        ("face_count", ctypes.c_int32),
        ("vertex_count", ctypes.c_int32),
        ("flags", ctypes.c_int32),
        ("reserved", ctypes.c_int32),
        ("bbox", ctypes.c_double * 3),
        ("area", ctypes.c_double),
        ("volume", ctypes.c_double),
        ("overhang_pct", ctypes.c_double),
        ("wall", ctypes.c_double),
        ("elapsed_ms", ctypes.c_double),
        ("error", ctypes.c_char * 256),
    ]


_lib = None
_load_error: str | None = None
_build_attempted = False


def _find_lib() -> Path | None:
    for name in LIB_NAMES:
        p = NATIVE_DIR / name
        if p.exists():
            return p
    return None


def _try_build() -> None:
    """首次使用时尝试编译一次（有编译器才做；失败静默，回退 numpy）。"""
    global _build_attempted
    if _build_attempted:
        return
    _build_attempted = True
    script = NATIVE_DIR / "build.sh"
    if not script.exists() or not shutil.which("cc"):
        return
    try:
        subprocess.run(["sh", str(script)], cwd=str(NATIVE_DIR), check=True,
                       capture_output=True, timeout=120)
        log.info("native stl_fast 已编译：%s", _find_lib())
    except Exception as e:  # 编译环境缺失不影响业务
        log.warning("native stl_fast 编译失败（将使用 numpy 回退）：%s", e)


def _load():
    global _lib, _load_error
    if _lib is not None or _load_error is not None:
        return _lib
    path = _find_lib()
    if path is None:
        _try_build()
        path = _find_lib()
    if path is None:
        _load_error = "native lib 不存在"
        return None
    try:
        lib = ctypes.CDLL(str(path))
        lib.stl_fast_analyze.argtypes = [ctypes.c_char_p, ctypes.POINTER(_Result)]
        lib.stl_fast_analyze.restype = ctypes.c_int
        lib.stl_fast_version.restype = ctypes.c_char_p
        _lib = lib
        return _lib
    except Exception as e:
        _load_error = f"加载失败：{e}"
        log.warning("native stl_fast 加载失败（将使用 numpy 回退）：%s", e)
        return None


def available() -> bool:
    return _load() is not None


def version() -> str | None:
    lib = _load()
    if lib is None:
        return None
    try:
        return lib.stl_fast_version().decode()
    except Exception:
        return None


def analyze(path: str | os.PathLike, *, max_faces_hint: int = 0) -> dict | None:
    """调用 C 解析器 → stats 字典（与 fast_loader.analyze_indexed 同口径）。

    返回 None 表示原生库不可用或解析失败，调用方应回退 numpy 实现。
    """
    lib = _load()
    if lib is None:
        return None
    res = _Result()
    try:
        rc = lib.stl_fast_analyze(os.fsencode(str(path)), ctypes.byref(res))
    except Exception as e:  # 段错误防护：ctypes 调用异常
        log.warning("native stl_fast 调用异常：%s", e)
        return None
    if rc != 0:
        err = bytes(res.error).split(b"\x00", 1)[0].decode("utf-8", "replace")
        log.info("native stl_fast 解析失败（%s）：%s", rc, err)
        return None
    if res.face_count <= 0:
        return None

    closed = bool(res.flags & FLAG_CLOSED)
    manifold = bool(res.flags & FLAG_MANIFOLD)
    wall = round(res.wall, 2) if res.wall >= 0 else None
    report = {
        "volume_cm3": round(res.volume / 1000.0, 2),
        "surface_cm2": round(res.area / 100.0, 1),
        "bbox": [round(float(res.bbox[i]), 1) for i in range(3)],
        "closed": closed,
        "manifold": manifold,
        "self_intersect": False,
        "face_count": int(res.face_count),
        "overhang_pct": round(res.overhang_pct, 1),
        "min_wall": wall,
        "wall_source": "mean_2v_a" if wall is not None else None,
        "parse_mode": "native_c",
        "parse_ms": round(res.elapsed_ms, 1),
        "vertex_count": int(res.vertex_count),
    }
    if res.flags & FLAG_NAN_SKIPPED:
        report["nan_facets_skipped"] = True
    if res.flags & FLAG_TOPOLOGY_SKIPPED:
        report["topology_note"] = f"面数 {res.face_count:,} 超过拓扑检查上限，已跳过封闭/流形检查"
    return report
