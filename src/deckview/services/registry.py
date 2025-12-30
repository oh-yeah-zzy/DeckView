"""
ServiceAtlas 服务注册模块
优先使用 ServiceAtlas SDK，若未安装则使用内置实现
"""
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# 尝试导入 SDK
try:
    from serviceatlas_client import AsyncServiceAtlasClient
    SDK_AVAILABLE = True
    logger.debug("[ServiceAtlas] 使用 ServiceAtlas SDK")
except ImportError:
    SDK_AVAILABLE = False
    logger.debug("[ServiceAtlas] SDK 未安装，使用内置实现")


# ================== 内置实现（SDK 不可用时使用）==================
if not SDK_AVAILABLE:
    import asyncio
    import httpx

    class AsyncServiceAtlasClient:
        """
        内置的 ServiceAtlas 异步注册客户端
        仅在 SDK 未安装时使用
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
            base_path: str = "",
            metadata: Optional[Dict[str, Any]] = None,
            heartbeat_interval: int = 30,
            trust_env: bool = True,
        ):
            self.registry_url = registry_url.rstrip("/")
            self.service_id = service_id
            self.service_name = service_name
            self.host = host
            self.port = port
            self.protocol = protocol
            self.health_check_path = health_check_path
            self.is_gateway = is_gateway
            self.base_path = base_path
            self.metadata = metadata or {}
            self.heartbeat_interval = heartbeat_interval
            self.trust_env = trust_env

            self._running = False
            self._heartbeat_task: Optional[asyncio.Task] = None

        async def start(self) -> bool:
            """启动客户端：注册服务并开始心跳"""
            if self._running:
                return True

            if not await self._register():
                logger.warning("[ServiceAtlas] 注册失败，服务将以离线模式运行")
                return False

            self._running = True
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info(f"[ServiceAtlas] 服务 '{self.service_id}' 已注册到 {self.registry_url}")
            return True

        async def stop(self):
            """停止客户端：停止心跳并注销服务"""
            if not self._running:
                return

            self._running = False

            if self._heartbeat_task:
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except asyncio.CancelledError:
                    pass

            await self._unregister()
            logger.info(f"[ServiceAtlas] 服务 '{self.service_id}' 已注销")

        async def _register(self) -> bool:
            """注册服务到 ServiceAtlas"""
            try:
                register_data = {
                    "id": self.service_id,
                    "name": self.service_name,
                    "host": self.host,
                    "port": self.port,
                    "protocol": self.protocol,
                    "health_check_path": self.health_check_path,
                    "is_gateway": self.is_gateway,
                    "service_meta": self.metadata,
                }
                if self.base_path:
                    register_data["base_path"] = self.base_path

                async with httpx.AsyncClient(timeout=10, trust_env=self.trust_env) as client:
                    response = await client.post(
                        f"{self.registry_url}/api/v1/services",
                        json=register_data
                    )
                    if response.status_code in (200, 201):
                        return True
                    else:
                        logger.warning(f"[ServiceAtlas] 注册返回: {response.status_code}")
                        return False
            except Exception as e:
                logger.warning(f"[ServiceAtlas] 注册异常: {type(e).__name__}: {e}")
                return False

        async def _unregister(self):
            """从 ServiceAtlas 注销服务"""
            try:
                async with httpx.AsyncClient(timeout=5, trust_env=self.trust_env) as client:
                    await client.delete(
                        f"{self.registry_url}/api/v1/services/{self.service_id}"
                    )
            except Exception:
                pass

        async def _heartbeat_loop(self):
            """心跳循环"""
            while self._running:
                try:
                    async with httpx.AsyncClient(timeout=5, trust_env=self.trust_env) as client:
                        await client.post(
                            f"{self.registry_url}/api/v1/services/{self.service_id}/heartbeat"
                        )
                except Exception:
                    pass
                await asyncio.sleep(self.heartbeat_interval)


# ================== 全局客户端管理 ==================

_registry_client: Optional[AsyncServiceAtlasClient] = None


def get_registry_client() -> Optional[AsyncServiceAtlasClient]:
    """获取注册客户端实例"""
    return _registry_client


async def init_registry(
    registry_url: str,
    service_id: str,
    service_name: str,
    host: str,
    port: int,
    protocol: str = "http",
    health_check_path: str = "/health",
    is_gateway: bool = False,
    base_path: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    heartbeat_interval: int = 30,
    trust_env: bool = False,  # 默认禁用代理，避免环境变量干扰
) -> bool:
    """
    初始化并启动服务注册

    Args:
        registry_url: ServiceAtlas 注册中心地址
        service_id: 服务唯一标识
        service_name: 服务显示名称
        host: 服务地址
        port: 服务端口
        protocol: 协议（http/https）
        health_check_path: 健康检查路径
        is_gateway: 是否作为网关服务
        base_path: 代理路径前缀（通过网关代理时设置）
        metadata: 扩展元数据
        heartbeat_interval: 心跳间隔（秒）
        trust_env: 是否信任环境变量中的代理配置

    Returns:
        注册是否成功
    """
    global _registry_client

    _registry_client = AsyncServiceAtlasClient(
        registry_url=registry_url,
        service_id=service_id,
        service_name=service_name,
        host=host,
        port=port,
        protocol=protocol,
        health_check_path=health_check_path,
        is_gateway=is_gateway,
        base_path=base_path,
        metadata=metadata,
        heartbeat_interval=heartbeat_interval,
        trust_env=trust_env,
    )

    return await _registry_client.start()


async def shutdown_registry():
    """关闭服务注册"""
    global _registry_client

    if _registry_client:
        await _registry_client.stop()
        _registry_client = None
