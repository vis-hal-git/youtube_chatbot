"""
Database module for YouTube Chatbot
Handles all SQLite database operations for persistent storage
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

# Database path
DB_DIR = os.path.join(os.path.dirname(__file__), 'data')
DB_PATH = os.path.join(DB_DIR, 'chatbot.db')


def ensure_db_directory():
    """Ensure the data directory exists"""
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)


@contextmanager
def get_connection():
    """Context manager for database connections"""
    ensure_db_directory()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_database():
    """Initialize database with all required tables"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Videos table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT UNIQUE NOT NULL,
                url TEXT NOT NULL,
                title TEXT,
                channel TEXT,
                duration TEXT,
                transcript TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Chat sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Session-Video relationship (many-to-many for multi-video support)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS session_videos (
                session_id INTEGER NOT NULL,
                video_id INTEGER NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (session_id, video_id),
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
            )
        ''')
        
        # Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                video_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE SET NULL
            )
        ''')
        
        # Bookmarks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                message_id INTEGER,
                video_id INTEGER,
                title TEXT NOT NULL,
                timestamp_seconds INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE SET NULL,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE SET NULL
            )
        ''')
        
        # Notes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                video_id INTEGER,
                bookmark_id INTEGER,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE SET NULL,
                FOREIGN KEY (bookmark_id) REFERENCES bookmarks(id) ON DELETE SET NULL
            )
        ''')


# ============ VIDEO OPERATIONS ============

def save_video(video_id: str, url: str, title: str = None, 
               channel: str = None, duration: str = None, 
               transcript: str = None) -> int:
    """Save or update a video record"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO videos (video_id, url, title, channel, duration, transcript)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                title = COALESCE(excluded.title, title),
                channel = COALESCE(excluded.channel, channel),
                duration = COALESCE(excluded.duration, duration),
                transcript = COALESCE(excluded.transcript, transcript)
        ''', (video_id, url, title, channel, duration, transcript))
        
        cursor.execute('SELECT id FROM videos WHERE video_id = ?', (video_id,))
        return cursor.fetchone()[0]


def get_video(video_id: str) -> Optional[Dict]:
    """Get video by YouTube video ID"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM videos WHERE video_id = ?', (video_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_video_by_id(db_id: int) -> Optional[Dict]:
    """Get video by database ID"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM videos WHERE id = ?', (db_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_videos() -> List[Dict]:
    """Get all videos"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM videos ORDER BY created_at DESC')
        return [dict(row) for row in cursor.fetchall()]


# ============ SESSION OPERATIONS ============

def create_session(name: str = None) -> int:
    """Create a new chat session"""
    if not name:
        name = f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO chat_sessions (name) VALUES (?)',
            (name,)
        )
        return cursor.lastrowid


def get_session(session_id: int) -> Optional[Dict]:
    """Get session by ID"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM chat_sessions WHERE id = ?', (session_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_sessions() -> List[Dict]:
    """Get all chat sessions"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT cs.*, COUNT(DISTINCT m.id) as message_count,
                   COUNT(DISTINCT sv.video_id) as video_count
            FROM chat_sessions cs
            LEFT JOIN messages m ON cs.id = m.session_id
            LEFT JOIN session_videos sv ON cs.id = sv.session_id
            GROUP BY cs.id
            ORDER BY cs.updated_at DESC
        ''')
        return [dict(row) for row in cursor.fetchall()]


def update_session_name(session_id: int, name: str):
    """Update session name"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE chat_sessions SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (name, session_id)
        )


def delete_session(session_id: int):
    """Delete a session and all related data"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM chat_sessions WHERE id = ?', (session_id,))


def add_video_to_session(session_id: int, video_db_id: int):
    """Add a video to a session"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO session_videos (session_id, video_id)
            VALUES (?, ?)
        ''', (session_id, video_db_id))
        cursor.execute(
            'UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (session_id,)
        )


def get_session_videos(session_id: int) -> List[Dict]:
    """Get all videos in a session"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT v.* FROM videos v
            JOIN session_videos sv ON v.id = sv.video_id
            WHERE sv.session_id = ?
            ORDER BY sv.added_at
        ''', (session_id,))
        return [dict(row) for row in cursor.fetchall()]


def remove_video_from_session(session_id: int, video_db_id: int):
    """Remove a video from a session"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'DELETE FROM session_videos WHERE session_id = ? AND video_id = ?',
            (session_id, video_db_id)
        )


# ============ MESSAGE OPERATIONS ============

