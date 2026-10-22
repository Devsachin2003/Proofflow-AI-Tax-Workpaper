"""Test fixtures: a dedicated Postgres database, migrated from scratch and loaded with the packet once per run."""

import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.db import session as db_session

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _test_url() -> str:
    url = get_settings().test_database_url
    if not url:
        pytest.exit("TEST_DATABASE_URL is not set", returncode=2)
    return url


@pytest.fixture(scope="session", autouse=True)
def database():
    url = _test_url()
    eng = create_engine(url)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    eng.dispose()

    os.environ["ALEMBIC_DATABASE_URL"] = url
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    command.upgrade(cfg, "head")

    db_session.configure(url)
    from app.services.importer import import_packet

    db = db_session.session_factory()()
    try:
        result = import_packet(db, get_settings().packet_path)
    finally:
        db.close()
    yield result


@pytest.fixture()
def db():
    s = db_session.session_factory()()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture()
def fresh_workpaper(db):
    """Reset the human workpaper layer so a test starts from the imported baseline."""
    from app.services.admin import reset_workpaper

    reset_workpaper(db, validate=False)
    yield


@pytest.fixture(scope="session")
def client():
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


def as_user(user_id: str) -> dict[str, str]:
    return {"X-Demo-User": user_id}
