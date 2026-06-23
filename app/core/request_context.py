from uuid import uuid4

REQUEST_ID_HEADER = "X-Request-ID"


def build_request_id(candidate: str | None = None) -> str:
    if candidate and candidate.strip():
        return candidate.strip()
    return str(uuid4())
