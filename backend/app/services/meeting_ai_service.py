"""
Meeting & Post-Incorporation AI Drafts
Extensions to gemini_service.py for meeting documents
"""

import httpx
import os
from typing import Dict, Any, List

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
        response = await client.post(
            f"{GEMINI_ENDPOINT}?key={GEMINI_API_KEY}",
            json=payload, headers=headers
        )
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


# ─────────────────────────────────────────────
# MEETING NOTICE DRAFTS
# ─────────────────────────────────────────────

async def generate_board_meeting_notice(meeting_data: Dict[str, Any], company_data: Dict[str, Any]) -> str:
    agenda_str = "\n".join([f"  {i+1}. {item}" for i, item in enumerate(meeting_data.get("agenda_items", []))])
    prompt = f"""
You are a Company Secretary drafting a formal Board Meeting Notice under Companies Act 2013.

Company: {company_data.get("company_name")}
CIN: {company_data.get("cin", "To be updated")}
Registered Office: {company_data.get("registered_office_address", "As per records")}

Meeting Details:
- Meeting Type: {meeting_data.get("meeting_type")}
- Meeting Number: {meeting_data.get("meeting_number", "To be determined")}
- Date: {meeting_data.get("meeting_date")}
- Time: {meeting_data.get("meeting_time", "11:00 AM")}
- Venue: {meeting_data.get("venue", "Registered Office")}
- Notice Period: {meeting_data.get("notice_period_days", 7)} days

Agenda Items:
{agenda_str if agenda_str else "  1. To take note of routine business matters"}

Draft a complete, legally compliant meeting notice including:
1. Header with company name and CIN
2. Formal notice opening citing Section 173 of Companies Act 2013
3. Numbered agenda items
4. Note about attendance in person or through video conferencing
5. Company Secretary signature block
6. Enclosures: attendance slip, proxy form (for AGM/EGM)

Format professionally with proper legal language.
"""
    return await _call_gemini(prompt)


async def generate_agm_notice(meeting_data: Dict[str, Any], company_data: Dict[str, Any]) -> str:
    agenda_str = "\n".join([f"  {i+1}. {item}" for i, item in enumerate(meeting_data.get("agenda_items", []))])
    default_agm_agenda = ("  1. Adoption of Financial Statements\n"
                          "  2. Appointment/Re-appointment of Directors\n"
                          "  3. Appointment of Auditors and fix their remuneration\n"
                          "  4. Declaration of Dividend (if any)")
    prompt = f"""
You are a Company Secretary drafting a formal Annual General Meeting (AGM) Notice under Companies Act 2013.

Company: {company_data.get("company_name")}
CIN: {company_data.get("cin", "To be updated")}
Registered Office: {company_data.get("registered_office_address", "As per records")}

Meeting Details:
- Financial Year: {company_data.get("last_agm_financial_year", "2023-24")}
- Date: {meeting_data.get("meeting_date")}
- Time: {meeting_data.get("meeting_time", "11:00 AM")}
- Venue: {meeting_data.get("venue", "Registered Office")}

Agenda Items:
{agenda_str if agenda_str else default_agm_agenda}

Draft a complete AGM notice including:
1. Header and company details
2. Citation of Section 96 of Companies Act 2013 and relevant rules
3. Ordinary business items (adoption of accounts, director re-appointment, auditor appointment)
4. Special business items (if any) with explanatory statement under Section 102
5. Notice period statement (21 clear days)
6. E-voting instructions
7. Attendance slip and proxy form instructions (Section 105)
8. Company Secretary signature and date

Use formal legal language as required for AGM notices.
"""
    return await _call_gemini(prompt)


async def generate_egm_notice(meeting_data: Dict[str, Any], company_data: Dict[str, Any]) -> str:
    agenda_str = "\n".join([f"  {i+1}. {item}" for i, item in enumerate(meeting_data.get("agenda_items", []))])
    prompt = f"""
You are a Company Secretary drafting an Extraordinary General Meeting (EGM) Notice under Companies Act 2013.

Company: {company_data.get("company_name")}
CIN: {company_data.get("cin", "To be updated")}

Meeting Details:
- Date: {meeting_data.get("meeting_date")}
- Time: {meeting_data.get("meeting_time", "11:00 AM")}
- Venue: {meeting_data.get("venue", "Registered Office")}

Special Business / Agenda:
{agenda_str if agenda_str else "  1. To pass Special Resolution for amendment of Articles of Association"}

Draft a complete EGM Notice including:
1. Header with company details
2. Cite Section 100 of Companies Act 2013
3. Special business with full explanatory statement under Section 102
4. Nature of resolution (Ordinary/Special) for each item
5. Director/Board interest disclosure (Section 102(2))
6. E-voting details if applicable
7. Shorter notice consent provisions
8. Company Secretary signature block

Use precise legal language appropriate for EGM notices.
"""
    return await _call_gemini(prompt)


