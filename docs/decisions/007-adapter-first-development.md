# ADR 007: Adapter-first development

## Context
GPU and infrastructure are not yet available.

## Decision
All workflow dependencies use protocols and deterministic fakes before real adapters.

## Reason
Business logic and tests must run without GPU, network or SaaS services.

## Alternatives considered
Start with vLLM, PostgreSQL and Qdrant clients.

## Consequences
Production integrations can be added behind existing seams without changing workflow contracts.
