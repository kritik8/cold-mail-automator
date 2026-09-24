"""Helper script to generate clean initial starter resume PDFs for testing and out-of-the-box operation."""
import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def create_resume_pdf(filename: str, title: str, summary: str, skills: list, experience: list, projects: list):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    doc = SimpleDocTemplate(filename, pagesize=letter, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1a365d'),
        spaceAfter=4
    )
    
    sub_header_style = ParagraphStyle(
        'SubHeaderStyle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#4a5568'),
        spaceAfter=12
    )
    
    section_style = ParagraphStyle(
        'SectionStyle',
        parent=styles['Heading2'],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#2b6cb0'),
        spaceBefore=10,
        spaceAfter=4
    )
    
    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#2d3748'),
        spaceAfter=6
    )
    
    story = []
    
    # Header
    story.append(Paragraph("<b>KRITIK JAIN</b>", header_style))
    story.append(Paragraph("IIIT Bhopal | jkritik8@gmail.com | +91 62603 16055 | <a href='https://kritikjain.in'>Portfolio</a> | <a href='https://github.com/kritik8'>GitHub</a> | <a href='https://www.linkedin.com/in/kritik-jain-064350356/'>LinkedIn</a>", sub_header_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cbd5e0'), spaceAfter=10))
    
    # Target / Summary
    story.append(Paragraph(f"<b>Focus: {title}</b>", section_style))
    story.append(Paragraph(summary, body_style))
    
    # Skills
    story.append(Paragraph("<b>Technical Skills</b>", section_style))
    story.append(Paragraph(f"<b>Core Technologies:</b> {', '.join(skills)}", body_style))
    
    # Experience
    story.append(Paragraph("<b>Relevant Experience & Contributions</b>", section_style))
    for exp in experience:
        story.append(Paragraph(f"<b>{exp['role']}</b> — <i>{exp['company']}</i>", body_style))
        story.append(Paragraph(f"• {exp['desc']}", body_style))
        story.append(Spacer(1, 4))
        
    # Projects
    story.append(Paragraph("<b>Key Projects</b>", section_style))
    for proj in projects:
        story.append(Paragraph(f"<b>{proj['name']}</b> ({proj['tech']})", body_style))
        story.append(Paragraph(f"• {proj['desc']}", body_style))
        story.append(Spacer(1, 4))
        
    doc.build(story)
    print(f"Generated {filename}")

if __name__ == "__main__":
    resumes_dir = os.path.join(os.path.dirname(__file__), "resumes")
    
    # 1. AI / ML Resume
    create_resume_pdf(
        os.path.join(resumes_dir, "resume_1.pdf"),
        "AI / Machine Learning & LLM Systems",
        "Computer Science undergraduate at IIIT Bhopal specializing in Large Language Model (LLM) workflows, agentic architectures, RAG pipelines, and deep learning. Active competitive programmer with strong algorithmic foundations.",
        ["Python", "PyTorch", "LangChain", "LiteLLM", "Hugging Face", "Vector DBs (Chroma/FAISS)", "Transformers", "FastAPI", "Docker", "Git"],
        [
            {
                "role": "AI Engineering Fellow / Project Lead",
                "company": "Open-Source AI Initiatives",
                "desc": "Architected end-to-end RAG pipelines and autonomous LLM agents with tool calling, optimizing retrieval latency by 35% and improving context relevance across multi-modal benchmarks."
            },
            {
                "role": "Machine Learning Research Intern",
                "company": "Applied AI Lab",
                "desc": "Trained and fine-tuned domain-specific transformer models using LoRA/QLoRA on custom instruction datasets, reducing model hallucination rates."
            }
        ],
        [
            {
                "name": "Autonomous Agentic Outreach Engine",
                "tech": "Python, LiteLLM, Vector Retrieval, Prompt Optimization",
                "desc": "Built an intelligent email synthesis system utilizing web scraping context, dynamic prompt synthesis, and real-time quality heuristics to craft targeted cold outreach."
            },
            {
                "name": "Neural Semantic Search & Summarizer",
                "tech": "PyTorch, FastAPI, Hugging Face, FAISS",
                "desc": "Implemented dense passage retrieval over 100k+ technical research papers with hybrid re-ranking and streaming summarization."
            }
        ]
    )

    # 2. Backend & Distributed Systems Resume
    create_resume_pdf(
        os.path.join(resumes_dir, "resume_2.pdf"),
        "Backend & Distributed Systems Engineering",
        "Undergraduate software engineer at IIIT Bhopal with focus on high-throughput backend services, distributed systems, API design, database optimization, and cloud architecture. Strong problem-solving credentials on Codeforces & LeetCode.",
        ["Python", "Go (Golang)", "FastAPI", "Django", "PostgreSQL", "Redis", "Kafka", "Docker", "gRPC", "Linux/Bash", "System Design"],
        [
            {
                "role": "Backend Engineering Intern",
                "company": "Scalable Cloud Platforms",
                "desc": "Engineered asynchronous event-driven microservices handling 5,000+ RPS with sub-50ms latency using Go, Redis caching, and PostgreSQL connection pooling."
            },
            {
                "role": "Systems Contributor",
                "company": "Distributed Open-Source Core",
                "desc": "Optimized database queries and built resilient retry and rate-limiting middleware, eliminating sporadic timeouts under peak traffic loads."
            }
        ],
        [
            {
                "name": "Distributed Task & Queue Dispatcher",
                "tech": "Go, Redis Streams, Docker, Prometheus",
                "desc": "Created a lightweight distributed worker pool with exponential backoff, dead-letter queues, and graceful shutdown handling 20k+ concurrent jobs."
            },
            {
                "name": "High-Performance REST & gRPC Gateway",
                "tech": "Python, FastAPI, Redis, PostgreSQL",
                "desc": "Developed a secure API gateway with JWT authentication, rate limiting, and centralized structured logging."
            }
        ]
    )

    # 3. Full-Stack & Software Engineering Resume
    create_resume_pdf(
        os.path.join(resumes_dir, "resume_3.pdf"),
        "Full-Stack Software Engineering & Product Development",
        "Versatile Software Engineering undergraduate at IIIT Bhopal experienced in delivering full-lifecycle web products from responsive frontends to reliable backend APIs and automated deployments.",
        ["JavaScript/TypeScript", "React", "Next.js", "Node.js", "Python", "FastAPI", "PostgreSQL", "Tailwind CSS", "RESTful APIs", "Git/CI/CD"],
        [
            {
                "role": "Full-Stack Developer Intern",
                "company": "Tech Growth Startup",
                "desc": "Built interactive SaaS dashboards and customer-facing workflows in React/Next.js and FastAPI, boosting user onboarding conversion by 22%."
            },
            {
                "role": "Web Engineering Lead",
                "company": "University Technical Society",
                "desc": "Led development of student portal serving 3,000+ active users with real-time notifications, role-based access control, and automated CI/CD deployment pipelines."
            }
        ],
        [
            {
                "name": "Modern Collaborative Workspace Platform",
                "tech": "Next.js, TypeScript, Node.js, WebSockets, PostgreSQL",
                "desc": "Developed a real-time collaborative workspace with markdown editing, live cursor syncing, and granular permission controls."
            },
            {
                "name": "Developer Productivity & Outreach Suite",
                "tech": "React, Python, SQLite, REST APIs",
                "desc": "Created an intuitive end-to-end tooling suite for developer productivity, lead tracking, and automated document synthesis."
            }
        ]
    )
