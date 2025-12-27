"""
应用配置模块
定义所有配置项，支持环境变量覆盖
"""
import os
from pathlib import Path
from typing import Optional, Set, List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置类"""

    # 应用基本信息
    APP_NAME: str = "DeckView"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = True

    # 服务器配置
    HOST: str = "127.0.0.1"  # 默认只监听本地，安全考虑
    PORT: int = 8000

    # 内容目录（核心配置：指定要扫描的文档目录）
    CONTENT_DIR: Optional[Path] = None

    # 项目路径配置
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    CONVERTED_DIR: Path = DATA_DIR / "converted"
    THUMBNAIL_DIR: Path = DATA_DIR / "thumbnails"
    CACHE_DIR: Path = DATA_DIR / "cache"

    # 支持的文件扩展名
    ALLOWED_EXTENSIONS: Set[str] = {"pptx", "ppt", "pdf", "md", "markdown", "docx", "doc"}

    # 忽略的目录名（不扫描这些目录）
    IGNORE_DIRS: Set[str] = {
        ".git", ".svn", ".hg",
        "node_modules", "venv", ".venv", "env", ".env",
        "__pycache__", ".pytest_cache", ".mypy_cache",
        ".idea", ".vscode",
        "data", "dist", "build"
    }

    # LibreOffice配置（用于PPT/Word转PDF）
    LIBREOFFICE_PATH: str = "soffice"  # LibreOffice命令行工具路径
    CONVERSION_TIMEOUT: int = 120  # 转换超时时间（秒）

    # 缩略图配置
    THUMBNAIL_WIDTH: int = 200
    THUMBNAIL_FORMAT: str = "png"

    class Config:
        env_file = ".env"
        case_sensitive = True


# 创建全局配置实例
settings = Settings()


def set_content_dir(path: Path):
    """设置内容目录（由CLI调用）"""
    global settings
    settings.CONTENT_DIR = path.resolve()


def ensure_directories():
    """确保必要的目录存在"""
    for dir_path in [settings.CONVERTED_DIR, settings.THUMBNAIL_DIR, settings.CACHE_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)
