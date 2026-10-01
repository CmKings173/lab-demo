# Docker boundary

Lab 2's intended local stack is a structured-catalog PostgreSQL service, a separately
deployed WeKnora service for document parsing/indexing/retrieval, and the configured
local agent/model runtime. Lab2 does not own or directly deploy WeKnora's internal
vector-store implementation. Any future Compose profile must keep model, embedding,
reranking and storage providers on-prem; self-hosting WeKnora alone does not prove
that every configured dependency is offline.

The Lab2 source runtime and PostgreSQL/WeKnora adapters are implemented, but this
repository does not deploy a live WeKnora service or prove a GB300 setup. WeKnora
is expected on `127.0.0.1:8080`; the loopback-only Lab2 Tool API is `127.0.0.1:8090`.
See `references/weknora/SOURCE.md` for the pinned upstream deployment/source notes.
