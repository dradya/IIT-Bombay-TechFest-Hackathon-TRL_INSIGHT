"""Document upload schemas."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PageText(BaseModel):
    page: int
    text: str = Field(default="", description="Text extracted from this page/section")
    chars: int = 0


class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    original_name: str
    file_type: str
    size_bytes: int
    page_count: int
    char_count: int
    uploaded_at: str
    preview_text: str = Field(
        default="", description="First part of the extracted text for preview"
    )
    preview_pages: list[PageText] = Field(default_factory=list)
    headings: list[str] = Field(default_factory=list)
    has_tables: bool = False
    ocr_used: bool = False
    warnings: list[str] = Field(default_factory=list)
    extraction_method: str = "text"
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentInfo(BaseModel):
    id: str
    filename: str
    original_name: str
    file_type: str
    size_bytes: int
    page_count: int
    char_count: int
    uploaded_at: str
