"""
Automated Tests for Hermes AI Agent (Task 3).
Tests autonomous reasoning, tool selection, parameter binding,
and handling of invalid requests or tool execution failures.
"""
import unittest
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.database import SessionLocal, init_db
from backend.models import Lead, LeadAuditLog
from backend.hermes_agent import HermesAgent


class TestHermesAgent(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.agent = HermesAgent()

    def setUp(self):
        self.db = SessionLocal()
        self.db.query(LeadAuditLog).delete()
        self.db.query(Lead).delete()

        # Seed test lead
        self.test_lead = Lead(
            name="Elena Rostova",
            email="elena@apextech.com",
            phone_number="+1-555-777-9999",
            company="Apex Technologies",
            message="We need to deploy automated lead qualification across our sales reps by next month. Requesting urgent pricing.",
            status="New",
            classification="Hot Lead"
        )
        self.db.add(self.test_lead)
        self.db.commit()
        self.db.refresh(self.test_lead)

    def tearDown(self):
        self.db.close()

    def test_agent_selects_lead_lookup(self):
        """Test agent correctly selects lead_lookup tool from natural language."""
        instruction = f"Look up lead #{self.test_lead.id} and check their requirements"
        result = self.agent.execute(instruction=instruction, db=self.db)

        self.assertTrue(result["success"])
        self.assertEqual(result["tool_executed"], "lead_lookup")
        self.assertEqual(result["tool_input"]["lead_id"], self.test_lead.id)
        self.assertIn("Elena Rostova", result["final_response"])

    def test_agent_selects_lead_status_update(self):
        """Test agent correctly selects lead_status_update tool and applies changes."""
        instruction = f"Update lead #{self.test_lead.id} to Qualified because they requested urgent pricing."
        result = self.agent.execute(instruction=instruction, db=self.db)

        self.assertTrue(result["success"])
        self.assertEqual(result["tool_executed"], "lead_status_update")
        self.assertEqual(result["tool_input"]["new_status"], "Qualified")
        self.assertIn("Successfully executed lead status update", result["final_response"])

        # Check DB reflects change
        self.db.refresh(self.test_lead)
        self.assertEqual(self.test_lead.status, "Qualified")

    def test_agent_handles_invalid_request_missing_id(self):
        """Demonstrate agent handling an invalid request (missing lead ID)."""
        instruction = "Please update the lead status to Qualified"  # No ID provided!
        result = self.agent.execute(instruction=instruction, db=self.db)

        self.assertFalse(result["success"])
        self.assertIsNone(result["tool_executed"])
        self.assertIn("unable to proceed", result["final_response"])
        self.assertIn("no valid lead ID", result["agent_reasoning"])

    def test_agent_handles_tool_failure_nonexistent_lead(self):
        """Demonstrate agent handling a tool failure (non-existent lead ID #99999)."""
        instruction = "Update lead #99999 to Contacted because we called them."
        result = self.agent.execute(instruction=instruction, db=self.db)

        self.assertFalse(result["success"])
        self.assertEqual(result["tool_executed"], "lead_status_update")
        self.assertEqual(result["tool_result"]["error_code"], "LEAD_NOT_FOUND")
        self.assertIn("Hermes Agent encountered a handled tool failure", result["final_response"])
        self.assertIn("Lead with ID 99999 does not exist", result["final_response"])


if __name__ == "__main__":
    unittest.main()
