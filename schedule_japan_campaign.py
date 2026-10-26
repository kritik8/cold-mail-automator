"""Japan Campaign Timed Dispatcher & Windows Cron Scheduler.

Schedules cold outreach to arrive in Japan inboxes at 10:00 AM JST (06:30 AM IST),
ensuring maximum open rates right as hiring managers and recruiters start their workday.
"""
import os
import sys
import time
import argparse
from datetime import datetime, timedelta
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from send_japan_campaign import send_japan_outreach
from src.logger import setup_logger

logger = setup_logger(log_dir="logs")

def get_next_run_datetime(hour: int = 6, minute: int = 30) -> datetime:
    """Calculate the next upcoming target datetime at specified IST hour and minute."""
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target

def run_countdown_and_send(target_dt: datetime, dry_run: bool = False, max_send: int = 100):
    """Wait in a non-blocking loop until target_dt and trigger send_japan_outreach."""
    jst_target = target_dt + timedelta(hours=3, minutes=30)
    
    print("\n" + "=" * 65)
    print("  JAPAN OUTREACH CAMPAIGN - TIMED DISPATCH SCHEDULER")
    print("=" * 65)
    print(f"Scheduled IST Execution: {target_dt.strftime('%A, %d %B %Y at %I:%M:%S %p IST')}")
    print(f"Corresponding Tokyo Time: {jst_target.strftime('%A, %d %B %Y at %I:%M:%S %p JST')}")
    print(f"Current Local Time:       {datetime.now().strftime('%A, %d %B %Y at %I:%M:%S %p IST')}")
    print(f"Mode:                     {'DRY RUN (Simulation)' if dry_run else 'LIVE DISPATCH'}")
    print("=" * 65)

    diff = (target_dt - datetime.now()).total_seconds()
    if diff > 0:
        h = int(diff // 3600)
        m = int((diff % 3600) // 60)
        s = int(diff % 60)
        print(f"\nCountdown: {h} hours, {m} minutes, {s} seconds until dispatch.")
        print("Waiting until target time... (Press Ctrl+C to abort at any time)")
        
        while True:
            remaining = (target_dt - datetime.now()).total_seconds()
            if remaining <= 0:
                break
            sleep_step = min(30, remaining)
            time.sleep(sleep_step)

    print(f"\nTarget time reached! Triggering Japan cold outreach dispatch (dry_run={dry_run})...")
    return send_japan_outreach(dry_run=dry_run, max_send=max_send)

def create_windows_scheduled_task(target_time_str: str = "06:30"):
    """Generate the Windows schtasks command to register a daily/one-time cron task."""
    python_exe = sys.executable
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "send_japan_campaign.py"))
    task_name = "KritikJapanColdMailDispatch"

    cmd = (
        f'schtasks /Create /SC ONCE /TN "{task_name}" '
        f'/TR "\\"{python_exe}\\" \\"{script_path}\\" --live" '
        f'/ST {target_time_str} /F'
    )
    print("\n[Windows Task Scheduler Command]")
    print(f"To register this as a persistent Windows cron task, run:\n\n{cmd}\n")
    return cmd

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Schedule Japan cold mail campaign at 10 AM JST (6:30 AM IST).")
    parser.add_argument("--time", type=str, default="06:30", help="Target IST time in HH:MM format (default: 06:30)")
    parser.add_argument("--live", action="store_true", help="Execute in live sending mode (default: dry-run simulation)")
    parser.add_argument("--now", action="store_true", help="Trigger immediately without waiting")
    parser.add_argument("--register-task", action="store_true", help="Print/create Windows Task Scheduler cron command")

    args = parser.parse_args()

    if args.register_task:
        create_windows_scheduled_task(args.time)
        sys.exit(0)

    hour, minute = map(int, args.time.split(":"))
    if args.now:
        target_datetime = datetime.now()
    else:
        target_datetime = get_next_run_datetime(hour, minute)

    run_countdown_and_send(target_dt=target_datetime, dry_run=not args.live)
