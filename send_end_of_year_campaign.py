"""End-of-Year Campaign Dispatcher & Automated Daily Scheduler.

Reads data/end_of_year_campaign.csv (and syncs with end_of_year_campaign.csv),
filters leads by scheduled date, attaches the chosen resume PDF, rate-limits sends (40-65s),
formats emails with multipart plain-text and rich HTML hyperlinks for GitHub | LinkedIn | Portfolio,
updates status to SENT, and logs records to send_history.json and campaign CSVs.
Supports both first-touch cold outreach batches and scheduled follow-ups.
"""
import os
import sys

# Force immediate flush of output
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

import csv
import time
import json
import random
import smtplib
import argparse
import re
from datetime import datetime
from email.message import EmailMessage
from typing import Dict, Any, List, Tuple

LOG_FILE = os.path.join("logs", f"dispatch_eoy_{datetime.now().strftime('%Y_%m_%d')}.log")
os.makedirs("logs", exist_ok=True)

class TeeOutput:
    def __init__(self, stream, filepath):
        self.stream = stream
        self.file = open(filepath, "a", encoding="utf-8")
    def write(self, data):
        self.stream.write(data)
        self.file.write(data)
        self.file.flush()
    def flush(self):
        self.stream.flush()
        self.file.flush()

sys.stdout = TeeOutput(sys.stdout, LOG_FILE)
sys.stderr = TeeOutput(sys.stderr, LOG_FILE)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.config import load_config
from src.logger import setup_logger

logger = setup_logger(log_dir="logs")
PRIMARY_TRACKER_PATH = os.path.join("data", "end_of_year_campaign.csv")
SECONDARY_TRACKER_PATH = "end_of_year_campaign.csv"
HISTORY_PATH = os.path.join("data", "send_history.json")

GITHUB_URL = "https://github.com/kritik8"
LINKEDIN_URL = "https://www.linkedin.com/in/kritik-jain-064350356/"
PORTFOLIO_URL = "https://kritikjain.in/"

def format_email_content(raw_body: str) -> Tuple[str, str]:
    """Generates both plain-text fallback and rich HTML email parts with hyperlinks.
    Matches the user-specified signoff:
    Warm regards,
    Kritik Jain
    GitHub | LinkedIn | Portfolio
    """
    # 1. Plain text version
    plain_text = re.sub(
        r'\[GitHub\]\([^)]+\)\s*\|\s*\[LinkedIn\]\([^)]+\)\s*\|\s*\[Portfolio\]\([^)]+\)',
        f'GitHub ({GITHUB_URL}) | LinkedIn ({LINKEDIN_URL}) | Portfolio ({PORTFOLIO_URL})',
        raw_body
    )
    # Generic markdown link fallback if any
    plain_text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', plain_text)

    # 2. HTML version
    paragraphs = [p.strip() for p in raw_body.strip().split("\n\n") if p.strip()]
    html_paragraphs = []

    for p in paragraphs:
        if "Warm regards," in p and "Kritik Jain" in p:
            # Signoff block formatted exactly as requested
            html_signoff = (
                '<p style="margin: 20px 0 0 0; line-height: 1.5; color: #222222;">'
                'Warm regards,<br>'
                '<strong style="color: #111111;">Kritik Jain</strong><br>'
                f'<a href="{GITHUB_URL}" style="color: #0b57d0; text-decoration: underline;">GitHub</a> | '
                f'<a href="{LINKEDIN_URL}" style="color: #0b57d0; text-decoration: underline;">LinkedIn</a> | '
                f'<a href="{PORTFOLIO_URL}" style="color: #0b57d0; text-decoration: underline;">Portfolio</a>'
                '</p>'
            )
            html_paragraphs.append(html_signoff)
        else:
            p_escaped = p.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_html = p_escaped.replace('\n', '<br>')
            html_paragraphs.append(f'<p style="margin: 0 0 16px 0; color: #222222;">{p_html}</p>')

    html_body = (
        '<!DOCTYPE html>\n'
        '<html>\n'
        '<head><meta charset="utf-8"></head>\n'
        '<body style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, Helvetica, Arial, sans-serif; font-size: 14.5px; line-height: 1.6; color: #222222; margin: 0; padding: 0;">\n'
        f'{"\n".join(html_paragraphs)}\n'
        '</body>\n'
        '</html>'
    )

    return plain_text, html_body

