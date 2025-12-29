"""
应用配置模块
定义所有配置项，支持环境变量覆盖
"""
import os
from pathlib import Path
from typing import Optional, Set, List
from pydantic_settings import BaseSettings


def get_default_data_dir() -> Path:
    """获取默认数据目录（用户主目录下的 .deckview）"""
    # 优先使用环境变量
    if env_data_dir := os.environ.get("DECKVIEW_DATA_DIR"):
        return Path(env_data_dir)
    # 默认使用用户主目录
    return Path.home() / ".deckview"


def get_content_dir() -> Optional[Path]:
    """从环境变量获取内容目录"""
    if env_content_dir := os.environ.get("DECKVIEW_CONTENT_DIR"):
        return Path(env_content_dir)
    return None


def get_host() -> str:
    """从环境变量获取监听地址"""
    return os.environ.get("DECKVIEW_HOST", "127.0.0.1")


def get_port() -> int:
    """从环境变量获取监听端口"""
    return int(os.environ.get("DECKVIEW_PORT", "8000"))


class Settings(BaseSettings):
    """应用配置类"""

    # 应用基本信息
    APP_NAME: str = "DeckView"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = True

    # 服务器配置（从环境变量读取，支持 CLI 动态设置）
    HOST: str = get_host()
    PORT: int = get_port()

    # 内容目录（核心配置：指定要扫描的文档目录）
    # 通过环境变量 DECKVIEW_CONTENT_DIR 设置，支持 --reload 模式
    CONTENT_DIR: Optional[Path] = get_content_dir()

    # 数据目录配置（默认使用用户主目录下的 .deckview）
    DATA_DIR: Path = get_default_data_dir()
    CONVERTED_DIR: Path = DATA_DIR / "converted"
    THUMBNAIL_DIR: Path = DATA_DIR / "thumbnails"
    CACHE_DIR: Path = DATA_DIR / "cache"
    LO_PROFILE_DIR: Path = DATA_DIR / "lo_profile"  # LibreOffice高质量PDF导出配置目录

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
    THUMBNAIL_WIDTH: int = 600  # 提高缩略图分辨率以改善首页预览清晰度
    THUMBNAIL_FORMAT: str = "png"

    # ServiceAtlas 服务注册配置
    REGISTRY_ENABLED: bool = True  # 是否启用服务注册
    REGISTRY_URL: str = "http://127.0.0.1:9000"  # ServiceAtlas 注册中心地址
    SERVICE_ID: str = "deckview"  # 服务唯一标识
    HEARTBEAT_INTERVAL: int = 30  # 心跳间隔（秒）

    class Config:
        env_file = ".env"
        case_sensitive = True


# 创建全局配置实例
settings = Settings()


def set_content_dir(path: Path):
    """设置内容目录（由CLI调用）"""
    global settings
    # 同时设置环境变量，确保 --reload 模式下也能正确读取
    os.environ["DECKVIEW_CONTENT_DIR"] = str(path.resolve())
    settings.CONTENT_DIR = path.resolve()


def ensure_directories():
    """确保必要的目录存在"""
    for dir_path in [settings.CONVERTED_DIR, settings.THUMBNAIL_DIR, settings.CACHE_DIR, settings.LO_PROFILE_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)
