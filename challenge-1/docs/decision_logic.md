## Decision Logic

Decisions made by LLM:

1. Does the query require real-time data?
   - Examples:
     - "Who won the US election?" → real-time
     - "What is GDP?" → static
    
2. Opinion questions or invlid questions which are not appropriate should be ignored (Not valid).

3. If real-time:
   - Identify domain:
     - news
     - finance
     - weather
     - government policy

4. After retrieval:
   - Is this information stable enough to store?
     - Yes → vectorize + store
     - No → ephemeral response only
