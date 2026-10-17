import ast
import sys
from pathlib import Path

import pandas as pd
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_recall

# Running a file under scripts/ puts that directory, not the repo root, on
# sys.path. Add the root so the harness module can be imported reliably.
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from evaluation_harness import (
    DEFAULT_BEDROCK_MODEL_ID,
    OFFER_TEST_CASES,
    build_bedrock_judge,
)

input_path = ROOT_DIR / "docs/lab3-evidence/rag_eval_20261015T225907.csv"
output_path = ROOT_DIR / "docs/lab3-evidence/rag_eval_after_repeat.csv"
source = pd.read_csv(input_path)

dataset = Dataset.from_dict({
    "question": source["user_input"].tolist(),
    "answer": source["response"].tolist(),
    "contexts": [ast.literal_eval(value) for value in source["retrieved_contexts"]],
    "ground_truth": source["reference"].tolist(),
})

judge, embeddings = build_bedrock_judge(DEFAULT_BEDROCK_MODEL_ID, "us-east-1")
scores = evaluate(
    dataset,
    metrics=[faithfulness, answer_relevancy, context_recall],
    llm=judge,
    embeddings=embeddings,
).to_pandas()

results = pd.DataFrame({
    "customer_id": [case.customer_id for case in OFFER_TEST_CASES],
    "judge_model": DEFAULT_BEDROCK_MODEL_ID,
    "faithfulness": scores["faithfulness"],
    "answer_relevancy": scores["answer_relevancy"],
    "context_recall": scores["context_recall"],
})
results.to_csv(output_path, index=False)
print(results.to_string(index=False))

for metric in ["faithfulness", "answer_relevancy", "context_recall"]:
    values = results[metric].dropna()
    print(f"{metric}: mean={values.mean():.3f}, range={values.min():.3f}-{values.max():.3f}")

print(f"Saved: {output_path}")
