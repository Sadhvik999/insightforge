
import os
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Header, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import pandas as pd
import numpy as np
import math

from app.inspector import inspect_dataset
from app.cleaner import clean_dataset
from app.agent import analyze_dataset
from app.export_store import save_cleaned_export, get_cleaned_export
from app.llm_client import (
    set_session_config,
    get_session_config,
    clear_session_config,
    verify_provider_connection,
    mask_api_key,
    generate_session_id,
    validate_session_id,
    issue_session_token,
    register_session_token,
    verify_session_token,
    is_session_issued,
    validate_custom_api_url,
    check_connection_test_rate_limit,
    reset_connection_test_rate_limits,
)

from app.conversation_store import (
    create_conversation,
    get_conversation,
    update_conversation
)


app = FastAPI(
    title="InsightForge API",
    version="1.0.0",
    description="API for InsightForge - AI-powered Data Analytics Platform"
)

# Enable CORS for local frontend development and production HTTPS deployments
DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
env_origins = os.environ.get("CORS_ORIGINS")
allowed_origins = [o.strip() for o in env_origins.split(",") if o.strip()] if env_origins else DEFAULT_CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


# --------------------------------------------------
# Helper: Convert NumPy values into JSON-safe values
# --------------------------------------------------

def make_json_safe(data):

    if isinstance(data, dict):
        return {
            str(key): make_json_safe(value)
            for key, value in data.items()
        }

    elif isinstance(data, (list, tuple)):
        return [make_json_safe(value) for value in data]

    elif isinstance(data, np.ndarray):
        return make_json_safe(data.tolist())

    elif isinstance(data, np.generic):
        return make_json_safe(data.item())

    elif isinstance(data, float) and not math.isfinite(data):
        return None

    return data


# --------------------------------------------------
# Home Endpoint
# --------------------------------------------------

@app.get("/")
def home():

    return {
        "message": "Welcome to InsightForge API!",
        "status": "running"
    }


# --------------------------------------------------
# Health Check Endpoint
# --------------------------------------------------

@app.get("/health")
def health_check():

    return {
        "status": "healthy"
    }


# --------------------------------------------------
# AI Provider Configuration Endpoints (BYOK)
# --------------------------------------------------

class ConfigPayload(BaseModel):
    session_id: str | None = None
    provider: str = "ollama"
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None


@app.post("/config/session")
async def create_ai_session():
    """Generate, register, and issue an authoritative cryptographically random session token."""
    new_id = issue_session_token()
    return JSONResponse(content={"session_id": new_id})


