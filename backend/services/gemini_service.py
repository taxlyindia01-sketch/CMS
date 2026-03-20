"""
Gemini AI Service
Handles all AI drafting tasks using Gemini API
"""

import httpx
import os
from typing import Dict, Any

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent"


async def call_gemini(prompt: str) -> str:
    """
    Call Gemini API with a prompt and return the text response.
    """
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ]
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{GEMINI_ENDPOINT}?key={GEMINI_API_KEY}",
            json=payload,
            headers=headers
        )
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


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
