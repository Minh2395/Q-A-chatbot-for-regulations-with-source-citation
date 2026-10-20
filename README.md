# Q&A Chatbot for Regulations with Source Citation

## 1. Overview

**Q&A Chatbot for Regulations with Source Citation** is an AI-assisted question-answering system designed to help users access information about housing and land regulations.

The system retrieves information exclusively from an approved document repository and generates answers supported by verifiable source citations. Each answer is designed to include relevant legal provisions, source excerpts, and document versions.

The project follows object-oriented software design principles, emphasizing separation of responsibilities, maintainability, testability, and extensibility.

## 2. Objectives

- Answer natural-language questions about housing and land regulations.
- Retrieve relevant information from approved documents.
- Provide source citations, including document identifiers, relevant provisions, and source excerpts.
- Track document versions and their verified legal status.
- Refuse to answer when sufficient supporting evidence is unavailable.
- Provide an evaluation dataset containing at least 50 questions.
- Support automated testing and system quality evaluation.

## 3. Technology Stack

### Backend

- Python
- FastAPI
- Uvicorn
- Pydantic
- Python Virtual Environment (`.venv`)

### Frontend

- React
- TypeScript
- Vite
- CSS

### Planned Technologies

- Oracle Database or another suitable relational database.
- Vector store for semantic search.
- Retrieval-Augmented Generation (RAG).
- OpenTelemetry for observability and performance monitoring.

Additional technologies will be integrated as the project evolves.

## 4. Project Structure

```text
chatbotAI/
├── backend/
│   ├── .venv/
│   ├── app/
│   │   ├── api/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── repositories/
│   │   └── main.py
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   ├── package-lock.json
│   └── vite.config.ts
├── .gitignore
├── README.md
└── LICENSE.md
```

This structure represents the planned project organization. Some directories and files may not exist during the initial setup phase.

## 5. Prerequisites

Install the following tools before running the application:

- Python 3.12 or another compatible version.
- Node.js LTS compatible with the selected Vite version.
- npm.
- Visual Studio Code.
- Git (optional, for version control).

## 6. Installation and Setup

### 6.1. Clone the Repository

```bash
git clone <repository-url>
cd chatbotAI
```

Replace `<repository-url>` with the actual repository URL. Skip this step if the project already exists locally.

### 6.2. Set Up the Backend

Navigate to the backend directory:

```powershell
cd backend
```

Create a virtual environment:

```powershell
py -m venv .venv
```

Activate the virtual environment in Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, use Command Prompt instead:

```cmd
.venv\Scripts\activate.bat
```

Upgrade pip and install FastAPI:

```bash
python -m pip install --upgrade pip
pip install "fastapi[standard]"
```

Save the installed dependencies:

```powershell
pip freeze > requirements.txt
```

To install dependencies from an existing requirements file:

```bash
pip install -r requirements.txt
```

### 6.3. Run the Backend

From the `backend` directory, run:

```bash
python -m uvicorn app.main:app --reload
```

The backend will be available at:

- API root: http://127.0.0.1:8000
- Health check: http://127.0.0.1:8000/api/health
- Interactive API documentation: http://127.0.0.1:8000/docs

### 6.4. Set Up the Frontend

Open a separate terminal at the project root and navigate to the frontend directory:

```powershell
cd frontend
```

Install dependencies:

```bash
npm install
```

If the frontend application has not been initialized yet, run the following command from the project root:

```bash
npm create vite@latest frontend -- --template react-ts
```

Only run the initialization command when the directory does not already contain an application. Avoid overwriting existing files.

### 6.5. Run the Frontend

From the `frontend` directory, run:

```bash
npm run dev
```

The development server will typically be available at:

http://localhost:5173

Keep the backend and frontend running in separate terminals.

## 7. System Workflow

The intended question-answering workflow is:

1. The user submits a question about housing or land regulations.
2. The frontend sends the question to the backend through a REST API.
3. The backend retrieves relevant passages from the approved document repository.
4. The system evaluates whether the retrieved evidence is relevant and sufficient.
5. If sufficient evidence is available, the system generates an answer supported by source citations.
6. If sufficient evidence is unavailable, the system refuses to provide an unsupported answer.
7. The frontend displays the answer and its supporting sources.

## 8. Citation and Reliability Requirements

Each answer should provide the following information when available and verified:

- Answer content.
- Source document title.
- Document number or identifier.
- Relevant article, clause, or point.
- Supporting source excerpt.
- Document version.
- Verified legal status and applicable period.

Only approved documents may be used as authoritative sources. Model-generated text must not be treated as legal evidence.

## 9. Testing and Evaluation

The project aims to establish an evaluation dataset containing at least 50 questions, covering:

- Questions with sufficient supporting evidence.
- Questions requiring multiple source passages.
- Ambiguous questions or questions missing essential information.
- Questions not covered by the document repository.
- Questions involving different document versions.
- Questions designed to detect unsupported answers or fabricated citations.

### Evaluation Metrics

- Answer correctness.
- Citation accuracy and traceability.
- Evidence sufficiency assessment.
- Appropriate refusal behavior.
- Document version identification.
- Response latency and system stability.

## 10. Development Roadmap

- Implement the chatbot user interface.
- Develop question-answering and document management APIs.
- Design data models for documents, versions, and source passages.
- Integrate semantic search and RAG.
- Implement evidence validation and refusal mechanisms.
- Develop an automated evaluation dataset with at least 50 questions.
- Add logging, monitoring, and OpenTelemetry integration.
- Deploy the application and complete technical documentation.

## 11. Contribution Guidelines

Code changes should be tested before being merged into the main branch. New features should include relevant test cases and documentation updates.

The project's source code is subject to the terms specified in [LICENSE.md](LICENSE.md).

## 12. License

This project is proprietary software. All rights are reserved by the applicable copyright holder. See [LICENSE.md](LICENSE.md) for details.
