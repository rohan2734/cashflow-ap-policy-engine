from contextlib import asynccontextmanager
from fastapi import FastAPI
from api.routes import router
from api.dependencies import get_db, set_config
from db.seeder import seed_defaults
from config.loader import load_config_from_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_db()
    await db.create_tables()
    async with db.session() as session:
        await seed_defaults(session)
        config = await load_config_from_db(session)
        set_config(config)
    yield


app = FastAPI(title="CashFlo Policy Engine", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
