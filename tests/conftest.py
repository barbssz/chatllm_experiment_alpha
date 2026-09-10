from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app


@pytest.fixture(autouse=True)
def no_real_openrouter(monkeypatch):
    """A chave local nunca e usada em chamadas externas pelos testes."""
    monkeypatch.setattr("backend.services.openrouter.OPENROUTER_API_KEY", "")


@pytest.fixture
def engine():
    """Cria um engine SQLite em memoria para os testes."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def tables(engine):
    """Cria todas as tabelas antes dos testes e as remove ao final."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(engine, tables):
    """Cada teste possui seu proprio banco; commits/rollbacks reais ficam isolados."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with TestingSessionLocal() as session:
        yield session


@pytest.fixture
def client(db_session, engine, monkeypatch):
    """Retorna um TestClient do FastAPI com o banco de testes injetado."""

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    monkeypatch.setattr("backend.main.engine", engine)
    monkeypatch.setattr("backend.config.AUTH_COOKIE_SECURE", False)
    try:
        with TestClient(
            app, base_url="http://localhost:8000",
            headers={"X-Requested-With": "ChatLLM", "Origin": "http://localhost:8000"},
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def credentials():
    return {"email": "alice@example.com", "password": "uma frase secreta 123"}


@pytest.fixture
def authenticated_client(client, credentials):
    assert client.post("/api/auth/register", json=credentials).status_code == 201
    assert client.post("/api/auth/login", json=credentials).status_code == 200
    return client
