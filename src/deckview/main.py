"""
DeckView - Web文档查看器
FastAPI主应用入口
"""
import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from .core.config import settings, ensure_directories
from .api.library import router as library_router

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # === ServiceAtlas 服务注册 ===
    if settings.REGISTRY_ENABLED:
        from .services.registry import init_registry
        await init_registry(
            registry_url=settings.REGISTRY_URL,
            service_id=settings.SERVICE_ID,
            service_name=f"{settings.APP_NAME} 文档预览服务",
            host=settings.HOST,
            port=settings.PORT,
            health_check_path="/health",
            metadata={
                "version": settings.APP_VERSION,
                "description": "在线预览 PPT、PDF、Word、Markdown 文件"
            },
            heartbeat_interval=settings.HEARTBEAT_INTERVAL,
        )

    if settings.CONTENT_DIR:
        logger.info(f"Content directory: {settings.CONTENT_DIR}")

        # 启动时清理孤立缓存（源文件已删除的缓存）
        from .services.library import library_service
        from .services.cache_manager import cache_manager

        # 扫描目录获取当前有效的文件列表
        library_service.scan(force=True, clean_orphans=False)
        valid_file_ids = set(library_service._index.keys())

        # 清理孤立缓存
        orphan_count = cache_manager.clear_orphan_caches(valid_file_ids)
        if orphan_count > 0:
            logger.info(f"启动时清理了 {orphan_count} 个孤立缓存")

        # 检查是否启用文件监听
        watch_enabled = os.environ.get("DECKVIEW_WATCH", "1") == "1"
        if watch_enabled:
            from .services.watcher import watcher_service
            if watcher_service.is_available():
                watcher_service.start(
                    settings.CONTENT_DIR,
                    settings.ALLOWED_EXTENSIONS,
                    settings.IGNORE_DIRS
                )
            else:
                logger.warning("watchdog未安装，文件监听功能已禁用")
    else:
        logger.warning("未设置内容目录，请使用CLI指定目录启动")

    logger.info(f"Data directory: {settings.DATA_DIR}")

    yield

    # 关闭时
    logger.info("Shutting down...")

    # === ServiceAtlas 服务注销 ===
    if settings.REGISTRY_ENABLED:
        from .services.registry import shutdown_registry
        await shutdown_registry()

    from .services.watcher import watcher_service
    watcher_service.stop()


# 确保必要的目录存在
ensure_directories()

# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Web端文档查看器，支持PPT、PDF和Markdown文件的在线预览。指定目录启动，自动扫描并展示文档。",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# 配置CORS（允许跨域请求）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册API路由
app.include_router(library_router)

# 设置静态文件和模板目录（基于包内 web 目录）
web_dir = Path(__file__).parent / "web"
static_dir = web_dir / "static"
templates_dir = web_dir / "templates"

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 创建模板引擎
templates = Jinja2Templates(directory=str(templates_dir))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页 - 目录树导航页面"""
    content_dir_name = settings.CONTENT_DIR.name if settings.CONTENT_DIR else "未配置"
    return templates.TemplateResponse("index.html", {
        "request": request,
        "content_dir": content_dir_name
    })


@app.get("/view/{file_id}", response_class=HTMLResponse)
async def view_document(request: Request, file_id: str):
    """文档查看页面"""
    return templates.TemplateResponse("viewer.html", {
        "request": request,
        "doc_id": file_id
    })


@app.get("/health")
async def health_check():
    """健康检查接口"""
    from .services.conversion import conversion_service
    from .services.thumbnail import thumbnail_service
    from .services.watcher import watcher_service
    from .services.library import library_service

    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "content_dir": str(settings.CONTENT_DIR) if settings.CONTENT_DIR else None,
        "libreoffice_available": conversion_service.check_libreoffice_installed(),
        "pymupdf_available": thumbnail_service.is_available(),
        "watcher_available": watcher_service.is_available(),
        "watcher_running": watcher_service.is_running,
        "file_stats": library_service.get_stats() if settings.CONTENT_DIR else None
    }
