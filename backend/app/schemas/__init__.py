"""
Schemas模块初始化
"""
from .document import (
    DocumentType,
    ConversionStatus,
    DocumentBase,
    DocumentCreate,
    DocumentResponse,
    DocumentList,
    DocumentDetail,
    ThumbnailInfo
)

__all__ = [
    'DocumentType',
    'ConversionStatus',
    'DocumentBase',
    'DocumentCreate',
    'DocumentResponse',
    'DocumentList',
    'DocumentDetail',
    'ThumbnailInfo'
]
