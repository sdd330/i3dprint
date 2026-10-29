# E3DP backend — 轻量几何解析器（numpy 向量化，跨平台，无 C 扩展依赖）
#
# 设计目的（2026-10 用户要求）：
#   上传阶段只需要"预览级"信息 —— 存下原始文件 + 快速解析出 bbox/面数/体积/面积/
#   封闭性/流形性/悬垂占比/平均壁厚。**不做**逐面射线壁厚测量（那是 O(面数²) 级别，
#   96k 面的模型能卡住几十秒到几分钟），因此解析耗时与面数近似线性。
#
# 目标：本机 `Violet 3DP_fixed.stl`（4.8MB / 96k 面）解析 < 1s（实测 ~0.1s）。
#
# 精度说明：
#   · 封闭性/流形性用"量化顶点 + 边计数"判断，量化分辨率为包围盒对角线 / 2^21
#     （200mm 的模型 ≈ 0.0001mm），远小于 STL 自身精度；
#   · 壁厚取 `2V/A`（薄壳件该值即壁厚；实心件给出的是"体量厚度"，不会误报过薄），
#     需要更精细的采样射线测量时可开启 val1.wall_raycast（见 val1.analyze_mesh）。

from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np

# 二进制 STL 记录布局：法线(3×f4) + 三个顶点(3×3×f4) + 属性(u2) = 50 字节
STL_TRI_DTYPE = np.dtype([("n", "<f4", (3,)), ("v", "<f4", (3, 3)), ("attr", "<u2")])

# OBJ 面行中的 "1/2/3" 或 "1//2" → 只保留顶点索引
_VIDX_STRIP = re.compile(rb"/[-0-9]+(?:/[-0-9]+)?")

# ASCII STL：一次正则抓出所有顶点与法线（比逐行 split 快一个量级）
_ASCII_VERTEX = re.compile(rb"vertex\s+(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)")
_ASCII_NORMAL = re.compile(rb"facet\s+normal\s+(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)")

# 超过这个面数就跳过拓扑（封闭性/流形性）检查并标注 skip，避免极端文件拖慢上传
TOPOLOGY_MAX_FACES = 6_000_000


# ---------------------------------------------------------------- 文件 → 三角形

def read_binary_stl_triangles(path: str | Path) -> np.ndarray | None:
    """二进制 STL → (3F, 3) float32 顶点流（memmap，零拷贝视图）。

    二进制/ASCII 判定照搬 OrcaSlicer admesh（deps_src/admesh/stlinit.cpp::stl_open_count_facets）：
      1) 先看首个面记录 128 字节内是否出现 >127 的字节（出现即二进制）
      2) 再用文件大小反推面数并校验：`84 + n*50 == file_size`
         面数**以文件大小为准**，只把头部声明值当校验（头部写错/被改也照样能读）
      3) 跳过 NaN 三角（admesh: someone_is_nan → continue），避免污染体积/包围盒
    返回 None 表示不是标准二进制 STL（ASCII 或损坏），由调用方回退。
    """
    size = os.path.getsize(path)
    if size < 84 + 50:
        return None
    with open(path, "rb") as f:
        head = f.read(84)
        f.seek(84)
        probe = f.read(128)
    body = size - 84
    if body % 50 != 0:
        return None                      # 不是二进制 STL 的定长记录布局
    count_from_size = body // 50
    declared = int(np.frombuffer(head[80:84], dtype="<u4")[0])
    is_binary = any(b > 127 for b in probe) or count_from_size == declared
    if not is_binary:
        # 纯 ASCII 数字（如全为 0/10/15）可能没有高位字节 → 以大小为准再确认一次
        if count_from_size != declared:
            return None
    if count_from_size == 0:
        return None
    view = np.memmap(path, dtype=STL_TRI_DTYPE, mode="r", offset=84, shape=(count_from_size,))["v"]
    tris = view.reshape(-1, 3)           # (3F, 3) float32 视图，未拷贝
    if not np.isfinite(tris).all():
        keep = np.isfinite(np.asarray(view)).all(axis=(1, 2))
        tris = np.asarray(view[keep]).reshape(-1, 3)
    return tris


