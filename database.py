"""
Database module for YouTube Chatbot
Handles all MongoDB operations for persistent storage
"""

import os
from datetime import datetime
from typing import Optional, List, Dict
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "")
DB_NAME = "VIDMindm" 

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

videos_col = db['videos']
sessions_col = db['chat_sessions']
messages_col = db['messages']
bookmarks_col = db['bookmarks']
notes_col = db['notes']

def _doc_to_dict(doc: dict) -> Optional[dict]:
    """Helper to convert ObjectId to string id"""
    if not doc: return None
    doc['id'] = str(doc.pop('_id'))
    # Ensure dates are strings for easier pydantic/fastapi serialization if needed, 
    # but fastapi automatically handles datetime objects
    return doc

def save_video(video_id: str, url: str, metadata: dict = None, transcript: str = None) -> str:
    now = datetime.now()
    update_data = {
        "url": url,
        "transcript": transcript,
        "updated_at": now
    }
    if metadata:
        for k, v in metadata.items():
            update_data[k] = v
            
    # remove Nones to not overwrite existing data with null
    update_data = {k: v for k, v in update_data.items() if v is not None}
    
    result = videos_col.find_one_and_update(
        {"video_id": video_id},
        {"$set": update_data, "$setOnInsert": {"created_at": now}},
        upsert=True,
        return_document=True
    )
    return str(result['_id'])

def get_video(video_id: str) -> Optional[Dict]:
    doc = videos_col.find_one({"video_id": video_id})
    return _doc_to_dict(doc)

def get_video_by_id(db_id: str) -> Optional[Dict]:
    try:
        doc = videos_col.find_one({"_id": ObjectId(db_id)})
        return _doc_to_dict(doc)
    except:
        return None

def get_all_videos() -> List[Dict]:
    docs = videos_col.find().sort("created_at", -1)
    return [_doc_to_dict(doc) for doc in docs]

def create_session(name: str = None) -> str:
    """Create a new chat session"""
    if not name:
        name = "New Session"
    now = datetime.now()
    doc = {
        "name": name,
        "created_at": now,
        "updated_at": now,
        "is_active": True,
        "video_ids": []
    }
    result = sessions_col.insert_one(doc)
    return str(result.inserted_id)

def get_session(session_id: str) -> Optional[Dict]:
    try:
        doc = sessions_col.find_one({"_id": ObjectId(session_id)})
        return _doc_to_dict(doc)
    except:
        return None

def get_all_sessions() -> List[Dict]:
    pipeline = [
        {"$lookup": {"from": "messages", "localField": "_id", "foreignField": "session_id", "as": "msgs"}},
        {"$addFields": {
            "message_count": {"$size": "$msgs"},
            "video_count": {"$size": {"$ifNull": ["$video_ids", []]}}
        }},
        {"$project": {"msgs": 0}},
        {"$sort": {"updated_at": -1}}
    ]
    docs = list(sessions_col.aggregate(pipeline))
    return [_doc_to_dict(doc) for doc in docs]

def update_session_name(session_id: str, name: str):
    sessions_col.update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {"name": name, "updated_at": datetime.now()}}
    )

def delete_session(session_id: str):
    sid = ObjectId(session_id)
    sessions_col.delete_one({"_id": sid})
    messages_col.delete_many({"session_id": sid})
    bookmarks_col.delete_many({"session_id": sid})
    notes_col.delete_many({"session_id": sid})

def add_video_to_session(session_id: str, video_db_id: str):
    vid = ObjectId(video_db_id)
    sessions_col.update_one(
        {"_id": ObjectId(session_id)},
        {
            "$addToSet": {"video_ids": vid},
            "$set": {"updated_at": datetime.now()}
        }
    )

def get_session_videos(session_id: str) -> List[Dict]:
    session = get_session(session_id)
    if not session or not session.get('video_ids'):
        return []
    videos = list(videos_col.find({"_id": {"$in": session['video_ids']}}))
    return [_doc_to_dict(v) for v in videos]

