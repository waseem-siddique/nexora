# API reference and viva guide

## API conventions

All endpoints are under `/api`. JSON responses return either data or `{ "error": "message" }`. A failed request does not silently create a fallback AI plan. Mutating requests require `Content-Type: application/json`, `X-Nexora-Request: 1`, and after login `X-CSRF-Token` from the authenticated session response. Cookies remain same-origin. The browser wrapper in `frontend/src/core.jsx` implements these conventions.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /health | Local server availability |
| GET | /session | Current user and CSRF token, or null user |
| POST | /auth/signup | name, email, password, institution |
| POST | /auth/login | email and password |
| POST | /auth/demo | Create isolated fictional workspace |
| POST | /auth/logout | Revoke current session and in-memory key |
| POST | /auth/password | current_password and new_password; rotate session |
| PATCH | /profile | name, institution, department and bio |
| GET | /workspace | Current owner's students, evidence, plans, progress, activity and course catalog |
| POST | /workspace/seed | Load synthetic cohort only into an empty workspace |
| GET | /settings | Provider configuration and key availability; never the secret |
| PATCH | /settings | provider, model, consent; optional api_key or clear_key |
| POST | /settings/test | Run selected provider on fictional evidence; no plan is saved |
| POST | /students | Create student profile |
| PATCH | /students/:id | Update profile after ownership check |
| DELETE | /students/:id | `{ "confirm": "DELETE" }`; cascade-delete related academic data |
| POST | /students/:id/evidence | course, score, attendance, completion, optional topic/notes/recorded_on |
| POST | /students/import | `{ "csv": "..." }`; all-or-nothing validated import |
| POST | /plans/generate | student_id, course, weeks; optional parent_id for revision |
| PATCH | /plans/:id | action: edit, approve, task, complete or archive |
| POST | /plans/:id/progress | score, attendance, completion, notes, recorded_on |

Plan edits accept title, objective, target_score, review_on, and a same-length activities list with title/description/due_on. Task actions accept index, completed and optional faculty_note. All plan transitions verify current state and ownership. Approving a plan archives an existing active plan for the same student/course. A revision can only refer to an active parent with follow-up evidence; only one pending revision draft is allowed for that parent.

## Viva questions and honest answers

**What makes this agentic rather than a chatbot?**  
A bounded controller coordinates specialized evidence validation, risk assessment, resource retrieval, plan generation and faculty review with shared structured state. Implementation and follow-up evidence feed the next planning iteration. It is workflow-style agentic orchestration, not a claim of fully autonomous independent agents.

**Where is generative AI used?**  
The Gemini and Ollama planning adapters generate personalized objectives and activity explanations in a validated JSON structure. Risk, resources, authorization, state transitions and progress comparisons remain deterministic. Local rules mode is an explicitly labelled offline baseline, not generative AI.

**Why not let the LLM predict risk?**  
The prototype keeps support thresholds explainable and reproducible. There is no validated training dataset or calibrated risk model. The index summarizes observed metrics, not student potential.

**How does personalization work?**  
The selected course's evidence, learning-gap topic, score, attendance and assignment completion influence support targets and activities. An attendance support activity is added when appropriate. Generative mode can vary the academic explanations within the bounded schema. Curriculum resources are selected by course, not invented.

**How does the feedback loop work?**  
Every follow-up logs metrics against an approved plan and also updates the evidence store. The evaluator compares the latest assessment with that plan's original baseline, checks attendance, and recommends a next action. A revision is a separate draft. Faculty approval changes which plan is active.

**How are hallucinations limited?**  
Provider prompts exclude direct student identifiers; generated JSON is parsed and structurally validated; evidence IDs are attached; resource URLs are fixed in the catalog; basic unsafe phrases/links are rejected. These steps are imperfect. Faculty review is required and no outcome or grade is decided by the model.

**Why is an external AI key optional?**  
The project supports a deterministic offline demonstration without API usage, an eligible Gemini free-tier key, or local Ollama. This avoids requiring a paid subscription. Quotas, model availability and hardware limitations remain the operator's responsibility.

**Do the dashboard gains prove effectiveness?**  
No. Demo records are synthetic. Real observations are descriptive changes from a baseline; they do not establish that the intervention caused improvement. Controlled evaluation would be a separate study.

**How do you prevent users accessing another faculty's data?**  
The server identifies the owner through a session cookie and verifies user_id on each student and plan operation. SQL parameters prevent injection. The included HTTP tests attempt cross-account access and verify rejection.

**How is the API key stored?**  
Keys from Settings remain in the current session's server memory, never localStorage or SQLite. Logout, restart or password rotation removes their usability. Code configuration uses an ignored .env file restricted to a named faculty email. That file is not encrypted at rest and must be protected by the operator.

**What is the main limitation?**  
This is a localhost engineering prototype with heuristic thresholds and a bounded workflow. It does not include institutional SSO, multi-role collaboration, scheduled jobs, production transport, a trained risk model or a clinical/educational efficacy claim. Institutional deployment requires further security/privacy work and validation.

## Suggested 8-minute presentation

1. **0:00–0:45:** Problem context and title/logo/landing page.
2. **0:45–1:30:** Architecture diagram and explainable support index.
3. **1:30–2:30:** Open demo, inspect a student and evidence history.
4. **2:30–4:00:** Generate a draft; show agent trace and optional Gemini/Ollama settings.
5. **4:00–5:00:** Edit goal, approve, complete a task and add a faculty note.
6. **5:00–6:00:** Log a follow-up, inspect recommendation, draft/approve a revision.
7. **6:00–7:00:** Export a report, show profile/password page and mobile/dark themes.
8. **7:00–8:00:** Tests, privacy protections, honest limitations and future work.

## Provider references

- Gemini keys: https://aistudio.google.com/apikey
- Model availability: https://ai.google.dev/gemini-api/docs/models
- Current pricing/free-tier eligibility: https://ai.google.dev/gemini-api/docs/pricing
- Gemini API terms: https://ai.google.dev/gemini-api/terms
- Ollama local API: https://docs.ollama.com/api/generate
- Ollama structured outputs: https://docs.ollama.com/capabilities/structured-outputs

Live provider calls are user-configured and were not exercised with a personal key during project packaging. Automated tests mock external provider responses and validate the request shapes, minimization and error behavior. Use Save & test engine to verify your own configuration.

Developed by Batch - 8 of CSE-A
