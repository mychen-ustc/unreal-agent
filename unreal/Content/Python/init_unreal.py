# 项目 Python 启动脚本（编辑器启用 PythonScriptPlugin 时执行）
# 注册自研 Toolset（BasicSpawnTools / WorldIOTools / TidalLightPlay / TidalDemoIO）。
import unreal  # noqa: F401

from toolset_registry.registration import Registration
from basic_spawn.basic_spawn_tools import BasicSpawnTools
from worldio.world_io_tools import WorldIOTools
from tidalplay.tidal_play_tools import TidalLightPlayTools
from tidalplay.tidal_open import TidalDemoIO

_registration = Registration([BasicSpawnTools, WorldIOTools, TidalLightPlayTools, TidalDemoIO])


def register() -> None:
    _registration.register()


register()
