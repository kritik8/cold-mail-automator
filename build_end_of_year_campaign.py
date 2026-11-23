import os
import re
import csv
import socket
import concurrent.futures
import pandas as pd

SOURCE_CSV = "Company_Emails_Extracted.csv"
OUTPUT_CSV = "end_of_year_campaign.csv"
DATA_OUTPUT_CSV = os.path.join("data", "end_of_year_campaign.csv")

print(f"Reading source file: {SOURCE_CSV}...")
df_source = pd.read_csv(SOURCE_CSV)

# 1. Unroll rows into individual lead records
raw_leads = []
for idx, r in df_source.iterrows():
    c_name = str(r['Company Name']).strip()
    c_detail = str(r['Company Detail']).strip() if pd.notna(r['Company Detail']) else 'IT Services & Software Engineering'
    
    for j in range(1, 18):
        val = r.get(f'Mail ID {j}')
        if pd.notna(val) and '@' in str(val):
            raw_email = str(val).strip().lower()
            domain = raw_email.split('@')[-1] if '@' in raw_email else ''
            raw_leads.append({
                'source_row': idx + 1,
                'company': c_name,
                'detail': c_detail,
                'email': raw_email,
                'domain': domain
            })

print(f"Total extracted email records: {len(raw_leads)}")

# 2. Fast DNS Resolution check for all unique domains
unique_domains = list({l['domain'] for l in raw_leads if l['domain']})
socket.setdefaulttimeout(2.0)

def check_domain_dns(d):
    if not d or '.' not in d:
        return (d, False)
    try:
        socket.gethostbyname(d)
        return (d, True)
    except Exception:
        return (d, False)

print(f"Verifying DNS for {len(unique_domains)} unique domains...")
domain_resolves = {}
with concurrent.futures.ThreadPoolExecutor(max_workers=40) as executor:
    for d, ok in executor.map(check_domain_dns, unique_domains):
        domain_resolves[d] = ok

# 3. Classify Target vs Exclude
def evaluate_lead(lead):
    email = lead['email']
    domain = lead['domain']
    company = lead['company']
    dns_ok = domain_resolves.get(domain, False)

    # 1. DNS Failure
    if not dns_ok:
        return ('DO NOT TARGET', 'Dead / Unresolvable Domain (DNS resolution failed)')
    
    # 2. Defunct email providers
    if 'indiatimes.com' in domain:
        return ('DO NOT TARGET', 'Defunct Provider (Indiatimes Mail shut down)')
    if 'vsnl.com' in domain or 'vsnl.net.in' in domain or 'vsnl.co' in domain:
        return ('DO NOT TARGET', 'Legacy VSNL dial-up relay (High bounce risk / obsolete)')
    if domain.endswith('.ac.in') or domain.endswith('.edu') or domain.endswith('.edu.in'):
        return ('DO NOT TARGET', 'Academic Institution (College domain - not corporate)')
    if 'yahoo.com.uk' in domain:
        return ('DO NOT TARGET', 'Malformed Domain (Invalid TLD .com.uk)')
    
    # 3. Agency free webmail
    if company.lower() in ['independent/agency', 'independent / agency'] and domain in ['gmail.com', 'yahoo.com', 'yahoo.co.in', 'hotmail.com', 'rediffmail.com']:
        return ('DO NOT TARGET', 'Free Webmail Agency (Excluded to focus on direct tech employers)')
    
    # 4. Valid Corporate Target
    return ('TARGET', 'Active Corporate Domain - High Credibility Tech/Consulting')

for l in raw_leads:
    dec, reason = evaluate_lead(l)
    l['decision'] = dec
    l['reason'] = reason

target_leads = [l for l in raw_leads if l['decision'] == 'TARGET']
exclude_leads = [l for l in raw_leads if l['decision'] == 'DO NOT TARGET']

print(f"Target Leads: {len(target_leads)}")
print(f"Excluded Leads: {len(exclude_leads)}")

