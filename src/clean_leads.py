"""Data cleaner and merger for dirty contact CSVs."""
import re
import csv
import os
import pandas as pd
from typing import List, Dict, Tuple, Set

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')

def extract_name_from_email_or_url(email: str, url: str = "") -> str:
    """Infer clean human full name from email prefix, domain, or LinkedIn URL."""
    # Specific known email mappings
    known_email_names = {
        "hjain2@atlassian.com": "Himanshu Jain",
        "phasija@atlassian.com": "Prateek Hasija",
        "aayushar@qti.qualcomm.com": "Aayush Sharma",
        "v-huskhan@microsoft.com": "Hussain Khan",
        "v-kramtenki@microsoft.com": "Kiran Kumar",
        "ashwini.nair@sigmoidanalytics.com": "Ashwini Nair",
        "pavitra.deshpande@sigmoidanalytics.com": "Pavitra Deshpande",
        "aishwarya.g@servicenow.com": "Aishwarya Raj",
        "skathuria1@wayfair.com": "Siddharth Kathuria",
        "uzma.tabassum@walmart.com": "Uzma Tabassum",
        "ksingh@sumologic.com": "Krishna Pratap Singh",
        "shivansh.s@greyorange.com": "Shivansh Srivastava",
        "tanupriya10000@gmail.com": "Tanu Priya",
        "tanu.priya@aisensy.com": "Tanu Priya",
        "mohammed.imranullah@jiostar.com": "Mohammed Imranullah",
        "prerana.venugopalan@airtelbank.com": "Prerana Venugopalan",
        "kanika.pal@airtelbank.com": "Kanika Pal",
        "rbehera@zetainteractive.com": "Raseswaree Chinmayee Behera",
        "sudha.rangavajhula@dpworld.com": "Sudha Rangavajhula",
        "srivastavas@cars24.com": "Siddhant Srivastava",
        "anushka.agarwal@1mg.com": "Anushka Agarwal",
        "amrin.anjum0551@cientra.com": "Amrin Anjum",
        "sherin@deepmostai.com": "Sherin",
        "abhishekc1607@gmail.com": "Abhishek Chourasia",
        "rashmi@seisei.ai": "Rashmi Singh",
        "aditya@qapilot.com": "Aditya Challa",
        "girish@enumerate.ai": "Girish Kumar",
        "neeta@moleculeai.net": "Neeta Singal",
        "bshekar@iitb.ac.in": "Bharath Shekar",
        "saifee@rampp.ai": "Huzefa Saifee"
    }
    if email.lower() in known_email_names:
        return known_email_names[email.lower()]

    if url and "linkedin.com/in/" in url:
        slug = url.split("linkedin.com/in/")[1].split("/")[0].split("?")[0]
        clean_slug = re.sub(r'-[0-9a-fA-F]{6,}$', '', slug)
        clean_slug = re.sub(r'-[0-9]{4,}$', '', clean_slug)
        words = clean_slug.replace('-', ' ').replace('_', ' ').split()
        if words and not any(w in clean_slug.lower() for w in ["activity", "post"]):
            return " ".join(w.capitalize() for w in words if not w.isdigit())

    prefix = email.split('@')[0]
    prefix = re.sub(r'^[vV]-', '', prefix)
    parts = re.split(r'[._-]', prefix)
    parts = [re.sub(r'\d+', '', p).capitalize() for p in parts if re.sub(r'\d+', '', p)]
    if parts:
        return " ".join(parts)
    return "Hiring Team"


def clean_company_name(comp: str, email: str = "") -> str:
    comp = comp.strip()
    if not comp and email:
        domain = email.split('@')[1].split('.')[0]
        comp = domain.capitalize()
    
    # Clean known company name typos
    mapping = {
        "Microsofthyd": "Microsoft",
        "MicrosoftNoida": "Microsoft",
        "Airtel Bank": "Airtel Payments Bank",
        "Cientra": "Cientra",
        "TATA 1MG": "Tata 1mg",
        "JioHotstar": "JioCinema / Disney+ Hotstar",
        "SigMoid": "Sigmoid Analytics",
        "Servicenow": "ServiceNow",
        "SumoLogic": "Sumo Logic",
        "AI Sensy": "AiSensy",
        "Researchify Labs": "Researchify",
        "Actalyst.ai": "Actalyst",
        "DexyAI": "Dexy AI",
        "GoCodeo": "GoCodeo",
        "Deepmost Innovations": "Deepmost AI",
        "SyntX by OrangeCat": "SyntX",
        "Word Works Ai": "Word Works AI"
    }
    return mapping.get(comp, comp)


