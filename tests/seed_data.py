"""
Seed Data Generator and Automated Pipeline Runner.
Ingests 15 realistic B2B test leads across Hot, Warm, and Cold intent,
runs Ollama analysis, updates pipeline statuses, and generates sample metrics for Gamma.app.
"""
import os
import sys
import json

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.database import SessionLocal, init_db
from backend.models import Lead, LeadAuditLog
from backend.ollama_service import analyze_lead_with_ollama

SAMPLE_LEADS = [
    # --- HOT LEADS (Urgent, clear budget, demo/quote requests) ---
    {
        "name": "David Sterling",
        "email": "dsterling@apexlogistics.com",
        "phone_number": "+1-212-555-0143",
        "company": "Apex Global Logistics",
        "message": "We have an approved $50k Q1 budget to automate our 24/7 dispatch ticketing. Need an immediate demo this Thursday and enterprise quote for 150 agents."
    },
    {
        "name": "Meera Patel",
        "email": "meera.patel@finscale.io",
        "phone_number": "+44-20-7946-0912",
        "company": "FinScale Technologies",
        "message": "Urgent requirement: looking to replace our legacy CRM workflow with AI triage ASAP. We are deciding between two vendors by Friday. Please share contract pricing."
    },
    {
        "name": "Marcus Vance",
        "email": "mvance@healthcloud.org",
        "phone_number": "+1-415-555-8821",
        "company": "HealthCloud Systems",
        "message": "We need HIPAA-compliant lead routing and automated response drafting. 200,000 monthly inquiries. Immediate procurement decision needed."
    },
    {
        "name": "Sophia Chen",
        "email": "sophia.chen@novaretail.com",
        "phone_number": "+1-312-555-6677",
        "company": "Nova Retail Brands",
        "message": "Ready to buy. Our VP of Sales approved the onboarding. Can you send the master service agreement and schedule implementation kickoff next week?"
    },

    # --- WARM LEADS (Evaluating, feature exploration, comparison) ---
    {
        "name": "Carlos Gomez",
        "email": "carlos.g@solardrive.es",
        "phone_number": "+34-91-123-4567",
        "company": "SolarDrive Energy",
        "message": "Hi, we are researching AI automation tools for our customer support queue. How does your platform integrate with HubSpot and Zendesk? Can we start a 14-day trial?"
    },
    {
        "name": "Rachel Adams",
        "email": "rachel@cleantech.org",
        "phone_number": "+1-617-555-3211",
        "company": "CleanTech Innovations",
        "message": "Could you provide technical documentation on your webhook payloads and rate limits? We are evaluating automated lead scoring for next quarter."
    },
    {
        "name": "Arjun Rao",
        "email": "arjun.rao@hyperbuild.co",
        "phone_number": "+91-98765-43210",
        "company": "HyperBuild Infra",
        "message": "We'd like to understand how your Hermes agent integration handles multi-step tool calls. Do you have a whitepaper or case study on construction tech?"
    },
    {
        "name": "Emily Watson",
        "email": "ewatson@bluehorizon.net",
        "phone_number": "+1-206-555-7489",
        "company": "Blue Horizon Media",
        "message": "Exploring options for our digital marketing agency. What are the key differentiators between your solution and Zapier or standard n8n workflows?"
    },
    {
        "name": "Lukas Weber",
        "email": "l.weber@bavaria-auto.de",
        "phone_number": "+49-89-636-4820",
        "company": "Bavaria Automotive Parts",
        "message": "We are interested in automated lead classification for European distributors. Does your model support German language queries?"
    },
    {
        "name": "Fatima Al-Mansoor",
        "email": "fatima@gulflogistics.ae",
        "phone_number": "+971-4-321-7654",
        "company": "Gulf Express Logistics",
        "message": "Can you provide standard tier pricing sheets? We are currently gathering estimates for our mid-year planning committee."
    },

    # --- COLD LEADS (Generic inquiries, spam, job seekers, vendors selling to us) ---
    {
        "name": "Kevin Brooks",
        "email": "kbrooks892@gmail.com",
        "phone_number": "+1-555-019-3388",
        "company": "Freelance",
        "message": "Hello, are you hiring junior prompt engineers or AI developers? I graduated last semester and attach my resume."
    },
    {
        "name": "Spam Vendor Marketing",
        "email": "leads@b2b-bulk-leads-promo.xyz",
        "phone_number": "+1-800-555-0199",
        "company": "B2B Lead Lists Pro",
        "message": "Boost your outbound sales by 500% with our verified database of 50M CXO emails. Special discount today only $99."
    },
    {
        "name": "Timmy Johnson",
        "email": "tjohnson@student.univ.edu",
        "phone_number": "+1-555-908-1122",
        "company": "University Student",
        "message": "Hi, doing a class presentation on AI agents. Can you answer 5 questions for my homework assignment?"
    },
    {
        "name": "Anonymous Inquiry",
        "email": "info@randomdomain123.org",
        "phone_number": "+1-555-000-1111",
        "company": "N/A",
        "message": "Test message to check if this contact form is working."
    },
    {
        "name": "SEO Outreach Specialist",
        "email": "outreach@backlink-masters.co",
        "phone_number": "+44-161-555-0123",
        "company": "Backlink Masters",
        "message": "We noticed your website ranking could improve. We offer guest post placements on DA 60+ websites starting at $50 per link."
    }
]


