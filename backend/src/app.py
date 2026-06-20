# app.py
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from backend.src.routes.ai import ai_router
from backend.src.routes.langchain_ai import langchain_router
from backend.src.services.supabase_service import init_supabase
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

frontend_folder = os.path.join(os.getcwd(), "frontend", "dist")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_supabase()
    yield


app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost:5177",
    "http://127.0.0.1:5177",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Chat-ID"],
)

app.include_router(ai_router)
app.include_router(langchain_router)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "An internal server error occurred."},
    )


@app.get("/{path:path}")
async def serve_frontend(path: str):
    if path.startswith("api") or path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")

    filter_path = os.path.join(frontend_folder, path)

    if path and os.path.exists(filter_path) and os.path.isfile(filter_path):
        return FileResponse(filter_path)

    return FileResponse(os.path.join(frontend_folder, "index.html"))


if __name__ == "__main__":
    import uvicorn

    port_env = os.getenv("PORT", "5000")
    port = int(port_env) if port_env.isdigit() else 5000

    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    uvicorn.run("backend.src.app:app", host="0.0.0.0", port=port, reload=debug_mode)
