"""LiteLLM integration with structured JSON generation and fallback mock mode."""
import os
import json
import re
from typing import Dict, Any, Optional
from src.logger import get_logger

logger = get_logger()

# Attempt importing litellm
try:
    import litellm
    # Suppress verbose litellm logs
    litellm.suppress_debug_info = True
    HAS_LITELLM = True
except ImportError:
    HAS_LITELLM = False


def clean_json_response(raw_response: str) -> Dict[str, Any]:
    """Strip markdown code fences and extract valid JSON."""
    text = raw_response.strip()
    
    # Remove markdown codeblocks ```json ... ```
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    # Try finding JSON bracket bounds if extra preamble exists
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        text = text[start_idx:end_idx+1]

    return json.loads(text)


def mock_generate_email(lead_data: Dict[str, Any], sender_name: str = "Kritik Jain") -> Dict[str, Any]:
    """Generate high-quality mock responses for testing and offline execution."""
    name = lead_data.get("name", "there")
    first_name = name.split()[0] if name else "there"
    company = lead_data.get("company", "your team")
    role = lead_data.get("role", "")
    notes = lead_data.get("notes", "").lower()
    selected_resume = lead_data.get("selected_resume", "resume_1.pdf")

    # Tailor based on selected track
    if "resume_1" in selected_resume or any(k in notes for k in ["ai", "llm", "rag", "agent"]):
        subject = f"AI / LLM engineering at {company} — quick question"
        alt_subjects = [
            f"Interested in what you're building at {company}",
            f"Question regarding AI systems at {company}",
            f"Exploring AI & LLM internship opportunities at {company}"
        ]
        body = (
            f"Hi {first_name},\n\n"
            f"I've been following {company}'s work and really appreciate your focus on practical AI workflows. "
            f"I'm an undergraduate at IIIT Bhopal specializing in LLM agent architectures and RAG pipelines, "
            f"where I recently optimized retrieval latency by 35% in our autonomous tooling projects. "
            f"Would you be open to considering me for an AI/ML internship role on your team?\n\n"
            f"Best,\n{sender_name}"
        )
        reason = "Lead focuses on AI/LLM engineering; matching AI/ML resume with RAG and agent projects."
        sig = "AI workflows and tooling"
    elif "resume_2" in selected_resume or any(k in notes for k in ["backend", "distributed", "go", "systems", "infra"]):
        subject = f"Backend systems at {company} — quick question"
        alt_subjects = [
            f"Exploring backend opportunities at {company}",
            f"Distributed systems & Go at {company}",
            f"Question about engineering at {company}"
        ]
        body = (
            f"Hi {first_name},\n\n"
            f"I noticed {company}'s emphasis on scalable backend architecture and high-throughput services. "
            f"As a CS student at IIIT Bhopal, I've engineered asynchronous microservices in Go and Redis handling 5k+ RPS "
            f"and built distributed worker pools with resilient backoff strategies. "
            f"Are you currently open to backend / SDE interns contributing to your core infrastructure?\n\n"
            f"Best,\n{sender_name}"
        )
        reason = "Lead emphasizes backend and distributed architecture; matching Backend & Go resume."
        sig = "Backend architecture and scalable services"
    else:
        subject = f"Exploring software engineering opportunities at {company}"
        alt_subjects = [
            f"Interested in what you're building at {company}",
            f"Full-stack engineering at {company} — quick question",
            f"Question about engineering at {company}"
        ]
        body = (
            f"Hi {first_name},\n\n"
            f"I came across {company} and really like your product direction. "
            f"I'm an undergraduate at IIIT Bhopal experienced in building end-to-end web applications with React, TypeScript, and FastAPI, "
            f"along with strong algorithmic foundations from competitive programming. "
            f"Would you be open to a brief chat about potential software engineering internship roles?\n\n"
            f"Best,\n{sender_name}"
        )
        reason = "General software / product engineering match; selecting Full-Stack resume."
        sig = "Full-stack web application development"

    return {
        "recipient_name": name,
        "company": company,
        "role": role,
        "subject": subject,
        "alternative_subjects": alt_subjects,
        "email_body": body,
        "selected_resume": selected_resume,
        "resume_reason": reason,
        "personalization_signal": sig,
        "confidence": 0.92
    }


def call_llm(
    prompt: str,
    system_prompt: str = "You are an expert technical career advisor and email copywriter.",
    model: str = "google/gemini-3-flash-preview",
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    temperature: float = 0.2,
    fallback_mock_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Call LLM via LiteLLM with structured JSON parsing and graceful fallback."""
    # Check if we should run in mock mode
    is_mock = (
        not api_key and
        not api_base and
        not os.getenv("GEMINI_API_KEY") and
        not os.getenv("OPENAI_API_KEY") and
        not os.getenv("ANTHROPIC_API_KEY") and
        not os.getenv("GROQ_API_KEY")
    ) or (model.lower() == "mock")

    if is_mock or not HAS_LITELLM:
        if fallback_mock_data:
            logger.info("Operating in Mock LLM mode (no API key configured). Generating deterministic high-quality draft.")
            return mock_generate_email(fallback_mock_data)
        else:
            return {
                "selected_resume": "resume_1.pdf",
                "reason": "Default track matched in mock mode",
                "confidence": 0.90
            }

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    try:
        # If proxy URL is provided, ensure OpenAI-compatible prefix for LiteLLM
        model_name = model
        if api_base and not any(model_name.startswith(p) for p in ["openai/", "custom_openai/", "litellm_proxy/", "azure/", "anthropic/"]):
            model_name = f"openai/{model_name}"

        kwargs = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
        }
        if api_key:
            kwargs["api_key"] = api_key
        if api_base:
            kwargs["api_base"] = api_base

        response = litellm.completion(**kwargs)
        raw_text = response.choices[0].message.content.strip()
        return clean_json_response(raw_text)
    except Exception as e:
        logger.warning(f"LiteLLM call failed ({e}). Falling back to deterministic generation.")
        if fallback_mock_data:
            return mock_generate_email(fallback_mock_data)
        raise e
