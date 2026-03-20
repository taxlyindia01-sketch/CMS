"""
Module 3 AI Service
Gemini drafts for:
- Compliance checklists, board resolutions, reminder emails
- Auditor reappointment resolutions (ADT-1)
- Auditor resignation letter + ADT-3 (preoccupied elsewhere)
"""

import httpx
import os
from typing import Dict, Any

# FIX: Removed hardcoded "YOUR_GEMINI_API_KEY" fallback — now empty string
# If not set, call_gemini() returns a placeholder message instead of crashing
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# FIX: Model corrected from gemini-2.5-flash (experimental) → gemini-1.5-flash (stable)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


async def _call_gemini(prompt: str) -> str:
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    async with httpx.AsyncClient(timeout=45.0) as client:
        r = await client.post(f"{GEMINI_ENDPOINT}?key={GEMINI_API_KEY}", json=payload, headers=headers)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]


# ═══════════════════════════════════════════════
# COMPLIANCE DRAFTS
# ═══════════════════════════════════════════════

async def generate_compliance_checklist(reminder: Dict[str, Any], company: Dict[str, Any]) -> str:
    prompt = f"""
You are a Company Secretary at a CA firm. Generate a detailed compliance checklist for:

Compliance: {reminder.get('compliance_name')} ({reminder.get('form_number', '')})
Company: {company.get('company_name')}
CIN: {company.get('cin', 'To be updated')}
Financial Year: {reminder.get('financial_year', 'Current FY')}
Due Date: {reminder.get('due_date')}

Generate a step-by-step compliance checklist including:
1. Pre-requisites and documents required
2. Internal approvals needed (board resolution, if any)
3. Filing steps on MCA/GST/IT portal
4. Post-filing actions (keep acknowledgement, update registers)
5. Common errors to avoid
6. Penalty for non-compliance

Format as a numbered checklist under clear section headings.
Use practical language a CA firm staff member can follow.
"""
    return await _call_gemini(prompt)


async def generate_compliance_board_resolution(reminder: Dict[str, Any], company: Dict[str, Any]) -> str:
    prompt = f"""
You are a Company Secretary. Draft a Board Resolution authorising the filing of:

Form: {reminder.get('form_number', reminder.get('compliance_name'))}
Compliance: {reminder.get('compliance_name')}
Company: {company.get('company_name')}
CIN: {company.get('cin', 'To be updated')}
Financial Year: {reminder.get('financial_year', 'Current FY')}

Draft a complete Board Resolution including:
1. RESOLVED THAT clause authorising filing of {reminder.get('form_number', 'the form')}
2. FURTHER RESOLVED THAT authorising a director/company secretary to sign and file
3. FURTHER RESOLVED THAT ratifying any acts already done in this regard
4. Citation of the relevant section of Companies Act 2013 / applicable law

Output ONLY the resolution text with proper legal formatting.
Number the resolved clauses clearly. No preamble.
"""
    return await _call_gemini(prompt)


async def generate_compliance_reminder_email(reminder: Dict[str, Any], company: Dict[str, Any]) -> str:
    days_left = reminder.get('days_remaining', 'few')
    prompt = f"""
You are a compliance officer at a CA firm. Draft a professional reminder email to the 
management/directors of the company about an upcoming compliance deadline.

Compliance: {reminder.get('compliance_name')} ({reminder.get('form_number', '')})
Company: {company.get('company_name')}
Due Date: {reminder.get('due_date')}
Days Remaining: {days_left}
Statutory Deadline: {reminder.get('statutory_deadline', 'As applicable')}
Penalty: {reminder.get('penalty_info', 'As per Companies Act 2013')}

Draft an email with:
Subject: [URGENT] {reminder.get('compliance_name')} Due — Action Required

Body:
1. Brief mention of the compliance and its importance
2. Due date and days remaining
3. Documents/information needed from management immediately
4. Consequence of non-compliance (penalty)
5. Request for confirmation/availability for filing
6. Professional sign-off from CA firm

Keep it concise, professional, and action-oriented.
"""
    return await _call_gemini(prompt)


