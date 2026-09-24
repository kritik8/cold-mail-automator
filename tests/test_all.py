"""Comprehensive unit and integration tests for cold email outreach tool."""
import os
import json
import pytest
from src.models import Lead, EmailDraft, ResumeProfile, SenderProfile
from src.csv_loader import is_valid_email, normalize_column_name, load_leads_file
from src.resume_selector import score_resume_relevance, select_best_resume
from src.quality_checker import evaluate_email_quality
from src.storage import (
    load_do_not_contact,
    add_to_do_not_contact,
    load_send_history,
    record_send_event,
    save_drafts,
    load_drafts
)
from src.llm import clean_json_response, mock_generate_email
from src.smtp_sender import build_mime_message


def test_email_validation():
    assert is_valid_email("test@example.com") is True
    assert is_valid_email("first.last+tag@company.co.in") is True
    assert is_valid_email("invalid-email") is False
    assert is_valid_email("") is False
    assert is_valid_email("no_at_sign.com") is False


def test_column_normalization():
    assert normalize_column_name("Full Name") == "name"
    assert normalize_column_name("Work Email") == "email"
    assert normalize_column_name("Company Name") == "company"
    assert normalize_column_name("Job Title") == "role"
    assert normalize_column_name("Website") == "company_url"


def test_resume_relevance_scoring():
    ai_profile = ResumeProfile(
        filename="resume_1.pdf",
        file_path="resumes/resume_1.pdf",
        resume_name="AI Resume",
        target_profile="AI/ML Engineer, LLM Researcher",
        key_skills=["Python", "PyTorch", "LiteLLM", "RAG"],
        relevant_keywords=["ai", "llm", "rag", "pytorch"]
    )
    backend_profile = ResumeProfile(
        filename="resume_2.pdf",
        file_path="resumes/resume_2.pdf",
        resume_name="Backend Resume",
        target_profile="Backend Engineer, Systems Engineer",
        key_skills=["Go", "Redis", "Kafka", "PostgreSQL"],
        relevant_keywords=["backend", "go", "redis", "distributed"]
    )

    ai_lead_text = "XYZ AI building LLM agents and RAG pipelines"
    backend_lead_text = "ScaleInfra building distributed microservices in Go and Redis"

    assert score_resume_relevance(ai_lead_text, ai_profile) > score_resume_relevance(ai_lead_text, backend_profile)
    assert score_resume_relevance(backend_lead_text, backend_profile) > score_resume_relevance(backend_lead_text, ai_profile)


def test_clean_json_parsing():
    raw_markdown = '```json\n{"subject": "Hello", "confidence": 0.95}\n```'
    parsed = clean_json_response(raw_markdown)
    assert parsed["subject"] == "Hello"
    assert parsed["confidence"] == 0.95

    raw_with_text = 'Here is the response:\n{"selected_resume": "resume_1.pdf"}\nHope this helps!'
    parsed2 = clean_json_response(raw_with_text)
    assert parsed2["selected_resume"] == "resume_1.pdf"


def test_quality_checker_detects_cliches():
    lead = Lead(name="Rahul", email="rahul@xyz.ai", company="XYZ AI")
    
    # Bad email with cliché and fluff
    bad_draft = EmailDraft(
        email="rahul@xyz.ai",
        name="Rahul",
        company="XYZ AI",
        subject="Internship Application",
        body="I hope this email finds you well. I am writing to express my interest in your esteemed organization as a passionate individual.",
        selected_resume="resume_1.pdf",
        resume_reason="test"
    )
    result_bad = evaluate_email_quality(bad_draft, lead)
    assert result_bad.is_valid is False
    assert any("cliché" in issue for issue in result_bad.issues)

    # Good email following Tyagi guidelines
    good_draft = EmailDraft(
        email="rahul@xyz.ai",
        name="Rahul",
        company="XYZ AI",
        subject="AI agent workflows at XYZ AI — quick question",
        body=(
            "Hi Rahul,\n\n"
            "I've been following XYZ AI and really appreciate your focus on autonomous developer tooling. "
            "I'm an undergraduate at IIIT Bhopal specializing in LLM systems, where I recently built a RAG pipeline "
            "that cut latency by 35% with hybrid search. "
            "Would you be open to considering me for an AI engineering internship role?\n\n"
            "Best,\nKritik Jain"
        ),
        selected_resume="resume_1.pdf",
        resume_reason="test"
    )
    result_good = evaluate_email_quality(good_draft, lead)
    assert result_good.is_valid is True
    assert result_good.quality_score >= 0.85


def test_storage_and_blacklist(tmp_path):
    dnc_file = str(tmp_path / "do_not_contact.txt")
    add_to_do_not_contact(dnc_file, "blocked@company.com")
    
    blocked_set = load_do_not_contact(dnc_file)
    assert "blocked@company.com" in blocked_set

    # Test send history
    history_file = str(tmp_path / "send_history.json")
    record_send_event(history_file, "user@test.com", {"status": "SENT", "subject": "Test"})
    history = load_send_history(history_file)
    assert "user@test.com" in history
    assert history["user@test.com"]["status"] == "SENT"


def test_mime_message_attachment():
    msg, msg_id = build_mime_message(
        sender_name="Kritik Jain",
        sender_email="jkritik8@gmail.com",
        recipient_email="recipient@example.com",
        recipient_name="Recipient",
        subject="Subject line",
        body="Body text",
        attachment_path="resumes/resume_1.pdf"
    )
    assert msg["From"] == "Kritik Jain <jkritik8@gmail.com>"
    assert msg["To"] == "Recipient <recipient@example.com>"
    assert msg["Subject"] == "Subject line"
    assert msg["Message-ID"] == msg_id
