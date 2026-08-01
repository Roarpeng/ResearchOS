# ResearchOS Technology Selection

## Runtime

| Component | Choice | Reason |
|-|-|-|
| Agent Runtime | LangGraph | Stateful agent orchestration |
| API | FastAPI | Async Python ecosystem |
| Model Gateway | LiteLLM | Multi-provider abstraction |

## Knowledge

| Component | Choice | Purpose |
|-|-|-|
| Vector DB | Qdrant | Semantic retrieval |
| Graph DB | Neo4j | Entity relationships |
| Metadata | PostgreSQL | Business data |
| Object Storage | MinIO | Documents |

## AI Models

ResearchOS does not lock models.

Supported:

- OpenAI
- Claude
- Gemini
- Qwen
- DeepSeek
- Ollama

## Design Principle

Infrastructure must remain independent from model providers.
