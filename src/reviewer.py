"""Interactive CLI reviewer for generated outreach emails."""
import sys
from typing import List
from src.models import EmailDraft
from src.storage import save_drafts
from src.logger import get_logger

logger = get_logger()

# ANSI Color Codes for terminal formatting
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def format_header(title: str) -> str:
    line = "=" * 60
    return f"{CYAN}{line}\n  {title}\n{line}{RESET}"


def display_draft(draft: EmailDraft, current_idx: int, total: int) -> None:
    """Pretty print a single draft to terminal."""
    status_color = GREEN if draft.status == "APPROVED" else (RED if draft.status == "REJECTED" else YELLOW)
    print(f"\n{CYAN}------------------------------------------------------------{RESET}")
    print(f"[{current_idx}/{total}] {BOLD}{draft.name}{RESET} ({draft.email})")
    print(f"Role/Org: {draft.role or 'N/A'} @ {BOLD}{draft.company}{RESET}")
    print(f"Current Status: {status_color}{draft.status}{RESET}")
    print(f"Selected Resume: {BOLD}{draft.selected_resume}{RESET}")
    print(f"Resume Rationale: {DIM}{draft.resume_reason}{RESET}")
    print(f"Confidence: {draft.confidence:.2f} | Quality Score: {draft.quality_score:.2f}")
    
    if draft.quality_issues:
        print(f"{YELLOW}Quality Warnings:{RESET} {', '.join(draft.quality_issues)}")

    print(f"\n{BOLD}Subject:{RESET} {draft.subject}")
    if draft.alternative_subjects and len(draft.alternative_subjects) > 1:
        print(f"{DIM}Alternative Subjects:{RESET}")
        for idx, alt in enumerate(draft.alternative_subjects, 1):
            print(f"  {idx}. {alt}")

    print(f"\n{BOLD}Body:{RESET}\n{draft.body.strip()}")
    print(f"{CYAN}------------------------------------------------------------{RESET}")


def edit_draft_interactive(draft: EmailDraft) -> None:
    """Allow user to edit subject or body in the terminal."""
    print(f"\n{BOLD}Editing Draft for {draft.name} ({draft.company}):{RESET}")
    print(f"1. Keep current subject or enter new subject")
    print(f"2. Keep current body or enter replacement line-by-line (type 'END' on a new line to finish)")
    
    new_subject = input(f"New Subject (press Enter to keep '{draft.subject}'): ").strip()
    if new_subject:
        draft.subject = new_subject
        print(f"{GREEN}Subject updated.{RESET}")

    print("\nDo you want to edit the email body? [y/N]: ", end="")
    edit_body = input().strip().lower()
    if edit_body in ["y", "yes"]:
        print(f"{YELLOW}Enter new body text. Type 'END' on a new line when done:{RESET}")
        lines = []
        while True:
            try:
                line = input()
                if line.strip() == "END":
                    break
                lines.append(line)
            except EOFError:
                break
        if lines:
            draft.body = "\n".join(lines).strip()
            print(f"{GREEN}Body updated successfully.{RESET}")


def run_interactive_review(
    drafts: List[EmailDraft],
    csv_path: str,
    json_path: str,
    review_all: bool = False
) -> None:
    """Run interactive terminal review session."""
    if not drafts:
        print(f"\n{YELLOW}No generated drafts found to review.{RESET}")
        print("Run 'python main.py generate <leads.csv>' first.")
        return

    # Filter targets
    pending = [d for d in drafts if review_all or d.status == "GENERATED"]
    if not pending:
        print(f"\n{GREEN}All {len(drafts)} drafts have already been reviewed!{RESET}")
        print("Run 'python main.py review --all' to re-inspect all drafts, or 'python main.py send' to send approved emails.")
        return

    print(format_header(f"REVIEWING EMAILS ({len(pending)} Pending / {len(drafts)} Total)"))
    print("Actions for each draft: [a]pprove, [r]eject, [e]dit, [s]kip, [q]uit")

    total_pending = len(pending)
    modified_count = 0

    for idx, draft in enumerate(pending, 1):
        while True:
            display_draft(draft, idx, total_pending)
            try:
                action = input(f"\nAction [{BOLD}a{RESET}pprove / {BOLD}r{RESET}eject / {BOLD}e{RESET}dit / {BOLD}s{RESET}kip / {BOLD}q{RESET}uit]: ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                action = "q"

            if action in ["a", "approve"]:
                draft.status = "APPROVED"
                modified_count += 1
                print(f"{GREEN}[OK] Marked as APPROVED{RESET}")
                save_drafts(drafts, csv_path, json_path)
                break
            elif action in ["r", "reject"]:
                draft.status = "REJECTED"
                modified_count += 1
                print(f"{RED}[REJECTED] Marked as REJECTED{RESET}")
                save_drafts(drafts, csv_path, json_path)
                break
            elif action in ["e", "edit"]:
                edit_draft_interactive(draft)
                save_drafts(drafts, csv_path, json_path)
                # Redisplay updated draft
                continue
            elif action in ["s", "skip"]:
                print(f"{YELLOW}Skipped (remains GENERATED){RESET}")
                break
            elif action in ["q", "quit", "exit"]:
                print(f"\n{YELLOW}Exiting review session. Progress saved.{RESET}")
                save_drafts(drafts, csv_path, json_path)
                return
            else:
                print(f"{RED}Invalid choice. Please type 'a', 'r', 'e', 's', or 'q'.{RESET}")

    # Summary
    approved = sum(1 for d in drafts if d.status == "APPROVED")
    rejected = sum(1 for d in drafts if d.status == "REJECTED")
    remaining = sum(1 for d in drafts if d.status == "GENERATED")

    print(f"\n{GREEN}Review complete!{RESET}")
    print(f"Summary: {GREEN}{approved} Approved{RESET} | {RED}{rejected} Rejected{RESET} | {YELLOW}{remaining} Pending{RESET}")
    if approved > 0:
        print(f"\nNext step: Run '{BOLD}python main.py send{RESET}' to send approved emails.")
