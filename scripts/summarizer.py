"""Local extractive summarizer — vendored, zero required installs.

Implements TF-IDF + TextRank ourselves:
  1. tokenize sentences (stopword-filtered)
  2. TF-IDF sentence vectors
  3. cosine-similarity graph between sentences
  4. TextRank = PageRank power iteration over that graph
  5. keep the top-k sentences in original order

Two interchangeable implementations of the numeric core:
  * **numpy** — vectorized, used automatically when numpy is importable.
  * **pure Python** — same algorithm in stdlib only, used when numpy isn't there.

Either way there is no pip install required and nothing leaves the machine. numpy
is used only to go faster when it already exists.

`summarize(text, k)` returns up to `k` salient sentences in their original order.
"""

import math
import re
from collections import Counter

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_MIN_LEN = 24            # drop trivially short fragments
_MAX_RANK = 400          # cap sentences ranked (keep most recent) to bound cost
_DAMPING = 0.85
_MAX_ITERS = 100
_TOL = 1e-6

_STOPWORDS = set(
    "the a an and or but if then else of to in on at for with from by as is are was "
    "were be been being this that these those it its i you we they he she them us our "
    "your their not no do does did so than too very can will just into out up down over "
    "about which who whom what when where why how all any each more most other some such "
    "only own same s t don now i'll i've it's we'll let me here there".split()
)


def split_sentences(text):
    out = []
    for raw in _SENT_SPLIT.split(text or ""):
        s = " ".join(raw.split())
        if len(s) >= _MIN_LEN:
            out.append(s)
    return out


def _tokenize(sentence):
    return [w for w in re.findall(r"[a-zA-Z][a-zA-Z']+", sentence.lower())
            if w not in _STOPWORDS and len(w) > 2]


def summarize(text, k=8):
    sentences = split_sentences(text)
    if len(sentences) <= k:
        return sentences
    if len(sentences) > _MAX_RANK:
        sentences = sentences[-_MAX_RANK:]  # recency-biased; keeps it fast

    tokens = [_tokenize(s) for s in sentences]
    if not any(tokens):
        return sentences[:k]

    idf = _idf(tokens)
    try:
        import numpy  # noqa: F401
        scores = _textrank_numpy(tokens, idf)
    except Exception:
        scores = _textrank_python(tokens, idf)

    return _select(sentences, scores, k)


def _select(sentences, scores, k):
    """Top-k sentences by score, returned in original order. Scores are rounded
    before ranking and ties are broken by position, so the sub-epsilon numerical
    difference between the numpy and pure-Python cores can never change which
    sentences are chosen — both backends always produce the same summary (a
    committed context.md must not depend on whether numpy happens to be present)."""
    order = sorted(range(len(sentences)),
                   key=lambda i: (round(scores[i], 10), -i), reverse=True)
    return [sentences[i] for i in sorted(order[:k])]


def backend_name():
    try:
        import numpy  # noqa: F401
        return "TextRank (vendored, numpy-accelerated)"
    except ImportError:
        return "TextRank (vendored, pure Python)"


# --- shared TF-IDF ----------------------------------------------------------

def _idf(tokens):
    n = len(tokens)
    df = Counter()
    for toks in tokens:
        for w in set(toks):
            df[w] += 1
    return {w: math.log((1.0 + n) / (1.0 + d)) + 1.0 for w, d in df.items()}


# --- pure-Python core -------------------------------------------------------

def _tfidf_sparse(tokens, idf):
    vecs = []
    for toks in tokens:
        if not toks:
            vecs.append({})
            continue
        tf = Counter(toks)
        length = len(toks)
        vec = {w: (c / length) * idf[w] for w, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        vecs.append({w: v / norm for w, v in vec.items()})
    return vecs


def _cosine(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(val * b.get(w, 0.0) for w, val in a.items())


def _textrank_python(tokens, idf):
    vecs = _tfidf_sparse(tokens, idf)
    n = len(vecs)
    sim = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            c = _cosine(vecs[i], vecs[j])
            if c:
                sim[i][j] = sim[j][i] = c
    row_sum = [sum(row) for row in sim]

    scores = [1.0 / n] * n
    base = (1.0 - _DAMPING) / n
    for _ in range(_MAX_ITERS):
        new = [base] * n
        for i in range(n):
            if row_sum[i] == 0.0:
                continue
            share = _DAMPING * scores[i] / row_sum[i]
            row = sim[i]
            for j in range(n):
                w = row[j]
                if w:
                    new[j] += share * w
        if sum(abs(new[i] - scores[i]) for i in range(n)) < _TOL:
            scores = new
            break
        scores = new
    return scores


# --- numpy core -------------------------------------------------------------

def _textrank_numpy(tokens, idf):
    import numpy as np

    vocab = sorted(idf)
    index = {w: i for i, w in enumerate(vocab)}
    n, vsize = len(tokens), len(vocab)

    mat = np.zeros((n, vsize), dtype=np.float64)
    for i, toks in enumerate(tokens):
        if not toks:
            continue
        length = len(toks)
        for w, c in Counter(toks).items():
            mat[i, index[w]] = (c / length) * idf[w]

    norms = np.sqrt((mat * mat).sum(axis=1, keepdims=True))
    norms[norms == 0] = 1.0
    mat /= norms

    sim = mat @ mat.T
    np.fill_diagonal(sim, 0.0)
    row_sum = sim.sum(axis=1, keepdims=True)
    row_sum[row_sum == 0] = 1.0
    transition = sim / row_sum

    base = (1.0 - _DAMPING) / n
    scores = np.full(n, 1.0 / n)
    for _ in range(_MAX_ITERS):
        prev = scores
        scores = base + _DAMPING * (transition.T @ scores)
        if np.abs(scores - prev).sum() < _TOL:
            break
    return scores.tolist()
