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
from tools.dossier_generator import DossierGenerator
from models.company import CompanyIntegrityResult
from models.dossier import DossierRequest, ApplicationDossier, CandidateRegistration

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_wdiwf_client: Optional[WDIWFClient] = None
_dossier_generator: Optional[DossierGenerator] = None

# In-memory candidate store (replace with a database when ready)
_candidates: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _wdiwf_client, _dossier_generator
    _wdiwf_client = WDIWFClient(api_key=os.getenv("WDIWF_API_KEY", ""))
    _dossier_generator = DossierGenerator(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    logger.info("WDIWF client ready")
    logger.info("Dossier generator ready")
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


@app.post(
    "/api/generate-dossier",
    response_model=ApplicationDossier,
    summary="Generate a full application dossier for a candidate + job posting",
)
async def generate_dossier(body: DossierRequest) -> ApplicationDossier:
    """
    Takes a candidate profile + job posting, runs the company integrity
    check, then uses Claude to generate a complete dossier:
    why we applied, who is there, how to prepare, questions to ask,
    and a personalized cover letter.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured. Add it in Render environment variables."
        )

    # Run integrity check unless caller already provided it
    integrity_score = body.integrity_score or 75.0
    risk_level = body.risk_level or "LOW"
    integrity_disclosure = body.integrity_disclosure

    if body.integrity_score is None:
        try:
            integrity_result = await _wdiwf_client.get_company_integrity(
                company_name=body.job_posting.company_name,
                domain=body.job_posting.company_domain,
            )
            integrity_score = 100 - integrity_result.reality_gap_score
            risk_level = integrity_result.risk_level.value
            integrity_disclosure = integrity_result.disclosure_for_candidate
        except Exception as e:
            logger.warning(f"Integrity check failed for {body.job_posting.company_name}: {e}")

    dossier = await _dossier_generator.generate(
        candidate=body.candidate,
        job=body.job_posting,
        integrity_score=integrity_score,
        risk_level=risk_level,
        integrity_disclosure=integrity_disclosure,
    )

    return dossier


@app.post(
    "/api/candidates",
    summary="Register a candidate and activate their job search agent",
    status_code=201,
)
async def register_candidate(body: CandidateRegistration):
    """
    Saves a candidate's job search parameters.
    The agent will use these to find matching roles and generate dossiers.
    """
    _candidates[body.email] = body.model_dump()
    logger.info(f"Candidate registered: {body.email}")
    return {
        "status": "registered",
        "email": body.email,
        "message": "Your job search agent is active. Your first dossier will arrive within 24 hours.",
        "candidate_count": len(_candidates),
    }


@app.get(
    "/api/applications/{user_email}",
    summary="Get application dossiers for a candidate",
)
async def get_applications(user_email: str):
    """
    Returns the list of application dossiers for a candidate.
    Currently returns a sample dossier — replace with a real DB query when ready.
    """
    from datetime import datetime
    sample = {
        "applications": [
            {
                "company_name": "Meridian Health Tech",
                "job_title": "Senior Product Manager, Patient Experience",
                "applied_at": datetime.utcnow().isoformat(),
                "status": "Applied",
                "integrity_score": 84,
                "risk_level": "LOW",
                "why_we_applied": "Meridian's mission in patient-centered health technology aligns directly with your values around mission-driven work and growth. The role matches your target title and falls within your salary range.",
                "values_matched": ["Mission-driven work", "Growth opportunities", "Work-life balance"],
                "who_is_there": "Meridian Health Tech is a Series B health equity company focused on improving patient outcomes through technology. They have a 12-person product org led by Jordan Kim, VP of Product, who has been at the company for 8 years — a strong stability signal. Recent news: $40M Series B closed January 2026, 40% YoY growth.",
                "glassdoor_summary": "Glassdoor rating 4.3/5, trending up over the past 12 months. Employees consistently mention strong mission clarity and leadership transparency.",
                "how_to_prepare": [
                    "Lead with patient-first framing — every answer should connect back to patient outcomes",
                    "Prepare a product case study from your past work, especially one involving cross-functional collaboration",
                    "Research their recent Series B announcement and be ready to speak to how you'd contribute in a growth phase",
                    "Bring metrics — this team is data-driven and will want to see how you've measured impact before"
                ],
                "questions_to_ask": [
                    "How does the product team work directly with clinical staff day-to-day?",
                    "What does success look like in the first 90 days in this role?",
                    "How has the culture evolved since your Series B — what's changed and what's stayed the same?",
                    "How do you measure patient impact from product decisions, and how does that feed back into roadmap prioritization?"
                ],
                "cover_letter": "Meridian's work at the intersection of technology and patient equity is exactly the kind of mission I've been looking for in my next role. The opportunity to build product experiences that directly improve how patients navigate their care — not as a side effect of the work, but as the whole point — is rare, and it's where I want to invest the next chapter of my career.\n\nI bring a track record of leading cross-functional product teams through complex, high-stakes builds. I've worked closely with clinical, engineering, and design stakeholders, and I know how to translate patient and provider needs into product decisions that stick. My approach is deeply metrics-driven, and I'm comfortable operating in the ambiguity of a growth-stage company where the roadmap is still being shaped.\n\nI'd love the chance to learn more about the team and share how I think about the problem space. I'm confident there's strong alignment here, and I'm excited about what we could build together."
            }
        ],
        "total": 1,
        "agent_status": "active",
        "note": "Sample dossier shown. Live applications will appear here as your agent finds matches."
    }
    return sample


@app.get("/health")
async def health():
    return {"status": "ok"}
