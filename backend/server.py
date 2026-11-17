"""
Standalone REST API Server powered by aiohttp.web and Pydantic.
Runs out-of-the-box in any Python environment without requiring external uvicorn/fastapi packages.
Implements 100% of the assessment REST endpoints, validation, and error handling.
"""
import sys
import os
import json
from aiohttp import web
from pydantic import ValidationError

# Ensure root directory is in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.database import init_db, SessionLocal
from backend.models import Lead, LeadAuditLog
from backend.schemas import (
    LeadCreate,
    LeadStatusUpdate,
    AgentExecuteRequest,
)
from backend.ollama_service import analyze_lead_with_ollama
from backend.hermes_agent import HermesAgent
from backend.tools import execute_lead_status_update

# Initialize database schema
init_db()
hermes_agent = HermesAgent()


def json_response(data, status=200):
    return web.json_response(data, status=status)


async def handle_create_lead(request: web.Request):
    """POST /api/leads - Create lead with Pydantic validation & duplicate detection"""
    try:
        body = await request.json()
    except Exception:
        return json_response({"error_code": "INVALID_JSON", "message": "Request body must be valid JSON."}, 400)

    try:
        lead_in = LeadCreate(**body)
    except ValidationError as e:
        return json_response({"error_code": "VALIDATION_ERROR", "details": e.errors()}, 400)

    db = SessionLocal()
    try:
        # Check duplicate by email or phone
        existing = db.query(Lead).filter(
            (Lead.email == lead_in.email) | (Lead.phone_number == lead_in.phone_number)
        ).first()

        if existing:
            duplicate_field = "email" if existing.email == lead_in.email else "phone number"
            return json_response({
                "error_code": "DUPLICATE_LEAD",
                "message": f"A lead with this {duplicate_field} already exists (Lead ID: {existing.id}).",
                "existing_lead_id": existing.id
            }, 409)

        lead = Lead(
            name=lead_in.name,
            email=lead_in.email,
            phone_number=lead_in.phone_number,
            company=lead_in.company,
            message=lead_in.message,
            status="New",
            classification="Pending"
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)

        audit = LeadAuditLog(
            lead_id=lead.id,
            action="LEAD_CREATED",
            new_status="New",
            reason="Ingested via REST API endpoint",
            performed_by="REST_API"
        )
        db.add(audit)
        db.commit()

        return json_response(lead.to_dict(), 201)
    finally:
        db.close()


async def handle_list_leads(request: web.Request):
    """GET /api/leads - List and filter leads"""
    status = request.query.get("status")
    classification = request.query.get("classification")
    limit = int(request.query.get("limit", 50))

    db = SessionLocal()
    try:
        q = db.query(Lead)
        if status:
            q = q.filter(Lead.status == status)
        if classification:
            q = q.filter(Lead.classification == classification)
        leads = q.order_by(Lead.id.desc()).limit(limit).all()
        return json_response([l.to_dict() for l in leads])
    finally:
        db.close()


async def handle_get_lead(request: web.Request):
    """GET /api/leads/{id} - Retrieve single lead"""
    try:
        lead_id = int(request.match_info["id"])
    except ValueError:
        return json_response({"message": "Invalid lead ID format"}, 400)

    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            return json_response({"message": f"Lead with ID {lead_id} not found."}, 404)
        return json_response(lead.to_dict())
    finally:
        db.close()


async def handle_update_status(request: web.Request):
    """PATCH /api/leads/{id}/status - Update lead status"""
    try:
        lead_id = int(request.match_info["id"])
        body = await request.json()
        validated = LeadStatusUpdate(**body)
    except ValueError as ve:
        return json_response({"error_code": "INVALID_REQUEST", "message": str(ve)}, 400)
    except ValidationError as e:
        return json_response({"error_code": "VALIDATION_ERROR", "details": e.errors()}, 400)

    db = SessionLocal()
    try:
        result = execute_lead_status_update(
            lead_id=lead_id,
            new_status=validated.status,
            reason=validated.reason,
            agent_name=validated.agent_name or "REST_API",
            db=db
        )
        if result.get("status") == "error":
            code = 404 if result.get("error_code") == "LEAD_NOT_FOUND" else 400
            return json_response(result, code)
        return json_response(result)
    finally:
        db.close()


async def handle_analyze_lead(request: web.Request):
    """POST /api/leads/{id}/analyze - Run Ollama analysis on lead"""
    try:
        lead_id = int(request.match_info["id"])
    except ValueError:
        return json_response({"message": "Invalid lead ID"}, 400)

    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            return json_response({"message": f"Lead {lead_id} not found"}, 404)

        lead_data = {
            "id": lead.id,
            "name": lead.name,
            "company": lead.company,
            "email": lead.email,
            "phone_number": lead.phone_number,
            "message": lead.message
        }
        ai_res = analyze_lead_with_ollama(lead_data)

        lead.classification = ai_res.get("classification", "Warm Lead")
        lead.confidence_score = float(ai_res.get("confidence_score", 0.75))
        lead.business_intent = ai_res.get("business_intent")
        lead.extracted_requirements = json.dumps(ai_res.get("extracted_requirements", []))
        lead.ai_response = ai_res.get("personalized_response")

        audit = LeadAuditLog(
            lead_id=lead.id,
            action="AI_ANALYSIS_COMPLETED",
            previous_status=lead.status,
            new_status=lead.status,
            reason=f"Classification: {lead.classification}",
            performed_by=ai_res.get("_source", "OllamaService")
        )
        db.add(audit)
        db.commit()
        db.refresh(lead)

        return json_response({
            "status": "success",
            "lead_id": lead.id,
            "analysis": ai_res,
            "updated_lead": lead.to_dict()
        })
    finally:
        db.close()


