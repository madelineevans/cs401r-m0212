from dataclasses import dataclass
from pathlib import Path
import re
import json
import boto3
import numpy as np
import faiss


BEDROCK_REGION = "us-east-1"
EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"
EMBEDDING_DIMENSIONS = 256
DEFAULT_CORPUS_DIR = Path(__file__).resolve().parents[1] / "northstar-policy-docs"
DEFAULT_INDEX_DIR = Path(__file__).resolve().parent / "local_index"

# These are character counts, not tokenizer token counts. Chunks stay within
# one Markdown heading section, and line-aware splitting keeps policy tables
# and bullets intact when possible.
CHUNK_SIZE = 600
CHUNK_OVERLAP = 100

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_DOC_ID_RE = re.compile(r"^\*\*Document ID:\*\*\s*(\S+)", re.MULTILINE)

_bedrock_runtime = boto3.client(
    "bedrock-runtime",
    region_name=BEDROCK_REGION,
)


def embed_text(text: str) -> np.ndarray:
    """Return one normalized Titan v2 embedding as a float32 vector."""
    if not text.strip():
        raise ValueError("Cannot embed empty text")

    response = _bedrock_runtime.invoke_model(
        modelId=EMBEDDING_MODEL_ID,
        body=json.dumps({
            "inputText": text,
            "dimensions": EMBEDDING_DIMENSIONS,
            "normalize": True,
        }),
        contentType="application/json",
        accept="application/json",
    )

    payload = json.loads(response["body"].read())
    vector = np.asarray(payload["embedding"], dtype=np.float32)

    if vector.shape != (EMBEDDING_DIMENSIONS,):
        raise ValueError(f"Expected a 256-dimensional vector, got {vector.shape}")

    return vector

@dataclass(frozen=True)
class PolicyChunk:
    """A text chunk plus source information useful for citations and debugging."""

    chunk_id: str
    text: str
    metadata: dict[str, str | int]


def _heading_sections(markdown: str):
    """Yield (heading_path, body) pairs without joining separate sections."""
    heading_stack: dict[int, str] = {}
    body_lines: list[str] = []

    def current_heading() -> str:
        if not heading_stack:
            return "Document overview"
        return " > ".join(heading_stack[level] for level in sorted(heading_stack))

    active_heading = current_heading()
    for line in markdown.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            body = "\n".join(body_lines).strip()
            if body:
                yield active_heading, body

            level = len(match.group(1))
            for old_level in [n for n in heading_stack if n >= level]:
                del heading_stack[old_level]
            heading_stack[level] = match.group(2).strip()
            active_heading = current_heading()
            body_lines = []
        else:
            body_lines.append(line.rstrip())

    body = "\n".join(body_lines).strip()
    if body:
        yield active_heading, body


