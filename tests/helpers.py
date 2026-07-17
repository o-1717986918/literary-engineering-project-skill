import tempfile
from pathlib import Path

from literary_engineering_workbench.context_packet import build_context_packet
from literary_engineering_workbench.init_project import InitOptions, init_work_project
from literary_engineering_workbench.review_ci import review_scene_draft
from literary_engineering_workbench.scene_draft import build_scene_draft


class TempProjectMixin:
    def make_project(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name) / "work"
        init_work_project(
            InitOptions(
                target=root,
                title="测试作品",
                premise="一个用于测试文学工程工作流的故事。",
                genre="工程测试",
            )
        )
        self.addCleanup(tmp.cleanup)
        return root


def add_character(project_root: Path, name: str = "林舟") -> Path:
    path = project_root / "characters" / "linzhou.yaml"
    path.write_text(
        f"""character_id: linzhou
name: {name}
role: 主角
bdi:
  belief:
    - 城市的停电不是偶然。
  desire:
    - 找到被隐藏的档案。
  intention:
    - 在不惊动看守的情况下进入旧楼。
psychology:
  fear:
    - 牵连同伴。
  secret:
    - 他曾经读过一页残缺档案。
  moral_line: 不伤害无辜者。
background_story:
  summary: 他少年时因一次误判导致同伴受罚，从此习惯先观察再行动。
  formative_events:
    - 少年时期的误判让他对仓促决定保持警惕。
  behavior_influences:
    - 遇到危险时会先确认旁人是否会被牵连。
    - 面对档案和旧事时会表现得异常克制。
  reveal_policy: implicit_only
speech_style:
  rhythm: 短句，克制，少解释。
""",
        encoding="utf-8",
    )
    return path


def make_passing_scene(project_root: Path) -> Path:
    build_context_packet(project_root, scene=Path("scenes/scene_0001.yaml"), rebuild_index=True)
    draft = build_scene_draft(project_root, scene=Path("scenes/scene_0001.yaml")).draft_path
    text = draft.read_text(encoding="utf-8")
    body = (
        "林舟站在旧楼门口，听见楼道深处的电流声断断续续。他没有立刻进去，而是先数了三次呼吸，确认街角的巡逻灯还没有转向。"
        "这一次他不是为了证明什么，只是要把那页残缺档案和眼前的停电连起来。门后的灰尘被风推开，像有人刚从黑暗里离开。"
        "他把手电压低，沿着墙边移动，心里清楚每一步都会改变同伴明天能否继续调查。"
    )
    replacements = {
        "<!-- 在这里写入场景正文。 -->": body,
        "### 新增事实候选\n\n- ": "### 新增事实候选\n\n- 林舟发现旧楼停电与残缺档案有关。",
        "### 人物状态变化\n\n- ": "### 人物状态变化\n\n- 林舟从旁观转为主动调查。",
        "### 关系变化\n\n- ": "### 关系变化\n\n- 林舟开始隐瞒自己的行动计划。",
        "### 伏笔变化\n\n- ": "### 伏笔变化\n\n- 残缺档案成为后续追查线索。",
        "### 需要人工确认\n\n- ": "### 需要人工确认\n\n- 是否确认旧楼停电为主线事件。",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    draft.write_text(text, encoding="utf-8")
    return draft


def make_reviewed_passing_scene(project_root: Path) -> Path:
    draft = make_passing_scene(project_root)
    review_scene_draft(project_root, draft)
    return draft
