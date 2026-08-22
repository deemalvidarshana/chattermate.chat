from app.knowledge.content_processing import (
    clean_knowledge_text,
    select_relevant_passage,
    split_knowledge_text,
)


def test_clean_text_removes_obvious_chrome_and_duplicates():
    content = """Skip to content
Search
## Product plans
Family protection details.
Family protection details.
![logo](https://example.com/logo.png)
Contact us at https://example.com/contact
"""

    cleaned = clean_knowledge_text(content)

    assert "Skip to content" not in cleaned
    assert "![logo]" not in cleaned
    assert cleaned.count("Family protection details.") == 1
    assert "https://example.com/contact" in cleaned


def test_split_text_is_bounded_and_overlapping():
    content = " ".join(f"Sentence {i} has useful plan information." for i in range(200))

    chunks = split_knowledge_text(content, max_chars=600, overlap_chars=60)

    assert len(chunks) > 3
    assert all(0 < len(chunk) <= 600 for chunk in chunks)


def test_split_text_removes_inline_data_images_and_hard_splits_long_tokens():
    data_image = "![map](data:image/svg+xml," + ("x" * 3000) + ")"
    chunks = split_knowledge_text(
        f"Useful branch details. {data_image} End of details.",
        max_chars=500,
        overlap_chars=50,
    )

    assert chunks
    assert all(len(chunk) <= 500 for chunk in chunks)
    assert all("data:image" not in chunk for chunk in chunks)


def test_select_passage_prefers_query_terms_from_large_page():
    content = (
        "General company history. " * 150
        + "The Family Secure plan costs LKR 1,000 per month and includes hospital cover. "
        + "Leadership biographies. " * 150
    )

    passage = select_relevant_passage(
        content, "family secure plan price hospital cover", max_chars=700
    )

    assert "LKR 1,000" in passage
    assert len(passage) <= 700
