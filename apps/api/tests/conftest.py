import os

# Testmiljö måste sättas innan app-modulerna importeras (get_settings cachar).
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("CF_TEAM_DOMAIN", "testteam.cloudflareaccess.com")
os.environ.setdefault("CF_ACCESS_AUD", "test-aud-tag")

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.auth as auth_module
from app.db import Base, get_session
from app.main import app
from app.models import User


@pytest.fixture
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def make_token(rsa_key, monkeypatch):
    """Skapar signerade JWT:er och pekar om JWKS-uppslaget till testnyckeln."""

    class FakeSigningKey:
        def __init__(self, key):
            self.key = key

    class FakeJWKSClient:
        def get_signing_key_from_jwt(self, token):
            return FakeSigningKey(rsa_key.public_key())

    monkeypatch.setattr(auth_module, "_jwks_client", lambda: FakeJWKSClient())

    def _make(
        email: str | None = "daniel@example.com",
        aud: str = "test-aud-tag",
        iss: str = "https://testteam.cloudflareaccess.com",
    ) -> str:
        claims: dict = {"aud": aud, "iss": iss}
        if email is not None:
            claims["email"] = email
        return jwt.encode(claims, rsa_key, algorithm="RS256")

    return _make


@pytest.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def client(db_session):
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def known_user(db_session) -> User:
    user = User(email="daniel@example.com", display_name="Daniel")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def other_user(db_session) -> User:
    user = User(email="anna@example.com", display_name="Anna")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