# 4. Name Parser & Role Selection
def parse_contact_info(email, company):
    local = email.split('@')[0]
    generic_roles = ['hr', 'careers', 'career', 'jobs', 'recruitment', 'talent', 'admin', 'info', 'apply', 'support', 'contact', 'resume', 'cv', 'office', 'inquiries', 'sales', 'amat_gcp', 'amind_hr', 'dreamcareers', 'apply-here', 'adrecruit']
    
    if any(local == g or local.startswith(g + '.') or local.startswith(g + '_') or local.endswith('_hr') or local.endswith('_careers') or local == 'hrd' for g in generic_roles):
        return ('', '', 'Generic inbox')

    cleaned = re.sub(r'[0-9_\-\.]+', ' ', local).strip()
    parts = cleaned.split()
    
    if len(parts) >= 2:
        fn = parts[0].capitalize()
        ln = parts[-1].capitalize()
        if len(fn) == 1 and len(parts) > 1 and len(parts[1]) > 1:
            fn = parts[1].capitalize()
        return (f"{fn} {ln}", fn, 'Personal')
    elif len(parts) == 1 and len(parts[0]) >= 3:
        fn = parts[0].capitalize()
        return (fn, fn, 'Personal')
    else:
        return ('', '', 'Generic inbox')

# Select Target Role & Best-Fit Resume based on company and detail
def select_role_and_resume(company, detail):
    text = (company + " " + detail).lower()
    if any(k in text for k in ['ai', 'intelligence', 'machine learning', 'analytics', 'data', 'deep learning', 'llm', 'nlp', 'synopsys']):
        return ('AI / ML Engineering Intern', 'Kritik_Jain_CV3.pdf', 'AI/ML systems, FastAPI, and automated LLM evaluation')
    elif any(k in text for k in ['cisco', 'embedded', 'hardware', 'semiconductor', 'network', 'security', 'c++', 'amat', 'intel']):
        return ('Systems & Software Engineering Intern', 'Kritik_Jain_CV4.pdf', 'high-performance backend services, C++, and Dockerized infrastructure')
    elif any(k in text for k in ['web', 'cloud', 'platform', 'saas', 'fullstack', 'react']):
        return ('Full-Stack / Software Engineering Intern', 'Kritik_Jain_CV2.pdf', 'scalable backend services, React, and cloud-native APIs')
    else:
        return ('Software Engineering Intern', 'Kritik_Jain_CV.pdf', 'scalable backend services, high-throughput APIs (Go, Python), and microservices')

# Build First-Touch Email Body (under 120 words, strictly IT student, no CS)
def build_first_touch_email(salutation, company, role_title, strength_focus, detail, variant_idx):
    signoff = "Warm regards,\nKritik Jain\n[GitHub](https://github.com/kritik8) | [LinkedIn](https://www.linkedin.com/in/kritik-jain-064350356/) | [Portfolio](https://kritikjain.in/)"
    
    v = variant_idx % 3
    if v == 0:
        return (
            f"{salutation}\n\n"
            f"I have attached my resume for your reference as I'm actively seeking {role_title.lower()} opportunities.\n\n"
            f"I came across {company}'s work and was impressed by your engineering focus in {detail[:50].strip()}.\n\n"
            f"I'm a final-year B.Tech Information Technology student at IIIT Bhopal specializing in {strength_focus}. At IndiaMART, I built an automated Go evaluation service with OpenTelemetry and BigQuery, boosting audit accuracy to 98.5%. I also hold a 4-star CodeChef rating (1810 peak).\n\n"
            f"Could you let me know if {company} has any upcoming internship or early-career engineering openings?\n\n"
            f"{signoff}"
        )
    elif v == 1:
        return (
            f"{salutation}\n\n"
            f"I have attached my resume for your reference as I'm actively seeking {role_title.lower()} opportunities.\n\n"
            f"I've been following {company}'s technology footprint and appreciate your focus on building resilient software solutions.\n\n"
            f"As a final-year B.Tech Information Technology student at IIIT Bhopal, my background centers on {strength_focus}. During my SDE internship at IndiaMART, I developed high-throughput backend services and audit pipelines, achieving 98.5% precision. I have also solved 900+ algorithmic problems.\n\n"
            f"Would you have bandwidth for a brief conversation regarding potential engineering opportunities at {company}?\n\n"
            f"{signoff}"
        )
    else:
        return (
            f"{salutation}\n\n"
            f"I have attached my resume for your reference as I'm actively seeking {role_title.lower()} opportunities.\n\n"
            f"I admire {company}'s work in delivering scalable enterprise and technology platforms.\n\n"
            f"I am a final-year B.Tech Information Technology student at IIIT Bhopal with hands-on experience in {strength_focus}. At IndiaMART, I designed automated backend evaluation services that reduced operational turnaround significantly. I also hold a peak rating of 1810 on CodeChef.\n\n"
            f"Are there any upcoming early-career or internship openings on your engineering team where I could contribute?\n\n"
            f"{signoff}"
        )

