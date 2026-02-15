# Claim Verification RAG System — Design Document

**Document type:** Combined High-Level Design (HLD) and Low-Level Design (LLD)  
**Scope:** Current implementation (prototype); production/future scope noted briefly per section.  
**Purpose:** Architecture, flow, and design for demo and technical reference. Code-level detail is confined to Part II (LLD).

---

# Part I — High-Level Design (HLD)

High-level design describes the system in terms of **components, data flow, and technical decisions** without referencing specific files, functions, or code. It is suitable for stakeholder and demo presentations.

---

## 1. Architecture and Flow

### 1.1 System Overview

The system is an **agentic RAG (Retrieval-Augmented Generation)** pipeline that verifies user claims by:

- **Classifying** the claim (static vs dynamic vs invalid) and, when dynamic, identifying a **domain** (news, finance, weather, government, science, historical).
- **Querying a static knowledge base** (vector store of pre-ingested documents and verified facts) in parallel with classification.
- **Short-circuiting** when the claim is invalid or when the static KB returns sufficiently similar evidence (above a similarity threshold).
- **Invoking an agent** when static evidence is insufficient; the agent calls domain-specific live sources (web search, APIs), accumulates evidence, and triggers verification.
- **Verifying** the claim against gathered evidence via an LLM that returns a verdict, reasoning, and citations.
- **Optionally storing** stable facts back into the static KB for future reuse.

Components involved at a conceptual level:

- **Router** — LLM-based classifier: static / dynamic / invalid + optional domain.
- **Static KB** — Vector store (PostgreSQL with pgvector, HNSW index) over documents and facts; query-time embedding, similarity search, and optional reranking.
- **Dynamic sources** — Web search (with domain-restricted sources), weather API, and parallel science/historical search where applicable.
- **Agent** — Multi-step reasoner with tools (retrieval, verify, store); receives precomputed route and static result so it does not re-run routing or static search.
- **Verify & Synthesize** — LLM compares claim to evidence and returns verdict, reasoning, and citations; synthesis formats the final response.

### 1.2 Full Flow Diagram

The following diagram captures the end-to-end flow from user claim to verdict. Eager steps run in parallel; the rest is sequential.
![img](../rag-arch.png)

### 1.3 Flow Description

1. **Entry:** User claim is accepted. **Eager phase** runs two steps **in parallel**: (a) Router classifies the claim; (b) Static KB is searched (query is embedded, vector search on documents and facts, results merged, optionally reranked, similarity threshold evaluated).
2. **Invalid:** If the router returns “invalid”, the pipeline returns immediately with an “Invalid” verdict and no evidence.
3. **Static hit:** If the router did not return invalid and the static KB has at least one result with similarity at or above the configured threshold, the pipeline short-circuits: the static results are used as evidence, verification runs once, and the verdict plus citations are returned. No agent and no live web.
4. **Agent path:** If not invalid and not static hit, the agent is started with the **precomputed** route and static KB result (so it does not call the router or static search again). The agent reasons and may call tools (e.g. one domain-specific scraper). Evidence from tools is accumulated. When the agent calls verify, that evidence (and, when above threshold, static results) is passed to the verification step. After tools, if verify was already called the loop ends; otherwise control returns to the agent. Optional: after verify, the agent can call a store step that evaluates stability and, if stable, writes a normalized fact back to the vector DB (facts table).
5. **Verify & Synthesize:** Verification compares the claim to the evidence via an LLM and returns verdict, reasoning, and citations. Synthesis formats the final user-facing response (claim, verdict, reasoning, sources, optional reasoning trace).

Only the **Eager** step is parallel (route + static search). Static-hit and agent paths are mutually exclusive and sequential after that.

### 1.4 Production / Future Scope (Architecture)

For production, consider explicit observability (logging route, threshold outcome, path taken), idempotency keys for the verify API, and optional read replicas or a dedicated vector tier if scale demands it.

---

## 2. Embeddings

### 2.1 Role and Placement

Embeddings convert text into fixed-dimensional vectors so that semantic similarity can be computed (e.g. cosine). They are used in three places:

