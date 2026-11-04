# Enterprise AI Agent Platform
### An Intelligent Multi-Agent Workspace for Enterprise Productivity

An AI-powered enterprise workspace that combines Large Language Models (LLMs), Retrieval-Augmented Generation (RAG), and Multi-Agent Architecture to automate everyday business workflows.

---

## 1. Project Overview

The Enterprise AI Agent Platform is a centralized AI-powered workspace designed to improve organizational productivity.

Users can interact with intelligent AI agents through natural language to retrieve information from enterprise documents, summarize meetings, generate reports, and automate routine tasks.

Unlike traditional chatbots, the platform uses an intelligent orchestration layer to route requests to specialized agents and retrieve context-specific information from organizational knowledge bases.

## 2. Key Features

- **AI Chat Assistant:** Context-aware conversations with persistent chat history.
- **Multi-Agent Architecture:** Specialized agents coordinated through an AI orchestrator.
- **RAG-Based Knowledge Retrieval:** Answers questions using uploaded enterprise documents.
- **Document Intelligence:** Processes PDF, DOCX, PPTX, and XLSX files.
- **Research Agent:** Retrieves relevant information from internal documents.
- **Meeting Assistant:** Summarizes transcripts and extracts decisions and action items.
- **Report Generator:** Generates structured business and project reports.
- **AI Email Assistant:** Drafts, rewrites, and improves professional emails.
- **Administrative Dashboard:** Monitors users, documents, usage, and system activities.
- **Security and Access Control:** Authentication, authorization, and controlled document retrieval.

## 3. Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | Next.js, React.js, TypeScript |
| UI | Tailwind CSS |
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| Vector Database | Qdrant |
| AI/LLM | OpenAI / compatible LLM integration |
| AI Framework | RAG, Multi-Agent Architecture |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| Validation | Pydantic |
| Containerization | Docker, Docker Compose |
| Frontend Hosting | Vercel |
| Backend Hosting | Render |
| Managed Database | Supabase |
| Vector Hosting | Qdrant Cloud |
| Version Control | Git, GitHub |

## 4. System Architecture

```text
             USER
               |
               v
       NEXT.JS FRONTEND
               |
               v
          FASTAPI
          BACKEND
               |
       AUTHENTICATION
       AUTHORIZATION
               |
               v
       AI ORCHESTRATOR
               |
       AGENT ROUTING
               |
     +---------+----------+
     |         |          |
     v         v          v
  Research   Meeting    Report
   Agent     Agent      Agent
     |         |          |
     +---------+----------+
               |
               v
          RAG PIPELINE
               |
        DOCUMENT RETRIEVAL
               |
               v
            QDRANT
         VECTOR SEARCH
               |
               v
       RETRIEVED CONTEXT
               |
               v
          LLM PROCESSING
               |
               v
        GENERATED RESPONSE
               |
               v
          USER INTERFACE
```

PostgreSQL separately maintains structured application data such as users, conversations, and other relational records.

## 5. Multi-Agent Architecture

The platform uses specialized AI agents to handle different user requests.

| Agent | Responsibility |
|---|---|
| Orchestrator Agent | Understands requests and coordinates agents |
| Research Agent | Searches enterprise knowledge |
| Email Agent | Drafts and improves emails |
| Report Agent | Generates structured reports |
| Meeting Agent | Summarizes transcripts and extracts action items |
| Document Agent | Analyzes uploaded documents |

### How Agent Routing Works

1. User submits a natural-language request.
2. The orchestrator identifies the user's intent.
3. The appropriate specialized agent is selected.
4. The agent executes the assigned task.
5. Multiple agents can coordinate for complex requests.
6. The final result is returned to the user.

## 6. Retrieval-Augmented Generation (RAG)

RAG allows the platform to answer questions using private enterprise knowledge.

### Document Processing Workflow

```text
Document Upload
      |
      v
Document Extraction
      |
      v
Text Chunking
      |
      v
Embedding Generation
      |
      v
Qdrant Vector Storage
      |
      v
User Question
      |
      v
Semantic Search
      |
      v
Relevant Context Retrieval
      |
      v
LLM Response Generation
      |
      v
Final Answer
```

### Why RAG?

- Uses organization-specific information.
- Improves response relevance.
- Reduces unsupported AI-generated answers.
- Enables semantic document search.
- Supports knowledge retrieval across multiple file formats.

## 7. Database Architecture

### PostgreSQL

Used for structured relational information, including:

- User information.
- Authentication-related records.
- Conversations and chat history.
- Application records and metadata.

### Qdrant

Used as a vector database for:

- Document embeddings.
- Semantic similarity search.
- Relevant document chunk retrieval.
- Contextual information retrieval for RAG.

### Object Storage

S3-compatible storage can be configured for uploaded documents.

## 8. Security Architecture

The platform incorporates multiple security considerations:

