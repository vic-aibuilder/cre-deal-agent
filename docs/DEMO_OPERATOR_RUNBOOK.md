# Demo Operator Runbook (Joel)

This runbook is for operating the CRE demo end-to-end when Michael is unavailable.

## Goal

Show, live, that the agent can:

- send broker outreach email autonomously
- monitor inbox replies on the deal thread
- flag counter language for negotiation handoff

## 1) Open the project

Use the project root:

`/Users/michaelchabler/Documents/CRE Agent`

## 2) Generate Joel's Gmail access token

Use OAuth Playground with your own OAuth client.

1. Open https://developers.google.com/oauthplayground
2. Click the settings gear icon (top-right).
3. Enable `Use your own OAuth credentials`.
4. Paste your Web OAuth Client ID and Client Secret.
5. Add both scopes:
   - `https://www.googleapis.com/auth/gmail.send`
   - `https://www.googleapis.com/auth/gmail.readonly`
6. Click `Authorize APIs` and sign in as Joel.
7. Click `Exchange authorization code for tokens`.
8. Copy the `access_token`.

If you see `redirect_uri_mismatch`, your OAuth client is wrong type. Use a **Web application** client with redirect URI:

`https://developers.google.com/oauthplayground`

## 3) Put token in .env

Open `.env` in project root and set:

```bash
GMAIL_ACCESS_TOKEN=YOUR_TOKEN_HERE
```

Never commit or share this token.

## 4) Verify mailbox access

Run:

```bash
cd "/Users/michaelchabler/Documents/CRE Agent"
python3 scripts/email_smoke_test.py
```

Expected output includes:

- `Gmail smoke test passed.`
- Joel's email address

## 5) Run full demo

Run:

```bash
cd "/Users/michaelchabler/Documents/CRE Agent"
python3 main.py
```

Use these inputs:

- Asset type: `industrial`
- Submarket: `Phoenix-Mesa-Chandler`
- Price: `95000000`
- Cap rate: `5.8%`
- Key tenants: `Amazon · 65% of NOI`
- Lender: `Wells Fargo`
- DSCR constraint: `1.25`
- Listing broker email: demo recipient email
- Property address: demo address
- LOI PDF path: leave blank unless testing LOI send

Approve at checkpoint with `yes`.

## 6) Trigger negotiation detection (recommended)

Ask recipient to reply in-thread with counter language like:

`Counter at 96M with revised terms and 20-day due diligence.`

Then run:

```bash
cd "/Users/michaelchabler/Documents/CRE Agent" && python3 - <<'PY'
from pathlib import Path
from dotenv import load_dotenv
from agents.email_agent import monitor_broker_inbox

load_dotenv(Path('.env'))

# Replace with thread id printed by send step.
thread_id = 'REPLACE_THREAD_ID'

events = monitor_broker_inbox(active_thread_ids=[thread_id], max_results=50)
print('events_found:', len(events))
for event in events:
    print('---')
    print('from:', event.get('from'))
    print('subject:', event.get('subject'))
    print('action:', event.get('action'))
    print('snippet:', event.get('snippet'))
PY
```

Success condition:

- one event with `action: trigger_negotiation_agent`

## 7) Demo fallback if reply is delayed

If inbox reply does not appear immediately, wait 30-60 seconds and rerun monitor once.

## 8) Security cleanup after demo

- Revoke temporary OAuth grant if needed.
- Replace token in `.env` before handing machine to others.
