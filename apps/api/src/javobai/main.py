from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from javobai.ai_settings.router import router as ai_settings_router
from javobai.analytics.router import router as analytics_router
from javobai.auth.router import router as auth_router
from javobai.channels.router import router as channels_router
from javobai.config import settings
from javobai.faqs.router import router as faqs_router
from javobai.inbox.router import router as inbox_router
from javobai.internal.router import router as internal_router
from javobai.rules.router import router as rules_router
from javobai.tenants.router import router as tenants_router
from javobai.webhooks.telegram import router as telegram_webhook_router
from javobai.webhooks.whatsapp import router as whatsapp_webhook_router, channels_router as whatsapp_channels_router
from javobai.webhooks.meta import router as meta_webhook_router
from javobai.flows.router import router as flows_router
from javobai.actions.router import router as actions_router
from javobai.growth.router import router as growth_router, public_router as growth_public_router
from javobai.ws.router import router as ws_router
from javobai.ws.router import start_event_listener, stop_event_listener


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.arq = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    app.state.ws_listener_task = start_event_listener()
    yield
    await stop_event_listener(app.state.ws_listener_task)
    await app.state.arq.aclose()


app = FastAPI(
    title="JavobAI API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(tenants_router)
app.include_router(faqs_router)
app.include_router(channels_router)
app.include_router(rules_router)
app.include_router(ai_settings_router)
app.include_router(inbox_router)
app.include_router(ws_router)
app.include_router(telegram_webhook_router)
app.include_router(whatsapp_webhook_router)
app.include_router(whatsapp_channels_router)
app.include_router(meta_webhook_router)
app.include_router(flows_router)
app.include_router(actions_router)
app.include_router(growth_router)
app.include_router(growth_public_router)
app.include_router(analytics_router)
if settings.environment != "production":
    app.include_router(internal_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
