import os
import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
import re
from dotenv import load_dotenv
from datetime import datetime

# Import local modules
import database as db
from models import Video, Message, ChatSession, Bookmark, Note, ExportData
from export_utils import export_to_markdown, export_to_txt, export_to_pdf, get_export_filename

# Load environment variables from .env file
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="YouTube Video Chatbot",
    page_icon="🎥",
    layout="wide"
)

def initialize_session_state():
    """Initialize all session state variables"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "vector_stores" not in st.session_state:
        st.session_state.vector_stores = {}  # Dict of video_id -> vector_store
    if "active_videos" not in st.session_state:
        st.session_state.active_videos = []  # List of active video dicts
    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = None
    if "current_video_id" not in st.session_state:
        st.session_state.current_video_id = None  # Currently selected video for chat
    if "bookmarks" not in st.session_state:
        st.session_state.bookmarks = []
    if "notes" not in st.session_state:
        st.session_state.notes = []
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = "chat"

initialize_session_state()

# Get API key from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
        r'youtube\.com\/v\/([^&\n?#]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

@st.cache_resource
def get_transcript_and_process(video_url):
    """Get transcript and process it into vector store"""
    try:
        video_id = extract_video_id(video_url)
        if not video_id:
            return None, None, "Invalid YouTube URL"
        
        # Get transcript
        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id)
        transcript_text = " ".join([snippet.text for snippet in transcript])
        
        if not transcript_text.strip():
            return None, None, "No transcript available for this video"
        
        # Split transcript into chunks
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, 
            chunk_overlap=200
        )
        chunks = splitter.create_documents([transcript_text])
        
        # Create embeddings and vector store using OpenAI
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=OPENAI_API_KEY)
        vector_store = FAISS.from_documents(chunks, embeddings)
        
        return vector_store, transcript_text, f"Successfully processed {len(chunks)} transcript chunks"
        
    except Exception as e:
        return None, None, f"Error processing video: {str(e)}"

def format_docs(retrieved_docs):
    """Format retrieved documents for the prompt"""
    return "\n\n".join(doc.page_content for doc in retrieved_docs)


def setup_multi_video_rag_chain(vector_stores, active_video_id=None):
    """Setup the RAG chain for question answering with multi-video support"""
    try:
        if not vector_stores:
            return None, "No videos loaded"
        
        # If specific video selected, use only that; otherwise merge all
        if active_video_id and active_video_id in vector_stores:
            combined_retriever = vector_stores[active_video_id].as_retriever(
                search_type="similarity", 
                search_kwargs={"k": 4}
            )
        else:
            # Combine all vector stores
            retrievers = []
            for vid, vs in vector_stores.items():
                retrievers.append(vs.as_retriever(search_type="similarity", search_kwargs={"k": 2}))
            
            # Use first video's retriever as base (simplified approach)
            combined_retriever = list(vector_stores.values())[0].as_retriever(
                search_type="similarity", 
                search_kwargs={"k": 4}
            )
        
        # Setup LLM with OpenAI
        llm = ChatOpenAI(
            model="gpt-4o-mini", 
            temperature=0.2,
            api_key=OPENAI_API_KEY
        )
        
        # Create prompt template
        prompt = PromptTemplate(
            template="""
You are a world-class YouTube content analyst and video comprehension expert with expertise in extracting valuable insights from video transcripts. Your mission is to provide exceptionally helpful, accurate, and engaging responses based strictly on the provided transcript content.

CORE PRINCIPLES:
• SOURCE FIDELITY: Use ONLY information present in the transcript - never add external knowledge
• PRECISION: Quote specific segments and include timestamps when available
• CLARITY: Structure responses with clear headings, bullet points, and logical flow
• CONTEXT AWARENESS: Consider conversation history for personalized responses
• TRANSPARENCY: Explicitly acknowledge when information is insufficient

PREVIOUS CONVERSATION:
{chat_history}

TRANSCRIPT CONTENT:
{context}

CURRENT QUESTION: {question}

RESPONSE FRAMEWORK:
1. DIRECT ANSWER: Lead with a clear, concise answer if the transcript contains the information
2. SUPPORTING EVIDENCE: Include relevant quotes, timestamps, or specific transcript segments
3. COMPREHENSIVE COVERAGE: Address all aspects of the question using available transcript data
4. KNOWLEDGE GAPS: If transcript lacks information, state: "The transcript doesn't provide information about [specific aspect]. Based on what's available, I can tell you..."
5. ACTIONABLE INSIGHTS: When possible, organize information into practical takeaways

