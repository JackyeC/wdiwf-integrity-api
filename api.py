"""
WDIWF Company Integrity API

POST /api/company-integrity-check
  Body:    { "company_name": "Amazon", "company_id": "amazon-inc" }
  Returns: CompanyIntegrityResult as JSON

Run locally:
    uvicorn api:app --reload --port 8000

Deploy:
    See render.yaml — connect GitHub repo on render.com
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from tools.wdiwf_client import WDIWFClient
from models.company import CompanyIntegrityResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_wdiwf_client: Optional[WDIWFClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _wdiwf_client
    _wdiwf_client = WDIWFClient(api_key=os.getenv("WDIWF_API_KEY", ""))
    logger.info("WDIWF client ready")
    yield
    await _wdiwf_client.close()


app = FastAPI(
    title       = "WDIWF Company Integrity API",
    description = "Evaluates hiring companies before candidates are scored against them.",
    version     = "1.0.0",
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["*"],
    allow_methods  = ["POST", "GET"],
    allow_headers  = ["*"],
)


class CompanyIntegrityRequest(BaseModel):
    company_name: Optional[str] = None
    company_id:   Optional[str] = None
    domain:       Optional[str] = None


@app.post(
    "/api/company-integrity-check",
    response_model = CompanyIntegrityResult,
)
async def company_integrity_check(body: CompanyIntegrityRequest) -> CompanyIntegrityResult:
    if not any([body.company_id, body.company_name, body.domain]):
        raise HTTPException(status_code=422, detail="Provide at least one of: company_id, company_name, domain")

    return await _wdiwf_client.get_company_integrity(
        company_id   = body.company_id,
        company_name = body.company_name,
        domain       = body.domain,
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
