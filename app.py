"""Data Doctor — Main FastAPI application."""

import os
import uuid
import io
import json

import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from agents.profiler import run_profiler
from agents.anomaly import run_anomaly_detection
from agents.feature_engineer import run_feature_engineer
from agents.supervisor import run_supervisor
from agents.visualizer import generate_visualizations
from agents.chat import init_chat_session, chat
from api.schemas import ChatRequest

load_dotenv()

app = FastAPI(title="Data Doctor", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory store for uploaded dataframes
_dataframes: dict[str, pd.DataFrame] = {}


@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse("templates/index.html")


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    """Upload a CSV and run the full analysis pipeline."""

    if not file.filename.endswith((".csv", ".tsv")):
        raise HTTPException(400, "Please upload a CSV or TSV file.")

    # Read the file
    try:
        content = await file.read()
        sep = "\t" if file.filename.endswith(".tsv") else ","
        df = pd.read_csv(io.BytesIO(content), sep=sep)
    except Exception as e:
        raise HTTPException(400, f"Failed to parse file: {str(e)}")

    if df.empty:
        raise HTTPException(400, "The uploaded file is empty.")

    if len(df.columns) > 200:
        raise HTTPException(400, "Too many columns (max 200).")

    # Generate session ID
    session_id = str(uuid.uuid4())
    _dataframes[session_id] = df

    # ── Run agent pipeline ─────────────────────────────────────
    # Agent 1: Profiler
    profile = run_profiler(df)

    # Agent 2: Anomaly Detective
    anomalies = run_anomaly_detection(df, profile)

    # Agent 3: Feature Engineer
    features = run_feature_engineer(df, profile)

    # Agent 4: Supervisor (QA + scoring + LLM summary)
    report = run_supervisor(profile, anomalies, features)

    # Generate visualizations
    charts = generate_visualizations(df, report)

    # Initialize chat session
    sample_json = df.head(5).to_json(orient="records", indent=2, default_handler=str)
    init_chat_session(session_id, report, sample_json)

    return {
        "session_id": session_id,
        "report": report.model_dump(),
        "charts": charts,
    }


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """Send a message to the chat agent."""
    if req.session_id not in _dataframes:
        raise HTTPException(404, "Session not found. Please upload a CSV first.")

    reply = chat(req.session_id, req.message)
    return {"reply": reply}


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
