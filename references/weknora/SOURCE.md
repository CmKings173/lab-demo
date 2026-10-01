# WeKnora source reference — READ ONLY

This is source-derived integration metadata, not a vendored copy of WeKnora.

- Upstream: <https://github.com/Tencent/WeKnora>
- Release: `v0.8.0`
- Exact upstream commit: `1edcd54b43606d9079bb36650efe3f68707a79ea`
- Retrieved and inspected: `2026-09-24`
- Status: **READ ONLY**. Do not patch or copy upstream implementation into this repository.

The temporary upstream checkout used for this audit was kept outside the project
workspace. To reproduce it without adding vendor files to project history:

```powershell
git clone --filter=blob:none --no-checkout --depth 1 --branch v0.8.0 https://github.com/Tencent/WeKnora.git references/weknora/upstream
git -C references/weknora/upstream checkout --detach 1edcd54b43606d9079bb36650efe3f68707a79ea
git -C references/weknora/upstream describe --tags --exact-match
```

`references/weknora/upstream/` is ignored by the project. The tracked source of
truth is this pin and the upstream paths linked below.

## Source-derived API and behavior

All findings below refer to the pinned commit, not an unpinned `main` branch.

| Lab2 concern | WeKnora v0.8.0 source/API | Integration consequence |
|---|---|---|
| Knowledge base setup | `POST /api/v1/knowledge-bases`; supports a document KB and configuration including chunking and model/storage selections | Create/configure a stable Lab2 KB once; do not create a new KB per import run. The parser, chunker, embedding and index configuration belong to WeKnora. |
| File ingestion | `POST /api/v1/knowledge-bases/{kb_id}/knowledge/file` with multipart `file`; optional `fileName`, `metadata` (JSON string) and processing overrides | Lab2's future importer should upload only from its configured document directory and persist the returned knowledge ID in its product-document mapping. |
| Duplicate upload | The pinned knowledge API documents HTTP `409` for a duplicate file and returns a reference to the existing knowledge record. | Check Lab2 mapping before upload; if WeKnora reports a duplicate, reconcile the existing knowledge ID instead of creating an endless retry/failure loop. |
| Parse lifecycle | Upload response includes `data.id` and `parse_status`; `GET /api/v1/knowledge/{knowledge_id}` exposes status. States include `pending`, `processing`, `finalizing`, `completed`, `failed`, and `cancelled`. | Treat `finalizing` as still in progress; only report ready at `completed`. Do not poll indefinitely. |
| Document metadata | Knowledge/search results expose fields such as knowledge ID, title, filename, source/channel and metadata. Upload metadata is a string-to-string map. | Product association is owned by Lab2 mapping; metadata may duplicate a product ID for traceability, but it is not a `knowledge-search` filter. |
| Search | `POST /api/v1/knowledge-search`; body accepts `query`, `knowledge_base_id` or `knowledge_base_ids`, and optional `knowledge_ids`. It returns retrieved chunks without an LLM answer. | Use this endpoint as the primary retrieval adapter. For product-scoped requests send the configured KB ID together with mapped knowledge IDs. Without a product ID search only the configured Lab2 KB. |
| Product/document filter | `knowledge_ids` restricts search to selected knowledge files. The documented `knowledge-search` request has no arbitrary product-metadata predicate. | Resolve `product_id -> product_documents -> knowledge_ids` in Lab2 before the WeKnora call. If mapping is empty, return no evidence without issuing a broad search. |
| Result chunk | `SearchResult.id`, `content`, `knowledge_id`, `chunk_index`, `knowledge_title`, `knowledge_filename`, `metadata`, `seq`, `score`, and offsets | Map ID/content/knowledge identity/title/filename from actual response fields. Do not infer a page number from `chunk_index` or character offsets. |
| Result limit and total | `knowledge-search` request has no `top_k`; response is `data[]` without a total-count field | Apply `DocumentSearchRequest.top_k` client-side. `DocumentSearchResult.total` can only represent the number returned by WeKnora before local truncation, not a corpus-wide match count. |
| Ranking score | API documentation defines `score` as the final rerank-normalized score; `seq` is the hit ordering | It is not a separate raw retrieval score and not a separate rerank score. Preserve provider score as provider metadata unless a reviewed mapping policy is adopted; never label it as a raw vector score. |
| Citation provenance | Search results provide chunk ID, knowledge ID, title and filename; no dedicated `page` or `source_url` field is defined in the search result contract | `page` stays null unless actual returned metadata explicitly supplies a page. `source_url` may come only from a verified Lab2 document mapping, otherwise null. Build citations from retrieved hits, never from model-authored metadata. |
| Authentication | API examples use `X-API-Key` | Keep the key in server-side configuration; do not return or log it. |
| Self-host deployment | Pinned `docker-compose.yml` includes the WeKnora app, DocReader and internal dependencies (including PostgreSQL/Redis) with vector-store deployment options | WeKnora is a separate service and owns its internal parsing/retrieval stack. Lab2's structured catalog PostgreSQL remains a distinct source of truth. Self-hosting does not itself guarantee offline operation: choose local model, embedding, reranking and storage providers and disable cloud/web integrations. |

