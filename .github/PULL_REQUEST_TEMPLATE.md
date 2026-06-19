<!-- Thanks for contributing to Recall! -->

## Summary

<!-- What does this change and why? -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Refactor / cleanup
- [ ] Docs / CI only

## Checklist

- [ ] `ruff check scripts tests` passes
- [ ] `bandit -c pyproject.toml -r scripts` passes
- [ ] `pytest` passes **with and without numpy installed** (both summarizer paths)
- [ ] `claude plugin validate .` passes
- [ ] Added/updated tests under `tests/` for the behavior change
- [ ] Updated `CHANGELOG.md`
- [ ] No new runtime dependency, no network call, no API key (numpy stays optional)
