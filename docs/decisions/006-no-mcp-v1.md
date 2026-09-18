# ADR 006: No MCP in version 1

## Context
The initial product scope does not need a general tool protocol.

## Decision
Do not add MCP implementation or dependency in Phase 0-1.

## Reason
Controlled Python interfaces are sufficient for the foundation and reduce attack surface.

## Alternatives considered
Add MCP immediately for future extensibility.

## Consequences
Any later MCP boundary must be an explicit, reviewed integration decision.
