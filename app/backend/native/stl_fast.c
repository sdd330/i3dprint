/*
 * E3DP — 轻量 STL 解析器（C99，无第三方依赖）
 * ---------------------------------------------------------------------------
 * 设计参考 OrcaSlicer / admesh（deps_src/admesh/stlinit.cpp::stl_open_count_facets,
 * shared.cpp::stl_generate_shared_vertices）：
 *   1) 二进制 / ASCII 判定：先看首个面记录 128 字节内有无 >127 的字节，再用文件大小
 *      反推面数校验 `84 + n*50 == file_size`；面数以文件大小为准（头部声明值只做对照）
 *   2) mmap 零拷贝顺序读取 50 字节定长记录；跳过含 NaN 的三角（admesh: someone_is_nan）
 *   3) 顶点去重：坐标量化成 64 位键 → 基数排序 → 按 rank 分配索引（等价 admesh 的
 *      邻接/共享顶点构建，但用排序而非哈希，结果确定、无碰撞）
 *   4) 拓扑：无向边键排序后统计“每条边恰好出现 2 次” → 封闭；有向边键相邻重复
 *      → 缠绕不一致（非流形）
 *   5) 统计：包围盒 / 面积 / 有向体积（散度定理）/ 悬垂占比（法线 z < -sin45°）
 *   6) 壁厚：2V/A（薄壳件即壁厚；实心件给出体量厚度，不会误判“过薄”），不做逐面射线
 *
 * 只导出两个函数，供 Python ctypes 调用：
 *   int  stl_fast_analyze(const char *path, stl_result *out);
 *   const char *stl_fast_version(void);
 *
 * 编译：见同目录 build.sh（macOS .dylib / Linux .so）
 */

#include <errno.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#error "E3DP stl_fast: Windows 未适配（项目部署在 Linux/macOS）；请使用 numpy 回退路径"
#endif

#if defined(__BYTE_ORDER__) && (__BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__)
#error "E3DP stl_fast: 仅支持小端机器（big-endian 请使用 numpy 回退路径）"
#endif

#include <fcntl.h>
#include <sys/mman.h>
#include <time.h>
#include <sys/stat.h>
#include <unistd.h>

#define STL_HEADER_SIZE 84
#define STL_FACET_SIZE 50
#define ERR_LEN 256

/* 量化精度：包围盒对角线 / 2^21（200mm 模型 ≈ 0.0001mm），每轴 21 bit */
#define QUANT_BITS 21
#define QUANT_MAX ((1u << QUANT_BITS) - 1)

/* 超过该面数跳过拓扑（封闭/流形）检查，避免超大文件内存爆炸 */
#ifndef STL_TOPOLOGY_MAX_FACES
#define STL_TOPOLOGY_MAX_FACES 2000000u
#endif

typedef struct {
    int32_t face_count;     /* 有效三角数（已剔除 NaN 三角） */
    int32_t vertex_count;   /* 去重后的顶点数，-1 表示未做 */
    int32_t flags;          /* 见 STL_FLAG_* */
    int32_t reserved;
    double  bbox[3];        /* max - min */
    double  area;           /* 表面积（原始单位²） */
    double  volume;         /* 有向体积（原始单位³），非封闭网格置 0 */
    double  overhang_pct;   /* 悬垂面占比（%） */
    double  wall;           /* 2V/A（原始单位），-1 = 不可用 */
    double  elapsed_ms;     /* 解析耗时 */
    char    error[ERR_LEN];
} stl_result;

enum {
    STL_FLAG_BINARY            = 1 << 0,
    STL_FLAG_CLOSED            = 1 << 1,
    STL_FLAG_MANIFOLD          = 1 << 2,
    STL_FLAG_TOPOLOGY_SKIPPED  = 1 << 3,
    STL_FLAG_NAN_SKIPPED       = 1 << 4,
};

/* ------------------------------------------------------------------ 小工具 */

static void set_error(stl_result *out, const char *msg)
{
    if (!out) return;
    snprintf(out->error, ERR_LEN, "%s", msg ? msg : "unknown error");
}

static void *xmalloc(size_t n)
{
    if (n == 0) n = 1;
    void *p = malloc(n);
    return p;
}

