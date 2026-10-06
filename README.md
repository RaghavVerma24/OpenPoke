# OpenPoke 🌴

OpenPoke is a simplified, open-source take on [Interaction Company’s](https://interaction.co/about) [Poke](https://poke.com/) assistant—built to show how a multi-agent orchestration stack can feel genuinely useful. It keeps the handful of things Poke is great at (email triage, reminders, and persistent agents) while staying easy to spin up locally.

## Project overview
- Multi-agent FastAPI backend that mirrors Poke's interaction/execution split, powered by [OpenRouter](https://openrouter.ai/).
- Gmail tooling via [Composio](https://composio.dev/) for drafting/replying/forwarding without leaving chat.
- Trigger scheduler and background watchers for reminders and "important email" alerts.
- Next.js web UI that proxies everything through the shared `.env`, so plugging in API keys is the only setup.

## Take-home: reducing agent overload

**Problem:** As persistent agents accumulate, asking the Interaction Agent to
consider the whole roster makes its decision context grow with the agent count.

**Change:** Add a deterministic retrieval step that ranks compact agent
profiles before the Interaction Agent runs. The current router returns at most
four candidates and abstains below its confidence threshold; the Interaction
Agent still makes the final choice.

```text
Original: user request -> Interaction Agent + all N agent profiles -> chosen agent
New:      user request -> router -> at most K profiles
          -> Interaction Agent -> chosen agent
```

**Measured on the fixed 40-query, 10-agent evaluation:** Recall@1/3 93.8%,
no-match accuracy 100%, false reuse 0%, and mean downstream exposure 1.90 vs.
10 agents (81% fewer). These are deterministic router metrics, not live LLM
answer-quality results. The scale check measures bounded exposure; retrieval
itself remains a linear scan, as discussed below.

## Demo: three validation flows

Use these three paired flows to walk through the same types of requests in
the original architecture and with the router. They are based on
the deterministic 10-agent evaluation fixture. Run it from the repository
root with:

```powershell
python server/tests/evaluate_router.py
```

The candidate scores shown are actual outputs for these sample requests.
They are relative ranking signals, not calibrated probabilities. The
original-flow path is conceptual: the evaluator does not call an LLM to
measure old-flow answer accuracy. The distinction is not whether profiles are
compact: the original Interaction Agent could receive compact profiles too,
but it still receives all N of them; the router limits what reaches it to K.

### 1. Clear match: Alice's email

Request: **“Did Alice ever respond about lunch?”** The fixture includes
`Alice Email`, `Alice Calendar`, and other unrelated agents.

```text
ORIGINAL
User request
    |
    v
Interaction Agent sees all 10 agents
    |
    v
Chooses Alice Email

ROUTER APPROACH
User request
    |
    v
Router ranks compact profiles
    |
    +-- Alice Email       0.697 (rank 1)
    +-- Alice Calendar    0.528
    +-- Mom Email         0.275
    |
    v
Interaction Agent sees shortlist
    |
    v
Alice Email execution agent
```

**Demo point:** Both approaches can reach the correct agent. The new flow
makes retrieval an explicit step and gives the Interaction Agent a shortlist.
On the full 40-query evaluation, Recall@1 and Recall@3 are both 93.8% (MRR
0.938). Recall@K means the expected agent is present in the first K results;
it does not mean the agent completed the task correctly.

### 2. Entity and task collision: email versus calendar

Request: **“Schedule a meeting with Alice.”** Two persistent agents relate to
Alice, but only one handles scheduling.

```text
ORIGINAL
User request
    |
    v
Interaction Agent sees all 10 agents
    |
    v
Must distinguish Alice Email from Alice Calendar
    |
    v
Chooses Alice Calendar

ROUTER APPROACH
User request
    |
    v
Router scores entity + task terms
    |
    +-- Alice Calendar    0.807 (rank 1)
    +-- Alice Email       0.623
    |
    v
Interaction Agent sees shortlist
    |
    v
Alice Calendar execution agent
```

**Demo point:** The shared entity alone is not enough; task vocabulary helps
rank Calendar ahead of Email. The router narrows the options, while the
Interaction Agent remains responsible for the final choice.

### 3. No suitable agent: abstain

Request: **“Find a plumber near me.”** There is no plumbing agent in the
fixture.

```text
ORIGINAL
User request
    |
    v
Interaction Agent sees all 10 agents
    |
    v
Must decide whether to reuse or create

ROUTER APPROACH
User request
    |
    v
Router: no profile reaches threshold 0.29
    |
    v
Returns no candidates
    |
    v
Interaction Agent sees no reusable match
    |
    v
Create an agent or clarify the request
```

**Demo point:** The threshold gives the router an explicit abstention path,
instead of always returning the least-wrong existing agent. On the evaluator's
no-match examples, no-match accuracy is 100% and false reuse is 0%. These are
router metrics; the evaluator does not prove that a live Interaction Agent
will always create the right new agent.

### What happens as the roster grows? Where does an index fit?

The current scale check pads the fixture with unrelated agents and records
profiles exposed to downstream reasoning:

| Roster size | Original: all profiles | Router: mean candidates | Router: maximum |
| ---: | ---: | ---: | ---: |
| 10 | 10 | 1.90 | 4 |
| 50 | 50 | 1.95 | 4 |
| 100 | 100 | 1.95 | 4 |
| 500 | 500 | 1.95 | 4 |

On the 10-agent fixture this is 81% fewer agent candidates passed downstream;
estimated context-word reduction is 20%. The word estimate uses names and
compact summaries, not a tokenizer. This scale test uses synthetic distractors
and measures exposure, not latency or recall on a newly labeled 500-agent set.

Be clear about two different kinds of scaling. The router bounds the
Interaction Agent's context to at most K candidates (K defaults to 4), but the
prototype still scores every profile, so its retrieval computation is O(N).
It does not currently use an index or claim lower retrieval latency.

For production, profiles could be indexed when agents are created or updated.
A lexical inverted index maps terms to profiles; a vector approximate
nearest-neighbor (ANN) index can find semantically similar profiles. The query
would retrieve a candidate pool, optionally rerank it, then pass the final
Top-K to the Interaction Agent. An index trades memory and profile-update
work for query-time search savings. It is not automatically O(log N): exact
nearest-neighbor search can remain O(N), and ANN performance depends on the
index, data, and configuration. I would add one only after measuring
retrieval latency at realistic roster sizes, and evaluate Recall@K, abstention,
freshness, and latency together.


## Requirements
- Python 3.10+
- Node.js 18+
- npm 9+

## Quickstart
1. **Clone and enter the repo.**
   ```bash
   git clone https://github.com/shlokkhemani/OpenPoke
   cd OpenPoke
   ```
2. **Create a shared env file.** Copy the template and open it in your editor:
   ```bash
   cp .env.example .env
   ```
3. **Get your API keys and add them to `.env`:**
   
   **OpenRouter (Required)**
   - Create an account at [openrouter.ai](https://openrouter.ai/)
   - Generate an API key
   - Replace `your_openrouter_api_key_here` with your actual key in `.env`
   
   **Composio (Required for Gmail)**
   - Sign in at [composio.dev](https://composio.dev/)
   - Create an API key
   - Set up Gmail integration and get your auth config ID
   - Replace `your_composio_api_key_here` and `your_gmail_auth_config_id_here` in `.env`
4. **(Required) Create and activate a Python 3.10+ virtualenv:**
   ```bash
   # Ensure you're using Python 3.10+
   python3.10 -m venv .venv
   source .venv/bin/activate
   
   # Verify Python version (should show 3.10+)
   python --version
   ```
   On Windows (PowerShell):
   ```powershell
   # Use Python 3.10+ (adjust path as needed)
   python3.10 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   
   # Verify Python version
   python --version
   ```

5. **Install backend dependencies:**
   ```bash
   pip install -r server/requirements.txt
   ```
6. **Install frontend dependencies:**
   ```bash
   npm install --prefix web
   ```
7. **Start the FastAPI server:**
   ```bash
   python -m server.server --reload
   ```
8. **Start the Next.js app (new terminal):**
   ```bash
   npm run dev --prefix web
   ```
9. **Connect Gmail for email workflows.** With both services running, open [http://localhost:3000](http://localhost:3000), head to *Settings → Gmail*, and complete the Composio OAuth flow. This step is required for email drafting, replies, and the important-email monitor.

The web app proxies API calls to the Python server using the values in `.env`, so keeping both processes running is required for end-to-end flows.

## Project Layout
- `server/` – FastAPI application and agents
- `web/` – Next.js app
- `server/data/` – runtime data (ignored by git)

## Agent routing

The Interaction Agent previously received every execution-agent name on every turn. As that roster grows, the model has more context to inspect and more chances to reuse an unrelated agent.

OpenPoke now ranks existing agents before building the Interaction Agent message. The deterministic router searches the agent name and a short summary derived from up to eight recent log entries (only the latest request is retained in the searchable profile). It uses lexical overlap plus a small synonym map and named-entity overlap. It returns at most four candidates by default, and abstains when the best score is below `0.29`. With no match, the Interaction Agent is told to create a new agent for a new task rather than forcing reuse.

Set `OPENPOKE_AGENT_ROUTER_TOP_K` to choose a candidate limit from 1 to 5 and `OPENPOKE_AGENT_ROUTER_THRESHOLD` to tune confidence from 0 to 1. Defaults are 4 and 0.29. No external package or vector database is required.

### Tests and evaluation

Run the router and message-context tests, plus the evaluator, from the repository root:

```powershell
python -m unittest discover -s server/tests -p "test*.py"
python server/tests/evaluate_router.py
```

The evaluator includes 40 labeled queries across exact and paraphrased matches, entity and topic collisions, and unrelated requests. It compares candidate exposure with the existing full-roster behavior, which exposes all 10 fixture agents for each query. The current results are:

| Measure | Result |
| --- | ---: |
| Recall@1 / Recall@3 | 93.8% / 93.8% |
| MRR | 0.938 |
| False reuse rate on no-match queries | 0% |
| No-match accuracy | 100% |
| Mean agents exposed (baseline: 10) | 1.90 |
| Agent-count exposure reduction | 81.0% |
| Estimated context-word reduction | 20.0% |

The evaluator also pads the same fixture to 10, 50, 100, and 500 agents. It exposed a mean of 1.90, 1.95, 1.95, and 1.95 candidates respectively, with a hard maximum of four. The synthetic scale run measures bounded exposure and is not a latency benchmark. Context-word reduction is an estimate from names and compact summaries, not a tokenizer measurement.

There is no pre-existing automated server test suite in this checkout. The router unit tests and evaluator use only Python's standard library; the message-context integration tests use the app's installed backend dependencies. All tests are deterministic. Live model and Gmail flows still need valid API credentials.

### Local smoke test (Windows PowerShell)

Run these commands from the repository root with the Python virtual environment activated. If using the `.venv-openpoke` environment created for this Windows setup, replace `python` with `.\.venv-openpoke\Scripts\python.exe`.

1. Run automated checks:
   ```powershell
   python -m unittest discover -s server\tests -p "test*.py"
   python server\tests\evaluate_router.py
   ```
2. Start the backend in one terminal:
   ```powershell
   python -m server.server --reload
   ```
3. In a second terminal, start the frontend:
   ```powershell
   npm run dev --prefix web
   ```
   If npm is unavailable but `web\node_modules` is already installed, start Next from its project directory:
   ```powershell
   Set-Location web
   .\node_modules\.bin\next.cmd dev --hostname 127.0.0.1 --port 3000
   ```
4. Check the backend health endpoint and open the chat UI:
   ```powershell
   Invoke-RestMethod http://127.0.0.1:8001/api/v1/health
   Start-Process http://localhost:3000
   ```

The health endpoint should return `ok: true`; the chat page should load. The automated tests exercise ranking, confidence abstention, top-K limits, and the exact agent context sent to the Interaction Agent without making a paid model call.

### Tradeoffs and next steps

This baseline favors low cost, explainability, and safe abstention over broad semantic recall. It can miss paraphrases that share no vocabulary with an agent's name or recent request, and its synonym/entity rules are intentionally small. A production version could add vector retrieval, a learned reranker, richer entity extraction, and recent-agent caching after measuring those needs. Agent lifecycle management remains outside this change.

## License
MIT — see [LICENSE](LICENSE).
