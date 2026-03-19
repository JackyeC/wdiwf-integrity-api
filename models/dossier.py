"""
Dossier Models — WDIWF

Input:  DossierRequest  (job posting + candidate profile)
Output: ApplicationDossier (full research package for the candidate)
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CandidateProfile(BaseModel):
    email:               str
    target_roles:        list[str]          = Field(default_factory=list)
    industries:          list[str]          = Field(default_factory=list)
    location_preference: str               = "remote"
    salary_min:          int               = 0
    salary_max:          int               = 300000
    values:              list[str]          = Field(default_factory=list)
    integrity_threshold: int               = 60
    narrative_gap_filter: bool             = True
    mission_alignment:   bool              = False
    work_orientation:    float             = 0.5   # 0=compensation, 1=purpose
    resume_text:         Optional[str]     = None  # extracted text from resume
    impact_competencies: list[str]         = Field(default_factory=list)


class JobPosting(BaseModel):
    job_title:       str
    company_name:    str
    company_domain:  Optional[str] = None
    job_description: str
    location:        Optional[str] = None
    salary_range:    Optional[str] = None
    posted_url:      Optional[str] = None


class DossierRequest(BaseModel):
    candidate:   CandidateProfile
    job_posting: JobPosting
    # Optional: pre-computed integrity result (avoids double API call)
    integrity_score:      Optional[float] = None
    risk_level:           Optional[str]   = None
    integrity_disclosure: Optional[str]   = None


class ApplicationDossier(BaseModel):
    # Identity
    candidate_email: str
    company_name:    str
    job_title:       str
    applied_at:      datetime = Field(default_factory=datetime.utcnow)
    status:          str      = "Applied"

    # Why we applied
    why_we_applied:      str = ""
    values_matched:      list[str] = Field(default_factory=list)
    integrity_score:     float     = 0.0
    risk_level:          str       = "LOW"

    # Company intelligence
    who_is_there:        str = ""   # hiring manager, team, recent news
    glassdoor_summary:   str = ""

    # Interview prep
    how_to_prepare:      list[str] = Field(default_factory=list)
    questions_to_ask:    list[str] = Field(default_factory=list)

    # Cover letter
    cover_letter:        str = ""

    # Integrity disclosure (shown to candidate if flagged)
    integrity_disclosure: Optional[str] = None

    generated_at: datetime = Field(default_factory=datetime.utcnow)


class CandidateRegistration(BaseModel):
    email:               str
    target_roles:        list[str]  = Field(default_factory=list)
    industries:          list[str]  = Field(default_factory=list)
    location_preference: str        = "remote"
    salary_min:          int        = 0
    salary_max:          int        = 300000
    values:              list[str]  = Field(default_factory=list)
    integrity_threshold: int        = 60
    narrative_gap_filter: bool      = True
    mission_alignment:   bool       = False
    work_orientation:    float      = 0.5
