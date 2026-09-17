# Nexora — KITS Academic Success Hub

**PS-014 · Automated Academic Academic Planning**  
B.Tech CSE Major Project · Agentic AI & Generative AI  
**Developed by Batch - 8 of CSE-A**

A local-first KITS Singapur / JNTUH R23 CSE academic intelligence prototype that converts performance evidence into personalized support plans, tracks implementation, and proposes adjustments from subsequent progress. Includes a responsive React dashboard, custom vector logo, light/dark themes, and a working Python/SQLite backend.

## Start in one command

1. Extract the ZIP fully (do not run it from inside the archive).
2. Install **Python 3.10 or newer** if you do not already have it.
3. Open a terminal in the extracted `nexora` folder:

```bash
python run.py
```

On macOS/Linux, use `python3 run.py`. On Windows, `py -3 run.py` also works, or double-click `start.bat`. On macOS/Linux you can run `sh start.sh`.

4. Open **http://localhost:8000**.
5. Click **Explore live demo** for an isolated fictional CSE workspace, or create an account for an empty personal workspace.

**No npm installation, Python packages, API key, paid subscription, database server, or internet access is needed for this quick start.** A compiled React frontend is included. The default **Local rules** engine is deterministic and is explicitly **not generative AI**. Connect Gemini or local Ollama below to demonstrate language-model generation.

## What is implemented

- Product landing page and original embedded Nexora SVG logo; required footer on every page.
- Faculty signup/login/logout, profile edits, password changes, and local account recovery.
- Private, account-scoped SQLite workspaces; temporary isolated demo accounts with synthetic data.
- Overview dashboard with computed cohort counts, support groups, evidence trend, upcoming tasks and review queue.
- Student creation/edit/deletion; search, semester filters, transparent support index and evidence history.
- Atomic CSV import, template download, duplicate detection, range validation and CSV export.
- Course-specific intervention generation with five auditable workflow stages.
- Editable draft objectives, targets, review dates, activity instructions and due dates.
- Faculty approval gate, implementation checklists and faculty notes.
- Progress check-ins, baseline comparisons, adjustment recommendations, revision history and archival.
- One active intervention per student/course; approving a replacement archives the previous active plan.
- CSE resource catalog covering DSA, DBMS, OS, CN, SE and ML.
- Global search, live review inbox, error/empty states, keyboard-accessible dialogs, mobile navigation.
- Markdown/JSON intervention exports, progress/student CSV export, print/Save as PDF layout.
- Light/dark toggle on public and app pages; browser-local theme preference only.
- Google Gemini and local Ollama adapters; server-side keys, consent gate, structured output validation.
- Unit/integration tests and project documentation, including architecture and viva notes.

## Demonstrate the complete workflow

1. Open the demo. All 12 students and six plans are fictional and labelled accordingly.
2. Open **Students → a student → Evidence history** to inspect the data.
3. Choose **Create intervention**, select a student and a course with evidence, then generate.
4. Read **Agent activity**: Evidence → Assessment → Resource → Planning → Review gate.
5. Edit the draft if needed; click **Approve plan**. No messages or grades are changed.
6. Mark activities complete and record a faculty note.
7. Click **Log progress**, enter comparable follow-up percentages and save.
8. Open **Progress & adaptation**; inspect the baseline comparison and draft a revision.
9. Approve the revision to archive the previous plan without losing its history.
10. Export the plan, switch themes, and demonstrate mobile navigation.

## Option A — Google Gemini (eligible free-tier account)

1. Get a key from https://aistudio.google.com/apikey .
2. Verify the model's **current** free-tier availability and your project quota at https://ai.google.dev/gemini-api/docs/pricing . Use a project without paid billing for free-tier experiments. Nexora cannot inspect your billing tier or guarantee a zero bill on a billing-enabled project.
3. Open **AI settings → Google Gemini**.
4. Enter the API key and a currently supported, free-tier model ID. The editable default is `gemini-2.5-flash`; availability changes, so replace it if Google reports that the model was removed or is unavailable.
5. Read and enable the cloud-evidence consent checkbox.
6. Click **Save & test engine**. The test uses only synthetic metrics. Then create an intervention.

Settings-entered keys are held in **server memory for the current session**, never returned in an API response, stored in localStorage, or written to SQLite. Sign out or restart the server to forget the key. Enter it again in a new session.

### Configure from your code editor instead

Copy `.env.example` to `.env` in the project root, then edit:

```dotenv
GEMINI_API_KEY=your_real_key
GEMINI_MODEL=gemini-2.5-flash
ENV_KEY_OWNER_EMAIL=your-account@example.com
AI_PROVIDER=rules
```

Restart the server, sign in with the exact account email above, open AI settings, select Gemini and enable consent. Environment keys are restricted to the specified **personal** account, not demo accounts. User-saved settings override defaults. The .env file is ignored by Git; do not include it in submissions or shared ZIPs.

**Privacy:** Gemini receives course metrics, evidence dates and the learning-gap topic; no name, roll, email or private faculty note is transmitted. Do not put identifying information in the topic. Free-tier data may be used to improve Google's products; verify https://ai.google.dev/gemini-api/terms and institutional policy. Demonstrate with synthetic data. The app does not silently fall back to a paid provider on errors or exhausted quota.

## Option B — Local Ollama (no AI API charges)

