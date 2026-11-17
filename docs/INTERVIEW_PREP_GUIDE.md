# Technical Discussion & Interview Defense Guide

In accordance with Guideline 7 (*"Be prepared for a follow-up technical discussion where you may be asked to explain your implementation, demonstrate the workflow, troubleshoot issues, or make minor modifications"*), this document prepares you with deep architectural reasoning and answers to expected interview questions.

---

## 🎯 High-Probability Questions & Model Answers

### Q1: "Why did you choose FastAPI / Pydantic / SQLAlchemy for the REST API?"
**Answer:**
> *"I chose Python with Pydantic and SQLAlchemy because in AI automation and LLM agent systems, type safety, structured data validation, and clean ORM mappings are essential. Pydantic ensures incoming payloads are validated before any expensive LLM calls occur, saving compute and preventing injection. SQLAlchemy provides a database-agnostic layer with thread-safe connection pooling, making it easy to develop with zero-setup SQLite locally and switch to PostgreSQL in production."*

---

### Q2: "How does Hermes function calling work under the hood?"
**Answer:**
> *"Nous Hermes models are fine-tuned on special token formats such as `<tools>` and `<tool_call>`. In our implementation (`backend/hermes_agent.py`), we feed the model tool schemas in JSON Schema format inside `<tools>` tags in the system prompt. When Hermes identifies that an external operation is required, it outputs an internal `<thought>` followed by `<tool_call>{\"name\": ..., \"arguments\": {...}}</tool_call>`.
> Our agent parser intercepts this block, validates the arguments against our tool registry (`backend/tools.py`), invokes the matching Python function, and returns the observation back to the model or user. If tool execution fails, our handler catches the exception and returns a structured error code, ensuring no corrupt state occurs."*

---

### Q3: "How did you prevent prompt injection or rogue agent actions?"
**Answer:**
> *"We follow the Principle of Least Privilege:
> 1. Strict tool whitelisting: The agent only has access to `lead_lookup` and `lead_status_update`. It has zero access to system commands, database deletion, or raw SQL execution.
> 2. Parameter state machine: In `lead_status_update`, the target status is strictly validated against an allowed enum (`New`, `Contacted`, `Qualified`, `Disqualified`).
> 3. Audit Logging: Every modification writes an immutable record to `lead_audit_logs` tracking the timestamp, old status, new status, justification reason, and the actor name (`HermesAgent`)."*

---

### Q4: "If Ollama goes down during high traffic, how does your system react?"
**Answer:**
> *"We designed a Circuit Breaker and Heuristic Fallback Engine in `backend/ollama_service.py`. When an HTTP timeout or connection refusal occurs, rather than throwing a 500 error or dropping the lead, the system catches the exception and routes the lead through `_fallback_heuristic_analyzer`. This applies rule-based keyword matching on commercial signals to classify the lead, drafts an initial response, and tags the record with `_source: fallback_heuristic_engine`. This guarantees 100% uptime and business continuity."*

---

### Q5: "How does n8n coordinate between the API, Ollama, and Hermes?"
**Answer:**
> *"n8n acts as the central orchestration plane. It ingests leads via webhook, runs payload validation in a code node, and checks for duplicates against the API. Next, it invokes the Ollama analysis endpoint to categorize the lead. Based on the categorization (e.g. Hot Lead), it delegates a reasoning task to the Hermes Agent endpoint, which decides to upgrade the status to Qualified and logs the audit reason. Finally, n8n responds to the webhook and routes any unexpected failures to an Error Trigger node."*

---

## 🛠️ Live Modification Drills (Things They Might Ask You to Change Live)

### Drill 1: "Add a new tool to Hermes Agent (e.g., `lead_assign_agent`)"
- **Where to change**: `backend/tools.py`
- **Steps**:
  1. Add function `execute_lead_assign(lead_id: int, assigned_rep: str, db)`
  2. Add JSON schema to `HERMES_TOOL_SCHEMAS`.
  3. In `backend/hermes_agent.py`, add the execution branch in `execute()`.

### Drill 2: "Add a new field to incoming leads (e.g., `budget`)"
- **Where to change**:
  1. `backend/models.py`: Add `budget = Column(Float, nullable=True)`.
  2. `backend/schemas.py`: Add `budget: Optional[float] = None` to `LeadCreate`.
  3. `backend/ollama_service.py`: Add budget to prompt string.
