# 🏆 AI League #1: RAG / Agentic RAG

## Problem Statement: Real-Time News Claim Verification

## System

## 📌 Background

Misinformation spreads faster than facts. Headlines, tweets, and viral posts frequently contain
claims that are misleading, partially true, or entirely false. Individuals and organizations
increasingly need tools that can validate such claims quickly using trustworthy evidence.
This hackathon focuses on building a real-world **Retrieval-Augmented Generation (RAG)**
system, optionally enhanced with **Agentic RAG** , to verify claims with citations and transparent
reasoning.
This challenge emphasizes **building an ever-growing knowledge base of facts and
evidence** , enabling fast retrieval and scalable verification.

## 🎯 Challenge

Build a **Real-Time News Claim Verification Assistant** that can take a user-selected claim from
the web and automatically:

1. Extract the claim (text snippet, paragraph, or headline)
2. Retrieve supporting or contradicting evidence from a knowledge base and/or web
    sources _(open to imagination)_
3. Cross-check and validate the claim
4. Provide a verdict with citations
5. Explain reasoning transparently
The solution must be built using a **RAG pipeline** , and teams are encouraged to extend it with
an **agentic workflow** (multi-step decision-making and verification loops).


## 🖥 Deployment Requirement

The solution must be demo-able through one of the following:
● Browser extension _(preferred)_
● Web app (Streamlit / Next.js / Flask)
● CLI tool with clean outputs
**Bonus points** if the browser extension allows:
● Highlight text → Click “Verify claim” → result popup

## ⚠ Constraints & Rules

```
● The system must always cite sources
● The system must not fabricate sources
● If evidence is missing, it must respond: “Not Enough Evidence”
```
## 📦 Expected Deliverables

Each team must submit:

1. Working demo application
2. Architecture diagram (RAG flow + components)
3. Short technical explanation of:
    ○ Embedding model used
    ○ Vector DB (if used)
    ○ Chunking strategy (if used)
    ○ Reranking approach (if used)
    ○ Knowledge base design + Live web validation strategy (Static GK vs Current
       Affairs)
    ○ Verification/Validation logic


