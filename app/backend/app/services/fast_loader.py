# E3DP backend — 快速 OBJ 解析器（numpy 向量化，跨平台，无 C 扩展依赖）
# 背景：trimesh OBJ loader 对 197 万面大文件耗时 ~10s；本模块批量解析压到 ~4s
# （接近 BambuStudio C++ 载入量级）。只提取顶点/面（几何检查所需），忽略材质/法线/纹理。

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

_V_PAT = re.compile(rb"^v[ \t]+(-?[\d.eE+]+)[ \t]+(-?[\d.eE+]+)[ \t]+(-?[\d.eE+]+)", re.M)
_F_PAT = re.compile(rb"^f[ \t]+(.+)$", re.M)
# 去掉 "1/2/3" 或 "1//2" 中的法线/纹理索引部分（保留顶点索引）
_VIDX_STRIP = re.compile(rb"/[-0-9]+(?:/[-0-9]+)?")


def load_obj_vertices_faces(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """解析 OBJ → (vertices Nx3 float64, faces Mx3 int64 0-based)。

    策略：一次性 read + splitlines（C 级）+ 前缀过滤 → v 行整块 np.fromstring；
    f 行整块正则清洗（去 / 后缀）→ 三角形批量 reshape，多边形行兜底 fan 三角化。
    """
    data = Path(path).read_bytes()
    lines = data.splitlines()

    v_rows: list[bytes] = []
    f_rows: list[bytes] = []
    for ln in lines:
        if ln.startswith(b"v "):
            v_rows.append(ln[2:])
        elif ln.startswith(b"f "):
            f_rows.append(ln[2:])
    if not v_rows:
        raise ValueError("OBJ 中没有顶点（v）数据")
    if not f_rows:
        raise ValueError("OBJ 中没有面（f）数据")

    verts = np.fromstring(b"\n".join(v_rows), sep=" ", dtype=np.float64).reshape(-1, 3)

    # f 行：整块清洗（一次正则）→ 按行统计顶点数 → 三角批量 / 多边形兜底
    f_clean = _VIDX_STRIP.sub(b"", b"\n".join(f_rows))
    clean_lines = f_clean.splitlines()
    counts = np.array([ln.count(b" ") + 1 for ln in clean_lines], dtype=np.int64)
    tri_idx = np.where(counts == 3)[0]
    poly_idx = np.where(counts != 3)[0]

    if len(tri_idx):
        tri_faces = np.fromstring(b"\n".join(clean_lines[i] for i in tri_idx), sep=" ", dtype=np.int64).reshape(-1, 3)
    else:
        tri_faces = np.empty((0, 3), dtype=np.int64)

    poly_faces_list = []
    for i in poly_idx:
        toks = clean_lines[i].split()
        a, b = int(toks[0]), int(toks[1])
        for t in toks[2:]:
            c = int(t)
            poly_faces_list.append((a, b, c))
            b = c
    if poly_faces_list:
        poly_faces = np.array(poly_faces_list, dtype=np.int64)
        faces = np.vstack([tri_faces, poly_faces])
    else:
        faces = tri_faces

    faces -= 1  # OBJ 1-based → 0-based
    valid = (faces >= 0).all(axis=1) & (faces < len(verts)).all(axis=1)
    faces = faces[valid]
    if len(faces) == 0:
        raise ValueError("OBJ 面索引全部越界")
    return verts, faces


def fast_analyze_obj(path: str | Path) -> dict | None:
    """快速 OBJ 几何分析（供 analyze_file 分派）；解析失败返回 None 由调用方回退 trimesh。"""
    try:
        import trimesh
        from .val1 import analyze_mesh
        vertices, faces = load_obj_vertices_faces(path)
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        return analyze_mesh(mesh)
    except Exception:
        return None
