# ADR 005: OpenClaw is an adapter boundary

## Context
The business workflow needs an agent but must not grant unrestricted data access.

## Decision
OpenClaw calls allow-listed domain tools for catalog and documents.

## Reason
The model must not generate arbitrary SQL or invent product facts.

## Alternatives considered
Direct LLM-to-database access or a bespoke agent framework.

## Consequences
Agent runtime integration is deferred while tool contracts remain testable.
