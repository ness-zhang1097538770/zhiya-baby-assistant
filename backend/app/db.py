"""SQLite 数据库引擎与会话。"""
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

# 确保数据库目录存在
_db_dir = os.path.dirname(os.path.abspath(settings.db_path))
os.makedirs(_db_dir, exist_ok=True)

engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(engine, "connect")
def _enable_wal(dbapi_connection, connection_record):
    """WAL 模式：故事插画并发生成时，成本日志的并发写不被主线程读事务阻塞。"""
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
