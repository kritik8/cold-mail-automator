"""Japan Job Outreach Campaign Dispatcher.

Handles safe, throttled sending of validated cold emails with verified resume attachments,
rate limiting, randomized delays, duplicate checking, and persistent logging.
"""
import os
import sys
import json
import time
import random
import smtplib
import datetime
from email.message import EmailMessage
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.config import load_config
from src.logger import setup_logger

logger = setup_logger(logs_dir="logs")

def send_japan_outreach(dry_run: bool = True, max_send: int = 100) -> Dict[str, Any]:
    """Execute or simulate sending the Japan outreach campaign."""
    config = load_config()
    drafts_file = os.path.join(config.data_dir, "japan_campaign_drafts.json")

    if not os.path.exists(drafts_file):
        raise FileNotFoundError(f"Drafts file not found at {drafts_file}. Run generate_japan_campaign.py first.")

    with open(drafts_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    validated_targets: List[Dict[str, Any]] = data.get("validated_targets", [])
    skipped_targets: List[Dict[str, Any]] = data.get("skipped_targets", [])

    # Load send history to avoid duplicates
    send_history = {}
    if os.path.exists(config.send_history_path):
        try:
            with open(config.send_history_path, "r", encoding="utf-8") as f:
                send_history = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read send history: {e}")

    stats = {
        "total_checked": len(validated_targets) + len(skipped_targets),
        "total_targets": len(validated_targets),
        "total_sent": 0,
        "total_skipped": len(skipped_targets),
        "already_contacted": 0,
        "resume_distribution": {},
        "errors": []
    }

    # Count resume distribution
    for t in validated_targets:
        r = t["resume"]
        stats["resume_distribution"][r] = stats["resume_distribution"].get(r, 0) + 1

    if dry_run:
        print("\n[DRY RUN MODE] No real emails will be dispatched.")
        print(f"Total targets ready to send: {len(validated_targets)}")
        print(f"Total skipped targets: {len(skipped_targets)}")
        print(f"Resume Distribution: {stats['resume_distribution']}\n")
        return stats

    # Live sending mode
    print(f"\n[LIVE MODE] Initializing SMTP connection to {config.smtp_host}:{config.smtp_port}...")
    server = None
    try:
        if config.smtp_use_ssl:
            server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30)
            if config.smtp_use_tls:
                server.starttls()
        server.login(config.smtp_username, config.smtp_password)
        print("[SUCCESS] SMTP authenticated successfully.")
    except Exception as e:
        print(f"[FATAL] SMTP Authentication failed: {e}")
        stats["errors"].append(f"SMTP Auth Error: {e}")
        return stats

    outreach_log_path = os.path.join(config.data_dir, "sent_japan_outreach.csv")
    csv_exists = os.path.exists(outreach_log_path)
    csv_file = open(outreach_log_path, "a", newline="", encoding="utf-8")
    import csv
    csv_writer = csv.writer(csv_file)
    if not csv_exists:
        csv_writer.writerow([
            "Timestamp", "Company", "Recipient", "Email", "Category", "Resume", "Subject", "Status"
        ])

    try:
        for idx, target in enumerate(validated_targets, 1):
            if stats["total_sent"] >= max_send:
                print(f"[LIMIT] Reached max send limit of {max_send}. Stopping.")
                break

            recipient_email = target["email"].lower().strip()
            if recipient_email in send_history:
                print(f"[{idx}/{len(validated_targets)}] SKIP: {recipient_email} already in send_history.json")
                stats["already_contacted"] += 1
                continue

            # Verify resume exists
            resume_path = os.path.join(config.resumes_dir, target["resume"])
            if not os.path.exists(resume_path):
                err = f"Resume file missing at {resume_path}"
                print(f"[ERROR] {err}")
                stats["errors"].append(err)
                continue

            # Build message
            msg = EmailMessage()
            msg["Subject"] = target["subject"]
            msg["From"] = f"Kritik Jain <{config.smtp_username}>"
            msg["To"] = target["email"]
            msg["Reply-To"] = "jkritik8@gmail.com"
            msg.set_content(target["full_email"])

            # Attach resume
            with open(resume_path, "rb") as f:
                pdf_data = f.read()
            msg.add_attachment(
                pdf_data,
                maintype="application",
                subtype="pdf",
                filename=target["resume"]
            )

            # Send email
            try:
                server.send_message(msg)
                stats["total_sent"] += 1
                timestamp = datetime.datetime.now().isoformat()
                print(f"[{idx}/{len(validated_targets)}] SENT -> {target['company']} ({target['email']}) | Resume: {target['resume']}")

                # Record in send history
                send_history[recipient_email] = {
                    "sent_at": timestamp,
                    "company": target["company"],
                    "recipient": target["recipient_name"],
                    "category": target["category"],
                    "resume": target["resume"],
                    "subject": target["subject"]
                }

                # Record in CSV
                csv_writer.writerow([
                    timestamp,
                    target["company"],
                    target["recipient_name"],
                    target["email"],
                    target["category"],
                    target["resume"],
                    target["subject"],
                    "SENT"
                ])
                csv_file.flush()

                # Randomized safety delay between sends
                if idx < len(validated_targets):
                    delay = random.uniform(config.min_delay_seconds, config.max_delay_seconds)
                    print(f"  ... waiting {delay:.1f}s before next send ...")
                    time.sleep(delay)

            except Exception as e:
                err_msg = f"Failed to send to {target['email']}: {e}"
                print(f"[ERROR] {err_msg}")
                stats["errors"].append(err_msg)
                csv_writer.writerow([
                    datetime.datetime.now().isoformat(),
                    target["company"],
                    target["recipient_name"],
                    target["email"],
                    target["category"],
                    target["resume"],
                    target["subject"],
                    f"FAILED: {e}"
                ])
                csv_file.flush()

    finally:
        csv_file.close()
        if server:
            try:
                server.quit()
            except Exception:
                pass

        # Save updated send_history.json
        try:
            with open(config.send_history_path, "w", encoding="utf-8") as f:
                json.dump(send_history, f, indent=2)
            print(f"[SUCCESS] Updated {config.send_history_path}")
        except Exception as e:
            print(f"[ERROR] Could not save send_history.json: {e}")

    return stats

if __name__ == "__main__":
    is_live = "--live" in sys.argv
    send_japan_outreach(dry_run=not is_live)
