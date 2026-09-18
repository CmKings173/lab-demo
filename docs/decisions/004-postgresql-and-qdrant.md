# ADR 004: Separate exact catalog data from document retrieval

## Context
Numeric product constraints and technical evidence have different correctness needs.

## Decision
Use PostgreSQL for catalog facts and Qdrant for future document chunks.

## Reason
Exact filtering must not depend on vector similarity.

## Alternatives considered
Store everything in a vector index or everything in one relational table.

## Consequences
The agent needs two controlled retrieval contracts and explicit source handling.
