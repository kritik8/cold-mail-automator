"""Convenience launcher to run the scheduled send with an optional batch limit."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.scheduler import run_scheduled_job

if __name__ == "__main__":
    target_time = "2026-10-19 21:00:00"
    limit = 41  # 41 curated US tech outreach leads
    
    # Usage: python run_schedule.py [limit] [target_time]
    for arg in sys.argv[1:]:
        if arg.isdigit():
            limit = int(arg)
        elif len(arg) > 8 and ("-" in arg or ":" in arg):
            target_time = arg

    run_scheduled_job(target_time_str=target_time, limit=limit)
