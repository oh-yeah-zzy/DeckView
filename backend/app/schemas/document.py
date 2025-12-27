"""
文档相关的Pydantic模型
用于API请求和响应的数据验证
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """文档类型枚举"""
    PPTX = "pptx"
    PDF = "pdf"
    MARKDOWN = "markdown"
    DOCX = "docx"  # Word 文档


class ConversionStatus(str, Enum):
    """转换状态枚举"""
    PENDING = "pending"      # 等待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"        # 失败


class DocumentBase(BaseModel):
    """文档基础模型"""
    filename: str = Field(..., description="原始文件名")
    doc_type: DocumentType = Field(..., description="文档类型")


class DocumentCreate(DocumentBase):
    """创建文档时的模型"""
    pass


class DocumentResponse(DocumentBase):
    """文档响应模型"""
    id: str = Field(..., description="文档唯一ID")
    size: int = Field(..., description="文件大小（字节）")
    status: ConversionStatus = Field(..., description="转换状态")
    created_at: datetime = Field(..., description="创建时间")
    page_count: Optional[int] = Field(None, description="页数（PDF/PPTX）")
    error_message: Optional[str] = Field(None, description="错误信息")

    class Config:
        from_attributes = True


class DocumentList(BaseModel):
    """文档列表响应"""
    total: int = Field(..., description="总数量")
    documents: List[DocumentResponse] = Field(..., description="文档列表")


class ThumbnailInfo(BaseModel):
    """缩略图信息"""
    page: int = Field(..., description="页码")
    url: str = Field(..., description="缩略图URL")


class DocumentDetail(DocumentResponse):
    """文档详细信息"""
    thumbnails: Optional[List[ThumbnailInfo]] = Field(None, description="缩略图列表")
    pdf_url: Optional[str] = Field(None, description="PDF文件URL")
    content: Optional[str] = Field(None, description="Markdown内容")