async def handle_agent_execute(request: web.Request):
    """POST /api/agent/execute - Execute Hermes AI Agent command"""
    try:
        body = await request.json()
        req = AgentExecuteRequest(**body)
    except (ValueError, ValidationError) as e:
        return json_response({"error_code": "INVALID_REQUEST", "message": str(e)}, 400)

    db = SessionLocal()
    try:
        result = hermes_agent.execute(
            instruction=req.instruction,
            lead_id=req.lead_id,
            email=req.email,
            db=db
        )
        return json_response(result)
    finally:
        db.close()


async def handle_webhook(request: web.Request):
    """POST /api/webhook/leads - Automated pipeline for n8n webhook"""
    try:
        payload = await request.json()
    except Exception:
        return json_response({"message": "Invalid JSON body"}, 400)

    required_fields = ["name", "email", "phone_number", "company", "message"]
    missing = [f for f in required_fields if not payload.get(f)]
    if missing:
        return json_response({"message": f"Missing required fields: {missing}"}, 400)

    db = SessionLocal()
    try:
        existing = db.query(Lead).filter(
            (Lead.email == payload["email"].strip().lower()) |
            (Lead.phone_number == payload["phone_number"].strip())
        ).first()

        is_dup = False
        if existing:
            lead = existing
            is_dup = True
        else:
            lead = Lead(
                name=payload["name"].strip(),
                email=payload["email"].strip().lower(),
                phone_number=payload["phone_number"].strip(),
                company=payload["company"].strip(),
                message=payload["message"].strip(),
                status="New",
                classification="Pending"
            )
            db.add(lead)
            db.commit()
            db.refresh(lead)

        ai_res = analyze_lead_with_ollama({
            "id": lead.id,
            "name": lead.name,
            "company": lead.company,
            "email": lead.email,
            "phone_number": lead.phone_number,
            "message": lead.message
        })

        lead.classification = ai_res.get("classification", "Warm Lead")
        lead.confidence_score = float(ai_res.get("confidence_score", 0.75))
        lead.business_intent = ai_res.get("business_intent")
        lead.extracted_requirements = json.dumps(ai_res.get("extracted_requirements", []))
        lead.ai_response = ai_res.get("personalized_response")

        agent_res = None
        if lead.classification == "Hot Lead":
            agent_res = hermes_agent.execute(
                instruction=f"Update lead #{lead.id} to Qualified because high purchase intent detected.",
                lead_id=lead.id,
                db=db
            )
        elif lead.classification == "Cold Lead":
            agent_res = hermes_agent.execute(
                instruction=f"Update lead #{lead.id} to Disqualified because low intent.",
                lead_id=lead.id,
                db=db
            )
        else:
            agent_res = hermes_agent.execute(
                instruction=f"Update lead #{lead.id} to Contacted because personalized reply prepared.",
                lead_id=lead.id,
                db=db
            )

        db.commit()
        db.refresh(lead)

        return json_response({
            "status": "success",
            "is_duplicate": is_dup,
            "lead": lead.to_dict(),
            "ai_analysis": ai_res,
            "agent_workflow": agent_res
        })
    finally:
        db.close()


async def handle_stats(request: web.Request):
    """GET /api/stats/summary - Metrics for Gamma AI report"""
    db = SessionLocal()
    try:
        total = db.query(Lead).count()
        hot = db.query(Lead).filter(Lead.classification == "Hot Lead").count()
        warm = db.query(Lead).filter(Lead.classification == "Warm Lead").count()
        cold = db.query(Lead).filter(Lead.classification == "Cold Lead").count()

        status_counts = {
            "New": db.query(Lead).filter(Lead.status == "New").count(),
            "Contacted": db.query(Lead).filter(Lead.status == "Contacted").count(),
            "Qualified": db.query(Lead).filter(Lead.status == "Qualified").count(),
            "Disqualified": db.query(Lead).filter(Lead.status == "Disqualified").count()
        }

        sample_leads = db.query(Lead).limit(20).all()
        all_reqs = []
        for sl in sample_leads:
            if sl.extracted_requirements:
                try:
                    all_reqs.extend(json.loads(sl.extracted_requirements))
                except Exception:
                    pass

        return json_response({
            "total_leads_processed": total,
            "lead_distribution": {
                "hot_leads": hot,
                "warm_leads": warm,
                "cold_leads": cold
            },
            "status_distribution": status_counts,
            "common_requirements": list(set(all_reqs))[:10]
        })
    finally:
        db.close()


async def handle_health(request: web.Request):
    return json_response({"status": "healthy", "service": "lead-management-system", "version": "1.0.0"})


def create_app():
    app = web.Application()
    app.router.add_post("/api/leads", handle_create_lead)
    app.router.add_get("/api/leads", handle_list_leads)
    app.router.add_get("/api/leads/{id}", handle_get_lead)
    app.router.add_patch("/api/leads/{id}/status", handle_update_status)
    app.router.add_post("/api/leads/{id}/analyze", handle_analyze_lead)
    app.router.add_post("/api/agent/execute", handle_agent_execute)
    app.router.add_post("/api/webhook/leads", handle_webhook)
    app.router.add_get("/api/stats/summary", handle_stats)
    app.router.add_get("/health", handle_health)
    return app


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"🚀 Starting AI Lead Management REST Server on http://localhost:{port}")
    web.run_app(create_app(), host="127.0.0.1", port=port)
