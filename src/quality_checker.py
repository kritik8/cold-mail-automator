"""Quality control verification pass for generated emails."""
import re
from typing import List, Tuple
from src.models import QualityResult, EmailDraft, Lead

FORBIDDEN_PHRASES = [
    "hope this email finds you well",
    "i am writing to express my interest",
    "esteemed organization",
    "passionate individual",
    "cutting-edge",
    "cutting edge",
    "leverage",
    "synergy",
    "revolutionary",
    "dynamic environment",
    "i would be honored",
    "please find my resume attached",
    "find my resume attached",
    "kindly consider my application",
    "hope to hear from you",
    "looking forward to hearing from you",
    "let me know what you think",
    "i was impressed by your amazing company",
    "to whom it may concern"
]


def count_sentences(text: str) -> int:
    """Approximate number of sentences in text."""
    clean = re.sub(r'(?:Hi|Hello|Hey|Best|Thanks|Sincerely|Regards)[^\n]*', '', text, flags=re.IGNORECASE)
    clean = clean.strip()
    sentences = re.split(r'[.!?]+(?:\s+|\n+)', clean)
    return len([s for s in sentences if len(s.strip()) > 5])


def evaluate_email_quality(draft: EmailDraft, lead: Lead) -> QualityResult:
    """Deterministic quality analysis validating length, clichés, personalization, and CTA."""
    issues: List[str] = []
    body = draft.body.strip()
    body_lower = body.lower()
    subject_lower = draft.subject.lower()

    # 1. Word count check (target 50 - 150 words)
    words = body.split()
    word_count = len(words)
    if word_count < 35:
        issues.append(f"Email too brief ({word_count} words). Aim for 60-120 words.")
    elif word_count > 160:
        issues.append(f"Email too lengthy ({word_count} words). Aim for 60-120 words.")

    # 2. Sentence count check
    sentence_count = count_sentences(body)
    if sentence_count > 7:
        issues.append(f"Too many sentences ({sentence_count}). Aim for 3-5 concise sentences.")

    # 3. Forbidden phrases / AI cliché check
    for phrase in FORBIDDEN_PHRASES:
        if phrase in body_lower or phrase in subject_lower:
            issues.append(f"Contains AI-cliché or forbidden phrase: '{phrase}'.")

    # 4. Personalization signal check (must mention company or specific topic)
    company_clean = lead.company.lower()
    if company_clean and company_clean not in body_lower and company_clean not in subject_lower:
        issues.append(f"Company name '{lead.company}' missing from both subject and body.")

    # 5. Clear Call to Action / Ask check
    has_cta = any(cta in body_lower for cta in [
        "would you be open", "open to", "could we connect", "available for", "curious if",
        "open to considering", "brief chat", "internship role", "intern role", "opportunity"
    ])
    if not has_cta:
        issues.append("Missing a clean, natural call to action (ask).")

    # Calculate scores
    base_quality = 1.0 - (len(issues) * 0.15)
    quality_score = max(0.2, min(1.0, base_quality))

    personalization_score = 0.95
    if not lead.notes and not lead.company_url:
        personalization_score = 0.80
    if len(issues) > 1:
        personalization_score -= 0.15

    personalization_score = max(0.3, min(1.0, personalization_score))

    is_valid = len(issues) == 0 or (len(issues) == 1 and word_count >= 40 and word_count <= 150)

    return QualityResult(
        is_valid=is_valid,
        quality_score=round(quality_score, 2),
        personalization_score=round(personalization_score, 2),
        issues=issues
    )
