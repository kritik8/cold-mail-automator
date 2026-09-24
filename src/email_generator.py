"""Cold email generation engine following Ankur Tyagi's cold outreach principles."""
import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from src.models import Lead, EmailDraft, ResumeProfile, SenderProfile
from src.resume_selector import select_best_resume
from src.quality_checker import evaluate_email_quality
from src.llm import call_llm
from src.logger import get_logger

logger = get_logger()


def build_unified_generation_prompt(
    lead: Lead,
    resume_profiles: Dict[str, ResumeProfile],
    sender: SenderProfile,
    company_context: Dict[str, str]
) -> str:
    """Construct a unified prompt that selects the optimal resume and writes the cold email in one call."""
    first_name = lead.name.split()[0] if lead.name else "there"

    resumes_summary = {}
    for filename, prof in resume_profiles.items():
        resumes_summary[filename] = {
            "name": prof.resume_name,
            "target": prof.target_profile,
            "skills": prof.key_skills[:6],
            "experiences": prof.strongest_experiences[:2],
            "projects": prof.strongest_projects[:2]
        }

    prompt = f"""
You are an expert cold outreach copywriter writing a high-impact, human, 1-on-1 cold email for an engineering internship/new-grad opportunity for Kritik Jain.

CANDIDATE PROFILE:
Name: {sender.name}
Background: Computer Science & Engineering undergraduate at IIIT Bhopal.
Portfolio: {sender.links.get('portfolio')} | GitHub: {sender.links.get('github')} | LinkedIn: {sender.links.get('linkedin')}

AVAILABLE RESUMES:
{json.dumps(resumes_summary, indent=2)}

RECIPIENT & COMPANY DETAILS:
- Contact Name: {lead.name} (Address as 'Hi {first_name},')
- Role: {lead.role if lead.role else 'Engineering / Leadership / HR'}
- Company: {lead.company}
- Notes / Context: {lead.notes if lead.notes else 'None provided'}
- Scraped Company Info: {company_context.get('company_website_info', 'Not available')[:600]}
- Scraped Job Info: {company_context.get('job_posting_info', 'Not available')[:600]}

TASKS:
1. Select the SINGLE most appropriate resume from the available resumes for this company/role (AI/ML track -> AI resume, Backend/Infra track -> Backend resume, Full-stack/Web -> Full-stack resume).
2. Write a cold email strictly following the Ankur Tyagi Cold Outreach Principles:
   - Target length: 60–120 words, 3–5 sentences.
   - Line 1 (Context Hook): Start from what the recipient or company is building. Never say "I hope this email finds you well" or "My name is...".
   - Line 2-3 (Value & Proof Point): Reference ONE or TWO specific relevant technical accomplishments/projects from the selected resume that directly overlap with their stack/challenges.
   - Line 4 (Clear Action/Ask): A low-friction question asking if they are open to considering you for an engineering internship / new-grad role or a brief conversation.
   - Tone: authentic, human, concise. Absolutely NO corporate fluff ("esteemed organization", "passionate individual", "revolutionary").
3. Generate 3 distinct natural subject lines (e.g. 'Backend systems at {lead.company} — quick question', 'Interested in what you are building at {lead.company}'). Pick the best one for the primary subject.
4. Append a clean signature:
Best,
{sender.name}
B.Tech, IIIT Bhopal
{sender.email} | Portfolio: {sender.links.get('portfolio', '')} | GitHub: {sender.links.get('github', '')}

OUTPUT FORMAT:
Return strictly a JSON object with this exact structure:
{{
  "recipient_name": "{lead.name}",
  "company": "{lead.company}",
  "role": "{lead.role}",
  "selected_resume": "resume_1.pdf",
  "resume_reason": "Brief 1-sentence explanation of why this resume was selected",
  "subject": "Primary chosen subject line",
  "alternative_subjects": [
    "Alternative subject 1",
    "Alternative subject 2",
    "Alternative subject 3"
  ],
  "email_body": "Full email text including salutation and signature",
  "personalization_signal": "Specific topic or tech hook referenced",
  "confidence": 0.95
}}
"""
    return prompt.strip()


def generate_email_for_lead(
    lead: Lead,
    resume_profiles: Dict[str, ResumeProfile],
    sender: SenderProfile,
    company_context: Optional[Dict[str, str]] = None,
    model: str = "google/gemini-3-flash-preview",
    api_key: Optional[str] = None,
    api_base: Optional[str] = None
) -> EmailDraft:
    """Generate and validate a single cold email draft for a lead in a unified single LLM call."""
    context = company_context or {}

    # Determine fallback resume heuristically
    fallback_resume = "resume_1.pdf"
    if resume_profiles:
        lead_txt = f"{lead.company} {lead.role} {lead.notes}".lower()
        if any(k in lead_txt for k in ["ai", "llm", "rag", "agent", "machine learning"]):
            for r_file, prof in resume_profiles.items():
                if "ai" in prof.resume_name.lower():
                    fallback_resume = r_file
                    break
        elif any(k in lead_txt for k in ["backend", "go", "golang", "distributed", "infra", "microservices"]):
            for r_file, prof in resume_profiles.items():
                if "backend" in prof.resume_name.lower():
                    fallback_resume = r_file
                    break

    prompt = build_unified_generation_prompt(
        lead=lead,
        resume_profiles=resume_profiles,
        sender=sender,
        company_context=context
    )

    fallback_data = {
        "name": lead.name,
        "company": lead.company,
        "role": lead.role,
        "notes": lead.notes,
        "selected_resume": fallback_resume,
    }

    try:
        response = call_llm(
            prompt=prompt,
            system_prompt="You are a high-conviction cold outreach copywriter. Output strictly valid JSON.",
            model=model,
            api_key=api_key,
            api_base=api_base,
            temperature=0.3,
            fallback_mock_data=fallback_data
        )
    except Exception as e:
        logger.error(f"Failed to generate email for {lead.email}: {e}")
        response = fallback_data

    selected_resume = response.get("selected_resume") or fallback_resume
    if not selected_resume.endswith(".pdf"):
        selected_resume += ".pdf"
    if selected_resume not in resume_profiles:
        selected_resume = fallback_resume

    resume_reason = response.get("resume_reason") or f"Matched technical profile to {lead.company}."
    subject = response.get("subject") or f"Exploring engineering opportunities at {lead.company}"
    alt_subjects = response.get("alternative_subjects") or [subject]
    body = response.get("email_body") or ""
    personalization_sig = response.get("personalization_signal") or lead.notes or lead.company
    confidence = float(response.get("confidence", 0.92))

    draft = EmailDraft(
        id=str(uuid.uuid4())[:8],
        email=lead.email,
        name=lead.name,
        company=lead.company,
        role=lead.role,
        subject=subject,
        alternative_subjects=alt_subjects,
        body=body,
        selected_resume=selected_resume,
        resume_reason=resume_reason,
        personalization_signal=personalization_sig,
        confidence=confidence,
        status="GENERATED",
        created_at=datetime.now().isoformat()
    )

    # Quality Control Pass
    quality = evaluate_email_quality(draft, lead)
    draft.quality_score = quality.quality_score
    draft.personalization_score = quality.personalization_score
    draft.quality_issues = quality.issues

    return draft
