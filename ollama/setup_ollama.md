# Ollama Setup & Configuration Guide (Task 2 & Deliverable Details)

This document details the configuration, models, and execution instructions for the local LLM runtime powering the Lead Management & Automation System.

---

## 1. Prerequisites & Installation

### Windows Installation
1. Download the Ollama Windows installer from [ollama.com/download](https://ollama.com/download).
2. Run `OllamaSetup.exe` and follow on-screen prompts.
3. Ollama will start automatically in your system tray on `http://localhost:11434`.

---

## 2. Recommended Models

For this assessment, two models are configured and supported:

| Role | Recommended Model | Command | Strengths |
| :--- | :--- | :--- | :--- |
| **Lead Analysis & Triage (Task 2)** | `llama3.2:3b` or `llama3.2:1b` | `ollama pull llama3.2` | High-speed structured JSON generation, low VRAM footprint (~2.5GB). |
| **Hermes AI Agent (Task 3)** | `hermes3:8b` or `nous-hermes2` | `ollama pull hermes3` | Native support for `<tools>` and `<tool_call>` agent trajectories. |

---

## 3. Creating the Custom Model with the Provided Modelfile

A custom tuned model `lead-triage-agent` is defined in `ollama/Modelfile`. To build and register it locally:

```bash
cd ollama
ollama create lead-triage-agent -f ./Modelfile
```

Verify the model is registered:
```bash
ollama list
```

---

## 4. Testing Ollama Lead Analysis Directly

You can test the Ollama REST endpoint directly via curl or PowerShell:

```bash
curl -X POST http://localhost:11434/api/generate -d '{
  "model": "lead-triage-agent",
  "prompt": "Incoming Lead Details:\n- Name: Sarah Miller\n- Company: Nexus Global\n- Message: We need an urgent quote for 250 enterprise licenses and demo by Thursday.\",
  "stream": false,
  "format": "json"
}'
```

---

## 5. Built-in Circuit Breaker & Fallback Architecture

To satisfy **Problem-Solving Challenge #1** (*What happens if Ollama is unavailable?*):
- If the Ollama server is offline or downloading models, the backend automatically invokes the heuristic classifier (`backend/ollama_service.py:_fallback_heuristic_analyzer`).
- No lead submission will ever crash, hang, or be dropped.
- The system logs an audit note indicating fallback mode was used and marks the response with `_source: fallback_heuristic_engine`.
