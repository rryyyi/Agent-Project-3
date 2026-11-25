"""Small-corpus BM25, optional dense retrieval, RRF and evidence compression."""

import math
import re
from collections import Counter


def tokenize(text: str) -> list[str]:
    text = text.casefold()
    words = re.findall(r"[a-z0-9]+", text)
    for run in re.findall(r"[\u3400-\u9fff]+", text):
        words.extend(run)
        words.extend(run[i : i + 2] for i in range(len(run) - 1))
    return words


def chunk_document(doc: dict, size: int = 400, overlap: int = 60) -> list[dict]:
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("Require size > overlap >= 0")
    text = doc["text"]
    return [
        {
            "chunk_id": f"{doc['id']}:{start}",
            "document_id": doc["id"],
            "text": text[start : start + size],
            "source": doc["source"],
            "page": doc.get("page"),
            "title": doc.get("title", ""),
            "keywords": doc.get("keywords", []),
        }
        for start in range(0, len(text), size - overlap)
    ]


def compress(hits: list[dict], max_chars: int = 1600) -> list[dict]:
    """Extractive character budget (not a tokenizer-based token guarantee)."""
    result = []
    remaining = max_chars
    for hit in hits:
        if remaining <= 0:
            break
        text = hit["text"][:remaining]
        result.append({**hit, "text": text, "truncated": len(text) < len(hit["text"])})
        remaining -= len(text)
    return result


def rrf(rankings: list[list[dict]], k: int = 60) -> list[dict]:
    scores = Counter()
    records = {}
    for ranking in rankings:
        seen = set()
        for rank, hit in enumerate(ranking, 1):
            key = hit["chunk_id"]
            if key in seen:
                continue
            seen.add(key)
            scores[key] += 1 / (k + rank)
            records[key] = hit
    return [
        {**records[key], "score": score}
        for key, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    ]


def cosine(a, b) -> float:
    denominator = math.sqrt(sum(x * x for x in a) * sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / denominator if denominator else 0


class Retriever:
    def __init__(self, knowledge, dense=None, reranker=None):
        self.chunks = [chunk for doc in knowledge.documents for chunk in chunk_document(doc)]
        self.tokens = [Counter(tokenize(c["title"] + " " + c["text"])) for c in self.chunks]
        self.avg_length = sum(map(lambda c: sum(c.values()), self.tokens)) / max(
            1, len(self.tokens)
        )
        self.df = Counter(term for tokens in self.tokens for term in tokens)
        self.dense = dense
        self.reranker = reranker
        self.vectors = dense.encode([c["text"] for c in self.chunks]) if dense else None

    def search(self, query: str, limit: int = 3) -> list[dict]:
        if not query.strip():
            return []
        query_tokens = set(tokenize(query))
        lexical = []
        for chunk, tokens in zip(self.chunks, self.tokens, strict=True):
            exact = any(keyword.casefold() in query.casefold() for keyword in chunk["keywords"])
            matched = query_tokens.intersection(tokens)
            # A lone common CJK character is not enough evidence of relevance.
            informative = any(len(t) > 1 or t.isascii() for t in matched)
            if not exact and not informative:
                continue
            score = 2.0 * exact
            for term in matched:
                freq = tokens[term]
                idf = math.log(1 + (len(self.chunks) - self.df[term] + 0.5) / (self.df[term] + 0.5))
                norm = 1.2 * (0.25 + 0.75 * sum(tokens.values()) / max(1, self.avg_length))
                score += idf * freq * 2.2 / (freq + norm)
            lexical.append({**chunk, "score": score})
        rankings = [sorted(lexical, key=lambda h: -h["score"])[:10]]
        if self.dense and self.vectors:
            vector = self.dense.encode([query])[0]
            semantic = [
                {**chunk, "score": cosine(vector, embedding)}
                for chunk, embedding in zip(self.chunks, self.vectors, strict=True)
            ]
            rankings.append(
                sorted([h for h in semantic if h["score"] >= 0.5], key=lambda h: -h["score"])[:10]
            )
        hits = rrf(rankings)
        if self.reranker and hits:
            hits = self.reranker.rerank(query, hits)
        return compress(hits[:limit])
