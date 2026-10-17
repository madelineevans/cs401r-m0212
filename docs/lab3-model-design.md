# Lab 3 Model Design

**Chosen track: Track B — Offer Generation with RAG**

## 1. Churn model choice

The churn data is a modest-sized, structured customer table: the final training query returned 9,999 customers, and the model used 11 predictors derived from purchase and customer history. XGBoost was a good fit because boosted decision trees handle tabular features, can learn nonlinear thresholds and interactions, and do not require feature scaling. I trained it locally with limited preprocessing, avoiding the cost and setup of a managed training job.

The retention team needs a useful ranking of customers to contact and evidence about which signals the model uses. Logistic regression would be a simpler baseline for this binary problem: its coefficients are easier to inspect and work well when relationships are approximately linear in the log-odds of churn. It may need manual transformations or interaction terms to represent patterns a tree can learn directly. A neural network is not automatically more accurate; with about 10,000 tabular rows, it would add complexity without evidence of better results. XGBoost is not fully interpretable either: its gain plot summarizes feature use globally, but is not causal and does not explain each prediction.

I would reconsider the model if richer histories or substantially more data became available and a controlled comparison showed a meaningful business improvement, or if the team required simpler per-customer explanations.

## 2. Feature value

I compared the full model with a recency-only churn baseline that used `days_since_last_purchase` as its sole predictor. This is a comparison between churn models; it is separate from the retrieval strategies in my RAG system. On the same held-out validation set, the full model reached an AUC-ROC of **0.7819**, compared with **0.7226** for the recency-only baseline. The AUC lift was **0.0593**, and the paired-bootstrap 95% confidence interval was **[0.0404, 0.0767]**, which excludes zero. This is evidence that the additional features improved customer ranking on this validation sample. At the operational top-decile cutoff, precision was **0.7167** and recall was **0.3258**.

The gain plot ranks `days_since_last_purchase` highest, followed by `purchase_frequency_180d` and `purchase_frequency_30d`, suggesting both recency and purchase activity contributed useful splits. `total_spend_90d`, `online_to_store_ratio`, and `customer_tenure_days` were among the lowest-gain features. That means lower relative importance in this fit, not that they are useless: gain can be split among correlated predictors and does not show whether a feature raises or lowers churn. The results are in `docs/lab3-evaluation-report.md` and `docs/lab3-evidence/feature-importance.png`.

## 3. Why RAG for offer generation

I chose RAG over fine-tuning because this system needs to apply specific, changeable loyalty and retail policies when generating an offer. With RAG, I can update the policy documents and rebuild the index without retraining the language model. I can also inspect the retrieved chunks to see which policy text was available to the generator. Fine-tuning could shape the model’s style or behavior, but it would be a less direct way to keep exact policy details current and trace which rule supported a particular claim.

RAG does not eliminate hallucinations. Its main production risk is missing, incomplete, or outdated retrieved policy—or a generator that ignores the context. It can invent incentives or present an existing benefit as a new promotion. My failure examples include invented activation instructions for Gold benefits and an unsupported claim that a purchase would preserve Gold status. Too many chunks can also crowd the context, so retrieval quality and context size need monitoring.

## 4. What I would change with more time and data

With ten times more time and data, I would collect richer timestamped purchase histories and test whether customer behavior sequences improve churn prediction. I would compare a neural sequence model with the current XGBoost model on a time-based holdout, so the evaluation better reflects predicting future churn from past behavior. I would compare AUC, precision and recall at the contact budget, performance across loyalty tiers, and the complexity of explaining the results. I would adopt the neural model only if it produced a repeatable improvement large enough to justify its added data, training, and explanation requirements. More data could make that experiment worthwhile, but it would not guarantee that a neural network performs better.
