"""
FastAPI REST API Application for AI-Powered Lead Management & Automation System.
Implements Task 1 (REST API), Task 2 (Ollama Integration), Task 3 (Hermes Agent),
and Task 4 (n8n Webhook Integration).
"""
import os
import json
from datetime import datetime, timezone
from typing import List, Optional

try:
    from fastapi import FastAPI, Depends, HTTPException, Query, status
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
except ImportError:
    FastAPI = None

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.database import get_db, init_db, SessionLocal
from backend.models import Lead, LeadAuditLog
from backend.schemas import (
    LeadCreate,
    LeadResponse,
    LeadStatusUpdate,
    AIAnalysisResult,
    AgentExecuteRequest,
    AgentExecuteResponse,
)
from backend.ollama_service import analyze_lead_with_ollama
from backend.hermes_agent import HermesAgent
from backend.tools import execute_lead_lookup, execute_lead_status_update

# Initialize database schema on startup
init_db()

app = FastAPI(
    title="AI-Powered Lead Management & Automation System",
    description="Enterprise REST API for Lead Ingestion, Ollama AI Triage, and Hermes Agent Tool Calling",
    version="1.0.0"
) if FastAPI else None

if app:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

hermes_agent = HermesAgent()


# ==========================================
# Task 1: REST API Endpoints
# ==========================================

