# Contributing to signhook

Thanks for helping. The fastest way to contribute is to **add a new webhook provider**.

Providers are intentionally tiny: two functions and a registry entry. You should be able to land a new one in about **15 minutes** if you already know that provider’s signing scheme.

---

## Add a new provider in 15 minutes

### 1. Create `backend/providers/<name>.py`

Copy the shape of an existing module:

- [`stripe.py`](backend/providers/stripe.py) — JSON body + HMAC over canonical JSON  
- [`twilio.py`](backend/providers/twilio.py) — form params + URL-based signature (hardest pattern)  
- [`github.py`](backend/providers/github.py) — JSON body + `sha256=` header  

Minimum surface:

```python
EVENT_TYPES = ["event.one", "event.two"]

def generate_payload(event_type: str) -> dict:
    if event_type not in EVENT_TYPES:
        raise ValueError(...)
    # return a realistic payload for that event
    ...

def sign_payload(payload: dict, secret: str, *, target_url: str | None = None) -> dict[str, str]:
    # return signature headers only, e.g. {"X-Acme-Signature": "..."}
    ...
```

Rules:

- Validate `event_type` against `EVENT_TYPES` and raise `ValueError` if unknown.
- If signing needs the request URL (like Twilio), require `target_url` and raise `ValueError` when missing.
- Reuse helpers in [`utils/signing.py`](backend/utils/signing.py) (`canonical_json`, `hmac_sha256_hex`, `hmac_sha1_base64`) so sign and send never drift.
- Keep payloads realistic — match field names the real provider documents.

### 2. Register it

In [`backend/providers/__init__.py`](backend/providers/__init__.py):

1. Import your module.  
2. Add it to `PROVIDERS`.  
3. Add a `PROVIDER_META` entry with `id`, `name`, and `event_types`.

If the outbound body is not JSON, teach [`utils/outbound.py`](backend/utils/outbound.py) how to encode it (see Twilio’s form encoding).

Add a short failure hint in [`utils/diagnosis.py`](backend/utils/diagnosis.py) for the #1 mistake people make with that provider.

### 3. Extend the verify harness

In [`backend/tests/verify_signatures.py`](backend/tests/verify_signatures.py):

- Independent verify function (do **not** just call `sign_payload` to check itself).  
- Assert: correct signature matches, wrong secret fails, tampered payload fails.  
- If URL-bound: wrong URL fails.

Run:

```bash
cd backend
python tests/verify_signatures.py
```

### 4. Open a PR

- Keep the diff scoped to one provider when possible.  
- Mention the official docs URL for the signature scheme in the PR description.  
- No need for a frontend change — the UI loads providers from `GET /api/providers`.

---

## Local development

```bash
docker compose up --build
# or: backend uvicorn + frontend npm run dev (see README)
```

Please don’t commit `.venv/`, `node_modules/`, `.env.local`, or secrets.

---

## Code of conduct (lightweight)

Be respectful, assume good intent, and prefer small PRs that are easy to review.