@app.post("/config/test")
async def test_ai_config(
    request: Request,
    payload: ConfigPayload | None = None,
    x_session_id: str | None = Header(None, alias="X-Session-ID")
):
    # 1. Sliding window rate limit per client IP (20 requests / 60 seconds)
    client_ip = request.client.host if request.client else "unknown"
    if not check_connection_test_rate_limit(f"ip:{client_ip}", max_requests=20, window_seconds=60):
        raise HTTPException(
            status_code=429,
            detail="Too many connection test requests from this IP address. Please wait a minute before retrying."
        )

    # 2. Extract and enforce valid server-issued session token
    target_token = x_session_id or (payload.session_id if payload else None)
    if not target_token:
        raise HTTPException(
            status_code=400,
            detail="A valid server-issued session token is required to test AI configuration."
        )

    try:
        valid_session_id = verify_session_token(target_token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 3. Sliding window rate limit per session (10 requests / 60 seconds)
    if not check_connection_test_rate_limit(f"sess:{valid_session_id}", max_requests=10, window_seconds=60):
        raise HTTPException(
            status_code=429,
            detail="Too many connection test requests for this session. Please wait a minute before retrying."
        )

    p = payload or ConfigPayload()
    result = verify_provider_connection(
        provider=p.provider,
        api_key=p.api_key,
        model=p.model,
        base_url=p.base_url
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("detail", "Connection test failed.")
        )
    return JSONResponse(content=result)


@app.post("/config/save")
async def save_ai_config(
    payload: ConfigPayload | None = None,
    x_session_id: str | None = Header(None, alias="X-Session-ID")
):
    p = payload or ConfigPayload()
    target_token = x_session_id or p.session_id
    if not target_token:
        raise HTTPException(
            status_code=400,
            detail="A valid server-issued session token is required to save configuration."
        )
    try:
        target_session_id = verify_session_token(target_token)
        saved = set_session_config(
            session_id=target_session_id,
            provider=p.provider,
            api_key=p.api_key,
            model=p.model,
            base_url=p.base_url
        )
        return JSONResponse(content={"success": True, "config": saved})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/config/clear")
async def clear_ai_config(
    payload: ConfigPayload | None = None,
    x_session_id: str | None = Header(None, alias="X-Session-ID")
):
    target_token = x_session_id or (payload.session_id if payload else None)
    if not target_token:
        raise HTTPException(status_code=400, detail="session_id is required.")
    try:
        valid_id = verify_session_token(target_token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    cleared = clear_session_config(valid_id)
    return JSONResponse(content={"success": True, "cleared": cleared})


@app.get("/config/current")
async def get_current_ai_config(
    session_id: str | None = None,
    x_session_id: str | None = Header(None, alias="X-Session-ID")
):
    target_token = x_session_id or session_id
    valid_id = None
    if target_token:
        try:
            valid_id = verify_session_token(target_token)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        cfg = get_session_config(valid_id)
    else:
        cfg = get_session_config(None)

    return JSONResponse(content={
        "session_id": valid_id,
        "provider": cfg.get("provider", "ollama"),
        "model": cfg.get("model"),
        "base_url": cfg.get("base_url"),
        "has_api_key": bool(cfg.get("api_key")),
        "masked_key": mask_api_key(cfg.get("api_key"))
    })


# --------------------------------------------------
# Dataset Inspection Endpoint
# --------------------------------------------------

@app.post("/inspect")
async def inspect_file(file: UploadFile = File(...)):

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported"
        )

    try:
        df = pd.read_csv(
            file.file,
            encoding="latin1"
        )

        report = inspect_dataset(df)

        safe_report = make_json_safe(report)

        return JSONResponse(content=safe_report)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        await file.close()


# --------------------------------------------------
# Dataset Cleaning Endpoint
# --------------------------------------------------

@app.post("/clean")
async def clean_file(
    file: UploadFile = File(...),
    threshold: float = Form(75.0),
    numerical_strategy: str = Form("median"),
    categorical_fallback: str = Form("Unknown"),
    remove_duplicates: bool = Form(True),
    outlier_treatment: str = Form("detect"),
    approved_drop_columns: str | None = Form(None)
):

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported"
        )

    if threshold < 1 or threshold > 100:
        raise HTTPException(
            status_code=400,
            detail="Threshold must be between 1 and 100 inclusive"
        )

    if numerical_strategy not in ["median", "mean"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid numerical strategy '{numerical_strategy}'. Must be 'median' or 'mean'."
        )

    if outlier_treatment not in ["detect", "remove", "cap"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid outlier treatment '{outlier_treatment}'. Must be 'detect', 'remove', or 'cap'."
        )

    try:
        df = pd.read_csv(
            file.file,
            encoding="latin1"
        )

        cleaned_df, cleaning_report = clean_dataset(
            df,
            missing_threshold=threshold,
            numerical_strategy=numerical_strategy,
            categorical_fallback=categorical_fallback,
            remove_duplicate_rows=remove_duplicates,
            outlier_treatment=outlier_treatment,
            approved_drop_columns=approved_drop_columns
        )

        download_id, download_filename, _ = save_cleaned_export(
            cleaned_df,
            original_filename=file.filename
        )

        response = {
            "original_rows": len(df),
            "cleaned_rows": len(cleaned_df),
            "original_columns": len(df.columns),
            "cleaned_columns": len(cleaned_df.columns),
            "columns": cleaned_df.columns.tolist(),
            "cleaning_report": cleaning_report,
            "download_id": download_id,
            "download_url": f"/clean/download/{download_id}",
            "download_filename": download_filename
        }

        safe_response = make_json_safe(response)

        return JSONResponse(content=safe_response)

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        await file.close()


