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


def _append_row_to_csv(file_path: str, row: Dict[str, Any], fieldnames: List[str]) -> None:
    """Helper to append a clean row to CSV, creating headers if the file is new."""
    import csv
    file_exists = os.path.exists(file_path) and os.path.getsize(file_path) > 0
    with open(file_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def _remove_row_from_csv(file_path: str, email_lower: str) -> None:
    """Helper to remove a sent email row from pending CSV sheets."""
    if not os.path.exists(file_path):
        return
    import csv
    rows = []
    fieldnames = []
    with open(file_path, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for r in reader:
            target_email = r.get("Email") or r.get("Email address") or ""
            if target_email.strip().lower() != email_lower:
                rows.append(r)
    with open(file_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sync_trackers_on_send(
    data_dir: str,
    draft: EmailDraft,
    now_str: str,
    campaign_name: Optional[str] = None
) -> None:
    """Automatically update pending and sent CSV sheets when an email is sent."""
    try:
        clean_date = now_str.replace("T", " ")[:19]
        email_lower = draft.email.strip().lower()

        # 1. Determine campaign if not explicitly provided
        if not campaign_name:
            c_low = draft.company.lower()
            e_low = draft.email.lower()
            if any(x in c_low or x in e_low for x in [".co.uk", "uk", "adecco", "brook street", "castlefield", "barker ross", "acorn"]):
                campaign_name = "UK Tech & Recruiting"
            elif any(x in c_low or x in e_low for x in [".dev", ".io", ".us", "typify", "pond ai", "sidekick", "estuary", "krea"]):
                campaign_name = "US Tech & AI"
            else:
                campaign_name = "India Founders & Tech"

        # Determine target sent CSV
        if "uk" in campaign_name.lower():
            target_sent_file = os.path.join(data_dir, "sent_uk_campaign.csv")
        elif "us" in campaign_name.lower():
            target_sent_file = os.path.join(data_dir, "sent_us_campaign.csv")
        else:
            target_sent_file = os.path.join(data_dir, "sent_india_outreach.csv")

        sent_row = {
            "Name": draft.name,
            "Company": draft.company,
            "Email": draft.email,
            "Role": draft.role,
            "Subject": draft.subject,
            "Resume": draft.selected_resume,
            "Campaign": campaign_name,
            "Status": "SENT",
            "Date Sent": clean_date
        }
        sent_fields = ["Name", "Company", "Email", "Role", "Subject", "Resume", "Campaign", "Status", "Date Sent"]

        # Append to target sent file and master sent_all_outreach.csv
        _append_row_to_csv(target_sent_file, sent_row, sent_fields)
        master_sent_file = os.path.join(data_dir, "sent_all_outreach.csv")
        _append_row_to_csv(master_sent_file, sent_row, sent_fields)

        # 2. Remove sent email from pending CSV files
        for pending_fname in ["pending_india_founders.csv", "pending_all_outreach.csv"]:
            pending_path = os.path.join(data_dir, pending_fname)
            _remove_row_from_csv(pending_path, email_lower)

        # 3. Update founder_outreach_tracker.csv if present
        tracker_path = os.path.join(data_dir, "founder_outreach_tracker.csv")
        if os.path.exists(tracker_path):
            try:
                df = pd.read_csv(tracker_path, dtype=str)
                mask = df["Email address"].str.lower() == email_lower
                if mask.any():
                    df.loc[mask, "Status (Drafted / Approved / Sent / Replied / Follow-up needed)"] = "Sent"
                    df.loc[mask, "Date sent"] = clean_date
                    df.to_csv(tracker_path, index=False, encoding="utf-8")
            except Exception as ex:
                logger.error(f"Error updating tracker CSV: {ex}")

        logger.info(f"Synchronized CSV trackers for {draft.email} (Status: SENT)")
    except Exception as e:
        logger.error(f"Failed to sync trackers for {draft.email}: {e}")