def _split_section(text: str, chunk_size: int, overlap: int):
    """Split section text into bounded windows, preferring Markdown line breaks.

    Overlap is up to ``overlap`` characters. When possible, the next chunk
    starts after a newline near the overlap boundary so table rows and bullets
    are not needlessly cut in half.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be at least zero and smaller than chunk_size")

    start = 0
    text_length = len(text)
    while start < text_length:
        limit = min(start + chunk_size, text_length)
        end = limit

        if limit < text_length:
            # Prefer a line boundary in the latter part of this window. If a
            # single line is too long, fall back to a word boundary, then the
            # hard character limit.
            preferred_start = start + (chunk_size * 3 // 5)
            boundary = text.rfind("\n", preferred_start, limit)
            if boundary <= start:
                boundary = text.rfind(" ", preferred_start, limit)
            if boundary > start:
                end = boundary

        piece = text[start:end].strip()
        if piece:
            yield piece

        if end >= text_length:
            break

        next_start = max(start + 1, end - overlap)
        # Snap forward to a line start if one falls inside the overlap window.
        newline = text.find("\n", next_start, end)
        if newline >= 0:
            next_start = newline + 1
        start = next_start


def load_policy_chunks(
    corpus_dir: str | Path = DEFAULT_CORPUS_DIR,
    *,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[PolicyChunk]:
    """Load the four policy Markdown files and return section-aware chunks.

    Each chunk includes its section heading in the embedded text and stores
    the policy document ID, filename, heading path, and chunk position as
    metadata. This helper performs no AWS calls and creates no vector index.
    """
    corpus_path = Path(corpus_dir)
    markdown_files = sorted(corpus_path.glob("*.md"))
    if not markdown_files:
        raise FileNotFoundError(f"No Markdown policy documents found in {corpus_path}")

    chunks: list[PolicyChunk] = []
    for source_path in markdown_files:
        markdown = source_path.read_text(encoding="utf-8-sig")
        doc_id_match = _DOC_ID_RE.search(markdown)
        doc_id = doc_id_match.group(1) if doc_id_match else source_path.stem

        for section_index, (heading, body) in enumerate(_heading_sections(markdown), start=1):
            for chunk_index, body_chunk in enumerate(
                _split_section(body, chunk_size, overlap), start=1
            ):
                # Including the heading gives the embedder the policy topic;
                # metadata retains it separately for citations and inspection.
                chunk_text = f"{heading}\n\n{body_chunk}"
                chunks.append(
                    PolicyChunk(
                        chunk_id=f"{doc_id}-s{section_index:03d}-c{chunk_index:03d}",
                        text=chunk_text,
                        metadata={
                            "doc_id": doc_id,
                            "source_file": source_path.name,
                            "section_heading": heading,
                            "section_index": section_index,
                            "chunk_index": chunk_index,
                            "body_char_count": len(body_chunk),
                        },
                    )
                )

    return chunks

def build_local_faiss_index(
    chunks: list[PolicyChunk],
    index_dir: str | Path = DEFAULT_INDEX_DIR,
) -> None:
    """Embed policy chunks once and save their vectors and source text locally."""
    if not chunks:
        raise ValueError("Cannot build a FAISS index without chunks")

    vectors = np.vstack([embed_text(chunk.text) for chunk in chunks])
    index = faiss.IndexFlatIP(EMBEDDING_DIMENSIONS)
    index.add(vectors)

    output_dir = Path(index_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(output_dir / "policies.faiss"))

    chunk_data = [
        {
            "chunk_id": chunk.chunk_id,
            "text": chunk.text,
            "metadata": chunk.metadata,
        }
        for chunk in chunks
    ]
    (output_dir / "chunks.json").write_text(
        json.dumps(chunk_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_local_faiss_index(
    index_dir: str | Path = DEFAULT_INDEX_DIR,
) -> tuple[faiss.Index, list[PolicyChunk]]:
    """Load the saved vectors and their matching policy chunks."""
    input_dir = Path(index_dir)
    index = faiss.read_index(str(input_dir / "policies.faiss"))
    chunk_data = json.loads(
        (input_dir / "chunks.json").read_text(encoding="utf-8")
    )
    chunks = [
        PolicyChunk(
            chunk_id=item["chunk_id"],
            text=item["text"],
            metadata=item["metadata"],
        )
        for item in chunk_data
    ]

    if index.ntotal != len(chunks):
        raise ValueError("FAISS vector count does not match saved policy chunks")

    return index, chunks

def retrieve_policy_chunks(
    query: str,
    index: faiss.Index,
    chunks: list[PolicyChunk],
    k: int = 4,
    allowed_doc_ids: set[str] | None = None,
) -> list[tuple[PolicyChunk, float]]:
    """Return top-k policy chunks, optionally restricted to selected documents."""
    if not query.strip():
        raise ValueError("Cannot retrieve with an empty query")
    if k <= 0:
        raise ValueError("k must be greater than zero")
    if index.ntotal == 0:
        return []
    if index.ntotal != len(chunks):
        raise ValueError("FAISS vector count does not match the policy chunks")

    query_vector = embed_text(query).reshape(1, -1)
    search_k = index.ntotal if allowed_doc_ids is not None else min(k, index.ntotal)
    scores, positions = index.search(query_vector, search_k)

    results = []
    for score, position in zip(scores[0], positions[0]):
        if position < 0:
            continue

        chunk = chunks[int(position)]
        if allowed_doc_ids is not None and chunk.metadata["doc_id"] not in allowed_doc_ids:
            continue

        results.append((chunk, float(score)))
        if len(results) == k:
            break

    return results

def tier_benefit_query(customer_context: dict) -> str:
    tier = customer_context["loyalty_tier"]
    return (
        f"loyalty tier {tier} benefits points earn rate "
        "free shipping threshold return window birthday reward"
    )

def constraint_query() -> str:
    return (
        "final sale non-returnable exclusions expired offers cannot be reinstated "
        "retention offer validity single use combinability"
    )

def hybrid_query(customer_context: dict) -> str:
    tier = customer_context["loyalty_tier"]
    channel = (
        "online"
        if customer_context["online_to_store_ratio"] > 0.5
        else "in store"
    )
    return (
        f"tier {tier} entitlements and shipping thresholds "
        f"for a customer who shops {channel}"
    )

def retrieve_by_strategy(
    customer_context: dict,
    index: faiss.Index,
    chunks: list[PolicyChunk],
    strategy: str = "hybrid",
    k: int = 4,
) -> list[tuple[PolicyChunk, float]]:
    if strategy == "tier":
        query = tier_benefit_query(customer_context)
        allowed_doc_ids = None
    elif strategy == "constraints":
        query = constraint_query()
        allowed_doc_ids = None
    elif strategy == "hybrid":
        query = hybrid_query(customer_context)
        allowed_doc_ids = {"POL-LOY-011", "POL-SHP-007"}
    else:
        raise ValueError(
            "strategy must be 'tier', 'constraints', or 'hybrid'"
        )

    return retrieve_policy_chunks(
        query,
        index,
        chunks,
        k=k,
        allowed_doc_ids=allowed_doc_ids,
    )