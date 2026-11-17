"""
Ollama AI Integration Service (Task 2 & Problem-Solving Resilience).
Connects to local Ollama instance for lead classification, requirement extraction,
and personalized response generation. Includes fallback heuristics and timeout handling.
"""
import os
import json
import re
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
REQUEST_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "20"))


ANALYSIS_SYSTEM_PROMPT = """You are an expert enterprise sales qualification and AI lead triage agent.
Your task is to analyze incoming business leads, categorize them strictly, extract requirements, and draft a high-converting personalized email response.

Classification Rules:
1. "Hot Lead":
   - Explicit purchase intent, ready to buy, urgent timeline (< 30 days), requests demo/pricing/quote/contract, or mentions active budget.
2. "Warm Lead":
   - Exploring solutions, asking technical questions, evaluating vendors, interested in features or case studies, medium timeline (1-3 months).
3. "Cold Lead":
   - Generic inquiries, vague messages, job seekers, vendors selling to us (solicitation), or students without buying authority.

Output strictly valid JSON with this schema and NO commentary:
{
  "classification": "Hot Lead" | "Warm Lead" | "Cold Lead",
  "confidence_score": 0.0 to 1.0,
  "business_intent": "Clear 1-2 sentence summary of what the lead wants to achieve",
  "extracted_requirements": ["Requirement 1", "Requirement 2", "..."],
  "personalized_response": "Professional, courteous, customized reply directly addressing their specific company and inquiry",
  "suggested_follow_up": "Concrete recommended next sales action"
}
"""


