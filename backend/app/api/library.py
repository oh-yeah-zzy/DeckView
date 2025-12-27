"""
文件库API路由
处理目录树、文件访问等请求
"""
import asyncio
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse

from ..core.config import settings
from ..schemas.document import DocumentType, ConversionStatus
from ..services.library import library_service
from ..services.watcher import watcher_service
from ..services.conversion import conversion_service
from ..services.thumbnail import thumbnail_service
from ..services.cache_manager import cache_manager

router = APIRouter(prefix="/api/library", tags=["library"])


@router.get("/tree")
async def get_tree(refresh: bool = Query(False, description="强制刷新")):
    """
    获取目录树

    返回内容目录下所有文档的树形结构
    """
    if not settings.CONTENT_DIR:
        raise HTTPException(status_code=500, detail="内容目录未配置")

    tree = library_service.get_tree(force_refresh=refresh)
    return tree


@router.get("/stats")
async def get_stats():
    """获取文件统计信息"""
    return library_service.get_stats()


@router.get("/files/{file_id}")
async def get_file_info(file_id: str):
    """
    获取文件详细信息

    包括文件元数据、处理状态、页数等
    """
    file_info = library_service.get_file(file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="文件不存在")

    # 基础信息
    result = file_info.to_dict()

    # 检查是否需要转换（PPTX 或 DOCX）
    if file_info.doc_type in (DocumentType.PPTX, DocumentType.DOCX):
        pdf_path = _get_converted_pdf_path(file_id)
        if pdf_path.exists():
            result["status"] = ConversionStatus.COMPLETED.value
            result["pdf_url"] = f"/api/library/files/{file_id}/pdf"
            # 获取页数
            page_count = thumbnail_service.get_page_count(pdf_path)
            result["page_count"] = page_count
        else:
            result["status"] = ConversionStatus.PENDING.value
            result["page_count"] = None

    elif file_info.doc_type == DocumentType.PDF:
        result["status"] = ConversionStatus.COMPLETED.value
        result["pdf_url"] = f"/api/library/files/{file_id}/pdf"
        page_count = thumbnail_service.get_page_count(file_info.abs_path)
        result["page_count"] = page_count

    else:  # Markdown
        result["status"] = ConversionStatus.COMPLETED.value
        result["page_count"] = None

    # 添加缩略图URL列表
    if result.get("page_count"):
        result["thumbnails"] = [
            {"page": i, "url": f"/api/library/files/{file_id}/thumbnails/{i}"}
            for i in range(1, result["page_count"] + 1)
        ]

    return result


@router.get("/files/{file_id}/pdf")
async def get_file_pdf(file_id: str):
    """
    获取文件的PDF版本

    - PDF文件：直接返回
    - PPTX文件：返回转换后的PDF（首次访问时自动转换）
    - DOCX文件：返回转换后的PDF（首次访问时自动转换）

    缓存策略：
    - 如果源文件被修改，自动清除旧缓存并重新转换
    """
    file_info = library_service.get_file(file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="文件不存在")

    if file_info.doc_type == DocumentType.MARKDOWN:
        raise HTTPException(status_code=400, detail="Markdown文件不支持PDF格式")

    # 确定PDF路径
    if file_info.doc_type == DocumentType.PDF:
        pdf_path = file_info.abs_path
    else:
        # PPTX 或 DOCX 需要转换
        pdf_path = _get_converted_pdf_path(file_id)

        # 检查缓存是否有效（源文件未被修改）
        need_convert = False
        if not pdf_path.exists():
            need_convert = True
        elif not cache_manager.is_cache_valid(file_id, file_info.mtime):
            # 源文件已修改，清除旧缓存
            cache_manager.clear_file_cache(file_id)
            need_convert = True

        if need_convert:
            # 根据文件类型选择转换方法
            if file_info.doc_type == DocumentType.PPTX:
                success, converted_path, error = await conversion_service.convert_pptx_to_pdf(
                    file_info.abs_path,
                    settings.CONVERTED_DIR
                )
            elif file_info.doc_type == DocumentType.DOCX:
                success, converted_path, error = await conversion_service.convert_docx_to_pdf(
                    file_info.abs_path,
                    settings.CONVERTED_DIR
                )
            else:
                raise HTTPException(status_code=400, detail="不支持的文件类型")

            if not success:
                raise HTTPException(status_code=500, detail=f"转换失败: {error}")

            # 重命名为标准路径
            if converted_path and converted_path != pdf_path:
                converted_path.rename(pdf_path)

    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF文件不存在")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"{file_info.name.rsplit('.', 1)[0]}.pdf",
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600"
        }
    )