# Build Follow-Up Email Body (2-3 lines, polite, under 60 words)
def build_followup_body(salutation, company, role_title, variant_idx):
    signoff = "Warm regards,\nKritik Jain\n[GitHub](https://github.com/kritik8) | [LinkedIn](https://www.linkedin.com/in/kritik-jain-064350356/) | [Portfolio](https://kritikjain.in/)"
    
    v = variant_idx % 3
    if v == 0:
        return (
            f"{salutation}\n\n"
            f"I wanted to quickly follow up on my note from last week regarding potential {role_title.lower()} opportunities at {company}.\n\n"
            f"I would welcome the opportunity to connect briefly or share any additional details about my background if you have upcoming requirements. My resume remains attached for your review.\n\n"
            f"{signoff}"
        )
    elif v == 1:
        return (
            f"{salutation}\n\n"
            f"Following up briefly on my earlier email regarding engineering internship or early-career opportunities at {company}.\n\n"
            f"Please let me know if there might be an opening or team where my skill set could add value. Thanks again for your time and consideration!\n\n"
            f"{signoff}"
        )
    else:
        return (
            f"{salutation}\n\n"
            f"Checking in briefly regarding my note from last week exploring {role_title.lower()} openings at {company}.\n\n"
            f"I'd love to learn if your engineering team is considering candidates for upcoming roles. Thank you for reviewing my background!\n\n"
            f"{signoff}"
        )

# 5. Batch & Schedule Construction
# Schedule starts 2026-11-23 (Monday)
# Daily first-touch limit = 20 mails/day
# Weekdays only (Mon-Fri), strictly no sending on Sat-Sun
business_calendar = [
    ('Day 01', '2026-11-23', '2026-11-26'), # Mon 23 Nov -> Follow-up Thu 26 Nov
    ('Day 02', '2026-11-24', '2026-11-27'), # Tue 24 Nov -> Follow-up Fri 27 Nov
    ('Day 03', '2026-11-25', '2026-11-30'), # Wed 25 Nov -> Follow-up Mon 30 Nov (skips weekend 28-29)
    ('Day 04', '2026-11-26', '2026-12-01'), # Thu 26 Nov -> Follow-up Tue 01 Dec
    ('Day 05', '2026-11-27', '2026-12-02'), # Fri 27 Nov -> Follow-up Wed 02 Dec
    ('Day 06', '2026-11-30', '2026-12-03'), # Mon 30 Nov -> Follow-up Thu 03 Dec (skips weekend 28-29)
    ('Day 07', '2026-12-01', '2026-12-04'), # Tue 01 Dec -> Follow-up Fri 04 Dec
    ('Day 08', '2026-12-02', '2026-12-07'), # Wed 02 Dec -> Follow-up Mon 07 Dec (skips weekend 05-06)
    ('Day 09', '2026-12-03', '2026-12-08'), # Thu 03 Dec -> Follow-up Tue 08 Dec
    ('Day 10', '2026-12-04', '2026-12-09'), # Fri 04 Dec -> Follow-up Wed 09 Dec
    ('Day 11', '2026-12-07', '2026-12-10'), # Mon 07 Dec -> Follow-up Thu 10 Dec (skips weekend 05-06)
]

