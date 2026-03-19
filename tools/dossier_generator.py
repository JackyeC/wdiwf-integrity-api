"""
WDIWF Dossier Generator

Uses Claude (Anthropic API) to generate a full application dossier
for a candidate — given a job posting and their profile.

The dossier includes:
  - Why we applied (values + integrity match reasoning)
  - Who is there (company intel, hiring manager, team, news)
  - How to prepare (interview tips tailored to this company)
  - Questions to ask (specific to this role + company signals)
  - Cover letter (personalized to values + mission alignment)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

import anthropic

from models.dossier import ApplicationDossier, CandidateProfile, JobPosting

logger = logging.getLogger(__name__)

DOSSIER_PROMPT = """\
You are the WDIWF Job Search Agent. You help mission-aligned candidates
apply to jobs and prepare to succeed in interviews.

Your job is to generate a complete Application Dossier for the candidate below.
The dossier must be honest, specific, and genuinely useful — not generic.

CANDIDATE PROFILE:
- Target roles: {target_roles}
- Top values: {values}
- Work orientation: {work_orientation_label} ({work_orientation_pct}% toward purpose/impact)
- Salary target: ${salary_min:,} – ${salary_max:,}
- Location preference: {location_preference}
- Mission alignment enabled: {mission_alignment}
- Impact competencies: {impact_competencies}

JOB POSTING:
- Company: {company_name}
- Role: {job_title}
- Location: {location}
- Salary: {salary_range}
- Description:
{job_description}

COMPANY INTEGRITY:
- Reality Check Score: {integrity_score}/100
- Risk Level: {risk_level}
{integrity_disclosure}

Generate a JSON object with exactly these fields:

{{
  "why_we_applied": "2-3 sentence explanation of why this role matches the candidate's values, skills, and parameters. Be specific — mention actual things from the job description and candidate profile. Do not be generic.",

  "values_matched": ["list", "of", "3-5", "specific values", "that align between candidate and company"],

  "who_is_there": "3-4 sentences about the company: what they do, their culture signals, recent news or funding, team structure if known, Glassdoor signals. Be factual and specific. If you don't know something, say so rather than inventing.",

  "glassdoor_summary": "1-2 sentences on what employees say. If no data, say: 'No Glassdoor data available — ask directly about team culture in your interview.'",

  "how_to_prepare": [
    "Specific tip 1 — tied to something in the job description or company type",
    "Specific tip 2",
    "Specific tip 3",
    "Specific tip 4"
  ],

  "questions_to_ask": [
    "Question 1 — specific to this company and role, not generic",
    "Question 2",
    "Question 3",
    "Question 4 — one question that surfaces integrity/culture signals without being confrontational"
  ],

  "cover_letter": "A complete, ready-to-send cover letter. 3 paragraphs. First: why this specific company and mission. Second: what the candidate brings (draw from their values and competencies). Third: forward-looking close. Do not use generic openers like 'I am writing to express my interest.' Make it human and specific."
}}

Return ONLY the JSON object. No explanation, no markdown, no extra text.
"""


class DossierGenerator:
    """Generates application dossiers using Claude."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = "claude-3-5-haiku-20241022"  # fast + cost-effective for dossiers

    def _work_orientation_label(self, score: float) -> str:
        if score < 0.3:
            return "Compensation-focused"
        elif score < 0.5:
            return "Balanced, leaning compensation"
        elif score < 0.7:
            return "Balanced, leaning purpose"
        else:
            return "Purpose/impact-focused"

    async def generate(
        self,
        candidate: CandidateProfile,
        job: JobPosting,
        integrity_score: float = 75.0,
        risk_level: str = "LOW",
        integrity_disclosure: Optional[str] = None,
    ) -> ApplicationDossier:

        orientation_pct = int(candidate.work_orientation * 100)
        orientation_label = self._work_orientation_label(candidate.work_orientation)

        disclosure_text = ""
        if integrity_disclosure:
            disclosure_text = f"Integrity note for candidate:\n{integrity_disclosure}"

        prompt = DOSSIER_PROMPT.format(
            target_roles=", ".join(candidate.target_roles) or "Not specified",
            values=", ".join(candidate.values) or "Not specified",
            work_orientation_label=orientation_label,
            work_orientation_pct=orientation_pct,
            salary_min=candidate.salary_min,
            salary_max=candidate.salary_max,
            location_preference=candidate.location_preference,
            mission_alignment="Yes" if candidate.mission_alignment else "No",
            impact_competencies=", ".join(candidate.impact_competencies) or "Not specified",
            company_name=job.company_name,
            job_title=job.job_title,
            location=job.location or "Not specified",
            salary_range=job.salary_range or "Not specified",
            job_description=job.job_description[:3000],  # cap to avoid token overflow
            integrity_score=integrity_score,
            risk_level=risk_level,
            integrity_disclosure=disclosure_text,
        )

        logger.info(f"Generating dossier for {candidate.email} → {job.company_name} / {job.job_title}")

        message = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()

        # Strip markdown code fences if Claude wraps in ```json
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        data = json.loads(raw)

        return ApplicationDossier(
            candidate_email      = candidate.email,
            company_name         = job.company_name,
            job_title            = job.job_title,
            status               = "Applied",
            why_we_applied       = data.get("why_we_applied", ""),
            values_matched       = data.get("values_matched", []),
            integrity_score      = integrity_score,
            risk_level           = risk_level,
            who_is_there         = data.get("who_is_there", ""),
            glassdoor_summary    = data.get("glassdoor_summary", ""),
            how_to_prepare       = data.get("how_to_prepare", []),
            questions_to_ask     = data.get("questions_to_ask", []),
            cover_letter         = data.get("cover_letter", ""),
            integrity_disclosure = integrity_disclosure,
        )