- **Ingestion (offline):** Each document chunk is embedded and stored with its vector in the documents table. Stable facts, when stored, are embedded and written to the facts table.
- **Query time:** The user claim is embedded once; that vector is used to search both the documents and the facts tables (same embedding for both).
- **Fact storage:** When a new stable fact is written to the KB, it is embedded once and inserted; if the fact already exists (by content hash), no embedding or insert is performed.

### 2.2 Current Design

- **Model:** A single embedding model is used for all of the above (documents, facts, and query). Default is OpenAI text-embedding-3-small.
- **Dimension:** Vectors have a fixed dimension (1536 for the default model), which must match the vector store schema.
- **Similarity:** Retrieval uses **cosine similarity** (exposed as a value in [0, 1]; the store uses cosine distance for ordering). The same metric is used for both tables.
- **Batching:** During ingestion, texts are sent to the embedding API in batches to respect rate limits and improve throughput; batch size is configurable (default on the order of a hundred texts per request).
- **Deduplication:** Before storing a fact, the system checks by content hash whether it already exists; if so, no embedding or insert is done, keeping the store consistent and avoiding duplicate work.

There is no embedding cache at query or ingestion time; repeated identical texts are re-embedded.

### 2.3 Production / Future Scope (Embeddings)

Production could add retries and backoff for the embedding API, an optional embedding cache for repeated queries or hot facts, and an abstraction over the embedding provider to allow swapping models or vendors without changing call sites.

---

## 3. Vector Database

### 3.1 Choice and Role

The static knowledge base is implemented using **PostgreSQL with the pgvector extension**. One database holds both relational metadata and vector columns, so there is no separate vector service. This fits moderate scale and keeps operations simple (single backup, single connection pool).

### 3.2 Data Model

- **Two tables** share the same vector dimension and distance semantics:
  - **Documents:** Ingested chunks (e.g. from parsed URLs). Each row has text content, embedding vector, source URL/title, chunk index, and a content hash for deduplication.
  - **Facts:** Verified, stable facts intended for reuse. Each row has the fact text, embedding, source URL/title, and content hash.
- **Indexing:** Both tables use an HNSW (Hierarchical Navigable Small World) index on the embedding column with cosine distance. Index build parameters (e.g. number of connections per node, construction quality) use common defaults suited to balanced recall and build time. Query-time HNSW parameters (e.g. search beam size) are not explicitly set and rely on the engine default.
- **Distance and operator:** Queries order by cosine distance and return a cosine-similarity score (e.g. 1 − distance) per row. The index operator class matches the distance (cosine), so the index can be used for search.

### 3.3 Write and Read Behavior

- **Writes:** Documents are inserted during ingestion; facts are inserted when the agent stores a stable fact. Inserts are deduplicated by content hash (normalized text). Each insert updates the HNSW index incrementally.
- **Reads:** At query time, the claim embedding is used in two independent similarity searches (documents and facts), each returning up to K nearest vectors (K configurable). Results are merged, optionally reranked, and the maximum similarity is compared to a threshold to decide whether the static KB is considered to have sufficient evidence.

### 3.4 Production / Future Scope (Vector DB)

Production could introduce schema migrations (e.g. versioned DDL), explicit query-time HNSW tuning (e.g. search beam size), connection retries and pooling, and observability (latency, index usage). For very large scale, a dedicated vector store or read replicas could be evaluated.

---

## 4. Chunking Strategy

### 4.1 Purpose and When It Runs

Chunking splits long documents into smaller segments so that each segment can be embedded and stored as one row. It runs **offline during ingestion only**; it is not part of the request-time path. Only the resulting chunks (and, later, stored facts) are embedded and searched.

### 4.2 Current Design

- **Unit of split:** Token count, not character or sentence. The same tokenizer used by common LLMs (e.g. cl100k_base) is used so that chunk sizes are consistent with model context limits.
- **Parameters:** Each chunk has a maximum token length (default 512). Consecutive chunks overlap by a fixed number of tokens (default 50) so that context is not lost at boundaries.
- **Algorithm:** The document text is tokenized once. If the token count is at or below the chunk size, the document is treated as one chunk. Otherwise, a sliding window is applied: the first chunk is tokens 0 to chunk_size; the next window starts at (end − overlap), and so on until the end. Each window is decoded back to text and trimmed. Chunk boundaries are thus determined only by token positions; there is no sentence- or paragraph-boundary logic in the current design.
- **Output:** Each chunk is associated with source URL, title, and a chunk index. These metadata fields are stored with the chunk in the vector store for attribution and display.

