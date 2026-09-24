# Cold Mail Automator

A clean, intentionally simple, local Python application for personalized internship and job cold-email outreach built specifically for **Kritik Jain**.

---

## 🚀 Key Features

- **High-Conviction Personalization (Ankur Tyagi Framework)**:
  - 3–5 sentences (60–120 words).
  - Starts with relevant context/hook about the company or product.
  - Connects ONE or TWO concrete technical proof points from your background.
  - Ends with a natural, low-friction ask.
  - Strictly avoids corporate fluff and robotic AI clichés (*"hope this finds you well"*, *"esteemed organization"*, *"passionate individual"*, etc.).
- **Smart Resume Selection**:
  - Dynamically inspects lead context (company, role, JD, tech stack, notes) and automatically matches the most relevant resume (`resume_1.pdf` for AI/ML, `resume_2.pdf` for Backend/Distributed Systems, `resume_3.pdf` for Full-Stack/Product).
  - Attaches exactly ONE resume with a clean professional name (`Kritik_Jain_Resume.pdf`).
- **Safety & Human-in-the-Loop Review**:
  - Generates drafts first for terminal review before sending anything.
  - Interactive terminal review tool (`python main.py review`) to approve, reject, edit subject/body, or skip.
  - Duplicate detection across batches and historic sends (`data/send_history.json`).
  - Global blacklist (`data/do_not_contact.txt`).
  - Conservative pacing delays (30s–90s randomized) and maximum email limits per run.
- **LiteLLM Powered**:
  - Compatible with any model (Gemini, OpenAI GPT-4o, Claude 3.5 Sonnet, Groq, etc.).
  - Automatic Mock LLM fallback for testing without consuming API credits.

---

## 📁 Project Structure

```
cold-mail-automator/
├── main.py                     # CLI Entrypoint
├── requirements.txt            # Python dependencies
├── .env.example                # Configuration template
├── README.md                   # Documentation
│
├── config/
│   ├── profile.json            # Kritik's public profile, links, and signature
│   └── resumes.json            # Parsed & structured resume intelligence
│
├── resumes/
│   ├── resume_1.pdf            # AI / ML & LLM Engineering resume
│   ├── resume_2.pdf            # Backend & Distributed Systems resume
│   └── resume_3.pdf            # Full-Stack & Software Engineering resume
│
├── data/
│   ├── leads_sample.csv        # Sample leads CSV
│   ├── do_not_contact.txt      # Blacklisted emails
│   └── send_history.json       # Record of sent emails (deduplication)
│
├── output/
│   ├── generated_emails.csv    # Drafts with status (GENERATED/APPROVED/SENT)
│   └── generated_emails.json   # Full JSON structured drafts
│
├── logs/
│   └── app.log                 # Execution logs (passwords/keys redacted)
│
└── src/
    ├── config.py               # Settings loader
    ├── csv_loader.py           # CSV/XLSX parser & normalizer
    ├── pdf_parser.py           # PDF text extractor & resume profiler
    ├── company_research.py     # Public website text scraper
    ├── llm.py                  # LiteLLM client & mock generator
    ├── resume_selector.py      # Lead-to-resume matching engine
    ├── email_generator.py      # Cold outreach copywriter engine
    ├── quality_checker.py      # Automated tone & constraint gatekeeper
    ├── reviewer.py             # Interactive CLI review interface
    ├── smtp_sender.py          # SMTP TLS sender with attachments
    ├── storage.py              # Persistence & history tracking
    └── logger.py               # Credential-masked logging
```

---

## 🛠️ Quickstart & Setup

### 1. Requirements
- Python 3.10, 3.11, or 3.12

### 2. Installation
Install the dependencies:
```bash
pip install -r requirements.txt
```

