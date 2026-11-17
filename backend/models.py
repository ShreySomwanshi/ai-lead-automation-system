"""
SQLAlchemy ORM models for Lead Management and Agent Audit Logs.
"""
from datetime import datetime, timezone
import json
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    phone_number = Column(String(40), index=True, nullable=False)
    company = Column(String(120), nullable=False)
    message = Column(Text, nullable=False)

    # AI Analysis Fields (Task 2)
    classification = Column(String(30), default="Pending")  # 'Hot Lead', 'Warm Lead', 'Cold Lead', 'Pending'
    confidence_score = Column(Float, default=0.0)
    business_intent = Column(Text, nullable=True)
    extracted_requirements = Column(Text, nullable=True)  # JSON-encoded string
    ai_response = Column(Text, nullable=True)

    # CRM Pipeline Status (Task 1 & Task 3)
    status = Column(String(40), default="New", index=True)  # 'New', 'Contacted', 'Qualified', 'Disqualified'

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationship to audit logs
    audit_logs = relationship("LeadAuditLog", back_populates="lead", cascade="all, delete-orphan")

    def to_dict(self):
        """Converts model instance to JSON-serializable dictionary."""
        requirements = []
        if self.extracted_requirements:
            try:
                requirements = json.loads(self.extracted_requirements)
            except Exception:
                requirements = [self.extracted_requirements]

        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone_number": self.phone_number,
            "company": self.company,
            "message": self.message,
            "classification": self.classification,
            "confidence_score": self.confidence_score,
            "business_intent": self.business_intent,
            "extracted_requirements": requirements,
            "ai_response": self.ai_response,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class LeadAuditLog(Base):
    __tablename__ = "lead_audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    action = Column(String(60), nullable=False)  # 'STATUS_UPDATE', 'AI_ANALYSIS', 'AGENT_TOOL_CALL'
    previous_status = Column(String(40), nullable=True)
    new_status = Column(String(40), nullable=True)
    reason = Column(Text, nullable=True)
    performed_by = Column(String(60), default="System")  # 'HermesAgent', 'OllamaService', 'User'
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    lead = relationship("Lead", back_populates="audit_logs")

    def to_dict(self):
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "action": self.action,
            "previous_status": self.previous_status,
            "new_status": self.new_status,
            "reason": self.reason,
            "performed_by": self.performed_by,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
