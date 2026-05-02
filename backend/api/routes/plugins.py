"""Plugins API routes — list and install plugins."""

from fastapi import APIRouter

from backend.api.schemas import PluginInstallRequest
from backend.plugins.registry import get_registry

router = APIRouter()


@router.get(
    "/",
    summary="List available plugins",
    description="Return all registered plugins with name, version, description, and enabled status.",
)
async def list_plugins():
    """List all registered plugins.

    Returns:
        {"plugins": [...], "total": N}
    """
    registry = get_registry()
    plugins = registry.list_plugins()
    return {"plugins": plugins, "total": len(plugins)}


@router.post(
    "/install",
    summary="Install a plugin",
    description="Register a new plugin or update an existing one.",
)
async def install_plugin(request: PluginInstallRequest):
    """Install (register) a plugin.

    Args:
        request: Plugin name, version, and description.

    Returns:
        The installed plugin dict.
    """
    registry = get_registry()
    plugin = registry.install(
        name=request.name,
        version=request.version,
        description=request.description,
    )
    return plugin
