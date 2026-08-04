# Decisions log

Lightweight ADR-style log. Add an entry **before** writing the code it
governs, not after — the schedule's milestone checks depend on entries
existing ahead of implementation (e.g. JWT vs. session, password hashing
algorithm, API key format, circuit-breaker failure threshold, cache
invalidation strategy).

## Format

```
### YYYY-MM-DD — <short decision title>
- **Decision:** what you chose
- **Why:** the reasoning / constraint that drove it
- **Alternatives considered:** what else you weighed, and why you didn't pick it
```

Newest entries at the bottom.

---