### 4.3 Production / Future Scope (Chunking)

Production could add sentence- or paragraph-aware splitting (e.g. split on sentence boundaries then merge to target token size), semantic chunking (grouping by embedding similarity), or multiple chunk sizes for different retrieval strategies.

---

## 5. Re-ranking Strategy

### 5.1 Role and When It Runs

Re-ranking runs **at query time**, inside the static KB search path. After the vector store returns the top-K candidates per table and results are merged, a re-ranker refines the ordering of these candidates before the similarity threshold is applied and before results are passed to the agent or to direct verification.

### 5.2 Current Design

- **Model:** A cross-encoder model is used: it takes (query, candidate text) pairs and outputs a relevance score. The model is a small, publicly available cross-encoder (e.g. ms-marco–style) chosen for speed and reasonable quality on retrieval-style tasks.
- **When it runs:** Re-ranking is applied only when the number of candidates (after merging documents and facts) exceeds a small threshold (e.g. greater than the final result count needed). When there are few candidates, re-ranking is skipped and candidates are ordered by the vector similarity score only, to save latency (on the order of one to two seconds).
- **Output:** Candidates are reordered by the re-ranker score; the top N (configurable) are kept. The threshold decision (whether static KB is “above threshold”) is still based on the **maximum cosine similarity** from the initial vector search, not on the re-ranker score, so that the short-circuit logic remains consistent.

### 5.3 Production / Future Scope (Re-ranking)

Production could use a stronger or domain-specific cross-encoder or a hosted rerank API, and could expose the re-ranker score in responses for debugging or tuning.

---

## 6. Knowledge Base: Static vs Dynamic

### 6.1 Static Knowledge Base

- **Content:** (1) Ingested document chunks (e.g. from curated URLs, parsed and chunked); (2) verified facts that have been normalized and stored after verification (e.g. “India won ICC T20 World Cup 2024”).
- **Access pattern:** Query is embedded once; vector search is run on both the documents and the facts tables; results are merged, optionally reranked, and the maximum similarity is compared to a configurable threshold. No live fetch; all data is pre-stored.
- **Update pattern:** Documents are added during batch ingestion. Facts are added when the agent explicitly triggers a “store fact” step after verification; a separate LLM step decides whether the evidence is “stable” and produces a normalized fact; deduplication by content hash prevents duplicates.

### 6.2 Dynamic (Live Web) Sources

- **Content:** Real-time or recent information: news, finance, government, science, weather, and historical/reference content. Not stored in the vector DB at ingestion time; fetched on demand per request.
- **Access pattern:** When the static KB is below the similarity threshold, the agent (guided by the router’s domain) calls one or more domain-specific tools. Those tools invoke web search (with domain-allowlisted sources) or dedicated APIs (e.g. weather). Results are returned as evidence items (snippet, URL, title) and accumulated for verification. Historical claims may trigger parallel search over multiple domains (e.g. science and news) and use the first sufficient evidence.
- **Update pattern:** No persistence of raw dynamic results into the vector DB; only after verification can a “stable” fact be normalized and stored in the facts table.

### 6.3 Coordination Strategy

Static is always queried first (in parallel with routing). If the router says the claim is invalid, the pipeline returns immediately. If the router says static or dynamic but the static KB is above the similarity threshold, the pipeline uses static results as evidence and does not call live sources. Only when the claim is not invalid and static is below threshold does the agent run and call dynamic tools. Evidence from static is only treated as valid evidence when above threshold; otherwise the agent must rely on dynamic evidence. Optional fact storage then allows some dynamic-sourced information to become static for future requests.

### 6.4 Production / Future Scope (Knowledge Base)

Production could add caching for static results keyed by claim (or query) hash, observability for route and threshold outcomes, and richer domain or source metadata for filtering and analytics.

---

## 7. Verification and Validation

