# ADR-003: Search-First UI with LLM-Parsed Tag Pills

**Date:** 2026-05-17  
**Status:** Accepted

## Context

The primary user interaction is finding samples. Three UI patterns were considered:

- **A — Search First**: Prominent search bar dominates. Type natural language or tags, results appear instantly. No sidebar. Clean, fast, Spotlight-like.

- **B — Browse + Filter Panel**: Filter panel on the left (click tags to narrow), results list on the right, search bar at the top. Good for exploration when you're not sure what you want.

- **C — Search + Active Tag Pills**: Natural language query at the top. The LLM parses it into structured tag pills shown below the search bar — you can remove or add individual pills. Results update live as pills change. Best of search and filter in one flow.

## Decision

**Chose Option C — Search + Active Tag Pills.**

## Rationale

1. **Natural language first**: Producers think in musical terms ("dark, tense, no transients"). The LLM translates that directly to structured filters — no manual tag selection needed.
2. **Editable results**: The tag pills are interactive — remove ones the LLM got wrong, add ones it missed. The LLM gets you 90% there; manual adjustment handles the rest.
3. **Live feedback**: Results update as pills change, so the user sees the narrowing effect immediately.
4. **No sidebar clutter**: Unlike the browse panel, search mode uses full width for results. Browse is a separate screen for exploration.
5. **Two modes, not one**: Search and Browse are separate tabs — not a hybrid single screen. Search is for when you know what you want; Browse is for discovery.

## Consequences

- Requires LLM call on every search submit (adds latency, ~200-500ms)
- Tag pill UI is custom — no standard component library
- Need to handle LLM parsing failures gracefully (fall back to text search)
- Two distinct modes means duplicating some result-rendering logic (mitigated by shared `SampleRow` component)
