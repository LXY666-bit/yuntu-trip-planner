"""数据库连接和会话管理"""

import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{DATA_DIR / 'trips.db'}")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def init_db():
    async with engine.begin() as conn:
        # attractions_cache 是可再生的缓存表：旧库缺新列时直接重建，
        # 避免 create_all 不做列迁移导致查询报 no such column
        from sqlalchemy import inspect, text
        from .models.db_models import AttractionCache

        def _migrate_cache(sync_conn):
            insp = inspect(sync_conn)
            if not insp.has_table(AttractionCache.__tablename__):
                return
            existing_cols = {c["name"] for c in insp.get_columns(AttractionCache.__tablename__)}
            expected_cols = {c.name for c in AttractionCache.__table__.columns}
            if existing_cols and not expected_cols.issubset(existing_cols):
                missing = expected_cols - existing_cols
                print(f"⚠️ attractions_cache 缺列 {missing}，删除旧缓存表以便重建")
                AttractionCache.__table__.drop(sync_conn, checkfirst=True)

        await conn.run_sync(_migrate_cache)
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
