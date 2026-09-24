"""Outreach Scheduler for timing cold email campaigns."""
import os
import sys
import time
from datetime import datetime
from src.config import load_config
from src.storage import load_drafts
from src.smtp_sender import send_approved_batch
from src.logger import get_logger

logger = get_logger()

# Colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def run_scheduled_job(target_time_str: str = "2026-09-25 09:30:00") -> None:
    """Wait until target_time and automatically dispatch approved emails."""
    config = load_config()
    
    # Parse target datetime
    target_dt = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M:%S")
    now = datetime.now()

    diff_seconds = (target_dt - now).total_seconds()
    
    print(f"\n{CYAN}============================================================{RESET}")
    print(f"  {BOLD}COLD MAIL AUTOMATOR — SCHEDULED SEND DISPATCHER{RESET}")
    print(f"{CYAN}============================================================{RESET}")
    print(f"Scheduled Execution Time: {BOLD}{target_dt.strftime('%A, %d %B %Y at %I:%M %p')}{RESET}")
    print(f"Current Local Time:       {now.strftime('%A, %d %B %Y at %I:%M %p')}")

    if diff_seconds > 0:
        hours = int(diff_seconds // 3600)
        minutes = int((diff_seconds % 3600) // 60)
        seconds = int(diff_seconds % 60)
        print(f"Waiting:                  {hours}h {minutes}m {seconds}s ({int(diff_seconds)} total seconds)")
        print(f"{YELLOW}Scheduler is active in the background. It will automatically start sending when the target time is reached.{RESET}")
        print(f"{CYAN}============================================================{RESET}\n")

        # Sleep loop with periodic status logging
        while True:
            remaining = (target_dt - datetime.now()).total_seconds()
            if remaining <= 0:
                break
            # Sleep in increments of up to 60 seconds
            sleep_step = min(60, remaining)
            time.sleep(sleep_step)

    print(f"\n{GREEN}Target time {target_dt} reached! Initiating batch email dispatch...{RESET}")
    logger.info(f"Target schedule time {target_dt} reached. Dispatching approved outreach emails.")

    # Load approved drafts and send
    drafts = load_drafts(config.output_json_path, config.output_csv_path)
    send_approved_batch(drafts, config)
