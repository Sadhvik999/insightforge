
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse

import pandas as pd
import numpy as np
import math

from app.inspector import inspect_dataset
from app.cleaner import clean_dataset
from app.agent import analyze_dataset

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
async def clean_file(file: UploadFile = File(...)):

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

        cleaned_df, cleaning_report = clean_dataset(df)

        response = {
            "original_rows": len(df),
            "cleaned_rows": len(cleaned_df),
            "columns": cleaned_df.columns.tolist(),
            "cleaning_report": cleaning_report
        }

        safe_response = make_json_safe(response)

        return JSONResponse(content=safe_response)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        await file.close()


# --------------------------------------------------
# AI DATA ANALYSIS WITH CONVERSATION MEMORY
# --------------------------------------------------

@app.post("/analyze")
async def analyze_file(
    question: str = Form(...),
    conversation_id: str | None = Form(None),
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

        result = analyze_dataset(
            df,
            question,
            conversation_history=conversation_history
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
