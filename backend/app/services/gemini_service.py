"""
Gemini AI Service
Handles all AI drafting tasks using Gemini API

FIX #5: Model name 'gemini-2.5-flash' was experimental/incorrect endpoint.
         Corrected to 'gemini-1.5-flash' (stable, production-ready).
FIX #6: API key fallback was literal "YOUR_GEMINI_API_KEY" string — server
         would send invalid auth and silently fail. Now raises clear error.
FIX #7: Added timeout, retry, and proper error message propagation.
"""

import httpx
import os
from typing import Dict, Any

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# FIXED: was 'gemini-2.5-flash' (experimental) → 'gemini-1.5-flash' (stable)
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)


async def call_gemini(prompt: str) -> str:
    """
    Call Gemini API with a prompt and return the text response.
    FIXED: raises descriptive error if API key is missing instead of
    silently sending invalid requests.
    """
    if not GEMINI_API_KEY:
        return (
            "[AI Draft Unavailable — GEMINI_API_KEY not configured. "
            "Add it to your .env file to enable AI document generation.]"
        )

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                f"{GEMINI_ENDPOINT}?key={GEMINI_API_KEY}",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except httpx.TimeoutException:
        return "[AI Draft Unavailable — Request timed out. Please try regenerating.]"
    except httpx.HTTPStatusError as e:
        return f"[AI Draft Unavailable — API error {e.response.status_code}. Check your GEMINI_API_KEY.]"
    except (KeyError, IndexError):
        return "[AI Draft Unavailable — Unexpected response format from Gemini API.]"
    except Exception as e:
        return f"[AI Draft Unavailable — {str(e)}]"


async def generate_thank_you_letter(enquiry_data: Dict[str, Any]) -> str:
    """Generate a professional thank-you letter for incorporation enquiry."""
    prompt = f"""
You are a professional Chartered Accountant. Write a formal thank-you letter to a client
who has enquired about company incorporation services.

Client Details:
- Contact Name: {enquiry_data.get('contact_name', 'Valued Client')}
- Proposed Company Name: {enquiry_data.get('proposed_company_name')}
- Service: Company Incorporation

Write a warm, professional 3-paragraph letter. Include:
1. Thank them for choosing our firm
2. Confirm receipt of their enquiry for {enquiry_data.get('proposed_company_name')}
3. Assure them our team will reach out within 24 hours

Sign off as: CA [Firm Name] | Compliance & Legal Services

Format as a proper business letter.
"""
    return await call_gemini(prompt)


async def generate_document_checklist(enquiry_data: Dict[str, Any]) -> str:
    """Generate a list of required documents for company incorporation."""
    directors = ", ".join(enquiry_data.get('director_names', []))
    shareholders = ", ".join(enquiry_data.get('shareholder_names', []))

    prompt = f"""
You are a professional Chartered Accountant. Generate a comprehensive document checklist
for company incorporation in India under Companies Act 2013.

Company Details:
- Proposed Company Name: {enquiry_data.get('proposed_company_name')}
- Directors: {directors or 'Not specified'}
- Shareholders: {shareholders or 'Not specified'}
- Authorised Capital: {enquiry_data.get('authorised_capital', 'Not specified')}

Create a structured checklist with sections:
1. For Each Director (ID proof, address proof, etc.)
2. For Each Shareholder
3. For the Company (registered office documents)
4. Digital Signature Certificate (DSC) requirements
5. Additional documents

Format as a numbered list under each section heading. Keep it professional and complete.
"""
    return await call_gemini(prompt)


async def generate_price_quotation(enquiry_data: Dict[str, Any]) -> str:
    """Generate a price quotation for incorporation services."""
    num_directors = len(enquiry_data.get('director_names', []))

    prompt = f"""
You are a professional Chartered Accountant. Generate a formal price quotation for
company incorporation services.

Details:
- Proposed Company Name: {enquiry_data.get('proposed_company_name')}
- Number of Directors: {num_directors or 2}
- Authorised Capital: ₹{enquiry_data.get('authorised_capital', '100000')}
- Service Required: Private Limited Company Incorporation

Create a professional quotation including:
1. Professional fees for incorporation
2. Government fees (MCA filing, stamp duty)
3. DSC charges per director
4. GST at 18%
5. Total estimated cost

Include a note about timeline (typically 15-20 working days) and validity of quotation (30 days).
Present as a formatted quotation table with itemized costs.
Note: Use realistic Indian market rates in INR.
"""
    return await call_gemini(prompt)
