"""Canonical lexical similarity for generated training and independent evaluation."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from typing import Sequence

PRODUCT_ID_PATTERN = re.compile(r"\b(?:SYN|EVAL|DEMO)-[A-Z0-9]+(?:-[A-Z0-9]+)*\b", re.I)
CONFIG_ID_PATTERN = re.compile(r"\bcfg-[a-z0-9]+(?:-[a-z0-9]+)*\b", re.I)
NUMBER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])\d+(?:[.,]\d+)?(?=(?:gb|b|k)?\b)", re.I
)


def normalize_for_similarity(text: str) -> str:
    """Hide incidental identifiers and values, retaining words and units."""
    text = PRODUCT_ID_PATTERN.sub("product_id", text)
    text = CONFIG_ID_PATTERN.sub("configuration_id", text)
    text = NUMBER_PATTERN.sub("number", text)
    return " ".join(text.casefold().split())


def _trigrams(text: str) -> set[tuple[str, str, str]]:
    words = text.split()
    return set(zip(words, words[1:], words[2:]))


def near_duplicate_pairs(
    left_texts: Sequence[str],
    threshold: float,
    right_texts: Sequence[str] | None = None,
) -> set[tuple[int, int]]:
    """Find canonical near-pairs; trigrams block candidates, not semantic groups."""
    within = right_texts is None
    right_texts = left_texts if within else right_texts
    left = [normalize_for_similarity(text) for text in left_texts]
    right = left if within else [normalize_for_similarity(text) for text in right_texts]
    right_shingles = [_trigrams(text) for text in right]
    shingle_index: dict[tuple[str, str, str], set[int]] = defaultdict(set)
    normalized_index: dict[str, set[int]] = defaultdict(set)
    for index, shingles in enumerate(right_shingles):
        normalized_index[right[index]].add(index)
        for shingle in shingles:
            shingle_index[shingle].add(index)
    pairs: set[tuple[int, int]] = set()
    for index, text in enumerate(left):
        for candidate in normalized_index[text]:
            if not within or candidate > index:
                pairs.add((index, candidate))
        shingles = _trigrams(text)
        candidate_counts: Counter[int] = Counter()
        for shingle in shingles:
            for candidate in shingle_index[shingle]:
                if not within or candidate > index:
                    candidate_counts[candidate] += 1
        for candidate, shared in candidate_counts.items():
            if shared < 3:
                continue
            overlap = shared / max(1, len(shingles | right_shingles[candidate]))
            if overlap < 0.30:
                continue
            matcher = SequenceMatcher(None, text, right[candidate])
            if matcher.quick_ratio() >= threshold and matcher.ratio() >= threshold:
                pairs.add((index, candidate))
    return pairs


def near_duplicate_stats(texts: Sequence[str], threshold: float) -> tuple[int, float]:
    pairs = near_duplicate_pairs(texts, threshold)
    participants = {index for pair in pairs for index in pair}
    return len(pairs), len(participants) / len(texts) if texts else 0.0
