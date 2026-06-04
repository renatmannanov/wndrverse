"""
Fragment storage: SQLAlchemy models + CRUD for the fragments/clusters/
fragment_clusters/artifacts tables. Uses pgvector for embedding storage and
similarity search when available.

Ported from ayda_think with two community fields added (topic, author_name)
and a digest-selection query (get_fragments_for_digest).
"""

from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean, DateTime, ForeignKey,
    UniqueConstraint, func, or_
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from datetime import datetime
import logging

import core.db as _db
from core.db import Base, SessionLocal

# ---------------------------------------------------------------------------
# Conditional pgvector import
# ---------------------------------------------------------------------------
# Read pgvector_available dynamically from db module (not a copied value)
# because init_db() sets it to True AFTER this module may have been imported.
try:
    from pgvector.sqlalchemy import Vector
    _pgvector_import_ok = True
except ImportError:
    _pgvector_import_ok = False


def _pgvector_available() -> bool:
    """Check if pgvector is available (lazy DB probe, cached in db module)."""
    return _db.ensure_pgvector_checked() and _pgvector_import_ok

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Fragment(Base):
    __tablename__ = 'fragments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(255), unique=True, nullable=True)
    source = Column(String(50), nullable=False)          # telegram, instagram, ...
    text = Column(Text, nullable=False)
    tags = Column(ARRAY(Text), default=[])
    created_at = Column(DateTime, nullable=False)
    indexed_at = Column(DateTime, default=datetime.utcnow)
    metadata_ = Column('metadata', JSONB, default={})    # 'metadata' is reserved in SQLAlchemy
    content_type = Column(String(20), default='note')    # note / link / quote / repost
    language = Column(String(5), nullable=True)           # ru / en / mixed
    is_duplicate = Column(Boolean, default=False)
    is_outdated = Column(Boolean, default=False)
    sender_id = Column(BigInteger, nullable=True)          # Telegram user ID of author
    channel_id = Column(BigInteger, nullable=True)         # Telegram chat ID (-100 format)
    message_thread_id = Column(BigInteger, nullable=True)  # Forum topic / thread root id
    # --- community fields ---
    topic = Column(String(50), nullable=True, index=True)  # intro/offerings/harvest/...
    author_name = Column(String(255), nullable=True)       # sender_name at message time
    if _pgvector_import_ok:
        embedding = Column(Vector(1536), nullable=True)


class Cluster(Base):
    __tablename__ = 'clusters'

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Integer, nullable=False)
    label = Column(Integer, nullable=False)
    size = Column(Integer, default=0)
    preview = Column(Text, nullable=True)
    name = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('version', 'label', name='uq_cluster_version_label'),
    )


