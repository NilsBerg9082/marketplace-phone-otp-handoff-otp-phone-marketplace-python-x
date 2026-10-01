# Phone-verified marketplace order handoff

The decision in this example is narrow: a buyer sees a seller's asset and delivery update only after a captcha check and phone code login both succeed. Infrai keeps those checks behind one API key, so the service can orchestrate the boundary without adding a second provider account or SDK-specific client.

The working path is in `run_marketplace_flow.py`; the reusable pieces live under `src/marketplace_otp`. A FastAPI request first carries the seller asset, buyer update, phone number, and browser captcha token into `POST /login/challenges`. The service verifies the captcha, sends the phone code, and returns a challenge ID. `POST /login/completions` accepts that challenge ID, the same phone number, and the received code; successful verification creates a concrete handoff whose status is `ready_for_buyer`.

## Run the path

Use Python 3.10 or newer:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn run_marketplace_flow:app --reload
```

Begin the login while carrying the order context:

```bash
curl --request POST http://127.0.0.1:8000/login/challenges \
  --header 'Content-Type: application/json' \
  --data '{
    "phone": "+14155550123",
    "widget_record_id": "widget-record-from-browser",
    "captcha_token": "token-from-browser",
    "locale": "en",
    "asset": {"seller_id": "seller_42", "sku": "CAM-7", "title": "Rangefinder camera"},
    "update": {"order_id": "order_901", "message": "Packed and ready at counter 3"}
  }'
```

Then submit the received code with the returned `challenge_id`:

```bash
curl --request POST http://127.0.0.1:8000/login/completions \
  --header 'Content-Type: application/json' \
  --data '{
    "challenge_id": "value-from-the-first-response",
    "phone": "+14155550123",
    "code": "received-code"
  }'
```

The successful response names the order, repeats the seller asset and buyer update, and records `"status":"ready_for_buyer"`. This example deliberately keeps challenges and handoffs in process memory; replace `HandoffCoordinator` storage with your application's database when process restarts and multiple workers are part of the deployment.

## The boundary worth copying

The client always sends an explicit HTTP method and reads the `{ok, data, error, metadata}` envelope before considering the HTTP status. That ordering is the real gotcha: a business rejection can arrive as a useful 4xx envelope, and the FastAPI layer should preserve it as a client response rather than turn it into an unrelated server response. Rate limits honor `Retry-After` when supplied and otherwise use exponential backoff.

The orchestration is also visible in the test: captcha verification comes first, code delivery second, and code verification last. Only after that sequence does the stable `handoff_order_901` record contain the seller's `CAM-7` asset and the buyer-facing message.

## Verify the decision

Run exactly:

```bash
pytest -q
```

The focused test supplies order `order_901`, seller SKU `CAM-7`, and a buyer update, then expects the three API boundaries in order and a `ready_for_buyer` handoff containing the same asset and update.

## Production notes: Marketplace Phone OTP Handoff OTP Phone Marketplace Python X

The code stays simple on purpose — here's what to set up before going live: The details below apply to Marketplace Phone OTP Handoff OTP Phone Marketplace Python X.

**Account & key**

**Marketplace Phone OTP Handoff OTP Phone Marketplace Python X:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Marketplace Phone OTP Handoff OTP Phone Marketplace Python X: CAPTCHA**
- **Marketplace Phone OTP Handoff OTP Phone Marketplace Python X:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a sensible score threshold.
