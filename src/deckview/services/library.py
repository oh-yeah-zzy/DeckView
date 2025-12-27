"""
文件库服务
负责扫描目录、构建文件树、管理文件索引
"""
import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

from ..core.config import settings
from ..schemas.document import DocumentType

logger = logging.getLogger(__name__)


# 延迟导入，避免循环依赖
def _get_cache_manager():
    from .cache_manager import cache_manager
    return cache_manager


class FileNode:
    """文件/目录节点"""

    def __init__(
        self,
        name: str,
        path: str,
        node_type: str,  # "dir" 或 "file"
        doc_type: Optional[str] = None,
        file_id: Optional[str] = None,
        size: int = 0,
        mtime: float = 0
    ):
        self.name = name
        self.path = path  # 相对路径
        self.node_type = node_type
        self.doc_type = doc_type
        self.file_id = file_id
        self.size = size
        self.mtime = mtime
        self.children: List['FileNode'] = []

    def to_dict(self) -> dict:
        """转换为字典（用于JSON序列化）"""
        result = {
            "name": self.name,
            "path": self.path,
            "type": self.node_type
        }

        if self.node_type == "file":
            result["id"] = self.file_id
            result["doc_type"] = self.doc_type
            result["size"] = self.size
            result["mtime"] = self.mtime
        else:
            # 目录：递归转换子节点
            result["children"] = [child.to_dict() for child in self.children]

        return result


class FileInfo:
    """文件信息"""

    def __init__(
        self,
        file_id: str,
        name: str,
        rel_path: str,
        abs_path: Path,
        doc_type: DocumentType,
        size: int,
        mtime: float
    ):
        self.file_id = file_id
        self.name = name
        self.rel_path = rel_path
        self.abs_path = abs_path
        self.doc_type = doc_type
        self.size = size
        self.mtime = mtime

    def to_dict(self) -> dict:
        return {
            "id": self.file_id,
            "name": self.name,
            "path": self.rel_path,
            "doc_type": self.doc_type.value,
            "size": self.size,
            "mtime": self.mtime,
            "mtime_str": datetime.fromtimestamp(self.mtime).strftime("%Y-%m-%d %H:%M:%S")
        }


