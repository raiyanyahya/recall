import pytest
import summarizer

TEXT = (
    "The team migrated the database to Postgres and updated the schema. "
    "The Postgres migration required rewriting several queries in the data layer. "
    "Authentication now uses JWT tokens issued at login. "
    "We added rate limiting to the public endpoints. "
    "The frontend dashboard got a new charts component. "
    "The Postgres schema change also touched the migration scripts. "
    "Logging was switched to structured JSON output. "
    "The database migration was the largest change this week."
)


def test_short_text_passthrough():
    text = "Just one short sentence here please."
    assert summarizer.summarize(text, 5) == summarizer.split_sentences(text)


def test_summarize_returns_central_sentences():
    out = summarizer.summarize(TEXT, 3)
    assert 1 <= len(out) <= 3
    assert any("Postgres" in s or "database" in s for s in out)
    # Selected sentences are kept in their original order.
    idx = [TEXT.find(s[:20]) for s in out]
    assert idx == sorted(idx)


def test_pure_python_core_runs_without_numpy():
    toks = [summarizer._tokenize(s) for s in summarizer.split_sentences(TEXT)]
    scores = summarizer._textrank_python(toks, summarizer._idf(toks))
    assert len(scores) == len(toks)


def test_numpy_and_pure_python_cores_agree():
    np = pytest.importorskip("numpy")
    sentences = summarizer.split_sentences(TEXT)
    toks = [summarizer._tokenize(s) for s in sentences]
    idf = summarizer._idf(toks)
    a = np.array(summarizer._textrank_numpy(toks, idf))
    b = np.array(summarizer._textrank_python(toks, idf))
    assert np.allclose(a, b, atol=1e-6)
    # Scores being close isn't enough — the *selection* must be identical, so a
    # committed context.md never depends on whether numpy is installed. Ranking
    # rounds away the float noise and breaks ties by position to guarantee it.
    assert (summarizer._select(sentences, a.tolist(), 3)
            == summarizer._select(sentences, b.tolist(), 3))
