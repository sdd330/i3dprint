# Violet Print backend — 站娘知识库：本地向量检索（零外部 API）
# ---------------------------------------------------------------------------
# 为什么要自己实现：项目不接第三方 embedding 服务（无 key、零成本、离线可用），
# 所以用**稀疏向量 + 余弦相似度**（TF-IDF 空间模型）做语义检索：
#   1) Markdown 按标题层级切块（保留章节路径，回答时能给出出处）
#   2) 分词：中文按「单字 + 相邻二元组」切（无需词典依赖），英文/数字按词切
#   3) TF-IDF：sublinear tf（1+log tf）× idf，L2 归一化后存 DB（kb_chunks.vector）
#   4) 检索：把问题向量与所有块向量点积（块数量级 ~10²，纯 Python 足够快）
# 未来接入真实 embedding（如 bge/m3e 本地模型）时，只需替换 vectorize() 与 search()。
#
# 数据来源目录：backend/kb/*.md（教材/手册），启动时自动同步（按文件哈希幂等）。

from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path

from sqlalchemy.orm import Session

from ..models import KbChunk, KbSource

KB_DIR = Path(__file__).resolve().parents[2] / "kb"   # backend/kb

# embedding 批大小（LM Studio 对单请求条数有限制，分批更稳）
EMBED_BATCH = 16
CHUNK_MAX_CHARS = 420        # 单块正文上限（过长会稀释相似度）
CHUNK_MIN_CHARS = 40         # 过短的块（纯标题/目录行）丢弃
DEFAULT_MIN_SCORE = 0.06     # 稀疏(TF-IDF)命中阈值；稠密阈值见 kb_vector_min_score_dense
HYBRID_SPARSE_WEIGHT = 0.45  # 混合检索里字面分的权重（综合分 = dense + 0.45 × sparse）

# 中文停用词（短表即可；二元组本身已过滤掉大部分噪声）
_STOP = set("的了和与及或是把被在有为对从到等这那你我他她它其之则而且并但也就都还很更最可以一个什么怎么如何为什么需要如果因为所以")
_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_+-]*|\d+(?:\.\d+)?")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# 口语/写法归一：折叠常见同义写法，提高召回（TF-IDF 无法自动跨过这类差异）
_ALIASES = [
    ("第一层", "首层"), ("底层附着", "首层"), ("黏", "粘"),
    ("填充率", "填充"), ("支撑结构", "支撑"), ("翘曲", "翘边"),
    ("喷头", "喷嘴"), ("热床温度", "热床"), ("模型文件", "模型"),
]


def _normalize(text: str) -> str:
    for a, b in _ALIASES:
        text = text.replace(a, b)
    return text
_HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")


# ---------------------------------------------------------------- embedding（本地 LM Studio）

def embedding_conf() -> dict:
    """读取软件设置里的 embedding 配置（LM Studio 的 OpenAI 兼容端点）。"""
    from ..core.config import settings
    from ..core.dynamic_settings import get_setting
    return {
        "enabled": bool(get_setting("embedding_enabled", settings.embedding_enabled)),
        "base_url": (get_setting("embedding_base_url", settings.embedding_base_url) or "").rstrip("/"),
        "model": (get_setting("embedding_model", settings.embedding_model) or "").strip(),
    }


def _client():
    import httpx
    # 本地服务：绕过 http_proxy（否则走了代理会连不上 127.0.0.1）
    return httpx.Client(timeout=120, trust_env=False)


def detect_model(base_url: str) -> str | None:
    """从 /v1/models 里挑一个 embedding 模型（优先含 embedding/bge 的）。"""
    try:
        with _client() as c:
            r = c.get(f"{base_url}/models")
            r.raise_for_status()
            ids = [m.get("id", "") for m in r.json().get("data", [])]
    except Exception:
        return None
    for key in ("embedding", "bge", "text2vec"):
        for i in ids:
            if key in i.lower():
                return i
    return None


def probe() -> dict:
    """给管理端用的可用性探测。"""
    cfg = embedding_conf()
    info = {"enabled": cfg["enabled"], "base_url": cfg["base_url"], "model": cfg["model"], "reachable": False, "models": []}
    try:
        with _client() as c:
            r = c.get(f"{cfg['base_url']}/models")
            r.raise_for_status()
            info["models"] = [m.get("id", "") for m in r.json().get("data", [])]
            info["reachable"] = True
    except Exception as e:
        info["error"] = str(e)[:160]
    if not info["model"]:
        info["model"] = detect_model(cfg["base_url"]) or ""
    return info


