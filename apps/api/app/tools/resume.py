"""Resume tools: review and extract profile from resumes."""

from __future__ import annotations

import json
import logging
import re

from langchain_core.tools import tool

from app.db import get_conn
from app.resume_store import get_resume, list_resumes

from .shared import _uid

logger = logging.getLogger(__name__)


@tool
async def review_resume(resume_id: str = "") -> str:
    """Retrieve and return the user's uploaded resume text from storage.

    Use this tool whenever you need to read or reference the user's resume.
    If no resume_id is provided, returns the most recently uploaded resume.

    Args:
        resume_id: The resume ID to retrieve. Leave empty to get the latest resume.

    Returns:
        The full resume text, or an error message if not found.
    """
    try:
        if not resume_id:
            resumes = await list_resumes(_uid())
            if not resumes:
                return "No resumes uploaded yet. Ask the user to upload their resume using the panel on the right side."
            resume_id = resumes[-1]

        text = await get_resume(resume_id, _uid())
        if not text:
            available = await list_resumes(_uid())
            return f"Resume '{resume_id}' not found. Available resumes: {available}"

        return f"[Resume ID: {resume_id}]\n\n{text}"
    except Exception as e:
        logger.error("review_resume error: %s", e)
        return f"Error reading resume: {e}"


@tool
async def extract_resume_profile(resume_id: str = "") -> str:
    """Parse the user's resume and extract a structured profile with skills,
    job titles, years of experience, education, and technologies.

    Use this tool when you need structured data about the user's background
    rather than the raw resume text. Returns JSON that you can reason over
    to build strategies, match jobs, or prepare interview materials.

    Args:
        resume_id: The resume ID to parse. Leave empty for the latest resume.

    Returns:
        JSON object with extracted profile fields, or error message.
    """
    try:
        if not resume_id:
            resumes = await list_resumes(_uid())
            if not resumes:
                return json.dumps({"error": "No resumes uploaded yet."})
            resume_id = resumes[-1]

        text = await get_resume(resume_id, _uid())
        if not text:
            return json.dumps({"error": f"Resume '{resume_id}' not found."})

        text_lower = text.lower()
        lines = text.split("\n")

        # Extract job titles found in resume
        title_keywords = [
            "software engineer", "software developer", "data scientist",
            "data engineer", "product manager", "frontend developer",
            "backend developer", "full stack", "fullstack", "devops", "sre",
            "machine learning engineer", "cloud engineer", "solutions architect",
            "technical lead", "tech lead", "engineering manager", "qa engineer",
            "mobile developer", "ios developer", "android developer",
            "security engineer", "platform engineer", "data analyst",
            "site reliability engineer", "staff engineer", "principal engineer",
            "senior software engineer", "senior developer", "web developer",
            "systems engineer", "infrastructure engineer",
        ]
        found_titles = [kw for kw in title_keywords if kw in text_lower]

        # Extract technologies/skills
        tech_keywords = [
            "python", "javascript", "typescript", "java", "c++", "c#", "go",
            "rust", "ruby", "php", "swift", "kotlin", "scala", "r",
            "react", "angular", "vue", "next.js", "node.js", "express",
            "django", "flask", "fastapi", "spring", "rails",
            "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
            "jenkins", "github actions", "ci/cd", "linux",
            "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
            "graphql", "rest api", "microservices", "kafka",
            "machine learning", "deep learning", "tensorflow", "pytorch",
            "sql", "nosql", "git", "agile", "scrum",
        ]
        found_tech = [kw for kw in tech_keywords if kw in text_lower]

        # Estimate years of experience from date patterns
        year_pattern = re.compile(r"(20\d{2}|19\d{2})")
        years_found = sorted(set(int(y) for y in year_pattern.findall(text)))
        experience_years = 0
        if len(years_found) >= 2:
            experience_years = years_found[-1] - years_found[0]

        # Estimate seniority
        seniority = "mid"
        if experience_years >= 10 or any(k in text_lower for k in ["staff", "principal", "director", "vp"]):
            seniority = "senior+"
        elif experience_years >= 5 or "senior" in text_lower:
            seniority = "senior"
        elif experience_years <= 2 or "junior" in text_lower or "intern" in text_lower:
            seniority = "junior"

        # Extract education signals
        education = []
        edu_keywords = ["bachelor", "master", "phd", "ph.d", "mba", "b.s.", "m.s.", "b.a.", "m.a."]
        for line in lines:
            ll = line.lower()
            if any(ek in ll for ek in edu_keywords):
                education.append(line.strip())

        # Extract company names
        companies = []
        company_pattern = re.compile(r"(?:at|@)\s+(.+?)(?:\s*[|,\-–]|$)", re.IGNORECASE)
        for line in lines:
            m = company_pattern.search(line)
            if m:
                companies.append(m.group(1).strip())

        # Count saved jobs to understand pipeline state
        pipeline = {"total": 0, "by_status": {}}
        try:
            async with get_conn() as conn:
                rows = await conn.fetch("SELECT status, COUNT(*) AS cnt FROM saved_jobs GROUP BY status")
                for r in rows:
                    pipeline["by_status"][r["status"]] = r["cnt"]
                    pipeline["total"] += r["cnt"]
        except Exception:
            pass

        profile = {
            "resume_id": resume_id,
            "titles": found_titles,
            "technologies": found_tech,
            "experience_years": experience_years,
            "seniority": seniority,
            "education": education[:5],
            "companies": companies[:10],
            "pipeline": pipeline,
        }

        return json.dumps(profile, indent=2)
    except Exception as e:
        logger.error("extract_resume_profile error: %s", e)
        return json.dumps({"error": str(e)})
