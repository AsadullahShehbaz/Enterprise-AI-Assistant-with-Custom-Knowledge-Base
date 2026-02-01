# Persistent Chatbot API

A production-ready chatbot system with calculator tools, RAG-based document query, PostgreSQL thread-level memory, and JWT authentication.

## 🚀 Features

- **JWT Authentication**: Secure user registration and login
- **Calculator Tool**: LangGraph agent with mathematical computation capabilities
- **RAG System**: PDF document upload and semantic search using ChromaDB
- **Thread-Level Memory**: Persistent conversation history stored in PostgreSQL
- **FastAPI Backend**: High-performance async API with automatic docs
- **SQLAlchemy ORM**: Type-safe database operations
- **Multi-User Support**: Isolated data and conversations per user

## 📋 Prerequisites

- Python 3.9+
- PostgreSQL 12+
- OpenAI API Key

## 🛠️ Installation

1. **Clone and setup environment**
```bash
git clone <your-repo>
cd persistent-chatbot
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure PostgreSQL**
```bash
# Create database
createdb chatbot_db

# Or using psql
psql -U postgres
CREATE DATABASE chatbot_db;
\q
```

3. **Environment variables**
```bash
cp .env.example .env
# Edit .env with your credentials
```

Required variables:
- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: Generate with `openssl rand -hex 32`
- `OPENAI_API_KEY`: Your OpenAI API key

4. **Initialize database**
```bash
python -m app.database
```

5. **Run the server**
```bash
uvicorn app.main:app --reload
```

API will be available at `http://localhost:8000`

## 📚 API Documentation

Interactive docs available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🔑 API Endpoints

### Authentication

**Register User**
```bash
POST /api/auth/register
{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "secure_password"
}
```

**Login**
```bash
POST /api/auth/login
Form Data:
  username: john_doe
  password: secure_password

Response:
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Get Current User**
```bash
GET /api/auth/me
Headers: Authorization: Bearer <token>
```

### Chat

**Send Message**
```bash
POST /api/chat/
Headers: Authorization: Bearer <token>
{
  "message": "What is 25 * 4 + sqrt(144)?",
  "thread_id": null  // optional, creates new thread if null
}

Response:
{
  "message": "Let me calculate that for you...",
  "thread_id": 1,
  "sources": null
}
```

**Get All Threads**
```bash
GET /api/chat/threads
Headers: Authorization: Bearer <token>
```

**Get Thread Messages**
```bash
GET /api/chat/threads/{thread_id}/messages
Headers: Authorization: Bearer <token>
```

**Delete Thread**
```bash
DELETE /api/chat/threads/{thread_id}
Headers: Authorization: Bearer <token>
```

### Documents

**Upload PDF**
```bash
POST /api/documents/upload
Headers: Authorization: Bearer <token>
Form Data:
  file: <pdf_file>
```

**List Documents**
```bash
GET /api/documents/
Headers: Authorization: Bearer <token>
```

**Delete Document**
```bash
DELETE /api/documents/{document_id}
Headers: Authorization: Bearer <token>
```

## 💡 Usage Examples

### 1. Calculator Usage
```python
import requests

# Login
response = requests.post(
    "http://localhost:8000/api/auth/login",
    data={"username": "john_doe", "password": "secure_password"}
)
token = response.json()["access_token"]

# Ask math question
response = requests.post(
    "http://localhost:8000/api/chat/",
    headers={"Authorization": f"Bearer {token}"},
    json={"message": "Calculate: (45 + 55) * 3 - sqrt(400)"}
)
print(response.json()["message"])
```

### 2. RAG with PDF
```python
# Upload PDF
with open("document.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": f}
    )

