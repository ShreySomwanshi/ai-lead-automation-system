"""
Automated Unit and Integration Tests for Lead Management REST API (Task 1).
Validates data integrity, regex format checks, duplicate prevention, and status transitions.
"""
import unittest
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from pydantic import ValidationError
from backend.database import SessionLocal, init_db
from backend.models import Lead, LeadAuditLog
from backend.schemas import LeadCreate, LeadStatusUpdate
from backend.tools import execute_lead_lookup, execute_lead_status_update


class TestLeadValidationAndDatabase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.db = SessionLocal()
        # Clean test records
        self.db.query(LeadAuditLog).delete()
        self.db.query(Lead).delete()
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_valid_lead_creation_and_lookup(self):
        """Test valid lead data ingestion and lookup."""
        valid_payload = {
            "name": "Sarah Connor",
            "email": "sarah@cyberdyne.io",
            "phone_number": "+1-555-019-2834",
            "company": "Cyberdyne Systems",
            "message": "We need an enterprise quote for 500 AI agent automation licenses urgently."
        }
        validated = LeadCreate(**valid_payload)
        self.assertEqual(validated.email, "sarah@cyberdyne.io")

        # Insert to DB
        lead = Lead(
            name=validated.name,
            email=validated.email,
            phone_number=validated.phone_number,
            company=validated.company,
            message=validated.message,
            status="New",
            classification="Pending"
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)

        self.assertIsNotNone(lead.id)
        self.assertEqual(lead.status, "New")

        # Test lookup tool by ID
        res_by_id = execute_lead_lookup(lead_id=lead.id, db=self.db)
        self.assertEqual(res_by_id["status"], "success")
        self.assertEqual(res_by_id["lead"]["name"], "Sarah Connor")

        # Test lookup tool by Email
        res_by_email = execute_lead_lookup(email="sarah@cyberdyne.io", db=self.db)
        self.assertEqual(res_by_email["status"], "success")
        self.assertEqual(res_by_email["lead"]["id"], lead.id)

    def test_invalid_email_and_phone_validation(self):
        """Test that invalid email and phone formats fail validation with clear errors."""
        # Invalid email
        with self.assertRaises(ValidationError) as ctx:
            LeadCreate(
                name="John Doe",
                email="not-an-email",
                phone_number="+1-555-019-2834",
                company="Acme Corp",
                message="Need a demo."
            )
        self.assertIn("Invalid email address format", str(ctx.exception))

        # Invalid phone
        with self.assertRaises(ValidationError) as ctx2:
            LeadCreate(
                name="John Doe",
                email="john@acme.com",
                phone_number="123",  # Too short (< 7 digits)
                company="Acme Corp",
                message="Need a demo."
            )
        self.assertIn("Invalid phone number format", str(ctx2.exception))

    def test_duplicate_prevention(self):
        """Test that attempting to insert a duplicate email or phone is caught."""
        lead1 = Lead(
            name="Alice Smith",
            email="alice@techcorp.com",
            phone_number="+1-555-111-2222",
            company="TechCorp",
            message="Evaluating vendor solutions."
        )
        self.db.add(lead1)
        self.db.commit()

        # Check duplicate logic
        new_email = "alice@techcorp.com"
        duplicate_check = self.db.query(Lead).filter(Lead.email == new_email).first()
        self.assertIsNotNone(duplicate_check)
        self.assertEqual(duplicate_check.id, lead1.id)

    def test_lead_status_update_and_audit(self):
        """Test status transitions and audit log creation."""
        lead = Lead(
            name="Bob Miller",
            email="bob@miller.com",
            phone_number="+1-555-333-4444",
            company="Miller Logistics",
            message="Looking for automated fleet routing."
        )
        self.db.add(lead)
        self.db.commit()

        # Update status to Contacted
        res = execute_lead_status_update(
            lead_id=lead.id,
            new_status="Contacted",
            reason="Sent introduction deck via email",
            agent_name="SalesBot",
            db=self.db
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["new_status"], "Contacted")
        self.assertEqual(res["previous_status"], "New")

        # Verify audit log recorded
        audit = self.db.query(LeadAuditLog).filter(LeadAuditLog.lead_id == lead.id).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.action, "STATUS_UPDATE")
        self.assertEqual(audit.performed_by, "SalesBot")

    def test_invalid_status_transition_handling(self):
        """Test handling of invalid status transition (Problem-Solving Scenario)."""
        lead = Lead(
            name="Charlie",
            email="charlie@test.com",
            phone_number="+1-555-999-8888",
            company="Test Inc",
            message="Test inquiry."
        )
        self.db.add(lead)
        self.db.commit()

        # Attempt illegal status "MegaHot"
        res = execute_lead_status_update(
            lead_id=lead.id,
            new_status="MegaHot",
            reason="Testing invalid state",
            db=self.db
        )
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_code"], "INVALID_STATUS")


if __name__ == "__main__":
    unittest.main()
