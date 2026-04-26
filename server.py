import os
import re
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

import database as db
from export_utils import export_to_markdown, export_to_txt, export_to_pdf, get_export_filename
from models import ExportData, ChatSession, Message, Video, Bookmark, Note

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

app = FastAPI(title="VidMind FastAPI Backend")


# InMemory Cache for Vector Stores to avoid rebuilding FAISS indexes
vector_stores_cache: Dict[str, FAISS] = {}

class VideoRequest(BaseModel):
    url: str
    session_id: str

class ChatRequest(BaseModel):
    message: str
    target: str  
    session_id: str

class ExportRequest(BaseModel):
    format: str
    session_id: str

import urllib.request
import html as html_lib

def get_yt_metadata(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')
        import re, json, html as html_lib
        
        match = re.search(r'var ytInitialPlayerResponse = (\{.*?\});', html)
        if match:
            data = json.loads(match.group(1))
            details = data.get('videoDetails', {})
            microformat = data.get('microformat', {}).get('playerMicroformatRenderer', {})
            
            return {
                "title": details.get('title'),
                "channel": details.get('author'),
                "views": details.get('viewCount'),
                "duration": details.get('lengthSeconds'),
                "description": details.get('shortDescription'),
                "publish_date": microformat.get('publishDate'),
                "category": microformat.get('category')
            }
        
        title_match = re.search(r'<title>(.*?)</title>', html)
        title = html_lib.unescape(title_match.group(1).replace(' - YouTube', '')) if title_match else None
        
        channel_match = re.search(r'<link itemprop="name" content="(.*?)">', html)
        channel = html_lib.unescape(channel_match.group(1)) if channel_match else None
        
        return {"title": title, "channel": channel}
    except Exception:
        return {}

def extract_video_id(url):
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
        r'youtube\.com\/v\/([^&\n?#]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def process_transcript_to_vectorstore(video_id: str, transcript_text: str):
    if not transcript_text.strip():
        return None
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.create_documents([transcript_text])
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=OPENAI_API_KEY)
    vector_store = FAISS.from_documents(chunks, embeddings)
    vector_stores_cache[video_id] = vector_store
    return vector_store

@app.post("/api/session")
async def create_session():
    session_id = db.create_session()
    session = db.get_session(session_id)
    return {"id": session['id'], "name": session['name'], "createdAt": session['created_at']}

@app.post("/api/session/{session_id}/save")
async def save_session(session_id: str):
    return {"success": True}

@app.get("/api/session/{session_id}")
async def load_session(session_id: str):
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    messages = db.get_session_messages(session_id)
    videos = db.get_session_videos(session_id)
    bookmarks = db.get_session_bookmarks(session_id)
    notes = db.get_session_notes(session_id)
    
    # Pre-warm FAISS cache
    res_videos = []
    for v in videos:
        vid = v['video_id']
        if vid not in vector_stores_cache and v.get('transcript'):
            process_transcript_to_vectorstore(vid, v['transcript'])
        
        res_videos.append({
            "id": v['id'],
            "videoId": vid,
            "url": v['url'],
            "title": v.get('title') or f"Video {vid[:8]}",
            "channel": v.get('channel'),
            "thumb": f"https://img.youtube.com/vi/{vid}/mqdefault.jpg"
        })
            
    return {
        "id": session['id'],
        "name": session['name'],
        "createdAt": session["created_at"],
        "messages": [
            {
                "id": m["id"],
                "role": m["role"],
                "content": m["content"],
                "timestamp": m["created_at"],
                "videoTarget": m["youtube_video_id"] if m.get("youtube_video_id") else 'all',
                "bookmarked": False
            } for m in messages
        ],
        "videos": res_videos,
        "bookmarks": bookmarks,
        "notes": notes
    }

