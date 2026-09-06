# 项目 Python 启动脚本（编辑器启用 PythonScriptPlugin 时执行）
# 注册自研 Toolset（BasicSpawnTools / WorldIOTools）到引擎 ToolsetRegistry：
# —— @tool_call 方法会成为 MCP 可发现工具。
import unreal  # noqa: F401

from toolset_registry.registration import Registration
from basic_spawn.basic_spawn_tools import BasicSpawnTools
from worldio.world_io_tools import WorldIOTools

_registration = Registration([BasicSpawnTools, WorldIOTools])


def register() -> None:
    _registration.register()


register()