@router.get("/files/{file_id}/thumbnails/{page}")
async def get_file_thumbnail(file_id: str, page: int):
    """获取指定页的缩略图"""
    file_info = library_service.get_file(file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="文件不存在")

    if file_info.doc_type == DocumentType.MARKDOWN:
        raise HTTPException(status_code=400, detail="Markdown文件不支持缩略图")

    # 确定PDF路径
    if file_info.doc_type == DocumentType.PDF:
        pdf_path = file_info.abs_path
    elif file_info.doc_type in (DocumentType.PPTX, DocumentType.DOCX):
        pdf_path = _get_converted_pdf_path(file_id)
        if not pdf_path.exists():
            raise HTTPException(status_code=400, detail="请先访问PDF接口进行转换")
    else:
        raise HTTPException(status_code=400, detail="不支持的文件类型")

    # 检查缩略图是否存在
    thumb_path = settings.THUMBNAIL_DIR / f"{file_id}_page{page}.{settings.THUMBNAIL_FORMAT}"

    if not thumb_path.exists():
        # 生成缩略图
        success, paths, error = await thumbnail_service.generate_thumbnails(
            pdf_path,
            settings.THUMBNAIL_DIR,
            file_id
        )
        if not success:
            raise HTTPException(status_code=500, detail=f"生成缩略图失败: {error}")

    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="缩略图不存在")

    media_type = "image/webp" if settings.THUMBNAIL_FORMAT == "webp" else f"image/{settings.THUMBNAIL_FORMAT}"

    return FileResponse(
        path=thumb_path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"}
    )


@router.get("/files/{file_id}/content")
async def get_file_content(file_id: str):
    """获取Markdown文件的原始内容"""
    file_info = library_service.get_file(file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="文件不存在")

    if file_info.doc_type != DocumentType.MARKDOWN:
        raise HTTPException(status_code=400, detail="只有Markdown文件支持获取内容")

    try:
        content = file_info.abs_path.read_text(encoding='utf-8')
        return Response(
            content=content,
            media_type="text/plain; charset=utf-8"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")


@router.put("/files/{file_id}/content")
async def update_file_content(file_id: str, request: Request):
    """
    更新Markdown文件的内容

    - 只允许修改 Markdown 类型的文件
    - 内容大小限制 10MB
    - UTF-8 编码
    """
    file_info = library_service.get_file(file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="文件不存在")

    if file_info.doc_type != DocumentType.MARKDOWN:
        raise HTTPException(status_code=400, detail="只有Markdown文件支持编辑")

    try:
        # 读取请求体内容
        content = await request.body()

        # 内容大小限制（10MB）
        max_size = 10 * 1024 * 1024
        if len(content) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"文件内容过大，最大支持 {max_size // 1024 // 1024}MB"
            )

        # 解码内容
        content_text = content.decode('utf-8')

        # 写入文件
        file_info.abs_path.write_text(content_text, encoding='utf-8')

        return {"status": "success", "message": "保存成功"}

    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="内容编码错误，请使用UTF-8编码")
    except PermissionError:
        raise HTTPException(status_code=403, detail="没有写入权限")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@router.get("/events")
async def file_events():
    """
    SSE端点：推送文件变化事件

    客户端可以通过EventSource连接此端点，接收文件变化通知
    """
    if not watcher_service.is_running:
        raise HTTPException(status_code=503, detail="文件监听服务未运行")

    async def event_generator():
        queue = watcher_service.subscribe()
        try:
            # 发送初始连接成功消息
            yield f"data: connected\n\n"

            while True:
                try:
                    # 等待事件（带超时，用于发送心跳）
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {event}\n\n"
                except asyncio.TimeoutError:
                    # 发送心跳
                    yield f": heartbeat\n\n"

        finally:
            watcher_service.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用nginx缓冲
        }
    )


def _get_converted_pdf_path(file_id: str) -> Path:
    """获取转换后PDF的路径"""
    return settings.CONVERTED_DIR / f"{file_id}.pdf"
