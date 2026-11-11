
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse

import pandas as pd
import numpy as np
import math

from app.inspector import inspect_dataset
from app.cleaner import clean_dataset
from app.agent import analyze_dataset


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
        df = pd.read_csv(file.file, encoding="latin1")

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
        df = pd.read_csv(file.file, encoding="latin1")

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
# AI DATA ANALYSIS ENDPOINT
# --------------------------------------------------

@app.post("/analyze")
async def analyze_file(
    question: str = Form(...),
    file: UploadFile = File(...)
):

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported"
        )

    if not question.strip():
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty."
        )

    try:
        # 1. Read uploaded CSV
        df = pd.read_csv(
            file.file,
            encoding="latin1"
        )

        if df.empty:
            raise HTTPException(
                status_code=400,
                detail="Uploaded dataset is empty."
            )

        # 2. Run AI agent
        result = analyze_dataset(
            df,
            question
        )

        # 3. Convert results into JSON-safe values
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
        await file.close()
