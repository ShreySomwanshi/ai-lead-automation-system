# n8n Workflow Automation Guide: AI-Powered Lead Pipeline

This workflow implements **Task 4 (Workflow Automation)** of the Maxsource Technologies assessment.

---

## 8-Stage Architecture Overview

```mermaid
flowchart TD
    W[1. Webhook Ingest] --> V[2. Validate Payload]
    V -->|Valid| D[3. Duplicate & Ingest Check]
    V -->|Invalid| E1[Handle Invalid Request (400)]
    D -->|Duplicate| E2[Handle Duplicate Response (409)]
    D -->|New Lead| O[4. Ollama Lead Analysis]
    O --> H[5. Hermes Agent Tool Workflow]
    H --> S[6. Save Status & Audit Log]
    S --> R[7. Generate Success Response]
    ET[8. Global Error Trigger] --> L[Log & Alert Failed Execution]
```

---

## Detailed Node Breakdown

### 1. Receive a New Lead Through a Webhook
- **Node**: `1. Webhook - Ingest Lead` (`n8n-nodes-base.webhook`)
- **HTTP Method**: `POST`
- **Path**: `/webhook/leads`
- **Behavior**: Listens for incoming POST requests from contact forms, landing pages, or CRM integrations.

### 2. Validate Lead Information
- **Node**: `2. Validate Payload` (`n8n-nodes-base.code`)
- **Validation Rules**:
  - Checks presence of required non-empty fields: `name`, `email`, `phone_number`, `company`, `message`.
  - Runs RFC-compliant regular expression check on email format (`^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$`).
  - Routes invalid payloads to `Handle Invalid Request` (HTTP 400).

### 3. Check Whether the Lead Already Exists
- **Node**: `3. Ingest & Duplicate Check API` (`n8n-nodes-base.httpRequest`)
- **Target**: `POST http://127.0.0.1:8000/api/leads`
- **Logic**: Backend checks database constraints on `email` and `phone_number`.
  - If duplicate found: returns HTTP 409 Conflict.
  - If new: creates record with initial status `New` and classification `Pending`.
- **Node**: `Is Duplicate Lead?` (`n8n-nodes-base.if`) branches duplicate leads to `Handle Duplicate Response` (409) without re-processing.

### 4. Send Message to Ollama for Analysis
- **Node**: `4. Ollama Lead Analysis` (`n8n-nodes-base.httpRequest`)
- **Target**: `POST http://127.0.0.1:8000/api/leads/{{ $json.id }}/analyze`
- **Behavior**:
  - Sends lead message to local Ollama instance (e.g. `llama3.2` or `hermes3`).
  - Classifies into: `Hot Lead`, `Warm Lead`, or `Cold Lead`.
  - Extracts customer requirements and business intent.
  - Crafts a customized, personalized email response.
  - Persists analysis to database.

### 5. Execute Required Agent Workflow
- **Node**: `5. Hermes Agent Tool Workflow` (`n8n-nodes-base.httpRequest`)
- **Target**: `POST http://127.0.0.1:8000/api/agent/execute`
- **Instruction**:
  - Natural language reasoning prompt sent to Hermes Agent:
    `"Evaluate lead #{{ $json.lead_id }} ({{ $json.analysis.classification }}). If Hot, transition status to Qualified. If Warm, set to Contacted. If Cold, set to Disqualified."`
  - Agent evaluates logic, selects `lead_status_update` tool, and executes status transition.

### 6. Save Analysis and Lead Status
- **Node**: `6. Save Status & Audit Log` (`n8n-nodes-base.httpRequest`)
- **Target**: `PATCH http://127.0.0.1:8000/api/leads/{{ lead_id }}/status`
- **Behavior**: Verifies status mutation, saves audit timestamp, reason, and actor (`n8n_Hermes_Pipeline`).

### 7. Generate a Notification or Response
- **Node**: `7. Generate Success Response` (`n8n-nodes-base.respondToWebhook`)
- **Behavior**: Returns structured JSON response to the webhook caller:
  ```json
  {
    "status": "success",
    "message": "Lead successfully ingested, triaged by Ollama, and processed by Hermes Agent.",
    "lead_id": 1,
    "classification": "Hot Lead",
    "final_pipeline_status": "Qualified"
  }
  ```

### 8. Handle Errors and Failed Executions
- **Node**: `8. Global Error Trigger` (`n8n-nodes-base.errorTrigger`)
- **Node**: `Log & Alert Failed Execution` (`n8n-nodes-base.code`)
- **Behavior**: Catches workflow runtime exceptions (timeouts, network drops, server errors), formats alert JSON, logs execution ID, and prevents silent failures.

---

## How to Import into n8n

1. Open your local or cloud n8n dashboard (e.g., `http://localhost:5678`).
2. Click **Add Workflow** (`+`) $\rightarrow$ Click the **Three Dots (...)** in the top right $\rightarrow$ Select **Import from File**.
3. Choose `n8n/lead_management_workflow.json`.
4. Click **Save** and **Activate**.
