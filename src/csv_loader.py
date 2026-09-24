"""CSV and Excel lead loader with validation, normalization, and deduplication."""
import os
import re
import pandas as pd
from typing import List, Tuple, Set, Optional
from src.models import Lead
from src.logger import get_logger

logger = get_logger()

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

# Column mapping aliases for robustness
COLUMN_ALIASES = {
    "name": ["name", "full_name", "fullname", "contact_name", "first_name", "person_name", "lead_name", "candidate_name"],
    "email": ["email", "email_address", "mail", "contact_email", "work_email", "e-mail"],
    "company": ["company", "company_name", "organization", "org", "firm", "startup", "employer"],
    "role": ["role", "job_title", "title", "position", "designation", "contact_role"],
    "company_url": ["company_url", "website", "url", "company_website", "domain", "web_url"],
    "linkedin_url": ["linkedin_url", "linkedin", "linkedin_profile", "person_linkedin"],
    "job_url": ["job_url", "career_url", "job_link", "posting_url", "job_posting"],
    "notes": ["notes", "note", "context", "description", "background", "comments", "info"]
}


def normalize_column_name(col: str) -> str:
    """Normalize string column name to canonical schema key."""
    clean = re.sub(r'[^a-zA-Z0-9_]', '', col.strip().lower().replace(' ', '_').replace('-', '_'))
    for canonical, aliases in COLUMN_ALIASES.items():
        if clean in aliases:
            return canonical
    return clean


def is_valid_email(email: str) -> bool:
    """Check if the string matches a valid email pattern."""
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def load_leads_file(
    file_path: str,
    do_not_contact_emails: Optional[Set[str]] = None,
    sent_emails: Optional[Set[str]] = None
) -> Tuple[List[Lead], List[str]]:
    """
    Load leads from CSV or XLSX file.
    Performs:
    - Normalization of column names
    - Whitespace trimming
    - Required field validation (name, email, company)
    - Deduplication
    - Do-not-contact and already-sent filtering
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input file not found at: {file_path}")

    do_not_contact = do_not_contact_emails or set()
    sent = sent_emails or set()

    # Read CSV or Excel
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext in [".xlsx", ".xls"]:
            df = pd.read_excel(file_path, dtype=str)
        else:
            df = pd.read_csv(file_path, dtype=str)
    except Exception as e:
        raise ValueError(f"Failed to read file {file_path}: {e}")

    # Normalize column names
    df.columns = [normalize_column_name(str(c)) for c in df.columns]

    # Check mandatory columns
    mandatory = ["name", "email", "company"]
    missing_mandatory = [col for col in mandatory if col not in df.columns]
    if missing_mandatory:
        raise ValueError(f"Missing mandatory column(s) in {file_path}: {', '.join(missing_mandatory)}. Found columns: {list(df.columns)}")

    leads: List[Lead] = []
    skipped_messages: List[str] = []
    seen_in_batch: Set[str] = set()

    for idx, row in df.iterrows():
        row_num = idx + 2  # 1-indexed plus header

        name = str(row.get("name", "") or "").strip()
        email = str(row.get("email", "") or "").strip().lower()
        company = str(row.get("company", "") or "").strip()
        role = str(row.get("role", "") or "").strip()
        company_url = str(row.get("company_url", "") or "").strip()
        linkedin_url = str(row.get("linkedin_url", "") or "").strip()
        job_url = str(row.get("job_url", "") or "").strip()
        notes = str(row.get("notes", "") or "").strip()

        # Handle 'nan' from pandas
        if name.lower() == "nan": name = ""
        if email.lower() == "nan": email = ""
        if company.lower() == "nan": company = ""
        if role.lower() == "nan": role = ""
        if company_url.lower() == "nan": company_url = ""
        if linkedin_url.lower() == "nan": linkedin_url = ""
        if job_url.lower() == "nan": job_url = ""
        if notes.lower() == "nan": notes = ""

        # Validate mandatory values
        if not name or not email or not company:
            skipped_messages.append(f"Row {row_num}: Missing name, email, or company. Skipped.")
            continue

        if not is_valid_email(email):
            skipped_messages.append(f"Row {row_num}: Invalid email format '{email}'. Skipped.")
            continue

        # Check blacklist
        if email in do_not_contact:
            skipped_messages.append(f"Row {row_num}: '{email}' is in do-not-contact list. Skipped.")
            continue

        # Check already sent history
        if email in sent:
            skipped_messages.append(f"Row {row_num}: '{email}' already received an email earlier. Skipped.")
            continue

        # Check duplicate within this batch
        if email in seen_in_batch:
            skipped_messages.append(f"Row {row_num}: Duplicate email '{email}' in input file. Skipped.")
            continue

        seen_in_batch.add(email)

        leads.append(Lead(
            name=name,
            email=email,
            company=company,
            role=role,
            company_url=company_url,
            linkedin_url=linkedin_url,
            job_url=job_url,
            notes=notes,
            source_row=row_num
        ))

    logger.info(f"Loaded {len(leads)} valid leads from {file_path}. ({len(skipped_messages)} skipped)")
    return leads, skipped_messages
