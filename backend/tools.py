"""
Tools for Hermes AI Agent: Lead Lookup & Lead Status Update.
Provides full execution logic, schema definitions, and audit tracking.
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import Lead, LeadAuditLog

VALID_STATUSES = ["New", "Contacted", "Qualified", "Disqualified"]

# Hermes-compatible JSON Tool Schemas
HERMES_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "lead_lookup",
            "description": "Look up an existing lead's details, requirements, and current status by lead ID or email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lead_id": {
                        "type": "integer",
                        "description": "The unique numeric ID of the lead."
                    },
                    "email": {
                        "type": "string",
                        "description": "The email address of the lead."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lead_status_update",
            "description": "Update the pipeline status of a specific lead and log the reasoning.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lead_id": {
                        "type": "integer",
                        "description": "The unique numeric ID of the lead to update."
                    },
                    "new_status": {
                        "type": "string",
                        "enum": VALID_STATUSES,
                        "description": "The target status: 'New', 'Contacted', 'Qualified', or 'Disqualified'."
                    },
                    "reason": {
                        "type": "string",
                        "description": "The business reason or justification for this status change."
                    }
                },
                "required": ["lead_id", "new_status", "reason"]
            }
        }
    }
]


def execute_lead_lookup(lead_id: Optional[int] = None, email: Optional[str] = None, db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Tool: lead_lookup
    Queries lead records by lead_id or email address.
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        if not lead_id and not email:
            return {
                "status": "error",
                "error_code": "MISSING_ARGUMENT",
                "message": "Either 'lead_id' or 'email' must be provided for lead lookup."
            }

        query = db.query(Lead)
        if lead_id:
            lead = query.filter(Lead.id == lead_id).first()
        else:
            lead = query.filter(Lead.email == email.strip().lower()).first()

        if not lead:
            identifier = f"ID: {lead_id}" if lead_id else f"Email: '{email}'"
            return {
                "status": "error",
                "error_code": "LEAD_NOT_FOUND",
                "message": f"Lead with {identifier} does not exist in the database."
            }

        return {
            "status": "success",
            "lead": lead.to_dict()
        }
    finally:
        if should_close:
            db.close()


def execute_lead_status_update(
    lead_id: int,
    new_status: str,
    reason: str,
    agent_name: str = "HermesAgent",
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Tool: lead_status_update
    Validates transition, updates lead status, and writes an audit log entry.
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        # Validate target status
        if new_status not in VALID_STATUSES:
            return {
                "status": "error",
                "error_code": "INVALID_STATUS",
                "message": f"Invalid status '{new_status}'. Allowed statuses are: {VALID_STATUSES}"
            }

        if not reason or len(reason.strip()) < 3:
            return {
                "status": "error",
                "error_code": "INVALID_REASON",
                "message": "A valid reason (minimum 3 characters) is required for audit logging."
            }

        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            return {
                "status": "error",
                "error_code": "LEAD_NOT_FOUND",
                "message": f"Cannot update status: Lead with ID {lead_id} does not exist."
            }

        previous_status = lead.status
        if previous_status == new_status:
            return {
                "status": "success",
                "message": f"Lead {lead_id} is already in '{new_status}' status. No change made.",
                "lead_id": lead_id,
                "status": new_status,
                "unchanged": True
            }

        # Perform update
        lead.status = new_status

        # Create audit entry
        audit_entry = LeadAuditLog(
            lead_id=lead.id,
            action="STATUS_UPDATE",
            previous_status=previous_status,
            new_status=new_status,
            reason=reason.strip(),
            performed_by=agent_name
        )
        db.add(audit_entry)
        db.commit()
        db.refresh(lead)

        return {
            "status": "success",
            "message": f"Lead {lead_id} status updated from '{previous_status}' to '{new_status}'.",
            "lead_id": lead.id,
            "previous_status": previous_status,
            "new_status": new_status,
            "reason": reason.strip(),
            "performed_by": agent_name
        }
    except Exception as e:
        db.rollback()
        return {
            "status": "error",
            "error_code": "DATABASE_ERROR",
            "message": f"Internal database error while updating lead status: {str(e)}"
        }
    finally:
        if should_close:
            db.close()
