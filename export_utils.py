"""
Export utilities for YouTube Chatbot
Export chat sessions to various formats: Markdown, TXT, PDF
"""

import os
from datetime import datetime
from typing import List
from io import BytesIO

from models import ExportData, Message, Video, Bookmark, Note, ChatSession


def export_to_markdown(export_data: ExportData) -> str:
    """Export chat session to Markdown format"""
    lines = []
    
    # Header
    lines.append(f"# {export_data.session.name}")
    lines.append(f"\n**Exported:** {export_data.export_date.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    
    # Videos section
    if export_data.videos:
        lines.append("## 📹 Videos")
        lines.append("")
        for video in export_data.videos:
            title = video.title or video.video_id
            lines.append(f"- **{title}**")
            lines.append(f"  - URL: {video.url}")
            if video.channel:
                lines.append(f"  - Channel: {video.channel}")
        lines.append("")
    
    # Chat History section
    if export_data.messages:
        lines.append("## 💬 Chat History")
        lines.append("")
        for msg in export_data.messages:
            role_emoji = "👤" if msg.role == "user" else "🤖"
            role_name = "User" if msg.role == "user" else "Assistant"
            lines.append(f"### {role_emoji} {role_name}")
            if msg.video_title:
                lines.append(f"*Video: {msg.video_title}*")
            lines.append("")
            lines.append(msg.content)
            lines.append("")
            lines.append("---")
            lines.append("")
    
    # Bookmarks section
    if export_data.bookmarks:
        lines.append("## 🔖 Bookmarks")
        lines.append("")
        for bookmark in export_data.bookmarks:
            lines.append(f"### {bookmark.title}")
            if bookmark.timestamp_formatted:
                lines.append(f"- **Timestamp:** {bookmark.timestamp_formatted}")
            if bookmark.video_title:
                lines.append(f"- **Video:** {bookmark.video_title}")
            if bookmark.message_content:
                lines.append(f"- **Related message:** {bookmark.message_content[:200]}...")
            lines.append("")
    
    # Notes section
    if export_data.notes:
        lines.append("## 📝 Notes")
        lines.append("")
        for note in export_data.notes:
            lines.append(f"### Note")
            if note.video_title:
                lines.append(f"*Video: {note.video_title}*")
            if note.bookmark_title:
                lines.append(f"*Bookmark: {note.bookmark_title}*")
            lines.append("")
            lines.append(note.content)
            lines.append("")
            lines.append("---")
            lines.append("")
    
    return "\n".join(lines)


def export_to_txt(export_data: ExportData) -> str:
    """Export chat session to plain text format"""
    lines = []
    
    # Header
    lines.append("=" * 60)
    lines.append(f"  {export_data.session.name}")
    lines.append("=" * 60)
    lines.append(f"Exported: {export_data.export_date.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    
    # Videos section
    if export_data.videos:
        lines.append("-" * 40)
        lines.append("VIDEOS")
        lines.append("-" * 40)
        for video in export_data.videos:
            title = video.title or video.video_id
            lines.append(f"* {title}")
            lines.append(f"  URL: {video.url}")
            if video.channel:
                lines.append(f"  Channel: {video.channel}")
        lines.append("")
    
    # Chat History section
    if export_data.messages:
        lines.append("-" * 40)
        lines.append("CHAT HISTORY")
        lines.append("-" * 40)
        lines.append("")
        for msg in export_data.messages:
            role_name = "USER" if msg.role == "user" else "ASSISTANT"
            lines.append(f"[{role_name}]")
            if msg.video_title:
                lines.append(f"(Video: {msg.video_title})")
            lines.append("")
            lines.append(msg.content)
            lines.append("")
            lines.append("-" * 20)
            lines.append("")
    
    # Bookmarks section
    if export_data.bookmarks:
        lines.append("-" * 40)
        lines.append("BOOKMARKS")
        lines.append("-" * 40)
        for bookmark in export_data.bookmarks:
            lines.append(f"* {bookmark.title}")
            if bookmark.timestamp_formatted:
                lines.append(f"  Timestamp: {bookmark.timestamp_formatted}")
            if bookmark.video_title:
                lines.append(f"  Video: {bookmark.video_title}")
        lines.append("")
    
    # Notes section
    if export_data.notes:
        lines.append("-" * 40)
        lines.append("NOTES")
        lines.append("-" * 40)
        for note in export_data.notes:
            if note.video_title:
                lines.append(f"[Video: {note.video_title}]")
            if note.bookmark_title:
                lines.append(f"[Bookmark: {note.bookmark_title}]")
            lines.append(note.content)
            lines.append("")
            lines.append("-" * 20)
            lines.append("")
    
    return "\n".join(lines)


def export_to_pdf(export_data: ExportData) -> bytes:
    """Export chat session to PDF format"""
    try:
        from fpdf import FPDF
    except ImportError:
        raise ImportError("fpdf2 is required for PDF export. Install it with: pip install fpdf2")
    
    class PDF(FPDF):
        def header(self):
            self.set_font('Helvetica', 'B', 12)
            self.cell(0, 10, export_data.session.name, 0, 1, 'C')
            self.ln(5)
        
        def footer(self):
            self.set_y(-15)
            self.set_font('Helvetica', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
        
        def chapter_title(self, title):
            self.set_font('Helvetica', 'B', 14)
            self.set_fill_color(240, 240, 240)
            self.cell(0, 10, title, 0, 1, 'L', fill=True)
            self.ln(4)
        
        def chapter_body(self, body):
            self.set_font('Helvetica', '', 10)
            # Handle encoding issues
            safe_body = body.encode('latin-1', errors='replace').decode('latin-1')
            self.multi_cell(0, 5, safe_body)
            self.ln()
    
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Export date
    pdf.set_font('Helvetica', 'I', 10)
    pdf.cell(0, 10, f"Exported: {export_data.export_date.strftime('%Y-%m-%d %H:%M:%S')}", 0, 1)
    pdf.ln(5)
    
    # Videos section
    if export_data.videos:
        pdf.chapter_title("Videos")
        for video in export_data.videos:
            title = video.title or video.video_id
            pdf.set_font('Helvetica', 'B', 10)
            pdf.cell(0, 6, f"* {title}", 0, 1)
            pdf.set_font('Helvetica', '', 9)
            pdf.cell(0, 5, f"  URL: {video.url}", 0, 1)
            if video.channel:
                pdf.cell(0, 5, f"  Channel: {video.channel}", 0, 1)
        pdf.ln(5)
    
    # Chat History section
    if export_data.messages:
        pdf.chapter_title("Chat History")
        for msg in export_data.messages:
            role_name = "USER" if msg.role == "user" else "ASSISTANT"
            pdf.set_font('Helvetica', 'B', 10)
            pdf.cell(0, 6, f"[{role_name}]", 0, 1)
            
            if msg.video_title:
                pdf.set_font('Helvetica', 'I', 9)
                pdf.cell(0, 5, f"Video: {msg.video_title}", 0, 1)
            
            pdf.set_font('Helvetica', '', 10)
            safe_content = msg.content.encode('latin-1', errors='replace').decode('latin-1')
            pdf.multi_cell(0, 5, safe_content)
            pdf.ln(3)
            pdf.cell(0, 0, '', 'T')  # Horizontal line
            pdf.ln(5)
    
    # Bookmarks section
    if export_data.bookmarks:
        pdf.add_page()
        pdf.chapter_title("Bookmarks")
        for bookmark in export_data.bookmarks:
            pdf.set_font('Helvetica', 'B', 10)
            safe_title = bookmark.title.encode('latin-1', errors='replace').decode('latin-1')
            pdf.cell(0, 6, f"* {safe_title}", 0, 1)
            pdf.set_font('Helvetica', '', 9)
            if bookmark.timestamp_formatted:
                pdf.cell(0, 5, f"  Timestamp: {bookmark.timestamp_formatted}", 0, 1)
            if bookmark.video_title:
                pdf.cell(0, 5, f"  Video: {bookmark.video_title}", 0, 1)
        pdf.ln(5)
    
    # Notes section
    if export_data.notes:
        pdf.chapter_title("Notes")
        for note in export_data.notes:
            if note.video_title:
                pdf.set_font('Helvetica', 'I', 9)
                pdf.cell(0, 5, f"Video: {note.video_title}", 0, 1)
            if note.bookmark_title:
                pdf.set_font('Helvetica', 'I', 9)
                pdf.cell(0, 5, f"Bookmark: {note.bookmark_title}", 0, 1)
            
            pdf.set_font('Helvetica', '', 10)
            safe_content = note.content.encode('latin-1', errors='replace').decode('latin-1')
            pdf.multi_cell(0, 5, safe_content)
            pdf.ln(3)
            pdf.cell(0, 0, '', 'T')
            pdf.ln(5)
    
    # Return PDF as bytes
    return pdf.output()


def get_export_filename(session_name: str, format: str) -> str:
    """Generate a safe filename for export"""
    # Remove invalid characters
    safe_name = "".join(c for c in session_name if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_name = safe_name.replace(' ', '_')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{safe_name}_{timestamp}.{format}"
