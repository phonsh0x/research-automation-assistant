"""Quality scoring for PDF-to-Markdown conversion results."""


def compute_quality_score(result) -> int:
    """Compute a 0-100 quality score for a conversion result.

    Factors: char_count, section_count, word_count, page_count.
    """
    score = 0

    char_count = getattr(result, "char_count", 0) or 0
    if char_count > 500:
        score += 30
    elif char_count > 100:
        score += 15

    section_count = len(getattr(result, "sections", []) or [])
    if section_count >= 3:
        score += 25
    elif section_count >= 1:
        score += 10

    word_count = getattr(result, "word_count", 0) or 0
    if word_count > 200:
        score += 20
    elif word_count > 50:
        score += 10

    if getattr(result, "title", ""):
        score += 15

    if getattr(result, "abstract", ""):
        score += 10

    return min(score, 100)


def needs_review(quality_score: int, threshold: int = 40) -> bool:
    """Return True if the result likely needs manual review."""
    return quality_score < threshold
