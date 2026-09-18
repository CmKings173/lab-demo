# ADR 009: Final validation is code-driven

## Context
A proposal must not claim a product satisfies requirements without checking exact facts.

## Decision
Rule-based validation owns final validity; the LLM may explain results only.

## Reason
This prevents unsupported specifications and budget/resource mistakes.

## Alternatives considered
Let the LLM decide whether a product is suitable.

## Consequences
Unknown fields produce an explicit non-valid result until evidence is supplied.
