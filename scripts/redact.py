"""Best-effort secret redaction before writing to the (committable) md files.

A safety net so context.md / history.md don't accidentally carry an API key or
.env value into a commit. Conservative by design.
"""

import re

_R = "[REDACTED]"

_PATTERNS = [
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), _R),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), _R),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), _R),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), _R),
    (re.compile(r"(?i)\b(authorization|bearer)\b\s*[:=]?\s*[A-Za-z0-9._~+/-]{12,}=*"),
     r"\1 " + _R),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}\b"), _R),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
                re.DOTALL), _R),
]

_ENV_LINE = re.compile(
    r"(?im)^([ \t]*(?:export[ \t]+)?[A-Z0-9_]*"
    r"(?:SECRET|TOKEN|PASSWORD|PASSWD|API[_-]?KEY|ACCESS[_-]?KEY|PRIVATE[_-]?KEY)"
    r"[A-Z0-9_]*)[ \t]*=[ \t]*.+$"
)


def redact(text):
    if not text:
        return text
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return _ENV_LINE.sub(r"\1=" + _R, text)
