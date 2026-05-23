"""
Database setup for the community brain: SQLAlchemy engine, Base, session factory,
and init_db() that enables pgvector and creates the schema.

Storage: PostgreSQL + pgvector (local via docker-compose).
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
import logging
import os

# Base class for ORM models (Fragment/Cluster/... are defined in core.store.fragments_db)
Base = declarative_base()

# PostgreSQL only. Default points at the local docker-compose db (port 5434, db wndrverse).
# Port 5434 chosen to NOT collide with ayda (5433).
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:localpass@localhost:5434/wndrverse",
)

# Normalize Railway/Render style postgres:// → postgresql:// (SQLAlchemy requirement)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Flag: is pgvector available on this PostgreSQL instance?
pgvector_available = False


def init_db():
    """Create the schema. Enables pgvector and builds the HNSW index for embeddings.

    The DB starts clean (fresh docker volume), so tables are created correct from
    the start — no ALTER migrations needed.
    """
    global pgvector_available

    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        pgvector_available = True
        logging.info("pgvector extension enabled")
    except Exception as e:
        pgvector_available = False
        logging.warning(f"pgvector not available, embedding features disabled: {e}")

    # Import models so they are registered with Base.metadata.
    # Must happen AFTER pgvector_available is set (the Vector column is conditional).
    import core.store.fragments_db  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Create HNSW index for embeddings (only if pgvector is available)
    if pgvector_available:
        try:
            with engine.connect() as conn:
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_fragments_embedding "
                    "ON fragments USING hnsw (embedding vector_cosine_ops)"
                ))
                conn.commit()
            logging.info("HNSW index created for fragments.embedding")
        except Exception as e:
            logging.warning(f"Could not create HNSW index: {e}")


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        # Delegate to the canonical core.db module, NOT this __main__ copy.
        # `python -m core.db` runs this file as __main__; fragments_db does
        # `from core.db import Base`, which loads core.db a SECOND time with a
        # different Base. Calling __main__.init_db() would create_all() on the
        # empty __main__ Base. Importing core.db.init_db here uses the same Base
        # the models registered on.
        import core.db as canonical
        canonical.init_db()
        print("init_db() done")
    else:
        print("usage: python -m core.db init")