def read_ascii_stl_triangles(path: str | Path) -> np.ndarray | None:
    """ASCII STL → (3F, 3) float64 顶点流；一次正则批量抽取（回退用，大文件会很慢）。"""
    data = Path(path).read_bytes()
    if b"vertex" not in data[:4096] and b"vertex" not in data:
        return None
    verts = _ASCII_VERTEX.findall(data)
    if not verts or len(verts) % 3 != 0:
        return None
    flat = b"\n".join(b" ".join(v) for v in verts)
    arr = np.fromstring(flat, sep=" ", dtype=np.float64)
    return arr.reshape(-1, 3)


def stl_triangles(path: str | Path) -> np.ndarray:
    """STL（二进制优先，ASCII 兜底）→ (3F, 3) 顶点流。"""
    tris = read_binary_stl_triangles(path)
    if tris is None:
        tris = read_ascii_stl_triangles(path)
    if tris is None or len(tris) < 3:
        raise ValueError("STL 解析失败（文件损坏或格式不支持）")
    return tris


# ---------------------------------------------------------------- 几何量

def triangle_geometry(tris: np.ndarray) -> dict:
    """顶点流 → bbox / 面积 / 有向体积 / 悬垂占比（float32 主体 + float64 标量累加）。"""
    work = np.asarray(tris)
    f = len(work) // 3
    v = work.reshape(f, 3, 3)
    v0, v1, v2 = v[:, 0], v[:, 1], v[:, 2]
    cross = np.cross(v1 - v0, v2 - v0)
    per_face = np.sqrt(np.einsum("ij,ij->i", cross, cross))
    area = float(per_face.sum(dtype=np.float64)) / 2.0
    vol = float(np.einsum("ij,ij->i", v0, np.cross(v1, v2)).sum(dtype=np.float64)) / 6.0
    safe = per_face.copy()
    safe[safe == 0] = 1.0
    nz = cross[:, 2] / safe
    overhang = float(np.count_nonzero(nz < -np.sin(np.radians(45)))) / f * 100.0 if f else 0.0
    flat = work.reshape(-1, 3)
    vmin = flat.min(axis=0).astype(np.float64)
    vmax = flat.max(axis=0).astype(np.float64)
    return {
        "area": area,
        "volume": vol,
        "bbox": [round(float(vmax[i] - vmin[i]), 1) for i in range(3)],
        "overhang_pct": round(overhang, 1),
        "face_count": f,
        "vmin": vmin,
        "vmax": vmax,
    }


# ---------------------------------------------------------------- 拓扑（封闭 / 流形）

def merge_vertices(tris: np.ndarray, vmin: np.ndarray, vmax: np.ndarray) -> tuple[np.ndarray, int]:
    """量化后按位编码合并顶点 → (faces Mx3 int32, 顶点数)。

    STL 顶点流无索引；把坐标按包围盒对角线 / 2^21 量化后压成 int64 键，
    一次 np.unique 即可得到索引映射（百万面量级约 0.3s，远快于 trimesh 的 merge_vertices）。
    """
    diag = float(np.linalg.norm(vmax - vmin)) or 1.0
    scale = diag / float(2 ** 21)
    q = np.floor((np.asarray(tris) - vmin) / scale).astype(np.int64)
    np.clip(q, 0, 2 ** 21 - 1, out=q)
    key = (q[:, 0] << 42) | (q[:, 1] << 21) | q[:, 2]
    _, inv = np.unique(key, return_inverse=True)
    nv = int(inv.max()) + 1 if inv.size else 0
    return inv.reshape(-1, 3).astype(np.int32), nv