/* 基数排序：uint64 键 + 可选 uint32 载荷（4 趟 × 16 bit LSD） */
static int radix_sort_u64(uint64_t *keys, uint32_t *vals, size_t n,
                          uint64_t *tmp_keys, uint32_t *tmp_vals)
{
    if (n < 2) return 0;
    size_t *count = (size_t *)calloc(65536, sizeof(size_t));
    if (!count) return -1;

    uint64_t *src_k = keys, *dst_k = tmp_keys;
    uint32_t *src_v = vals, *dst_v = tmp_vals;

    for (int pass = 0; pass < 4; ++pass) {
        const int shift = pass * 16;
        memset(count, 0, 65536 * sizeof(size_t));
        for (size_t i = 0; i < n; ++i)
            count[(src_k[i] >> shift) & 0xFFFFu]++;

        size_t sum = 0;
        for (size_t b = 0; b < 65536; ++b) {
            size_t c = count[b];
            count[b] = sum;
            sum += c;
        }
        for (size_t i = 0; i < n; ++i) {
            size_t pos = count[(src_k[i] >> shift) & 0xFFFFu]++;
            dst_k[pos] = src_k[i];
            if (src_v) dst_v[pos] = src_v[i];
        }
        uint64_t *tk = src_k; src_k = dst_k; dst_k = tk;
        if (src_v) { uint32_t *tv = src_v; src_v = dst_v; dst_v = tv; }
    }
    if (src_k != keys) {
        memcpy(keys, src_k, n * sizeof(uint64_t));
        if (vals) memcpy(vals, src_v, n * sizeof(uint32_t));
    }
    free(count);
    return 0;
}

/* ------------------------------------------------------- 文件 → 三角顶点流 */

typedef struct {
    size_t       count;  /* 三角数 */
    int          binary;
    void        *map;    /* mmap 基址（ASCII 为 NULL） */
    size_t       map_len;
    float       *owned;  /* ASCII 解析出的缓冲区（需 free） */
    size_t       nan_skipped;
} stl_source;

static int looks_like_binary_stl(const char *path, size_t *out_count)
{
    int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;
    struct stat st;
    if (fstat(fd, &st) != 0) { close(fd); return -1; }
    const size_t size = (size_t)st.st_size;
    if (size < STL_HEADER_SIZE + STL_FACET_SIZE) { close(fd); return 0; }

    unsigned char head[STL_HEADER_SIZE + 128];
    ssize_t got = pread(fd, head, sizeof(head), 0);
    close(fd);
    if (got < (ssize_t)(STL_HEADER_SIZE + 128)) {
        /* 文件刚好一个面：退化为只读头部 */
        if (got < STL_HEADER_SIZE) return 0;
    }

    uint32_t declared = 0;
    memcpy(&declared, head + 80, 4);
    const size_t body = size - STL_HEADER_SIZE;
    if (body % STL_FACET_SIZE != 0) return 0;       /* 定长记录布局不成立 → ASCII */
    const size_t from_size = body / STL_FACET_SIZE;
    if (from_size == 0) return 0;

    int high_byte = 0;
    const ssize_t probe_n = got - STL_HEADER_SIZE;
    for (ssize_t i = 0; i < probe_n; ++i)
        if (head[STL_HEADER_SIZE + i] > 127) { high_byte = 1; break; }

    /* 纯 ASCII 数字（全 0/10/15）可能没有高位字节 → 以文件大小为准再确认一次 */
    if (!high_byte && from_size != (size_t)declared) return 0;

    *out_count = from_size;   /* 面数以文件大小为准，头部声明值只做对照 */
    return 1;
}

static int load_binary(stl_source *src, const char *path, size_t count)
{
    int fd = open(path, O_RDONLY);
    if (fd < 0) { return -1; }
    struct stat st;
    if (fstat(fd, &st) != 0) { close(fd); return -1; }
    size_t len = (size_t)st.st_size;
    void *map = mmap(NULL, len, PROT_READ, MAP_PRIVATE, fd, 0);
    close(fd);
    if (map == MAP_FAILED) return -1;

    src->map = map;
    src->map_len = len;
    src->binary = 1;
    src->count = count;
    return 0;
}

