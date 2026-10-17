import json
import boto3

from rag.build_index import load_local_faiss_index, retrieve_by_strategy

MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
REGION = "us-east-1"

index, chunks = load_local_faiss_index()
bedrock = boto3.client("bedrock-runtime", region_name=REGION)


def rag_invoke(customer_context: dict, question: str) -> dict:
    tier_hits = retrieve_by_strategy(
        customer_context, index, chunks, strategy="tier", k=3
    )
    constraint_hits = retrieve_by_strategy(
        customer_context, index, chunks, strategy="constraints", k=3
    )

    # Combine both retrieval passes and remove duplicate chunks.
    hits_by_id = {
        chunk.chunk_id: (chunk, score)
        for chunk, score in tier_hits + constraint_hits
    }
    hits = list(hits_by_id.values())

    contexts = [
        f"Source: {chunk.metadata['source_file']} | "
        f"Section: {chunk.metadata['section_heading']}\n{chunk.text}"
        for chunk, _ in hits
    ]

    system_prompt = """You write concise, truthful retention messages for NorthStar Retail.

Treat the retrieved policy context as the only source for loyalty benefits and policy
terms. Use the customer profile only for personalization. Do not infer or change the
customer's loyalty tier from lifetime value.
Do not imply that a purchase, offer, or return will preserve, improve, or cause the
loss of the customer's tier or status unless the retrieved context explicitly
supports that claim for this customer.

Do not invent or imply a new promotion. Never add a discount, bonus points, dollar
value, spending threshold, promo code, expiration date, deadline, activation step,
exclusivity, scarcity, eligibility condition, or service scope unless it is explicitly
stated in the retrieved context. Do not claim product availability. Do not describe an
existing tier benefit as new, extra, exclusive, or something NorthStar is newly offering.
If you mention an existing benefit, label it as an existing membership benefit. If no
campaign incentive is supported by context, write a reminder about an existing benefit
instead of making one up.

Refer to a product category only if it appears in the customer profile. Do not use
placeholders for missing customer information; omit it or use a generic greeting. Keep
the body to 3-5 sentences and include a clear call to action without false urgency.
Return exactly these sections: Subject, Body, and Rationale. The rationale must also
stay within the customer profile and retrieved context; do not claim unsupported terms
are documented or policy-compliant."""

    user_prompt = (
        f"Customer profile:\n{json.dumps(customer_context, indent=2)}\n\n"
        f"Question: {question}\n\n"
        "Retrieved policy context:\n" + "\n\n---\n\n".join(contexts)
    )

    response = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": user_prompt}]}],
        inferenceConfig={"maxTokens": 400, "temperature": 0},
    )

    answer = response["output"]["message"]["content"][0]["text"]
    profile_context = f"Customer profile: {json.dumps(customer_context)}"
    return {"answer": answer, "contexts": contexts + [profile_context]}
