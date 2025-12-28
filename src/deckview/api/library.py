"""
文件库API路由
处理目录树、文件访问等请求
"""
import asyncio
import re
import hashlib
from pathlib import Path
from typing import Optional
import aiofiles
from fastapi import APIRouter, HTTPException, Query, Request, UploadFile, File, Form
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


def _validate_file_extension(filename: str) -> str:
    """
    验证文件扩展名是否允许

    Args:
        filename: 文件名

    Returns:
        扩展名（不含点）

    Raises:
        HTTPException: 如果扩展名不允许
    """
    ext = Path(filename).suffix.lower().lstrip('.')
    if ext not in settings.ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(settings.ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型 '.{ext}'。支持的类型：{allowed}"
        )
    return ext


def _validate_target_dir(target_dir: str) -> Path:
    """
    验证目标目录安全性

    - 禁止 .. 路径遍历
    - 禁止绝对路径
    - 确保目标在 CONTENT_DIR 内

    Args:
        target_dir: 目标目录的相对路径

    Returns:
        验证后的完整路径

    Raises:
        HTTPException: 如果路径不安全或目录不存在
    """
    content_dir = settings.CONTENT_DIR

    # 清理和规范化路径
    target_dir = target_dir.strip().strip('/')

    # 检查危险模式
    if '..' in target_dir or target_dir.startswith('/'):
        raise HTTPException(status_code=400, detail="非法的目录路径")

    # 构建完整路径并验证
    if target_dir:
        full_path = (content_dir / target_dir).resolve()
    else:
        full_path = content_dir.resolve()

    # 确保在 CONTENT_DIR 内（防止符号链接逃逸）
    try:
        full_path.relative_to(content_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="目标目录不在允许范围内")

    # 检查目录是否存在
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="目标目录不存在")

    if not full_path.is_dir():
        raise HTTPException(status_code=400, detail="目标路径不是目录")

    return full_path


def _get_unique_filename(directory: Path, filename: str) -> str:
    """
    获取唯一的文件名

    如果文件已存在，添加数字后缀：file(1).pdf, file(2).pdf...

    Args:
        directory: 目标目录
        filename: 原始文件名

    Returns:
        唯一的文件名
    """
    target_path = directory / filename
    if not target_path.exists():
        return filename

    # 分离文件名和扩展名
    stem = Path(filename).stem
    suffix = Path(filename).suffix

    # 检查是否已有数字后缀，如 file(1)
    match = re.match(r'^(.+)\((\d+)\)$', stem)
    if match:
        base_name = match.group(1)
        start_num = int(match.group(2)) + 1
    else:
        base_name = stem
        start_num = 1

    # 循环查找可用的文件名
    counter = start_num
    while counter < 1000:  # 防止无限循环
        new_filename = f"{base_name}({counter}){suffix}"
        if not (directory / new_filename).exists():
            return new_filename
        counter += 1

    raise HTTPException(status_code=500, detail="无法生成唯一文件名")


