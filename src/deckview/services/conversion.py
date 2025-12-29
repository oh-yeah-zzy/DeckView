"""
文档转换服务
处理PPT/Word到PDF的转换
"""
import subprocess
import asyncio
from pathlib import Path
from typing import Optional, Tuple
import logging

from ..core.config import settings

logger = logging.getLogger(__name__)

# LibreOffice高质量PDF导出配置模板
# 使用无损压缩、不降低图像分辨率，保持最高质量
LO_PDF_CONFIG_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry"
           xmlns:xs="http://www.w3.org/2001/XMLSchema"
           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Common/Filter/PDF/Export">
  <prop oor:name="UseLosslessCompression" oor:op="fuse"><value>true</value></prop>
  <prop oor:name="ReduceImageResolution" oor:op="fuse"><value>false</value></prop>
  <prop oor:name="Quality" oor:op="fuse"><value>100</value></prop>
  <prop oor:name="MaxImageResolution" oor:op="fuse"><value>1200</value></prop>
</item>
</oor:items>
'''


class ConversionService:
    """文档转换服务类"""

    def __init__(self):
        """初始化转换服务"""
        self.libreoffice_path = settings.LIBREOFFICE_PATH
        self.timeout = settings.CONVERSION_TIMEOUT
        self.profile_dir = settings.LO_PROFILE_DIR
        # 初始化时确保高质量PDF配置已创建
        self._ensure_hq_pdf_config()

    def _ensure_hq_pdf_config(self):
        """
        确保LibreOffice高质量PDF导出配置文件存在

        创建一个专用的LibreOffice用户配置目录，包含高质量PDF导出设置：
        - UseLosslessCompression=true: 使用无损压缩（PNG格式）
        - ReduceImageResolution=false: 不降低图像分辨率
        - Quality=100: 最高质量
        - MaxImageResolution=1200: 最大分辨率1200 DPI
        """
        try:
            # 确保profile目录存在
            self.profile_dir.mkdir(parents=True, exist_ok=True)

            # 创建user目录结构
            user_dir = self.profile_dir / "user"
            user_dir.mkdir(exist_ok=True)

            # 写入配置文件
            config_file = user_dir / "registrymodifications.xcu"

            # 只在配置文件不存在时创建，避免覆盖用户自定义配置
            if not config_file.exists():
                config_file.write_text(LO_PDF_CONFIG_TEMPLATE, encoding='utf-8')
                logger.info(f"已创建LibreOffice高质量PDF导出配置: {config_file}")

        except Exception as e:
            logger.warning(f"创建LibreOffice配置失败（将使用默认配置）: {e}")

    def _get_profile_uri(self) -> str:
        """获取LibreOffice profile目录的URI格式路径"""
        return self.profile_dir.resolve().as_uri()

    async def _convert_to_pdf(self, input_path: Path, output_dir: Path, doc_type: str) -> Tuple[bool, Optional[Path], Optional[str]]:
        """
        将文档转换为PDF的通用方法

        使用LibreOffice headless模式进行转换，支持 PPTX、DOC、DOCX 等格式

        Args:
            input_path: 输入文件路径
            output_dir: 输出目录
            doc_type: 文档类型（用于日志）

        Returns:
            Tuple[bool, Optional[Path], Optional[str]]: (是否成功, PDF路径, 错误信息)
        """
        try:
            # 构建LibreOffice命令
            # --headless: 无界面模式
            # --convert-to pdf: 转换为PDF格式
            # --outdir: 指定输出目录
            # -env:UserInstallation: 使用自定义profile（包含高质量PDF导出配置）
            profile_uri = self._get_profile_uri()
            cmd = [
                self.libreoffice_path,
                '--headless',
                '--invisible',
                '--nologo',
                '--nofirststartwizard',
                f'-env:UserInstallation={profile_uri}',
                '--convert-to', 'pdf',
                '--outdir', str(output_dir),
                str(input_path)
            ]

            logger.info(f"执行{doc_type}转换命令: {' '.join(cmd)}")

            # 异步执行命令
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return False, None, f"转换超时（超过{self.timeout}秒）"

            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore')
                logger.error(f"{doc_type}转换失败: {error_msg}")
                return False, None, f"转换失败: {error_msg}"

            # 查找生成的PDF文件
            # LibreOffice会将输出文件名改为与输入文件同名，扩展名为.pdf
            pdf_filename = input_path.stem + '.pdf'
            pdf_path = output_dir / pdf_filename

            if pdf_path.exists():
                logger.info(f"{doc_type}转换成功: {pdf_path}")
                return True, pdf_path, None
            else:
                return False, None, "PDF文件未生成"

        except FileNotFoundError:
            error_msg = f"LibreOffice未找到，请确保已安装并配置路径: {self.libreoffice_path}"
            logger.error(error_msg)
            return False, None, error_msg
        except Exception as e:
            error_msg = f"转换过程中发生错误: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

    async def convert_pptx_to_pdf(self, input_path: Path, output_dir: Path) -> Tuple[bool, Optional[Path], Optional[str]]:
        """
        将PPTX文件转换为PDF

        Args:
            input_path: 输入的PPTX文件路径
            output_dir: 输出目录

        Returns:
            Tuple[bool, Optional[Path], Optional[str]]: (是否成功, PDF路径, 错误信息)
        """
        return await self._convert_to_pdf(input_path, output_dir, "PPTX")

    async def convert_docx_to_pdf(self, input_path: Path, output_dir: Path) -> Tuple[bool, Optional[Path], Optional[str]]:
        """
        将DOCX/DOC文件转换为PDF

        Args:
            input_path: 输入的Word文件路径
            output_dir: 输出目录

        Returns:
            Tuple[bool, Optional[Path], Optional[str]]: (是否成功, PDF路径, 错误信息)
        """
        return await self._convert_to_pdf(input_path, output_dir, "DOCX")

    def check_libreoffice_installed(self) -> bool:
        """检查LibreOffice是否已安装"""
        try:
            result = subprocess.run(
                [self.libreoffice_path, '--version'],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False


# 创建全局转换服务实例
conversion_service = ConversionService()