# Assign batches to target leads (20 per batch)
final_rows = []
batch_size = 20

for i, lead in enumerate(target_leads):
    batch_idx = i // batch_size
    batch_day, sched_date, fu_due_date = business_calendar[batch_idx]
    
    recip_name, first_name, email_type = parse_contact_info(lead['email'], lead['company'])
    salutation = "Hi Team," if email_type == 'Generic inbox' or not first_name else f"Hi {first_name},"
    role_title, resume_pdf, strength = select_role_and_resume(lead['company'], lead['detail'])
    
    subject = f"{role_title} Opportunities at {lead['company']} — Kritik Jain"
    body = build_first_touch_email(salutation, lead['company'], role_title, strength, lead['detail'], i)
    fu_subject = f"Re: {subject}"
    fu_body = build_followup_body(salutation, lead['company'], role_title, i)
    
    final_rows.append({
        'Index': len(final_rows) + 1,
        'Decision': 'TARGET',
        'Audit Reason': lead['reason'],
        'Batch / Day': batch_day,
        'Scheduled Date': sched_date,
        'Follow-up 1 Due Date': fu_due_date,
        'Company': lead['company'],
        'Company Detail': lead['detail'],
        'Domain': lead['domain'],
        'Recipient Email': lead['email'],
        'Recipient Name': recip_name,
        'First Name': first_name,
        'Email Type': email_type,
        'Target Role': role_title,
        'Selected Resume': resume_pdf,
        'Custom Subject': subject,
        'Email Body': body,
        'Status': 'GENERATED',
        'Sent At': '',
        'Follow-up 1 Subject': fu_subject,
        'Follow-up 1 Body': fu_body,
        'Follow-up 1 Status': 'PENDING',
        'Follow-up 1 Sent At': '',
        'Replied': '',
        'Bounced': '',
        'Unsubscribed': '',
        'Notes': ''
    })

# Append Excluded leads
for lead in exclude_leads:
    recip_name, first_name, email_type = parse_contact_info(lead['email'], lead['company'])
    final_rows.append({
        'Index': len(final_rows) + 1,
        'Decision': 'DO NOT TARGET',
        'Audit Reason': lead['reason'],
        'Batch / Day': 'N/A',
        'Scheduled Date': 'N/A',
        'Follow-up 1 Due Date': 'N/A',
        'Company': lead['company'],
        'Company Detail': lead['detail'],
        'Domain': lead['domain'],
        'Recipient Email': lead['email'],
        'Recipient Name': recip_name,
        'First Name': first_name,
        'Email Type': email_type,
        'Target Role': 'N/A',
        'Selected Resume': 'N/A',
        'Custom Subject': 'N/A',
        'Email Body': 'N/A',
        'Status': 'EXCLUDED',
        'Sent At': '',
        'Follow-up 1 Subject': 'N/A',
        'Follow-up 1 Body': 'N/A',
        'Follow-up 1 Status': 'EXCLUDED',
        'Follow-up 1 Sent At': '',
        'Replied': '',
        'Bounced': '',
        'Unsubscribed': '',
        'Notes': lead['reason']
    })

fieldnames = list(final_rows[0].keys())

# Save to root and to data/
for out_path in [OUTPUT_CSV, DATA_OUTPUT_CSV]:
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    with open(out_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(final_rows)
    print(f"Saved {len(final_rows)} rows to {out_path}")

# Verification stats
df_final = pd.DataFrame(final_rows)
print("\n=== Final Campaign Verification ===")
print("Decision breakdown:")
print(df_final['Decision'].value_counts())
print("\nTarget Leads per Day:")
print(df_final[df_final['Decision'] == 'TARGET']['Batch / Day'].value_counts().sort_index())
print("\nTarget Leads per Scheduled Date:")
print(df_final[df_final['Decision'] == 'TARGET']['Scheduled Date'].value_counts().sort_index())
print("\nResume Selection breakdown:")
print(df_final[df_final['Decision'] == 'TARGET']['Selected Resume'].value_counts())
