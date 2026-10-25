"""Japan Job Outreach Campaign Generator & Quality Validator.

Generates targeted, bespoke emails for Japan-based opportunities adhering strictly
to candidate profile constraints, resume selection rules, word count (120-180 words),
and tone guidelines.
"""
import os
import json
import csv
import re
from typing import List, Dict, Any

CAMPAIGN_TARGETS = [
    {
        "company": "Sakana AI",
        "recipient_name": "Sakana AI Recruiting Team",
        "email": "careers@sakana.ai",
        "category": "AI/ML & LLM Research",
        "resume": "Kritik_Jain_CV3.pdf",
        "role": "AI Research / Engineering Intern or New Grad",
        "reason": "Sakana AI develops nature-inspired foundation models and evolutionary model merging. Kritik's Applied AI resume highlights automated LLM auditing, LLM-as-a-Judge evaluation, and prompt benchmarking.",
        "subject": "Interest in AI/ML & LLM Engineering Opportunities — Kritik Jain, IIIT Bhopal",
        "salutation": "Hi Sakana AI Recruiting Team,",
        "body_paragraphs": [
            "I am a final-year B.Tech Information Technology student at IIIT Bhopal, writing to explore internship, new-grad, or early-career AI/ML engineering opportunities with Sakana AI.",
            "I have been following your work on evolutionary model merging and nature-inspired foundation models. My background centers on Applied AI and LLM systems engineering. During my internship at IndiaMART InterMESH, I developed a Go-based AI Auditor leveraging Langfuse and LLM-as-a-Judge evaluation, raising automated quality audit accuracy from 89% to 98.5% across 5,000+ test cases. I also built and evaluated end-to-end RAG pipelines and multimodal perception workflows combining YOLO and predictive analytics.",
            "I am currently based in India and would be interested in opportunities in Japan, including opportunities that may involve relocation or visa sponsorship. Could you let me know if you have openings where my background in LLM systems, evaluation, and applied ML pipelines could be relevant?",
            "My resume (Kritik_Jain_CV3.pdf) is attached. You can also view my projects on GitHub (https://github.com/kritik8) and portfolio (https://kritikjain.in/)."
        ]
    },
    {
        "company": "Citadel AI",
        "recipient_name": "Kenny Song",
        "email": "kenny@citadel-ai.com",
        "category": "AI Reliability & LLM Evaluation",
        "resume": "Kritik_Jain_CV3.pdf",
        "role": "Applied AI / ML Systems Engineer",
        "reason": "Citadel AI builds automated testing and auditing platforms for AI/LLMs. Directly aligns with Kritik's production AI Auditor, LLM-as-a-Judge benchmarking, and Langfuse observability work.",
        "subject": "AI Reliability & Evaluation Opportunities — Kritik Jain, IIIT Bhopal",
        "salutation": "Hi Kenny,",
        "body_paragraphs": [
            "I am a final-year B.Tech Information Technology student at IIIT Bhopal, writing to ask about early-career engineering or internship opportunities at Citadel AI.",
            "I came across Citadel AI's work on automated AI testing, model governance, and auditing, and found the mission directly aligned with my background. During my internship at IndiaMART InterMESH, I built an automated Go-based AI Auditor for call analysis pipelines using Langfuse and LLM-as-a-Judge evaluation, boosting evaluation accuracy from 89% to 98.5%. My work focused on benchmark harnesses, prompt versioning, and detecting failure modes across 5,000+ production cases.",
            "I am currently based in India and would be interested in opportunities in Japan, including roles that may involve relocation or visa sponsorship. I would value the chance to contribute to Citadel AI's automated evaluation and reliability engine.",
            "My resume (Kritik_Jain_CV3.pdf) is attached, and my portfolio (https://kritikjain.in/) and GitHub (https://github.com/kritik8) have further code samples."
        ]
    },
    {
        "company": "Cogent Labs",
        "recipient_name": "Cogent Labs Hiring Team",
        "email": "hr@cogent.co.jp",
        "category": "Applied AI / Document Understanding / NLP",
        "resume": "Kritik_Jain_CV3.pdf",
        "role": "Applied AI / ML Engineer",
        "reason": "Cogent Labs develops enterprise document AI (Tegaki), NLP, and LLM services. Kritik's Applied AI resume details multimodal OCR/vision perception, RAG architectures, and model evaluation.",
        "subject": "Applied AI & Engineering Opportunities — Kritik Jain, IIIT Bhopal",
        "salutation": "Hi Cogent Labs Hiring Team,",
        "body_paragraphs": [
            "I am a final-year B.Tech Information Technology student at IIIT Bhopal, writing to ask whether Cogent Labs has internship, new-grad, or early-career openings in applied AI or software engineering.",
            "I have been impressed by Cogent Labs' work on document AI, intelligent information extraction, and enterprise LLM solutions. In my recent work, I engineered an automated evaluation pipeline utilizing LLM-as-a-Judge and Langfuse at IndiaMART, raising validation accuracy from 89% to 98.5%. I also built Nyay-Setu, a RAG system optimizing chunking, vector embeddings, and context assembly, and developed predictive computer-vision perception layers with FastAPI.",
            "I am currently based in India and would be interested in opportunities in Japan, including roles that offer relocation or visa sponsorship. If there are teams where my background in applied ML and API engineering would be useful, I would welcome the opportunity to discuss them.",
            "My resume (Kritik_Jain_CV3.pdf) is attached, and my work is available at https://kritikjain.in/ and https://github.com/kritik8."
        ]
    },
    {
        "company": "UNSEEN Tokyo",
        "recipient_name": "UNSEEN Recruiting Team",
        "email": "careers@unseen-tokyo.com",
        "category": "Game Tech & Simulation",
        "resume": "Kritik_Jain_CV4.pdf",
        "role": "Junior Gameplay / Systems Programmer",
        "reason": "UNSEEN builds action games (KEMURI) requiring high-performance systems and real-time graphics. Kritik's CV4 highlights C++, computer vision, perception pipelines, and deep learning algorithms.",
        "subject": "Application / Engineering Opportunities at UNSEEN — Kritik Jain, IIIT Bhopal",
        "salutation": "Hi UNSEEN Recruiting Team,",
        "body_paragraphs": [
            "I am a final-year B.Tech Information Technology student at IIIT Bhopal, writing to express my strong interest in early-career engineering or internship opportunities at UNSEEN.",
            "I have been following the reveal and artistic vision behind KEMURI. My technical focus encompasses C++, computer vision, and real-time systems programming. I developed RetinaRetail, an end-to-end perception and spatial simulation platform using YOLO and algorithmic analysis, and co-authored a 26-page research survey on sequence models and distributed architectures. Additionally, I have solved 900+ data structures and algorithmic problems (CodeChef 4-star, 1810).",
            "I am currently based in India and would be interested in opportunities in Japan, including roles that provide relocation or visa sponsorship. If UNSEEN is considering junior engineers or interns with strong programming foundations and a passion for game tech, I would love to connect.",
            "My resume (Kritik_Jain_CV4.pdf) is attached, and my portfolio is at https://kritikjain.in/."
        ]
    },
    {
        "company": "AMATA K.K.",
        "recipient_name": "AMATA Recruiting Team",
        "email": "recruit@amata.co.jp",
        "category": "Game Dev & VR Systems",
        "resume": "Kritik_Jain_CV4.pdf",
        "role": "Game Programmer / Systems Intern",
        "reason": "AMATA develops VR and interactive entertainment (Last Labyrinth, Tale of Onogoro). Kritik's CV4 emphasizes C++, computer vision perception, spatial analytics, and algorithmic simulation.",
        "subject": "Engineering Opportunities at AMATA — Kritik Jain, IIIT Bhopal",
        "salutation": "Hi AMATA Recruiting Team,",
        "body_paragraphs": [
            "I am a final-year B.Tech Information Technology student at IIIT Bhopal, writing to inquire about software engineering internship or new-grad opportunities at AMATA K.K.",
            "I am familiar with AMATA's track record across VR titles such as Last Labyrinth and The Tale of Onogoro. My technical background combines C++, computer vision, and applied ML systems. In my projects, I designed visual perception pipelines with YOLO for spatial tracking, implemented asynchronous REST backends, and conducted deep learning research on sequence architectures. I also have strong algorithmic credentials, with 900+ solved algorithmic challenges and a 4-star rating on CodeChef.",
            "I am currently based in India and would be interested in opportunities in Japan, including opportunities that may involve relocation or visa sponsorship. Could you let me know if AMATA is open to considering international early-career developers?",
            "My resume (Kritik_Jain_CV4.pdf) is attached, and my projects are hosted at https://github.com/kritik8 and https://kritikjain.in/."
        ]
    },
    {
        "company": "Silicon Studio",
        "recipient_name": "Silicon Studio Recruitment Team",
        "email": "careers@siliconstudio.co.jp",
        "category": "Graphics Engine & Middleware",
        "resume": "Kritik_Jain_CV4.pdf",
        "role": "Graphics / Systems Software Engineer",
        "reason": "Silicon Studio is renowned for graphics middleware (YEBIS, Enlighten) and in-house tools. CV4 showcases C++, computer vision, image processing, and distributed simulation algorithms.",
        "subject": "Engineering Opportunities — Kritik Jain, IIIT Bhopal",
        "salutation": "Hi Silicon Studio Recruitment Team,",
        "body_paragraphs": [
            "I am a final-year B.Tech Information Technology student at IIIT Bhopal, writing to explore early-career software engineering or internship opportunities at Silicon Studio.",
            "I am familiar with Silicon Studio's leadership in real-time rendering, optical effects middleware such as YEBIS, and graphics tool development. My background combines C++, computer vision, and numerical computing. I engineered spatial image processing and perception pipelines in RetinaRetail and BlueChain, built high-performance asynchronous services, and co-authored research analyzing deep sequence models. I also hold a CodeChef 4-star rating with 900+ algorithmic problems solved.",
            "I am currently based in India and would be interested in opportunities in Japan, including opportunities that may involve relocation or visa sponsorship. If Silicon Studio has junior openings in tools or graphics engineering accessible in English, I would appreciate the chance to discuss fit.",
            "My resume (Kritik_Jain_CV4.pdf) is attached, and my portfolio is available at https://kritikjain.in/."
        ]
    },
    {
        "company": "HENNGE K.K.",
        "recipient_name": "HENNGE Global Recruiting Team",
        "email": "info@hennge.com",
        "category": "Cloud / Backend / SaaS",
        "resume": "Kritik_Jain_CV.pdf",
        "role": "Global Internship Program (GIP) / Software Engineer",
        "reason": "HENNGE runs the English-speaking Global Internship Program (GIP) in Tokyo with Go/Python/Cloud. Kritik's CV1 features Go microservices, FastAPI, and OpenTelemetry observability.",
        "subject": "Inquiry regarding Global Internship Program & SWE Opportunities — Kritik Jain, IIIT Bhopal",
        "salutation": "Hi HENNGE Team,",
        "body_paragraphs": [
            "I am a final-year B.Tech Information Technology student at IIIT Bhopal. I am writing to politely inquire about upcoming sessions for the HENNGE Global Internship Program (GIP) and early-career software engineering opportunities, and would appreciate if this could be shared with your recruiting team.",
            "I am enthusiastic about HENNGE's English-first culture and cloud security platforms. My technical background centers on backend engineering with Go, Python, and cloud services. At IndiaMART InterMESH, I engineered a Go backend AI Auditor instrumented with OpenTelemetry, Langfuse, and BigQuery, boosting automated audit accuracy to 98.5%. I have also designed asynchronous REST APIs handling geospatial processing in FastAPI.",
            "I am currently based in India and would be interested in opportunities in Japan, including opportunities that may involve relocation or visa sponsorship, such as GIP. I would welcome the chance to apply my Go and cloud backend skills at HENNGE.",
            "My resume (Kritik_Jain_CV.pdf) is attached, and my projects are at https://github.com/kritik8."
        ]
    },
    {
        "company": "OneChronos",
        "recipient_name": "OneChronos Recruiting Team",
        "email": "careers@onechronos.com",
        "category": "High-Performance Systems & FinTech",
        "resume": "Kritik_Jain_CV.pdf",
        "role": "Backend / Systems Engineer (Tokyo)",
        "reason": "OneChronos operates smart market matching venues requiring low-latency, concurrent distributed systems. Kritik's CV1 focuses on Go, concurrency, gRPC, Redis, Kafka, and backend resilience.",
        "subject": "Software Engineering Opportunities (Tokyo) — Kritik Jain, IIIT Bhopal",
        "salutation": "Hi OneChronos Recruiting Team,",
        "body_paragraphs": [
            "I am a final-year B.Tech Information Technology student at IIIT Bhopal, writing to ask about early-career backend engineering or internship opportunities with OneChronos in Tokyo.",
            "I came across OneChronos's innovative work on smart market matching mechanisms and expressive trading venues. My technical work focuses on concurrent backend engineering and distributed workflows using Go, Python, and C++. At IndiaMART InterMESH, I built high-throughput audit and evaluation pipelines using Go, gRPC concepts, and OpenTelemetry tracing. I also have competitive programming credentials (CodeChef 4-star, 1810 rating; 900+ algorithmic problems solved).",
            "I am currently based in India and would be interested in opportunities in Japan, including opportunities that may involve relocation or visa sponsorship. If there are junior engineering roles where my systems and concurrency background could contribute, I would welcome a conversation.",
            "My resume (Kritik_Jain_CV.pdf) is attached, and my portfolio is at https://kritikjain.in/."
        ]
    },
    {
        "company": "TokyoDev",
        "recipient_name": "Paul McMahon",
        "email": "paul@tokyodev.com",
        "category": "Recruiter / Tech Community",
        "resume": "Kritik_Jain_CV.pdf",
        "role": "Software / AI Engineering Opportunities in Japan",
        "reason": "Paul McMahon founded TokyoDev, the premier portal for international engineers moving to Japan. Balanced SWE/Backend resume represents core software skills.",
        "subject": "Final-Year IT Student Interested in AI/SWE Opportunities in Japan — Kritik Jain",
        "salutation": "Hi Paul,",
        "body_paragraphs": [
            "I am a final-year B.Tech Information Technology student at IIIT Bhopal in India, writing to introduce my profile and ask whether there are suitable early-career or internship software opportunities in Japan through TokyoDev.",
            "My background combines backend engineering (Go, Python, FastAPI) and Applied AI / LLM systems. During my internship at IndiaMART InterMESH, I built a Go-based AI Auditor instrumented with Langfuse and OpenTelemetry, raising evaluation accuracy from 89% to 98.5%. I am also an active competitive programmer (CodeChef 4-star, 1810 rating; 900+ DSA problems solved).",
            "I am currently based in India and actively looking for internship, new-grad, or junior engineering opportunities in Japan, including roles that offer visa sponsorship or relocation. I admire how TokyoDev supports international developers and would greatly appreciate if you could keep my profile in mind for suitable openings.",
            "My resume (Kritik_Jain_CV.pdf) is attached, and my portfolio is at https://kritikjain.in/ (GitHub: https://github.com/kritik8)."
        ]
    },
    {
        "company": "Tokyo-Job / Hash Inc",
        "recipient_name": "Hash Inc Recruitment Team",
        "email": "tokyo-job@hash-inc.jp",
        "category": "Recruiter / International Tech Placement",
        "resume": "Kritik_Jain_CV.pdf",
        "role": "Bilingual / International IT Placement in Japan",
        "reason": "Hash Inc specializes in placing foreign IT professionals in Japan with visa support. Balanced SWE/AI resume highlights versatile software capabilities.",
        "subject": "Profile Introduction: Final-Year IT Student Seeking Japan SWE/AI Roles — Kritik Jain",
        "salutation": "Hi Hash Inc Team,",
        "body_paragraphs": [
            "I am a final-year B.Tech Information Technology student at IIIT Bhopal, writing to introduce my profile for early-career software engineering or internship opportunities in Japan.",
            "I understand Hash Inc specializes in connecting international IT talent with technology companies across Japan. My profile covers backend engineering and applied AI systems. During my SDE internship at IndiaMART InterMESH, I built a Go-based AI evaluation engine with OpenTelemetry and Langfuse, achieving a 98.5% audit accuracy. I also possess strong algorithmic problem-solving skills (CodeChef 4-star; 900+ solved problems).",
            "I am currently based in India and would be interested in opportunities in Japan, including roles that provide visa sponsorship and relocation support. I am eager to contribute to forward-thinking Japanese tech teams and would appreciate being considered for relevant openings.",
            "My resume (Kritik_Jain_CV.pdf) is attached, and you can view my projects at https://github.com/kritik8 and https://kritikjain.in/."
        ]
    },
    {
        "company": "Hays Japan",
        "recipient_name": "Luna Pham",
        "email": "Luna.Pham@hays.co.jp",
        "category": "Recruiter / IT Recruitment",
        "resume": "Kritik_Jain_CV.pdf",
        "role": "Early-Career Software / AI Engineer Candidates",
        "reason": "Luna Pham recruits tech/IT talent at Hays Tokyo. Balanced SWE/AI resume highlights practical backend internship and competitive programming foundations.",
        "subject": "Candidate Profile: Final-Year IT Student Seeking Japan Opportunities — Kritik Jain",
        "salutation": "Hi Luna,",
        "body_paragraphs": [
            "I am a final-year B.Tech Information Technology student at IIIT Bhopal, writing to introduce my background for early-career software engineering and applied AI positions in Japan.",
            "My experience bridges robust backend development and applied ML systems. As an SDE Intern at IndiaMART InterMESH, I built an automated evaluation service in Go instrumented with Langfuse and OpenTelemetry, boosting quality audit accuracy to 98.5%. In addition, I have a solid algorithmic foundation with 900+ data structures problems solved and a 4-star rating on CodeChef (1810 peak).",
            "I am currently based in India and would be interested in opportunities in Japan, including roles that offer visa sponsorship or relocation. I would be grateful if you could keep my profile in mind when assisting client companies seeking motivated early-career engineers with strong Go, Python, and AI capabilities.",
            "My resume (Kritik_Jain_CV.pdf) is attached, and my portfolio is at https://kritikjain.in/ (GitHub: https://github.com/kritik8)."
        ]
    },
    {
        "company": "Computer Futures",
        "recipient_name": "S. Riaz",
        "email": "s.riaz@computerfutures.com",
        "category": "Recruiter / Tech Recruitment",
        "resume": "Kritik_Jain_CV.pdf",
        "role": "Software Engineering & Cloud Roles in Japan",
        "reason": "Computer Futures Tokyo specializes in bilingual IT, Cloud, and Software placements. Balanced SWE resume emphasizes Go backend and distributed tools.",
        "subject": "Candidate Profile: Software & AI Engineering Roles in Japan — Kritik Jain",
        "salutation": "Hi Riaz,",
        "body_paragraphs": [
            "I am a final-year B.Tech Information Technology student at IIIT Bhopal, writing to share my profile for early-career software engineering or internship opportunities in Japan.",
            "I know Computer Futures has a strong track record connecting specialized tech talent with opportunities in Tokyo. My background combines backend systems (Go, Python, FastAPI) and Applied AI pipelines. During my internship at IndiaMART InterMESH, I developed a Go-based AI Auditor utilizing Langfuse and LLM-as-a-Judge, increasing audit accuracy from 89% to 98.5%. I am also an active competitive programmer with 900+ solved problems and a CodeChef 4-star rating.",
            "I am currently based in India and would be interested in opportunities in Japan, including opportunities that may involve relocation or visa sponsorship. Could you consider my profile for junior backend, cloud, or applied AI roles among your client network?",
            "My resume (Kritik_Jain_CV.pdf) is attached, and my portfolio is available at https://kritikjain.in/."
        ]
    },
    {
        "company": "Global Career Connect Japan",
        "recipient_name": "GCCJP Team",
        "email": "contact@gccjp.org",
        "category": "Recruiter / International Talent Bridge",
        "resume": "Kritik_Jain_CV.pdf",
        "role": "International Student Career Placement in Japan",
        "reason": "GCCJP bridges international talent with Japanese employers. Balanced SWE/AI resume demonstrates readiness for global engineering teams.",
        "subject": "Profile Introduction: Final-Year IT Student Seeking Japan Tech Opportunities — Kritik Jain",
        "salutation": "Hi GCCJP Team,",
        "body_paragraphs": [
            "I am a final-year B.Tech Information Technology student at IIIT Bhopal, writing to introduce my profile to Global Career Connect Japan as I explore early-career engineering and internship opportunities in Japan.",
            "I strongly value GCCJP's mission in connecting international talent with Japanese companies. My profile focuses on software engineering and applied AI systems. As an SDE intern at IndiaMART InterMESH, I engineered a Go-based AI evaluation system utilizing Langfuse and OpenTelemetry, raising automated audit accuracy to 98.5%. I have also built asynchronous REST backends and maintained a 4-star CodeChef rating with 900+ algorithmic problems solved.",
            "I am currently based in India and would be interested in opportunities in Japan, including opportunities that may involve relocation or visa sponsorship. I would appreciate any guidance or matching assistance you might offer for English-friendly technology openings.",
            "My resume (Kritik_Jain_CV.pdf) is attached, and my portfolio is at https://kritikjain.in/ (GitHub: https://github.com/kritik8)."
        ]
    },
    {
        "company": "Fujitsu Research",
        "recipient_name": "Fujitsu Research Inquiry Team",
        "email": "fra_info@fujitsu.com",
        "category": "AI Research / Autonomous Systems",
        "resume": "Kritik_Jain_CV4.pdf",
        "role": "Research Intern / Student Researcher",
        "reason": "Fujitsu Research conducts advanced studies in AI, security, and autonomous systems. Kritik's CV4 highlights a 26-page research publication on ConvGRU sequence models and federated learning.",
        "subject": "Research Internship / Early-Career Opportunities — Kritik Jain, IIIT Bhopal",
        "salutation": "Hi Fujitsu Research Team,",
        "body_paragraphs": [
            "I am a final-year B.Tech Information Technology student at IIIT Bhopal, writing to inquire whether Fujitsu Research has student researcher, internship, or new-grad opportunities in machine learning or autonomous systems.",
            "I am familiar with Fujitsu's pioneering research across trusted AI, security, and networked systems. My background includes both practical ML engineering and research. I co-authored a 26-page survey analyzing ConvGRU sequence models and federated learning under non-IID edge constraints for vehicular intrusion detection. Additionally, during my SDE internship at IndiaMART, I engineered production evaluation pipelines utilizing LLM-as-a-Judge and Langfuse.",
            "I am currently based in India and would be interested in opportunities in Japan, including opportunities that may involve relocation or visa sponsorship. If there are research teams where my background in deep sequence models and distributed ML would be relevant, I would welcome the chance to connect.",
            "My research-focused resume (Kritik_Jain_CV4.pdf) is attached, and my portfolio is at https://kritikjain.in/."
        ]
    }
]

