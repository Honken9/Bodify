import time
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import (
    admin,
    ai,
    cardio,
    dashboard,
    exercises,
    food,
    goals,
    integrations,
    me,
    meals,
    metrics,
    photos,
    programs,
    push,
    sessions,
    social,
    webhooks,
)


def _startup_checks() -> None:
    """Vägrar starta med en osäker produktionskonfiguration.

    Produktion = Cloudflare Access är konfigurerat (CF_ACCESS_AUD satt).
    Lokal utveckling utan Access påverkas inte."""
    settings = get_settings()
    if not settings.cf_access_aud:
        return
    if settings.secret_key == "dev-secret-change-me":
        raise RuntimeError(
            "SECRET_KEY har kvar standardvärdet. Sätt ett långt slumpvärde "
            "i .env (t.ex. `openssl rand -hex 32`) innan produktionstart."
        )
    if settings.dev_auth_email:
        raise RuntimeError(
            "DEV_AUTH_EMAIL får inte vara satt när Cloudflare Access används "
            "— det skulle kringgå all inloggning. Ta bort den ur .env."
        )


_startup_checks()

app = FastAPI(title="Bodify API", version="0.1.0")


# ── CSRF-skydd ────────────────────────────────────────────────
# Cloudflare Access autentiserar även via cookie (CF_Authorization),
# så en främmande sajt kan tvinga inloggade webbläsare att skicka
# state-ändrande anrop. Origin-kontrollen stoppar det: skrivande
# anrop från en annan origin än vår egen nekas. Webhooks undantas —
# de anropas server-till-server och skyddas av egna hemligheter.

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _allowed_origins(request: Request) -> set[str]:
    allowed = set()
    public = urlsplit(get_settings().public_base_url).netloc
    if public:
        allowed.add(public)
    host = request.headers.get("host")
    if host:
        allowed.add(host)
    return allowed


@app.middleware("http")
async def csrf_origin_check(request: Request, call_next):
    if (
        request.method not in _SAFE_METHODS
        and not request.url.path.startswith("/api/webhooks")
    ):
        origin = request.headers.get("origin")
        if origin:
            if urlsplit(origin).netloc not in _allowed_origins(request):
                return JSONResponse(
                    {"detail": "Anropet kommer från fel origin."}, status_code=403
                )
    return await call_next(request)


# ── Rate limiting för webhooks ────────────────────────────────
# Webhook-endpoints nås utan Cloudflare Access och skyddas därför
# extra mot flödesattacker: enkel minutbudget per klient-IP.

_RATE_LIMIT_PER_MINUTE = 60
_rate_buckets: dict[str, tuple[int, int]] = {}


def _client_ip(request: Request) -> str:
    return (
        request.headers.get("cf-connecting-ip")
        or (request.client.host if request.client else "unknown")
    )


@app.middleware("http")
async def webhook_rate_limit(request: Request, call_next):
    if request.url.path.startswith("/api/webhooks"):
        minute = int(time.time() // 60)
        key = _client_ip(request)
        count, bucket_minute = _rate_buckets.get(key, (0, minute))
        if bucket_minute != minute:
            count = 0
        count += 1
        _rate_buckets[key] = (count, minute)
        if len(_rate_buckets) > 10_000:  # svältskydd för minnet
            _rate_buckets.clear()
        if count > _RATE_LIMIT_PER_MINUTE:
            return JSONResponse(
                {"detail": "För många anrop — försök igen om en stund."},
                status_code=429,
            )
    return await call_next(request)


app.include_router(me.router)
app.include_router(admin.router)
app.include_router(exercises.router)
app.include_router(programs.router)
app.include_router(programs.active_router)
app.include_router(sessions.router)
app.include_router(food.router)
app.include_router(meals.router)
app.include_router(meals.templates_router)
app.include_router(meals.targets_router)
app.include_router(integrations.router)
app.include_router(webhooks.router)
app.include_router(metrics.router)
app.include_router(cardio.router)
app.include_router(goals.router)
app.include_router(dashboard.router)
app.include_router(photos.router)
app.include_router(push.router)
app.include_router(social.router)
app.include_router(ai.router)


@app.get("/healthz", tags=["infra"])
async def healthz() -> dict:
    return {"status": "ok"}
