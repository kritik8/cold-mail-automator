"""Data models for cold email outreach tool."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Lead(BaseModel):
    name: str
    email: str
    company: str
    role: Optional[str] = ""
    company_url: Optional[str] = ""
    linkedin_url: Optional[str] = ""
    job_url: Optional[str] = ""
    notes: Optional[str] = ""
    source_row: Optional[int] = None


class ResumeProfile(BaseModel):
    filename: str
    file_path: str
    resume_name: str
    target_profile: str
    key_skills: List[str] = []
    strongest_experiences: List[str] = []
    strongest_projects: List[str] = []
    relevant_keywords: List[str] = []
    suitable_categories: List[str] = []
    raw_text: Optional[str] = ""


class QualityResult(BaseModel):
    is_valid: bool = True
    quality_score: float = 1.0
    personalization_score: float = 1.0
    issues: List[str] = []


class EmailDraft(BaseModel):
    id: Optional[str] = None
    email: str
    name: str
    company: str
    role: Optional[str] = ""
    subject: str
    alternative_subjects: List[str] = []
    body: str
    selected_resume: str
    resume_reason: str
    personalization_signal: Optional[str] = ""
    confidence: float = 0.90
    quality_score: float = 1.0
    personalization_score: float = 1.0
    quality_issues: List[str] = []
    status: str = "GENERATED"  # GENERATED, APPROVED, REJECTED, SENT, FAILED, SKIPPED, DUPLICATE
    sent_at: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None


class SenderProfile(BaseModel):
    name: str = "Kritik Jain"
    phone: str = "+91 62603 16055"
    email: str = "jkritik8@gmail.com"
    education: Dict[str, str] = {}
    links: Dict[str, str] = {}
    default_signature: str = ""
    summary: str = ""
