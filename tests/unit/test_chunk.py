import pytest

from app.ingest.chunk import estimate_tokens, make_chunks
from app.ingest.extract import TextBlock


def test_short_block_is_one_chunk_and_keeps_metadata() -> None:
    chunks = make_chunks(
        [TextBlock("A short synthetic sentence.", page=3, section_heading="Heading")],
        max_tokens=100,
        overlap_tokens=10,
    )

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.text == "A short synthetic sentence."
    assert chunk.token_count == estimate_tokens(chunk.text)
    assert chunk.page == 3
    assert chunk.section_heading == "Heading"


def test_long_text_is_split_under_the_limit_with_overlap() -> None:
    text = " ".join(
        f"Sentence {index} contains several synthetic words for chunking." for index in range(80)
    )
    chunks = make_chunks(
        [TextBlock(text, page=7, section_heading="Synthetic Section")],
        max_tokens=40,
        overlap_tokens=10,
    )

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.token_count == estimate_tokens(chunk.text)
        assert chunk.token_count <= 40
        assert chunk.page == 7
        assert chunk.section_heading == "Synthetic Section"

    for previous, current in zip(chunks, chunks[1:], strict=False):
        previous_words = set(previous.text.split())
        current_words = set(current.text.split())
        assert previous_words & current_words


def test_long_sentence_is_split_by_words() -> None:
    text = "word " * 300
    chunks = make_chunks(
        [TextBlock(text, page=None, section_heading=None)],
        max_tokens=30,
        overlap_tokens=5,
    )

    assert len(chunks) > 1
    assert all(chunk.token_count <= 30 for chunk in chunks)
    assert all(chunk.text for chunk in chunks)


def test_custom_token_counter_forces_character_split() -> None:
    chunks = make_chunks(
        [TextBlock("x" * 200, page=None, section_heading=None)],
        max_tokens=50,
        overlap_tokens=5,
        count_tokens=len,
    )

    assert len(chunks) >= 4
    assert all(chunk.token_count <= 50 for chunk in chunks)
    assert all(chunk.token_count == len(chunk.text) for chunk in chunks)


def test_empty_blocks_are_ignored() -> None:
    chunks = make_chunks(
        [TextBlock("   ", page=None, section_heading=None)],
        max_tokens=100,
        overlap_tokens=10,
    )
    assert chunks == []


def test_invalid_chunk_settings_are_rejected() -> None:
    with pytest.raises(ValueError, match="max_tokens"):
        make_chunks([], max_tokens=0, overlap_tokens=0)
    with pytest.raises(ValueError, match="overlap_tokens"):
        make_chunks([], max_tokens=50, overlap_tokens=50)
