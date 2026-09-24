"""Intelligent resume selector matching leads to the most relevant resume PDF."""
import os
import json
from typing import Dict, Any, Tuple, Optional
from src.models import Lead, ResumeProfile
from src.llm import call_llm
from src.logger import get_logger

logger = get_logger()


def score_resume_relevance(lead_text: str, profile: ResumeProfile) -> float:
    """Calculate rule-based heuristic relevance score between lead context and resume profile."""
    lead_lower = lead_text.lower()
    score = 0.0

    # Match keywords
    for kw in profile.relevant_keywords:
        if kw in lead_lower:
            score += 2.0

    # Match key skills
    for skill in profile.key_skills:
        if skill.lower() in lead_lower:
            score += 1.5

    # Match target profiles
    for target in profile.target_profile.lower().split(","):
        if target.strip() and target.strip() in lead_lower:
            score += 3.0

    return score


def select_best_resume(
    lead: Lead,
    resume_profiles: Dict[str, ResumeProfile],
    model: str = "google/gemini-3-flash-preview",
    api_key: Optional[str] = None,
    api_base: Optional[str] = None
) -> Tuple[str, str, float]:
    """
    Determine the most appropriate resume for the contact.
    Returns: (selected_resume_filename, reason, confidence)
    """
    if not resume_profiles:
        # Default fallback if no profiles are configured
        return "resume_1.pdf", "Default resume selected (no profiles found).", 0.70

    # Compile lead context
    lead_context = (
        f"Company: {lead.company}\n"
        f"Role: {lead.role}\n"
        f"Notes: {lead.notes}\n"
        f"Company Website Context: {lead.company_url}\n"
        f"Job Posting Context: {lead.job_url}\n"
    )

    # Calculate heuristic scores first
    scores = {}
    for filename, prof in resume_profiles.items():
        scores[filename] = score_resume_relevance(lead_context, prof)

    best_heuristic_file = max(scores, key=scores.get) if scores else "resume_1.pdf"

    # Prepare prompt for LLM selection
    resumes_summary = {}
    for filename, prof in resume_profiles.items():
        resumes_summary[filename] = {
            "name": prof.resume_name,
            "target": prof.target_profile,
            "skills": prof.key_skills[:6],
            "experiences": prof.strongest_experiences[:2],
            "projects": prof.strongest_projects[:2]
        }

    prompt = (
        f"You are selecting the single most relevant resume for a candidate outreach email.\n\n"
        f"Candidate: Kritik Jain (IIIT Bhopal)\n\n"
        f"Available Resumes:\n{json.dumps(resumes_summary, indent=2)}\n\n"
        f"Recipient Context:\n"
        f"- Name: {lead.name}\n"
        f"- Company: {lead.company}\n"
        f"- Role: {lead.role}\n"
        f"- Notes: {lead.notes}\n\n"
        f"Decision Rules:\n"
        f"1. AI/ML/LLM/GenAI company or role -> Choose AI/ML focused resume (e.g. resume_1.pdf).\n"
        f"2. Backend/Infra/Go/Systems/Distributed/Cloud company or role -> Choose Backend resume (e.g. resume_2.pdf).\n"
        f"3. Full-Stack/Web/Product/SaaS/General SDE -> Choose Full-Stack resume (e.g. resume_3.pdf).\n"
        f"4. If role is unclear, pick the closest match and assign a conservative confidence score.\n\n"
        f"Return strictly a JSON object with this format:\n"
        f"{{\n"
        f'  "resume": "resume_1.pdf",\n'
        f'  "reason": "Brief 1-sentence technical reason for selecting this resume.",\n'
        f'  "confidence": 0.95\n'
        f"}}"
    )

    fallback_data = {
        "name": lead.name,
        "company": lead.company,
        "role": lead.role,
        "notes": lead.notes,
        "selected_resume": best_heuristic_file
    }

    try:
        res = call_llm(
            prompt=prompt,
            system_prompt="You are a precise technical recruiter matching candidate resumes to job leads. Output valid JSON only.",
            model=model,
            api_key=api_key,
            api_base=api_base,
            temperature=0.1,
            fallback_mock_data=fallback_data
        )

        selected_file = res.get("resume") or res.get("selected_resume") or best_heuristic_file
        # Normalize filename
        if not selected_file.endswith(".pdf"):
            selected_file += ".pdf"
        if selected_file not in resume_profiles:
            selected_file = best_heuristic_file

        reason = res.get("reason") or res.get("resume_reason") or f"Matched based on {lead.role or lead.company} technical profile."
        confidence = float(res.get("confidence", 0.85))

        return selected_file, reason, confidence

    except Exception as e:
        logger.warning(f"LLM resume selection failed: {e}. Using heuristic selection.")
        return best_heuristic_file, f"Heuristic match based on {lead.role or lead.company} keywords.", 0.80