def parse_hr_email_list(file_path: str) -> List[Dict[str, str]]:
    leads = []
    if not os.path.exists(file_path):
        return leads

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        
        for row in reader:
            if not row or len(row) < 2:
                continue
            company_raw = row[0].strip()
            mail_raw = row[1].strip()
            linkedin_url = row[2].strip() if len(row) > 2 else ""

            # Extract all valid emails in the cell
            found_emails = EMAIL_REGEX.findall(mail_raw)
            if not found_emails:
                continue

            company = clean_company_name(company_raw, found_emails[0])

            for em in found_emails:
                em_clean = em.strip().lower()
                name = extract_name_from_email_or_url(em_clean, linkedin_url)
                
                # Role inference
                role = "Talent Acquisition / HR"
                if "software" in linkedin_url.lower() or "developer" in linkedin_url.lower():
                    role = "Engineering Team"

                leads.append({
                    "name": name,
                    "email": em_clean,
                    "company": company,
                    "role": role,
                    "company_url": "",
                    "linkedin_url": linkedin_url,
                    "job_url": "",
                    "notes": "Outreach to HR / Talent Acquisition contact for tech hiring & internship roles."
                })
    return leads


def parse_founders_list(file_path: str) -> List[Dict[str, str]]:
    leads = []
    if not os.path.exists(file_path):
        return leads

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader, None)

        for row in reader:
            if not row or len(row) < 3:
                continue
            company_raw = row[0].strip()
            founder_raw = row[1].strip()
            mail1_raw = row[2].strip() if len(row) > 2 else ""
            mail2_raw = row[3].strip() if len(row) > 3 else ""

            # Extract emails
            found_emails = []
            found_emails.extend(EMAIL_REGEX.findall(mail1_raw))
            found_emails.extend(EMAIL_REGEX.findall(mail2_raw))

            if not found_emails:
                continue

            # Clean name
            name = founder_raw
            if not name:
                name = extract_name_from_email_or_url(found_emails[0])

            # Select primary email (prefer work domain over free providers if available)
            work_emails = [e for e in found_emails if not any(free in e.lower() for free in ["@gmail.", "@yahoo.", "@hotmail.", "@rediffmail."])]
            selected_email = work_emails[0] if work_emails else found_emails[0]
            selected_email = selected_email.strip().lower()

            # Clean company
            company = clean_company_name(company_raw, selected_email)
            if not company:
                domain = selected_email.split('@')[1].split('.')[0]
                company = domain.capitalize()

            leads.append({
                "name": name,
                "email": selected_email,
                "company": company,
                "role": "Founder / Leadership",
                "company_url": f"https://{selected_email.split('@')[1]}" if not any(free in selected_email for free in ["gmail", "yahoo", "hotmail", "rediff"]) else "",
                "linkedin_url": "",
                "job_url": "",
                "notes": f"Founder outreach at {company} regarding engineering opportunities."
            })
    return leads


def clean_and_merge_all():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    dirty_dir = os.path.join(base_dir, "dirty_data")
    
    hr_file = os.path.join(dirty_dir, "HR Email List  - Sheet1.csv")
    founders_file = os.path.join(dirty_dir, "maild ids - Progress.csv")

    hr_leads = parse_hr_email_list(hr_file)
    founders_leads = parse_founders_list(founders_file)

    all_leads = hr_leads + founders_leads

    # Deduplicate primarily on email
    unique_leads = []
    seen_emails = set()

    for l in all_leads:
        em = l["email"].lower().strip()
        if em not in seen_emails and len(em) > 5 and "." in em:
            seen_emails.add(em)
            unique_leads.append(l)

    output_path = os.path.join(base_dir, "data", "cleaned_leads.csv")
    df = pd.DataFrame(unique_leads)
    df.to_csv(output_path, index=False, encoding="utf-8")
    print(f"Successfully cleaned and unified {len(unique_leads)} leads into {output_path}")
    return output_path

if __name__ == "__main__":
    clean_and_merge_all()
