"""Cold Mail Automator - CLI Entrypoint.

Usage:
  python main.py generate <leads.csv_or_xlsx>
  python main.py review [--all]
  python main.py send
  python main.py status
  python main.py test-email
  python main.py analyze-resumes
"""
import sys
import os
import argparse
from datetime import datetime

# Add root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ensure utf-8 stdout encoding on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.config import load_config
from src.logger import setup_logger
from src.pdf_parser import load_resume_profiles
from src.csv_loader import load_leads_file
from src.company_research import gather_lead_context
from src.email_generator import generate_email_for_lead
from src.reviewer import run_interactive_review
from src.smtp_sender import send_approved_batch, send_test_email
from src.storage import (
    load_do_not_contact,
    load_send_history,
    save_drafts,
    load_drafts
)

# Colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

OK_ICON = "[OK]"
FAIL_ICON = "[X]"


def command_analyze_resumes(config):
    """Inspect and display structured profile representations of all configured resumes."""
    print(f"\n{CYAN}=== Resume Intelligence & Profiling ==={RESET}")
    profiles = load_resume_profiles(config.resumes_dir, config.config_dir)
    
    if not profiles:
        print(f"{RED}No resume PDFs found in {config.resumes_dir}!{RESET}")
        print("Please place resume_1.pdf, resume_2.pdf, and resume_3.pdf in the 'resumes/' folder.")
        return

    for filename, prof in profiles.items():
        print(f"\n{BOLD}[{filename}]{RESET} -> {GREEN}{prof.resume_name}{RESET}")
        print(f"  Target: {prof.target_profile}")
        print(f"  Skills: {', '.join(prof.key_skills[:7])}")
        print(f"  Top Projects: {', '.join(p.split(':')[0] for p in prof.strongest_projects)}")
        print(f"  Categories: {', '.join(prof.suitable_categories)}")

    print(f"\n{GREEN}Structured resume intelligence saved to config/resumes.json{RESET}")


def command_generate(args, config, logger):
    """Generate personalized cold email drafts from input CSV/XLSX file."""
    file_path = args.file
    if not os.path.exists(file_path):
        print(f"{RED}Error: Leads file not found at '{file_path}'{RESET}")
        sys.exit(1)

    print(f"\n{CYAN}--- Loading Leads & Resumes ---{RESET}")
    do_not_contact = load_do_not_contact(config.do_not_contact_path)
    send_history = load_send_history(config.send_history_path)
    sent_emails = set(send_history.keys())

    leads, skipped = load_leads_file(
        file_path,
        do_not_contact_emails=do_not_contact,
        sent_emails=sent_emails
    )

    if skipped:
        print(f"{YELLOW}Skipped {len(skipped)} lead(s):{RESET}")
        for s in skipped[:5]:
            print(f"  • {s}")
        if len(skipped) > 5:
            print(f"  ... and {len(skipped) - 5} more.")

    if not leads:
        print(f"{YELLOW}No actionable leads found in {file_path}.{RESET}")
        return

    print(f"\n{BOLD}Loaded {len(leads)} lead(s) ready for generation.{RESET}")

    # Load resumes
    resume_profiles = load_resume_profiles(config.resumes_dir, config.config_dir)
    if not resume_profiles:
        print(f"{YELLOW}Warning: No resumes found in {config.resumes_dir}. Generating starter resumes...{RESET}")
        from generate_resumes import create_resume_pdf
        # Generate defaults if absent
        command_analyze_resumes(config)
        resume_profiles = load_resume_profiles(config.resumes_dir, config.config_dir)

    print(f"\n{CYAN}--- Generating Email Drafts ---{RESET}")
    drafts = []

    # Check existing drafts to avoid overwriting previously approved/sent drafts
    existing_drafts = {d.email.lower(): d for d in load_drafts(config.output_json_path, config.output_csv_path)}

    for idx, lead in enumerate(leads, 1):
        # If already exists and is approved or sent, preserve it
        if lead.email.lower() in existing_drafts:
            prev = existing_drafts[lead.email.lower()]
            if prev.status in ["APPROVED", "SENT"]:
                print(f"[{idx}/{len(leads)}] {lead.name} @ {lead.company} -> {GREEN}Preserved ({prev.status}){RESET}")
                drafts.append(prev)
                continue

        print(f"[{idx}/{len(leads)}] {lead.name} @ {lead.company}...", end="", flush=True)

        # Web research if URL is available
        context = {}
        if lead.company_url or lead.job_url:
            context = gather_lead_context(lead.company_url, lead.job_url)

        draft = generate_email_for_lead(
            lead=lead,
            resume_profiles=resume_profiles,
            sender=config.sender_profile,
            company_context=context,
            model=config.llm_model,
            api_key=config.litellm_api_key,
            api_base=config.litellm_proxy_url
        )
        drafts.append(draft)
        print(f" {GREEN}{OK_ICON} Drafted ({draft.selected_resume} | Conf: {draft.confidence:.2f}){RESET}")

    # Save to storage
    save_drafts(drafts, config.output_csv_path, config.output_json_path)

    print(f"\n{GREEN}Generated {len(drafts)} drafts saved to:{RESET}")
    print(f"  - {config.output_csv_path}")
    print(f"  - {config.output_json_path}")
    print(f"\nRun: {BOLD}python main.py review{RESET} to inspect and approve.")


