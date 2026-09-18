from collections.abc import Sequence

from shared.contracts import DocumentHit


class FakeReranker:
    def rank(self, query: str, hits: Sequence[DocumentHit]) -> list[DocumentHit]:
        terms = set(query.casefold().split())
        ranked = sorted(
            hits,
            key=lambda hit: len(terms.intersection(hit.chunk.text.casefold().split())),
            reverse=True,
        )
        return [
            hit.model_copy(
                update={
                    "rerank_score": float(
                        len(terms.intersection(hit.chunk.text.casefold().split()))
                    ),
                    "rank": index,
                }
            )
            for index, hit in enumerate(ranked, start=1)
        ]


class BGEReranker:
    """Reserved for a local BGE reranker; model loading is deferred."""

    def rank(self, query: str, hits: Sequence[DocumentHit]) -> list[DocumentHit]:
        raise NotImplementedError("BGE reranker is planned for a later phase")
