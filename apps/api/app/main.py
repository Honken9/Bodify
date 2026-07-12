from fastapi import FastAPI

from app.routers import admin, exercises, food, me, meals, programs, sessions

app = FastAPI(title="Bodify API", version="0.1.0")

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


@app.get("/healthz", tags=["infra"])
async def healthz() -> dict:
    return {"status": "ok"}
