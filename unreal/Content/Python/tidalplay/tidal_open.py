# TidalDemoIO —— 打开沉塔 Demo 关卡（供玩法 probe 使用）
import json
import unreal

import toolset_registry


@unreal.uclass()
class TidalDemoIO(unreal.ToolsetDefinition):
    @toolset_registry.tool_call
    @staticmethod
    def open_demo(game_path: str = "/Game/TidalLight/Demo") -> str:
        """Open the given /Game level in editor (EditorLevelLibrary.load_level)."""
        try:
            E = unreal.EditorLevelLibrary
            if hasattr(E, "load_level"):
                r = E.load_level(game_path)
                return json.dumps({"ok": True, "r": "true" if r else "false", "map": game_path})
            return json.dumps({"ok": False, "error": "load_level 不可用"})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": str(exc)[:200]})
