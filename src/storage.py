"""Storage and persistence utilities for drafts, send history, and blacklist."""
import os
import json
import pandas as pd
from typing import List, Dict, Set, Optional, Any
from src.models import EmailDraft
from src.logger import get_logger

logger = get_logger()


def load_do_not_contact(file_path: str) -> Set[str]:
    """Load set of blacklisted emails from do_not_contact.txt."""
    if not os.path.exists(file_path):
        return set()

    emails = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    emails.add(line.lower())
    except Exception as e:
        logger.error(f"Error reading do_not_contact list {file_path}: {e}")
    return emails


def add_to_do_not_contact(file_path: str, email: str) -> None:
    """Add a single email to the blacklist file."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    clean_email = email.strip().lower()
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(f"{clean_email}\n")
    logger.info(f"Added '{clean_email}' to do-not-contact blacklist.")


def load_send_history(file_path: str) -> Dict[str, Dict[str, Any]]:
    """Load send history mapping from send_history.json."""
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading send history {file_path}: {e}")
        return {}


def record_send_event(file_path: str, email: str, record: Dict[str, Any]) -> None:
    """Record a sent email entry into send_history.json."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    history = load_send_history(file_path)
    history[email.lower()] = record
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to record send history for {email}: {e}")


def save_drafts(drafts: List[EmailDraft], csv_path: str, json_path: str) -> None:
    """Save email drafts to both CSV and JSON formats."""
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    os.makedirs(os.path.dirname(json_path), exist_ok=True)

    # 1. Save JSON
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump([d.model_dump() for d in drafts], f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save drafts to JSON {json_path}: {e}")

    # 2. Save CSV
    try:
        rows = []
        for d in drafts:
            rows.append({
                "email": d.email,
                "name": d.name,
                "company": d.company,
                "role": d.role,
                "subject": d.subject,
                "body": d.body,
                "selected_resume": d.selected_resume,
                "resume_reason": d.resume_reason,
                "confidence": d.confidence,
                "quality_score": d.quality_score,
                "status": d.status,
                "sent_at": d.sent_at or "",
                "error_message": d.error_message or ""
            })
        df = pd.DataFrame(rows)
        df.to_csv(csv_path, index=False, encoding="utf-8")
        logger.info(f"Saved {len(drafts)} drafts to {csv_path} and {json_path}")
    except Exception as e:
        logger.error(f"Failed to save drafts to CSV {csv_path}: {e}")


def load_drafts(json_path: str, csv_path: Optional[str] = None) -> List[EmailDraft]:
    """Load generated email drafts from storage."""
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [EmailDraft(**item) for item in data]
        except Exception as e:
            logger.error(f"Failed to load drafts from JSON: {e}")

    if csv_path and os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path, dtype=str)
            drafts = []
            for _, row in df.iterrows():
                drafts.append(EmailDraft(
                    email=str(row.get("email", "")),
                    name=str(row.get("name", "")),
                    company=str(row.get("company", "")),
                    role=str(row.get("role", "")),
                    subject=str(row.get("subject", "")),
                    body=str(row.get("body", "")),
                    selected_resume=str(row.get("selected_resume", "resume_1.pdf")),
                    resume_reason=str(row.get("resume_reason", "")),
                    confidence=float(row.get("confidence", 0.90)),
                    quality_score=float(row.get("quality_score", 1.0)),
                    status=str(row.get("status", "GENERATED")),
                    sent_at=str(row.get("sent_at", "")) or None,
                    error_message=str(row.get("error_message", "")) or None
                ))
            return drafts
        except Exception as e:
            logger.error(f"Failed to load drafts from CSV: {e}")

    return []