# ═══════════════════════════════════════════════
# AUDITOR AI DOCUMENTS
# ═══════════════════════════════════════════════

async def generate_auditor_reappointment_resolution(auditor: Dict[str, Any], company: Dict[str, Any]) -> str:
    prompt = f"""
You are a Company Secretary. Draft a complete Board Resolution and AGM Ordinary Resolution 
for the re-appointment of Statutory Auditor under Section 139 of Companies Act 2013.

Company: {company.get('company_name')}
CIN: {company.get('cin', 'To be updated')}

Auditor Details:
- Firm Name: {auditor.get('firm_name')}
- Partner: {auditor.get('partner_name', 'Partner')}
- Membership No: {auditor.get('membership_number', 'XXXXXX')}
- FRN: {auditor.get('firm_registration', 'XXXXXXXXW')}
- Original Appointment: {auditor.get('appointment_date')}
- Re-appointment for Term: 5 years (subject to ratification at each AGM)

Generate THREE documents:

## DOCUMENT 1: BOARD RESOLUTION (recommending re-appointment)
[Board resolution recommending re-appointment to members at AGM]

---

## DOCUMENT 2: AGM ORDINARY RESOLUTION (actual re-appointment)
[Ordinary Resolution to be passed at AGM for re-appointment for next 5 years]

---

## DOCUMENT 3: AUDITOR CONSENT-CUM-CERTIFICATE (Section 139(1))
[Format of consent letter from auditor to be re-appointed, confirming eligibility under 
Section 141 of Companies Act 2013, limits under Section 141(3)(g), ICAI membership status]

---

Use precise legal language per Companies Act 2013 and ICAI standards.
"""
    return await _call_gemini(prompt)


async def generate_adt3_resignation_draft(auditor: Dict[str, Any], company: Dict[str, Any]) -> str:
    """
    Generate ADT-3 resignation letter.
    Reason: Preoccupied elsewhere and unable to devote requisite time and attention.
    """
    prompt = f"""
You are drafting a formal Auditor Resignation Letter (basis for ADT-3 filing) under 
Section 140(2) of Companies Act 2013 read with Rule 8 of Companies (Audit and Auditors) Rules, 2014.

REASON FOR RESIGNATION: Preoccupied elsewhere and unable to devote requisite time and attention 
to the audit of the company.

Details:
Auditor Firm: {auditor.get('firm_name')}
Partner: {auditor.get('partner_name', 'Partner')}
Membership No: {auditor.get('membership_number', 'XXXXXX')}
FRN: {auditor.get('firm_registration', 'XXXXXXXXW')}
Company: {company.get('company_name')}
CIN: {company.get('cin', 'To be updated')}
Appointed on: {auditor.get('appointment_date')}
Resignation Date: {auditor.get('cessation_date', '[DATE]')}

Generate the following complete documents:

## DOCUMENT 1: RESIGNATION LETTER FROM AUDITOR TO COMPANY
[Formal letter from auditor to Board of Directors resigning from office, citing reason 
as being preoccupied elsewhere. Must state: no dues pending, audit for period up to 
resignation date completed/status, confirmation no other reason exists]

---

## DOCUMENT 2: STATEMENT OF CIRCUMSTANCES (for ADT-3 Form — Section 140(2))
[Detailed statement of circumstances connected with resignation as required for filing 
with MCA in Form ADT-3. Include: no malpractice, no fraud suspected, no disagreement 
with management on accounting policies. State clearly the only reason is preoccupation.]

---

## DOCUMENT 3: BOARD RESOLUTION — TAKING NOTE OF AUDITOR RESIGNATION
[Board Resolution taking note of the resignation and authorising filing of ADT-3 within 
30 days. Also include resolution to appoint replacement auditor at EGM/by members.]

---

## DOCUMENT 4: COVERING LETTER FOR ADT-3 FILING
[Brief covering letter to ROC along with ADT-3 form]

---

## KEY COMPLIANCE NOTES
- ADT-3 must be filed by company within 30 days of receiving resignation
- Auditor must file ADT-3 with ROC within 30 days of resignation
- Penalty for late filing: as per Section 140(3)
- Company must appoint replacement auditor within 30 days of vacancy

Use formal legal language throughout. Ensure all documents are complete and ready to use.
"""
    return await _call_gemini(prompt)