### 7.1 Validation (Eligibility and Routing)

- **Input validation:** Before any LLM or retrieval, the claim is validated: it must be a non-empty string within a minimum and maximum length. If validation fails, the pipeline returns a single verdict (e.g. “Invalid”) with a short reason and no citations.
- **Router:** The router LLM classifies the claim into one of: static, dynamic, invalid. If dynamic, it also returns a domain (e.g. news, finance, weather, government, science, historical). Invalid or out-of-set values are normalized to safe defaults (e.g. invalid route or null domain). This is classification, not verification of the claim’s truth.
- **Static KB threshold:** A numeric check determines whether any retrieved chunk or fact has cosine similarity at or above the configured threshold (e.g. 0.6). This produces a boolean “above threshold” that drives short-circuit vs agent path and whether static results count as evidence.

### 7.2 Verification (Claim vs Evidence)

- **Input:** The claim string and a list of evidence items (each with content, source URL, source title). Evidence may come from the static KB and/or from dynamic tools.
- **Process:** Evidence text is truncated per source to cap prompt size. The verification LLM receives the claim and the evidence under a system prompt that defines verdict labels and rules (e.g. how to handle multi-part claims, when to use “Partly Verified” vs “Refuted”).
- **Output:** The LLM returns a structured object: verdict (one of a fixed set of labels), reasoning (free text), and citations (source URL, title, relevant snippet). If there is no evidence, the system does not call the LLM and returns a default verdict (e.g. “Inconclusive”) with a short reason. If the LLM response is missing or malformed, the same default verdict and reason are used.

### 7.3 Verdict and Route Values

- **Router output:** Route is one of: static, dynamic, invalid. Domain is one of: news, finance, weather, govt, science, historical, or null.
- **Verification verdicts (canonical):** Verified, Refuted, Partly Verified, Partly Refuted, Inconclusive, Mixed.
- **System verdicts (not from verification LLM):** Invalid (input or router), Incomplete (e.g. max steps reached without sufficient evidence or fallback failure).

The final response to the user includes the verdict, reasoning, and citations; optionally a formatted narrative and an agent reasoning trace when the agent path was taken.

### 7.4 Production / Future Scope (Verification and Validation)

Production could introduce typed enums for route, domain, and verdict; schema validation (e.g. Pydantic) for LLM outputs; and optional persistence of verification results (claim hash, verdict, timestamp) for audit and analytics.

---

# Part II — Low-Level Design (LLD)

Low-level design adds **implementation detail**: modules, entry points, key functions, and where behaviors are implemented. It follows the same section order as the HLD for easy cross-reference.

---

## 1. Architecture and Flow — Implementation

### 1.1 Entry Points

- **Programmatic API:** The main entry is a single function that accepts a claim string, runs validation, then invokes the agent pipeline. It returns a dictionary with claim, verdict, reasoning, citations, reasoning trace, and formatted response.
- **CLI:** A command-line script accepts the claim as arguments and prints the formatted response; it can optionally enable verbose logging or include the reasoning trace.
- **HTTP API:** A minimal Flask app exposes a POST endpoint that accepts a JSON body with a claim field, calls the same programmatic entry, and returns claim, verdict, reasoning, and citations in JSON. Health and CORS are handled for browser or extension clients.

### 1.2 Pipeline Orchestration

- The pipeline is implemented as a graph (e.g. LangGraph): nodes for “agent” (LLM with tools) and “tools” (tool execution), with conditional edges so that after tools the flow either returns to the agent or ends (e.g. when verify has already been called).
- Before the graph runs, two tasks are submitted in parallel using a thread pool: (1) router call (single LLM request returning route and domain); (2) static KB search (embed claim, search documents and facts, merge, optionally rerank, compute above_threshold). Results are then used for short-circuits and injected into the initial agent state so the agent does not call the router or static search tools again.
- Short-circuits: if the router result has route “invalid”, the function returns immediately with verdict “Invalid”. If route is not invalid and static result has above_threshold true and non-empty results, verification is run on the static results (sliced to a max evidence count), and the function returns with that verification result and a short reasoning trace. Otherwise, the graph is invoked with the claim and the precomputed route and static result in state.
- If the graph ends without a verification result (e.g. max steps reached), the pipeline attempts to run verification on any accumulated evidence; if there is none, it may run a fallback dynamic search (e.g. limited domains) and verify on that, or return an “Incomplete” verdict with a message.