### 3. Setup Environment Variables
Copy `.env.example` to `.env`:
```bash
copy .env.example .env
```
Edit `.env` with your preferred LLM and SMTP credentials:
```ini
# LLM Provider
GEMINI_API_KEY=AIzaSy...
LLM_MODEL=gemini/gemini-1.5-flash

# For OpenAI:
# OPENAI_API_KEY=sk-...
# LLM_MODEL=openai/gpt-4o-mini

# SMTP Settings (Gmail Example)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=jkritik8@gmail.com
SMTP_PASSWORD=your_16_char_google_app_password
SMTP_USE_TLS=true
TEST_EMAIL=jkritik8@gmail.com

# Conservative Sending Rate
MIN_DELAY_SECONDS=30
MAX_DELAY_SECONDS=90
MAX_EMAILS_PER_RUN=100
```
> **Note**: For Gmail, use an **App Password** (Google Account → Security → 2-Step Verification → App passwords).

### 4. Provide Your 3 Resumes
Place your 3 PDF resumes in the `resumes/` folder:
- `resumes/resume_1.pdf` (e.g. AI / ML focus)
- `resumes/resume_2.pdf` (e.g. Backend & Systems focus)
- `resumes/resume_3.pdf` (e.g. Full-Stack / Product focus)

To inspect and verify how the tool analyzes your resumes:
```bash
python main.py analyze-resumes
```

---

## 📋 Standard Workflow

### Step 1: Prepare Leads File (`.csv` or `.xlsx`)
Create or export your contacts CSV/Excel file.

**Supported Columns** (only `name`, `email`, and `company` are mandatory):
```csv
name,email,company,role,company_url,linkedin_url,job_url,notes
Rahul Sharma,rahul@xyz.ai,XYZ AI,Founder,https://xyz.ai,,,Building AI coding agents
Priya Mehta,priya@scaleinfra.io,ScaleInfra,Engineering Manager,https://scaleinfra.io,,,Distributed systems in Go
```

### Step 2: Generate Personalized Drafts
```bash
python main.py generate data/leads_sample.csv
```
This will:
1. Deduplicate and filter out blacklisted/already-sent contacts.
2. Fetch clean public context from `company_url` or `job_url` if provided.
3. Select the best resume with rationale.
4. Craft a personalized 3–5 sentence cold email + 3 subject line options.
5. Run the automated quality control check.
6. Save all drafts to `output/generated_emails.csv` and `output/generated_emails.json`.

### Step 3: Interactive Review & Approval
```bash
python main.py review
```
Interactive terminal interface to inspect each draft:
- Press `a` to **Approve** (mark ready to send).
- Press `r` to **Reject**.
- Press `e` to **Edit** the subject or body directly in the terminal.
- Press `s` to **Skip** (remain pending).
- Press `q` to **Quit** (progress is auto-saved).

To re-review all drafts including previously approved ones:
```bash
python main.py review --all
```

### Step 4: Test SMTP Connection
Before sending to external leads, send a test email to yourself:
```bash
python main.py test-email
```
This verifies your SMTP credentials, TLS connection, and PDF attachment delivery.

### Step 5: Send Approved Emails
```bash
python main.py send
```
- Only sends drafts with `status == APPROVED`.
- Never resends to contacts already present in `data/send_history.json`.
- Applies randomized delays (`30s–90s`) between emails.
- Updates statuses in `output/generated_emails.csv` and logs events in `logs/app.log`.

### Step 6: Check Campaign Status
```bash
python main.py status
```
Shows a breakdown of generated, approved, sent, and failed emails.

---

## 🛡️ Safety & Blacklisting

To prevent reaching out to specific emails or domains:
Add them to `data/do_not_contact.txt` (one email per line).
Any lead in this file will automatically be skipped during generation and sending.

---

## 🧪 Running Tests

Run the test suite:
```bash
pytest -v
```
All unit tests verify:
- Lead normalization & email validation
- Resume matching algorithms
- Tone and cliché detection heuristics
- Blacklist & duplicate protection
- MIME attachment encoding
