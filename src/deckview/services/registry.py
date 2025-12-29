"""
ServiceAtlas 服务注册模块
自动将 DeckView 注册到 ServiceAtlas 注册中心
"""
import asyncio
import logging
from typing import Optional, Dict, Any

import httpx

logger = logging.getLogger(__name__)


class ServiceAtlasClient:
    """
    ServiceAtlas 异步注册客户端
    支持自动注册、心跳维护、优雅注销
    """

    def __init__(
        self,
        registry_url: str,
        service_id: str,
        service_name: str,
        host: str,
        port: int,
        protocol: str = "http",
        health_check_path: str = "/health",
        is_gateway: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        heartbeat_interval: int = 30,
    ):
        self.registry_url = registry_url.rstrip("/")
        self.service_id = service_id
        self.service_name = service_name
        self.host = host
        self.port = port
        self.protocol = protocol
        self.health_check_path = health_check_path
        self.is_gateway = is_gateway
        self.metadata = metadata or {}
        self.heartbeat_interval = heartbeat_interval

        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def start(self) -> bool:
        """启动客户端：注册服务并开始心跳"""
        if self._running:
            return True

        # 注册服务
        if not await self._register():
            logger.warning(f"[ServiceAtlas] 注册失败，服务将以离线模式运行")
            return False

        # 启动心跳任务
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        logger.info(f"[ServiceAtlas] 服务 '{self.service_id}' 已注册到 {self.registry_url}")
        return True

    async def stop(self):
        """停止客户端：停止心跳并注销服务"""
        if not self._running:
            return

        self._running = False

        # 取消心跳任务
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # 注销服务
        await self._unregister()
        logger.info(f"[ServiceAtlas] 服务 '{self.service_id}' 已注销")

    async def _register(self) -> bool:
        """注册服务到 ServiceAtlas"""
        try:
            # trust_env=False 禁用从环境变量读取代理配置
            async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                response = await client.post(
                    f"{self.registry_url}/api/v1/services",
                    json={
                        "id": self.service_id,
                        "name": self.service_name,
                        "host": self.host,
                        "port": self.port,
                        "protocol": self.protocol,
                        "health_check_path": self.health_check_path,
                        "is_gateway": self.is_gateway,
                        "service_meta": self.metadata,
                    }
                )
                if response.status_code in (200, 201):
                    return True
                else:
                    logger.warning(f"[ServiceAtlas] 注册返回状态码: {response.status_code}, 响应: {response.text}")
                    return False
        except Exception as e:
            logger.warning(f"[ServiceAtlas] 注册异常: {type(e).__name__}: {e}")
            return False

    async def _unregister(self):
        """从 ServiceAtlas 注销服务"""
        try:
            async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
                await client.delete(
                    f"{self.registry_url}/api/v1/services/{self.service_id}"
                )
        except Exception:
            pass

    async def _heartbeat_loop(self):
        """心跳循环"""
        while self._running:
            try:
                async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
                    await client.post(
                        f"{self.registry_url}/api/v1/services/{self.service_id}/heartbeat"
                    )
            except Exception:
                pass
            await asyncio.sleep(self.heartbeat_interval)


# 全局客户端实例
_registry_client: Optional[ServiceAtlasClient] = None


def get_registry_client() -> Optional[ServiceAtlasClient]:
    """获取注册客户端实例"""
    return _registry_client


async def init_registry(
    registry_url: str,
    service_id: str,
    service_name: str,
    host: str,
    port: int,
    **kwargs
) -> bool:
    """
    初始化并启动服务注册

    Args:
        registry_url: ServiceAtlas 注册中心地址
        service_id: 服务唯一标识
        service_name: 服务显示名称
        host: 服务地址
        port: 服务端口
        **kwargs: 其他配置参数

    Returns:
        注册是否成功
    """
    global _registry_client

    _registry_client = ServiceAtlasClient(
        registry_url=registry_url,
        service_id=service_id,
        service_name=service_name,
        host=host,
        port=port,
        **kwargs
    )

    return await _registry_client.start()


async def shutdown_registry():
    """关闭服务注册"""
    global _registry_client

    if _registry_client:
        await _registry_client.stop()
        _registry_client = None