def embed_texts(texts: list[str], cfg: dict | None = None) -> list[list[float]] | None:
    """批量取 embedding（单位化后返回，余弦=点积）。失败返回 None，由调用方回退 TF-IDF。"""
    cfg = cfg or embedding_conf()
    if not cfg["enabled"] or not texts:
        return None
    model = cfg["model"] or detect_model(cfg["base_url"])
    if not model:
        return None
    out: list[list[float]] = []
    try:
        with _client() as c:
            for i in range(0, len(texts), EMBED_BATCH):
                batch = texts[i:i + EMBED_BATCH]
                r = c.post(f"{cfg['base_url']}/embeddings", json={"model": model, "input": batch})
                r.raise_for_status()
                data = r.json().get("data", [])
                if len(data) != len(batch):
                    return None
                for item in sorted(data, key=lambda d: d.get("index", 0)):
                    vec = item.get("embedding") or []
                    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
                    out.append([round(v / norm, 6) for v in vec])
        return out if len(out) == len(texts) else None
    except Exception:
        return None


def _dense_cos(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


# ---------------------------------------------------------------- 切块

def _clean(text: str) -> str:
    """去掉 Markdown 修饰（图片/链接/强调/表格管道符），保留可读正文。

    表格转成「· 单元格1 ｜ 单元格2 ｜ 单元格3」的可读行——直接丢给聊天框时不会再冒出裸竖线。
    """
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)           # 图片
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)        # 链接 → 文本
    text = text.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
    out = []
    for line in text.splitlines():
        s = line.strip()
        if re.fullmatch(r"\|?[\s:|-]{6,}\|?", s or ""):           # 表格分隔行
            continue
        if s.startswith("|") and s.count("|") >= 2:                  # 表格数据行
            cells = [c.strip() for c in s.strip("|").split("|")]
            cells = [c for c in cells if c]
            if cells:
                out.append("· " + " ｜ ".join(cells))
            continue
        out.append(line)
    text = "\n".join(out)
    text = re.sub(r"[*_`>#]+", "", text)                        # 强调/引用/代码符
    text = re.sub(r"\\\.", ".", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_markdown(text: str) -> list[dict]:
    """按标题切块 → [{heading, content}]；单块过长时按段落再切。"""
    lines = text.splitlines()
    trail: list[tuple[int, str]] = []   # (level, title) 当前标题栈
    chunks: list[dict] = []
    buf: list[str] = []

    def flush():
        body = _clean("\n".join(buf))
        buf.clear()
        if len(body) < CHUNK_MIN_CHARS:
            return
        heading = " › ".join(t for _, t in trail) or "正文"
        # 过长 → 按段落贪心切分
        if len(body) <= CHUNK_MAX_CHARS:
            chunks.append({"heading": heading, "content": body})
            return
        para, cur = re.split(r"\n\s*\n", body), ""
        for p in para:
            if len(cur) + len(p) + 2 > CHUNK_MAX_CHARS and len(cur) >= CHUNK_MIN_CHARS:
                chunks.append({"heading": heading, "content": cur.strip()})
                cur = ""
            cur += p + "\n\n"
        if len(cur.strip()) >= CHUNK_MIN_CHARS:
            chunks.append({"heading": heading, "content": cur.strip()})

    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            flush()
            level = len(m.group(1))
            title = _clean(m.group(2)) or "未命名"
            trail = [(lv, t) for lv, t in trail if lv < level] + [(level, title)]
            continue
        buf.append(line)
    flush()
    return chunks


# ---------------------------------------------------------------- 分词 / 向量

def tokenize(text: str) -> list[str]:
    """中文：单字 + 二元组（去停用词）；英文/数字：小写词。"""
    text = _normalize(text).lower()
    tokens: list[str] = []
    cjk_buf: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if _CJK_RE.match(ch):
            cjk_buf.append(ch)
            i += 1
            continue
        # 非中文：先把攒下的中文吐出来
        if cjk_buf:
            tokens.extend(_cjk_tokens(cjk_buf))
            cjk_buf = []
        m = _WORD_RE.match(text, i)
        if m:
            w = m.group(0)
            if len(w) > 1 or w.isdigit():
                tokens.append(w)
            i = m.end()
            continue
        i += 1
    if cjk_buf:
        tokens.extend(_cjk_tokens(cjk_buf))
    return tokens


def _cjk_tokens(chars: list[str]) -> list[str]:
    out: list[str] = []
    n = len(chars)
    for i, ch in enumerate(chars):
        if ch not in _STOP:
            out.append(ch)
        if i + 1 < n:
            bi = ch + chars[i + 1]
            if not (ch in _STOP and chars[i + 1] in _STOP):
                out.append(bi)
    return out


def _token_weight(token: str) -> float:
    """权重：中文单字 0.45（噪声大）、中文二元组 1.0、英文/数字 1.3（区分度高）"""
    if _CJK_RE.match(token[0]):
        return 0.45 if len(token) == 1 else 1.0
    return 1.3


def _tf(tokens: list[str]) -> dict[str, float]:
    tf: dict[str, float] = {}
    for t in tokens:
        tf[t] = tf.get(t, 0.0) + _token_weight(t)
    return tf


def _weigh(tf: dict[str, float], idf: dict[str, float]) -> dict[str, float]:
    """sublinear tf × idf，L2 归一化（缺失 idf 的 token 用最大 idf，避免长尾词被忽略）。"""
    if not tf:
        return {}
    default_idf = max(idf.values()) if idf else 1.0
    vec = {t: (1.0 + math.log(c)) * idf.get(t, default_idf) for t, c in tf.items()}
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {t: round(v / norm, 6) for t, v in vec.items()}


def build_source(chunks: list[dict]) -> tuple[list[dict], dict[str, float]]:
    """切块列表 → (带向量的块, idf 表)。idf 供查询侧复用同一坐标系。"""
    # 标题权重 ×2：很多问题的答案就写在标题里（如「3.4 涂胶：让首层能黏住」）
    tokenized = [tokenize(c["heading"]) * 2 + tokenize(c["content"]) for c in chunks]
    df: dict[str, int] = {}
    for toks in tokenized:
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    total = max(1, len(chunks))
    idf = {t: round(math.log((1 + total) / (1 + d)) + 1.0, 4) for t, d in df.items()}
    out = []
    for c, toks in zip(chunks, tokenized):
        out.append({**c, "vector": _weigh(_tf(toks), idf), "char_count": len(c["content"])})
    return out, idf


# ---------------------------------------------------------------- 检索

def query_vector(question: str, idf: dict[str, float]) -> dict[str, float]:
    return _weigh(_tf(tokenize(question)), idf)


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(t, 0.0) for t, v in a.items())