class FragmentCluster(Base):
    __tablename__ = 'fragment_clusters'

    fragment_id = Column(Integer, ForeignKey('fragments.id'), primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id'))
    version = Column(Integer, primary_key=True)


class Artifact(Base):
    __tablename__ = 'artifacts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    cluster_id = Column(Integer, ForeignKey('clusters.id'), nullable=True)
    fragment_ids = Column(ARRAY(Integer), default=[])
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# CRUD — insert
# ---------------------------------------------------------------------------

def insert_fragment(
    source: str,
    text: str,
    created_at: datetime,
    tags: list[str] | None = None,
    content_type: str = 'note',
    metadata: dict | None = None,
    external_id: str | None = None,
    topic: str | None = None,
    author_name: str | None = None,
    sender_id: int | None = None,
    channel_id: int | None = None,
    message_thread_id: int | None = None,
) -> int | None:
    """Insert a fragment. Returns fragment id, or None if duplicate (by external_id)."""
    session = SessionLocal()
    try:
        frag = Fragment(
            external_id=external_id,
            source=source,
            text=text,
            created_at=created_at,
            tags=tags or [],
            content_type=content_type,
            metadata_=metadata or {},
            topic=topic,
            author_name=author_name,
            sender_id=sender_id,
            channel_id=channel_id,
            message_thread_id=message_thread_id,
        )
        session.add(frag)
        session.commit()
        return frag.id
    except Exception:
        session.rollback()
        return None
    finally:
        session.close()


def insert_fragments_batch(fragments: list[dict]) -> dict:
    """
    Insert multiple fragments. Skips duplicates by external_id.
    Returns {'indexed': N, 'duplicates_skipped': N, 'inserted_ids': [int]}.
    Each dict may carry: external_id, source, text, created_at, tags, content_type,
    metadata, topic, author_name, sender_id, channel_id, message_thread_id.
    """
    session = SessionLocal()
    indexed = 0
    skipped = 0
    inserted_ids = []
    try:
        for f in fragments:
            # Check duplicate by external_id
            if f.get('external_id'):
                exists = session.query(Fragment.id).filter(
                    Fragment.external_id == f['external_id']
                ).first()
                if exists:
                    skipped += 1
                    continue

            frag = Fragment(
                external_id=f.get('external_id'),
                source=f['source'],
                text=f['text'],
                created_at=f['created_at'],
                tags=f.get('tags', []),
                content_type=f.get('content_type', 'note'),
                metadata_=f.get('metadata', {}),
                topic=f.get('topic'),
                author_name=f.get('author_name'),
                sender_id=f.get('sender_id'),
                channel_id=f.get('channel_id'),
                message_thread_id=f.get('message_thread_id'),
            )
            session.add(frag)
            session.flush()  # get frag.id before commit
            inserted_ids.append(frag.id)
            indexed += 1

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return {'indexed': indexed, 'duplicates_skipped': skipped, 'inserted_ids': inserted_ids}


# ---------------------------------------------------------------------------
# CRUD — read
# ---------------------------------------------------------------------------

def get_fragments_count() -> int:
    """Total number of fragments."""
    session = SessionLocal()
    try:
        return session.query(func.count(Fragment.id)).scalar()
    finally:
        session.close()


def get_fragments_for_digest(
    topic: str | None,
    since: datetime | None,
    until: datetime | None = None,
    min_chars: int = 150,
) -> list[dict]:
    """Fragments for digest synthesis.

    Filters: topic == topic (if given), created_at >= since (if given),
    created_at < until (if given — UPPER bound EXCLUSIVE),
    char_length(text) >= min_chars, is_duplicate IS NOT TRUE. Sorted by created_at.

    For an inclusive `from..till` day range the caller passes
    until = date_till + 1 day (next midnight), so a fragment at 23:59 on
    date_till is included. created_at is UTC.

    Returns [{id, text, created_at, author_name, sender_id, tags}, ...].
    NOTE: created_at is returned as an ISO STRING (.isoformat()), matching all the
    other query functions in this file — synthesis does f['created_at'][:10].
    """
    session = SessionLocal()
    try:
        query = session.query(
            Fragment.id,
            Fragment.text,
            Fragment.created_at,
            Fragment.author_name,
            Fragment.sender_id,
            Fragment.tags,
        ).filter(Fragment.is_duplicate.isnot(True))

        if topic is not None:
            query = query.filter(Fragment.topic == topic)
        if since is not None:
            query = query.filter(Fragment.created_at >= since)
        if until is not None:
            query = query.filter(Fragment.created_at < until)
        query = query.filter(func.char_length(Fragment.text) >= min_chars)
        query = query.order_by(Fragment.created_at)

        results = query.all()
        return [
            {
                'id': r.id,
                'text': r.text,
                'created_at': r.created_at.isoformat() if r.created_at else None,
                'author_name': r.author_name,
                'sender_id': r.sender_id,
                'tags': r.tags or [],
            }
            for r in results
        ]
    finally:
        session.close()


def search_by_embedding(embedding: list[float], limit: int = 10) -> list[dict]:
    """Find closest fragments by cosine distance. Requires pgvector + embeddings."""
    if not _pgvector_available():
        logging.warning("search_by_embedding called but pgvector is not available")
        return []

    session = SessionLocal()
    try:
        results = (
            session.query(
                Fragment.id,
                Fragment.external_id,
                Fragment.text,
                Fragment.source,
                Fragment.tags,
                Fragment.created_at,
                Fragment.content_type,
                Fragment.embedding.cosine_distance(embedding).label('distance')
            )
            .filter(Fragment.embedding.isnot(None))
            .filter(Fragment.is_duplicate.isnot(True))
            .order_by('distance')
            .limit(limit)
            .all()
        )
        return [
            {
                'id': r.id,
                'external_id': r.external_id,
                'text': r.text,
                'source': r.source,
                'tags': r.tags,
                'created_at': r.created_at.isoformat(),
                'content_type': r.content_type,
                'distance': float(r.distance),
            }
            for r in results
        ]
    finally:
        session.close()


def get_unembedded_fragments(limit: int = 100) -> list[dict]:
    """Get fragments without embeddings (embedding IS NULL, is_duplicate=False)."""
    if not _pgvector_available():
        logging.warning("get_unembedded_fragments called but pgvector is not available")
        return []

    session = SessionLocal()
    try:
        results = (
            session.query(Fragment.id, Fragment.text)
            .filter(Fragment.embedding.is_(None))
            .filter(Fragment.is_duplicate.isnot(True))
            .limit(limit)
            .all()
        )
        return [{'id': r.id, 'text': r.text} for r in results]
    finally:
        session.close()


def count_unembedded_fragments() -> int:
    """Count fragments without embeddings (for --estimate and progress)."""
    if not _pgvector_available():
        return 0
    session = SessionLocal()
    try:
        return (
            session.query(func.count(Fragment.id))
            .filter(Fragment.embedding.is_(None))
            .filter(Fragment.is_duplicate.isnot(True))
            .scalar()
        )
    finally:
        session.close()


def sum_unembedded_chars() -> int:
    """Sum of text length over unembedded fragments (for cost --estimate)."""
    if not _pgvector_available():
        return 0
    session = SessionLocal()
    try:
        total = (
            session.query(func.coalesce(func.sum(func.char_length(Fragment.text)), 0))
            .filter(Fragment.embedding.is_(None))
            .filter(Fragment.is_duplicate.isnot(True))
            .scalar()
        )
        return int(total or 0)
    finally:
        session.close()


def update_embedding(fragment_id: int, embedding: list[float]) -> None:
    """Save embedding for a fragment."""
    session = SessionLocal()
    try:
        session.query(Fragment).filter(Fragment.id == fragment_id).update(
            {Fragment.embedding: embedding}
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def update_fragment_fields(fragment_id: int, **fields) -> None:
    """Update arbitrary fields (language, is_duplicate, is_outdated)."""
    session = SessionLocal()
    try:
        session.query(Fragment).filter(Fragment.id == fragment_id).update(
            {getattr(Fragment, k): v for k, v in fields.items()}
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def find_near_duplicates(
    embedding: list[float],
    threshold: float = 0.95,
    exclude_id: int | None = None,
) -> list[dict]:
    """Find fragments with cosine similarity > threshold.
    Only compares against originals (is_duplicate=False).
    """
    if not _pgvector_available():
        logging.warning("find_near_duplicates called but pgvector is not available")
        return []

    session = SessionLocal()
    try:
        query = (
            session.query(
                Fragment.id,
                Fragment.text,
                Fragment.embedding.cosine_distance(embedding).label('distance')
            )
            .filter(Fragment.embedding.isnot(None))
            .filter(Fragment.is_duplicate.isnot(True))
            .filter(
                Fragment.embedding.cosine_distance(embedding) < (1 - threshold)
            )
        )
        if exclude_id is not None:
            query = query.filter(Fragment.id != exclude_id)

        results = query.order_by('distance').all()
        return [
            {'id': r.id, 'text': r.text, 'distance': float(r.distance)}
            for r in results
        ]
    finally:
        session.close()


def get_fragments_by_ids(fragment_ids: list[int]) -> list[dict]:
    """Get fragments by list of IDs. Returns {id, text, created_at, author_name, sender_id}."""
    session = SessionLocal()
    try:
        results = (
            session.query(
                Fragment.id, Fragment.text, Fragment.created_at,
                Fragment.author_name, Fragment.sender_id,
            )
            .filter(Fragment.id.in_(fragment_ids))
            .all()
        )
        return [
            {
                'id': r.id,
                'text': r.text,
                'created_at': r.created_at.isoformat() if r.created_at else None,
                'author_name': r.author_name,
                'sender_id': r.sender_id,
            }
            for r in results
        ]
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Cluster CRUD (kept for the clustering feature, not used in MVP digest)
# ---------------------------------------------------------------------------

def get_all_embedded_fragments() -> list[dict]:
    """All fragments with embeddings (excluding duplicates).
    Returns [{id, embedding, tags, text, created_at}, ...].
    """
    if not _pgvector_available():
        logging.warning("get_all_embedded_fragments called but pgvector is not available")
        return []

    session = SessionLocal()
    try:
        results = (
            session.query(
                Fragment.id,
                Fragment.embedding,
                Fragment.tags,
                Fragment.text,
                Fragment.created_at,
            )
            .filter(Fragment.embedding.isnot(None))
            .filter(Fragment.is_duplicate.isnot(True))
            .all()
        )
        return [
            {
                'id': r.id,
                'embedding': list(r.embedding),
                'tags': r.tags or [],
                'text': r.text,
                'created_at': r.created_at,
            }
            for r in results
        ]
    finally:
        session.close()


def get_latest_cluster_version() -> int | None:
    """Max version from clusters table. None if no clusters exist."""
    session = SessionLocal()
    try:
        return session.query(func.max(Cluster.version)).scalar()
    finally:
        session.close()


def save_cluster_results(version: int, clusters_data: list[dict]) -> None:
    """Save clustering results in a single transaction.
    clusters_data: [{label, size, preview, fragment_ids, name}, ...]
    """
    session = SessionLocal()
    try:
        for cd in clusters_data:
            cluster = Cluster(
                version=version,
                label=cd['label'],
                size=cd['size'],
                preview=cd['preview'],
                name=cd.get('name', ''),
            )
            session.add(cluster)
            session.flush()  # get cluster.id

            for fid in cd['fragment_ids']:
                fc = FragmentCluster(
                    fragment_id=fid,
                    cluster_id=cluster.id,
                    version=version,
                )
                session.add(fc)

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_clusters_by_version(version: int) -> list[dict]:
    """Clusters for a given version, sorted by size DESC."""
    session = SessionLocal()
    try:
        results = (
            session.query(Cluster)
            .filter(Cluster.version == version)
            .order_by(Cluster.size.desc())
            .all()
        )
        return [
            {
                'id': r.id,
                'label': r.label,
                'size': r.size,
                'preview': r.preview,
                'name': r.name or '',
                'created_at': r.created_at.isoformat() if r.created_at else None,
            }
            for r in results
        ]
    finally:
        session.close()


def get_cluster_fragments(cluster_id: int, limit: int = 10, offset: int = 0) -> list[dict]:
    """Fragments of a specific cluster, sorted by created_at. Paginated."""
    session = SessionLocal()
    try:
        results = (
            session.query(
                Fragment.id,
                Fragment.external_id,
                Fragment.text,
                Fragment.tags,
                Fragment.created_at,
            )
            .join(FragmentCluster, FragmentCluster.fragment_id == Fragment.id)
            .filter(FragmentCluster.cluster_id == cluster_id)
            .order_by(Fragment.created_at)
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [
            {
                'id': r.id,
                'external_id': r.external_id,
                'text': r.text,
                'tags': r.tags or [],
                'created_at': r.created_at.isoformat() if r.created_at else None,
            }
            for r in results
        ]
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Artifact CRUD
# ---------------------------------------------------------------------------

def save_artifact(
    topic: str,
    content: str,
    fragment_ids: list[int],
    cluster_id: int | None = None,
) -> int:
    """Save artifact (a generated digest). Returns id."""
    session = SessionLocal()
    try:
        artifact = Artifact(
            topic=topic,
            content=content,
            fragment_ids=fragment_ids,
            cluster_id=cluster_id,
        )
        session.add(artifact)
        session.commit()
        return artifact.id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_artifacts_count() -> int:
    """Total number of artifacts."""
    session = SessionLocal()
    try:
        return session.query(func.count(Artifact.id)).scalar()
    finally:
        session.close()


def get_latest_artifacts(limit: int = 10) -> list[dict]:
    """Latest artifacts by date."""
    session = SessionLocal()
    try:
        results = (
            session.query(Artifact)
            .order_by(Artifact.created_at.desc())
            .limit(limit)
            .all()
        )
        return [_artifact_to_dict(r) for r in results]
    finally:
        session.close()


def _artifact_to_dict(a: Artifact) -> dict:
    return {
        'id': a.id,
        'topic': a.topic,
        'content': a.content,
        'cluster_id': a.cluster_id,
        'fragment_ids': a.fragment_ids or [],
        'created_at': a.created_at.isoformat() if a.created_at else None,
    }
