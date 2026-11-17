# Screen Recording Checklist & Demo Walkthrough Guide

The instructions require continuous screen recording capturing the development, implementation, testing, and execution process, uploaded to Google Drive.

Use this checklist to ensure every required assessment task is clearly demonstrated on camera.

---

## ⏱️ Target Video Duration: 10 to 15 Minutes
*Recommended Recording Software: OBS Studio, Windows Xbox Game Bar (`Win + G`), Loom, or ShareX.*

---

## 🎬 Step-by-Step Recording Sequence

### Scene 1: Project Architecture & Structure Overview (1–2 mins)
- Open VS Code with the project folder `ai-lead-automation-system`.
- Walk through the directory tree:
  - `backend/`: FastAPI / aiohttp REST API, SQLAlchemy models, Pydantic schemas, Ollama service, Hermes agent, tools.
  - `n8n/`: Complete `lead_management_workflow.json` with 8-node pipeline.
  - `ollama/`: Modelfile, configuration instructions, model parameters.
  - `gamma/`: Presentation prompt, generated metrics dataset (`sample_lead_data.json`).
  - `docs/`: Comprehensive problem-solving documentation for the 6 technical challenges.
  - `tests/`: Automated unit tests for validation, duplicate checks, and Hermes agent tool calls.

---

### Scene 2: Running the Automated Test Suite (2 mins)
- Open the integrated terminal in VS Code.
- Run the test suite:
  ```bash
  python -m unittest discover -s tests -v
  ```
- Highlight to the reviewer:
  - 9 out of 9 tests passing.
  - Validation catches malformed emails and invalid phone numbers.
  - Duplicate detection blocks identical leads.
  - Hermes agent executes `lead_lookup` and `lead_status_update`.
  - Error handling gracefully recovers from invalid requests and missing IDs.

---

### Scene 3: Starting the REST API Server (2 mins)
- In the terminal, start the server:
  ```bash
  python backend/server.py
  ```
- Show server starting on `http://127.0.0.1:8000`.
- Show Healthcheck in browser or via curl:
  ```bash
  curl http://127.0.0.1:8000/health
  ```
- Send a valid lead POST request:
  ```bash
  curl -X POST http://127.0.0.1:8000/api/leads -H "Content-Type: application/json" -d "{\"name\": \"David Sterling\", \"email\": \"dsterling@apex.com\", \"phone_number\": \"+1-212-555-0143\", \"company\": \"Apex Logistics\", \"message\": \"Approved $50k budget. Urgent demo required.\"}"
  ```
- Show duplicate detection in action by sending the exact same curl command again:
  - Highlight the **HTTP 409 Conflict** response preventing duplicate creation!

---

### Scene 4: Demonstrating Task 2 (Ollama AI Triage) (2 mins)
- Trigger lead analysis endpoint:
  ```bash
  curl -X POST http://127.0.0.1:8000/api/leads/1/analyze
  ```
- Show the structured JSON returned:
  - `classification`: Hot Lead
  - `confidence_score`: 0.92
  - `business_intent`: Extracted enterprise requirements
  - `personalized_response`: Customized email drafted directly to David Sterling
  - `suggested_follow_up`: Discovery session scheduling

---

### Scene 5: Demonstrating Task 3 (Hermes AI Agent & Tool Execution) (2–3 mins)
- **Successful Agent Workflow**:
  - Send natural language command:
    ```bash
    curl -X POST http://127.0.0.1:8000/api/agent/execute -H "Content-Type: application/json" -d "{\"instruction\": \"Look up lead #1 and check their status\"}"
    ```
  - Show agent reasoning, tool selected (`lead_lookup`), and formatted reply.
- **Agent Status Update**:
  - Send status update command:
    ```bash
    curl -X POST http://127.0.0.1:8000/api/agent/execute -H "Content-Type: application/json" -d "{\"instruction\": \"Update lead #1 status to Qualified because they have an approved budget\", \"lead_id\": 1}"
    ```
  - Show audit entry written and status changed to `Qualified`.
- **Handling Invalid Request & Tool Failure (Mandatory Rubric Item)**:
  - Demonstrate invalid ID failure:
    ```bash
    curl -X POST http://127.0.0.1:8000/api/agent/execute -H "Content-Type: application/json" -d "{\"instruction\": \"Update lead #9999 to Qualified\", \"lead_id\": 9999}"
    ```
  - Show agent catching the `LEAD_NOT_FOUND` error code and responding calmly without crashing.

---

### Scene 6: Demonstrating Task 4 (n8n Workflow Automation) (2 mins)
- Open n8n interface (or show `n8n/lead_management_workflow.json` in VS Code / workflow diagram in `n8n/workflow_guide.md`).
- Walk through the 8 stages:
  1. Webhook Trigger (`/webhook/leads`)
  2. Validation Code node
  3. Duplicate Check HTTP Request
  4. Ollama Analysis node
  5. Hermes Agent workflow node
  6. Save status node
  7. Success response
  8. Global Error Trigger

---

### Scene 7: Demonstrating Task 5 (Gamma AI Report) (1–2 mins)
- Open Gamma.app in browser.
- Show the generated presentation created with `gamma/gamma_presentation_prompt.md`.
- Highlight key slides:
  - Total 15 leads processed
  - Distribution chart: 5 Hot (33.3%), 4 Warm (26.7%), 6 Cold (40.0%)
  - AI insights and customer requirements
  - Recommended follow-up actions

---

### Scene 8: Wrapping Up & Submitting
- Stop recording.
- Upload video file (e.g. `.mp4` or `.mkv`) to Google Drive.
- **CRITICAL**: Right-click video in Google Drive $\rightarrow$ Share $\rightarrow$ Set access to **"Anyone with the link can view"**!
