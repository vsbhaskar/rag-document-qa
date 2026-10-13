from app.ingest import chunk_text, clean_text


def test_clean_text_joins_broken_lines_and_collapses_spaces():
    assert clean_text("hello\nworld   again\n") == "hello world again"


def test_chunks_follow_sentence_boundaries_with_one_sentence_overlap():
    sentences = [f"This is sentence number {i:02d} of the test." for i in range(10)]
    chunks = chunk_text(" ".join(sentences), max_chars=100, overlap_sentences=1)
    assert len(chunks) == 9
    assert chunks[0] == sentences[0] + " " + sentences[1]
    for i, chunk in enumerate(chunks):
        assert chunk.startswith("This") and chunk.endswith(".")      # never cut mid-sentence
        if i + 1 < len(chunks):
            assert chunks[i + 1].startswith(sentences[i + 1])         # overlap
    assert all(any(s in c for c in chunks) for s in sentences)        # nothing lost


def test_one_very_long_sentence_is_kept_whole():
    sentence = "word " * 400 + "end."
    assert chunk_text(sentence, max_chars=800) == [sentence]