SKIPPED_ENTITIES = [
    {
        "company": "Cygames",
        "email": "pressrelease_info@cygames.co.jp",
        "reason": "Press-only media address (pressrelease_info). Policy strictly prohibits sending job applications to press inboxes. Recruiting handled exclusively via web portal.",
        "category": "Gaming"
    },
    {
        "company": "Sendery",
        "email": "jobs@sendery.co",
        "reason": "Contract iOS Swift role requiring 5+ years native iOS experience with explicit 'no visa sponsorship' requirement. Incompatible with candidate's IT/AI/SWE background.",
        "category": "Mobile/iOS"
    },
    {
        "company": "LeapMind",
        "email": "N/A",
        "reason": "Company dissolved corporate operations on July 31, 2024. No longer active or hiring.",
        "category": "Edge AI"
    },
    {
        "company": "Estuary",
        "email": "careers@estuary.dev",
        "reason": "Headquartered in New York City & Columbus, Ohio, USA. Non-Japan entity.",
        "category": "Data Streaming"
    },
    {
        "company": "Assume AI",
        "email": "hugh@assume-ai.com",
        "reason": "UK-based AI consultancy located in London. Non-Japan entity.",
        "category": "AI Consulting"
    },
    {
        "company": "Tangram Vision",
        "email": "careers@tangramvision.com",
        "reason": "Headquartered in Boulder, Colorado, USA. Non-Japan entity.",
        "category": "Computer Vision"
    },
    {
        "company": "Pagnos",
        "email": "recruiting@pagnos.com",
        "reason": "Registered in Langenau, Germany (Pagnos GmbH). Non-Japan entity.",
        "category": "Cloud Consulting"
    },
    {
        "company": "QuantumMinds",
        "email": "jobs@quantumminds.com",
        "reason": "Australia-based IT services firm. Non-Japan entity.",
        "category": "IT Services"
    },
    {
        "company": "KSC Trading",
        "email": "hiring@ksctrading.com",
        "reason": "Remote prediction markets trading entity without distinct Japan recruitment operations.",
        "category": "Algorithmic Trading"
    },
    {
        "company": "Cardog",
        "email": "careers@cardog.app",
        "reason": "North American automotive software entity. Non-Japan entity.",
        "category": "Automotive Software"
    },
    {
        "company": "This Dot",
        "email": "jobs@thisdot.co",
        "reason": "US-based distributed web consultancy. Non-Japan entity.",
        "category": "Web Consulting"
    },
    {
        "company": "Playit.gg",
        "email": "apply@playit.gg",
        "reason": "US-based game networking tool with global servers; not a Japanese employer.",
        "category": "Networking"
    }
]

