"""
Company Intelligence Models — WDIWF Layer

Signal definitions
──────────────────
Reality Gap (0–100)   Distance between stated and lived culture. >70 = HIGH_RISK.
Civic Footprint (0–100)  ESG/legal/community impact. Higher = worse.
Insider Score (0–100)  Insider dysfunction signal. >70 = HIGH_RISK.
Workforce Stability   stable | declining | volatile | restructuring
Glassdoor Trajectory  improving | stable | declining | deteriorating
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class WorkforceStabilitySignal(str, Enum):
    STABLE        = "stable"
    DECLINING     = "declining"
    VOLATILE      = "volatile"
    RESTRUCTURING = "restructuring"
    UNKNOWN       = "unknown"


class GlassdoorTrajectory(str, Enum):
    IMPROVING    = "improving"
    STABLE       = "stable"
    DECLINING    = "declining"
    DETERIORATING = "deteriorating"
    UNKNOWN      = "unknown"


class CompanyRiskLevel(str, Enum):
    LOW      = "LOW"
    MODERATE = "MODERATE"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


HIGH_RISK_FLAG_MESSAGE = (
    "HIGH_RISK — candidate should be informed of these signals before proceeding"
)


class CompanyDossier(BaseModel):
    company_id:            str
    company_name:          str
    domain:                Optional[str]  = None
    industry:              Optional[str]  = None
    employee_count_range:  Optional[str]  = None

    reality_gap_score:     float = Field(0.0, ge=0.0, le=100.0)
    civic_footprint_score: float = Field(0.0, ge=0.0, le=100.0)
    insider_score:         float = Field(0.0, ge=0.0, le=100.0)

    workforce_stability:   WorkforceStabilitySignal = WorkforceStabilitySignal.UNKNOWN
    glassdoor_trajectory:  GlassdoorTrajectory      = GlassdoorTrajectory.UNKNOWN
    glassdoor_rating:      Optional[float]          = Field(None, ge=1.0, le=5.0)

    reality_gap_evidence:   list[str] = Field(default_factory=list)
    insider_score_evidence: list[str] = Field(default_factory=list)
    civic_concerns:         list[str] = Field(default_factory=list)

    dossier_as_of:    Optional[datetime] = None
    data_confidence:  str               = "medium"
    wdiwf_profile_url: Optional[str]   = None


class CompanyIntegrityResult(BaseModel):
    company_id:   str
    company_name: str
    risk_level:   CompanyRiskLevel = CompanyRiskLevel.LOW

    reality_gap_flagged:   bool = False
    insider_score_flagged: bool = False
    civic_flagged:         bool = False

    company_integrity_flag: Optional[str] = None

    summary_for_recruiter:    str = ""
    disclosure_for_candidate: str = ""

    reality_gap_score:     float = 0.0
    civic_footprint_score: float = 0.0
    insider_score:         float = 0.0
    workforce_stability:   str   = WorkforceStabilitySignal.UNKNOWN.value
    glassdoor_trajectory:  str   = GlassdoorTrajectory.UNKNOWN.value
    glassdoor_rating:      Optional[float] = None

    reality_gap_evidence:   list[str] = Field(default_factory=list)
    insider_score_evidence: list[str] = Field(default_factory=list)
    civic_concerns:         list[str] = Field(default_factory=list)

    checked_at:       datetime        = Field(default_factory=datetime.utcnow)
    data_confidence:  str             = "medium"
    wdiwf_profile_url: Optional[str] = None


def evaluate_company_integrity(dossier: CompanyDossier) -> CompanyIntegrityResult:
    """
    Pure function — deterministically evaluates a CompanyDossier.
    Reality Gap > 70 OR Insider Score > 70 → HIGH_RISK flag.
    Both > 70 → CRITICAL.
    """
    reality_flagged = dossier.reality_gap_score    > 70
    insider_flagged = dossier.insider_score         > 70
    civic_flagged   = dossier.civic_footprint_score > 60

    if reality_flagged and insider_flagged:
        risk_level = CompanyRiskLevel.CRITICAL
    elif reality_flagged or insider_flagged:
        risk_level = CompanyRiskLevel.HIGH
    elif civic_flagged:
        risk_level = CompanyRiskLevel.MODERATE
    else:
        risk_level = CompanyRiskLevel.LOW

    is_high_risk = risk_level in (CompanyRiskLevel.HIGH, CompanyRiskLevel.CRITICAL)
    flag = HIGH_RISK_FLAG_MESSAGE if is_high_risk else None

    # Recruiter summary
    lines = [
        f"WDIWF Company Check: {dossier.company_name}",
        f"  Risk Level:           {risk_level.value}",
        f"  Reality Gap:          {dossier.reality_gap_score:.0f}/100" + (" ⚠ FLAGGED" if reality_flagged else ""),
        f"  Insider Score:        {dossier.insider_score:.0f}/100" + (" ⚠ FLAGGED" if insider_flagged else ""),
        f"  Civic Footprint:      {dossier.civic_footprint_score:.0f}/100" + (" ⚠ NOTE" if civic_flagged else ""),
        f"  Workforce Stability:  {dossier.workforce_stability.value}",
        f"  Glassdoor Trajectory: {dossier.glassdoor_trajectory.value}" +
            (f" ({dossier.glassdoor_rating:.1f}★)" if dossier.glassdoor_rating else ""),
    ]
    if reality_flagged:
        for e in dossier.reality_gap_evidence:
            lines.append(f"    • {e}")
    if insider_flagged:
        for e in dossier.insider_score_evidence:
            lines.append(f"    • {e}")

    # Candidate disclosure
    if is_high_risk:
        disc = [
            f"Before you proceed with this application, our independent company intelligence "
            f"signals some concerns about {dossier.company_name} that you should be aware of:",
        ]
        if reality_flagged:
            disc.append(
                f"  • Culture gap signal ({dossier.reality_gap_score:.0f}/100): "
                "There is a notable difference between how this company publicly describes "
                "its culture and what employees report internally."
            )
            for e in dossier.reality_gap_evidence:
                disc.append(f"    – {e}")
        if insider_flagged:
            disc.append(
                f"  • Insider experience signal ({dossier.insider_score:.0f}/100): "
                "Aggregated insider accounts flag structural or management concerns."
            )
            for e in dossier.insider_score_evidence:
                disc.append(f"    – {e}")
        disc.append(
            "We encourage you to ask direct questions about these areas during your process. "
            "This information is provided to help you make a fully informed decision."
        )
        disclosure = "\n".join(disc)
    else:
        disclosure = (
            f"No significant concerns were flagged for {dossier.company_name} "
            "in our company intelligence check."
        )

    return CompanyIntegrityResult(
        company_id             = dossier.company_id,
        company_name           = dossier.company_name,
        risk_level             = risk_level,
        reality_gap_flagged    = reality_flagged,
        insider_score_flagged  = insider_flagged,
        civic_flagged          = civic_flagged,
        company_integrity_flag = flag,
        summary_for_recruiter  = "\n".join(lines),
        disclosure_for_candidate = disclosure,
        reality_gap_score      = dossier.reality_gap_score,
        civic_footprint_score  = dossier.civic_footprint_score,
        insider_score          = dossier.insider_score,
        workforce_stability    = dossier.workforce_stability.value,
        glassdoor_trajectory   = dossier.glassdoor_trajectory.value,
        glassdoor_rating       = dossier.glassdoor_rating,
        reality_gap_evidence   = dossier.reality_gap_evidence,
        insider_score_evidence = dossier.insider_score_evidence,
        civic_concerns         = dossier.civic_concerns,
        data_confidence        = dossier.data_confidence,
        wdiwf_profile_url      = dossier.wdiwf_profile_url,
    )