if app:
    @app.post(
        "/api/leads",
        response_model=LeadResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create a new lead with validation & duplicate detection"
    )
    def create_lead(lead_in: LeadCreate, db: Session = Depends(get_db)):
        """
        Receives lead information: name, email, phone_number, company, message.
        Validates incoming data and enforces duplicate prevention (Problem-Solving Challenge #2).
        """
        # Check for duplicate lead by email or phone number
        existing_lead = db.query(Lead).filter(
            (Lead.email == lead_in.email) | (Lead.phone_number == lead_in.phone_number)
        ).first()

        if existing_lead:
            duplicate_field = "email" if existing_lead.email == lead_in.email else "phone number"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error_code": "DUPLICATE_LEAD",
                    "message": f"A lead with this {duplicate_field} already exists (Lead ID: {existing_lead.id}).",
                    "existing_lead_id": existing_lead.id
                }
            )

        new_lead = Lead(
            name=lead_in.name,
            email=lead_in.email,
            phone_number=lead_in.phone_number,
            company=lead_in.company,
            message=lead_in.message,
            status="New",
            classification="Pending"
        )
        db.add(new_lead)
        db.commit()
        db.refresh(new_lead)

        # Audit initial creation
        audit = LeadAuditLog(
            lead_id=new_lead.id,
            action="LEAD_CREATED",
            new_status="New",
            reason="Lead ingested via REST API endpoint",
            performed_by="REST_API"
        )
        db.add(audit)
        db.commit()

        return new_lead.to_dict()


    @app.get(
        "/api/leads",
        response_model=List[LeadResponse],
        summary="List all leads with optional filtering"
    )
    def list_leads(
        status: Optional[str] = Query(None, description="Filter by status: New, Contacted, Qualified, Disqualified"),
        classification: Optional[str] = Query(None, description="Filter by classification: Hot Lead, Warm Lead, Cold Lead"),
        limit: int = Query(50, ge=1, le=200),
        db: Session = Depends(get_db)
    ):
        """Lists stored leads with optional filtering and pagination."""
        query = db.query(Lead)
        if status:
            query = query.filter(Lead.status == status)
        if classification:
            query = query.filter(Lead.classification == classification)
        leads = query.order_by(Lead.id.desc()).limit(limit).all()
        return [l.to_dict() for l in leads]


    @app.get(
        "/api/leads/{lead_id}",
        response_model=LeadResponse,
        summary="Look up a lead by ID"
    )
    def get_lead(lead_id: int, db: Session = Depends(get_db)):
        """Retrieves a single lead's full details."""
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead with ID {lead_id} was not found."
            )
        return lead.to_dict()


    @app.patch(
        "/api/leads/{lead_id}/status",
        summary="Update lead status with reason and audit tracking"
    )
    def update_lead_status(lead_id: int, update_data: LeadStatusUpdate, db: Session = Depends(get_db)):
        """Updates pipeline status (New, Contacted, Qualified, Disqualified) with audit reasoning."""
        result = execute_lead_status_update(
            lead_id=lead_id,
            new_status=update_data.status,
            reason=update_data.reason,
            agent_name=update_data.agent_name or "REST_API",
            db=db
        )
        if result.get("status") == "error":
            code = status.HTTP_404_NOT_FOUND if result.get("error_code") == "LEAD_NOT_FOUND" else status.HTTP_400_BAD_REQUEST
            raise HTTPException(status_code=code, detail=result)
        return result


    # ==========================================
    # Task 2: AI Integration Using Ollama
    # ==========================================

    @app.post(
        "/api/leads/{lead_id}/analyze",
        summary="Trigger Ollama AI analysis for a lead"
    )
    def analyze_lead_endpoint(lead_id: int, db: Session = Depends(get_db)):
        """
        Sends lead inquiry to local Ollama LLM to classify (Hot/Warm/Cold),
        extract requirements and business intent, and draft a personalized response.
        """
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead {lead_id} not found")

        lead_data = {
            "id": lead.id,
            "name": lead.name,
            "company": lead.company,
            "email": lead.email,
            "phone_number": lead.phone_number,
            "message": lead.message
        }

        # Run AI analysis (with built-in fallback)
        ai_result = analyze_lead_with_ollama(lead_data)

        # Update lead in database
        lead.classification = ai_result.get("classification", "Warm Lead")
        lead.confidence_score = float(ai_result.get("confidence_score", 0.75))
        lead.business_intent = ai_result.get("business_intent")
        lead.extracted_requirements = json.dumps(ai_result.get("extracted_requirements", []))
        lead.ai_response = ai_result.get("personalized_response")
        lead.updated_at = datetime.now(timezone.utc)

        # Audit log entry
        audit = LeadAuditLog(
            lead_id=lead.id,
            action="AI_ANALYSIS_COMPLETED",
            previous_status=lead.status,
            new_status=lead.status,
            reason=f"AI classified as {lead.classification} (Confidence: {lead.confidence_score:.2f})",
            performed_by=ai_result.get("_source", "OllamaService")
        )
        db.add(audit)
        db.commit()
        db.refresh(lead)

        return {
            "status": "success",
            "lead_id": lead.id,
            "analysis": ai_result,
            "updated_lead": lead.to_dict()
        }


    # ==========================================
    # Task 3: AI Agent Using Hermes
    # ==========================================

    @app.post(
        "/api/agent/execute",
        response_model=AgentExecuteResponse,
        summary="Execute natural language instruction via Hermes AI Agent"
    )
    def execute_agent_command(request: AgentExecuteRequest, db: Session = Depends(get_db)):
        """
        Hermes AI Agent endpoint. Understands user request, selects appropriate tool
        (lead_lookup or lead_status_update), executes it, and handles errors gracefully.
        """
        agent_outcome = hermes_agent.execute(
            instruction=request.instruction,
            lead_id=request.lead_id,
            email=request.email,
            db=db
        )
        return agent_outcome


    # ==========================================
    # Task 4: Workflow Automation Webhook Endpoint
    # ==========================================

    @app.post(
        "/api/webhook/leads",
        status_code=status.HTTP_200_OK,
        summary="Automated pipeline webhook (n8n integration)"
    )
    def webhook_lead_automation(payload: dict, db: Session = Depends(get_db)):
        """
        Comprehensive automated workflow endpoint matching n8n pipeline:
        1. Validates payload
        2. Duplicate check
        3. Ingests or locates lead
        4. Triggers Ollama analysis
        5. Executes Hermes agent workflow
        6. Updates status
        7. Returns final response
        """
        required_fields = ["name", "email", "phone_number", "company", "message"]
        missing = [f for f in required_fields if not payload.get(f)]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Webhook validation failed. Missing fields: {missing}"
            )

        # Duplicate check
        existing = db.query(Lead).filter(
            (Lead.email == payload["email"].strip().lower()) |
            (Lead.phone_number == payload["phone_number"].strip())
        ).first()

        is_duplicate = False
        if existing:
            lead = existing
            is_duplicate = True
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

        # Run AI Analysis
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

        # Execute Hermes Agent workflow step: auto-qualify Hot leads
        agent_action = None
        if lead.classification == "Hot Lead":
            agent_action = hermes_agent.execute(
                instruction=f"Update lead #{lead.id} to Qualified because AI classified high intent with immediate budget.",
                lead_id=lead.id,
                db=db
            )
        elif lead.classification == "Cold Lead":
            agent_action = hermes_agent.execute(
                instruction=f"Update lead #{lead.id} to Disqualified because AI classified as low intent.",
                lead_id=lead.id,
                db=db
            )
        else:
            agent_action = hermes_agent.execute(
                instruction=f"Update lead #{lead.id} to Contacted because personalized reply was prepared.",
                lead_id=lead.id,
                db=db
            )

        db.commit()
        db.refresh(lead)

        return {
            "status": "success",
            "is_duplicate": is_duplicate,
            "lead": lead.to_dict(),
            "ai_analysis": ai_res,
            "agent_workflow": agent_action
        }


    # ==========================================
    # Task 5: Aggregated Reporting Endpoint
    # ==========================================

    @app.get(
        "/api/stats/summary",
        summary="Aggregate metrics for Gamma AI Presentation and Reporting"
    )
    def get_summary_stats(db: Session = Depends(get_db)):
        """Returns aggregated figures for Gamma AI presentation."""
        total_leads = db.query(Lead).count()
        hot_leads = db.query(Lead).filter(Lead.classification == "Hot Lead").count()
        warm_leads = db.query(Lead).filter(Lead.classification == "Warm Lead").count()
        cold_leads = db.query(Lead).filter(Lead.classification == "Cold Lead").count()
        pending = db.query(Lead).filter(Lead.classification == "Pending").count()

        status_counts = {
            "New": db.query(Lead).filter(Lead.status == "New").count(),
            "Contacted": db.query(Lead).filter(Lead.status == "Contacted").count(),
            "Qualified": db.query(Lead).filter(Lead.status == "Qualified").count(),
            "Disqualified": db.query(Lead).filter(Lead.status == "Disqualified").count()
        }

        # Gather sample requirements
        sample_leads = db.query(Lead).limit(15).all()
        all_reqs = []
        for sl in sample_leads:
            if sl.extracted_requirements:
                try:
                    all_reqs.extend(json.loads(sl.extracted_requirements))
                except Exception:
                    pass

        return {
            "total_leads_processed": total_leads,
            "lead_distribution": {
                "hot_leads": hot_leads,
                "warm_leads": warm_leads,
                "cold_leads": cold_leads,
                "pending": pending
            },
            "status_distribution": status_counts,
            "common_requirements": list(set(all_reqs))[:10],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


    @app.get("/health", summary="Healthcheck")
    def health_check(db: Session = Depends(get_db)):
        return {"status": "healthy", "service": "lead-management-system", "database": "connected"}