async def generate_auditor_renewal_alert_letter(auditor: Dict[str, Any], company: Dict[str, Any]) -> str:
    prompt = f"""
You are a CA firm compliance officer. Draft a formal reminder/alert letter to the 
management of a company that their statutory auditor's 5-year term is due for renewal.

Company: {company.get('company_name')}
CIN: {company.get('cin', 'To be updated')}
Current Auditor: {auditor.get('firm_name')}
Original Appointment Date: {auditor.get('appointment_date')}
Term End / Renewal Due: {auditor.get('renewal_due_date', 'This AGM')}

Draft:

## ALERT LETTER — AUDITOR TERM RENEWAL DUE

[Formal letter to Board of Directors informing them that the 5-year term of the auditor 
is expiring at the upcoming AGM. Include:
1. Reference to Section 139(2) of Companies Act 2013 (rotation for certain companies)
2. Section 139(1) - maximum one term of 5 consecutive years (for individual auditors)
3. Options available: re-appoint for second term OR appoint new auditor
4. Eligibility check reminder (Section 141)
5. Action required: convene Board meeting to recommend, pass AGM resolution
6. Deadline for action]

---

## CHECKLIST FOR AUDITOR RENEWAL AT AGM
[Step-by-step checklist]

Use formal, professional language.
"""
    return await _call_gemini(prompt)


# ═══════════════════════════════════════════════
# SPECIFIC FORM DRAFTS
# ═══════════════════════════════════════════════

COMPLIANCE_PROMPTS = {
    "MGT-7": """Draft a Board Resolution authorising filing of MGT-7 (Annual Return) and provide 
a complete checklist of information/documents required for preparation of Annual Return 
under Section 92 of Companies Act 2013. Include all registers and records to be annexed.""",

    "AOC-4": """Draft a Board Resolution authorising adoption and filing of Financial Statements 
(Form AOC-4) under Section 137 of Companies Act 2013. Include checklist for documents 
required and steps for board approval and AGM adoption of accounts.""",

    "DIR-3 KYC": """Draft a reminder letter and checklist for DIR-3 KYC compliance. Include 
deadline (30 September each year), documents required (Aadhaar, PAN, email OTP, mobile OTP), 
penalty for non-compliance (₹5,000), and step-by-step filing instructions on MCA portal.""",

    "MSME-1": """Draft a Board Resolution and reminder for filing MSME Form I (Half-yearly return 
of outstanding dues to Micro and Small Enterprises). Include details of which companies 
are required to file, due dates (April 30 and October 31), and documents needed.""",

    "DPT-3": """Draft a Board Resolution and filing checklist for Form DPT-3 (Return of Deposits) 
under Rule 16 of Companies (Acceptance of Deposits) Rules 2014. Include annual due date 
(30 June), outstanding loans to be disclosed, and penalty for non-compliance.""",

    "MGT-14": """Draft a checklist and board resolution for filing MGT-14 (Filing of Resolutions 
with ROC) under Section 117 of Companies Act 2013. Include which resolutions require 
filing, 30-day deadline, and penalty for late filing (₹500/day up to ₹5 lakhs).""",
}


async def generate_specific_compliance_draft(form_number: str, company: Dict[str, Any]) -> str:
    base_prompt = COMPLIANCE_PROMPTS.get(form_number, f"""
Draft a compliance checklist and board resolution for {form_number} filing.
Include applicable section of Companies Act / relevant law, due date, and penalty.
""")
    full_prompt = f"""
You are a Company Secretary at a CA firm.
Company: {company.get('company_name')}
CIN: {company.get('cin', 'To be updated')}

{base_prompt}

Format with clear section headings. Use formal legal language.
"""
    return await _call_gemini(full_prompt)