## Contract mapping and compatibility gaps

| Existing Lab contract | Mapping / limitation |
|---|---|
| `DocumentSearchRequest.query` | `knowledge-search.query`. |
| `DocumentSearchRequest.product_id` | Not sent as a provider filter. Resolve through Lab2's product-document repository to the configured KB ID and a list of WeKnora knowledge IDs. |
| `DocumentSearchRequest.top_k` | No corresponding request field. Retrieve using the provider's configured behavior and truncate client-side; this cannot guarantee the same recall as a provider-side top-k. |
| `DocumentChunk.id` / `.text` | `SearchResult.id` / `.content`. |
| `DocumentChunk.product_id` | Set only from a product-scoped request or verified returned metadata/mapping. Do not guess it from filename. |
| `DocumentChunk.page` | Not directly mapped by the pinned search result schema; leave `None` unless actual response metadata contains a documented page value. |
| `DocumentChunk.source_url` | Not directly present in search hits. Use a stored, verified `ProductDocument.source_url` mapping when available; otherwise `None`. |
| `DocumentChunk.metadata` | `SearchResult.Metadata` is `map[string]string`, directly compatible with the shared `dict[str, str]` shape; copy only metadata actually present in the provider response. |
| `DocumentHit.rank` | Use actual response ordering/`seq` where valid; do not derive it from score. |
| `DocumentHit.retrieval_score` / `.rerank_score` | The API supplies one final normalized score, not two distinct scores. Preserve it as provider score metadata and leave both dedicated fields unset until an explicit contract mapping is reviewed. |
| `DocumentSearchResult.total` | API response has no total field; report count in the received result array (before local top-k truncation), not a claimed total corpus match count. |

These limitations are adapter concerns. Do not add WeKnora models to `shared/contracts`
or change shared public contracts as part of source documentation.

## Pinned upstream references

- [Release v0.8.0](https://github.com/Tencent/WeKnora/releases/tag/v0.8.0)
- [Knowledge base API](https://github.com/Tencent/WeKnora/blob/1edcd54b43606d9079bb36650efe3f68707a79ea/docs/api/knowledge-base.md)
- [Knowledge/file API and parse status](https://github.com/Tencent/WeKnora/blob/1edcd54b43606d9079bb36650efe3f68707a79ea/docs/api/knowledge.md)
- [Knowledge search API](https://github.com/Tencent/WeKnora/blob/1edcd54b43606d9079bb36650efe3f68707a79ea/docs/api/knowledge-search.md)
- [Search result source type](https://github.com/Tencent/WeKnora/blob/1edcd54b43606d9079bb36650efe3f68707a79ea/internal/types/search.go)
- [Self-host Docker Compose](https://github.com/Tencent/WeKnora/blob/1edcd54b43606d9079bb36650efe3f68707a79ea/docker-compose.yml)
