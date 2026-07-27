# Architecture Decision Records

Use ADRs for durable decisions that future agents must not repeatedly rediscover or re-litigate.

Create an ADR when a decision changes:

- a public API or persisted contract;
- a domain invariant or source of truth;
- data ownership, privacy, or security behavior;
- a provider seam or compatibility promise;
- deployment topology or operational safety;
- a reused dependency with material license or maintenance consequences.

Do not create ADRs for local bug fixes, temporary experiments, naming cleanups, or choices already obvious from code.

Name files `NNNN-short-decision-title.md` and use:

```md
# ADR-NNNN: Decision title

Status: Proposed | Accepted | Superseded
Date: YYYY-MM-DD
Supersedes: ADR-NNNN, if applicable

## Context

What evidence or constraint forced a decision?

## Decision

What is now true?

## Consequences

What becomes easier, harder, required, or forbidden?

## Alternatives considered

What credible alternatives were rejected and why?

## Verification

Which tests, traces, measurements, or user observations validate the decision?
```

## Current records

- `0001`–`0006`: existing Product API, provider, deployment, and Skill decisions.
- `0007-native-ios-trip-planning-and-storekit.md`: native iOS Journey client, generated API contracts, offline store, StoreKit entitlement truth, and China-first dependency boundary.
