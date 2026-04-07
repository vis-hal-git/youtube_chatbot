"""
Data models for YouTube Chatbot
Dataclasses for type-safe data handling
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class Video:
    """Represents a YouTube video"""
    id: int = None
    video_id: str = ""  # YouTube video ID
    url: str = ""
    title: Optional[str] = None
    channel: Optional[str] = None
    duration: Optional[str] = None
    transcript: Optional[str] = None
    created_at: datetime = None
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Video':
        return cls(
            id=data.get('id'),
            video_id=data.get('video_id', ''),
            url=data.get('url', ''),
            title=data.get('title'),
            channel=data.get('channel'),
            duration=data.get('duration'),
            transcript=data.get('transcript'),
            created_at=data.get('created_at')
        )


@dataclass
class Message:
    """Represents a chat message"""
    id: int = None
    session_id: int = None
    role: str = ""  # 'user' or 'assistant'
    content: str = ""
    video_id: Optional[int] = None
    video_title: Optional[str] = None
    youtube_video_id: Optional[str] = None
    created_at: datetime = None
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Message':
        return cls(
            id=data.get('id'),
            session_id=data.get('session_id'),
            role=data.get('role', ''),
            content=data.get('content', ''),
            video_id=data.get('video_id'),
            video_title=data.get('video_title'),
            youtube_video_id=data.get('youtube_video_id'),
            created_at=data.get('created_at')
        )


@dataclass
class ChatSession:
    """Represents a chat session"""
    id: int = None
    name: str = ""
    created_at: datetime = None
    updated_at: datetime = None
    is_active: bool = True
    message_count: int = 0
    video_count: int = 0
    messages: List[Message] = field(default_factory=list)
    videos: List[Video] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ChatSession':
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
            is_active=bool(data.get('is_active', 1)),
            message_count=data.get('message_count', 0),
            video_count=data.get('video_count', 0)
        )


@dataclass
class Bookmark:
    """Represents a bookmark"""
    id: int = None
    session_id: int = None
    message_id: Optional[int] = None
    video_id: Optional[int] = None
    title: str = ""
    timestamp_seconds: Optional[int] = None
    message_content: Optional[str] = None
    video_title: Optional[str] = None
    created_at: datetime = None
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Bookmark':
        return cls(
            id=data.get('id'),
            session_id=data.get('session_id'),
            message_id=data.get('message_id'),
            video_id=data.get('video_id'),
            title=data.get('title', ''),
            timestamp_seconds=data.get('timestamp_seconds'),
            message_content=data.get('message_content'),
            video_title=data.get('video_title'),
            created_at=data.get('created_at')
        )
    
    @property
    def timestamp_formatted(self) -> str:
        """Format timestamp as MM:SS or HH:MM:SS"""
        if self.timestamp_seconds is None:
            return ""
        hours, remainder = divmod(self.timestamp_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"


@dataclass
class Note:
    """Represents a note"""
    id: int = None
    session_id: int = None
    video_id: Optional[int] = None
    bookmark_id: Optional[int] = None
    content: str = ""
    video_title: Optional[str] = None
    bookmark_title: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Note':
        return cls(
            id=data.get('id'),
            session_id=data.get('session_id'),
            video_id=data.get('video_id'),
            bookmark_id=data.get('bookmark_id'),
            content=data.get('content', ''),
            video_title=data.get('video_title'),
            bookmark_title=data.get('bookmark_title'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )


@dataclass
class ExportData:
    """Data structure for export operations"""
    session: ChatSession
    messages: List[Message]
    videos: List[Video]
    bookmarks: List[Bookmark]
    notes: List[Note]
    export_date: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'session_name': self.session.name,
            'session_id': self.session.id,
            'export_date': self.export_date.isoformat(),
            'videos': [
                {
                    'title': v.title or v.video_id,
                    'url': v.url,
                    'video_id': v.video_id
                } for v in self.videos
            ],
            'messages': [
                {
                    'role': m.role,
                    'content': m.content,
                    'video_title': m.video_title,
                    'timestamp': str(m.created_at) if m.created_at else None
                } for m in self.messages
            ],
            'bookmarks': [
                {
                    'title': b.title,
                    'timestamp': b.timestamp_formatted,
                    'video_title': b.video_title
                } for b in self.bookmarks
            ],
            'notes': [
                {
                    'content': n.content,
                    'video_title': n.video_title,
                    'bookmark_title': n.bookmark_title
                } for n in self.notes
            ]
        }