def remove_video_from_session(session_id: str, video_db_id: str):
    sessions_col.update_one(
        {"_id": ObjectId(session_id)},
        {
            "$pull": {"video_ids": ObjectId(video_db_id)},
            "$set": {"updated_at": datetime.now()}
        }
    )

def save_message(session_id: str, role: str, content: str, video_id: str = None) -> str:
    now = datetime.now()
    doc = {
        "session_id": ObjectId(session_id),
        "role": role,
        "content": content,
        "video_id": ObjectId(video_id) if video_id else None,
        "created_at": now
    }
    res = messages_col.insert_one(doc)
    sessions_col.update_one({"_id": ObjectId(session_id)}, {"$set": {"updated_at": now}})
    return str(res.inserted_id)

def get_session_messages(session_id: str) -> List[Dict]:
    pipeline = [
        {"$match": {"session_id": ObjectId(session_id)}},
        {"$lookup": {"from": "videos", "localField": "video_id", "foreignField": "_id", "as": "video_info"}},
        {"$unwind": {"path": "$video_info", "preserveNullAndEmptyArrays": True}},
        {"$addFields": {
            "youtube_video_id": "$video_info.video_id",
            "video_title": "$video_info.title"
        }},
        {"$project": {"video_info": 0}},
        {"$sort": {"created_at": 1}}
    ]
    docs = list(messages_col.aggregate(pipeline))
    res = []
    for d in docs:
        if 'video_id' in d and d['video_id']: d['video_id'] = str(d['video_id'])
        if 'session_id' in d: d['session_id'] = str(d['session_id'])
        res.append(_doc_to_dict(d))
    return res

def delete_message(message_id: str):
    messages_col.delete_one({"_id": ObjectId(message_id)})

def create_bookmark(session_id: str, title: str, message_id: str = None,
                    video_id: str = None, timestamp_seconds: int = None) -> str:
    doc = {
        "session_id": ObjectId(session_id),
        "title": title,
        "message_id": ObjectId(message_id) if message_id else None,
        "video_id": ObjectId(video_id) if video_id else None,
        "timestamp_seconds": timestamp_seconds,
        "created_at": datetime.now()
    }
    res = bookmarks_col.insert_one(doc)
    return str(res.inserted_id)

def get_session_bookmarks(session_id: str) -> List[Dict]:
    pipeline = [
        {"$match": {"session_id": ObjectId(session_id)}},
        {"$lookup": {"from": "messages", "localField": "message_id", "foreignField": "_id", "as": "msg"}},
        {"$lookup": {"from": "videos", "localField": "video_id", "foreignField": "_id", "as": "vid"}},
        {"$unwind": {"path": "$msg", "preserveNullAndEmptyArrays": True}},
        {"$unwind": {"path": "$vid", "preserveNullAndEmptyArrays": True}},
        {"$addFields": {
            "message_content": "$msg.content",
            "video_title": "$vid.title"
        }},
        {"$project": {"msg": 0, "vid": 0}},
        {"$sort": {"created_at": -1}}
    ]
    docs = list(bookmarks_col.aggregate(pipeline))
    res = []
    for d in docs:
        if 'session_id' in d: d['session_id'] = str(d['session_id'])
        if 'video_id' in d and d['video_id']: d['video_id'] = str(d['video_id'])
        if 'message_id' in d and d['message_id']: d['message_id'] = str(d['message_id'])
        res.append(_doc_to_dict(d))
    return res

def delete_bookmark(bookmark_id: str):
    bookmarks_col.delete_one({"_id": ObjectId(bookmark_id)})

def create_note(session_id: str, content: str, video_id: str = None,
                bookmark_id: str = None) -> str:
    now = datetime.now()
    doc = {
        "session_id": ObjectId(session_id),
        "content": content,
        "video_id": ObjectId(video_id) if video_id else None,
        "bookmark_id": ObjectId(bookmark_id) if bookmark_id else None,
        "created_at": now,
        "updated_at": now
    }
    res = notes_col.insert_one(doc)
    return str(res.inserted_id)