def seed_database():
    print("🌱 Initializing Database Schema...")
    init_db()
    db = SessionLocal()

    # Clear old records for clean run
    db.query(LeadAuditLog).delete()
    db.query(Lead).delete()
    db.commit()

    processed_leads = []
    print(f"📥 Ingesting and Triaging {len(SAMPLE_LEADS)} Leads with AI Analysis...")

    for i, lead_raw in enumerate(SAMPLE_LEADS, start=1):
        lead = Lead(
            name=lead_raw["name"],
            email=lead_raw["email"],
            phone_number=lead_raw["phone_number"],
            company=lead_raw["company"],
            message=lead_raw["message"],
            status="New",
            classification="Pending"
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)

        # Run AI analysis
        ai_res = analyze_lead_with_ollama({
            "id": lead.id,
            "name": lead.name,
            "company": lead.company,
            "email": lead.email,
            "phone_number": lead.phone_number,
            "message": lead.message
        })

        lead.classification = ai_res.get("classification", "Warm Lead")
        lead.confidence_score = float(ai_res.get("confidence_score", 0.8))
        lead.business_intent = ai_res.get("business_intent")
        lead.extracted_requirements = json.dumps(ai_res.get("extracted_requirements", []))
        lead.ai_response = ai_res.get("personalized_response")

        # Automatic status transitions based on classification
        if lead.classification == "Hot Lead":
            lead.status = "Qualified"
        elif lead.classification == "Warm Lead":
            lead.status = "Contacted"
        else:
            lead.status = "Disqualified"

        audit = LeadAuditLog(
            lead_id=lead.id,
            action="AI_TRIAGE_AND_STATUS_UPDATE",
            previous_status="New",
            new_status=lead.status,
            reason=f"Auto-classified as {lead.classification}",
            performed_by="OllamaTriageService"
        )
        db.add(audit)
        db.commit()
        db.refresh(lead)

        processed_leads.append(lead.to_dict())
        print(f"  [{i:02d}/{len(SAMPLE_LEADS)}] {lead.company[:25]:<25} -> {lead.classification:<10} | Status: {lead.status}")

    # Export metrics for Gamma AI
    gamma_dir = os.path.join(PROJECT_ROOT, "gamma")
    os.makedirs(gamma_dir, exist_ok=True)
    out_file = os.path.join(gamma_dir, "sample_lead_data.json")

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(processed_leads, f, indent=2)

    total = len(processed_leads)
    hot = sum(1 for l in processed_leads if l["classification"] == "Hot Lead")
    warm = sum(1 for l in processed_leads if l["classification"] == "Warm Lead")
    cold = sum(1 for l in processed_leads if l["classification"] == "Cold Lead")

    print("\n" + "=" * 60)
    print("📊 SEEDING & ANALYSIS COMPLETE - PIPELINE SUMMARY:")
    print(f"  Total Leads Processed : {total}")
    print(f"  🔥 Hot Leads          : {hot} ({hot/total*100:.1f}%) -> Status: Qualified")
    print(f"  🌤️  Warm Leads         : {warm} ({warm/total*100:.1f}%) -> Status: Contacted")
    print(f"  ❄️  Cold Leads         : {cold} ({cold/total*100:.1f}%) -> Status: Disqualified")
    print(f"  Exported to           : {out_file}")
    print("=" * 60 + "\n")
    db.close()


if __name__ == "__main__":
    seed_database()
