from difflib import SequenceMatcher
from html import escape
from itertools import zip_longest

from jiwer import cer, wer

from .text_normalization import normalize_text


def compute_htr_metrics(reference: str, candidate: str, profile: str = "lowercase") -> dict:
    reference_norm = normalize_text(reference, profile=profile)
    candidate_norm = normalize_text(candidate, profile=profile)

    return {
        "reference_normalized": reference_norm,
        "candidate_normalized": candidate_norm,
        "wer": wer(reference_norm, candidate_norm),
        "cer": cer(reference_norm, candidate_norm),
    }


def _highlight_inline_diff(reference: str, candidate: str) -> tuple[str, str]:
    matcher = SequenceMatcher(None, reference, candidate)
    reference_parts: list[str] = []
    candidate_parts: list[str] = []

    for tag, ref_start, ref_end, cand_start, cand_end in matcher.get_opcodes():
        ref_chunk = escape(reference[ref_start:ref_end])
        cand_chunk = escape(candidate[cand_start:cand_end])

        if tag == "equal":
            reference_parts.append(ref_chunk)
            candidate_parts.append(cand_chunk)
        else:
            if ref_chunk:
                reference_parts.append(f'<span class="diff-ref-change">{ref_chunk}</span>')
            if cand_chunk:
                candidate_parts.append(f'<span class="diff-cand-change">{cand_chunk}</span>')

    return "".join(reference_parts), "".join(candidate_parts)


def _build_diff_row(
    reference_line_no: int | None,
    reference_line: str | None,
    candidate_line_no: int | None,
    candidate_line: str | None,
) -> str:
    if reference_line is None:
        reference_html = '<span class="diff-empty">Brak wiersza</span>'
        candidate_html = f'<span class="diff-cand-change">{escape(candidate_line or "")}</span>'
        row_class = "diff-row diff-row-insert"
    elif candidate_line is None:
        reference_html = f'<span class="diff-ref-change">{escape(reference_line)}</span>'
        candidate_html = '<span class="diff-empty">Brak wiersza</span>'
        row_class = "diff-row diff-row-delete"
    else:
        reference_html, candidate_html = _highlight_inline_diff(reference_line, candidate_line)
        row_class = "diff-row"
        if reference_line != candidate_line:
            row_class += " diff-row-change"

    return (
        f'<tr class="{row_class}">'
        f'<td class="diff-line-no">{reference_line_no or ""}</td>'
        f'<td class="diff-line-text">{reference_html}</td>'
        f'<td class="diff-line-no">{candidate_line_no or ""}</td>'
        f'<td class="diff-line-text">{candidate_html}</td>'
        "</tr>"
    )


def make_html_diff(reference: str, candidate: str) -> str:
    reference_lines = reference.splitlines() or [""]
    candidate_lines = candidate.splitlines() or [""]
    matcher = SequenceMatcher(None, reference_lines, candidate_lines)
    rows: list[str] = []

    for tag, ref_start, ref_end, cand_start, cand_end in matcher.get_opcodes():
        if tag == "equal":
            for ref_index, cand_index in zip(range(ref_start, ref_end), range(cand_start, cand_end)):
                rows.append(
                    _build_diff_row(
                        ref_index + 1,
                        reference_lines[ref_index],
                        cand_index + 1,
                        candidate_lines[cand_index],
                    )
                )
            continue

        ref_block = list(range(ref_start, ref_end))
        cand_block = list(range(cand_start, cand_end))
        for ref_index, cand_index in zip_longest(ref_block, cand_block):
            rows.append(
                _build_diff_row(
                    None if ref_index is None else ref_index + 1,
                    None if ref_index is None else reference_lines[ref_index],
                    None if cand_index is None else cand_index + 1,
                    None if cand_index is None else candidate_lines[cand_index],
                )
            )

    return (
        '<table class="htr-diff-table">'
        "<colgroup>"
        '<col class="diff-col-no">'
        '<col class="diff-col-text">'
        '<col class="diff-col-no">'
        '<col class="diff-col-text">'
        "</colgroup>"
        "<thead>"
        "<tr>"
        "<th>Nr wiersza</th>"
        "<th>Wzorzec</th>"
        "<th>Nr wiersza</th>"
        "<th>Porównywany</th>"
        "</tr>"
        "</thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )
