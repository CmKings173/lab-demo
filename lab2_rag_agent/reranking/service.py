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
    """Legacy direct-BGE placeholder superseded for Lab2 by ADR 011."""

    def rank(self, query: str, hits: Sequence[DocumentHit]) -> list[DocumentHit]:
        raise NotImplementedError("Direct BGE reranking is superseded by ADR 011")
