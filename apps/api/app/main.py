from fastapi import FastAPI

from app.routers import admin, me

app = FastAPI(title="Bodify API", version="0.1.0")

app.include_router(me.router)
app.include_router(admin.router)


@app.get("/healthz", tags=["infra"])
async def healthz() -> dict:
    return {"status": "ok"}