/* ASCII STL：扫描 "vertex x y z"，用 strtof 解析（不依赖 locale） */
static int load_ascii(stl_source *src, const char *path)
{
    FILE *fp = fopen(path, "rb");
    if (!fp) return -1;
    if (fseek(fp, 0, SEEK_END) != 0) { fclose(fp); return -1; }
    long size = ftell(fp);
    if (size <= 0) { fclose(fp); return -1; }
    rewind(fp);
    char *buf = (char *)xmalloc((size_t)size + 1);
    if (!buf) { fclose(fp); return -1; }
    size_t got = fread(buf, 1, (size_t)size, fp);
    fclose(fp);
    buf[got] = '\0';

    /* 粗估顶点数：每个 "vertex" 一个 → 预分配 */
    size_t cap = 3 * 1024, n = 0;
    float *verts = (float *)xmalloc(cap * 3 * sizeof(float));
    if (!verts) { free(buf); return -1; }

    char *p = buf;
    while ((p = strstr(p, "vertex")) != NULL) {
        if (p != buf) {
            char prev = *(p - 1);
            if (!(prev == ' ' || prev == '\t' || prev == '\n' || prev == '\r')) { p += 6; continue; }
        }
        p += 6;
        char *end = NULL;
        float x = strtof(p, &end);
        if (end == p) continue;
        p = end;
        float y = strtof(p, &end);
        if (end == p) continue;
        p = end;
        float z = strtof(p, &end);
        if (end == p) continue;
        p = end;
        if (n + 3 > cap) {
            cap *= 2;
            float *grown = (float *)realloc(verts, cap * 3 * sizeof(float));
            if (!grown) { free(verts); free(buf); return -1; }
            verts = grown;
        }
        verts[n] = x; verts[n + 1] = y; verts[n + 2] = z;
        n += 3;
    }
    free(buf);
    if (n < 3) { free(verts); return -1; }
    src->owned = verts;
    src->count = n / 9;   /* 每面 3 顶点 × 3 分量 */
    src->binary = 0;
    return 0;
}

static void free_source(stl_source *src)
{
    if (src->map && src->map != MAP_FAILED) munmap(src->map, src->map_len);
    if (src->owned) free(src->owned);
    src->map = NULL;
    src->owned = NULL;
    src->count = 0;
}

/* 取出第 i 个面的 9 个坐标（3 顶点 × xyz）。
 * 二进制 STL 每面 50 字节（法线 12 + 顶点 36 + 属性 2），不是 float 对齐的连续数组，
 * 因此按 50 字节跨步 + memcpy 读取（编译器会内联成向量化 load）。 */
static inline void fetch_facet(const stl_source *src, size_t i, float out[9])
{
    if (src->binary) {
        const char *p = (const char *)src->map + STL_HEADER_SIZE + i * STL_FACET_SIZE + 12;
        memcpy(out, p, 9 * sizeof(float));
    } else {
        memcpy(out, src->owned + i * 9, 9 * sizeof(float));
    }
}

/* ------------------------------------------------------------- 主分析流程 */

static double now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec * 1000.0 + (double)ts.tv_nsec / 1e6;
}

