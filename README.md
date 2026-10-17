# CS 401R Lab 3 — NorthStar Churn and Offer Generation

This repository contains the Lab 3 churn model (Track A), policy-grounded offer-generation RAG system (Track B), evaluation code, and saved evidence. The churn model is trained locally with XGBoost; a SageMaker training job is not required.

## Prerequisites

- Windows PowerShell, Python, and the project’s `cs401r-lab3` Conda environment.
- AWS CLI credentials in the `MaeAdmin` profile and the `us-east-1` region for AWS-backed data access, Bedrock evaluation, and artifact uploads.
- The Lab 1–2 AWS infrastructure and populated SageMaker Feature Store for a fresh Athena-backed training run. Those resources were torn down after this evidence was collected, so recreate them before rerunning that training path.

Set AWS defaults in PowerShell for a session:

```powershell
conda activate cs401r-lab3
$env:AWS_PROFILE = "MaeAdmin"
$env:AWS_DEFAULT_REGION = "us-east-1"
```

## Train and evaluate the churn model

The training script queries the Feature Store offline data through Athena, preprocesses the returned customer features, trains XGBoost, checks the required evaluation thresholds, registers the model, and logs the run to the configured MLflow App when `MLFLOW_APP_ARN` is set.

After restoring the Lab 1–2 infrastructure, run from the repository root. Replace the bucket name if using a different account:

```powershell
python -X utf8 .\churn_training_skeleton.py `
  --artifacts-bucket northstar-dev-data-722160254691 `
  --run-name xgb-depth6-eta0.1-final `
  --output-data-dir .\docs\lab3-evidence
```

The default model settings are depth 6, learning rate (`eta`) 0.1, and 200 boosting rounds. To try other settings, pass options such as `--max-depth 4`, `--eta 0.05`, or `--num-round 300`. Use `--local-data-path <csv>` only for local development checks; it bypasses the Feature Store and is not the Athena-backed training run documented here.

The script writes local model and evaluation outputs to `model/` and the directory passed to `--output-data-dir`. With the command above, evidence includes `docs/lab3-evidence/evaluation_metrics.json` and `docs/lab3-evidence/slice_evaluation.csv`; plots and the captured final log are also saved there. It uploads the model archive to `s3://<artifacts-bucket>/artifacts/models/churn/<timestamp>/model.tar.gz`, writes Athena query results under `artifacts/athena-results/`, and registers the model in the `northstar-churn-models` Model Registry group. MLflow run metadata is recorded in the configured MLflow App.

## Run Track B RAG evaluation

The RAG system builds/reuses a local FAISS index from `northstar-policy-docs/`, retrieves policy chunks, and generates offers with Amazon Bedrock. The evaluation harness runs the four built-in offer cases and scores faithfulness, answer relevancy, and context recall using its configured Bedrock judge. Bedrock inference can incur charges.

```powershell
python .\evaluation_harness.py --track B --output-dir .\evaluation_results --region us-east-1
```

The harness writes a timestamped `rag_eval_*.csv` to `evaluation_results/`. The submitted full-run output is preserved at [`docs/lab3-evidence/rag_eval.csv`](docs/lab3-evidence/rag_eval.csv); the judge model and score interpretation are recorded in [`docs/lab3-evidence/rag-eval-notes.md`](docs/lab3-evidence/rag-eval-notes.md). Rerunning the harness calls the model again and can produce different judge scores.

To reproduce the small retrieval-strategy comparison:

```powershell
python .\scripts\compare_retrieval_strategies.py
```

It writes `docs/lab3-evidence/retrieval-strategy-comparison.csv`. The comparison is exploratory and covers the four built-in cases; see the notes for limitations and interpretation.

## Evidence map

| Artifact | Purpose |
|---|---|
| `docs/lab3-evidence/evaluation_metrics.json` | Churn-model metrics and threshold results |
| `docs/lab3-evidence/slice_evaluation.csv` | Model performance by customer slice |
| `docs/lab3-evidence/confusion-matrix.png`, `feature-importance.png` | Churn-model evaluation visuals |
| `docs/lab3-evidence/rag_eval.csv` | Saved Track B full-harness answers, contexts, references, and RAGAS scores |
| `docs/lab3-evidence/rag-eval-notes.md` | Judge model, results, interpretation, and evaluation limitations |
| `docs/lab3-evidence/retrieval-strategy-comparison.csv` | Per-case retrieval-strategy experiment |
| `notebooks/lab3-demo.ipynb` | Walkthrough of the Track B retrieval and generation flow |

## Cost cleanup

The Lab 1–2 infrastructure used for feature engineering, Feature Store, and MLflow was destroyed after the recorded runs to avoid ongoing AWS charges. It must be recreated for a new Athena-backed training run. The local model, notebook, and saved evidence remain in this repository. Track B evaluation invokes Bedrock when rerun; run it only when needed. No SageMaker training job or always-on inference endpoint is needed for this project workflow.
