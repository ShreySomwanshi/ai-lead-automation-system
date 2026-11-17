"""
Hermes AI Agent Implementation (Task 3).
Demonstrates agent-based reasoning, dynamic tool selection, parameter extraction,
and resilient error handling using Hermes function-calling conventions.
"""
import json
import re
import urllib.request
import urllib.error
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.tools import (
    HERMES_TOOL_SCHEMAS,
    execute_lead_lookup,
    execute_lead_status_update,
)

HERMES_SYSTEM_PROMPT = """You are Hermes, an autonomous AI Operations Agent specialized in enterprise CRM and lead automation.
You have access to the following tools:

<tools>
""" + json.dumps(HERMES_TOOL_SCHEMAS, indent=2) + """
</tools>

When the user asks you to inspect or modify leads, you MUST carefully reason about the user's intent.
If a tool is needed, respond with your reasoning followed by the tool call in this exact format:
<thought>
Your internal reasoning here
</thought>
<tool_call>
{"name": "<tool_name>", "arguments": {<args>}}
</tool_call>

If no tool is required, or after receiving the tool result, provide your clear, helpful final response.
Never invent arguments that weren't specified. Always handle errors calmly and professionally.
"""


class HermesAgent:
    """
    Hermes Agent Engine.
    Executes tool-calling workflows either by connecting to an Ollama hermes3 model,
    or using the resilient Hermes deterministic parser when running in local/test mode.
    """

    def __init__(self, model_name: str = "hermes3", ollama_host: str = "http://localhost:11434"):
        self.model_name = model_name
        self.ollama_host = ollama_host.rstrip("/")

    def _call_ollama_for_agent(self, prompt: str) -> Optional[str]:
        """Attempts to invoke Ollama running hermes3 or equivalent tool model."""
        payload = {
            "model": self.model_name,
            "system": HERMES_SYSTEM_PROMPT,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0}
        }
        url = f"{self.ollama_host}/api/generate"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data.get("response", "")
        except Exception:
            return None
        return None

    def _deterministic_reasoner(
        self, instruction: str, lead_id: Optional[int] = None, email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Deterministic reasoning fallback matching Hermes function-calling logic.
        Ensures 100% testability and demonstration even if Ollama is not pre-pulled.
        """
        text = instruction.lower().strip()

        # Extract explicit lead_id if mentioned in text (e.g., "lead 5" or "id #5")
        id_match = re.search(r"(?:lead\s*(?:id|#)?\s*|#)(\d+)", text)
        extracted_id = int(id_match.group(1)) if id_match else lead_id

        # Extract email if present
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", instruction)
        extracted_email = email_match.group(0) if email_match else email

        # Detect intent: Status update vs Lookup
        update_verbs = ["update", "change", "set", "mark", "upgrade", "downgrade", "qualify", "disqualify"]
        is_update = any(v in text for v in update_verbs)

        if is_update:
            # Determine target status
            target_status = None
            if "qualified" in text and "disqualified" not in text:
                target_status = "Qualified"
            elif "disqualified" in text:
                target_status = "Disqualified"
            elif "contacted" in text:
                target_status = "Contacted"
            elif "new" in text:
                target_status = "New"
            elif "hot" in text:
                # If user says "mark as hot", status transition maps to Qualified
                target_status = "Qualified"

            # Check for simulated invalid status request to demonstrate failure handling
            invalid_status_match = re.search(r"status\s+(?:to\s+)?['\"]?([a-zA-Z]+)['\"]?", text)
            if invalid_status_match and not target_status:
                target_status = invalid_status_match.group(1).capitalize()

            reason = f"Agent workflow execution for instruction: '{instruction}'"
            if "because" in text:
                reason = instruction.split("because", 1)[1].strip()

            if extracted_id is None:
                return {
                    "reasoning": "The user requested a lead status update, but no valid lead ID or identifier was specified.",
                    "tool": None,
                    "args": {},
                    "error": "Missing required parameter 'lead_id' for status update."
                }

            return {
                "reasoning": f"User requested to update lead {extracted_id} to status '{target_status}'. Selected tool 'lead_status_update'.",
                "tool": "lead_status_update",
                "args": {
                    "lead_id": extracted_id,
                    "new_status": target_status or "Unknown",
                    "reason": reason
                }
            }

        # Lookup intent
        lookup_verbs = ["look up", "lookup", "find", "get", "check", "fetch", "search", "show", "details"]
        is_lookup = any(v in text for v in lookup_verbs) or (extracted_id is not None and not is_update)

        if is_lookup:
            if not extracted_id and not extracted_email:
                return {
                    "reasoning": "The user wants to look up a lead, but neither a lead ID nor an email was provided in the prompt.",
                    "tool": None,
                    "args": {},
                    "error": "Missing lookup identifier (lead ID or email)."
                }

            args = {}
            if extracted_id is not None:
                args["lead_id"] = extracted_id
            if extracted_email:
                args["email"] = extracted_email

            return {
                "reasoning": f"User requested lead information for identifier ({args}). Selected tool 'lead_lookup'.",
                "tool": "lead_lookup",
                "args": args
            }

        return {
            "reasoning": "Instruction did not match known operations for lead lookup or status update.",
            "tool": None,
            "args": {},
            "error": "Unsupported or unrecognized request."
        }

    def execute(
        self,
        instruction: str,
        lead_id: Optional[int] = None,
        email: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Runs the Hermes agent loop:
        1. Formulates reasoning
        2. Selects tool
        3. Executes tool
        4. Handles failures gracefully
        5. Returns structured output
        """
        # Step 1: Attempt LLM reasoning if Ollama is accessible, else use deterministic Hermes engine
        raw_llm_response = self._call_ollama_for_agent(
            f"User Instruction: {instruction}\nTarget Lead ID: {lead_id}\nEmail: {email}"
        )

        plan = None
        if raw_llm_response:
            # Parse <thought> and <tool_call> tags
            thought_match = re.search(r"<thought>(.*?)</thought>", raw_llm_response, re.DOTALL)
            tool_match = re.search(r"<tool_call>\s*({.*?})\s*</tool_call>", raw_llm_response, re.DOTALL)
            if tool_match:
                try:
                    tool_json = json.loads(tool_match.group(1))
                    plan = {
                        "reasoning": thought_match.group(1).strip() if thought_match else "Analyzed user prompt via Hermes-3 model.",
                        "tool": tool_json.get("name"),
                        "args": tool_json.get("arguments", {})
                    }
                except Exception:
                    pass

        if not plan:
            plan = self._deterministic_reasoner(instruction, lead_id=lead_id, email=email)

        reasoning = plan.get("reasoning", "")
        tool_name = plan.get("tool")
        tool_args = plan.get("args", {})

        # Handle agent-level validation failure (e.g. invalid request)
        if not tool_name:
            err_msg = plan.get("error", "Could not determine an appropriate tool for this request.")
            return {
                "instruction": instruction,
                "agent_reasoning": reasoning,
                "tool_executed": None,
                "tool_input": None,
                "tool_result": {"status": "error", "message": err_msg},
                "final_response": f"Hermes Agent was unable to proceed: {err_msg}",
                "success": False
            }

        # Step 2: Execute selected tool
        tool_result: Dict[str, Any] = {}
        if tool_name == "lead_lookup":
            tool_result = execute_lead_lookup(
                lead_id=tool_args.get("lead_id"),
                email=tool_args.get("email"),
                db=db
            )
        elif tool_name == "lead_status_update":
            tool_result = execute_lead_status_update(
                lead_id=tool_args.get("lead_id"),
                new_status=tool_args.get("new_status"),
                reason=tool_args.get("reason", "Automated Hermes Agent workflow"),
                agent_name="HermesAgent",
                db=db
            )
        else:
            tool_result = {
                "status": "error",
                "error_code": "UNKNOWN_TOOL",
                "message": f"Tool '{tool_name}' is not recognized or permitted."
            }

        # Step 3: Handle tool success or failure to synthesize final response
        is_success = tool_result.get("status") == "success"

        if is_success:
            if tool_name == "lead_lookup":
                lead = tool_result.get("lead", {})
                final_text = (
                    f"Successfully retrieved lead records for {lead.get('name')} ({lead.get('company')}). "
                    f"Current Status: '{lead.get('status')}', Classification: '{lead.get('classification')}'. "
                    f"Requirements: {', '.join(lead.get('extracted_requirements') or ['None recorded'])}."
                )
            else:
                final_text = (
                    f"Successfully executed lead status update. "
                    f"Lead #{tool_result.get('lead_id')} status transitioned from "
                    f"'{tool_result.get('previous_status')}' to '{tool_result.get('new_status')}'. "
                    f"Reason recorded: '{tool_result.get('reason')}'."
                )
        else:
            # Demonstration of handling tool failures gracefully (Task 3 requirement)
            error_msg = tool_result.get("message", "Unknown error during tool execution.")
            error_code = tool_result.get("error_code", "GENERIC_ERROR")
            final_text = (
                f"Hermes Agent encountered a handled tool failure ({error_code}): {error_msg} "
                f"No state corruption occurred. Suggestion: Verify parameters and try again."
            )

        return {
            "instruction": instruction,
            "agent_reasoning": reasoning,
            "tool_executed": tool_name,
            "tool_input": tool_args,
            "tool_result": tool_result,
            "final_response": final_text,
            "success": is_success
        }