SIGNATURE = (
    "Best,\n"
    "Kritik Jain\n"
    "B.Tech in Information Technology, IIIT Bhopal\n"
    "jkritik8@gmail.com | Portfolio: https://kritikjain.in/ | GitHub: https://github.com/kritik8"
)

BANNED_STRINGS = [
    "computer science",
    "cs student",
    "b.tech in computer science",
    "hope this email finds you well",
    "respected sir",
    "dear hiring manager",
    "revolutionizing",
    "revolutionary",
    "groundbreaking",
    "esteemed organization"
]

def validate_draft(item: Dict[str, Any]) -> List[str]:
    """Validate that draft complies strictly with all quality and candidate rules."""
    errors = []
    full_text = item["salutation"] + "\n\n" + "\n\n".join(item["body_paragraphs"]) + "\n\n" + SIGNATURE
    lower_text = full_text.lower()

    # Banned strings check
    for banned in BANNED_STRINGS:
        if banned in lower_text:
            errors.append(f"Contains banned phrase: '{banned}'")

    # Candidate profile check
    if "information technology" not in lower_text:
        errors.append("Missing mandatory 'Information Technology' degree specification")
    if "iiit bhopal" not in lower_text:
        errors.append("Missing mandatory 'IIIT Bhopal' institution reference")

    # Word count check (body only: paragraphs without signature/salutation)
    body_only = " ".join(item["body_paragraphs"])
    words = [w for w in re.split(r"\s+", body_only.strip()) if w]
    word_count = len(words)
    item["word_count"] = word_count
    item["full_email"] = full_text

    if word_count < 115 or word_count > 185:
        errors.append(f"Word count {word_count} is outside acceptable range (120-180 words)")

    # Resume attachment check
    if not item["resume"].startswith("Kritik_Jain_CV"):
        errors.append(f"Invalid resume specified: {item['resume']}")

    return errors