# --------------------------------------------------
# Cleaned Dataset Download Endpoint
# --------------------------------------------------

@app.get("/clean/download/{download_id}")
async def download_cleaned_file(download_id: str):

    try:
        export_path, filename = get_cleaned_export(download_id)
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=404,
            detail="Download not found or has expired. Please re-run the cleaning pipeline."
        )

    if not export_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Cleaned dataset export file not found on server."
        )

    return FileResponse(
        path=str(export_path),
        media_type="text/csv",
        filename=filename
    )


# --------------------------------------------------
# AI DATA ANALYSIS WITH CONVERSATION MEMORY
# --------------------------------------------------

@app.post("/analyze")
async def analyze_file(
    question: str = Form(...),
    conversation_id: str | None = Form(None),
    session_id: str | None = Form(None),
    x_session_id: str | None = Header(None, alias="X-Session-ID"),
    file: UploadFile | None = File(None)
):

    if not question.strip():
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty."
        )

    try:

        # --------------------------------------------------
        # FIRST REQUEST: Create a new conversation
        # --------------------------------------------------

        if conversation_id is None:

            if file is None:
                raise HTTPException(
                    status_code=400,
                    detail="Upload a CSV file to start a conversation."
                )

            if not file.filename.lower().endswith(".csv"):
                raise HTTPException(
                    status_code=400,
                    detail="Only CSV files are supported."
                )

            # Read uploaded dataset.
            df = pd.read_csv(
                file.file,
                encoding="latin1"
            )

            if df.empty:
                raise HTTPException(
                    status_code=400,
                    detail="Uploaded dataset is empty."
                )

            # Create conversation and store dataset.
            conversation_id = create_conversation(df)

            conversation = get_conversation(conversation_id)

        # --------------------------------------------------
        # FOLLOW-UP REQUEST: Retrieve existing conversation
        # --------------------------------------------------

        else:

            if file is not None:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Do not upload another file "
                        "in an existing conversation."
                    )
                )

            try:
                conversation = get_conversation(
                    conversation_id
                )

            except ValueError:
                raise HTTPException(
                    status_code=404,
                    detail="Conversation not found."
                )

        # --------------------------------------------------
        # RETRIEVE DATASET AND PREVIOUS CONVERSATION HISTORY
        # --------------------------------------------------

        df = conversation["df"]

        conversation_history = conversation["messages"]

        # --------------------------------------------------
        # RUN CONTEXT-AWARE AI ANALYSIS
        # --------------------------------------------------

        target_token = x_session_id or session_id
        valid_session_id = None
        if target_token:
            try:
                valid_session_id = verify_session_token(target_token)
            except ValueError:
                # If session token is unissued or expired, it cannot access any BYOK credentials.
                # Safely fall back to default session configuration (local Ollama engine)
                # so analysis and visualizations succeed without error.
                valid_session_id = None

        session_config = get_session_config(valid_session_id)

        result = analyze_dataset(
            df,
            question,
            conversation_history=conversation_history,
            session_config=session_config
        )

        # --------------------------------------------------
        # SAVE UPDATED CONVERSATION HISTORY
        # --------------------------------------------------

        update_conversation(
            conversation_id,
            result["conversation_history"]
        )

        # Include conversation ID in API response.
        result["conversation_id"] = conversation_id

        # Convert response into JSON-safe values.
        safe_result = make_json_safe(result)

        return JSONResponse(content=safe_result)

    except HTTPException:
        raise

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail=str(e)
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        if file is not None:
            await file.close()
