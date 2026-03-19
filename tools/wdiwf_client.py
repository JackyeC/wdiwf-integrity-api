"""
WDIWF Company Intelligence Client
wdiwf.jackyeclayton.com

GET /api/v1/dossier?company_id={id}
GET /api/v1/dossier?domain={domain}
GET /api/v1/dossier?name={company_name}

Returns 404 if company not in database — client falls back to zero-scored stub.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from models.company import (
    CompanyDossier, CompanyIntegrityResult,
    WorkforceStabilitySignal, GlassdoorTrajectory,
    evaluate_company_integrity,
)

logger = logging.getLogger(__name__)

WDIWF_BASE_URL = "https://wdiwf.jackyeclayton.com"
CACHE_TTL_HOURS = 24


class WDIWFClient:
    def __init__(self, api_key: str = "", base_url: str = WDIWF_BASE_URL, timeout: float = 15.0):
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": "wdiwf-recruiting-agent/1.0",
            },
            timeout=timeout,
        )
        self._cache: dict[str, tuple[CompanyIntegrityResult, datetime]] = {}

    async def get_company_integrity(
        self,
        *,
        company_id:   Optional[str] = None,
        company_name: Optional[str] = None,
        domain:       Optional[str] = None,
    ) -> CompanyIntegrityResult:
        cache_key = company_id or domain or (company_name or "").lower().replace(" ", "-")

        if cache_key in self._cache:
            result, expires = self._cache[cache_key]
            if datetime.now(timezone.utc) < expires:
                return result

        dossier = await self._fetch_dossier(company_id=company_id, company_name=company_name, domain=domain)
        result  = evaluate_company_integrity(dossier)
        self._cache[cache_key] = (result, datetime.now(timezone.utc) + timedelta(hours=CACHE_TTL_HOURS))

        if result.company_integrity_flag:
            logger.warning("[WDIWF] HIGH RISK: %s (RG=%.0f IS=%.0f)",
                           result.company_name, result.reality_gap_score, result.insider_score)
        return result

    async def _fetch_dossier(self, company_id=None, company_name=None, domain=None) -> CompanyDossier:
        params = {}
        if company_id:   params["company_id"] = company_id
        elif domain:     params["domain"]      = domain
        elif company_name: params["name"]      = company_name
        else:
            raise ValueError("Provide at least one of: company_id, company_name, domain")

        try:
            resp = await self._client.get("/api/v1/dossier", params=params)
            if resp.status_code == 404:
                return self._no_data_stub(company_id or "unknown", company_name or domain or "Unknown Company")
            resp.raise_for_status()
            return self._parse_response(resp.json())
        except (httpx.TimeoutException, httpx.HTTPStatusError, Exception) as e:
            logger.warning("[WDIWF] Fetch failed (%s) — using stub", e)
            return self._no_data_stub(company_id or "error", company_name or domain or "Unknown Company",
                                      note=f"WDIWF unavailable: {e}")

    @staticmethod
    def _parse_response(data: dict) -> CompanyDossier:
        scores   = data.get("scores", {})
        signals  = data.get("signals", {})
        evidence = data.get("evidence", {})
        meta     = data.get("meta", {})
        return CompanyDossier(
            company_id            = data.get("company_id", ""),
            company_name          = data.get("company_name", ""),
            domain                = data.get("domain"),
            industry              = data.get("industry"),
            employee_count_range  = data.get("employee_count_range"),
            reality_gap_score     = float(scores.get("reality_gap", 0)),
            civic_footprint_score = float(scores.get("civic_footprint", 0)),
            insider_score         = float(scores.get("insider", 0)),
            workforce_stability   = WorkforceStabilitySignal(signals.get("workforce_stability", "unknown")),
            glassdoor_trajectory  = GlassdoorTrajectory(signals.get("glassdoor_trajectory", "unknown")),
            glassdoor_rating      = signals.get("glassdoor_rating"),
            reality_gap_evidence  = evidence.get("reality_gap", []),
            insider_score_evidence= evidence.get("insider_score", []),
            civic_concerns        = evidence.get("civic", []),
            dossier_as_of         = datetime.fromisoformat(meta["dossier_as_of"]) if meta.get("dossier_as_of") else None,
            data_confidence       = meta.get("data_confidence", "medium"),
            wdiwf_profile_url     = meta.get("profile_url"),
        )

    @staticmethod
    def _no_data_stub(company_id: str, company_name: str, note: str = "Company not yet in WDIWF database") -> CompanyDossier:
        return CompanyDossier(
            company_id           = company_id,
            company_name         = company_name,
            reality_gap_score    = 0.0,
            civic_footprint_score= 0.0,
            insider_score        = 0.0,
            workforce_stability  = WorkforceStabilitySignal.UNKNOWN,
            glassdoor_trajectory = GlassdoorTrajectory.UNKNOWN,
            data_confidence      = "low",
            reality_gap_evidence = [note],
        )

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self): return self
    async def __aexit__(self, *args): await self.close()
