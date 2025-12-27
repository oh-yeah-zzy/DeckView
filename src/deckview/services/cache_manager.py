"""
缓存管理服务
负责管理转换后的 PDF 和缩略图缓存，确保缓存与源文件同步

安全原则：
1. 只操作 data/converted/ 和 data/thumbnails/ 目录
2. 永远不删除或修改源文件
3. 通过路径验证确保操作安全
"""
import logging
from pathlib import Path
from typing import Set, List, Optional
import os

from ..core.config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """缓存管理器"""

    def __init__(self):
        """初始化缓存管理器"""
        # 允许操作的目录（白名单）
        self._allowed_dirs: Set[Path] = set()

    def _init_allowed_dirs(self):
        """初始化允许操作的目录"""
        if not self._allowed_dirs:
            self._allowed_dirs = {
                settings.CONVERTED_DIR.resolve(),
                settings.THUMBNAIL_DIR.resolve(),
                settings.CACHE_DIR.resolve()
            }

    def _is_safe_path(self, path: Path) -> bool:
        """
        检查路径是否安全（在允许的缓存目录内）

        这是核心安全检查，确保不会误删源文件
        """
        self._init_allowed_dirs()

        try:
            resolved = path.resolve()
            # 检查路径是否在允许的目录内
            for allowed_dir in self._allowed_dirs:
                try:
                    resolved.relative_to(allowed_dir)
                    return True
                except ValueError:
                    continue
            return False
        except Exception as e:
            logger.error(f"路径安全检查失败 {path}: {e}")
            return False

    def _safe_delete(self, path: Path) -> bool:
        """
        安全删除文件

        只有通过安全检查的文件才会被删除
        """
        if not self._is_safe_path(path):
            logger.warning(f"拒绝删除不安全路径: {path}")
            return False

        try:
            if path.exists() and path.is_file():
                path.unlink()
                logger.debug(f"已删除缓存文件: {path}")
                return True
        except Exception as e:
            logger.error(f"删除文件失败 {path}: {e}")
        return False

    def clear_file_cache(self, file_id: str) -> int:
        """
        清理指定文件的所有缓存

        Args:
            file_id: 文件 ID

        Returns:
            删除的文件数量
        """
        deleted_count = 0

        # 1. 清理转换后的 PDF
        pdf_path = settings.CONVERTED_DIR / f"{file_id}.pdf"
        if self._safe_delete(pdf_path):
            deleted_count += 1

        # 2. 清理缩略图（可能有多页）
        thumbnail_pattern = f"{file_id}_page*"
        try:
            for thumb_file in settings.THUMBNAIL_DIR.glob(thumbnail_pattern):
                if self._safe_delete(thumb_file):
                    deleted_count += 1
        except Exception as e:
            logger.error(f"清理缩略图失败: {e}")

        if deleted_count > 0:
            logger.info(f"已清理文件 {file_id} 的 {deleted_count} 个缓存文件")

        return deleted_count

    def is_cache_valid(self, file_id: str, source_mtime: float) -> bool:
        """
        检查缓存是否有效（源文件未被修改）

        Args:
            file_id: 文件 ID
            source_mtime: 源文件的修改时间

        Returns:
            缓存是否有效
        """
        pdf_path = settings.CONVERTED_DIR / f"{file_id}.pdf"

        if not pdf_path.exists():
            return False

        try:
            cache_mtime = pdf_path.stat().st_mtime
            # 缓存时间应该晚于源文件修改时间
            return cache_mtime > source_mtime
        except Exception:
            return False

    def clear_orphan_caches(self, valid_file_ids: Set[str]) -> int:
        """
        清理孤立缓存（源文件已不存在的缓存）

        Args:
            valid_file_ids: 当前有效的文件 ID 集合

        Returns:
            删除的文件数量
        """
        deleted_count = 0

        # 1. 清理孤立的 PDF 缓存
        try:
            for pdf_file in settings.CONVERTED_DIR.glob("*.pdf"):
                file_id = pdf_file.stem
                if file_id not in valid_file_ids:
                    if self._safe_delete(pdf_file):
                        deleted_count += 1
                        logger.info(f"清理孤立 PDF 缓存: {pdf_file.name}")
        except Exception as e:
            logger.error(f"清理孤立 PDF 缓存失败: {e}")

        # 2. 清理孤立的缩略图
        try:
            for thumb_file in settings.THUMBNAIL_DIR.glob("*_page*"):
                # 从文件名提取 file_id（格式：{file_id}_page{n}.png）
                file_id = thumb_file.stem.rsplit('_page', 1)[0]
                if file_id not in valid_file_ids:
                    if self._safe_delete(thumb_file):
                        deleted_count += 1
        except Exception as e:
            logger.error(f"清理孤立缩略图失败: {e}")

        if deleted_count > 0:
            logger.info(f"共清理 {deleted_count} 个孤立缓存文件")

        return deleted_count

    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        stats = {
            "converted_count": 0,
            "converted_size": 0,
            "thumbnail_count": 0,
            "thumbnail_size": 0
        }

        try:
            # 统计转换后的 PDF
            for pdf_file in settings.CONVERTED_DIR.glob("*.pdf"):
                stats["converted_count"] += 1
                stats["converted_size"] += pdf_file.stat().st_size
        except Exception:
            pass

        try:
            # 统计缩略图
            for thumb_file in settings.THUMBNAIL_DIR.glob("*_page*"):
                stats["thumbnail_count"] += 1
                stats["thumbnail_size"] += thumb_file.stat().st_size
        except Exception:
            pass

        return stats


# 创建全局缓存管理器实例
cache_manager = CacheManager()
