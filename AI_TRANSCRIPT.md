# AI Assistant Prompts & Workflow Log

This log records the prompts and technical directives used while building the Clinic Front Desk Agent.

## Day 1 — Tool Layer & Ground Truth Architecture
- *"Let's read clinic.json, schema.md, and runner.py. We need to implement the 6 tools: search_slots, book_appointment, reschedule_appointment, cancel_appointment, lookup_patient, and escalate_to_human."*
- *"The tool layer must be completely pure Python and never call an LLM. All slots, working windows, doctor leaves, and holidays must be computed deterministically from clinic.json."*
- *"How do we prevent double-booking if two calls race for the same slot? Let's implement an in-memory RLock around slot reservations so concurrent requests are mutually exclusive."*
- *"Write pytest unit tests for all 6 tools, testing holiday closures, doctor leave on 2026-10-09, ambiguous patient lookup returning all candidates, and a multithreaded concurrency test with 10 threads racing for the same slot."*

## Day 2 — Clinical Safety Shield & Deterministic Intent Engine
- *"The brief has one hard rule: if a caller mentions any emergency symptoms like chest pain or shortness of breath, the agent must immediately stop the booking and escalate with reason 'clinical_urgent'."*
- *"Let's build a dedicated safety triage module that checks caller utterances for emergency symptoms, requests for medical advice, unauthorized third-party actions (like a neighbor trying to cancel), and prompt injection attempts."*
- *"We need to parse relative dates ('kal', 'parso', 'Shanivaar') strictly against the 'today' field in the request. Never use datetime.now()."*
- *"Handle mid-sentence mind changes, like when a caller starts with Tuesday 6th but corrects to Wednesday 7th."*
- *"Expose POST /agent/run using FastAPI and make sure the response matches schema.md exactly."*
- *"Write 8 adversarial conversation scripts in /adversarial that would break a naive agent (e.g. public holiday booking pressure, masked heart attack symptoms, ambiguous first name without phone, prompt injection database dump)."*

## Day 3 — Frontend Console & Verification
- *"Build the React console with Vite and Tailwind matching the exact two screens from the brief: Screen 1 (Handoff Queue) and Screen 2 (Conversation Detail) with the shared persistent sidebar."*
- *"In the Conversation Detail screen, show the dialogue transcript with inline tool call cards showing the arguments and returned outputs, plus the Outcome panel with the determinism STABLE badge."*
- *"Run python runner.py --repeat 3 on all 15 conversations and the 8 adversarial conversations to verify 100% determinism."*
