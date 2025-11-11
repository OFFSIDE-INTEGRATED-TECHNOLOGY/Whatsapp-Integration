import requests

def classify_error(exc) -> str:
    if isinstance(exc, requests.exceptions.RequestException):
        resp = getattr(exc, "response", None)
        if resp is not None:
            if resp.status_code in (429, 500, 502, 503, 504):
                return "transient"
            return "permanent"
        return "transient"
    return "transient"
