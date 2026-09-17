# Architecture and project rationale

## Problem statement

**PS-014 — Automated Academic Intervention Planning.** Faculty can identify struggling students but often lack time to prepare individualized interventions. The system converts academic evidence into support plans, tracks implementation and recommends changes from follow-up evidence.

**Title:** Nexora — Academic Intervention Studio  
**Tagline:** Every student. A clearer path forward.  
**Team attribution:** Developed by Batch - 8 of CSE-A

## Implemented architecture

```text
Browser: React SPA + responsive CSS + native SVG charts
                         |
                  Same-origin JSON API
              HttpOnly session + CSRF header
                         |
          Python standard-library HTTP server
        Accounts | Student CRUD | CSV | Plan actions
                         |
        Bounded agent workflow / shared JSON state
                         |
 Evidence -> Assessment -> Resource -> Planning -> Review gate
                                          |             |
                                 Rules / Gemini / Ollama|
                                                        v
                                              Faculty approval
                                                        |
                                                Active checklist
                                                        |
                                          Dated progress observations
                                                        |
                                 Progress evaluator -> Draft revision
                                                        |
                                                 Faculty approval
                         |
      SQLite: users, sessions, students, evidence, plans,
                    progress, activity
```

The agentic element is **bounded workflow orchestration** with specialized components, shared structured state, provider/tool calls, measurable feedback and a mandatory human approval transition. The five stages are auditable. This does not claim multiple independent LLM personalities, autonomous background scheduling, reinforcement learning or unrestricted agent execution. The execution trace is a record of operations and outcomes, not hidden chain-of-thought.

## Agent responsibilities

1. **Evidence agent:** validates 0–100 percentages; selects the latest dated evidence for the requested course; attaches an evidence ID.
2. **Assessment agent:** derives an explainable support index and course-level threshold signals. It does not let the model assign or modify risk.
3. **Resource agent:** retrieves the course's curated learning resource from a fixed catalog. No model-generated links are permitted.
4. **Planning agent:** creates a bounded 1–8 week intervention. Local rules use deterministic evidence-driven templates. Gemini/Ollama can generate narrative activities through a schema-constrained JSON response.
5. **Review gate:** requires faculty approval. Before approval, the goal, target, date and activity content are editable. Drafts cannot record implementation.
6. **Progress evaluator:** compares the latest logged follow-up with the plan baseline; recommends review/adjustment/continuation. A requested revision reruns the workflow against the latest evidence. Approval archives previous active support for the same course and student.

## State machine

```text
Draft -> Active -> Completed
   |        |         |
   +--------+---------+--> Archived

Active + follow-up -> new Draft (parent reference, revision + 1)
New Draft approval -> old Active archived; new draft becomes Active
```

Only active plans accept progress and activity completion. All activities must be checked before completion. Closing a plan does not mean its learning target was met. Archived plans are read-only through the UI. Existing evidence is append-only; deleting a student removes all their related evidence, plans and progress. Faculty activity logs preserve operational history without storing provider credentials.

## Data model

- **users:** faculty account, unique email, PBKDF2 password hash, institution, department, bio, settings, demo flag.
- **sessions:** SHA256 hash of a random session token, CSRF token, owning user, expiration. Cookie token itself is not stored in the database.
- **students:** owner user, name, roll, semester, section, optional email, synthetic flag. Roll is unique within an owner workspace.
- **evidence:** student reference, course, assessment, attendance, assignment completion, topic, local faculty note, observed date and creation timestamp.
- **plans:** owner/student/course, status, revision, parent plan, structured plan JSON, creation/update timestamps.
- **progress:** plan reference, evidence reference, academic metrics, local note, observed date, timestamp. Every check-in also creates an evidence record.
- **activity:** owner, operation title, detail, entity reference and timestamp.

Foreign keys and cascade deletes preserve referential integrity. Write transitions use transactions. Every student/plan mutation checks ownership. Model calls are bounded and serialize per user to avoid simultaneously generating multiple drafts. The initial implementation targets a small departmental demonstration, not a large distributed SaaS deployment.

## Support index and chart methodology

For each course's latest evidence:

`index = .55 × (100 − score) + .30 × (100 − attendance) + .15 × (100 − completion)`

The student's index is the rounded equal-weight average of observed courses. **Priority ≥45; Watch ≥25 and <45; On track <25.** No evidence means no index. Course-level explanations flag score <50, attendance <75, and completion <60. These are demonstration support thresholds, not institutional pass rules. They can be adjusted in `backend/domain.py` after validation.

The overview trend uses weekly as-of checkpoints over four weeks: latest record per observed course, mean per student, then equal-weight mean across students with evidence. The cohort can change across checkpoints. There is no future interpolation. The latest assessment-change card averages the latest follow-up minus the individual baseline for active plans with observations; it is measured in **percentage points**, not relative percent change.

Progress recommendations:
- No follow-up: collect evidence.
- Assessment decreases OR attendance <60: revise support.
- Assessment gain <5 points: adjust approach.
- Otherwise: continue and review.

These are descriptive rules, not causal inference, a validated predictive model or an automatic educational decision.

## Privacy and security boundaries

- PBKDF2-HMAC-SHA256: 600,000 iterations, independent random salts.
- Random HttpOnly, SameSite=Strict cookies; 12-hour sessions; configurable Secure flag for HTTPS.
- CSRF header plus same-origin/custom-header checks; host allowlist for localhost binding.
- Parameterized SQL, workspace ownership checks, bounded request sizes and rate limits.
- React escapes text; generated HTML is not executed; restrictive Content Security Policy.
- Browser-entered keys are session-scoped server memory only. Environment key use requires an explicit owning account email.
- Cloud prompt receives minimized metrics/topic; identifiers and private faculty notes are excluded.
- Ollama endpoint is operator-configured, not an arbitrary user-entered network URL.
- Strict structural validation and a basic support-only keyword/link guardrail. This guardrail is not a complete safety guarantee; faculty approval remains necessary.
- Demo data is fictional and isolated. No automatic email, messaging, grading or discipline.

## Technology choices

React provides reusable interactive views; esbuild creates a compact locally served bundle. Pure Python minimizes setup and demonstrates explicit orchestration rather than framework magic. SQLite permits an offline one-command demo. The API adapters use standard-library HTTPS/HTTP requests instead of paid SDK services. The prebuilt bundle is included; npm is only needed to change frontend source.

## Academic evaluation plan (not claimed completed)

Evaluate on consented/de-identified or synthetic cases with faculty review: plan relevance, actionability, evidence fidelity, curriculum alignment, time to draft, inappropriate assumptions, and revision quality. Compare faculty-only planning, local rules, Gemini and Ollama using the same evidence. Use multiple independent reviewers, a predefined rubric, response latency and error rates. Actual learning outcomes require prospective study and cannot be inferred from this demo's synthetic improvement records.

## Future work

Validated thresholds and uncertainty reporting; institutional SSO and role separation; encryption at rest and managed secrets; background scheduling; instructor collaboration; larger evidence stores and semantic retrieval; syllabus-specific resources; accommodations reviewed by authorized staff; notification integrations with consent; controlled longitudinal effectiveness evaluation; load testing and hardened deployment.
