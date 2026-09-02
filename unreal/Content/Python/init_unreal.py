# 项目 Python 启动脚本（编辑器启用 PythonScriptPlugin 时执行）
# 注册自研 Toolset 到引擎 ToolsetRegistry，使 BasicSpawnTools 的 @tool_call 方法可被 MCP 发现。
import unreal  # noqa: F401

from toolset_registry.registration import Registration
from basic_spawn.basic_spawn_tools import BasicSpawnTools

_registration = Registration([BasicSpawnTools])


def register() -> None:
    _registration.register()


register()
