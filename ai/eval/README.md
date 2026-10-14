# Evaluation

`run_eval.py` measures the AI module end to end with **real models** (it costs API calls).
It ingests `eval/docs/` into an isolated org (`eval-org`, role `eval`), runs every question in
`dataset.jsonl` through `service.run`, scores the router on `routing.jsonl`, and writes
`eval/results/<timestamp>[-label].json` plus a summary table.

## 1. Prepare the data

**Documents** go in `eval/docs/` (pdf, docx, pptx, xlsx). Aim for 8–10 realistic company
documents: a policy PDF, a project report, meeting transcripts, a spreadsheet and so on.

**Questions** go in `dataset.jsonl`, one JSON object per line. Aim for 30–40 questions, about 8 of them unanswerable.

```json
{"question": "How many days of paid annual leave do employees get?", "expected_doc": "hr_policy.pdf", "expected_answer_keywords": ["24 days"], "answerable": true}
{"question": "What is the company's parental leave policy?", "expected_doc": null, "expected_answer_keywords": [], "answerable": false}
```

| field | meaning |
|---|---|
| `expected_doc` | file name in `eval/docs/` that contains the answer (`null` if unanswerable) |
| `expected_answer_keywords` | short facts the answer must contain (numbers, names); matching ignores case, `*`, and thousands commas |
| `answerable` | `false` = the documents do **not** contain the answer, so the system must refuse |

Good unanswerable questions are *near misses*, topics close to your documents but not in them
("parental leave" when only annual leave is covered). They test grounding much harder than
off-topic trivia.

**Routing cases** go in `routing.jsonl`:
```json
{"query": "Summarize this meeting and email the action items to the team", "expected_agents": ["meeting", "email"], "transcript": true}
{"query": "Summarize this file", "expected_agents": ["document"], "selected_docs": 1}
```

## 2. Run

```powershell
docker compose up -d                                    # Qdrant must be running
uv run python eval/run_eval.py                          # ingest + QA + routing + judge
uv run python eval/run_eval.py --skip-ingest --no-judge # faster re-run, same docs
```

Options: `--route` (send QA through the router instead of forcing the research agent),
`--pause 3` (more spacing if you hit rate limits), `--label name` (results file suffix),
`--docs/--dataset/--routing` (other paths).

## 3. Metrics

| metric | definition |
|---|---|
| `hit@k` | share of answerable questions whose `expected_doc` is among the k sources shown (k = `FINAL_K`) |
| `keyword_recall` | share of expected keywords found in the answer (refused answers excluded) |
| `false_refusal_rate` | share of answerable questions the system wrongly refused |
| `refusal_accuracy` | share of unanswerable questions correctly refused ("I couldn't find this…") |
| `groundedness_1to5` | fast-model judge: are the answer's claims supported by the retrieved sources? |
| `router_accuracy` | share of routing cases where the planned agent sequence matches exactly |
| `avg/p95_latency_s`, `avg_tokens` | per question, from the `done` event (judge calls not included) |

## 4. Tune one setting at a time

Every results file records the config it ran with. Change **one** setting per run, label it, then compare:

```powershell
uv run python eval/run_eval.py --label baseline
$env:SCORE_THRESHOLD="0.70"; uv run python eval/run_eval.py --skip-ingest --label thr070
$env:FINAL_K="3";            uv run python eval/run_eval.py --skip-ingest --label k3
$env:CHUNK_SIZE="400";       uv run python eval/run_eval.py --label chunk400   # re-ingest!
Remove-Item Env:SCORE_THRESHOLD, Env:FINAL_K, Env:CHUNK_SIZE                  # reset

uv run python eval/run_eval.py --compare eval/results/*-baseline.json eval/results/*-thr070.json
```

`--compare` prints the settings that differ, then every metric side by side. That is your
before/after table. A chunk-size change requires re-ingesting, so don't pass `--skip-ingest`.

**What to expect:** a higher `SCORE_THRESHOLD` refuses more cheaply (fewer tokens, better
refusal accuracy) but can start missing real answers (`hit@k` and `false_refusal_rate` get worse).
Pick the value where refusal accuracy is high and false refusals stay near zero.

## Notes

- Rate limits: the smart model allows about 30 requests/min on the current Mistral plan; the default
  `--pause 2` keeps a 40-question run within that. A full run takes roughly 3–5 minutes.
- `eval/results/` is git-ignored. Copy the runs you report (baseline and best) somewhere permanent, or
  commit them with `git add -f`.
- Answers vary slightly between runs; for the final report, run the best config twice and report both.