def command_review(args, config):
    """Review generated drafts in interactive terminal mode."""
    drafts = load_drafts(config.output_json_path, config.output_csv_path)
    run_interactive_review(
        drafts,
        csv_path=config.output_csv_path,
        json_path=config.output_json_path,
        review_all=getattr(args, "all", False)
    )


def command_send(config):
    """Send approved email drafts via SMTP."""
    drafts = load_drafts(config.output_json_path, config.output_csv_path)
    if not drafts:
        print(f"{YELLOW}No drafts found.{RESET}")
        print("Run 'python main.py generate <leads.csv>' first.")
        return

    send_approved_batch(drafts, config)


def command_status(config):
    """Display summary of generated, approved, sent, and blacklisted contacts."""
    drafts = load_drafts(config.output_json_path, config.output_csv_path)
    history = load_send_history(config.send_history_path)
    do_not_contact = load_do_not_contact(config.do_not_contact_path)

    counts = {
        "GENERATED": 0,
        "APPROVED": 0,
        "REJECTED": 0,
        "SENT": 0,
        "FAILED": 0,
        "SKIPPED": 0,
        "DUPLICATE": 0
    }

    for d in drafts:
        counts[d.status] = counts.get(d.status, 0) + 1

    print(f"\n{CYAN}============================================================{RESET}")
    print(f"  {BOLD}COLD MAIL AUTOMATOR — SYSTEM STATUS{RESET}")
    print(f"{CYAN}============================================================{RESET}")
    print(f"Total Drafts:           {len(drafts)}")
    print(f"  • {YELLOW}Generated / Pending:{RESET}  {counts['GENERATED']}")
    print(f"  • {GREEN}Approved (Ready):{RESET}    {counts['APPROVED']}")
    print(f"  • {RED}Rejected:{RESET}            {counts['REJECTED']}")
    print(f"  • {GREEN}Sent (Current File):{RESET} {counts['SENT']}")
    print(f"  • {RED}Failed:{RESET}              {counts['FAILED']}")
    print(f"------------------------------------------------------------")
    print(f"Total Sent in History:  {len(history)}")
    print(f"Do-Not-Contact List:    {len(do_not_contact)}")
    print(f"LLM Model:              {config.llm_model}")
    print(f"Sender:                 {config.sender_profile.name} <{config.smtp_username}>")
    print(f"{CYAN}============================================================{RESET}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Personalized Cold Outreach Mailer",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # generate
    gen_parser = subparsers.add_parser("generate", help="Generate drafts from CSV or XLSX")
    gen_parser.add_argument("file", help="Path to CSV or XLSX leads file")

    # review
    rev_parser = subparsers.add_parser("review", help="Review generated drafts interactively")
    rev_parser.add_argument("--all", action="store_true", help="Review all drafts including previously decided")

    # send
    subparsers.add_parser("send", help="Send approved emails via SMTP")

    # status
    subparsers.add_parser("status", help="Show system status and stats")

    # test-email
    subparsers.add_parser("test-email", help="Send a single verification email to TEST_EMAIL")

    # analyze-resumes
    subparsers.add_parser("analyze-resumes", help="Inspect and build resume profile representations")

    # schedule-send
    sched_parser = subparsers.add_parser("schedule-send", help="Schedule approved emails to be sent at a specific date and time")
    sched_parser.add_argument("--time", default="2026-09-25 09:30:00", help="Target execution timestamp (format: YYYY-MM-DD HH:MM:SS)")

    args = parser.parse_args()

    # Load configuration
    config = load_config()
    logger = setup_logger(config.logs_dir)

    if args.command == "generate":
        command_generate(args, config, logger)
    elif args.command == "review":
        command_review(args, config)
    elif args.command == "send":
        command_send(config)
    elif args.command == "schedule-send":
        from src.scheduler import run_scheduled_job
        run_scheduled_job(args.time)
    elif args.command == "status":
        command_status(config)
    elif args.command == "test-email":
        send_test_email(config)
    elif args.command == "analyze-resumes":
        command_analyze_resumes(config)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