# ─────────────────────────────────────────────
# MINUTES DRAFTS
# ─────────────────────────────────────────────

async def generate_meeting_minutes(meeting_data: Dict[str, Any], company_data: Dict[str, Any], resolutions: List[str]) -> str:
    agenda_str = "\n".join([f"  {i+1}. {item}" for i, item in enumerate(meeting_data.get("agenda_items", []))])
    resolution_str = "\n".join([f"  - {r}" for r in resolutions]) if resolutions else "  - Routine business matters"
    attendees_str = ""
    if meeting_data.get("attendees"):
        attendees_str = "\n".join([f"  {a.get('name','Unknown')} {'(Present)' if a.get('present') else '(Absent/LOA)'}" for a in meeting_data["attendees"]])
    else:
        attendees_str = "  All directors present"

    prompt = f"""
You are a Company Secretary drafting formal {meeting_data.get("meeting_type")} Minutes under Companies Act 2013 and Secretarial Standards SS-1/SS-2.

Company: {company_data.get("company_name")}
CIN: {company_data.get("cin", "To be updated")}

Meeting Details:
- Type: {meeting_data.get("meeting_type")}
- Number: {meeting_data.get("meeting_number", "")}
- Date: {meeting_data.get("meeting_date")}
- Time: {meeting_data.get("meeting_time", "11:00 AM")}
- Venue: {meeting_data.get("venue", "Registered Office")}
- Chairman: {meeting_data.get("chairman", "Director")}
- Quorum: {meeting_data.get("quorum_present", "As required")} present out of {meeting_data.get("quorum_required", "required")}

Attendees:
{attendees_str}

Agenda Discussed:
{agenda_str if agenda_str else "  1. Routine business matters"}

Resolutions Passed:
{resolution_str}

Draft complete, compliant meeting minutes including:
1. Commencement — date, time, venue, chairman declaration
2. Attendance register note and quorum confirmation
3. Leave of absence (if any)
4. Reading and confirmation of previous meeting minutes
5. Agenda-wise discussion — each item discussed, decided
6. Resolution text for each resolution passed (numbered properly)
7. Any other business with permission of Chair
8. Conclusion — time of adjournment
9. Signature block for Chairman (to be signed at next meeting)

Follow Secretarial Standard SS-1 for Board and SS-2 for general meetings.
Use proper resolution numbering: BR-XXX/YYYY for board, OR/SR for general meetings.
"""
    return await _call_gemini(prompt)


# ─────────────────────────────────────────────
# RESOLUTION DRAFTS
# ─────────────────────────────────────────────

async def generate_resolution_draft(subject: str, resolution_type: str, company_data: Dict[str, Any]) -> str:
    prompt = f"""
You are a Company Secretary. Draft a formal {resolution_type} for:

Subject: {subject}
Company: {company_data.get("company_name")}
CIN: {company_data.get("cin", "To be updated")}

Draft the complete resolution text including:
1. "RESOLVED THAT" clause — clear and legally precise
2. "FURTHER RESOLVED THAT" clauses for authorisation and consequential actions
3. Where applicable: cite the relevant section of Companies Act 2013
4. Authorisation clause for filing, signing documents, MCA portal etc.

For Board Resolutions: Format as per Secretarial Standard SS-1
For Ordinary/Special Resolutions: Format as per SS-2 with explanatory statement

Output ONLY the resolution text — no preamble or explanation.
"""
    return await _call_gemini(prompt)


# ─────────────────────────────────────────────
# POST-INCORPORATION ALERT DRAFTS
# ─────────────────────────────────────────────

