"""November Campaign Dispatcher & Automated Daily Scheduler.

Reads data/november_campaign_tracker.csv, filters emails by scheduled date,
attaches the chosen resume PDF, rate-limits sends (40-65s), updates status to SENT,
and logs records to send_history.json and data/november_campaign_tracker.csv.
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
from datetime import datetime
from email.message import EmailMessage
from typing import Dict, Any, List, Optional

LOG_FILE = os.path.join("logs", f"dispatch_{datetime.now().strftime('%Y_%m_%d')}.log")
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
TRACKER_PATH = os.path.join("data", "november_campaign_tracker.csv")
HISTORY_PATH = os.path.join("data", "send_history.json")

def record_send_history(email: str, company: str, recipient_name: str, subject: str, resume: str, sent_at: str, message_id: str = "") -> None:
    history = {}
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = {}

    history[email.lower().strip()] = {
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
    if not os.path.exists(TRACKER_PATH):
        raise FileNotFoundError(f"Campaign tracker not found at {TRACKER_PATH}")

    with open(TRACKER_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_leads = list(reader)

    if target_date:
        filtered = [r for r in all_leads if r.get("Scheduled Date") == target_date]
        return filtered
    return all_leads

def load_followup_leads(due_date: str) -> List[Dict[str, Any]]:
    if not os.path.exists(TRACKER_PATH):
        raise FileNotFoundError(f"Campaign tracker not found at {TRACKER_PATH}")

    with open(TRACKER_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_leads = list(reader)

    filtered = [
        r for r in all_leads
        if r.get("Follow-up 1 Due Date") == due_date
        and r.get("Follow-up 1 Status") not in ["SENT"]
        and r.get("Replied", "").lower().strip() != "yes"
        and r.get("Bounced", "").lower().strip() != "yes"
        and r.get("Unsubscribed", "").lower().strip() != "yes"
        and r.get("Follow-up 1 Subject")
        and r.get("Follow-up 1 Body")
    ]
    return filtered

def update_lead_status(email: str, status: str, sent_at: str = "") -> None:
    with open(TRACKER_PATH, mode="r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    for r in rows:
        if r.get("Recipient Email", "").lower().strip() == email.lower().strip():
            r["Status"] = status
            if sent_at:
                r["Sent At"] = sent_at

    with open(TRACKER_PATH, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def update_followup_status(email: str, status: str, sent_at: str = "") -> None:
    with open(TRACKER_PATH, mode="r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    for r in rows:
        if r.get("Recipient Email", "").lower().strip() == email.lower().strip():
            r["Follow-up 1 Status"] = status
            if sent_at:
                r["Follow-up 1 Sent At"] = sent_at

    with open(TRACKER_PATH, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def connect_smtp(config):
    print(f"\n[LIVE] Connecting to SMTP server {config.smtp_host}:{config.smtp_port}...")
    if config.smtp_use_ssl:
        server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=30)
    else:
        server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30)
        if config.smtp_use_tls:
            server.starttls()
    server.login(config.smtp_username, config.smtp_password)
    print("[SUCCESS] SMTP authenticated successfully.\n")
    return server

def dispatch_batch(target_date: str, dry_run: bool = True, max_send: int = 50, min_delay: float = None, max_delay: float = None, server = None) -> Dict[str, Any]:
    config = load_config()
    actual_min_delay = min_delay if min_delay is not None else config.min_delay_seconds
    actual_max_delay = max_delay if max_delay is not None else config.max_delay_seconds
    leads = load_campaign_leads(target_date=target_date)
    unprocessed = [l for l in leads if l.get("Status") in ["GENERATED", "DRAFTED", "PENDING"]]

    print("\n" + "=" * 65)
    print(f"  NOVEMBER OUTREACH DISPATCHER (FIRST-TOUCH) — {target_date}")
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

            msg = EmailMessage()
            msg["Subject"] = lead["Custom Subject"]
            msg["From"] = f"Kritik Jain <{config.smtp_username}>"
            msg["To"] = recipient_email
            msg["Reply-To"] = "jkritik8@gmail.com"
            msg.set_content(lead["Email Body"])

            with open(resume_path, "rb") as f:
                pdf_data = f.read()
            msg.add_attachment(
                pdf_data,
                maintype="application",
                subtype="pdf",
                filename=resume_filename
            )

            try:
                try:
                    server.send_message(msg)
                except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, smtplib.SMTPException, OSError) as reconn_err:
                    print(f"  [WARN] SMTP connection interrupted ({reconn_err}). Reconnecting...")
                    time.sleep(3)
                    server = connect_smtp(config)
                    server.send_message(msg)

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

            except Exception as e:
                err_msg = f"Failed to send to {recipient_email}: {e}"
                print(f"[ERROR] {err_msg}")
                stats["errors"].append(err_msg)
                update_lead_status(recipient_email, status=f"FAILED: {e}")

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
    print(f"  NOVEMBER OUTREACH DISPATCHER (FOLLOW-UP 1) — DUE: {due_date}")
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

            msg = EmailMessage()
            msg["Subject"] = lead["Follow-up 1 Subject"]
            msg["From"] = f"Kritik Jain <{config.smtp_username}>"
            msg["To"] = recipient_email
            msg["Reply-To"] = "jkritik8@gmail.com"
            msg.set_content(lead["Follow-up 1 Body"])

            if os.path.exists(resume_path):
                with open(resume_path, "rb") as f:
                    pdf_data = f.read()
                msg.add_attachment(
                    pdf_data,
                    maintype="application",
                    subtype="pdf",
                    filename=resume_filename
                )

            try:
                try:
                    server.send_message(msg)
                except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, smtplib.SMTPException, OSError) as reconn_err:
                    print(f"  [WARN] SMTP connection interrupted ({reconn_err}). Reconnecting...")
                    time.sleep(3)
                    server = connect_smtp(config)
                    server.send_message(msg)

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

            except Exception as e:
                err_msg = f"Failed to send follow-up to {recipient_email}: {e}"
                print(f"[ERROR] {err_msg}")
                stats["errors"].append(err_msg)
                update_followup_status(recipient_email, status=f"FAILED: {e}")

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
    parser = argparse.ArgumentParser(description="Dispatch cold outreach batch and follow-ups by date.")
    parser.add_argument("--date", type=str, default="2026-11-09", help="Target scheduled date (YYYY-MM-DD)")
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
