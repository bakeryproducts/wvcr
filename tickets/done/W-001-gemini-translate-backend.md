# Ticket: Gemini Realtime Translate Backend

## Motivation

We have a working OpenAI-backed live translation pipeline (`wvcr-translate`)
that hijacks the system mic via a virtual PipeWire device. It works, but locks
us into one provider, one pricing curve, and one set of language/voice
trade-offs.

Gemini exposes its own realtime/live translation surface. Adding it as a
second backend gives us:

- **Provider choice per session** — pick the model that handles a given
  language pair best (Gemini may win on some, OpenAI on others).
- **Fallback / resilience** — when one provider has an outage or rate-limits,
  the other is one preset switch away.
- **Cost flexibility** — route casual sessions to the cheaper backend, keep
  the premium one for high-stakes calls.
- **Latency comparison** — empirically measure first-audio and
  end-of-utterance latency between the two on real calls.
- **Voice / style differences** — different models, different translated
  voice character; user preference may swing either way.

## Scope

Reuse everything that isn't OpenAI-specific:

- virtual mic + loopback infra (`audio.py`)
- wofi picker, presets, recording, CLI lifecycle (`runner.py`, `cli.py`,
  `recorder.py`, `presets.py`)

Add only what's provider-specific:

- a Gemini session client (parallel to `session.py`)
- a backend selector (config or CLI flag) so a preset can pin a backend
- preset schema gains an optional `backend: openai | gemini` field

## Out of Scope

- Mixing backends mid-session
- Quality benchmarking harness (separate ticket)
- Streaming both backends in parallel for A/B comparison

## Success Criteria

- `wvcr-translate toggle` with a Gemini preset behaves identically from the
  user's POV: hotkey → wofi → Meet hears translated audio
- Switching between OpenAI and Gemini presets requires only a preset edit,
  no code change
- Recording (`--record`) saves source + translated WAV regardless of backend
