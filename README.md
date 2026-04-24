# 🎥 YouTube Video Chatbot

An AI-powered chatbot that lets you chat with YouTube videos! Ask questions, get summaries, and extract insights from any YouTube video using RAG (Retrieval-Augmented Generation) technology.

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)

## ✨ Features

### 💬 Core Chat Features
- **Chat with YouTube Videos** - Ask questions about any video with transcripts
- **Multi-Video Support** - Load multiple videos and chat across all of them
- **Intelligent Responses** - Powered by GPT-4o-mini with RAG architecture

### 📁 Data Management
- **Session Management** - Create, save, and load chat sessions
- **Chat History Database** - All conversations stored in SQLite
- **Bookmarks** - Save important AI responses or create custom bookmarks
- **Notes** - Add personal notes linked to videos or bookmarks

### 📤 Export Options
- **Markdown (.md)** - Perfect for documentation
- **Plain Text (.txt)** - Simple and universal
- **PDF (.pdf)** - Professional formatted export

### 🔍 Search & History
- **Search Messages** - Find past conversations across all sessions
- **Session History** - Browse and manage all previous sessions

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- OpenAI API Key

### Installation

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
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

4. **Run the app**
   ```bash
   streamlit run app.py
   ```

5. **Open in browser**
   
   Navigate to `http://localhost:8501`

## 📖 How to Use

1. **Add a Video** - Paste a YouTube URL in the sidebar and click "Add Video"
2. **Start Chatting** - Ask questions about the video content
3. **Add More Videos** - Load multiple videos to compare or analyze together
4. **Save Your Work** - Sessions auto-save, or export to MD/TXT/PDF
5. **Bookmark Insights** - Save important responses for later
6. **Take Notes** - Add your own notes to sessions

## 🗂️ Project Structure

```
youtube_chatbot/
├── app.py              # Main Streamlit application
├── database.py         # SQLite database operations
├── models.py           # Data models/schemas
├── export_utils.py     # Export functionality (MD, TXT, PDF)
├── Requirements.txt    # Python dependencies
├── .env               # API keys (not in repo)
├── .gitignore         # Git ignore rules
└── data/              # SQLite database (auto-created)
```

## 🛠️ Tech Stack

| Technology | Purpose |
|------------|---------|
| **Streamlit** | Web UI framework |
| **LangChain** | RAG orchestration |
| **OpenAI GPT-4o-mini** | Language model |
| **OpenAI Embeddings** | Text embeddings |
| **FAISS** | Vector similarity search |
| **SQLite** | Local database |
| **youtube-transcript-api** | Fetch video transcripts |

## 📝 Requirements

```
streamlit
langchain
langchain-openai
langchain-community
langchain-text-splitters
youtube-transcript-api
faiss-cpu
python-dotenv
fpdf2
```

## ⚠️ Limitations

- Only works with videos that have transcripts/captions
- Requires OpenAI API key (paid)
- Video title detection is basic (shows video ID)

## 🔮 Future Improvements

- [ ] Auto-detect video titles from YouTube API
- [ ] Timestamp navigation with clickable links
- [ ] Embedded video player
- [ ] Multiple AI model support
- [ ] Voice input/output
- [ ] Auto-generated summaries

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Open issues for bugs or feature requests
- Submit pull requests
- Suggest improvements

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

## 👨‍💻 Author

**Vishal**
- GitHub: [@vis-hal-git](https://github.com/vis-hal-git)

---

⭐ **Star this repo if you find it useful!**
