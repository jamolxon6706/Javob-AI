from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from javobai.auth.router import router as auth_router
from javobai.config import settings
from javobai.faqs.router import router as faqs_router
from javobai.tenants.router import router as tenants_router

app = FastAPI(
    title="JavobAI API",
    version="0.1.0",
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
