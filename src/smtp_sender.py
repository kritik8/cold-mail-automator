"""SMTP email sender with TLS, attachments, conservative rate limiting, and duplicate safety."""
import os
import re
import html
import smtplib
import time
import random
import mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formataddr, make_msgid
from datetime import datetime
from typing import List, Optional, Tuple
from src.config import AppConfig
from src.models import EmailDraft
from src.storage import record_send_event, save_drafts, load_send_history, sync_trackers_on_send
from src.logger import get_logger

logger = get_logger()

# ANSI Color Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def build_mime_message(
    sender_name: str,
    sender_email: str,
    recipient_email: str,
    recipient_name: str,
    subject: str,
    body: str,
    attachment_path: Optional[str] = None,
    attachment_display_name: str = "Kritik_Jain_Resume.pdf"
) -> Tuple[MIMEMultipart, str]:
    """Build a multi-part MIME email message with optional resume PDF attachment and HTML hyperlink support."""
    msg = MIMEMultipart("mixed")
    msg_id = make_msgid()
    msg["Message-ID"] = msg_id
    msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
    msg["From"] = formataddr((sender_name, sender_email))
    msg["To"] = formataddr((recipient_name, recipient_email))
    msg["Subject"] = subject

    # Create alternative container for plain text and HTML
    alt_part = MIMEMultipart("alternative")

    # Plain text body fallback: convert markdown links [Text](URL) -> Text
    plain_body = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', body)
    alt_part.attach(MIMEText(plain_body, "plain", "utf-8"))

    # HTML body: convert markdown links [Text](URL) -> <a href="URL">Text</a>
    escaped_body = html.escape(body)
    html_body_content = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        r'<a href="\2" style="color: #0b57d0; text-decoration: underline;">\1</a>',
        escaped_body
    )
    html_lines = html_body_content.split("\n")
    html_formatted = "<br>".join(html_lines)
    full_html = f"""<html>
<head></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14px; line-height: 1.5; color: #222222;">
<div>{html_formatted}</div>
</body>
</html>"""
    alt_part.attach(MIMEText(full_html, "html", "utf-8"))

    msg.attach(alt_part)

    # Attach PDF resume if provided
    if attachment_path:
        if not os.path.exists(attachment_path):
            raise FileNotFoundError(f"Resume file not found at: {attachment_path}")
        
        with open(attachment_path, "rb") as f:
            pdf_bytes = f.read()

        part = MIMEApplication(pdf_bytes, _subtype="pdf")
        part.add_header("Content-Disposition", "attachment", filename=attachment_display_name)
        msg.attach(part)

    return msg, msg_id


def connect_smtp(config: AppConfig) -> smtplib.SMTP:
    """Establish authenticated connection to SMTP server."""
    if not config.smtp_password:
        raise ValueError("SMTP_PASSWORD is not set in .env. Please set your email app password.")

    if config.smtp_use_ssl:
        server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=20)
    else:
        server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=20)
        if config.smtp_use_tls:
            server.starttls()

    server.login(config.smtp_username, config.smtp_password)
    return server


