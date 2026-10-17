# Track B RAG Evaluation Notes

## Evaluation setup

- **Scorer:** RAGAS with the Bedrock judge `us.anthropic.claude-haiku-4-5-20251001-v1:0` in `us-east-1`.
- **Cases:** Four built-in offer test cases: Gold (`CUST-10000317`), Bronze (`CUST-10000904`), Platinum (`CUST-10000122`), and Silver (`CUST-10000588`).
- **Metrics:** faithfulness, answer relevancy, and context recall. Each score is on a 0–1 scale; higher is better, but the metrics measure different properties and are not policy-compliance guarantees.
- **Saved full runs:** `rag_eval_20261015T225738.csv` (earlier) and `rag_eval_20261015T225907.csv` (later; copied to `rag_eval.csv`).
- **Repeat scoring:** `rag_eval_after_repeat.csv` rescored the later run's saved answers and contexts. It is not another generation run.

The two full-run CSVs contain the same four generated answers. In the later CSV, the evaluation `contexts` also include a serialized customer profile; the earlier CSV contains retrieved policy text only. This is an evaluation-input change, not evidence that the answer generator or policy retrieval improved. In particular, a profile can help RAGAS match profile-related ground-truth details even though it is not a retrieved policy chunk.

## Full-run scores by case

Values below are transcribed from the two saved full-run CSVs. The “earlier” and “later” labels refer to those artifacts, not to a proven generation-pipeline improvement.

| Case | Faithfulness earlier → later | Answer relevancy earlier → later | Context recall earlier → later |
|---|---:|---:|---:|
| Gold — `CUST-10000317` | 0.400 → 0.560 | 0.462 → 0.462 | 0.750 → 0.750 |
| Bronze — `CUST-10000904` | 0.185 → 0.407 | 0.466 → 0.466 | 0.400 → 0.400 |
| Platinum — `CUST-10000122` | 0.160 → 0.440 | 0.381 → 0.381 | 0.333 → 0.333 |
| Silver — `CUST-10000588` | 0.192 → 0.346 | 0.000 → 0.000 | 0.500 → 1.000 |
| **Mean** | **0.234 → 0.438** | **0.327 → 0.327** | **0.496 → 0.621** |
| **Range** | **0.160–0.400 → 0.346–0.560** | **0.000–0.466 → 0.000–0.466** | **0.333–0.750 → 0.333–1.000** |

### Repeat-score variability

The later run's saved answers and contexts were scored again in `rag_eval_after_repeat.csv`. Faithfulness mean was **0.413** (range **0.346–0.538**), compared with **0.438** on the first scoring. For example, the Gold case changed from 0.560 to 0.360 and the Platinum case from 0.440 to 0.538. Answer relevancy and context recall stayed the same in this repeat. This illustrates that faithfulness is an LLM-judge estimate and can vary between scoring passes; interpret small differences cautiously.

## What the metrics tell us—and what they miss

### Faithfulness

Faithfulness estimates whether claims in an answer are supported by the supplied contexts. It does **not** independently verify the retailer's complete policy or whether the answer is a useful retention offer. Chunk boundaries and missing policy details can leave the generator without support, and the generator can still add unsupported claims. The judge can also vary between runs, as the repeat scores show.

Examples from the saved examples document:

- The earlier Gold failure framed existing gear repairs and sale access as a new “bonus” and invented activation instructions. The benefits exist, but the policy context did not authorize those offer mechanics.
- Another Gold answer said “keep your Gold status strong,” implying that a purchase maintains tier status without support for that promise. Removing that phrase fixed the specific issue.
- The separate Silver smoke test said products could “sell out,” an unsupported scarcity claim. This is not one of the four scored harness cases.

### Answer relevancy

Answer relevancy estimates how closely the answer addresses the question. It does **not** establish factual accuracy, policy compliance, or retrieval quality. In these runs the Silver case (`CUST-10000588`) scored 0.000 while the other cases scored 0.381–0.466. That outlier merits review of the saved answer and the metric's judgment; it should not be treated by itself as proof of a particular cause. The metric values are identical between the two full runs because the generated answers are identical.

### Context recall

Context recall estimates how much of the reference answer's information is present in the supplied evaluation contexts. It is sensitive to chunking, retrieval strategy, and how the reference is written. It is not a direct measure of answer quality. In the later full run, Silver recall rose from 0.500 to 1.000 after the customer profile was appended to the evaluation contexts. Since the generated answer and retrieved policy chunks did not change, this increase should **not** be presented as a retrieval improvement. For a retrieval-only comparison, score policy chunks separately from customer-profile data and keep the evaluation inputs consistent.

## Retrieval-strategy comparison

`retrieval-strategy-comparison.csv` compares context recall on the same four built-in cases:

| Strategy | Mean context recall |
|---|---:|
| Tier-focused | 0.446 |
| Constraint-focused | 0.050 |
| Hybrid | 0.446 |

Tier-focused and hybrid tied on this small sample; constraint-focused performed worse against these references. This does not show that tier-focused retrieval is generally superior: there are only four cases, and the result depends on these queries, chunks, references, and the judge. Hybrid may still retrieve important policy limits that the reference cases do not reward. The comparison is exploratory evidence, not a broad ranking of strategies.

## Measured before/after change: profile added to the evaluation context

The change between the two full harness runs was to the **context passed to the RAGAS judge**: the later run appended a serialized customer profile to each case's retrieved policy contexts. The earlier run passed policy chunks only. The generator prompt, generated offers, and retrieved policy chunks were unchanged; the saved answer text is identical case by case. This was an evaluation-context change, not a change to offer generation or policy retrieval.

| RAGAS metric | Before: policy chunks only | After: policy chunks + customer profile | Change | Did it help? |
|---|---:|---:|---:|---|
| Faithfulness (mean) | 0.234 | 0.438 | +0.204 | Helped the judge recognize claims grounded in the customer profile; the repeat score was 0.413, so the gain is not perfectly stable. |
| Answer relevancy (mean) | 0.327 | 0.327 | +0.000 | No change. |
| Context recall (mean) | 0.496 | 0.621 | +0.125 | Increased because the judge could now see profile facts included in the reference; this is not evidence of better policy retrieval. |

The result is mixed: adding profile context made faithfulness and context recall scores higher, while answer relevancy did not move. The answer and retrieval behavior did not improve; the judge simply received additional evidence when scoring. Treat these as before/after scores for the **evaluation-context change**, not as proof that the RAG offer pipeline itself improved. The full per-case scores and ranges are in the table above, and both full-run CSVs plus the repeat score file are saved alongside this note.

## Separate retrieval-strategy experiment

The retrieval-strategy comparison is a different experiment. It evaluates tier-focused, constraint-focused, and hybrid policy retrieval using context recall only; tier-focused and hybrid both averaged 0.446, while constraint-focused averaged 0.050. On these four cases, hybrid did not improve mean context recall over tier-focused retrieval. This small exploratory comparison does not establish a general retrieval winner or a change to the generated offers. See `retrieval-strategy-comparison.csv` for per-case scores.

## Evidence files

- `rag_eval.csv` — later full harness output (four cases, answers, contexts, references, and scores).
- `rag_eval_20261015T225738.csv` — earlier full harness output.
- `rag_eval_20261015T225907.csv` — later full harness output before it was copied to `rag_eval.csv`.
- `rag_eval_after_repeat.csv` — repeat scores for the later run; includes the judge model ID.
- `retrieval-strategy-comparison.csv` — per-case context-recall comparison for tier, constraints, and hybrid retrieval.
- `track-b-examples.md` — example inputs/outputs and two failure cases with concrete fixes.
