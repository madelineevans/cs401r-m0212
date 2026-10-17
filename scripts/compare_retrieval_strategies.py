from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import context_recall

from evaluation_harness import OFFER_TEST_CASES, build_bedrock_judge
from rag.build_index import load_local_faiss_index, retrieve_by_strategy


index, chunks = load_local_faiss_index()

rows = []
for strategy in ("tier", "constraints", "hybrid"):
    for case in OFFER_TEST_CASES:
        hits = retrieve_by_strategy(
            case.customer_context, index, chunks,
            strategy=strategy, k=4,
        )
        rows.append({
            "strategy": strategy,
            "customer_id": case.customer_id,
            "question": case.question,
            "answer": "",
            "contexts": [chunk.text for chunk, _ in hits],
            "ground_truth": case.ground_truth,
        })

dataset = Dataset.from_list(rows)
judge_llm, judge_embeddings = build_bedrock_judge(
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    region="us-east-1",
)
scores = evaluate(
    dataset,
    metrics=[context_recall],
    llm=judge_llm,
    embeddings=judge_embeddings,
).to_pandas()

scores["strategy"] = [row["strategy"] for row in rows]
scores["customer_id"] = [row["customer_id"] for row in rows]

print(scores[["strategy", "customer_id", "context_recall"]].to_string(index=False))
print("\nMean context recall by strategy:")
print(scores.groupby("strategy")["context_recall"].mean().sort_values(ascending=False))

output = ROOT / "docs" / "lab3-evidence" / "retrieval-strategy-comparison.csv"
scores.to_csv(output, index=False)
print(f"\nSaved: {output}")