int stl_fast_analyze(const char *path, stl_result *out)
{
    if (!out) return -1;
    memset(out, 0, sizeof(*out));
    out->wall = -1.0;
    const double t0 = now_ms();
    if (!path) { set_error(out, "path is null"); return -2; }

    stl_source src;
    memset(&src, 0, sizeof(src));

    size_t binary_count = 0;
    int is_binary = looks_like_binary_stl(path, &binary_count);
    if (is_binary < 0) { set_error(out, "cannot open file"); return -2; }

    if (is_binary == 1) {
        if (load_binary(&src, path, binary_count) != 0) {
            set_error(out, "mmap failed");
            return -2;
        }
    } else {
        if (load_ascii(&src, path) != 0) {
            set_error(out, "ASCII STL parse failed (no vertex tokens)");
            return -2;
        }
    }

    const size_t f_count = src.count;
    if (f_count == 0) { free_source(&src); set_error(out, "empty STL (no facets)"); return -2; }

    /* ---- 第一遍：统计 + 收集顶点键（跳过 NaN 面） ---- */
    double bmin[3] = { INFINITY, INFINITY, INFINITY };
    double bmax[3] = { -INFINITY, -INFINITY, -INFINITY };
    double area2 = 0.0;     /* 2×面积累计（避免 0.5 的重复乘） */
    double vol6 = 0.0;      /* 6×体积累计 */
    size_t overhang = 0;
    const double sin45 = 0.7071067811865476;

    /* 先扫一遍取包围盒（量化需要 vmin/vmax） */
    size_t finite_faces = 0;
    for (size_t i = 0; i < f_count; ++i) {
        float v[9];
        fetch_facet(&src, i, v);
        int bad = 0;
        for (int j = 0; j < 9; ++j) if (!isfinite(v[j])) { bad = 1; break; }
        if (bad) { src.nan_skipped++; continue; }
        finite_faces++;
        for (int k = 0; k < 3; ++k) {
            /* v 的布局：v0x v0y v0z v1x v1y v1z v2x v2y v2z */
            const double x = v[k * 3], y = v[k * 3 + 1], z = v[k * 3 + 2];
            if (x < bmin[0]) bmin[0] = x;
            if (y < bmin[1]) bmin[1] = y;
            if (z < bmin[2]) bmin[2] = z;
            if (x > bmax[0]) bmax[0] = x;
            if (y > bmax[1]) bmax[1] = y;
            if (z > bmax[2]) bmax[2] = z;
        }
    }
    if (finite_faces == 0) { free_source(&src); set_error(out, "all facets are NaN"); return -2; }

    out->face_count = (int32_t)finite_faces;
    out->flags |= src.binary ? STL_FLAG_BINARY : 0;
    if (src.nan_skipped) out->flags |= STL_FLAG_NAN_SKIPPED;
    for (int k = 0; k < 3; ++k) out->bbox[k] = bmax[k] - bmin[k];

    double diag2 = 0.0;
    for (int k = 0; k < 3; ++k) { double d = bmax[k] - bmin[k]; diag2 += d * d; }
    const double diag = sqrt(diag2);
    const double quant_scale = (diag > 0.0 ? diag : 1.0) / (double)(1u << QUANT_BITS);

    /* ---- 第二遍：几何量（面积 / 有向体积 / 悬垂）——不需要大数组 ---- */
    for (size_t i = 0; i < f_count; ++i) {
        float v[9];
        fetch_facet(&src, i, v);
        int bad = 0;
        for (int j = 0; j < 9; ++j) if (!isfinite(v[j])) { bad = 1; break; }
        if (bad) continue;

        const double x0 = v[0], y0 = v[1], z0 = v[2];
        const double x1 = v[3], y1 = v[4], z1 = v[5];
        const double x2 = v[6], y2 = v[7], z2 = v[8];
        const double e1x = x1 - x0, e1y = y1 - y0, e1z = z1 - z0;
        const double e2x = x2 - x0, e2y = y2 - y0, e2z = z2 - z0;
        const double cx = e1y * e2z - e1z * e2y;
        const double cy = e1z * e2x - e1x * e2z;
        const double cz = e1x * e2y - e1y * e2x;
        const double cn = sqrt(cx * cx + cy * cy + cz * cz);
        area2 += cn;
        if (cn > 0.0 && cz / cn < -sin45) overhang++;
        /* 有向体积：dot(v0, cross(v1, v2)) / 6 */
        const double nx = y1 * z2 - z1 * y2;
        const double ny = z1 * x2 - x1 * z2;
        const double nz = x1 * y2 - y1 * x2;
        vol6 += x0 * nx + y0 * ny + z0 * nz;
    }
    out->area = area2 * 0.5;
    out->overhang_pct = (double)overhang / (double)finite_faces * 100.0;

    /* ---- 第三遍（可选）：顶点去重 + 拓扑。面数超限则整段跳过，避免几百 MB 峰值 ---- */
    int closed = 0, manifold = 0, skipped = 0;
    if (finite_faces > STL_TOPOLOGY_MAX_FACES) {
        skipped = 1;
    } else {
    const size_t corner_n = finite_faces * 3;
    uint64_t *keys = (uint64_t *)xmalloc(corner_n * sizeof(uint64_t));
    uint32_t *vidx = (uint32_t *)xmalloc(corner_n * sizeof(uint32_t));
    uint64_t *keys_tmp = (uint64_t *)xmalloc(corner_n * sizeof(uint64_t));
    uint32_t *vidx_tmp = (uint32_t *)xmalloc(corner_n * sizeof(uint32_t));
    uint32_t *ids = (uint32_t *)xmalloc(corner_n * sizeof(uint32_t));
    if (!keys || !vidx || !keys_tmp || !vidx_tmp || !ids) {
        free(keys); free(vidx); free(keys_tmp); free(vidx_tmp); free(ids);
        free_source(&src);
        set_error(out, "out of memory (vertex buffers)");
        return -3;
    }

    size_t c = 0;
    for (size_t i = 0; i < f_count; ++i) {
        float v[9];
        fetch_facet(&src, i, v);
        int bad = 0;
        for (int j = 0; j < 9; ++j) if (!isfinite(v[j])) { bad = 1; break; }
        if (bad) continue;
        for (int k = 0; k < 3; ++k) {
            const double vx = v[k * 3], vy = v[k * 3 + 1], vz = v[k * 3 + 2];
            long qx = (long)floor((vx - bmin[0]) / quant_scale);
            long qy = (long)floor((vy - bmin[1]) / quant_scale);
            long qz = (long)floor((vz - bmin[2]) / quant_scale);
            if (qx < 0) qx = 0; if (qx > (long)QUANT_MAX) qx = QUANT_MAX;
            if (qy < 0) qy = 0; if (qy > (long)QUANT_MAX) qy = QUANT_MAX;
            if (qz < 0) qz = 0; if (qz > (long)QUANT_MAX) qz = QUANT_MAX;
            keys[c] = ((uint64_t)qx << 42) | ((uint64_t)qy << 21) | (uint64_t)qz;
            vidx[c] = (uint32_t)c;
            c++;
        }
    }

    /* ---- 顶点去重：排序键 → 按 rank 分配 id ---- */
    if (radix_sort_u64(keys, vidx, corner_n, keys_tmp, vidx_tmp) != 0) {
        free(keys); free(vidx); free(keys_tmp); free(vidx_tmp); free(ids);
        free_source(&src);
        set_error(out, "radix sort failed (vertices)");
        return -3;
    }
    uint32_t next_id = 0;
    uint64_t prev_key = keys[0];
    ids[vidx[0]] = 0;
    for (size_t i = 1; i < corner_n; ++i) {
        if (keys[i] != prev_key) { next_id++; prev_key = keys[i]; }
        ids[vidx[i]] = next_id;
    }
    const uint32_t nv = next_id + 1;
    out->vertex_count = (int32_t)nv;
    free(keys); free(vidx); free(keys_tmp); free(vidx_tmp);

        /* ---- 无向边键：统计每条边出现次数（全为 2 → 封闭） ---- */
        const size_t edge_n = corner_n;
        uint64_t *ekey = (uint64_t *)xmalloc(edge_n * sizeof(uint64_t));
        uint64_t *etmp = (uint64_t *)xmalloc(edge_n * sizeof(uint64_t));
        if (!ekey || !etmp) {
            free(ekey); free(etmp); free(ids); free_source(&src);
            set_error(out, "out of memory (edge buffers)");
            return -3;
        }
        const uint64_t stride = (uint64_t)nv + 1u;
        for (size_t i = 0; i < finite_faces; ++i) {
            const uint32_t a = ids[i * 3 + 0], b = ids[i * 3 + 1], d = ids[i * 3 + 2];
            const uint64_t lo0 = a < b ? a : b, hi0 = a < b ? b : a;
            const uint64_t lo1 = b < d ? b : d, hi1 = b < d ? d : b;
            const uint64_t lo2 = d < a ? d : a, hi2 = d < a ? a : d;
            ekey[i * 3 + 0] = lo0 * stride + hi0;
            ekey[i * 3 + 1] = lo1 * stride + hi1;
            ekey[i * 3 + 2] = lo2 * stride + hi2;
        }
        if (radix_sort_u64(ekey, NULL, edge_n, etmp, NULL) != 0) {
            free(ekey); free(etmp); free(ids); free_source(&src);
            set_error(out, "radix sort failed (edges)");
            return -3;
        }
        closed = 1;
        size_t run = 1;
        for (size_t i = 1; i < edge_n; ++i) {
            if (ekey[i] == ekey[i - 1]) { run++; }
            else { if (run != 2) { closed = 0; break; } run = 1; }
        }
        if (closed && run != 2) closed = 0;

        /* ---- 有向边键：同向重复 → 缠绕不一致（非流形） ---- */
        if (closed) {
            manifold = 1;
            for (size_t i = 0; i < finite_faces; ++i) {
                const uint32_t a = ids[i * 3 + 0], b = ids[i * 3 + 1], d = ids[i * 3 + 2];
                ekey[i * 3 + 0] = (uint64_t)a * stride + b;
                ekey[i * 3 + 1] = (uint64_t)b * stride + d;
                ekey[i * 3 + 2] = (uint64_t)d * stride + a;
            }
            if (radix_sort_u64(ekey, NULL, edge_n, etmp, NULL) != 0) {
                free(ekey); free(etmp); free(ids); free_source(&src);
                set_error(out, "radix sort failed (winding)");
                return -3;
            }
            for (size_t i = 1; i < edge_n; ++i)
                if (ekey[i] == ekey[i - 1]) { manifold = 0; break; }
        }
        free(ekey); free(etmp);
        free(ids);
    }  /* end topology block */
    free_source(&src);

    out->volume = closed ? fabs(vol6 / 6.0) : 0.0;
    if (closed) out->flags |= STL_FLAG_CLOSED;
    if (manifold) out->flags |= STL_FLAG_MANIFOLD;
    if (skipped) out->flags |= STL_FLAG_TOPOLOGY_SKIPPED;
    if (closed && out->area > 0.0) out->wall = 2.0 * out->volume / out->area;
    out->elapsed_ms = now_ms() - t0;
    return 0;
}

const char *stl_fast_version(void)
{
    return "e3dp-stl-fast/1.0 (c99, mmap, radix-sort, admesh-style)";
}