def send_single_draft(
    draft: EmailDraft,
    config: AppConfig,
    server: Optional[smtplib.SMTP] = None
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Send an individual approved email draft.
    Returns: (success_bool, message_id_or_none, error_str_or_none)
    """
    resume_path = os.path.join(config.resumes_dir, draft.selected_resume)
    if not os.path.exists(resume_path):
        return False, None, f"Selected resume '{draft.selected_resume}' not found on disk at {resume_path}"

    display_attachment_name = f"{config.sender_profile.name.replace(' ', '_')}_Resume.pdf"

    try:
        mime_msg, msg_id = build_mime_message(
            sender_name=config.sender_profile.name,
            sender_email=config.smtp_username,
            recipient_email=draft.email,
            recipient_name=draft.name,
            subject=draft.subject,
            body=draft.body,
            attachment_path=resume_path,
            attachment_display_name=display_attachment_name
        )

        should_close = False
        if server is None:
            server = connect_smtp(config)
            should_close = True

        server.sendmail(config.smtp_username, [draft.email], mime_msg.as_string())

        if should_close:
            server.quit()

        return True, msg_id, None
    except Exception as e:
        return False, None, str(e)


def send_test_email(config: AppConfig) -> bool:
    """Send a test email to the configured TEST_EMAIL address to verify SMTP setup."""
    print(f"\n{CYAN}--- Testing SMTP Connection ---{RESET}")
    print(f"Host: {config.smtp_host}:{config.smtp_port}")
    print(f"User: {config.smtp_username}")
    print(f"Target Test Email: {config.test_email}")

    sample_resume = "resume_1.pdf"
    resume_path = os.path.join(config.resumes_dir, sample_resume)
    if not os.path.exists(resume_path):
        print(f"{YELLOW}Warning: {sample_resume} not found. Testing without attachment.{RESET}")
        resume_path = None

    test_draft = EmailDraft(
        email=config.test_email,
        name=config.sender_profile.name,
        company="Test Outreach",
        role="Test Role",
        subject="[Test] Cold Mail Automator — SMTP Verification",
        body=(
            f"Hello {config.sender_profile.name},\n\n"
            f"This is a test outreach verification email sent from your Cold Mail Automator tool.\n"
            f"If you received this with the attached resume, your SMTP credentials and PDF attachments are functioning properly.\n\n"
            f"{config.sender_profile.default_signature}"
        ),
        selected_resume=sample_resume,
        resume_reason="SMTP configuration testing",
        status="APPROVED"
    )

    try:
        print(f"Connecting to SMTP server...")
        success, msg_id, err = send_single_draft(test_draft, config)
        if success:
            print(f"{GREEN}[OK] Test email successfully sent to {config.test_email}! (Message ID: {msg_id}){RESET}")
            logger.info(f"Test email sent successfully to {config.test_email}")
            return True
        else:
            print(f"{RED}[FAILED] Test email failed: {err}{RESET}")
            logger.error(f"Test email failed: {err}")
            return False
    except Exception as e:
        print(f"{RED}[FAILED] SMTP Connection Error: {e}{RESET}")
        logger.error(f"SMTP verification exception: {e}")
        return False


def send_approved_batch(drafts: List[EmailDraft], config: AppConfig, limit: Optional[int] = None) -> None:
    """Send all drafts marked as APPROVED with conservative delays and safety checks."""
    approved_drafts = [d for d in drafts if d.status == "APPROVED"]

    if not approved_drafts:
        print(f"\n{YELLOW}No APPROVED drafts found to send.{RESET}")
        print("Run 'python main.py review' or 'python main.py approve-all' to inspect and approve drafts first.")
        return

    # Determine batch limit
    max_count = limit if limit is not None and limit > 0 else config.max_emails_per_run
    to_send = approved_drafts[:max_count]
    print(f"\n{CYAN}============================================================{RESET}")
    print(f"  {BOLD}OUTREACH SENDER: {len(to_send)} approved email(s) queued (Limit: {max_count}){RESET}")
    print(f"  Pacing: {config.min_delay_seconds}s - {config.max_delay_seconds}s randomized delay")
    print(f"  From: {config.smtp_username}")
    print(f"{CYAN}============================================================{RESET}")

    # Connect to SMTP
    try:
        server = connect_smtp(config)
    except Exception as e:
        print(f"\n{RED}Failed to authenticate with SMTP server: {e}{RESET}")
        print("Check your SMTP_USERNAME and SMTP_PASSWORD in .env, or run 'python main.py test-email'.")
        return

    sent_count = 0
    failed_count = 0

    try:
        for idx, draft in enumerate(to_send, 1):
            # Double-check send history
            history = load_send_history(config.send_history_path)
            if draft.email.lower() in history:
                print(f"[{idx}/{len(to_send)}] {YELLOW}Skipping {draft.email} (already sent in previous run).{RESET}")
                draft.status = "DUPLICATE"
                save_drafts(drafts, config.output_csv_path, config.output_json_path)
                continue

            print(f"[{idx}/{len(to_send)}] Sending to {BOLD}{draft.name}{RESET} <{draft.email}> @ {draft.company}...", end="", flush=True)

            # Attempt sending with auto-reconnect on timeout
            success = False
            msg_id = None
            err = None
            for attempt in range(2):
                try:
                    if server is None:
                        server = connect_smtp(config)
                    success, msg_id, err = send_single_draft(draft, config, server=server)
                    if success:
                        break
                    # If failed due to connection, reconnect and retry once
                    if err and any(discon in err.lower() for discon in ["connect", "closed", "broken pipe", "timeout", "reset", "abort"]):
                        try:
                            server.quit()
                        except Exception:
                            pass
                        server = connect_smtp(config)
                        success, msg_id, err = send_single_draft(draft, config, server=server)
                        if success:
                            break
                except Exception as e:
                    err = str(e)
                    try:
                        server = connect_smtp(config)
                    except Exception:
                        server = None

            now_str = datetime.now().isoformat()
            if success:
                draft.status = "SENT"
                draft.sent_at = now_str
                draft.error_message = None
                sent_count += 1
                print(f" {GREEN}[OK] SENT{RESET}")
                logger.info(f"Sent email to {draft.email} ({draft.company})")

                # Record in send history
                record_send_event(config.send_history_path, draft.email, {
                    "recipient_name": draft.name,
                    "company": draft.company,
                    "subject": draft.subject,
                    "selected_resume": draft.selected_resume,
                    "sent_at": now_str,
                    "message_id": msg_id,
                    "status": "SENT"
                })

                # Automatically update sent and pending CSV sheets
                sync_trackers_on_send(config.data_dir, draft, now_str)
            else:
                draft.status = "FAILED"
                draft.error_message = err
                failed_count += 1
                print(f" {RED}[FAILED] ({err}){RESET}")
                logger.error(f"Failed to send to {draft.email}: {err}")

            # Persist state after each send
            save_drafts(drafts, config.output_csv_path, config.output_json_path)

            # Apply conservative delay if more emails remain
            if idx < len(to_send):
                delay = random.randint(config.min_delay_seconds, config.max_delay_seconds)
                print(f"  {DIM}Waiting {delay}s before next email...{RESET}")
                time.sleep(delay)

    finally:
        try:
            server.quit()
        except Exception:
            pass

    print(f"\n{CYAN}============================================================{RESET}")
    print(f"Sending batch finished: {GREEN}{sent_count} Sent{RESET} | {RED}{failed_count} Failed{RESET}")
    print(f"{CYAN}============================================================{RESET}")
