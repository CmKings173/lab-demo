# Infrastructure boundary

## Target hardware

The target is one workstation with an NVIDIA RTX PRO 5000 48GB. This is a
capacity target, not a claim that all future services can occupy the GPU at
once.

## Future services

- Docker for repeatable local service lifecycle.
- PostgreSQL for product catalog facts.
- Qdrant for technical-document retrieval.
- vLLM for the locally served Lab 1 model.
- OpenClaw for controlled local agent behavior.
- NemoClaw/OpenShell for future execution policy.

The initial phase has no server or GPU requirement. Service lifecycle must
allow training, model serving, embedding and reranking to start/stop by phase;
do not assume training, vLLM, BGE-M3 and reranker all stay resident together.

Network-dependent tests and cloud inference are explicitly excluded.
