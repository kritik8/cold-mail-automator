from src.config import load_config
from src.storage import load_drafts, save_drafts

cfg = load_config()
drafts = load_drafts(cfg.output_json_path, cfg.output_csv_path)

reset_count = 0
for d in drafts:
    if d.status == "FAILED":
        d.status = "APPROVED"
        d.error_message = None
        reset_count += 1

save_drafts(drafts, cfg.output_csv_path, cfg.output_json_path)
total_approved = sum(1 for d in drafts if d.status == "APPROVED")
total_sent = sum(1 for d in drafts if d.status == "SENT")

print(f"Reset {reset_count} failed drafts back to APPROVED.")
print(f"Total Sent: {total_sent} | Total Approved (Ready to send): {total_approved} | Total: {len(drafts)}")
