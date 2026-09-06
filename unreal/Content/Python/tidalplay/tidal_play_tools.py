# TidalLightPlayTools —— 在沉塔-灯塔 Demo 关卡上真实可执行的「玩法判定 probe」。
#
# 3 阶段 step: 不造假手感，只提供能被 orchestrator/测试读取的玩法 state(几何判定雏形)：
#   - 依 label (tl_*) 收集 关卡中 ACTOR 的位置（影带怪 enemy_shadow、光闸柱 gate_col、
#     菲涅尔 lens、塔梯 steps 等），据此 compute:
#       gate_ready   两光柱宽度是否落可开阈值（简单几何判定）
#       影带怪在暗/近玩家区 计数与最逼近距离(<视为"需拖入光"的近)。
#       可见塔件 counts / 路径连续性提示
#   - 该 read 为真实世界 probe，供后续玩法规则在此基础上作真逻辑。
#
# 仅作最小“Read & derive”，不 claim 已含可玩控制/镜头/手感（那些属未来玩法引擎）。

import json
import unreal

import toolset_registry

_PREFIX = "tl_"


def _json(ok: bool, **kw):
    return json.dumps(dict(ok=ok, **kw), ensure_ascii=False)


@unreal.uclass()
class TidalLightPlayTools(unreal.ToolsetDefinition):
    """TidalLight demo play-state probe (read-only)."""

    @staticmethod
    def _actors():
        return unreal.EditorLevelLibrary.get_all_level_actors()

    @staticmethod
    def _vec3(a):
        p = a.get_actor_location()
        return (p.x, p.y, p.z)

    @staticmethod
    def _dist(xyz1, xyz2):
        import math
        return math.hypot(xyz1[0] - xyz2[0], xyz1[1] - xyz2[1])

    @toolset_registry.tool_call
    @staticmethod
    def list_markers() -> str:
        """List actors whose label starts with 'tl_' with coordinates (read-only)."""
        out = []
        try:
            for a in TidalLightPlayTools._actors():
                lb = a.get_actor_label()
                if lb.startswith(_PREFIX):
                    x, y, z = TidalLightPlayTools._vec3(a)
                    out.append({"label": lb, "x": x, "y": y, "z": z})
        except Exception as exc:  # noqa: BLE001
            return _json(False, error=str(exc))
        return _json(True, count=len(out), markers=out)

    @toolset_registry.tool_call
    @staticmethod
    def play_state(open_gate_dist: float = 600.0, near_enemy_dist: float = 400.0) -> str:
        """Derive a minimal play-structure state from world geometry (read-only).

        简单判定（供玩法逻辑进一步实现，不假装手感）：
          gate_ready：撮两 tl_gate_col_* 柱水平宽度 ≤ open_gate_dist（视为光闸可被两光点触发开启）
          影带怪区：tl_enemy_shadow_* 计数和一个“距入口最近”怪距离；entrance 帮助零位
            node（用 tl_suika_entrance 位置作为玩家近点参考）
        Returns JSON.
        """
        try:
            markers = {}
            for a in TidalLightPlayTools._actors():
                lb = a.get_actor_label()
                if lb.startswith(_PREFIX):
                    markers.setdefault(lb, TidalLightPlayTools._vec3(a))
        except Exception as exc:  # noqa: BLE001
            return _json(False, error=str(exc))

        gate_cols = [v for k, v in markers.items() if k.startswith("tl_gate_col")]
        enemies = [v for k, v in markers.items() if k.startswith("tl_enemy_shadow")]
        entrance = next((v for k, v in markers.items()
                         if k in ("tl_suika_entrance", "tl_entrance")), None)

        gate_ready = False
        if len(gate_cols) >= 2:
            w = TidalLightPlayTools._dist(gate_cols[0], gate_cols[1])
            gate_ready = w <= open_gate_dist
        near = None
        if entrance and enemies:
            near = min(TidalLightPlayTools._dist(entrance, e) for e in enemies)
        return _json(
            True,
            gate_ready=gate_ready,
            gate_width=round(TidalLightPlayTools._dist(gate_cols[0], gate_cols[1]), 1)
            if len(gate_cols) >= 2 else None,
            enemy_count=len(enemies),
            nearest_enemy_dist=round(near, 1) if near is not None else None,
            has_entrance=entrance is not None,
        )
