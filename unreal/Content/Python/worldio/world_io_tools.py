# WorldIOTools —— 把「当前编辑器关卡」持久保存成 .uassET / umap（阶段 A：真实可重开关卡）。
#
# 背景：引擎预置 MCP 无「保存当前地图到 /Game」能力；这里补一个最小自研 Python toolset，
# 用 EditorLevelLibrary / LevelEditorSubsystem 真将当前世界存档为可再打开的 .umap，
# 供 C（沉塔-灯塔灰盒→真实可玩 Demo Map）使用。
#
# 稳健性：完整可用 method 名随 UE 版本可异，提供多个候选并按是否已存在返回清晰信息。
#
import json
import unreal

import toolset_registry


def _json(ok: bool, **kw):
    return json.dumps(dict(ok=ok, **kw), ensure_ascii=False)


@unreal.uclass()
class WorldIOTools(unreal.ToolsetDefinition):
    """Minimal world / map persistence helpers (stage A)."""
    @toolset_registry.tool_call
    @staticmethod
    def new_level(game_path: str = "/Game/TidalLight/Demo") -> str:
        """Create & switch to a fresh project level at the given /Game path (blank, ownable)."""
        if not game_path.startswith("/Game"):
            return _json(False, error="game_path 必须以 /Game 开头")
        try:
            had = hasattr(unreal.EditorLevelLibrary, "new_level")
            if not had:
                return _json(False, error="EditorLevelLibrary 无 new_level", candidates=True)
            res = unreal.EditorLevelLibrary.new_level(game_path)
            return _json(True, asset=game_path, res=bool(res))
        except Exception as exc:  # noqa: BLE001
            return _json(False, error=str(exc))

    @toolset_registry.tool_call
    @staticmethod
    def save_current_level(game_path: str = "/Game/TidalLight/Demo") -> str:
        """Save current editor level to the given /Game path (creates .umap if possible).

        Args:
            game_path: UE content package path (e.g. "/Game/TidalLight/Demo")
        """
        if not game_path.startswith("/Game"):
            return _json(False, error="game_path 必须以 /Game 开头")
        el = unreal.EditorLevelLibrary
        notes = []
        for cand in (game_path, game_path + ".umap"):
            try:
                if not hasattr(el, "save_current_level"):
                    notes.append("no attr save_current_level")
                    break
                r = el.save_current_level(cand)
                notes.append(f"path={cand} ret={r!r}")
                # UE 若返回 None/False 无法确认，继续尝试下个；True则成功
                if bool(r):
                    return _json(True, asset=cand)
            except Exception as exc:  # noqa: BLE001
                notes.append(f"path={cand} EXC {type(exc).__name__}: {exc}")
        # 兜底：保存所有 dirty level（可能包括当前）
        try:
            dirty = el.save_all_dirty_levels()
            if bool(dirty):
                return _json(True, asset=game_path, via="save_all_dirty_levels")
            notes.append(f"save_all_dirty_levels returned {dirty!r}")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"save_all_dirty EXC {type(exc).__name__}: {exc}")
        return _json(False, error="; ".join(notes) or "未知", candidates=[m for m in dir(el) if "save" in m.lower()])

    @toolset_registry.tool_call
    @staticmethod
    def current_level_name() -> str:
        """Return the currently opened level name (context proving)."""
        try:
            name = unreal.EditorLevelLibrary.get_editor_world().get_name()
            return _json(True, level=name)
        except Exception as exc:  # noqa: BLE001
            return _json(False, error=str(exc))
