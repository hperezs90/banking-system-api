from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import auth, accounts, transactions, statements, users

app = FastAPI(
    title=settings.app_name,
    description="API REST para sistema bancario - Equipo 4 UMG Ingeniería de Software",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — en producción reemplazar con el dominio de Vercel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Actualizar con URL de Vercel en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(accounts.router)
app.include_router(transactions.router)
app.include_router(statements.router)


@app.get("/", tags=["Health"])
async def root():
    return {
        "app": settings.app_name,
        "status": "online",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
