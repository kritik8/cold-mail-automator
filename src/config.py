"""Configuration loader for cold email outreach tool."""
import os
import json
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv
from src.models import SenderProfile
from src.logger import get_logger

# Load .env if present
load_dotenv()


@dataclass
class AppConfig:
    # LLM Settings
    litellm_api_key: Optional[str]
    litellm_proxy_url: Optional[str]
    llm_model: str
    
    # SMTP Settings
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_use_tls: bool
    smtp_use_ssl: bool
    
    # Rate Limiting & Safety
    min_delay_seconds: int
    max_delay_seconds: int
    max_emails_per_run: int
    
    # Test Email
    test_email: str
    
    # Directories & Paths
    base_dir: str
    config_dir: str
    resumes_dir: str
    data_dir: str
    output_dir: str
    logs_dir: str
    profile_path: str
    do_not_contact_path: str
    send_history_path: str
    output_csv_path: str
    output_json_path: str
    
    # Sender Profile
    sender_profile: SenderProfile


def load_config(base_dir: Optional[str] = None) -> AppConfig:
    """Load application configuration from environment variables and config files."""
    if base_dir is None:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    config_dir = os.path.join(base_dir, "config")
    resumes_dir = os.path.join(base_dir, "resumes")
    data_dir = os.path.join(base_dir, "data")
    output_dir = os.path.join(base_dir, "output")
    logs_dir = os.path.join(base_dir, "logs")

    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(resumes_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)

    profile_path = os.path.join(config_dir, "profile.json")
    do_not_contact_path = os.path.join(data_dir, "do_not_contact.txt")
    send_history_path = os.path.join(data_dir, "send_history.json")
    output_csv_path = os.path.join(output_dir, "generated_emails.csv")
    output_json_path = os.path.join(output_dir, "generated_emails.json")

    # Load sender profile
    if os.path.exists(profile_path):
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                profile_data = json.load(f)
                sender_profile = SenderProfile(**profile_data)
        except Exception as e:
            get_logger().warning(f"Could not parse profile.json: {e}. Using defaults.")
            sender_profile = SenderProfile()
    else:
        sender_profile = SenderProfile()

    # Rate limits with safe defaults
    min_delay = int(os.getenv("MIN_DELAY_SECONDS", "30"))
    max_delay = int(os.getenv("MAX_DELAY_SECONDS", "90"))
    if min_delay > max_delay:
        min_delay, max_delay = max_delay, min_delay

    max_emails = int(os.getenv("MAX_EMAILS_PER_RUN", "100"))

    return AppConfig(
        litellm_api_key=os.getenv("LITELLM_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"),
        litellm_proxy_url=os.getenv("LITELLM_PROXY_URL") or os.getenv("LITELLM_API_BASE") or os.getenv("API_BASE"),
        llm_model=os.getenv("LITELLM_MODEL") or os.getenv("LLM_MODEL", "google/gemini-3-flash-preview"),
        smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_username=os.getenv("SMTP_USERNAME", sender_profile.email),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_use_tls=os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes"),
        smtp_use_ssl=os.getenv("SMTP_USE_SSL", "false").lower() in ("true", "1", "yes"),
        min_delay_seconds=min_delay,
        max_delay_seconds=max_delay,
        max_emails_per_run=max_emails,
        test_email=os.getenv("TEST_EMAIL", sender_profile.email),
        base_dir=base_dir,
        config_dir=config_dir,
        resumes_dir=resumes_dir,
        data_dir=data_dir,
        output_dir=output_dir,
        logs_dir=logs_dir,
        profile_path=profile_path,
        do_not_contact_path=do_not_contact_path,
        send_history_path=send_history_path,
        output_csv_path=output_csv_path,
        output_json_path=output_json_path,
        sender_profile=sender_profile,
    )