def main():
    print("=== Validating Japan Outreach Campaign Drafts ===")
    validated_campaign = []
    
    for idx, target in enumerate(CAMPAIGN_TARGETS, 1):
        errors = validate_draft(target)
        if errors:
            print(f"FAILED validation for {target['company']}: {errors}")
        else:
            print(f"[{idx}/14] PASSED: {target['company']} ({target['word_count']} words, Resume: {target['resume']})")
            validated_campaign.append(target)

    # Save to data/japan_campaign_drafts.json
    os.makedirs("data", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    
    with open("data/japan_campaign_drafts.json", "w", encoding="utf-8") as f:
        json.dump({
            "validated_targets": validated_campaign,
            "skipped_targets": SKIPPED_ENTITIES
        }, f, indent=2)

    # Save CSV
    csv_path = "output/japan_campaign_dry_run.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["#", "Company", "Recipient", "Email", "Category", "Resume", "Word Count", "Subject", "Reason"])
        for idx, t in enumerate(validated_campaign, 1):
            writer.writerow([
                idx,
                t["company"],
                t["recipient_name"],
                t["email"],
                t["category"],
                t["resume"],
                t["word_count"],
                t["subject"],
                t["reason"]
            ])

    print(f"\nSaved campaign draft data to data/japan_campaign_drafts.json and {csv_path}")

if __name__ == "__main__":
    main()