FORMATTING GUIDELINES:
• Use headers (##) for main sections
• Use bullet points for lists and key points
• Include quotes in "quotation marks" with context
• Add timestamps [MM:SS] when referencing specific moments
• Bold **key terms** for emphasis (maximum 3 per response)

YOUR EXPERT ANALYSIS:
""",
            input_variables=['context', 'question', 'chat_history']
        )
        
        # Create RAG chain with safe history access
        def get_chat_history():
            if "messages" not in st.session_state or len(st.session_state.messages) <= 2:
                return "No previous conversation."
            
            history = []
            for i in range(max(0, len(st.session_state.messages) - 6), len(st.session_state.messages) - 1):
                msg = st.session_state.messages[i]
                history.append(f"{msg['role'].title()}: {msg['content']}")
            return "\n".join(history)
        
        parallel_chain = RunnableParallel({
            'context': combined_retriever | RunnableLambda(format_docs),
            'question': RunnablePassthrough(),
            'chat_history': RunnableLambda(lambda x: get_chat_history())
        })
        
        parser = StrOutputParser()
        main_chain = parallel_chain | prompt | llm | parser
        
        return main_chain, None
        
    except Exception as e:
        return None, f"Error setting up RAG chain: {str(e)}"


def load_session(session_id):
    """Load a chat session from database"""
    session = db.get_session(session_id)
    if session:
        st.session_state.current_session_id = session_id
        st.session_state.messages = []
        
        # Load messages
        messages = db.get_session_messages(session_id)
        for msg in messages:
            st.session_state.messages.append({
                "role": msg['role'],
                "content": msg['content'],
                "id": msg['id']
            })
        
        # Load videos
        videos = db.get_session_videos(session_id)
        st.session_state.active_videos = videos
        
        # Reload vector stores for session videos
        for video in videos:
            if video['video_id'] not in st.session_state.vector_stores:
                vs, _, _ = get_transcript_and_process(video['url'])
                if vs:
                    st.session_state.vector_stores[video['video_id']] = vs
        
        # Load bookmarks and notes
        st.session_state.bookmarks = db.get_session_bookmarks(session_id)
        st.session_state.notes = db.get_session_notes(session_id)
        
        return True
    return False


def save_current_session():
    """Save current session state to database"""
    if st.session_state.current_session_id:
        # Messages are saved as they're created
        return st.session_state.current_session_id
    return None


def create_new_session(name=None):
    """Create a new session and set it as current"""
    session_id = db.create_session(name)
    st.session_state.current_session_id = session_id
    st.session_state.messages = []
    st.session_state.active_videos = []
    st.session_state.bookmarks = []
    st.session_state.notes = []
    return session_id


def get_export_data():
    """Prepare data for export"""
    if not st.session_state.current_session_id:
        return None
    
    session = db.get_session(st.session_state.current_session_id)
    messages = db.get_session_messages(st.session_state.current_session_id)
    videos = db.get_session_videos(st.session_state.current_session_id)
    bookmarks = db.get_session_bookmarks(st.session_state.current_session_id)
    notes = db.get_session_notes(st.session_state.current_session_id)
    
    return ExportData(
        session=ChatSession.from_dict(session),
        messages=[Message.from_dict(m) for m in messages],
        videos=[Video.from_dict(v) for v in videos],
        bookmarks=[Bookmark.from_dict(b) for b in bookmarks],
        notes=[Note.from_dict(n) for n in notes]
    )


# ============ MAIN UI ============

st.title("🎥 YouTube Video Chatbot")
st.markdown("Chat with multiple YouTube videos using AI! Manage sessions, save conversations, and export your insights.")

# Create tabs for different features
tab_chat, tab_bookmarks, tab_notes, tab_history = st.tabs(["💬 Chat", "🔖 Bookmarks", "📝 Notes", "📚 History"])

# ============ SIDEBAR ============
with st.sidebar:
    st.header("📹 Video Management")
    
    # Session Management
    st.subheader("📁 Sessions")
    
    sessions = db.get_all_sessions()
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ New Session", use_container_width=True):
            create_new_session()
            st.rerun()
    
    with col2:
        if st.session_state.current_session_id:
            if st.button("💾 Save", use_container_width=True):
                st.success("Session saved!")
    
    # Session selector
    if sessions:
        session_options = {f"{s['name']} ({s['message_count']} msgs)": s['id'] for s in sessions}
        current_name = None
        if st.session_state.current_session_id:
            for s in sessions:
                if s['id'] == st.session_state.current_session_id:
                    current_name = f"{s['name']} ({s['message_count']} msgs)"
                    break
        
        selected_session = st.selectbox(
            "Load Session:",
            options=[""] + list(session_options.keys()),
            index=0 if not current_name else (list(session_options.keys()).index(current_name) + 1 if current_name in session_options else 0)
        )
        
        if selected_session and selected_session in session_options:
            session_id = session_options[selected_session]
            if session_id != st.session_state.current_session_id:
                if st.button("📂 Load Selected Session"):
                    load_session(session_id)
                    st.rerun()
    
    st.divider()
    
    # Video Input
    st.subheader("🎬 Add Video")
    video_url = st.text_input(
        "YouTube URL:",
        placeholder="https://www.youtube.com/watch?v=...",
        key="video_url_input"
    )
    
    if st.button("➕ Add Video", type="primary", use_container_width=True):
        if video_url:
            video_id = extract_video_id(video_url)
            if video_id:
                # Check if already added
                if video_id in st.session_state.vector_stores:
                    st.warning("Video already added!")
                else:
                    with st.spinner("Processing video transcript..."):
                        vector_store, transcript, message = get_transcript_and_process(video_url)
                        
                        if vector_store:
                            # Create session if not exists
                            if not st.session_state.current_session_id:
                                create_new_session(f"Session - {video_id[:8]}")
                            
                            # Save video to database
                            video_db_id = db.save_video(
                                video_id=video_id,
                                url=video_url,
                                title=f"Video {video_id[:8]}",
                                transcript=transcript
                            )
                            
                            # Add to session
                            db.add_video_to_session(st.session_state.current_session_id, video_db_id)
                            
                            # Update state
                            st.session_state.vector_stores[video_id] = vector_store
                            video_data = db.get_video(video_id)
                            st.session_state.active_videos.append(video_data)
                            
                            if not st.session_state.current_video_id:
                                st.session_state.current_video_id = video_id
                            
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
            else:
                st.error("Invalid YouTube URL")
        else:
            st.warning("Please enter a YouTube URL")
    
    # Active Videos List
    if st.session_state.active_videos:
        st.divider()
        st.subheader(f"📺 Active Videos ({len(st.session_state.active_videos)})")
        
        for video in st.session_state.active_videos:
            vid = video['video_id']
            is_selected = st.session_state.current_video_id == vid
            
            col1, col2 = st.columns([3, 1])
            with col1:
                btn_label = f"{'✅ ' if is_selected else ''}{video.get('title', vid[:12])}"
                if st.button(btn_label, key=f"select_{vid}", use_container_width=True):
                    st.session_state.current_video_id = vid
                    st.rerun()
            with col2:
                if st.button("❌", key=f"remove_{vid}"):
                    # Remove video
                    if vid in st.session_state.vector_stores:
                        del st.session_state.vector_stores[vid]
                    st.session_state.active_videos = [v for v in st.session_state.active_videos if v['video_id'] != vid]
                    if st.session_state.current_video_id == vid:
                        st.session_state.current_video_id = st.session_state.active_videos[0]['video_id'] if st.session_state.active_videos else None
                    st.rerun()
        
        # Option to chat with all videos
        if len(st.session_state.active_videos) > 1:
            if st.button("🔀 Chat with ALL Videos", use_container_width=True):
                st.session_state.current_video_id = None
                st.rerun()
    
    # Export Section
    if st.session_state.current_session_id and st.session_state.messages:
        st.divider()
        st.subheader("📤 Export")
        
        export_format = st.selectbox("Format:", ["Markdown (.md)", "Text (.txt)", "PDF (.pdf)"])
        
        if st.button("📥 Export Chat", use_container_width=True):
            export_data = get_export_data()
            if export_data:
                try:
                    if "Markdown" in export_format:
                        content = export_to_markdown(export_data)
                        filename = get_export_filename(export_data.session.name, "md")
                        st.download_button(
                            "⬇️ Download Markdown",
                            content,
                            filename,
                            "text/markdown",
                            use_container_width=True
                        )
                    elif "Text" in export_format:
                        content = export_to_txt(export_data)
                        filename = get_export_filename(export_data.session.name, "txt")
                        st.download_button(
                            "⬇️ Download Text",
                            content,
                            filename,
                            "text/plain",
                            use_container_width=True
                        )
                    else:
                        content = export_to_pdf(export_data)
                        filename = get_export_filename(export_data.session.name, "pdf")
                        st.download_button(
                            "⬇️ Download PDF",
                            content,
                            filename,
                            "application/pdf",
                            use_container_width=True
                        )
                except Exception as e:
                    st.error(f"Export error: {str(e)}")


# ============ CHAT TAB ============
with tab_chat:
    if not st.session_state.active_videos:
        st.info("👈 Add a YouTube video using the sidebar to start chatting!")
    else:
        # Show current video info
        if st.session_state.current_video_id:
            current_video = next((v for v in st.session_state.active_videos if v['video_id'] == st.session_state.current_video_id), None)
            if current_video:
                st.caption(f"💬 Chatting with: **{current_video.get('title', current_video['video_id'])}**")
        else:
            st.caption(f"💬 Chatting with: **All {len(st.session_state.active_videos)} videos**")
        
        # Display chat messages
        for i, message in enumerate(st.session_state.messages):
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
                # Bookmark button for assistant messages
                if message["role"] == "assistant":
                    if st.button("🔖 Bookmark", key=f"bookmark_msg_{i}"):
                        if st.session_state.current_session_id:
                            msg_id = message.get('id')
                            bookmark_id = db.create_bookmark(
                                session_id=st.session_state.current_session_id,
                                title=f"Response {i+1}",
                                message_id=msg_id
                            )
                            st.session_state.bookmarks = db.get_session_bookmarks(st.session_state.current_session_id)
                            st.success("Bookmarked!")
        
        # Chat input
        if prompt := st.chat_input("Ask a question about the video(s)..."):
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Save to database
            if st.session_state.current_session_id:
                msg_id = db.save_message(
                    st.session_state.current_session_id,
                    "user",
                    prompt
                )
                st.session_state.messages[-1]['id'] = msg_id
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Generate and display assistant response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        # Setup RAG chain
                        rag_chain, error = setup_multi_video_rag_chain(
                            st.session_state.vector_stores,
                            st.session_state.current_video_id
                        )
                        
                        if error:
                            response = f"Error: {error}"
                        else:
                            response = rag_chain.invoke(prompt)
                        
                        st.markdown(response)
                        
                        # Add assistant response to chat history
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": response
                        })
                        
                        # Save to database
                        if st.session_state.current_session_id:
                            msg_id = db.save_message(
                                st.session_state.current_session_id,
                                "assistant",
                                response
                            )
                            st.session_state.messages[-1]['id'] = msg_id
                        
                    except Exception as e:
                        error_response = f"Sorry, I encountered an error: {str(e)}"
                        st.markdown(error_response)
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": error_response
                        })


# ============ BOOKMARKS TAB ============
with tab_bookmarks:
    st.subheader("🔖 Your Bookmarks")
    
    if not st.session_state.current_session_id:
        st.info("Start a session and add bookmarks to see them here!")
    else:
        # Add new bookmark
        with st.expander("➕ Add New Bookmark"):
            bookmark_title = st.text_input("Bookmark Title:", key="new_bookmark_title")
            bookmark_note = st.text_area("Notes (optional):", key="new_bookmark_note")
            
            if st.button("💾 Save Bookmark"):
                if bookmark_title:
                    bookmark_id = db.create_bookmark(
                        session_id=st.session_state.current_session_id,
                        title=bookmark_title
                    )
                    if bookmark_note:
                        db.create_note(
                            session_id=st.session_state.current_session_id,
                            content=bookmark_note,
                            bookmark_id=bookmark_id
                        )
                    st.session_state.bookmarks = db.get_session_bookmarks(st.session_state.current_session_id)
                    st.success("Bookmark saved!")
                    st.rerun()
                else:
                    st.warning("Please enter a title")
        
        # Display bookmarks
        bookmarks = st.session_state.bookmarks
        if bookmarks:
            for bookmark in bookmarks:
                with st.container():
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**{bookmark['title']}**")
                        if bookmark.get('video_title'):
                            st.caption(f"📹 {bookmark['video_title']}")
                        if bookmark.get('message_content'):
                            st.caption(f"💬 {bookmark['message_content'][:100]}...")
                    with col2:
                        if st.button("🗑️", key=f"del_bookmark_{bookmark['id']}"):
                            db.delete_bookmark(bookmark['id'])
                            st.session_state.bookmarks = db.get_session_bookmarks(st.session_state.current_session_id)
                            st.rerun()
                    st.divider()
        else:
            st.info("No bookmarks yet. Bookmark messages from the chat or add custom bookmarks above!")


# ============ NOTES TAB ============
with tab_notes:
    st.subheader("📝 Your Notes")
    
    if not st.session_state.current_session_id:
        st.info("Start a session to add notes!")
    else:
        # Add new note
        with st.expander("➕ Add New Note"):
            note_content = st.text_area("Note content:", key="new_note_content", height=150)
            
            # Optional: link to video
            video_options = {"None": None}
            for v in st.session_state.active_videos:
                video_options[v.get('title', v['video_id'])] = v['id']
            
            selected_video = st.selectbox("Link to video (optional):", options=list(video_options.keys()))
            
            if st.button("💾 Save Note"):
                if note_content:
                    db.create_note(
                        session_id=st.session_state.current_session_id,
                        content=note_content,
                        video_id=video_options[selected_video]
                    )
                    st.session_state.notes = db.get_session_notes(st.session_state.current_session_id)
                    st.success("Note saved!")
                    st.rerun()
                else:
                    st.warning("Please enter note content")
        
        # Display notes
        notes = st.session_state.notes
        if notes:
            for note in notes:
                with st.container():
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(note['content'])
                        meta = []
                        if note.get('video_title'):
                            meta.append(f"📹 {note['video_title']}")
                        if note.get('bookmark_title'):
                            meta.append(f"🔖 {note['bookmark_title']}")
                        if note.get('created_at'):
                            meta.append(f"📅 {note['created_at']}")
                        if meta:
                            st.caption(" | ".join(meta))
                    with col2:
                        if st.button("🗑️", key=f"del_note_{note['id']}"):
                            db.delete_note(note['id'])
                            st.session_state.notes = db.get_session_notes(st.session_state.current_session_id)
                            st.rerun()
                    st.divider()
        else:
            st.info("No notes yet. Add your first note above!")


# ============ HISTORY TAB ============
with tab_history:
    st.subheader("📚 Chat History")
    
    # Search
    search_query = st.text_input("🔍 Search messages:", key="search_messages")
    
    if search_query:
        results = db.search_messages(search_query)
        if results:
            st.success(f"Found {len(results)} results")
            for result in results[:20]:  # Limit to 20 results
                with st.container():
                    role_emoji = "👤" if result['role'] == "user" else "🤖"
                    st.markdown(f"{role_emoji} **{result['role'].title()}** - *{result.get('session_name', 'Unknown session')}*")
                    st.markdown(result['content'][:300] + "..." if len(result['content']) > 300 else result['content'])
                    st.divider()
        else:
            st.info("No results found")
    
    # All sessions
    st.divider()
    st.subheader("📁 All Sessions")
    
    all_sessions = db.get_all_sessions()
    if all_sessions:
        for session in all_sessions:
            with st.container():
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.markdown(f"**{session['name']}**")
                    st.caption(f"💬 {session['message_count']} messages | 📹 {session['video_count']} videos | 📅 {session.get('updated_at', '')}")
                with col2:
                    if st.button("📂 Load", key=f"load_session_{session['id']}"):
                        load_session(session['id'])
                        st.rerun()
                with col3:
                    if st.button("🗑️", key=f"del_session_{session['id']}"):
                        db.delete_session(session['id'])
                        if st.session_state.current_session_id == session['id']:
                            st.session_state.current_session_id = None
                            st.session_state.messages = []
                            st.session_state.active_videos = []
                        st.rerun()
                st.divider()
    else:
        st.info("No previous sessions. Start chatting to create your first session!")


# Footer
st.markdown("---")
st.markdown(
    "💡 **Tips:** Add multiple videos to compare content, use bookmarks to save important insights, "
    "and export your conversations for later reference!"
)