def _extract_json_from_text(raw_text: str) -> Optional[Dict[str, Any]]:
    """Resilient JSON extractor that parses raw text or extracts fenced JSON code blocks."""
    if not raw_text:
        return None

    # First attempt: direct parse
    try:
        return json.loads(raw_text.strip())
    except json.JSONDecodeError:
        pass

    # Second attempt: extract from markdown ```json ... ```
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw_text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Third attempt: find the first { and last }
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = raw_text[start : end + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            pass

    return None


def _fallback_heuristic_analyzer(lead_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Intelligent heuristic fallback analyzer when Ollama is unavailable or returns invalid data.
    Ensures zero pipeline failure and guarantees business continuity (Problem-Solving Challenge #1 & #3).
    """
    message = (lead_data.get("message") or "").lower()
    company = lead_data.get("company", "your organization")
    name = lead_data.get("name", "there")

    cold_keywords = [
        "hiring", "resume", "job", "internship", "student", "homework",
        "backlink", "guest post", "ranking", "seo outreach", "boost your outbound",
        "test message", "freelance", "50m cxo", "leads pro", "bulk leads", "special discount today"
    ]
    hot_keywords = ["urgent", "buy", "quote", "demo", "budget", "contract", "immediately", "asap", "procurement", "enterprise tier", "license", "ready to buy"]
    warm_keywords = ["feature", "integration", "how does", "compare", "trial", "pilot", "support", "roadmap", "api", "capabilities", "timeline", "pricing", "whitepaper"]

    # Check Cold first (disqualify non-prospects, spam, and applicants)
    is_cold = any(kw in message for kw in cold_keywords) or company.lower() in ["freelance", "university student", "n/a", "b2b lead lists pro", "backlink masters"]

    if is_cold:
        classification = "Cold Lead"
        confidence = 0.90
        intent = f"Low-priority, exploratory inquiry, or non-commercial solicitation from {company}."
        follow_up = "Route to automated archive or send standard non-sales notification."
        personalized_response = (
            f"Hello {name},\n\nThank you for reaching out. We have logged your submission. "
            f"If this is regarding careers or non-sales partnerships, our operations team will review accordingly.\n\n"
            f"Best regards,\nOperations Team"
        )
        requirements = ["Non-commercial inquiry / recruitment / solicitation"]
        return {
            "classification": classification,
            "confidence_score": confidence,
            "business_intent": intent,
            "extracted_requirements": requirements,
            "personalized_response": personalized_response,
            "suggested_follow_up": follow_up,
            "_source": "fallback_heuristic_engine"
        }

    score = 0
    requirements = []

    for kw in hot_keywords:
        if kw in message:
            score += 2
            requirements.append(f"Inquired about {kw}")

    for kw in warm_keywords:
        if kw in message:
            score += 1
            requirements.append(f"Technical interest in {kw}")

    if score >= 3 or any(w in message for w in ["demo", "quote", "approved", "ready to buy", "procurement", "enterprise quote"]):
        classification = "Hot Lead"
        confidence = 0.92
        intent = f"{company} has high immediate purchase intent and requires priority sales contact for pricing or demo."
        follow_up = "Schedule high-priority discovery call within 2 hours."
        personalized_response = (
            f"Hello {name},\n\nThank you for reaching out to us regarding {company}'s requirements. "
            f"We would be delighted to demonstrate our platform and discuss tailored enterprise options for your team. "
            f"Could you please share your availability for a brief 15-minute discovery session this week?\n\nBest regards,\nSales Engineering Team"
        )
    elif score >= 1:
        classification = "Warm Lead"
        confidence = 0.82
        intent = f"{company} is actively evaluating platform capabilities and exploring alignment."
        follow_up = "Send relevant technical case studies and invite to product webinar."
        personalized_response = (
            f"Hello {name},\n\nThank you for contacting us from {company}. "
            f"We appreciate your interest in our automation capabilities. "
            f"Based on your message, we have attached our solution brief and integration documentation for your review. "
            f"Let us know if you'd like to arrange a technical deep-dive!\n\nBest regards,\nCustomer Success Team"
        )
    else:
        classification = "Cold Lead"
        confidence = 0.70
        intent = f"General inquiry from {company} with limited immediate buying signals."
        follow_up = "Add to nurture email campaign and monitor future engagement."
        personalized_response = (
            f"Hello {name},\n\nThank you for reaching out. We have received your note regarding {company}. "
            f"You can explore our knowledge base and self-service documentation at any time.\n\nBest regards,\nSupport Team"
        )

    if not requirements:
        requirements = ["General platform inquiry"]

    return {
        "classification": classification,
        "confidence_score": confidence,
        "business_intent": intent,
        "extracted_requirements": requirements,
        "personalized_response": personalized_response,
        "suggested_follow_up": follow_up,
        "_source": "fallback_heuristic_engine"
    }


def analyze_lead_with_ollama(
    lead_data: Dict[str, Any],
    model: str = DEFAULT_MODEL,
    host: str = OLLAMA_HOST,
    timeout: int = REQUEST_TIMEOUT
) -> Dict[str, Any]:
    """
    Sends lead inquiry to local Ollama LLM and extracts structured analysis.
    Gracefully falls back to heuristic engine if Ollama is offline or times out.
    """
    user_prompt = f"""Incoming Lead Details:
- Name: {lead_data.get('name')}
- Company: {lead_data.get('company')}
- Email: {lead_data.get('email')}
- Phone: {lead_data.get('phone_number')}
- Message: "{lead_data.get('message')}"

Perform complete lead analysis and return strictly the JSON structure specified.
"""

    payload = {
        "model": model,
        "system": ANALYSIS_SYSTEM_PROMPT,
        "prompt": user_prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.1,
            "num_predict": 512
        }
    }

    url = f"{host.rstrip('/')}/api/generate"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                result_bytes = response.read()
                data = json.loads(result_bytes.decode("utf-8"))
                response_text = data.get("response", "")
                parsed = _extract_json_from_text(response_text)
                if parsed and "classification" in parsed:
                    parsed["_source"] = f"ollama_{model}"
                    # Ensure confidence_score is float
                    parsed["confidence_score"] = float(parsed.get("confidence_score", 0.85))
                    return parsed

        # If LLM response failed to parse as valid JSON
        return _fallback_heuristic_analyzer(lead_data)

    except (urllib.error.URLError, TimeoutError, ConnectionRefusedError, Exception) as exc:
        # Graceful fallback when Ollama is offline, unreachable, or times out
        fallback_result = _fallback_heuristic_analyzer(lead_data)
        fallback_result["_ollama_unavailable_reason"] = str(exc)
        return fallback_result