### 1.3 Key Modules (by concern)

- **Router:** One module holds the router logic: build messages from the router system prompt and the claim, call the LLM with JSON response format, parse route and domain, and normalize invalid values.
- **Static retrieval:** One module implements static KB search: get embedding for the query, open a DB session, call document search and fact search (each with a top-K parameter from settings), close session, merge lists, run rerank or sort by similarity, compute max similarity and above_threshold from the merged list, return results and flags.
- **Dynamic retrieval:** One module dispatches by domain: weather uses a dedicated API client; other domains use web search (either a third-party search+scrape integration or the LLM provider’s web search with domain filters from config). Domain config (allowed domains, search instructions) is read from a YAML config. Historical domain can run multiple domain searches in parallel and return as soon as one returns evidence.
- **Agent and tools:** The agent is a graph node that receives the current state (messages, claim, evidence accumulator, precomputed route and static result), invokes the LLM with a system prompt and the list of tools (router, static KB, per-domain scrapers, weather, historical, verify, store_fact). The tools node executes the requested tool calls: for router and static KB it returns the precomputed state values; for scrapers it calls the dynamic retrieval layer; for verify it calls the verification function with the accumulated evidence (capped to a max count); for store_fact it enqueues a stability evaluation and insert on a background thread. Evidence from tools is merged into state; static KB results are only merged when above_threshold.
- **Verification and synthesis:** One module contains the verification function (claim + evidence → LLM → verdict, reasoning, citations) and the synthesis function (verdict + reasoning + citations + optional trace → formatted string). Evidence text is truncated per source before sending to the LLM; the verification prompt defines the six verdict labels and rules. Fallback verdict (e.g. “Inconclusive”) is used when evidence is empty or the LLM response is missing or invalid.

### 1.4 Production / Future Scope (Architecture — LLD)

Same as HLD: observability, idempotency, optional replication or dedicated vector tier. In code: add logging/metrics at short-circuit and agent-entry points; optional request-id and idempotency key in the API layer.

---

## 2. Embeddings — Implementation

### 2.1 Module and Client

- A single core module provides two entry points: one for a single text (returns one vector), one for a list of texts (returns a list of vectors, processed in configurable batch size). The same LLM-provider client (e.g. OpenAI) is used; the client is lazily initialized from settings (API key, model name). The model name and dimension are fixed in configuration and schema (e.g. text-embedding-3-small, 1536).

### 2.2 Call Sites

- **Ingestion:** The ingestion script parses URLs, chunks documents, then calls the batch embedding function with the list of chunk texts and a batch size (e.g. 100). The returned vectors are paired with chunk metadata and passed to the document insert function.
- **Query time:** The static retrieval module calls the single-text embedding function once with the claim string and uses that vector for both document and fact search.
- **Fact storage:** The store module, before inserting a fact, checks existence by content hash. If the fact is new, it calls the single-text embedding function with the normalized fact string, then passes the vector to the fact insert function.

### 2.3 Production / Future Scope (Embeddings — LLD)

Add retries/backoff around the embedding client calls; optional in-memory or distributed cache keyed by normalized text; and an interface (e.g. protocol or abstract class) so that the embedding implementation can be swapped without changing the three call sites above.

---

## 3. Vector Database — Implementation

### 3.1 Stack and Schema

- **Engine and session:** A database connection module creates an engine from a connection URL (from settings), sets pool size and overflow, and enables pre-ping. A session factory is bound to that engine; “get session” returns a new session; callers are responsible for closing it (e.g. try/finally).
- **Initialization:** An init function ensures the pgvector extension is created (raw SQL), then creates all tables and indexes from the declarative base metadata (single create_all call). No separate migration stack in the current codebase.
- **Models:** Two ORM models define the tables. Each has a UUID primary key, text content, optional source URL and title, a content hash (unique, indexed), timestamps, and an embedding column typed as vector with dimension 1536. One model has an extra chunk index field. Index objects are defined on the embedding column: HNSW, with m and ef_construction in the index options, and the cosine operator class. These index definitions are attached to the metadata so create_all creates them.

