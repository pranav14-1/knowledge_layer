import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

# Anchor default database to repository root so running from /backend or root uses same DB
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__)) # /backend/app
_REPO_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, "..", "..")) # /knowledge_layer
_DEFAULT_DB_PATH = os.path.join(_REPO_ROOT, "facts.db")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_DEFAULT_DB_PATH}")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_schema(eng=engine):
    """Guarantees backward compatibility by ensuring all required columns exist in SQLite."""
    try:
        with eng.connect() as conn:
            res = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='documents'"))
            if res.fetchone():
                info = conn.execute(text("PRAGMA table_info(documents)")).fetchall()
                existing_cols = {col[1] for col in info}
                if "progress" not in existing_cols:
                    conn.execute(text("ALTER TABLE documents ADD COLUMN progress INTEGER NOT NULL DEFAULT 0"))
                if "error_message" not in existing_cols:
                    conn.execute(text("ALTER TABLE documents ADD COLUMN error_message TEXT"))
                if "status" not in existing_cols:
                    conn.execute(text("ALTER TABLE documents ADD COLUMN status VARCHAR(50) NOT NULL DEFAULT 'QUEUED'"))
                if "chat_session_id" not in existing_cols:
                    conn.execute(text("ALTER TABLE documents ADD COLUMN chat_session_id INTEGER"))
                conn.commit()

            res = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_sessions'"))
            if res.fetchone():
                info = conn.execute(text("PRAGMA table_info(chat_sessions)")).fetchall()
                existing_cols = {col[1] for col in info}
                if "updated_at" not in existing_cols:
                    conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN updated_at DATETIME"))
                conn.commit()
    except Exception as e:
        # StaticPool or in-memory test databases might ignore pragmas
        pass


def init_db():
    """Initializes tables and runs schema migration checks."""
    from datetime import datetime
    Base.metadata.create_all(bind=engine)
    ensure_schema(engine)

    # Guarantee at least one workspace exists and associate any unassigned docs
    try:
        with SessionLocal() as db:
            from app.models import ChatSession, Document
            first_session = db.query(ChatSession).order_by(ChatSession.id.asc()).first()
            if not first_session:
                now = datetime.utcnow()
                first_session = ChatSession(title="Default Workspace", created_at=now, updated_at=now)
                db.add(first_session)
                db.commit()
                db.refresh(first_session)

            # Assign orphaned documents to default workspace
            orphaned = db.query(Document).filter(Document.chat_session_id.is_(None)).all()
            if orphaned:
                for doc in orphaned:
                    doc.chat_session_id = first_session.id
                db.commit()
    except Exception as e:
        pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

