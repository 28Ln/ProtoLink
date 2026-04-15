from __future__ import annotations

from protolink.core.models import ModuleStatus
from protolink.presentation import display_module_name, display_module_status
from protolink.ui.text import CURRENT_DRAFT_TEXT, DRAFT_TEXT, READY_TEXT, module_status_text


def test_product_copy_uses_user_facing_language() -> None:
    assert READY_TEXT == "等待操作"
    assert CURRENT_DRAFT_TEXT == "未保存配置"
    assert DRAFT_TEXT == "编辑内容"

    assert display_module_name("dashboard") == "开始页面"

    assert display_module_status(ModuleStatus.BOOTSTRAPPED) == "可用"
    assert display_module_status(ModuleStatus.NEXT) == "持续完善"
    assert display_module_status(ModuleStatus.PLANNED) == "即将提供"

    assert module_status_text(ModuleStatus.BOOTSTRAPPED) == "可用"
    assert module_status_text(ModuleStatus.NEXT) == "持续完善"
    assert module_status_text(ModuleStatus.PLANNED) == "即将提供"