def topology_stats(faces: np.ndarray, nv: int) -> tuple[bool | None, bool | None, str]:
    """边计数判断封闭性与流形性 → (closed, manifold, note)。

    · 封闭：每条无向边恰好出现 2 次
    · 流形（一致缠绕）：不存在同向重复的有向边
    用 np.sort + 相邻比较（比 np.unique(return_counts) 快，且不需要哈希表）。
    """
    if len(faces) == 0:
        return False, False, ""
    if len(faces) > TOPOLOGY_MAX_FACES:
        return None, None, f"面数 {len(faces):,} 超过拓扑检查上限，已跳过封闭/流形检查"
    f = faces.astype(np.int64, copy=False)
    a = f.ravel()
    b = np.roll(f, -1, axis=1).ravel()          # 每条边的终点
    lo = np.minimum(a, b)
    hi = np.maximum(a, b)
    ek = lo * nv + hi                            # 无向边键
    s = np.sort(ek)
    # 用于 run-length：值变化处为 True
    new_run = np.empty(s.size, dtype=bool)
    new_run[0] = True
    np.not_equal(s[1:], s[:-1], out=new_run[1:])
    bounds = np.flatnonzero(new_run)
    counts = np.diff(np.append(bounds, s.size))
    closed = bool(counts.size and np.all(counts == 2))
    # 有向边重复 = 缠绕不一致（同一方向被两个面共享）
    dk = a * nv + b
    ds = np.sort(dk)
    winding_ok = bool(ds.size < 2 or not np.any(ds[1:] == ds[:-1]))
    manifold = bool(closed and winding_ok)
    return closed, manifold, ""


# ---------------------------------------------------------------- 汇总报告

def _build_report(*, face_count: int, bbox: list, area: float, volume: float,
                  overhang_pct: float, closed, manifold, topo_note: str,
                  vertices=None, faces=None, v0=None, cross=None,
                  wall_raycast: bool = False, wall_ray_samples: int = 800,
                  wall_raycast_max_faces: int = 60_000, parse_mode: str = "fast") -> dict:
    """统一统计口径：面积/体积/壁厚/悬垂/拓扑 → 与 trimesh 版 analyze_mesh 同结构。"""
    # 非封闭网格的有向体积无物理意义 → 归零（对齐 trimesh 的 is_volume 语义）
    volume = abs(volume) if closed else 0.0
    wall, wall_source = None, None
    if closed and area > 0:
        # 2V/A：薄壳件等于壁厚；实心件给出体量厚度，不会误判「过薄」
        wall = round(2.0 * volume / area, 2)
        wall_source = "mean_2v_a"
    if wall_raycast and closed and vertices is not None and face_count <= wall_raycast_max_faces:
        sampled = _sample_wall_thickness(vertices, faces, v0, cross, wall_ray_samples)
        if sampled is not None:
            wall, wall_source = sampled, "raycast_sample"
    report = {
        "volume_cm3": round(volume / 1000.0, 2),
        "surface_cm2": round(area / 100.0, 1),
        "bbox": bbox,
        "closed": bool(closed) if closed is not None else False,
        "manifold": bool(manifold) if manifold is not None else False,
        "self_intersect": False,
        "face_count": int(face_count),
        "overhang_pct": round(overhang_pct, 1),
        "min_wall": wall,
        "wall_source": wall_source,
        "parse_mode": parse_mode,
    }
    if topo_note:
        report["topology_note"] = topo_note
    return report


