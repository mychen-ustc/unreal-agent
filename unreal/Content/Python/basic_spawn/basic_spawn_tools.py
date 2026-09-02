# 自研 BasicSpawnToolset（AC-P0-06：在关卡放置/移除一个 Cube StaticMeshActor 验证最小闭环）
#
# 对齐引擎 ToolsetRegistry 的规范 Python 注册：
#   @unreal.uclass()                                       声明 ToolsetDefinition
#   @toolset_registry.tool_call @staticmethod f(a: T, ...)  把带类型注解静态方法暴露为 MCP 工具
#   Registration([BasicSpawnTools]).register()             由 unreal/Content/Python/init_unreal.py 启动自注册
#
# 语义：不放凭空 .uasset；放置 /Engine/BasicShapes/Cube.Cube 立方体 StaticMeshActor 到当前关卡，
# 以 actor_label 作为可移除句柄（rollback），产物可用 list/remove 查询清理。

import json

import unreal

import toolset_registry


def _err(msg: str) -> str:
    return json.dumps({"ok": False, "error": msg})


@unreal.uclass()
class BasicSpawnTools(unreal.ToolsetDefinition):
    """Minimal spawn/remove of a cube StaticMeshActor in the current editor level."""

    _CUBE = '/Engine/BasicShapes/Cube.Cube'
    _TAG_BASIC = 'ac_p0_cube'

    @toolset_registry.tool_call
    @staticmethod
    def place_cube(
        location_x: float = 0.0,
        location_y: float = 0.0,
        location_z: float = 100.0,
        label: str = "AgentCube") -> str:
        """Spawn a cube StaticMeshActor at location and tag it as agent-generated.

        Args:
            location_x: world X coordinate
            location_y: world Y coordinate
            location_z: world Z coordinate
            label: stable actor label used later by remove_actor
        """
        try:
            loader = unreal
            cube_asset = unreal.load_asset(BasicSpawnTools._CUBE)
            if cube_asset is None:
                return _err('加载 %s 失败' % BasicSpawnTools._CUBE)
            loc = unreal.Vector(location_x, location_y, location_z)
            rot = unreal.Rotator(0, 0, 0)
            actor = unreal.EditorLevelLibrary.spawn_actor_from_object(cube_asset, loc, rot)
            if actor is None:
                return _err('spawn_actor_from_object 返回空')
            actor.set_actor_label(label)
            actor.tags = list(actor.tags) + [BasicSpawnTools._TAG_BASIC, 'agent_generated']
            return json.dumps({"ok": True, "actor_label": label})
        except Exception as exc:  # noqa: BLE001
            return _err('place_cube 异常: %s' % exc)

    @toolset_registry.tool_call
    @staticmethod
    def list_agent_cubes() -> str:
        """List labels/locations of agent-generated cube actors in the current level (read-only verify)."""
        result = []
        try:
            for actor in unreal.EditorLevelLibrary.get_all_level_actors():
                if BasicSpawnTools._TAG_BASIC in getattr(actor, 'tags', []):
                    t = actor.get_actor_location()
                    result.append({"label": actor.get_actor_label(),
                                   "x": t.x, "y": t.y, "z": t.z})
        except Exception as exc:  # noqa: BLE001
            return _err('list_agent_cubes 异常: %s' % exc)
        return json.dumps(result)

    @toolset_registry.tool_call
    @staticmethod
    def remove_cube(label: str) -> str:
        """Remove the actor with the given label from level (rollback). Returns removed count.

        Args:
            label: actor label returned by place_cube
        """
        removed = 0
        try:
            for actor in unreal.EditorLevelLibrary.get_all_level_actors():
                if BasicSpawnTools._TAG_BASIC in getattr(actor, 'tags', []) and actor.get_actor_label() == label:
                    unreal.EditorLevelLibrary.destroy_actor(actor)
                    removed += 1
        except Exception as exc:  # noqa: BLE001
            return _err('remove_cube 异常: %s' % exc)
        return json.dumps({"ok": True, "removed": removed})
