from collections.abc import Iterator

from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tts_service.db.base import Base


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite" and url.database:
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
