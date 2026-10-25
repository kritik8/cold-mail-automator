"""Resume PDF parser and profile analyzer."""
import os
import re
import json
from typing import List, Dict, Optional
from pypdf import PdfReader
from src.models import ResumeProfile
from src.logger import get_logger

logger = get_logger()


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract clean text content from a given PDF file."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at: {pdf_path}")
    
    reader = PdfReader(pdf_path)
    text_chunks = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_chunks.append(page_text)
            
    return "\n".join(text_chunks).strip()


def analyze_resume_text(filename: str, file_path: str, raw_text: str) -> ResumeProfile:
    """Inspect raw resume text and extract structured profile attributes."""
    lower_text = raw_text.lower()
    
    ai_keywords = ["llm", "large language model", "agent", "rag", "pytorch", "hugging face", "machine learning", "ai "]
    backend_keywords = ["distributed", "golang", "go ", "microservice", "kafka", "redis", "throughput", "concurrency", "backend services", "grpc", "distributed systems"]
    fullstack_keywords = ["react", "next.js", "frontend", "full-stack", "full stack", "javascript", "typescript", "ui/ux", "web engineering", "collaborative workspace"]

    ai_score = sum(1 for k in ai_keywords if k in lower_text)
    backend_score = sum(1 for k in backend_keywords if k in lower_text)
    fullstack_score = sum(1 for k in fullstack_keywords if k in lower_text)

    # Determine target track by highest score
    if ai_score >= backend_score and ai_score >= fullstack_score and ai_score > 0:
        resume_name = "AI / ML & LLM Engineering Resume"
        target_profile = "AI/ML Engineer, LLM Systems Engineer, GenAI Developer, Applied ML Intern"
        suitable_categories = ["AI/ML Startup", "GenAI Platform", "Applied AI Company", "Research & LLM Teams"]
        key_skills = ["Python", "PyTorch", "LiteLLM", "LangChain", "RAG Pipelines", "Transformers", "FastAPI", "Vector Databases", "Prompt Optimization"]
        relevant_keywords = ["llm", "rag", "agent", "fine-tuning", "vector search", "ai", "machine learning", "nlp", "prompt", "transformers", "pytorch"]
        strongest_experiences = [
            "AI Engineering Fellow / Project Lead: Architected end-to-end RAG pipelines and autonomous LLM agents with tool calling, optimizing retrieval latency by 35%.",
            "Machine Learning Research Intern: Fine-tuned domain-specific transformer models using LoRA/QLoRA on custom instruction datasets."
        ]
        strongest_projects = [
            "Autonomous Agentic Outreach Engine: Intelligent multi-step synthesis system utilizing web scraping context and prompt optimization.",
            "Neural Semantic Search & Summarizer: Dense passage retrieval over 100k+ research papers with hybrid re-ranking."
        ]
    elif fullstack_score > backend_score and fullstack_score > 0:
        # Full-Stack / General Software Engineering
        resume_name = "Full-Stack & Software Engineering Resume"
        target_profile = "Full-Stack Developer, Frontend/Web Engineer, Software Engineer (SDE), Product Engineer"
        suitable_categories = ["Full-stack/Software Company", "Early Stage Product Startup", "B2B SaaS", "Developer Tooling"]
        key_skills = ["JavaScript/TypeScript", "React", "Next.js", "Node.js", "Python", "FastAPI", "PostgreSQL", "Tailwind CSS", "RESTful APIs", "Git/CI/CD"]
        relevant_keywords = ["full-stack", "react", "next.js", "typescript", "javascript", "node.js", "frontend", "web", "saas", "ui/ux", "product", "software"]
        strongest_experiences = [
            "Full-Stack Developer Intern: Built interactive SaaS dashboards and user onboarding workflows in React/Next.js and FastAPI, boosting conversion by 22%.",
            "Web Engineering Lead: Led development of student portal serving 3,000+ active users with real-time notifications and RBAC."
        ]
        strongest_projects = [
            "Modern Collaborative Workspace Platform: Real-time collaborative workspace with markdown editing, live cursor syncing, and WebSockets.",
            "Developer Productivity & Outreach Suite: End-to-end tooling suite for developer productivity and automated synthesis."
        ]
    else:
        resume_name = "Backend & Distributed Systems Resume"
        target_profile = "Backend Engineer, Distributed Systems Engineer, SDE Intern, Cloud Systems Engineer"
        suitable_categories = ["Backend/Infra Startup", "High-Scale SaaS", "Cloud Platforms", "FinTech / High-Throughput Services"]
        key_skills = ["Go (Golang)", "Python", "FastAPI", "Django", "PostgreSQL", "Redis", "Kafka", "Docker", "gRPC", "Distributed Systems", "System Design"]
        relevant_keywords = ["backend", "go", "golang", "distributed", "microservices", "redis", "kafka", "concurrency", "database", "grpc", "scale", "infrastructure"]
        strongest_experiences = [
            "Backend Engineering Intern: Engineered asynchronous event-driven microservices handling 5,000+ RPS with sub-50ms latency using Go, Redis, and PostgreSQL.",
            "Systems Contributor: Optimized database queries and built resilient retry/rate-limiting middleware eliminating timeouts."
        ]
        strongest_projects = [
            "Distributed Task & Queue Dispatcher: Lightweight worker pool with exponential backoff and dead-letter queues handling 20k+ concurrent jobs.",
            "High-Performance REST & gRPC Gateway: Secure API gateway with rate limiting and centralized structured logging."
        ]

    return ResumeProfile(
        filename=filename,
        file_path=file_path,
        resume_name=resume_name,
        target_profile=target_profile,
        key_skills=key_skills,
        strongest_experiences=strongest_experiences,
        strongest_projects=strongest_projects,
        relevant_keywords=relevant_keywords,
        suitable_categories=suitable_categories,
        raw_text=raw_text[:2000]
    )


def load_resume_profiles(resumes_dir: str, config_dir: Optional[str] = None) -> Dict[str, ResumeProfile]:
    """Inspect all configured resumes and return structured resume profiles."""
    profiles: Dict[str, ResumeProfile] = {}

    # Check if pre-configured resumes.json exists
    if config_dir:
        resumes_json_path = os.path.join(config_dir, "resumes.json")
        if os.path.exists(resumes_json_path):
            try:
                with open(resumes_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for filename, prof_dict in data.items():
                        # Ensure file_path points to existing file or resumes_dir
                        if "file_path" not in prof_dict or not os.path.exists(prof_dict["file_path"]):
                            prof_dict["file_path"] = os.path.join(resumes_dir, filename)
                        profiles[filename] = ResumeProfile(**prof_dict)
                if profiles:
                    logger.info(f"Loaded {len(profiles)} resume profiles from {resumes_json_path}")
                    return profiles
            except Exception as e:
                logger.warning(f"Failed to load profiles from {resumes_json_path}: {e}")

    # Fallback: scan resumes_dir for any PDFs
    pdf_files = [f for f in os.listdir(resumes_dir) if f.lower().endswith(".pdf")] if os.path.exists(resumes_dir) else []
    for filename in sorted(pdf_files):
        file_path = os.path.join(resumes_dir, filename)
        try:
            raw_text = extract_text_from_pdf(file_path)
            profile = analyze_resume_text(filename, file_path, raw_text)
            profiles[filename] = profile
            logger.info(f"Loaded and analyzed resume: {filename} -> {profile.resume_name}")
        except Exception as e:
            logger.error(f"Error parsing resume {file_path}: {e}")

    return profiles

