# OpenPoke 🌴

OpenPoke is a simplified, open-source take on [Interaction Company’s](https://interaction.co/about) [Poke](https://poke.com/) assistant—built to show how a multi-agent orchestration stack can feel genuinely useful. It keeps the handful of things Poke is great at (email triage, reminders, and persistent agents) while staying easy to spin up locally.

- Multi-agent FastAPI backend that mirrors Poke's interaction/execution split, powered by [OpenRouter](https://openrouter.ai/).
- Gmail tooling via [Composio](https://composio.dev/) for drafting/replying/forwarding without leaving chat.
- Trigger scheduler and background watchers for reminders and "important email" alerts.
- Next.js web UI that proxies everything through the shared `.env`, so plugging in API keys is the only setup.

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

### Tradeoffs and next steps

This baseline favors low cost, explainability, and safe abstention over broad semantic recall. It can miss paraphrases that share no vocabulary with an agent's name or recent request, and its synonym/entity rules are intentionally small. A production version could add vector retrieval, a learned reranker, richer entity extraction, and recent-agent caching after measuring those needs. Agent lifecycle management remains outside this change.

## License
MIT — see [LICENSE](LICENSE).