def search(db: Session, question: str, top_k: int = 3, min_score: float | None = None) -> list[dict]:
    """检索：有 embedding 索引时用稠密语义检索，否则回退 TF-IDF。

    返回 [{heading, content, score, source, mode}]，按相似度降序。
    """
    sources = db.query(KbSource).all()
    if not sources:
        return []
    dense_sources = [s for s in sources if (s.embedding_model or "")]
    if dense_sources:
        dense = _search_dense(db, question, dense_sources, top_k)
        if dense:
            return dense
        # embedding 服务暂时不可用 → 回退稀疏
    min_score = DEFAULT_MIN_SCORE if min_score is None else min_score
    idf: dict[str, float] = {}
    for s in sources:
        for t, v in (s.idf or {}).items():
            idf[t] = max(idf.get(t, 0.0), float(v))
    qv = query_vector(question, idf)
    if not qv:
        return []
    name_of = {s.id: s.name for s in sources}
    rows = db.query(KbChunk).all()
    scored = []
    for ch in rows:
        score = cosine(qv, ch.vector or {})
        if score >= min_score:
            scored.append({"heading": ch.heading, "content": ch.content,
                           "score": round(score, 4), "source": name_of.get(ch.source_id, "")})
    scored.sort(key=lambda x: x["score"], reverse=True)
    for item in scored:
        item["mode"] = "sparse"
    return scored[:top_k]