def record_send_history(email: str, company: str, recipient_name: str, subject: str, resume: str, sent_at: str, message_id: str = "") -> None:
    history = {}
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = {}

    history[email.lower().strip()] = {
        "campaign": "end_of_year",
        "recipient_name": recipient_name,
        "company": company,
        "subject": subject,
        "selected_resume": resume,
        "sent_at": sent_at,
        "message_id": message_id,
        "status": "SENT"
    }

    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to update send_history.json: {e}")

def record_followup_history(email: str, company: str, recipient_name: str, subject: str, sent_at: str, message_id: str = "") -> None:
    history = {}
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = {}

    key = email.lower().strip()
    if key in history:
        history[key]["followup_1_sent_at"] = sent_at
        history[key]["followup_1_subject"] = subject
        history[key]["followup_1_status"] = "SENT"
    else:
        history[key] = {
            "campaign": "end_of_year",
            "recipient_name": recipient_name,
            "company": company,
            "subject": subject,
            "followup_1_sent_at": sent_at,
            "status": "SENT"
        }

    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to update send_history.json for follow-up: {e}")

def load_campaign_leads(target_date: str = None) -> List[Dict[str, Any]]:
    tracker = PRIMARY_TRACKER_PATH if os.path.exists(PRIMARY_TRACKER_PATH) else SECONDARY_TRACKER_PATH
    if not os.path.exists(tracker):
        raise FileNotFoundError(f"Campaign tracker not found at {PRIMARY_TRACKER_PATH} or {SECONDARY_TRACKER_PATH}")

    with open(tracker, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_leads = list(reader)

    if target_date:
        filtered = [
            r for r in all_leads
            if r.get("Scheduled Date") == target_date
            and r.get("Decision") == "TARGET"
        ]
        return filtered
    return [r for r in all_leads if r.get("Decision") == "TARGET"]

def load_followup_leads(due_date: str) -> List[Dict[str, Any]]:
    tracker = PRIMARY_TRACKER_PATH if os.path.exists(PRIMARY_TRACKER_PATH) else SECONDARY_TRACKER_PATH
    if not os.path.exists(tracker):
        raise FileNotFoundError(f"Campaign tracker not found at {PRIMARY_TRACKER_PATH} or {SECONDARY_TRACKER_PATH}")

    with open(tracker, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_leads = list(reader)

    filtered = [
        r for r in all_leads
        if r.get("Follow-up 1 Due Date") == due_date
        and r.get("Decision") == "TARGET"
        and r.get("Status") == "SENT"
        and r.get("Follow-up 1 Status") not in ["SENT"]
        and r.get("Replied", "").lower().strip() != "yes"
        and r.get("Bounced", "").lower().strip() != "yes"
        and r.get("Unsubscribed", "").lower().strip() != "yes"
        and r.get("Follow-up 1 Subject")
        and r.get("Follow-up 1 Body")
    ]
    return filtered

def update_lead_status(email: str, status: str, sent_at: str = "") -> None:
    for path in [PRIMARY_TRACKER_PATH, SECONDARY_TRACKER_PATH]:
        if not os.path.exists(path):
            continue
        with open(path, mode="r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
            fieldnames = list(rows[0].keys())

        for r in rows:
            if r.get("Recipient Email", "").lower().strip() == email.lower().strip():
                r["Status"] = status
                if sent_at:
                    r["Sent At"] = sent_at

        with open(path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

def update_followup_status(email: str, status: str, sent_at: str = "") -> None:
    for path in [PRIMARY_TRACKER_PATH, SECONDARY_TRACKER_PATH]:
        if not os.path.exists(path):
            continue
        with open(path, mode="r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
            fieldnames = list(rows[0].keys())

        for r in rows:
            if r.get("Recipient Email", "").lower().strip() == email.lower().strip():
                r["Follow-up 1 Status"] = status
                if sent_at:
                    r["Follow-up 1 Sent At"] = sent_at

        with open(path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

def connect_smtp(config, max_retries: int = 5, initial_delay: float = 5.0):
    for attempt in range(1, max_retries + 1):
        try:
            print(f"\n[LIVE] Connecting to SMTP server {config.smtp_host}:{config.smtp_port} (attempt {attempt}/{max_retries})...")
            if config.smtp_use_ssl:
                server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30)
                if config.smtp_use_tls:
                    server.starttls()
            server.login(config.smtp_username, config.smtp_password)
            print("[SUCCESS] SMTP authenticated successfully.\n")
            return server
        except Exception as e:
            print(f"  [WARN] SMTP connection failed ({e}).")
            if attempt < max_retries:
                delay = initial_delay * attempt
                print(f"  Retrying in {delay}s...")
                time.sleep(delay)
            else:
                raise e

def dispatch_batch(target_date: str, dry_run: bool = True, max_send: int = 50, min_delay: float = None, max_delay: float = None, server = None) -> Dict[str, Any]:
    config = load_config()
    actual_min_delay = min_delay if min_delay is not None else config.min_delay_seconds
    actual_max_delay = max_delay if max_delay is not None else config.max_delay_seconds
    leads = load_campaign_leads(target_date=target_date)
    unprocessed = [l for l in leads if l.get("Status") != "SENT"]

    print("\n" + "=" * 65)
    print(f"  END-OF-YEAR OUTREACH DISPATCHER (FIRST-TOUCH) — {target_date}")
    print("=" * 65)
    print(f"Total leads scheduled for {target_date}: {len(leads)}")
    print(f"Pending/Ready to send:                 {len(unprocessed)}")
    print(f"Mode:                                  {'DRY RUN (Simulation)' if dry_run else 'LIVE SEND'}")
    print("=" * 65)

    if not unprocessed:
        print(f"No pending first-touch emails found for date {target_date}.")
        return {"total_sent": 0}

    stats = {
        "target_date": target_date,
        "total": len(unprocessed),
        "sent": 0,
        "skipped": 0,
        "errors": []
    }

    if dry_run:
        print("\n[DRY RUN SUMMARY OF FIRST-TOUCH BATCH]:")
        for i, lead in enumerate(unprocessed, 1):
            plain, html = format_email_content(lead["Email Body"])
            print(f"  [{i}/{len(unprocessed)}] {lead['Company']} | To: {lead['Recipient Email']} | Subject: {lead['Custom Subject']} | Resume: {lead['Selected Resume']}")
        return stats

    # Live Mode
    own_server = False
    if server is None:
        try:
            server = connect_smtp(config)
            own_server = True
        except Exception as e:
            print(f"[FATAL] SMTP connection error: {e}")
            stats["errors"].append(str(e))
            return stats

    try:
        for idx, lead in enumerate(unprocessed, 1):
            if stats["sent"] >= max_send:
                print(f"[LIMIT] Reached max limit of {max_send} sends. Pausing.")
                break

            recipient_email = lead["Recipient Email"].strip()
            resume_filename = lead["Selected Resume"].strip()
            resume_path = os.path.join(config.resumes_dir, resume_filename)

            if not os.path.exists(resume_path):
                err = f"Missing resume at {resume_path}"
                print(f"[ERROR] {err}")
                stats["errors"].append(err)
                continue

            plain_content, html_content = format_email_content(lead["Email Body"])

            msg = EmailMessage()
            msg["Subject"] = lead["Custom Subject"]
            msg["From"] = f"Kritik Jain <{config.smtp_username}>"
            msg["To"] = recipient_email
            msg["Reply-To"] = "jkritik8@gmail.com"

            # Multipart: plain text fallback + rich HTML alternative
            msg.set_content(plain_content)
            msg.add_alternative(html_content, subtype="html")

            # Attachment (PDF resume)
            with open(resume_path, "rb") as f:
                pdf_data = f.read()
            msg.add_attachment(
                pdf_data,
                maintype="application",
                subtype="pdf",
                filename=resume_filename
            )

            sent_ok = False
            last_err = None
            for send_attempt in range(1, 4):
                try:
                    if server is None:
                        server = connect_smtp(config)
                    server.send_message(msg)
                    sent_ok = True
                    break
                except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, smtplib.SMTPException, OSError) as reconn_err:
                    last_err = reconn_err
                    print(f"  [WARN] SMTP issue on attempt {send_attempt}/3 ({reconn_err}). Reconnecting...")
                    try:
                        if server:
                            server.quit()
                    except Exception:
                        pass
                    server = None
                    time.sleep(5 * send_attempt)

            if not sent_ok:
                err_msg = f"Failed to send to {recipient_email}: {last_err}"
                print(f"[ERROR] {err_msg}")
                stats["errors"].append(err_msg)
                update_lead_status(recipient_email, status=f"FAILED: {last_err}")
                continue

            now_str = datetime.now().isoformat()
            stats["sent"] += 1
            update_lead_status(recipient_email, status="SENT", sent_at=now_str)
            record_send_history(
                email=recipient_email,
                company=lead["Company"],
                recipient_name=lead["Recipient Name"],
                subject=lead["Custom Subject"],
                resume=resume_filename,
                sent_at=now_str,
                message_id=msg.get("Message-ID", "")
            )
            print(f"[{idx}/{len(unprocessed)}] FIRST-TOUCH SENT -> {lead['Company']} ({recipient_email}) | Resume: {resume_filename}")

            if idx < len(unprocessed):
                delay = random.uniform(actual_min_delay, actual_max_delay)
                print(f"  ... pausing {delay:.1f}s to maintain delivery reputation ...")
                time.sleep(delay)

    finally:
        if own_server and server:
            try:
                server.quit()
            except Exception:
                pass

    print(f"\n[COMPLETE] Successfully sent {stats['sent']} first-touch emails for date {target_date}.")
    return stats

def dispatch_followups(due_date: str, dry_run: bool = True, max_send: int = 50, min_delay: float = None, max_delay: float = None, server = None) -> Dict[str, Any]:
    config = load_config()
    actual_min_delay = min_delay if min_delay is not None else config.min_delay_seconds
    actual_max_delay = max_delay if max_delay is not None else config.max_delay_seconds
    followups = load_followup_leads(due_date=due_date)

    print("\n" + "=" * 65)
    print(f"  END-OF-YEAR OUTREACH DISPATCHER (FOLLOW-UP 1) — DUE: {due_date}")
    print("=" * 65)
    print(f"Total follow-ups due for {due_date}:    {len(followups)}")
    print(f"Mode:                                  {'DRY RUN (Simulation)' if dry_run else 'LIVE SEND'}")
    print("=" * 65)

    if not followups:
        print(f"No pending follow-up emails due for date {due_date}.")
        return {"total_sent": 0}

    stats = {
        "due_date": due_date,
        "total": len(followups),
        "sent": 0,
        "skipped": 0,
        "errors": []
    }

    if dry_run:
        print("\n[DRY RUN SUMMARY OF FOLLOW-UP BATCH]:")
        for i, lead in enumerate(followups, 1):
            print(f"  [{i}/{len(followups)}] {lead['Company']} | To: {lead['Recipient Email']} | Subject: {lead['Follow-up 1 Subject']} | Resume: {lead['Selected Resume']}")
        return stats

    # Live Mode
    own_server = False
    if server is None:
        try:
            server = connect_smtp(config)
            own_server = True
        except Exception as e:
            print(f"[FATAL] SMTP connection error: {e}")
            stats["errors"].append(str(e))
            return stats

    try:
        for idx, lead in enumerate(followups, 1):
            if stats["sent"] >= max_send:
                print(f"[LIMIT] Reached max limit of {max_send} follow-up sends. Pausing.")
                break

            recipient_email = lead["Recipient Email"].strip()
            resume_filename = lead["Selected Resume"].strip()
            resume_path = os.path.join(config.resumes_dir, resume_filename)

            plain_content, html_content = format_email_content(lead["Follow-up 1 Body"])

            msg = EmailMessage()
            msg["Subject"] = lead["Follow-up 1 Subject"]
            msg["From"] = f"Kritik Jain <{config.smtp_username}>"
            msg["To"] = recipient_email
            msg["Reply-To"] = "jkritik8@gmail.com"

            msg.set_content(plain_content)
            msg.add_alternative(html_content, subtype="html")

            if os.path.exists(resume_path):
                with open(resume_path, "rb") as f:
                    pdf_data = f.read()
                msg.add_attachment(
                    pdf_data,
                    maintype="application",
                    subtype="pdf",
                    filename=resume_filename
                )

            sent_ok = False
            last_err = None
            for send_attempt in range(1, 4):
                try:
                    if server is None:
                        server = connect_smtp(config)
                    server.send_message(msg)
                    sent_ok = True
                    break
                except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, smtplib.SMTPException, OSError) as reconn_err:
                    last_err = reconn_err
                    print(f"  [WARN] SMTP issue on attempt {send_attempt}/3 ({reconn_err}). Reconnecting...")
                    try:
                        if server:
                            server.quit()
                    except Exception:
                        pass
                    server = None
                    time.sleep(5 * send_attempt)

            if not sent_ok:
                err_msg = f"Failed to send follow-up to {recipient_email}: {last_err}"
                print(f"[ERROR] {err_msg}")
                stats["errors"].append(err_msg)
                update_followup_status(recipient_email, status=f"FAILED: {last_err}")
                continue

            now_str = datetime.now().isoformat()
            stats["sent"] += 1
            update_followup_status(recipient_email, status="SENT", sent_at=now_str)
            record_followup_history(
                email=recipient_email,
                company=lead["Company"],
                recipient_name=lead["Recipient Name"],
                subject=lead["Follow-up 1 Subject"],
                sent_at=now_str,
                message_id=msg.get("Message-ID", "")
            )
            print(f"[{idx}/{len(followups)}] FOLLOW-UP SENT -> {lead['Company']} ({recipient_email}) | Subject: {lead['Follow-up 1 Subject']}")

            if idx < len(followups):
                delay = random.uniform(actual_min_delay, actual_max_delay)
                print(f"  ... pausing {delay:.1f}s to maintain delivery reputation ...")
                time.sleep(delay)

    finally:
        if own_server and server:
            try:
                server.quit()
            except Exception:
                pass

    print(f"\n[COMPLETE] Successfully sent {stats['sent']} follow-up emails for due date {due_date}.")
    return stats

def dispatch_daily_campaign(target_date: str, dry_run: bool = True, max_send: int = 100, min_delay: float = None, max_delay: float = None, send_new: bool = True, send_followups: bool = True):
    config = load_config()
    server = None
    if not dry_run:
        server = connect_smtp(config)

    try:
        new_stats = {"sent": 0}
        fu_stats = {"sent": 0}

        if send_new:
            new_stats = dispatch_batch(
                target_date=target_date,
                dry_run=dry_run,
                max_send=max_send,
                min_delay=min_delay,
                max_delay=max_delay,
                server=server
            )

        if send_followups:
            if not dry_run and new_stats.get("sent", 0) > 0:
                print("\nPausing 30s between first-touch batch and follow-up batch...")
                time.sleep(30)

            fu_stats = dispatch_followups(
                due_date=target_date,
                dry_run=dry_run,
                max_send=max_send,
                min_delay=min_delay,
                max_delay=max_delay,
                server=server
            )

        print("\n" + "=" * 65)
        print(f"  DAILY DISPATCH SUMMARY — {target_date}")
        print("=" * 65)
        print(f"First-touch sent: {new_stats.get('sent', 0)}")
        print(f"Follow-ups sent:  {fu_stats.get('sent', 0)}")
        print(f"Total delivered:  {new_stats.get('sent', 0) + fu_stats.get('sent', 0)}")
        print("=" * 65)

    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dispatch End-of-Year cold outreach batch and follow-ups by date.")
    parser.add_argument("--date", type=str, default="2026-11-23", help="Target scheduled date (YYYY-MM-DD)")
    parser.add_argument("--today", action="store_true", help="Send emails scheduled for today")
    parser.add_argument("--live", action="store_true", help="Enable live sending mode (default: dry run)")
    parser.add_argument("--limit", type=int, default=100, help="Maximum emails to send in one run")
    parser.add_argument("--min-delay", type=float, default=None, help="Custom minimum delay in seconds")
    parser.add_argument("--max-delay", type=float, default=None, help="Custom maximum delay in seconds")
    parser.add_argument("--skip-new", action="store_true", help="Skip sending new first-touch emails")
    parser.add_argument("--skip-followups", action="store_true", help="Skip sending follow-up emails")

    args = parser.parse_args()
    target_dt = datetime.now().strftime("%Y-%m-%d") if args.today else args.date
    dispatch_daily_campaign(
        target_date=target_dt,
        dry_run=not args.live,
        max_send=args.limit,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        send_new=not args.skip_new,
        send_followups=not args.skip_followups
    )
