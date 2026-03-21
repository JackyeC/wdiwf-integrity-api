"""
WDIWF Company Intelligence Client — Claude-powered

Uses Anthropic Claude to generate company integrity scores
based on publicly available knowledge about the company.

Scores returned:
  Reality Gap (0-100)       Culture stated vs lived
  Civic Footprint (0-100)   ESG/legal/ethical concerns. Higher = worse.
  Insider Score (0-100)     Insider dysfunction/nepotism signal
  Workforce Stability       stable | declining | volatile | restructuring
  Glassdoor Trajectory      improving | stable | declining | deteriorating
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import anthropic

from models.company import (
    CompanyIntegrityResult,
    WorkforceStabilitySignal,
    GlassdoorTrajectory,
    evaluate_company_integrity,
)

logger = logging.getLogger(__name__)

INTEL_PROMPT = """You are the WDIWF Company Intelligence Engine. Assess this company for candidates considering working there.

Company: {company_name}

Return ONLY valid JSON with these exact fields:
{{
  "reality_gap_score": <int 0-100, gap between stated and lived culture, higher=worse>,
  "civic_footprint_score": <int 0-100, ESG/legal/ethical concerns, higher=worse>,
  "insider_score": <int 0-100, insider dysfunction/nepotism signal, higher=worse>,
  "workforce_stability": <"stable"|"declining"|"volatile"|"restructuring"|"unknown">,
  "glassdoor_trajectory": <"improving"|"stable"|"declining"|"deteriorating"|"unknown">,
  "glassdoor_rating": <float 1.0-5.0 or null if unknown>,
  "reality_gap_evidence": [<2-4 short factual observations about culture vs reality>],
  "insider_score_evidence": [<2-3 observations about leadership network and hiring patterns>],
  "civic_concerns": [<0-3 specific ESG or legal concerns — empty list if none>],
  "data_confidence": <"high"|"medium"|"low">,
  "summary_for_recruiter": "<1-2 sentence plain summary of overall integrity signal>",
  "disclosure_for_candidate": "<1 honest sentence for a candidate considering this company>"
}}

Be honest and specific. Base scores on publicly known information.
If a company genuinely has strong values and culture (e.g. Patagonia, REI, Costco, Ben and Jerrys),
reflect that with LOW reality_gap_score and LOW civic_footprint_score.
Do not inflate risks for well-regarded, mission-aligned employers.
Return only the JSON object — no markdown, no explanation, no code fences."""


class WDIWFClient:
    def __init__(self, api_key: str = "", base_url: str = "", timeout: float = 30.0):
        self._anthropic_key = os.environ.get("ANTHROPIC_API_KEY", api_key)

    async def get_company_integrity(self, company_name: str) -> CompanyIntegrityResult:
        """Use Claude to generate real company integrity scores."""
        if not self._anthropic_key:
            logger.warning("ANTHROPIC_API_KEY not set — returning stub")
            return self._zero_stub(company_name, "no_api_key")

        try:
            client = anthropic.Anthropic(api_key=self._anthropic_key)
            prompt = INTEL_PROMPT.format(company_name=company_name)

            message = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )

            raw = message.content[0].text.strip()

            # Strip markdown code fences if Claude wrapped the JSON
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1]).strip()

            data = json.loads(raw)

            workforce = WorkforceStabilitySignal(
                data.get("workforce_stability", "unknown")
            )
            glassdoor = GlassdoorTrajectory(
                data.get("glassdoor_trajectory", "unknown")
            )

            result = CompanyIntegrityResult(
                company_id=company_name.lower().replace(" ", "-"),
                company_name=company_name,
                reality_gap_score=int(data.get("reality_gap_score", 0)),
                civic_footprint_score=int(data.get("civic_footprint_score", 0)),
                insider_score=int(data.get("insider_score", 0)),
                workforce_stability=workforce,
                glassdoor_trajectory=glassdoor,
                glassdoor_rating=data.get("glassdoor_rating"),
                reality_gap_evidence=data.get("reality_gap_evidence", []),
                insider_score_evidence=data.get("insider_score_evidence", []),
                civic_concerns=data.get("civic_concerns", []),
                data_confidence=data.get("data_confidence", "medium"),
                summary_for_recruiter=data.get("summary_for_recruiter", ""),
                disclosure_for_candidate=data.get("disclosure_for_candidate", ""),
                checked_at=datetime.now(timezone.utc),
            )

            result.risk_level = evaluate_company_integrity(result)
            logger.info(f"Claude intel success for {company_name}: risk={result.risk_level}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Claude returned invalid JSON for {company_name}: {e}")
            return self._zero_stub(company_name, "parse_error")
        except Exception as e:
            logger.error(f"Claude intel failed for {company_name}: {e}")
            return self._zero_stub(company_name, "api_error")

    def _zero_stub(self, company_name: str, reason: str) -> CompanyIntegrityResult:
        return CompanyIntegrityResult(
            company_id=reason,
            company_name=company_name,
            risk_level="LOW",
            reality_gap_flagged=False,
            insider_score_flagged=False,
            civic_flagged=False,
            company_integrity_flag=None,
            summary_for_recruiter=f"Intelligence unavailable for {company_name}.",
            disclosure_for_candidate="No data available. Research independently before applying.",
            reality_gap_score=0,
            civic_footprint_score=0,
            insider_score=0,
            workforce_stability=WorkforceStabilitySignal.UNKNOWN,
            glassdoor_trajectory=GlassdoorTrajectory.UNKNOWN,
            glassdoor_rating=None,
            reality_gap_evidence=[],
            insider_score_evidence=[],
            civic_concerns=[],
            checked_at=datetime.now(timezone.utc),
            data_confidence="low",
        )

    async def close(self):
        pass