def _search_dense(db: Session, question: str, sources: list[KbSource], top_k: int) -> list[dict]:
    """混合检索：稠密语义分 + 稀疏字面分。

    · dense：embedding 余弦（语义召回，跨越"粘住/黏住""噼啪响/受潮"这类说法差异）
    · sparse：TF-IDF 余弦（字面钉准，避免语义漂到别的章节）
    · 综合分 = dense + HYBRID_SPARSE_WEIGHT × sparse，入场门槛为"任一通道达标"
    """
    from ..core.dynamic_settings import get_setting
    cfg = embedding_conf()
    if not cfg["enabled"]:
        return []
    qvec = embed_texts([question], cfg)
    if not qvec:
        return []
    qv = qvec[0]
    dense_min = float(get_setting("kb_vector_min_score_dense", 0.30))
    sparse_min = float(get_setting("kb_vector_min_score", DEFAULT_MIN_SCORE))
    weight = float(get_setting("kb_vector_hybrid_sparse_weight", HYBRID_SPARSE_WEIGHT))

    idf: dict[str, float] = {}
    for s in sources:
        for t, v in (s.idf or {}).items():
            idf[t] = max(idf.get(t, 0.0), float(v))
    sqv = query_vector(question, idf)

    ids = [s.id for s in sources]
    name_of = {s.id: s.name for s in sources}
    rows = db.query(KbChunk).filter(KbChunk.source_id.in_(ids)).all()
    # 查询里的中文二元组：用于字面命中加成（钉准「噼啪响」「首层」这类具体说法）
    q_bigrams = {t for t in tokenize(question) if len(t) == 2 and _CJK_RE.match(t[0])}

    scored = []
    for ch in rows:
        d_full = _dense_cos(qv, ch.embedding) if ch.embedding else 0.0
        d_head = _dense_cos(qv, ch.embedding_heading) if ch.embedding_heading else 0.0
        dense = max(d_full, d_head)          # 标题向量通道：解决「答案写在标题里」的情况
        sparse = cosine(sqv, ch.vector or {}) if sqv else 0.0
        if dense < dense_min and sparse < sparse_min:
            continue
        literal = sum(1 for b in q_bigrams if b in ch.heading or b in ch.content)
        bonus = min(0.06, 0.02 * literal)
        scored.append({
            "heading": ch.heading, "content": ch.content,
            "score": round(dense + weight * sparse + bonus, 4),
            "dense": round(dense, 3), "sparse": round(sparse, 3), "literal": literal,
            "source": name_of.get(ch.source_id, ""), "mode": "hybrid",
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


# ---------------------------------------------------------------- 同步（幂等）

def ensure_columns(db: Session) -> None:
    """SQLite 不支持 create_all 加列：这里显式 ALTER（幂等，先查 PRAGMA）。"""
    from sqlalchemy import text
    wanted = (
        ("kb_chunks", "embedding", "ALTER TABLE kb_chunks ADD COLUMN embedding JSON"),
        ("kb_chunks", "embedding_heading", "ALTER TABLE kb_chunks ADD COLUMN embedding_heading JSON"),
        ("kb_sources", "embedding_model", "ALTER TABLE kb_sources ADD COLUMN embedding_model VARCHAR(128) DEFAULT ''"),
    )
    for table, column, ddl in wanted:
        cols = [r[1] for r in db.execute(text(f"PRAGMA table_info({table})")).fetchall()]
        if cols and column not in cols:
            db.execute(text(ddl))
            db.commit()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sync_file(db: Session, path: Path, force: bool = False) -> dict:
    """把单个 Markdown 文件同步进知识库（内容/embedding 模型未变则跳过）。

    同时构建两套索引：
      · 稀疏 TF-IDF（永远可用，embedding 不可用时兜底）
      · 稠密 embedding（本地 LM Studio）：正文向量 + 标题向量两条通道
    """
    name = path.name
    cfg = embedding_conf()
    chunks, idf = build_source(chunk_markdown(path.read_text(encoding="utf-8")))
    docs = [f"{c['heading']}\n{c['content']}" for c in chunks]
    heads = [c["heading"] for c in chunks]
    dense = embed_texts(docs, cfg) if cfg["enabled"] else None
    dense_head = embed_texts(heads, cfg) if dense else None
    mode = "dense" if dense else "sparse"
    model = (cfg["model"] or detect_model(cfg["base_url"])) if dense else ""
    # 哈希带上模式与模型：换模型/开关变化时自动重建
    fhash = f"{_file_hash(path)}|{mode}|{model}"
    src = db.query(KbSource).filter_by(name=name).first()
    if src and src.file_hash == fhash and not force:
        return {"name": name, "changed": False, "chunks": src.chunk_count, "mode": mode, "model": model}
    if src:
        db.query(KbChunk).filter_by(source_id=src.id).delete()
        src.path, src.file_hash, src.chunk_count, src.idf = str(path), fhash, len(chunks), idf
        src.embedding_model = model
        src.updated_at = _now()
    else:
        src = KbSource(name=name, path=str(path), file_hash=fhash, chunk_count=len(chunks),
                       idf=idf, embedding_model=model)
        db.add(src)
    db.flush()
    for i, c in enumerate(chunks):
        db.add(KbChunk(source_id=src.id, ordinal=i, heading=c["heading"][:256],
                       content=c["content"], vector=c["vector"], char_count=c["char_count"],
                       embedding=(dense[i] if dense else None),
                       embedding_heading=(dense_head[i] if dense_head else None)))
    db.commit()
    return {"name": name, "changed": True, "chunks": len(chunks), "tokens": len(idf),
            "mode": mode, "model": model}


def sync_all(db: Session, force: bool = False) -> list[dict]:
    """同步 kb 目录下所有 Markdown（启动时调用；幂等）。"""
    ensure_columns(db)
    if not KB_DIR.exists():
        return []
    return [sync_file(db, p, force=force) for p in sorted(KB_DIR.glob("*.md"))]


def status(db: Session) -> list[dict]:
    rows = db.query(KbSource).all()
    return [{"id": s.id, "name": s.name, "chunks": s.chunk_count,
             "tokens": len(s.idf or {}), "updated_at": s.updated_at,
             "mode": "dense" if (getattr(s, "embedding_model", "") or "") else "sparse",
             "embedding_model": getattr(s, "embedding_model", "") or ""} for s in rows]


def _now() -> str:
    from datetime import datetime
    return datetime.utcnow().isoformat(timespec="seconds")
