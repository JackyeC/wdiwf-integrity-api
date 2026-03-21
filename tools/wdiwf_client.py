"""
WDIWF Company Intelligence Client — Claude-powered
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import anthropic

from models.company import (
    CompanyIntegrityResult,
    WorkforceStabilitySignal,
    GlassdoorTrajectory,
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
  "civic_concerns": [<0-3 specific ESG or legal concerns, empty list if none>],
  "data_confidence": <"high"|"medium"|"low">,
  "summary_for_recruiter": "<1-2 sentence plain summary of overall integrity signal>",
  "disclosure_for_candidate": "<1 honest sentence for a candidate considering this company>"
}}

Be honest. If a company genuinely has strong culture (Patagonia, REI, Costco), give LOW scores.
Return only the JSON object — no markdown, no explanation."""


def _compute_risk(reality_gap: int, insider: int, civic: int) -> str:
    if reality_gap > 70 or insider > 70:
        return "HIGH_RISK"
    elif reality_gap > 40 or insider > 40 or civic > 40:
        return "MEDIUM_RISK"
    return "LOW"


class WDIWFClient:
    def __init__(self, api_key: str = "", base_url: str = "", timeout: float = 30.0):
        self._anthropic_key = os.environ.get("ANTHROPIC_API_KEY", api_key)

    async def get_company_integrity(
        self,
        company_name: str = None,
        company_id: str = None,
        domain: str = None,
    ) -> CompanyIntegrityResult:
        name = company_name or company_id or domain or "Unknown Company"

        if not self._anthropic_key:
            logger.warning("ANTHROPIC_API_KEY not set")
            return self._zero_stub(name, "no_api_key")

        try:
            client = anthropic.Anthropic(api_key=self._anthropic_key)
            prompt = INTEL_PROMPT.format(company_name=name)

            message = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )

            raw = message.content[0].text.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1]).strip()

            data = json.loads(raw)

            reality_gap = int(data.get("reality_gap_score", 0))
            civic = int(data.get("civic_footprint_score", 0))
            insider = int(data.get("insider_score", 0))
            risk_level = _compute_risk(reality_gap, insider, civic)

            workforce_str = data.get("workforce_stability", "unknown")
            glassdoor_str = data.get("glassdoor_trajectory", "unknown")

            try:
                workforce = WorkforceStabilitySignal(workforce_str)
            except Exception:
                workforce = WorkforceStabilitySignal.UNKNOWN

            try:
                glassdoor = GlassdoorTrajectory(glassdoor_str)
            except Exception:
                glassdoor = GlassdoorTrajectory.UNKNOWN

            result = CompanyIntegrityResult(
                company_id=name.lower().replace(" ", "-"),
                company_name=name,
                risk_level=risk_level,
                reality_gap_score=reality_gap,
                civic_footprint_score=civic,
                insider_score=insider,
                reality_gap_flagged=reality_gap > 70,
                insider_score_flagged=insider > 70,
                civic_flagged=civic > 70,
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

            logger.info(f"Claude intel success for {name}: risk={risk_level}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Claude JSON parse error for {name}: {e}")
            return self._zero_stub(name, "parse_error")
        except Exception as e:
            logger.error(f"Claude intel failed for {name}: {e}")
            return self._zero_stub(name, "api_error")

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