# Query document
response = requests.post(
    "http://localhost:8000/api/chat/",
    headers={"Authorization": f"Bearer {token}"},
    json={"message": "Summarize the key points from my document"}
)
print(response.json()["message"])
print(response.json()["sources"])  # Shows which documents were used
```

### 3. Conversation Continuity
```python
# First message (creates thread)
response1 = requests.post(
    "http://localhost:8000/api/chat/",
    headers={"Authorization": f"Bearer {token}"},
    json={"message": "My name is Alice"}
)
thread_id = response1.json()["thread_id"]

# Follow-up message (continues thread)
response2 = requests.post(
    "http://localhost:8000/api/chat/",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "message": "What's my name?",
        "thread_id": thread_id
    }
)
print(response2.json()["message"])  # Will remember "Alice"
```

## 🏗️ Architecture

```
┌─────────────┐
│   FastAPI   │
│   Server    │
└──────┬──────┘
       │
       ├──────────────┬──────────────┬─────────────┐
       │              │              │             │
   ┌───▼────┐   ┌────▼─────┐   ┌───▼────┐   ┌────▼────┐
   │  Auth  │   │   Chat   │   │  Docs  │   │ Health  │
   │ Router │   │  Router  │   │ Router │   │  Check  │
   └───┬────┘   └────┬─────┘   └───┬────┘   └─────────┘
       │             │              │
       │        ┌────▼─────┐        │
       │        │ LangGraph│        │
       │        │  Agent   │        │
       │        └────┬─────┘        │
       │             │              │
       │      ┌──────┴──────┐       │
       │      │             │       │
       │  ┌───▼────┐   ┌────▼────┐ │
       │  │  Tool  │   │   RAG   │ │
       │  │  Node  │   │ System  │ │
       │  └────────┘   └────┬────┘ │
       │                    │      │
   ┌───▼─────────────┐  ┌───▼──────▼─┐
   │   PostgreSQL    │  │  ChromaDB  │
   │  (Threads &     │  │  (Vector   │
   │   Messages)     │  │   Store)   │
   └─────────────────┘  └────────────┘
```

## 🧪 Testing

```bash
# Test registration
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@test.com","password":"test123"}'

# Test login and get token
TOKEN=$(curl -X POST http://localhost:8000/api/auth/login \
  -F "username=test" \
  -F "password=test123" | jq -r '.access_token')

# Test calculator
curl -X POST http://localhost:8000/api/chat/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Calculate 15 * 8 + sqrt(225)"}'
```

## 🔒 Security Features

- Password hashing with bcrypt
- JWT token-based authentication
- SQL injection protection via SQLAlchemy ORM
- User data isolation
- Secure file upload handling

## 📊 Database Schema

```sql
users
  ├── id (PK)
  ├── username (UNIQUE)
  ├── email (UNIQUE)
  ├── hashed_password
  └── created_at

threads
  ├── id (PK)
  ├── user_id (FK -> users)
  ├── title
  ├── created_at
  └── updated_at

messages
  ├── id (PK)
  ├── thread_id (FK -> threads)
  ├── role (user/assistant)
  ├── content
  ├── metadata (JSON)
  └── created_at

documents
  ├── id (PK)
  ├── user_id (FK -> users)
  ├── filename
  ├── file_path
  ├── file_size
  ├── upload_date
  └── processed (0/1/-1)
```

## 🚀 Deployment

### Using Docker (Coming Soon)
```bash
docker-compose up -d
```

### Manual Deployment
1. Set up PostgreSQL on your server
2. Configure environment variables
3. Run migrations: `python -m app.database`
4. Start with: `gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker`

## 🤝 Contributing

This is a portfolio project showcasing AI Engineering skills including:
- LangGraph agent orchestration
- RAG implementation
- FastAPI backend development
- Database design with SQLAlchemy
- JWT authentication
- Vector database integration

## 📝 License

MIT License - feel free to use this for your own projects!

## 👤 Author

Built as part of AI/ML Engineering learning journey.

## 🔗 Related Technologies

- [LangChain](https://langchain.com/)
- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [ChromaDB](https://www.trychroma.com/)
- [OpenAI](https://openai.com/)