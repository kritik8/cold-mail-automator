"""November Outreach Campaign Timed Dispatcher & Scheduler.

Schedules cold outreach to execute automatically within a specified time window
(e.g., 9:00 AM to 9:40 AM IST), calculating exact per-email delays to evenly
distribute sends across the window and complete safely before the end time.
"""
import os
import sys

# Force immediate flush of output
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

import time
import argparse
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, Any, List

LOG_FILE = os.path.join("logs", f"scheduled_send_{datetime.now().strftime('%Y_%m_%d')}.log")
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
from send_november_campaign import dispatch_daily_campaign, load_campaign_leads, load_followup_leads
from src.logger import setup_logger

logger = setup_logger(log_dir="logs")

def get_target_datetime(time_str: str, target_date_str: str) -> datetime:
    hour, minute = map(int, time_str.split(":"))
    date_parts = list(map(int, target_date_str.split("-")))
    return datetime(year=date_parts[0], month=date_parts[1], day=date_parts[2], hour=hour, minute=minute, second=0)

def calculate_window_delays(num_leads: int, start_str: str, end_str: str) -> tuple[float, float]:
    """Calculate min_delay and max_delay to fit all leads inside the window with safety margin."""
    sh, sm = map(int, start_str.split(":"))
    eh, em = map(int, end_str.split(":"))
    window_seconds = (eh * 3600 + em * 60) - (sh * 3600 + sm * 60)
    
    if num_leads <= 1:
        return (40.0, 60.0)

    # Reserve 10% of window as trailing buffer so it always finishes well before end_time
    usable_seconds = window_seconds * 0.90
    avg_delay = usable_seconds / (num_leads - 1)
    
    # Bound between at least 40s and reasonable max (65s)
    min_d = max(40.0, round(avg_delay - 10.0, 1))
    max_d = max(min_d + 10.0, round(avg_delay + 10.0, 1))
    return (min_d, max_d)

def run_scheduled_campaign(target_date: str = "2026-11-12", start_time: str = "08:15", end_time: str = "09:15", dry_run: bool = True, run_now: bool = False):
    leads = load_campaign_leads(target_date=target_date)
    unprocessed = [l for l in leads if l.get("Status") in ["GENERATED", "DRAFTED", "PENDING"]]
    num_new = len(unprocessed)

    followups = load_followup_leads(due_date=target_date)
    num_fu = len(followups)
    total_leads = num_new + num_fu

    min_delay, max_delay = calculate_window_delays(total_leads, start_time, end_time)
    target_start_dt = get_target_datetime(start_time, target_date)
    target_end_dt = get_target_datetime(end_time, target_date)

    print("\n" + "=" * 70)
    print("  NOVEMBER OUTREACH CAMPAIGN — TIMED WINDOW SCHEDULER")
    print("=" * 70)
    print(f"Scheduled Date:           {target_date}")
    print(f"Target Window:            {start_time} IST to {end_time} IST ({target_start_dt.strftime('%I:%M %p')} - {target_end_dt.strftime('%I:%M %p')})")
    print(f"First-Touch Leads:        {num_new}")
    print(f"Follow-ups Due:           {num_fu}")
    print(f"Total Emails to Deliver:  {total_leads}")
    print(f"Calculated Rate Limits:   {min_delay:.1f}s to {max_delay:.1f}s between sends (avg ~{(min_delay+max_delay)/2:.1f}s)")
    est_duration_min = ((total_leads - 1) * ((min_delay + max_delay) / 2)) / 60 if total_leads > 1 else 0
    print(f"Estimated Total Duration: ~{est_duration_min:.1f} minutes (completes around {(target_start_dt + timedelta(minutes=est_duration_min)).strftime('%I:%M %p')})")
    print(f"Current Local Time:       {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p IST')}")
    print(f"Mode:                     {'DRY RUN (Simulation)' if dry_run else 'LIVE DISPATCH'}")
    print("=" * 70)

    if not run_now:
        wait_seconds = (target_start_dt - datetime.now()).total_seconds()
        if wait_seconds > 0:
            h = int(wait_seconds // 3600)
            m = int((wait_seconds % 3600) // 60)
            s = int(wait_seconds % 60)
            print(f"\nCountdown: {h}h {m}m {s}s remaining until {start_time} IST start window.")
            print("System scheduler is actively running. Standing by until window opens...")
            
            while True:
                remaining = (target_start_dt - datetime.now()).total_seconds()
                if remaining <= 0:
                    break
                sleep_step = min(15, remaining)
                time.sleep(sleep_step)

    print(f"\n[WINDOW OPEN: {datetime.now().strftime('%I:%M:%S %p IST')}] Triggering November campaign dispatch (First-touch + Follow-ups)...")
    return dispatch_daily_campaign(
        target_date=target_date,
        dry_run=dry_run,
        max_send=100,
        min_delay=min_delay,
        max_delay=max_delay,
        send_new=True,
        send_followups=True
    )

def register_windows_task(target_date: str = "2026-11-12", start_time: str = "08:15"):
    """Register task in Windows Task Scheduler as an independent system safeguard."""
    python_exe = sys.executable
    script_path = os.path.abspath(__file__)
    task_name = f"KritikNovemberBatch_{target_date.replace('-', '_')}"
    
    # schtasks format for date: DD-MM-YYYY
    d_obj = datetime.strptime(target_date, "%Y-%m-%d")
    sd_str = d_obj.strftime("%d-%m-%Y")

    cmd = (
        f'schtasks /Create /SC ONCE /TN "{task_name}" '
        f'/TR "\\"{python_exe}\\" \\"{script_path}\\" --date {target_date} --start-time {start_time} --live --now" '
        f'/ST {start_time} /SD {sd_str} /F'
    )
    print("\n[Windows Task Scheduler Registration]")
    print(cmd)
    return cmd

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Schedule November cold mail batch for a specific time window.")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"), help="Target scheduled date (YYYY-MM-DD)")
    parser.add_argument("--start-time", type=str, default="08:15", help="Window start IST time (HH:MM)")
    parser.add_argument("--end-time", type=str, default="09:15", help="Window end IST time (HH:MM)")
    parser.add_argument("--live", action="store_true", help="Enable live sending mode (default: dry run)")
    parser.add_argument("--now", action="store_true", help="Trigger immediately without waiting for window start")
    parser.add_argument("--register-task", action="store_true", help="Register Windows Task Scheduler task")

    args = parser.parse_args()

    if args.register_task:
        register_windows_task(target_date=args.date, start_time=args.start_time)
        sys.exit(0)

    run_scheduled_campaign(
        target_date=args.date,
        start_time=args.start_time,
        end_time=args.end_time,
        dry_run=not args.live,
        run_now=args.now
    )