1. Install Ollama: https://ollama.com/download .
2. Download a local model, for example:

```bash
ollama pull qwen2.5:3b
```

3. Ensure Ollama is running (`ollama serve` only if a service is not already running).
4. In Nexora AI settings, select **Local Ollama**, enter `qwen2.5:3b`, and save/test.

The default endpoint is `http://127.0.0.1:11434`; change `OLLAMA_BASE_URL` in .env only if needed by the server operator. Use a **local downloaded** model; cloud-named models are rejected. Model downloads need internet; inference runs locally after download. Hardware/RAM and electricity are still required. Small models may return invalid structured drafts; retry, select a more capable local model or use rules mode. Local request timeout is 120 seconds.

## Edit the React source

Install Node.js 20+ (tested with Node 24). Then, from the project root:

```bash
npm install
npm run build
python run.py
```

For automatic rebundling during development:

```bash
# Terminal 1
python run.py
# Terminal 2
npm run dev
```

Refresh the browser after saving a source file. This is an esbuild watcher, not a Vite hot-reload server. Both development and built UI use the same origin at port 8000. There are no remote fonts, CDN runtime dependencies or externally loaded UI scripts.

## Data and imports

SQLite is created at `data/nexora.sqlite3` on first run. Faculty accounts are independent; this prototype does **not** include student/parent accounts, an admin tenant hierarchy, email verification, SMTP, SMS or calendar integration.

CSV headers:

```csv
name,roll,semester,section,course,score,attendance,completion,topic,notes,recorded_on
Sample Student,CS001,5,A,DSA,45,70,55,Recursion,Synthetic record,
```

Required columns are the first eight. Optional: email, topic, notes, recorded_on. Dates use YYYY-MM-DD; blank means the server's current calendar date. All percentages must be 0–100. Semester must be an integer 1–8. Use one student/course/date per CSV row. All-or-nothing imports reject conflicting student details and existing same-day/course evidence. Files are limited to 500 KB and 500 rows. Use the in-app template or `samples/`.

To reset the entire local instance: stop the server, back up any required records, then delete the `data` folder. This permanently removes accounts and academic data. Never delete data while the server is running.

## Tests

```bash
python -m unittest discover -s tests -v
```

Tests create a temporary database and local HTTP server. They cover risk math, missing/invalid evidence, agent stages, consent and data minimization, mocked Gemini/Ollama adapters, authorization/CSRF, account/password workflows, atomic imports, revision approval, task completion and demo seeding. They do **not** call a real paid or free AI endpoint. Live generation depends on your key/quota or installed local model.

## Important limitations and responsible use

This is a complete **local engineering-project implementation**, not a production-certified institutional system. Risk thresholds are transparent heuristics, not a trained or calibrated predictor. Improvement comparisons are descriptive, not proof of causal effectiveness. Faculty must verify generated content; the schema and keyword guardrail cannot guarantee all model text is safe or pedagogically correct.

No automated grading, discipline, admissions, diagnosis or student messaging occurs. Nexora implements a bounded sequential agentic workflow with shared state and explicit human approval, **not** autonomous agents independently running in the background. The Progress evaluator runs when data is viewed/logged or a revision is requested, not on a scheduler.

Use synthetic data for your demonstration. A real deployment needs institutional consent, retention policies, HTTPS, a hardened application server/reverse proxy, backups, privacy review, access-role design, monitoring and testing. The bundled standard-library HTTP server binds to localhost and is for a local demonstration. SameSite/HttpOnly cookies, CSRF, salted password hashing and scoped SQL queries are implemented but do not make the prototype production-ready.

## Project structure

```text
nexora/
  run.py                       One-command local entry point
  backend/server.py            HTTP routes, accounts, authorization, CRUD
  backend/domain.py            Agents, risk, evaluation and AI adapters
  backend/storage.py           SQLite schema and synthetic demo records
  frontend/src/                React components and design system
  frontend/public/             HTML entry, logo and theme initialization
  frontend/dist/               Prebuilt offline-ready frontend
  scripts/build.mjs            esbuild bundling and watch mode
  scripts/reset_password.py    Interactive local account recovery
  tests/test_app.py            Automated tests (temporary database)
  samples/                     Evidence import sample
  docs/                        Architecture, API reference, viva guide
  .env.example                 Key and server configuration template
```

## Troubleshooting

- **Python not found:** install Python 3.10+ and enable PATH; use `py -3` on Windows or `python3` on macOS/Linux.
- **Port 8000 in use:** stop the other process or set `NEXORA_PORT=8001` in .env; then visit port 8001.
- **Cannot sign in:** demo accounts have no fixed password; use Explore live demo again. For a personal account, run `python scripts/reset_password.py` from the server computer.
- **No course to generate:** add an evidence record for the selected student first.
- **Gemini key missing after restart:** expected for session keys. Re-enter it or use the account-scoped .env option.
- **Gemini quota/model error:** check current model/free-tier access; use Local rules or local Ollama. No paid fallback is used.
- **Ollama unreachable:** run Ollama on the same computer as the Nexora backend, and verify `ollama list` shows the configured model.
- **Frontend missing/stale:** `npm install` then `npm run build`, and refresh the browser.
- **Cloud consent required:** enable it in AI settings, or choose an offline/local mode.

Developed by Batch - 8 of CSE-A
