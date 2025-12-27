"""
文件监听服务
使用watchdog监听文件变化，并通过SSE推送更新
"""
import asyncio
import logging
import os
import threading
from pathlib import Path
from typing import Set, Callable, Optional
from queue import Queue, Empty

logger = logging.getLogger(__name__)

# 尝试导入watchdog
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logger.warning("watchdog未安装，文件监听功能将不可用。安装: pip install watchdog")


class FileChangeHandler(FileSystemEventHandler if WATCHDOG_AVAILABLE else object):
    """文件变化处理器"""

    def __init__(self, allowed_extensions: Set[str], ignore_dirs: Set[str]):
        self.allowed_extensions = allowed_extensions
        self.ignore_dirs = ignore_dirs
        self.change_queue: Queue = Queue()
        self._debounce_timer: Optional[threading.Timer] = None
        self._debounce_delay = 0.5  # 500ms防抖

    def _should_ignore(self, path: str) -> bool:
        """检查路径是否应该忽略"""
        path_parts = Path(path).parts
        for part in path_parts:
            if part in self.ignore_dirs or part.startswith('.'):
                return True
        return False

    def _is_allowed_file(self, path: str) -> bool:
        """检查是否是允许的文件类型"""
        ext = Path(path).suffix.lower().lstrip('.')
        return ext in self.allowed_extensions

    def _notify_change(self):
        """通知变化（防抖后调用）"""
        self.change_queue.put("changed")

    def _schedule_notify(self):
        """调度通知（防抖）"""
        if self._debounce_timer:
            self._debounce_timer.cancel()
        self._debounce_timer = threading.Timer(self._debounce_delay, self._notify_change)
        self._debounce_timer.start()

    def on_any_event(self, event: 'FileSystemEvent'):
        """处理任何文件事件"""
        # 只响应真正的文件变化事件：创建、删除、修改、移动
        # 忽略其他事件类型（如 opened、closed、accessed 等）
        if event.event_type not in ('created', 'deleted', 'modified', 'moved'):
            return

        # 忽略目录事件（除了创建/删除/移动）
        if event.is_directory:
            if not self._should_ignore(event.src_path):
                self._schedule_notify()
            return

        # 检查是否应该忽略
        if self._should_ignore(event.src_path):
            return

        # 检查文件类型
        if not self._is_allowed_file(event.src_path):
            # 对于移动事件，也检查目标路径
            if hasattr(event, 'dest_path') and event.dest_path:
                if not self._is_allowed_file(event.dest_path):
                    return
            else:
                return

        logger.debug(f"文件变化: {event.event_type} - {event.src_path}")
        self._schedule_notify()


class WatcherService:
    """文件监听服务"""

    def __init__(self):
        self._observer: Optional['Observer'] = None
        self._handler: Optional[FileChangeHandler] = None
        self._running = False
        self._subscribers: Set[asyncio.Queue] = set()
        self._notify_thread: Optional[threading.Thread] = None

    def is_available(self) -> bool:
        """检查服务是否可用"""
        return WATCHDOG_AVAILABLE

    def start(self, content_dir: Path, allowed_extensions: Set[str], ignore_dirs: Set[str]):
        """
        启动文件监听

        Args:
            content_dir: 要监听的目录
            allowed_extensions: 允许的文件扩展名
            ignore_dirs: 忽略的目录名
        """
        if not WATCHDOG_AVAILABLE:
            logger.warning("watchdog未安装，无法启动文件监听")
            return

        if self._running:
            logger.warning("文件监听已在运行")
            return

        self._handler = FileChangeHandler(allowed_extensions, ignore_dirs)
        self._observer = Observer()
        self._observer.schedule(self._handler, str(content_dir), recursive=True)

        try:
            self._observer.start()
            self._running = True
            logger.info(f"文件监听已启动: {content_dir}")

            # 启动通知线程
            self._notify_thread = threading.Thread(target=self._notify_loop, daemon=True)
            self._notify_thread.start()

        except Exception as e:
            logger.error(f"启动文件监听失败: {e}")
            self._running = False

    def stop(self):
        """停止文件监听"""
        if self._observer and self._running:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._running = False
            logger.info("文件监听已停止")

    def _notify_loop(self):
        """通知循环（在单独线程中运行）"""
        while self._running:
            try:
                # 等待变化通知
                self._handler.change_queue.get(timeout=1)

                # 通知所有订阅者
                for queue in list(self._subscribers):
                    try:
                        # 使用线程安全的方式添加到异步队列
                        queue.put_nowait("tree_changed")
                    except Exception:
                        pass

            except Empty:
                continue
            except Exception as e:
                logger.error(f"通知循环错误: {e}")

    def subscribe(self) -> asyncio.Queue:
        """
        订阅文件变化事件

        Returns:
            asyncio.Queue: 事件队列
        """
        queue = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """取消订阅"""
        self._subscribers.discard(queue)

    @property
    def is_running(self) -> bool:
        return self._running


# 创建全局服务实例
watcher_service = WatcherService()
