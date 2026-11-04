# BootSight

**A dead PC is a photograph away from a repair plan.**

BootSight is a copilot for field technicians. You photograph the screen of a machine
that won't boot — BIOS text, a bluescreen, a kernel panic, a RAID controller warning —
and it tells you what you are looking at, what it means, and the exact next command to
run. Then it writes the ticket.

Built for the [Meta Global AI Developer Hackathon](https://cerebralvalley.ai/e/meta-ai-developer-hackathon)
(startup track). No code from any private product is included in this repository.

## The problem

A technician arrives at a machine that won't start. The first ten minutes are spent
decoding a screen: is this a dead disk, a bad boot sector, a corrupted driver, or a
loose SATA cable? The answer is on the screen, but reading it requires experience the
junior tech on site does not have yet. So they take a photo and send it to someone
senior, and wait.

That wait is the product.

## What it does

1. **Read the screen.** A photo goes to `muse-spark-1.3` (vision + structured output).
   The model returns the machine state as data: vendor, boot phase, error codes,
   the exact strings that matter, and what it cannot see.
2. **Locate the evidence.** `sam-3.1` segments the region of the photo that carries the
   error — the STOP code line, the SMART warning, the missing-boot-device message — so
   the technician knows what to look at, not just what to read.
3. **Build a plan.** The model proposes repair steps, each one with a command, the
   expected output, and the condition that means "stop, this is not the problem".
4. **Record it.** The run is exported as a ticket: photo, diagnosis, steps taken,
   outcome. That record is what turns a lucky fix into a repeatable one.

Every step is a **read-only diagnostic** by default. Anything that writes to the disk
requires an explicit, separate confirmation and is refused in demo mode.

## Why this wins the startup track

The startup track is judged on technical execution and whether it holds up in
production. BootSight is not a weekend prototype of an idea: it is a narrow tool with a
hard safety boundary, a deterministic schema, a test suite that runs without network
access, and a cost model that fits a real service business.

## Stack

- Python 3.13, FastAPI, no build step.
- `muse-spark-1.3` over the OpenAI-compatible endpoint at `https://api.meta.ai/v1`.
- `sam-3.1` for segmentation masks.
- Vanilla HTML/JS front end, served by the same process. Works on a phone.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # put your MODEL_API_KEY in it
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8099
```

Open `http://localhost:8099`.

Without a key, run in mock mode and the whole flow still works end to end:

```bash
BOOTSIGHT_MOCK=1 .venv/bin/python -m uvicorn app.main:app --port 8099
```

## Tests

```bash
.venv/bin/python -m pytest -q
```

The suite covers schema validation, the command allowlist, and a full diagnosis cycle
against the mock backend. It does not touch the network.

## Licence

Apache-2.0. See `LICENSE`.