class LibraryService:
    """文件库服务类"""

    def __init__(self):
        """初始化文件库服务"""
        # 文件索引：file_id -> FileInfo
        self._index: Dict[str, FileInfo] = {}
        # 目录树缓存
        self._tree: Optional[FileNode] = None
        # 上次扫描时间
        self._last_scan: float = 0
        # 缓存有效期（秒）
        self._cache_ttl: float = 2.0

    def _generate_file_id(self, rel_path: str) -> str:
        """根据相对路径生成稳定的文件ID"""
        # 使用SHA256哈希的前16位作为ID
        return hashlib.sha256(rel_path.encode('utf-8')).hexdigest()[:16]

    def _get_doc_type(self, ext: str) -> Optional[DocumentType]:
        """根据扩展名获取文档类型"""
        ext = ext.lower().lstrip('.')
        if ext in ('pptx', 'ppt'):
            return DocumentType.PPTX
        elif ext == 'pdf':
            return DocumentType.PDF
        elif ext in ('md', 'markdown'):
            return DocumentType.MARKDOWN
        elif ext in ('docx', 'doc'):
            return DocumentType.DOCX
        return None

    def _should_ignore(self, name: str) -> bool:
        """检查是否应该忽略该目录"""
        return name in settings.IGNORE_DIRS or name.startswith('.')

    def _is_allowed_file(self, filename: str) -> bool:
        """检查文件是否是允许的类型"""
        ext = Path(filename).suffix.lower().lstrip('.')
        return ext in settings.ALLOWED_EXTENSIONS

    def scan(self, force: bool = False, clean_orphans: bool = True) -> FileNode:
        """
        扫描内容目录，构建文件树

        Args:
            force: 是否强制重新扫描（忽略缓存）
            clean_orphans: 是否清理孤立缓存

        Returns:
            FileNode: 根目录节点
        """
        import time
        now = time.time()

        # 检查缓存是否有效
        if not force and self._tree and (now - self._last_scan) < self._cache_ttl:
            return self._tree

        content_dir = settings.CONTENT_DIR
        if not content_dir or not content_dir.exists():
            logger.warning("内容目录未设置或不存在")
            return FileNode(name="", path="", node_type="dir")

        logger.info(f"扫描目录: {content_dir}")

        # 保存旧的文件 ID 集合（用于检测删除的文件）
        old_file_ids = set(self._index.keys())

        # 清空索引
        self._index.clear()

        # 递归扫描
        root = self._scan_directory(content_dir, "")

        self._tree = root
        self._last_scan = now

        logger.info(f"扫描完成，共 {len(self._index)} 个文件")

        # 清理孤立缓存（源文件已删除的缓存）
        if clean_orphans and old_file_ids:
            # 找出已删除的文件
            deleted_file_ids = old_file_ids - set(self._index.keys())
            if deleted_file_ids:
                cache_mgr = _get_cache_manager()
                for file_id in deleted_file_ids:
                    cache_mgr.clear_file_cache(file_id)
                logger.info(f"已清理 {len(deleted_file_ids)} 个已删除文件的缓存")

        return root

    def _scan_directory(self, dir_path: Path, rel_path: str) -> FileNode:
        """
        递归扫描目录

        Args:
            dir_path: 目录绝对路径
            rel_path: 目录相对路径

        Returns:
            FileNode: 目录节点
        """
        dir_name = dir_path.name if rel_path else settings.CONTENT_DIR.name
        node = FileNode(name=dir_name, path=rel_path, node_type="dir")

        try:
            # 获取目录内容并排序
            entries = sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))

            for entry in entries:
                # 跳过隐藏文件和忽略的目录
                if entry.name.startswith('.'):
                    continue

                entry_rel_path = f"{rel_path}/{entry.name}" if rel_path else entry.name

                if entry.is_dir():
                    # 检查是否应该忽略
                    if self._should_ignore(entry.name):
                        continue
                    # 递归扫描子目录
                    child_node = self._scan_directory(entry, entry_rel_path)
                    # 只添加非空目录
                    if child_node.children:
                        node.children.append(child_node)

                elif entry.is_file():
                    # 检查文件类型
                    if not self._is_allowed_file(entry.name):
                        continue

                    # 获取文件信息
                    ext = entry.suffix.lower().lstrip('.')
                    doc_type = self._get_doc_type(ext)
                    if not doc_type:
                        continue

                    stat = entry.stat()
                    file_id = self._generate_file_id(entry_rel_path)

                    # 创建文件节点
                    file_node = FileNode(
                        name=entry.name,
                        path=entry_rel_path,
                        node_type="file",
                        doc_type=doc_type.value,
                        file_id=file_id,
                        size=stat.st_size,
                        mtime=stat.st_mtime
                    )
                    node.children.append(file_node)

                    # 添加到索引
                    self._index[file_id] = FileInfo(
                        file_id=file_id,
                        name=entry.name,
                        rel_path=entry_rel_path,
                        abs_path=entry,
                        doc_type=doc_type,
                        size=stat.st_size,
                        mtime=stat.st_mtime
                    )

        except PermissionError:
            logger.warning(f"无权限访问目录: {dir_path}")
        except Exception as e:
            logger.error(f"扫描目录出错 {dir_path}: {e}")

        return node

    def get_tree(self, force_refresh: bool = False) -> dict:
        """获取目录树（JSON格式）"""
        root = self.scan(force=force_refresh)
        return root.to_dict()

    def get_file(self, file_id: str) -> Optional[FileInfo]:
        """根据ID获取文件信息"""
        # 确保索引已构建
        self.scan()
        return self._index.get(file_id)

    def get_file_by_path(self, rel_path: str) -> Optional[FileInfo]:
        """根据相对路径获取文件信息"""
        file_id = self._generate_file_id(rel_path)
        return self.get_file(file_id)

    def get_all_files(self) -> List[FileInfo]:
        """获取所有文件列表"""
        self.scan()
        return list(self._index.values())

    def invalidate_cache(self):
        """使缓存失效（文件变化时调用）"""
        self._last_scan = 0
        self._tree = None

    def get_stats(self) -> dict:
        """获取统计信息"""
        self.scan()

        stats = {
            "total_files": len(self._index),
            "by_type": {}
        }

        for file_info in self._index.values():
            doc_type = file_info.doc_type.value
            if doc_type not in stats["by_type"]:
                stats["by_type"][doc_type] = 0
            stats["by_type"][doc_type] += 1

        return stats


# 创建全局服务实例
library_service = LibraryService()
