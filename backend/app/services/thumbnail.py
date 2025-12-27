"""
缩略图生成服务
使用PyMuPDF (fitz) 从PDF生成缩略图
"""
import asyncio
from pathlib import Path
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# 尝试导入PyMuPDF
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger.warning("PyMuPDF未安装，缩略图生成功能将不可用")

from ..core.config import settings


class ThumbnailService:
    """缩略图生成服务类"""

    def __init__(self):
        """初始化缩略图服务"""
        self.width = settings.THUMBNAIL_WIDTH
        self.format = settings.THUMBNAIL_FORMAT

    def is_available(self) -> bool:
        """检查服务是否可用"""
        return PYMUPDF_AVAILABLE

    async def generate_thumbnails(
        self,
        pdf_path: Path,
        output_dir: Path,
        doc_id: str
    ) -> Tuple[bool, List[str], Optional[str]]:
        """
        从PDF生成所有页面的缩略图

        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            doc_id: 文档ID

        Returns:
            Tuple[bool, List[str], Optional[str]]: (是否成功, 缩略图路径列表, 错误信息)
        """
        if not PYMUPDF_AVAILABLE:
            return False, [], "PyMuPDF未安装"

        # 在线程池中执行CPU密集型操作
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._generate_thumbnails_sync,
            pdf_path,
            output_dir,
            doc_id
        )

    def _generate_thumbnails_sync(
        self,
        pdf_path: Path,
        output_dir: Path,
        doc_id: str
    ) -> Tuple[bool, List[str], Optional[str]]:
        """同步方式生成缩略图"""
        try:
            # 确保输出目录存在
            output_dir.mkdir(parents=True, exist_ok=True)

            # 打开PDF文件
            doc = fitz.open(str(pdf_path))
            thumbnail_paths = []

            for page_num in range(len(doc)):
                page = doc.load_page(page_num)

                # 计算缩放比例以保持宽度一致
                zoom = self.width / page.rect.width
                matrix = fitz.Matrix(zoom, zoom)

                # 渲染页面为图像
                pix = page.get_pixmap(matrix=matrix)

                # 生成输出文件名
                output_filename = f"{doc_id}_page{page_num + 1}.{self.format}"
                output_path = output_dir / output_filename

                # 保存图像
                if self.format == 'webp':
                    # PyMuPDF支持直接输出webp
                    pix.save(str(output_path))
                else:
                    pix.save(str(output_path))

                thumbnail_paths.append(str(output_path))
                logger.info(f"生成缩略图: {output_path}")

            doc.close()

            return True, thumbnail_paths, None

        except Exception as e:
            error_msg = f"生成缩略图失败: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg

    def get_page_count(self, pdf_path: Path) -> int:
        """获取PDF页数"""
        if not PYMUPDF_AVAILABLE:
            return 0

        try:
            doc = fitz.open(str(pdf_path))
            count = len(doc)
            doc.close()
            return count
        except Exception:
            return 0


# 创建全局缩略图服务实例
thumbnail_service = ThumbnailService()
