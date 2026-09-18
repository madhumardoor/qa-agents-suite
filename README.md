# 5 AI QA Agents Suite - 2026

Five working AI-powered QA automation agents, each runnable standalone,
each supporting a **mock mode** (zero API keys, runs instantly) and a
**live mode** (real integrations: Jira, Jenkins, TestRail, OWASP ZAP,
Slack, GitHub, Playwright, Claude/GPT).

| # | Agent | What it does |
|---|-------|---------------|
| 1 | [Test Case Generator](agent1_test_case_generator/) | Reads a PRD/Jira ticket → generates 30–50+ positive/negative/edge test cases → exports to TestRail |
| 2 | [Self-Healing Automation Agent](agent2_self_healing/) | Detects broken UI locators after a redesign, finds the best replacement via similarity scoring, updates a locator store |
| 3 | [Bug Report & Log Analyzer](agent3_bug_log_analyzer/) | Parses Jenkins CI failure logs, classifies root cause, auto-creates Jira bug tickets, posts a Slack summary |
| 4 | [API Test & Security Agent](agent4_api_security/) | Generates functional tests from an OpenAPI/Swagger spec, runs an OWASP ZAP security scan, produces one combined report |
| 5 | [Visual Regression & Accessibility Agent](agent5_visual_regression/) | Pixel-diffs screenshots against a baseline, runs WCAG 2.1 accessibility checks, posts a PR comment |

---

## Quick Start (Mock Mode — works immediately, no API keys)

```bash
# 1. Clone / unzip this project, then:
cd qa-agents-suite
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Copy the env template (mock mode is already the default)
cp .env.example .env

# 3. Run any agent
cd agent1_test_case_generator && python3 main.py --file mock_data/sample_prd.txt
cd ../agent2_self_healing      && python3 main.py --demo
cd ../agent3_bug_log_analyzer  && python3 main.py --log-file mock_data/sample_jenkins_log.txt
cd ../agent4_api_security      && python3 main.py --swagger mock_data/sample_swagger.json
cd ../agent5_visual_regression && python3 main.py --demo
```

Each agent prints its results to the console and writes reports/artifacts
to its own `output/` folder (git-ignored).

---

## Going Live

Every agent works off one shared switch: the `MODE` environment variable.

```bash
MODE=live python3 main.py ...
```

Live mode is **granular** — you don't need every integration filled in at
once. Open `.env` and fill in only the keys for the services you want to
connect. Any integration whose keys are blank automatically falls back to
its mock behavior (with a printed warning), so you can, for example, turn
on a real LLM for Agent 1 while still mocking TestRail.

### What each agent needs for full live mode