def save_message(session_id: int, role: str, content: str, 
                 video_id: int = None) -> int:
    """Save a message to a session"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO messages (session_id, role, content, video_id)
            VALUES (?, ?, ?, ?)
        ''', (session_id, role, content, video_id))
        
        cursor.execute(
            'UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (session_id,)
        )
        return cursor.lastrowid


def get_session_messages(session_id: int) -> List[Dict]:
    """Get all messages in a session"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT m.*, v.video_id as youtube_video_id, v.title as video_title
            FROM messages m
            LEFT JOIN videos v ON m.video_id = v.id
            WHERE m.session_id = ?
            ORDER BY m.created_at
        ''', (session_id,))
        return [dict(row) for row in cursor.fetchall()]


def delete_message(message_id: int):
    """Delete a specific message"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM messages WHERE id = ?', (message_id,))


# ============ BOOKMARK OPERATIONS ============

def create_bookmark(session_id: int, title: str, message_id: int = None,
                    video_id: int = None, timestamp_seconds: int = None) -> int:
    """Create a new bookmark"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO bookmarks (session_id, message_id, video_id, title, timestamp_seconds)
            VALUES (?, ?, ?, ?, ?)
        ''', (session_id, message_id, video_id, title, timestamp_seconds))
        return cursor.lastrowid


def get_session_bookmarks(session_id: int) -> List[Dict]:
    """Get all bookmarks in a session"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT b.*, m.content as message_content, v.title as video_title
            FROM bookmarks b
            LEFT JOIN messages m ON b.message_id = m.id
            LEFT JOIN videos v ON b.video_id = v.id
            WHERE b.session_id = ?
            ORDER BY b.created_at DESC
        ''', (session_id,))
        return [dict(row) for row in cursor.fetchall()]


def delete_bookmark(bookmark_id: int):
    """Delete a bookmark"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM bookmarks WHERE id = ?', (bookmark_id,))


# ============ NOTE OPERATIONS ============

def create_note(session_id: int, content: str, video_id: int = None,
                bookmark_id: int = None) -> int:
    """Create a new note"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO notes (session_id, video_id, bookmark_id, content)
            VALUES (?, ?, ?, ?)
        ''', (session_id, video_id, bookmark_id, content))
        return cursor.lastrowid


def get_session_notes(session_id: int) -> List[Dict]:
    """Get all notes in a session"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT n.*, v.title as video_title, b.title as bookmark_title
            FROM notes n
            LEFT JOIN videos v ON n.video_id = v.id
            LEFT JOIN bookmarks b ON n.bookmark_id = b.id
            WHERE n.session_id = ?
            ORDER BY n.created_at DESC
        ''', (session_id,))
        return [dict(row) for row in cursor.fetchall()]


def update_note(note_id: int, content: str):
    """Update a note's content"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE notes SET content = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (content, note_id))


def delete_note(note_id: int):
    """Delete a note"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM notes WHERE id = ?', (note_id,))


# ============ SEARCH OPERATIONS ============

def search_messages(query: str, session_id: int = None) -> List[Dict]:
    """Search messages by content"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if session_id:
            cursor.execute('''
                SELECT m.*, cs.name as session_name, v.title as video_title
                FROM messages m
                JOIN chat_sessions cs ON m.session_id = cs.id
                LEFT JOIN videos v ON m.video_id = v.id
                WHERE m.content LIKE ? AND m.session_id = ?
                ORDER BY m.created_at DESC
            ''', (f'%{query}%', session_id))
        else:
            cursor.execute('''
                SELECT m.*, cs.name as session_name, v.title as video_title
                FROM messages m
                JOIN chat_sessions cs ON m.session_id = cs.id
                LEFT JOIN videos v ON m.video_id = v.id
                WHERE m.content LIKE ?
                ORDER BY m.created_at DESC
            ''', (f'%{query}%',))
        return [dict(row) for row in cursor.fetchall()]


def search_notes(query: str, session_id: int = None) -> List[Dict]:
    """Search notes by content"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if session_id:
            cursor.execute('''
                SELECT n.*, cs.name as session_name
                FROM notes n
                JOIN chat_sessions cs ON n.session_id = cs.id
                WHERE n.content LIKE ? AND n.session_id = ?
                ORDER BY n.created_at DESC
            ''', (f'%{query}%', session_id))
        else:
            cursor.execute('''
                SELECT n.*, cs.name as session_name
                FROM notes n
                JOIN chat_sessions cs ON n.session_id = cs.id
                WHERE n.content LIKE ?
                ORDER BY n.created_at DESC
            ''', (f'%{query}%',))
        return [dict(row) for row in cursor.fetchall()]


# Initialize database on module import
init_database()