def get_session_notes(session_id: str) -> List[Dict]:
    pipeline = [
        {"$match": {"session_id": ObjectId(session_id)}},
        {"$lookup": {"from": "videos", "localField": "video_id", "foreignField": "_id", "as": "vid"}},
        {"$lookup": {"from": "bookmarks", "localField": "bookmark_id", "foreignField": "_id", "as": "bm"}},
        {"$unwind": {"path": "$vid", "preserveNullAndEmptyArrays": True}},
        {"$unwind": {"path": "$bm", "preserveNullAndEmptyArrays": True}},
        {"$addFields": {
            "video_title": "$vid.title",
            "bookmark_title": "$bm.title"
        }},
        {"$project": {"vid": 0, "bm": 0}},
        {"$sort": {"created_at": -1}}
    ]
    docs = list(notes_col.aggregate(pipeline))
    res = []
    for d in docs:
        if 'session_id' in d: d['session_id'] = str(d['session_id'])
        if 'video_id' in d and d['video_id']: d['video_id'] = str(d['video_id'])
        if 'bookmark_id' in d and d['bookmark_id']: d['bookmark_id'] = str(d['bookmark_id'])
        res.append(_doc_to_dict(d))
    return res

def update_note(note_id: str, content: str):
    notes_col.update_one(
        {"_id": ObjectId(note_id)},
        {"$set": {"content": content, "updated_at": datetime.now()}}
    )

def delete_note(note_id: str):
    notes_col.delete_one({"_id": ObjectId(note_id)})

def search_messages(query: str, session_id: str = None) -> List[Dict]:
    match_stage = {"content": {"$regex": query, "$options": "i"}}
    if session_id:
        match_stage["session_id"] = ObjectId(session_id)
        
    pipeline = [
        {"$match": match_stage},
        {"$lookup": {"from": "chat_sessions", "localField": "session_id", "foreignField": "_id", "as": "sess"}},
        {"$lookup": {"from": "videos", "localField": "video_id", "foreignField": "_id", "as": "vid"}},
        {"$unwind": {"path": "$sess", "preserveNullAndEmptyArrays": True}},
        {"$unwind": {"path": "$vid", "preserveNullAndEmptyArrays": True}},
        {"$addFields": {
            "session_name": "$sess.name",
            "video_title": "$vid.title"
        }},
        {"$project": {"sess": 0, "vid": 0}},
        {"$sort": {"created_at": -1}}
    ]
    docs = list(messages_col.aggregate(pipeline))
    res = []
    for d in docs:
        if 'session_id' in d: d['session_id'] = str(d['session_id'])
        if 'video_id' in d and d['video_id']: d['video_id'] = str(d['video_id'])
        res.append(_doc_to_dict(d))
    return res

def search_notes(query: str, session_id: str = None) -> List[Dict]:
    match_stage = {"content": {"$regex": query, "$options": "i"}}
    if session_id:
        match_stage["session_id"] = ObjectId(session_id)
        
    pipeline = [
        {"$match": match_stage},
        {"$lookup": {"from": "chat_sessions", "localField": "session_id", "foreignField": "_id", "as": "sess"}},
        {"$unwind": {"path": "$sess", "preserveNullAndEmptyArrays": True}},
        {"$addFields": {
            "session_name": "$sess.name"
        }},
        {"$project": {"sess": 0}},
        {"$sort": {"created_at": -1}}
    ]
    docs = list(notes_col.aggregate(pipeline))
    res = []
    for d in docs:
        if 'session_id' in d: d['session_id'] = str(d['session_id'])
        if 'video_id' in d and d['video_id']: d['video_id'] = str(d['video_id'])
        if 'bookmark_id' in d and d['bookmark_id']: d['bookmark_id'] = str(d['bookmark_id'])
        res.append(_doc_to_dict(d))
    return res