| Agent | Required for live mode |
|---|---|
| 1. Test Case Generator | `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`), `JIRA_*`, `TESTRAIL_*` |
| 2. Self-Healing Agent | `playwright install chromium` (no API keys — it's algorithmic) |
| 3. Bug/Log Analyzer | `JENKINS_*`, `JIRA_*`, `SLACK_BOT_TOKEN`, optionally an LLM key for richer summaries |
| 4. API Test & Security | A running OWASP ZAP daemon (`ZAP_API_URL`), the target API's base URL |
| 5. Visual Regression & A11y | `playwright install chromium`, `GITHUB_TOKEN` + `GITHUB_REPO` for PR comments |

See `.env.example` for the full list with comments.

### Installing Playwright browsers (Agents 2 & 5 live mode)

```bash
pip install playwright
playwright install chromium
```

### Running OWASP ZAP locally (Agent 4 live mode)

```bash
docker run -p 8080:8080 zaproxy/zap-stable zap.sh -daemon -host 0.0.0.0 -port 8080 -config api.disablekey=true
```

---

## Project Structure

```
qa-agents-suite/
├── .env.example              # copy to .env and fill in what you need
├── requirements.txt
├── README.md                 # this file
├── shared/
│   ├── config.py              # central mock/live switch, reads .env
│   └── llm_client.py           # unified Claude/OpenAI wrapper
├── agent1_test_case_generator/
│   ├── main.py                 # CLI entrypoint
│   ├── generator.py            # core test-case generation (mock + LLM)
│   ├── jira_client.py          # fetch PRD from Jira / post comment
│   ├── testrail_client.py      # export cases to TestRail / local CSV
│   ├── mock_data/sample_prd.txt
│   └── output/                 # generated reports land here
├── agent2_self_healing/
│   ├── main.py
│   ├── dom_analyzer.py         # real similarity-scoring algorithm
│   ├── locator_store.py        # persistent JSON locator store
│   ├── playwright_runner.py    # live-mode browser integration
│   └── mock_data/dom_before.html, dom_after.html
├── agent3_bug_log_analyzer/
│   ├── main.py
│   ├── log_parser.py           # regex/heuristic root-cause classifier
│   ├── jenkins_client.py
│   ├── jira_bug_creator.py
│   ├── slack_notifier.py
│   └── mock_data/sample_jenkins_log.txt
├── agent4_api_security/
│   ├── main.py
│   ├── spec_loader.py          # OpenAPI/Swagger parser
│   ├── functional_tests.py     # test generation + execution
│   ├── zap_client.py           # OWASP ZAP integration
│   └── mock_data/sample_swagger.json
├── agent5_visual_regression/
│   ├── main.py
│   ├── visual_diff.py          # real Pillow pixel-diff + heatmap
│   ├── a11y_checker.py         # real WCAG 2.1 contrast-ratio math
│   ├── github_client.py        # PR comment poster
│   └── mock_data/ (sample screenshots + HTML)
└── docs/
    └── QA_Agents_Architecture.docx
```

---

## Why Mock Mode Is a Real Feature, Not a Placeholder

Every mock path in this suite runs genuine logic against realistic sample
data — nothing is faked or hardcoded to "look" like it works:

- **Agent 2** runs a real attribute/text similarity-scoring algorithm
  (weighted `difflib.SequenceMatcher` across tag, id, name, class,
  placeholder, data-testid) — it correctly re-locates elements after a
  simulated UI redesign.
- **Agent 5** performs real pixel-level image diffing with Pillow and
  computes actual WCAG 2.1 relative-luminance contrast ratios (verified:
  black-on-white = exactly 21:1, matching the spec).
- **Agent 3** uses real regex-based log parsing and a rule engine to
  classify root causes (timeout, null reference, assertion mismatch, auth
  failure, etc.) from raw CI log text.
- **Agent 1**'s mock generator parses numbered acceptance criteria from
  any PRD and expands each into positive/negative/edge cases — it's not
  limited to the bundled sample.
- **Agent 4** generates real functional test cases (status, schema, auth,
  injection, rate-limit) from any OpenAPI/Swagger spec you point it at.

This means the entire suite is demo-ready and interview-ready today, and
upgrading to live mode is a matter of filling in `.env` — no code changes.

---

## Extending

- Add a new LLM provider: edit `shared/llm_client.py`.
- Add a new root-cause rule to Agent 3: add a tuple to `ROOT_CAUSE_RULES`
  in `agent3_bug_log_analyzer/log_parser.py`.
- Add a new accessibility rule to Agent 5: add a check function in
  `agent5_visual_regression/a11y_checker.py`.
- Wire Agent 4 into CI on a schedule: see the GitHub Actions example below.

### Example: Running Agent 4 on a schedule (GitHub Actions)

```yaml
name: API Security Scan
on:
  schedule:
    - cron: "0 3 * * *"   # nightly at 3am
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: |
          cd agent4_api_security
          MODE=live python3 main.py --swagger ${{ vars.SWAGGER_URL }} --target ${{ vars.API_BASE_URL }}
        env:
          ZAP_API_URL: ${{ secrets.ZAP_API_URL }}
```

---

## License

Internal/demo use. Adapt freely for your own QA org.