async def generate_inc20a_draft(company_data: Dict[str, Any]) -> str:
    prompt = f"""
You are a Company Secretary. Draft a Board Resolution and checklist for filing INC-20A 
(Declaration for Commencement of Business) under Section 10A of Companies Act 2013.

Company: {company_data.get("company_name")}
CIN: {company_data.get("cin", "To be updated")}
Date of Incorporation: {company_data.get("date_of_incorporation", "As per records")}
Paid-up Capital: ₹{company_data.get("paidup_capital", "As per records")}

Generate:

## BOARD RESOLUTION FOR INC-20A FILING

[Draft a formal board resolution authorising the filing of INC-20A]

---

## COMPLIANCE CHECKLIST — INC-20A

[List all requirements before filing]

---

## KEY FACTS

- Deadline: 180 days from date of incorporation
- Penalty for non-filing: ₹50,000 for company + ₹1,000/day for officer in default
- Requirement: Each subscriber must deposit subscription amount in company bank account
- Bank statement must evidence the receipt of share subscription money

Use formal legal language throughout.
"""
    return await _call_gemini(prompt)


async def generate_adt1_draft(company_data: Dict[str, Any]) -> str:
    prompt = f"""
You are a Company Secretary. Draft a Board Resolution and filing checklist for ADT-1 
(Appointment of First Auditor) under Section 139(6) of Companies Act 2013.

Company: {company_data.get("company_name")}
CIN: {company_data.get("cin", "To be updated")}
Date of Incorporation: {company_data.get("date_of_incorporation", "As per records")}

Generate:

## BOARD RESOLUTION FOR APPOINTMENT OF FIRST AUDITOR

[Draft a formal board resolution appointing the first auditor within 30 days of incorporation]

---

## CONSENT LETTER FORMAT — FROM AUDITOR

[Draft a standard consent-cum-certificate letter from the appointed auditor]

---

## ADT-1 FILING CHECKLIST

[Complete checklist for ADT-1 filing]

---

## KEY FACTS

- Deadline: Within 30 days of incorporation (Board to appoint)
- If Board fails: Members to appoint within 90 days at EGM
- Auditor holds office till conclusion of 1st AGM
- ADT-1 must be filed within 15 days of appointment

Use formal legal language throughout.
"""
    return await _call_gemini(prompt)


async def generate_first_board_meeting_draft(company_data: Dict[str, Any]) -> str:
    prompt = f"""
You are a Company Secretary. Draft a complete First Board Meeting Notice and Agenda
for a newly incorporated company under Companies Act 2013.

Company: {company_data.get("company_name")}
CIN: {company_data.get("cin", "To be updated")}
Date of Incorporation: {company_data.get("date_of_incorporation", "As per records")}

Generate:

## NOTICE OF FIRST BOARD MEETING

[Formal notice to all directors citing Section 173 of Companies Act 2013]

---

## AGENDA FOR FIRST BOARD MEETING

Include all mandatory agenda items:
1. Taking note of Certificate of Incorporation
2. Appointment of Chairman
3. Appointment of First Auditors (Section 139(6))
4. Adoption of Common Seal (if applicable)
5. Opening of Company Bank Account — authorising signatories
6. Appointment of Key Managerial Personnel (if applicable)
7. Taking note of Subscribers to MOA/AOA
8. Noting of registered office address (Section 12)
9. Fixing of Financial Year
10. Discussion on INC-20A filing
11. Authorisation for various compliance filings

---

## DRAFT BOARD RESOLUTIONS

[Draft brief resolution text for each agenda item above]

Use formal Company Secretarial language per Secretarial Standard SS-1.
"""
    return await _call_gemini(prompt)


async def generate_statutory_meeting_reminder(alert_type: str, company_data: Dict[str, Any]) -> str:
    prompt = f"""
You are a Compliance Officer at a CA firm. Draft a formal reminder email/letter 
to the management of a company for the following compliance:

Compliance: {alert_type}
Company: {company_data.get("company_name")}
CIN: {company_data.get("cin", "To be updated")}

Draft:
1. Subject line for the email
2. Formal reminder letter with:
   - Reference to applicable section of Companies Act 2013
   - Deadline details
   - Penalty for non-compliance  
   - Action required from management
   - Documents/information required from them
3. Sign-off from CA firm

Keep it professional, clear, and action-oriented.
"""
    return await _call_gemini(prompt)