### 3.2 Operations

- **Document search:** A function takes session, query embedding (list of floats), and top_k. It builds a parameterized SQL string that casts the embedding to vector, selects from the documents table, orders by cosine distance (<=>), limits by top_k, and returns id, content, source fields, chunk_index, and similarity (1 − distance). The session execute returns rows that are mapped to a list of dicts.
- **Fact search:** Same pattern for the facts table (no chunk_index).
- **Insert document:** A function takes session, content, embedding, and optional metadata. It computes a content hash (normalized text), checks for an existing row with that hash; if found, returns without inserting. Otherwise it creates a new row, adds it, commits, and returns the instance.
- **Insert fact:** Same pattern: content hash, dedup check, then insert with embedding and metadata. Used by the ingestion path (documents) and by the store module (facts).

### 3.3 Where Index Is Used

- The HNSW indexes are created when init_db runs (create_all). They are used by the planner whenever the document or fact search runs the “order by embedding <=> … limit” query; no explicit query-time HNSW parameter (e.g. ef_search) is set in the current code.

### 3.4 Production / Future Scope (Vector DB — LLD)

Introduce migrations (e.g. Alembic) and replace create_all with migration steps; before running the search SQL, optionally execute a “set local” for ef_search; add retry/backoff in the connection layer and log or metricize search latency and errors.

---

## 4. Chunking Strategy — Implementation

### 4.1 Chunker Module

- A chunker module exposes a token-count function (encoding name fixed, e.g. cl100k_base) and two main functions: one that chunks a single text, one that chunks a list of documents (each with text, source_url, title) and returns a list of chunk dicts (text, source_url, title, chunk_index).
- Chunk size and overlap are read from settings (e.g. 512 and 50). The single-text function encodes the text, then if length ≤ chunk_size returns the whole text as one chunk; otherwise it runs a loop: window from start to start+chunk_size, decode to text, append; then start = end − overlap until the end of the token list. No sentence or paragraph splitting is implemented despite docstrings that might suggest it.

### 4.2 Ingestion Script

- The ingestion script imports the docling parser, the chunker, and the vectorizer. It initializes the DB, parses a fixed list of URLs (e.g. EU AI Act pages) via the parser (each URL → one or more documents with full text and metadata), runs the document chunker on the list of documents, then calls the vectorize-and-store function with the chunk list. The vectorizer extracts text from each chunk, calls the batch embedding function, then for each (chunk, embedding) pair calls the document insert function with a new session.

### 4.3 Production / Future Scope (Chunking — LLD)

Implement sentence-boundary or paragraph-boundary splitting (e.g. using a small NLP library or markdown structure) and merge segments to target token size; or add a second pass that uses embeddings to merge semantically close sentences into chunks.

---

## 5. Re-ranking — Implementation

### 5.1 Reranker Module

- A core reranker module lazily loads a cross-encoder model (e.g. from the Sentence Transformers family, by name). The rerank function takes the query string, a list of candidate dicts (each with a content key or a configurable key), and an optional top_k. It builds (query, content) pairs, runs the model’s predict on the pairs, attaches the score to each candidate, sorts by score descending, and returns the top_k candidates. Device is fixed (e.g. CPU) to avoid runtime issues on some environments.

### 5.2 Integration in Static Search

- The static retrieval module, after merging document and fact results, checks the length of the merged list. If length is at or below a small threshold (e.g. max(2, top_k_rerank)), it skips the reranker and instead sorts by the similarity field and slices to top_k_rerank. Otherwise it calls the rerank function with the query, the merged list, and top_k_rerank. The threshold (above_threshold) and max_similarity are computed from the merged list before this step (so they reflect the vector search scores, not the reranker scores).

### 5.3 Production / Future Scope (Re-ranking — LLD)

Swap or add a stronger cross-encoder or call a rerank API (e.g. Cohere) behind an interface; optionally add a rerank_score field to the response for debugging.

---

## 6. Knowledge Base: Static vs Dynamic — Implementation

### 6.1 Static KB