def _generate_file_id(rel_path: str) -> str:
    """根据相对路径生成文件ID"""
    return hashlib.sha256(rel_path.encode('utf-8')).hexdigest()[:16]


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(..., description="要上传的文件"),
    target_dir: str = Form("", description="目标目录（相对路径，默认为根目录）")
):
    """
    上传文件到指定目录

    - 仅支持文档类型：.pdf, .pptx, .ppt, .docx, .doc, .md, .markdown
    - 文件名冲突时自动重命名（添加数字后缀）
    - 返回上传结果和新文件信息
    """
    # 1. 验证内容目录已配置
    if not settings.CONTENT_DIR:
        raise HTTPException(status_code=500, detail="内容目录未配置")

    # 2. 验证文件名存在
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    # 3. 验证文件扩展名
    _validate_file_extension(file.filename)

    # 4. 验证目标目录
    target_path = _validate_target_dir(target_dir)

    # 5. 获取唯一文件名
    safe_filename = _get_unique_filename(target_path, file.filename)

    # 6. 保存文件
    file_path = target_path / safe_filename
    try:
        async with aiofiles.open(file_path, 'wb') as f:
            # 分块读取，避免大文件内存溢出（1MB chunks）
            while chunk := await file.read(1024 * 1024):
                await f.write(chunk)
    except PermissionError:
        raise HTTPException(status_code=403, detail="没有写入权限")
    except Exception as e:
        # 清理可能创建的不完整文件
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"保存文件失败: {str(e)}")

    # 7. 触发目录刷新
    library_service.invalidate_cache()

    # 8. 获取新文件信息
    rel_path = file_path.relative_to(settings.CONTENT_DIR)
    file_id = _generate_file_id(str(rel_path))

    return {
        "status": "success",
        "message": "文件上传成功",
        "file": {
            "id": file_id,
            "name": safe_filename,
            "path": str(rel_path),
            "original_name": file.filename,
            "renamed": safe_filename != file.filename
        }
    }


def _validate_filename(filename: str) -> str:
    """
    验证并清理文件名

    - 去除首尾空格
    - 检查是否为空
    - 检查是否包含非法字符
    - 返回清理后的文件名（不含扩展名）
    """
    # 去除首尾空格
    filename = filename.strip()

    # 检查是否为空
    if not filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    # 非法字符列表
    invalid_chars = '/\\:*?"<>|'
    for char in invalid_chars:
        if char in filename:
            raise HTTPException(
                status_code=400,
                detail=f"文件名不能包含以下字符: {invalid_chars}"
            )

    # 如果用户输入了 .md 扩展名，去掉它（后面会统一添加）
    if filename.lower().endswith('.md'):
        filename = filename[:-3]
    elif filename.lower().endswith('.markdown'):
        filename = filename[:-9]

    # 再次检查去除扩展名后是否为空
    if not filename.strip():
        raise HTTPException(status_code=400, detail="文件名不能为空")

    return filename


@router.post("/create")
async def create_file(
    filename: str = Form(..., description="文件名（可不含扩展名，自动添加 .md）"),
    target_dir: str = Form("", description="目标目录（相对路径，默认为根目录）")
):
    """
    创建新的 Markdown 文件

    - 自动添加 .md 扩展名
    - 文件名冲突时自动重命名（添加数字后缀）
    - 返回新文件信息，包含 file_id 用于前端跳转
    """
    # 1. 验证内容目录已配置
    if not settings.CONTENT_DIR:
        raise HTTPException(status_code=500, detail="内容目录未配置")

    # 2. 验证并清理文件名
    clean_name = _validate_filename(filename)

    # 3. 添加 .md 扩展名
    full_filename = f"{clean_name}.md"

    # 4. 验证目标目录
    target_path = _validate_target_dir(target_dir)

    # 5. 获取唯一文件名（处理同名冲突）
    safe_filename = _get_unique_filename(target_path, full_filename)

    # 6. 创建文件，写入默认模板
    file_path = target_path / safe_filename
    # 使用文件名（不含扩展名）作为默认标题
    title = safe_filename[:-3] if safe_filename.endswith('.md') else safe_filename
    default_content = f"# {title}\n\n"

    try:
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(default_content)
    except PermissionError:
        raise HTTPException(status_code=403, detail="没有写入权限")
    except Exception as e:
        # 清理可能创建的不完整文件
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"创建文件失败: {str(e)}")

    # 7. 触发目录刷新
    library_service.invalidate_cache()

    # 8. 获取新文件信息
    rel_path = file_path.relative_to(settings.CONTENT_DIR)
    file_id = _generate_file_id(str(rel_path))

    return {
        "status": "success",
        "message": "文件创建成功",
        "file": {
            "id": file_id,
            "name": safe_filename,
            "path": str(rel_path),
            "original_name": full_filename,
            "renamed": safe_filename != full_filename
        }
    }


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
