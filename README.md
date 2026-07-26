# signhook

**Stop hand-crafting curl commands and reverse-engineering signature schemes to test webhooks.**

Generate realistic Stripe, Twilio, and GitHub webhook payloads, sign them the way those providers actually do, and send them to your local server — with a clear diagnosis when verification fails.

> **Demo GIF** — *placeholder: record a 20–30s walkthrough (pick provider → Sign & Send → green 200) and drop it here before launch.*

---

## Quick start

```bash
git clone https://github.com/krish-mittal1/signhook.git
cd signhook
docker compose up --build
```

Open **http://localhost:3000**

That’s it. No accounts, no hosted SaaS, no extra config.

| Service  | URL                     |
|----------|-------------------------|
| UI       | http://localhost:3000   |
| API      | http://localhost:8000   |
| Echo*    | http://echo:9999        |

\*The Compose stack includes a small `echo` receiver so Sign & Send works out of the box. The UI defaults to `http://echo:9999/hooks/<provider>`. Point `target_url` at your own app (or ngrok URL) whenever you’re ready.

---

## How it works

1. **Pick a provider** and event type (loaded from the API — not hardcoded in the UI).
2. **Generate a payload** — realistic JSON (Stripe/GitHub) or form-style params (Twilio). Edit freely in the textarea.
3. **Sign & Send** — the backend signs with the real provider scheme and POSTs to your `target_url`.
4. **See the result** — status code, response body, headers sent, and a plain-English diagnosis on failure.

---

## Trust: secrets stay on your machine

signhook is **local-only**. You paste webhook secrets / auth tokens into the UI; they are used only by the process running on your computer. Nothing is uploaded to a third-party service. That is intentional — and the main reason this is not a hosted product.

---

## Supported providers

| Provider | Events | Signature |
|----------|--------|-----------|
| **Stripe** | `payment_intent.succeeded`, `customer.created`, `invoice.paid` | `Stripe-Signature` (`t=…,v1=…` HMAC-SHA256) |
| **Twilio** | `message.received`, `call.completed` | `X-Twilio-Signature` (HMAC-SHA1 over URL + sorted params) |
| **GitHub** | `push`, `pull_request`, `issues` | `X-Hub-Signature-256` (`sha256=` HMAC-SHA256) |

---

## Run without Docker

**Terminal 1 — API**

```bash
cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — UI**

```bash
cd frontend
cp .env.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

Open **http://localhost:3000**.

Optional echo receiver for signature checks:

```bash
cd backend
python -u tests/echo_receiver.py
# listens on http://127.0.0.1:9999
```

Use target URLs like `http://127.0.0.1:9999/hooks/stripe` and the smoke secrets documented in `backend/tests/echo_receiver.py`.

---

## Offline signature harness

```bash
cd backend
python tests/verify_signatures.py
```

Confirms Stripe, Twilio, and GitHub signing match independent verifiers (including Twilio’s official algorithm).

---

## License

MIT — see [LICENSE](LICENSE).
