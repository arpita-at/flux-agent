# flux-agent

**flux-agent is an open-source month-end flux commentary agent for finance teams.** It reads actuals, budget and prior period, decides which variances are material, retrieves the postings behind each one, and drafts the "why did this move" sentence. Matching and materiality are deterministic rules. A model only writes the sentence, and only from evidence it was handed.

Sample data is synthetic. There are no real cost centres or ledgers in this repo.

```
actuals + budget + prior ──┐
                           ├─► variance engine   (rules)   what moved, and by how much
ledger / journals / POs ───┘
                           ──► materiality rule  (rules)   40 lines become the 12 that matter
                           ──► evidence lookup   (rules)   the postings behind each one
                           ──► drafter           (claude)  names the cause, cites the docs
                           ──► your review       (human)   nothing ships unreviewed
```

---

## What is flux commentary?

Flux commentary, also called flux analysis or variance commentary, is the written explanation that goes next to each line of a month-end pack. It answers four questions for every material variance:

| | Question |
|---|---|
| 1 | What moved |
| 2 | Why it moved |
| 3 | Was it rate, volume, timing or a one-off |
| 4 | Does it repeat next month |

Nobody reads a number they can already see in the row above. They read the cause. That makes flux commentary a writing task sitting on top of a data task, which is why it eats so much of close week.

## Why not just paste the variance report into ChatGPT?

Because it will answer. Confidently. You gave it a number and no evidence, and inventing a plausible reason is the only way to answer a question like that.

The fix is not a better prompt. It is a retrieval step in front of the model, and a hard rule that a line with no supporting postings is returned as a gap rather than a sentence:

```python
def test_a_line_with_no_evidence_is_never_explained():
    text, cites, gap, by = draft(LINE, None, [])
    assert gap is True
    assert text == ""
```

That test is the whole design in four lines.

## What does the model actually do?

| Stage | Who | Why |
|---|---|---|
| Join actuals, budget, prior | rules | A join. Deterministic, testable |
| Decide what is material | rules | A threshold is a policy, not a judgement call |
| Compute rate / volume / joint | rules | Arithmetic. It must tie exactly |
| Retrieve supporting postings | rules | A filter. The model gets no ledger access |
| **Name the cause, draft the sentence** | **claude** | Genuine ambiguity. This is what models are good at |
| Review, edit, approve | human | Accountability does not move to software |

The model never touches a number. It writes the sentence about the number.

With no `ANTHROPIC_API_KEY` set, the drafter falls back to deterministic template sentences built from the same decomposition and evidence. The pack still ships. Failing closed beats failing clever when there is a deadline.

## How is materiality decided?

Both tests must pass, or the ceiling must be breached:

```python
abs(variance) >= ceiling                                   # always explain
or (abs(variance) >= floor and abs(variance / budget) >= pct)
```

The `and` is the point. With `or`, a cost centre that budgeted 500 and spent 2,000 lands in the pack every single month at 300% and tells nobody anything.

Defaults are `floor=25,000`, `pct=0.10`, `ceiling=500,000`. Pass your own.

## How is a variance split into rate and volume?

The classic price-volume decomposition:

```
variance = P1*Q1 - P0*Q0
rate     = (P1 - P0) * Q0
volume   = (Q1 - Q0) * P0
joint    = (P1 - P0) * (Q1 - Q0)
```

Those three terms sum to the variance exactly, for any inputs. `tests/test_variance.py` asserts it across five cases including zeros and awkward decimals. If that assertion ever fails, every number in the pack is wrong, so it fails loudly.

## Run it

Python 3.11 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000 and click **Run the demo**.

Optional, for Claude-drafted sentences instead of template ones:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Run the tests:

```bash
pytest -q        # 23 passed
```

## What the demo returns

Eight sample lines, three flagged, 98.4% of the total movement explained:

| Cost centre | Account | Variance | Commentary |
|---|---:|---:|---|
| CC-4300 | 7100 | 578,500 | Driven by a single posting, PO-30211, annual licence renewal booked in full |
| CC-4100 | 6200 | 68,200 | Driven by a single posting, JE-88120, contractor rate uplift. Mostly rate, around 93% of the movement |
| CC-4200 | 7100 | -33,700 | Driven by a single posting, JE-88140, campaign deferred to November |

`coverage` is the share of total variance the pack accounts for. Under about 80% means the materiality rule is set too loose to be useful, and the pack is explaining noise while missing the story.

## API

| Method | Path | Does |
|---|---|---|
| `GET` | `/` | The demo page |
| `GET` | `/healthz` | Liveness |
| `POST` | `/api/demo` | Runs the synthetic sample end to end |
| `POST` | `/api/pack` | Your four CSVs: `actuals`, `budget`, `prior`, `ledger` |

CSV columns: `cost_centre,account,amount` for the three period files, and `doc_id,cost_centre,account,amount,posted_on,description,source` for the ledger.

## FAQ

**Does this post anything to my ERP?** No. It returns a draft pack. Nothing in this repo writes to a ledger, sends an email or takes any action.

**Can it work without an API key?** Yes. The deterministic path is the default and covers everything except the drafted sentence.

**Does it work with SAP?** It reads CSV. Export from FAGLL03, FS10N, or any report that gives you cost centre, account and amount. There is no SAP connector here on purpose; an export is auditable and a live connection is a much bigger security conversation.

**Why not let the model do the matching too?** Because a model right 99% of the time is wrong on a balance sheet, and you cannot write a regression test for a vibe. If it must tie to the penny, it is a rule.

**Is the sample data real?** No. Synthetic, generated for this repo.

**I want to deploy this somewhere.** Set `FLUX_API_TOKEN` first, then send `Authorization: Bearer <token>`. Without it both endpoints are open, and every flagged line can cost one model call, so an open endpoint with a key set is somebody else's bill. Other limits: `FLUX_MAX_BYTES` (2 MB per file), `FLUX_MAX_ROWS` (20,000), `FLUX_MAX_DRAFTS` (25 model calls per run, the tail falls back to deterministic sentences). Materiality is validated too, because `floor=0&pct=0` would flag every line.

## Licence

Apache-2.0.

---

Built by [Arpita Tiwari](https://www.linkedin.com/in/arpita-tiwari-5b955a307). FP&A and record to report by day, agents for finance workflows in my own time. Tell me where the logic breaks.
