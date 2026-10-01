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
The source integration consists of a loopback FastAPI Tool API and an OpenClaw plugin
with exactly six allow-listed domain tools. Ingestion is not one of those tools.
Gateway/plugin loading and the Qwen3-14B end-to-end tool round trip on GB300 remain
unverified deployment work; source integration must not be presented as a live E2E pass.
