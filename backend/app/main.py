"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .routers import advisor, budgets, expenses, gmail, settings, upload


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(
    title="Finance Agent",
    description="Personal finance tracker with bank statement parsing and purchase advisor",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "https://moneyflow.skdev.one"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(expenses.router)
app.include_router(budgets.router)
app.include_router(upload.router)
app.include_router(advisor.router)
app.include_router(gmail.router)
app.include_router(settings.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