- Authentication to verify user identity.
- Authorization to control resource access.
- Role and organization-based access restrictions.
- Controlled document retrieval.
- Environment-based secret configuration.
- Secure API communication.
- Activity logging and audit trails.
- Protection of sensitive organizational information.

Security controls should be enforced at the backend and data-access layers rather than relying only on frontend restrictions.

## 9. Project Structure

```text
enterprise-ai-agent-platform/
|
|-- Backend/
|   |-- app/
|   |   |-- api/
|   |   |-- core/
|   |   |-- models/
|   |   |-- schemas/
|   |   |-- services/
|   |-- alembic/
|   |-- docker/
|   |-- tests/
|   |-- Dockerfile
|   |-- docker-compose.yml
|   |-- pyproject.toml
|
|-- Frontend/
|   |-- src/
|   |-- public/
|   |-- e2e/
|   |-- Dockerfile
|   |-- package.json
|
|-- ai/
|   |-- src/eap_ai/
|   |   |-- agents/
|   |   |-- export/
|   |   |-- ingestion/
|   |   |-- orchestrator/
|   |   |-- rag/
|   |   |-- vectorstore/
|   |-- eval/
|   |-- tests/
|   |-- Dockerfile
|   |-- pyproject.toml
|
|-- README.md
```

## 10. Docker and Deployment

Docker is used to package application services and their dependencies into containers.

### Benefits

- Consistent development and production environments.
- Easier application deployment.
- Service isolation.
- Simplified dependency management.
- Easier maintenance and scaling.

### Common Docker Commands

```bash
# Start services
docker compose up -d

# Build and start services
docker compose up --build -d

# Check running containers
docker ps

# View logs
docker compose logs -f

# Stop services
docker compose down
```

Run Docker Compose from the directory containing the relevant Compose file.

### Managed Hosting

The repository includes deployment support for:

- Vercel – Frontend hosting.
- Render – Backend hosting.
- Supabase – Managed PostgreSQL.
- Qdrant Cloud – Managed vector database.
- S3-compatible storage – Document storage.

Refer to `Backend/docs/DEPLOY.md` for the backend deployment procedure.

## 11. AI Evaluation Framework

The project includes a dedicated evaluation module to measure AI performance.

### Evaluation Dataset

- 36 answerable questions.
- 10 unanswerable questions.
- 7 fictional enterprise documents.
- Agent-routing test cases.

### Evaluation Metrics

| Metric | Purpose |
|---|---|
| Hit@K | Document retrieval accuracy |
| Keyword Recall | Expected information coverage |
| False Refusal Rate | Incorrect refusals |
| Refusal Accuracy | Correct handling of unanswerable questions |
| Groundedness | Support from retrieved sources |
| Router Accuracy | Agent selection correctness |
| Average Latency | Average response time |
| P95 Latency | 95th-percentile response time |
| Average Tokens | Token consumption |

### Running AI Evaluation

Start the required Qdrant service:

```bash
docker compose up -d
```

Run the evaluation:

```bash
uv run python eval/run_eval.py
```

Run without ingestion and LLM judging:

```bash
uv run python eval/run_eval.py --skip-ingest --no-judge
```

Compare evaluation configurations:

```bash
uv run python eval/run_eval.py --compare baseline.json optimized.json
```

Refer to `ai/eval/README.md` for dataset preparation, configuration tuning, and detailed evaluation instructions.

## 12. Team Members

| Team Member | Roll Number | Responsibility |
|---|---|---|
| Ashwin Yadav | 2329109 | AI/ML Development |
| Diptanshu Vishwa | 2329114 | Database & DevOps |
| Diyasha Nag | 2329116 | Backend Development |
| Sayantan Mazumdar | 2329148 | Frontend Development |

## 13. Future Enhancements

- Voice-based AI interaction.
- Mobile application.
- Calendar integration.
- Slack and Microsoft Teams integration.
- OCR support for scanned documents.
- Advanced enterprise analytics.
- Real-time collaboration.
- Workflow automation.
- Multi-language support.
- Offline and on-premise deployment.

## 14. Expected Outcomes

- Reduced time spent searching for enterprise information.
- Improved productivity through intelligent automation.
- Context-aware AI responses.
- Better document accessibility.
- Automated meeting and reporting workflows.
- A modular and scalable enterprise AI architecture.

## 15. Conclusion

The Enterprise AI Agent Platform demonstrates how Generative AI, RAG, and Multi-Agent Systems can be combined to create an intelligent enterprise productivity workspace.

By integrating document intelligence, agent orchestration, automated reporting, meeting assistance, and enterprise knowledge retrieval, the platform aims to simplify everyday organizational workflows while emphasizing security, scalability, and reliability.

---

**Project:** Enterprise AI Agent Platform  
**Domain:** Artificial Intelligence, Generative AI, Full-Stack Development  
**Academic Level:** B.Tech 7th Semester Major Project  
**Team Size:** 4 Members