- Implemented in the static retrieval module: one public function that takes the query string, gets the query embedding, opens a session, calls document search and fact search with the same embedding and top_k from settings, closes the session, merges the two result lists, then applies the rerank-or-sort logic and computes above_threshold and max_similarity from settings (similarity_threshold). Returns a dict with results, above_threshold, and max_similarity. Document and fact search are implemented in the database operations module as described in Section 3.

### 6.2 Dynamic Sources

- A dynamic retrieval module exposes a search function that accepts query, optional single domain, or optional list of domains. For a single domain it delegates to an internal single-domain function. The single-domain function reads domain config from the shared YAML; if the domain is weather (or type api), it uses a weather fetcher class that calls an external weather API. Otherwise it gets the allowed domains list, optionally uses a third-party search+scrape client (if configured) with domain allowlists and claim context, or falls back to the LLM provider’s web search with domain filters. When multiple domains are requested, it iterates over them and concatenates results. Parallel execution (e.g. thread pool) is used when querying multiple sources within a domain or for historical (e.g. science + news in parallel). Early exit is implemented so that as soon as a minimum number of evidence items is reached, further calls can be skipped.

### 6.3 Fact Storage

- A store module implements evaluate-and-store: it takes claim, evidence list, and domain. If domain is weather it returns without calling the LLM. It builds an evidence text from the top few items, calls the LLM with a stability prompt (claim, domain, evidence), parses JSON for is_stable and normalized_fact. If not stable or no normalized_fact it returns. It then computes content hash for the normalized fact, opens a session, and checks for an existing fact with that hash; if found it returns “stored” without embedding or insert. Otherwise it gets an embedding for the normalized fact, opens a new session, and calls the fact insert function with content, embedding, and source from the first evidence item. The store is invoked from the agent’s store_fact tool, which runs the evaluate-and-store call in a background thread so the HTTP response is not blocked.

### 6.4 Production / Future Scope (Knowledge Base — LLD)

Add response caching in the static retrieval path (keyed by claim or embedding hash); log route, domain, and above_threshold in the agent entry; add domain/source to evidence metadata for analytics.

---

## 7. Verification and Validation — Implementation

### 7.1 Input Validation

- A validators module exposes a function that takes a claim string, checks non-empty and type, strips, then enforces min and max length (e.g. 5 and 2000 characters). On failure it raises a value error. The main programmatic entry catches that exception and returns a fixed response dict with verdict “Invalid”, the exception message as reasoning, and empty citations and trace.

### 7.2 Router

- The router module has one public function: claim in, messages built from the router system prompt (from the prompts module) and the claim, single LLM call with JSON response format. Response is parsed; route is validated against the three allowed values and defaulted to “invalid” if not; domain is validated against the allowed list and set to null if not in set. Returns a dict with route and domain.

### 7.3 Verification

- The verification module defines a constant for the fallback verdict (e.g. “Inconclusive”). The verify function: if evidence is empty, returns that verdict with a short reason and empty citations. Otherwise it truncates each evidence item’s content to a max length, builds a single evidence text block, calls the LLM with the verification system prompt and a user message containing claim and evidence, and parses the response. If the response is empty or not valid JSON, it returns the fallback verdict and reason. Otherwise it returns verdict (with get and default to the fallback), reasoning, and citations. The verification system prompt in the prompts module defines the six verdict labels and citation shape.

### 7.4 Stability (Store)

- The store module (see Section 6.3) uses a stability prompt that asks for is_stable (boolean) and normalized_fact (string or null). No verdict enum; the outcome is stored (boolean) and optional fact text.

### 7.5 Response Shape

- The programmatic entry returns a dict with: claim, verdict, reason/reasoning, citations, reasoning_trace (list of strings), and formatted_response (string). The HTTP endpoint returns a subset: claim, verdict, reasoning, citations. Verdict can be any of: the six verification labels, “Invalid”, or “Incomplete”.

### 7.6 Production / Future Scope (Verification — LLD)

Introduce enums for Route, Domain, and Verdict; validate and normalize LLM JSON with Pydantic; optionally persist verification results (e.g. claim hash, verdict, timestamp) to a table or log for audit.

---

**End of Design Document**