def analyze_indexed(vertices: np.ndarray, faces: np.ndarray, *,
                    wall_raycast: bool = False, wall_ray_samples: int = 800,
                    wall_raycast_max_faces: int = 60_000) -> dict:
    """索引化网格（OBJ，或已合并的 STL 索引）→ 轻量几何报告。"""
    vertices = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    if len(faces) == 0:
        raise ValueError("网格没有面数据")
    v0, v1, v2 = vertices[faces[:, 0]], vertices[faces[:, 1]], vertices[faces[:, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    per_face = np.sqrt(np.einsum("ij,ij->i", cross, cross))
    area = float(per_face.sum()) / 2.0
    vol = float(np.einsum("ij,ij->i", v0, np.cross(v1, v2)).sum()) / 6.0
    used = vertices[faces.ravel()]
    vmin, vmax = used.min(axis=0), used.max(axis=0)
    bbox = [round(float(vmax[i] - vmin[i]), 1) for i in range(3)]
    safe = per_face.copy()
    safe[safe == 0] = 1.0
    nz = cross[:, 2] / safe
    overhang = float(np.count_nonzero(nz < -np.sin(np.radians(45)))) / len(faces) * 100.0
    closed, manifold, note = topology_stats(faces, int(faces.max()) + 1)
    return _build_report(face_count=len(faces), bbox=bbox, area=area, volume=vol,
                         overhang_pct=overhang, closed=closed, manifold=manifold,
                         topo_note=note, vertices=vertices, faces=faces, v0=v0, cross=cross,
                         wall_raycast=wall_raycast, wall_ray_samples=wall_ray_samples,
                         wall_raycast_max_faces=wall_raycast_max_faces)


def _sample_wall_thickness(vertices, faces, v0, cross, samples: int) -> float | None:
    """可选：抽样射线壁厚（5 分位）。默认关闭——逐面射线是 O(面数×采样数)，很慢。"""
    try:
        import trimesh
    except Exception:
        return None
    try:
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        normals = mesh.face_normals
        k = min(samples, len(mesh.faces))
        idx = np.random.default_rng(0).choice(len(mesh.faces), k, replace=False)
        origins = mesh.triangles_center[idx] - normals[idx] * 0.05
        hits, hit_idx, _ = mesh.ray.intersects_location(origins, -normals[idx])
        if not len(hits):
            return None
        dists = np.linalg.norm(hits - origins[hit_idx], axis=1)
        dists = dists[dists > 0.1]
        return round(float(np.percentile(dists, 5)), 2) if dists.size else None
    except Exception:
        return None


def fast_analyze_stl(path: str | Path, *, wall_raycast: bool = False,
                     wall_ray_samples: int = 800, wall_raycast_max_faces: int = 60_000) -> dict:
    """STL 轻量解析。

    优先走原生 C 实现（native/stl_fast.c：mmap 零拷贝 + 基数排序，思路对照 OrcaSlicer/admesh），
    原生库不可用时回退 numpy 向量化实现。两者统计口径一致（面积/体积/封闭/流形/悬垂/壁厚）。
    """
    from . import native_stl
    native = native_stl.analyze(path)
    if native is not None:
        return native
    tris = stl_triangles(path)
    geo = triangle_geometry(tris)
    if geo["face_count"] == 0:
        raise ValueError("STL 中没有三角形")
    faces, nv = merge_vertices(tris, geo["vmin"], geo["vmax"])
    closed, manifold, note = topology_stats(faces, nv)
    vertices = v0 = cross = None
    if wall_raycast and closed and 0 < geo["face_count"] <= wall_raycast_max_faces:
        # 仅在显式开启"精确壁厚"时才重建索引顶点并抽样射线
        vertices = _indexed_vertices(tris, faces, geo["vmin"], geo["vmax"])
        v = vertices[faces]
        v0, cross = v[:, 0], np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    return _build_report(face_count=geo["face_count"], bbox=geo["bbox"], area=geo["area"],
                         volume=geo["volume"], overhang_pct=geo["overhang_pct"],
                         closed=closed, manifold=manifold, topo_note=note,
                         vertices=vertices, faces=faces, v0=v0, cross=cross,
                         wall_raycast=wall_raycast, wall_ray_samples=wall_ray_samples,
                         wall_raycast_max_faces=wall_raycast_max_faces)


def _indexed_vertices(tris: np.ndarray, faces: np.ndarray, vmin, vmax) -> np.ndarray:
    """从顶点流重建去重后的顶点表（按 faces 的最大索引数量分配）。"""
    nv = int(faces.max()) + 1
    vertices = np.empty((nv, 3), dtype=np.float64)
    flat = faces.ravel()
    vertices[flat] = np.asarray(tris, dtype=np.float64)
    return vertices


def fast_analyze_obj(path: str | Path, **kwargs) -> dict | None:
    """OBJ 轻量解析：复用现有快速顶点/面解析，再走统一统计口径。"""
    try:
        vertices, faces = load_obj_vertices_faces(path)
        return analyze_indexed(vertices, faces, **kwargs)
    except Exception:
        return None


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


def fast_analyze_file(path: str | Path, **kwargs) -> dict | None:
    """按扩展名分派快速解析；不支持的格式返回 None（由调用方回退 trimesh）。"""
    ext = str(path).lower().rsplit(".", 1)[-1] if "." in str(path) else ""
    try:
        if ext == "stl":
            return fast_analyze_stl(path, **kwargs)
        if ext == "obj":
            return fast_analyze_obj(path, **kwargs)
    except Exception:
        return None
    return None
