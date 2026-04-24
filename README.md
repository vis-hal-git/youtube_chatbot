# 🎥 VidMind: AI YouTube Video Chatbot

An advanced, AI-powered chatbot that lets you chat with YouTube videos! Extract insights, get summaries, and ask complex questions across multiple YouTube videos simultaneously using Retrieval-Augmented Generation (RAG).

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-4EA94B?style=for-the-badge&logo=mongodb&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

## ✨ Features

### 💬 Core Chat Features
- **Chat with YouTube Videos** - Ask questions about any video with closed captions/transcripts.
- **Multi-Video Context** - Load multiple videos into a single session and chat across all of them at once.
- **Intelligent Responses** - Powered by LangChain, OpenAI embeddings, and GPT-4o-mini.

### 📁 Data & Session Management
- **MongoDB Database** - Persistent, scalable storage for all user data.
- **Session Management** - Create, auto-save, and seamlessly resume previous chat sessions.
- **Bookmarks & Notes** - Save important AI responses to your Bookmarks and add custom notes to track your research.

### 🔍 Search & History
- **Search History** - Instantly search through past conversations and notes across all your sessions.
- **Thread Tracking** - Browse and manage all previous AI sessions in the dedicated History tab.

### 📤 Export Options
- Export your research and chats to **Markdown (.md)**, **Plain Text (.txt)**, or **PDF (.pdf)**.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- MongoDB instance (local or MongoDB Atlas)
- OpenAI API Key

### Standard Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/vis-hal-git/youtube_chatbot.git
   cd youtube_chatbot
   ```

2. **Install dependencies**
   ```bash
   pip install -r Requirements.txt
   ```

3. **Set up environment variables**
   Create a `.env` file in the project root:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   MONGO_URI=mongodb+srv://<username>:<password>@cluster.mongodb.net/
   ```

4. **Run the FastAPI Server**
   ```bash
   uvicorn server:app --reload
   ```

5. **Open in browser**
   Navigate to `http://localhost:8000`

### 🐳 Docker Installation

To run the application using Docker:

1. Ensure your `.env` file is fully configured.
2. Build and start the container:
   ```bash
   docker-compose up --build
   ```
3. The app will be available at `http://localhost:8000`.

---

## 🗂️ Project Structure

```
youtube_chatbot/
├── server.py           # FastAPI Backend Application
├── app.js              # Vanilla JS Frontend Logic
├── index.html          # Custom UI Layout
├── styles.css          # Frontend Styling
├── database.py         # MongoDB Operations
├── models.py           # Data Models
├── export_utils.py     # PDF/MD/TXT Exporter
├── Requirements.txt    # Python Dependencies
└── Dockerfile          # Container Config
```

---

## 🛠️ Tech Stack

| Technology | Purpose |
|------------|---------|
| **FastAPI** | High-performance backend framework |
| **HTML/CSS/JS** | Custom, dynamic frontend UI |
| **MongoDB** | Cloud database for sessions, messages, and notes |
| **LangChain** | RAG orchestration and splitting |
| **OpenAI** | Embeddings and GPT-4o-mini LLM |
| **FAISS** | In-memory vector similarity search |
| **youtube-transcript-api** | Fetching video transcripts |
| **Docker** | Containerization and deployment |

---

## ⚠️ Limitations
- Only works with YouTube videos that have transcripts/captions available.
- Requires a valid OpenAI API key to process embeddings and generate responses.

---

## 👨‍💻 Author

**Vishal**
- GitHub: [@vis-hal-git](https://github.com/vis-hal-git)

---
⭐ **Star this repo if you find it useful!**