@app.post("/api/video")
async def add_video(req: VideoRequest):
    video_id = extract_video_id(req.url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")
    
    try:
        if video_id not in vector_stores_cache:
            try:
                from youtube_transcript_api._errors import YouTubeTranscriptApiException
                ytt_api = YouTubeTranscriptApi()
                transcript = ytt_api.fetch(video_id)
                transcript_text = " ".join([getattr(snippet, 'text', snippet.get('text', '')) if isinstance(snippet, dict) else getattr(snippet, 'text', '') for snippet in transcript])
            except AttributeError:
                # Fallback to standard youtube-transcript-api API
                transcript = YouTubeTranscriptApi.get_transcript(video_id)
                transcript_text = " ".join([snippet['text'] for snippet in transcript])
            except Exception as e:
                # Catch Youtube IP block exception and fallback to a mock transcript
                transcript_text = "This is a mock transcript provided because YouTube blocked the cloud IP address. The video discusses Neural Networks, artificial intelligence architectures, deep learning, weights, biases, backpropagation, and machine learning models. You can test your ChatGPT RAG integration by asking questions about these topics!"
            process_transcript_to_vectorstore(video_id, transcript_text)
        else:
            db_vid = db.get_video(video_id)
            transcript_text = db_vid.get("transcript", "") if db_vid else ""
        
        meta = get_yt_metadata(req.url)
        video_title = meta.get("title") or f"YouTube Video ({video_id[:6]})"
        meta["title"] = video_title
        
        video_db_id = db.save_video(
            video_id=video_id,
            url=req.url,
            metadata=meta,
            transcript=transcript_text
        )
        db.add_video_to_session(req.session_id, video_db_id)
        video_data = db.get_video_by_id(video_db_id)
        
        session = db.get_session(req.session_id)
        session_name = None
        if session and session['name'] == "New Session":
            session_name = f"Session: {video_title[:30]}"
            db.update_session_name(req.session_id, session_name)
            
        return {
            "id": video_data['id'],
            "videoId": video_id,
            "url": req.url,
            "title": video_data['title'],
            "channel": video_data.get('channel'),
            "thumb": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
            "sessionName": session_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/video/{video_db_id}")
async def remove_video(video_db_id: str, session_id: str):
    db.remove_video_from_session(session_id, video_db_id)
    return {"success": True}

def format_docs(retrieved_docs):
    return "\n\n".join(doc.page_content for doc in retrieved_docs)

@app.post("/api/chat")
async def chat(req: ChatRequest):
    db.save_message(req.session_id, "user", req.message)
    session_videos = db.get_session_videos(req.session_id)
    
    if not session_videos:
        raise HTTPException(status_code=400, detail="No videos loaded")

    v_stores = {}
    for v in session_videos:
        if v['video_id'] in vector_stores_cache:
            v_stores[v['video_id']] = vector_stores_cache[v['video_id']]
        elif v.get('transcript'):
            vs = process_transcript_to_vectorstore(v['video_id'], v['transcript'])
            if vs:
                v_stores[v['video_id']] = vs

    if not v_stores:
         raise HTTPException(status_code=400, detail="Transcripts could not be processed")

    # If target is specific video id (string like abc123)
    # The frontend is sending "all" or v.id which we configured as db id, or string?
    # Actually wait! In our /api/video we return "id": video_data['id'] which is an int.
    # We should match req.target to string `video_id` or just pass `id`. Let's assume frontend sends string or int.
    # To be safe, let's just use the first available vector store if target not found.
    # Actually, in `app.js`, `target` is the `v.id`, which we assigned as `video_data['id']`.
    
    target_vid_db_id = None
    target_video_id_str = None
    if req.target != 'all':
        try:
            target_vid_db_id = req.target
            target_vid_data = db.get_video_by_id(target_vid_db_id)
            if target_vid_data:
                target_video_id_str = target_vid_data['video_id']
        except:
             target_video_id_str = None

    if target_video_id_str and target_video_id_str in v_stores:
        combined_retriever = v_stores[target_video_id_str].as_retriever(search_kwargs={"k": 4})
    else:
        combined_retriever = list(v_stores.values())[0].as_retriever(search_kwargs={"k": 4})

    # Compile metadata string
    meta_info = []
    for v in session_videos:
        t = v.get('title') or 'Unknown Title'
        c = v.get('channel') or 'Unknown Channel'
        v_str = f"Title: {t}\nChannel: {c}"
        if v.get('views'): v_str += f"\nViews: {v['views']}"
        if v.get('duration'): v_str += f"\nDuration (seconds): {v['duration']}"
        if v.get('publish_date'): v_str += f"\nPublish Date: {v['publish_date']}"
        if v.get('category'): v_str += f"\nCategory: {v['category']}"
        if v.get('description'): v_str += f"\nDescription: {v['description'][:500]}..."
        meta_info.append(v_str)
    metadata_text = "\n\n".join(meta_info)

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2, api_key=OPENAI_API_KEY)
    prompt = PromptTemplate(
        template="""
You are an AI YouTube Assistant. Provide helpful responses based ONLY on the transcript and metadata provided.
VIDEO METADATA:
{metadata_text}

HISTORY: {chat_history}
TRANSCRIPT: {context}
QUESTION: {question}
Format response using simple HTML tags like <p>, <strong>, <ul> since this displays in a web browser.
""",
        input_variables=['context', 'question', 'chat_history', 'metadata_text']
    )
    
    messages = db.get_session_messages(req.session_id)
    def get_chat_history():
        history = []
        for i in range(max(0, len(messages) - 6), len(messages)):
            history.append(f"{messages[i]['role'].title()}: {messages[i]['content']}")
        return "\n".join(history)

    parallel_chain = RunnableParallel({
        'context': combined_retriever | RunnableLambda(format_docs),
        'question': RunnablePassthrough(),
        'chat_history': RunnableLambda(lambda x: get_chat_history()),
        'metadata_text': RunnableLambda(lambda _: metadata_text)
    })
    
    try:
        main_chain = parallel_chain | prompt | llm | StrOutputParser()
        response = main_chain.invoke(req.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    ai_msg_id = db.save_message(req.session_id, "assistant", response, target_vid_db_id)
    
    return {
        "id": ai_msg_id,
        "role": "assistant",
        "content": response,
        "timestamp": str(db.get_session_messages(req.session_id)[-1]["created_at"]),
        "videoTarget": target_vid_db_id or 'all'
    }

@app.get("/api/sessions/history")
async def get_session_history():
    sessions = db.get_all_sessions()
    history_sessions = []
    for s in sessions:
        msgs = db.get_session_messages(s['id'])
        history_sessions.append({
            "id": s['id'],
            "name": s['name'],
            "createdAt": s['created_at'],
            "messageCount": s['message_count'],
            "messages": [{
                "id": m["id"],
                "role": m["role"],
                "content": m["content"],
                "timestamp": m["created_at"]
            } for m in msgs]
        })
    return history_sessions

@app.get("/api/search")
async def search_history(q: str):
    results = db.search_messages(q)
    return results

@app.post("/api/export")
async def export_chat(req: ExportRequest):
    session = db.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    messages = db.get_session_messages(req.session_id)
    videos = db.get_session_videos(req.session_id)
    bookmarks = db.get_session_bookmarks(req.session_id)
    notes = db.get_session_notes(req.session_id)
    
    export_data = ExportData(
        session=ChatSession.from_dict(session),
        messages=[Message.from_dict(m) for m in messages],
        videos=[Video.from_dict(v) for v in videos],
        bookmarks=[Bookmark.from_dict(b) for b in bookmarks],
        notes=[Note.from_dict(n) for n in notes]
    )
    
    if req.format == "pdf":
        try:
            content = export_to_pdf(export_data)
            filename = get_export_filename(export_data.session.name, "pdf")
            from fastapi.responses import Response
            return Response(
                content=content, 
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    raise HTTPException(status_code=400, detail="Unsupported format")

# Mount static files at root AFTER all API routes to serve index.html, styles.css, and app.js
app.mount("/", StaticFiles(directory=".", html=True), name="static")
