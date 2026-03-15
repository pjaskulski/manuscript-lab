from sacrebleu import corpus_bleu, corpus_chrf, sentence_bleu, sentence_chrf


def _normalize_text(text: str) -> str:
    return (text or "").strip()


def compute_bleu(reference: str, candidate: str) -> float:
    reference = _normalize_text(reference)
    candidate = _normalize_text(candidate)
    if not reference or not candidate:
        return 0.0
    return float(sentence_bleu(candidate, [reference]).score)


def compute_chrf(reference: str, candidate: str) -> float:
    reference = _normalize_text(reference)
    candidate = _normalize_text(candidate)
    if not reference or not candidate:
        return 0.0
    return float(sentence_chrf(candidate, [reference]).score)


def compute_corpus_bleu(references: list[str], candidates: list[str]) -> float:
    pairs = [
        (_normalize_text(reference), _normalize_text(candidate))
        for reference, candidate in zip(references, candidates, strict=False)
        if _normalize_text(reference) and _normalize_text(candidate)
    ]
    if not pairs:
        return 0.0
    corpus_references = [reference for reference, _candidate in pairs]
    corpus_candidates = [candidate for _reference, candidate in pairs]
    return float(corpus_bleu(corpus_candidates, [corpus_references]).score)


def compute_corpus_chrf(references: list[str], candidates: list[str]) -> float:
    pairs = [
        (_normalize_text(reference), _normalize_text(candidate))
        for reference, candidate in zip(references, candidates, strict=False)
        if _normalize_text(reference) and _normalize_text(candidate)
    ]
    if not pairs:
        return 0.0
    corpus_references = [reference for reference, _candidate in pairs]
    corpus_candidates = [candidate for _reference, candidate in pairs]
    return float(corpus_chrf(corpus_candidates, [corpus_references]).score)
