## High-Level Architecture

Flow:

1. User Query
2. Query Router (LLM-based)
   - Classifies query as:
     a) Static fact (vector DB)
     b) Dynamic / real-time fact
3. If static:
   - Retrieve from pgvector
   - If not available move to dynamic
4. If dynamic:
   - Decide source domain (news, finance, weather, govt policy)
   - Search & scrape websites or call APIs
   - Decide whether new fact should be vectorized
   - Store verified info in vector DB (use appropriate chunking strategy)
5. Final Response:
   - Augment retrieved data
   - Format answer
   - Provide citations / timestamps
