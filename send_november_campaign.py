"""November Campaign Dispatcher & Automated Daily Scheduler.

Reads data/november_campaign_tracker.csv, filters emails by scheduled date,
attaches the chosen resume PDF, rate-limits sends (40-65s), updates status to SENT,
and logs records to send_history.json and data/november_campaign_tracker.csv.
"""
import os
import sys
import csv
import time
import json
import random
import smtplib
import argparse
from datetime import datetime
from email.message import EmailMessage
from typing import Dict, Any, List

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

def dispatch_batch(target_date: str, dry_run: bool = True, max_send: int = 50) -> Dict[str, Any]:
    config = load_config()
    leads = load_campaign_leads(target_date=target_date)
    unprocessed = [l for l in leads if l.get("Status") in ["GENERATED", "DRAFTED", "PENDING"]]

    print("\n" + "=" * 65)
    print(f"  NOVEMBER OUTREACH DISPATCHER — {target_date}")
    print("=" * 65)
    print(f"Total leads scheduled for {target_date}: {len(leads)}")
    print(f"Pending/Ready to send:                 {len(unprocessed)}")
    print(f"Mode:                                  {'DRY RUN (Simulation)' if dry_run else 'LIVE SEND'}")
    print("=" * 65)

    if not unprocessed:
        print(f"No pending emails found for date {target_date}.")
        return {"total_sent": 0}

    stats = {
        "target_date": target_date,
        "total": len(unprocessed),
        "sent": 0,
        "skipped": 0,
        "errors": []
    }

    if dry_run:
        print("\n[DRY RUN SUMMARY OF BATCH]:")
        for i, lead in enumerate(unprocessed, 1):
            print(f"  [{i}/{len(unprocessed)}] {lead['Company']} | To: {lead['Recipient Email']} | Subject: {lead['Custom Subject']} | Resume: {lead['Selected Resume']}")
        print(f"\nDry-run complete. Run with --live to dispatch {len(unprocessed)} emails via SMTP.")
        return stats

    # Live Mode
    print(f"\n[LIVE] Connecting to SMTP server {config.smtp_host}:{config.smtp_port}...")
    server = None
    try:
        if config.smtp_use_ssl:
            server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30)
            if config.smtp_use_tls:
                server.starttls()
        server.login(config.smtp_username, config.smtp_password)
        print("[SUCCESS] SMTP authenticated successfully.\n")
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
                print(f"[{idx}/{len(unprocessed)}] SENT -> {lead['Company']} ({recipient_email}) | Resume: {resume_filename}")

                if idx < len(unprocessed):
                    delay = random.uniform(config.min_delay_seconds, config.max_delay_seconds)
                    print(f"  ... pausing {delay:.1f}s to maintain delivery reputation ...")
                    time.sleep(delay)

            except Exception as e:
                err_msg = f"Failed to send to {recipient_email}: {e}"
                print(f"[ERROR] {err_msg}")
                stats["errors"].append(err_msg)
                update_lead_status(recipient_email, status=f"FAILED: {e}")

    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass

    print(f"\n[COMPLETE] Successfully sent {stats['sent']} emails for date {target_date}.")
    return stats

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dispatch cold outreach batch by scheduled date.")
    parser.add_argument("--date", type=str, default="2026-11-04", help="Target scheduled date (YYYY-MM-DD)")
    parser.add_argument("--today", action="store_true", help="Send emails scheduled for today")
    parser.add_argument("--live", action="store_true", help="Enable live sending mode (default: dry run)")
    parser.add_argument("--limit", type=int, default=50, help="Maximum emails to send in one run")

    args = parser.parse_args()
    target_dt = datetime.now().strftime("%Y-%m-%d") if args.today else args.date
    dispatch_batch(target_date=target_dt, dry_run=not args.live, max_send=args.limit)

