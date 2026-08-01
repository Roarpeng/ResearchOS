# GraphRAG Architecture

## Goal

Combine semantic retrieval with relationship reasoning.

## Pipeline

```
Documents
 |
Parser
 |
Entity Extraction
 |
Neo4j Graph
 |
Qdrant Embedding
 |
Hybrid Retrieval
 |
Agent Context
```

## Graph Entities

- Company
- Product
- Feature
- Document
- Patent
- Standard
- Review
- Version

## Relations

- HAS_FEATURE
- COMPARES
- REFERENCES
- UPDATED_BY
- PRODUCED_BY
