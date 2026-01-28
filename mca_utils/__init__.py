"""
MCA Automation Utilities Package
Shared modules for MCA portal automation scripts
"""

from .config import *
from .captcha_solver import solve_captcha
from .utils import (
    get_robust_locator,
    type_slowly,
    wait_for_result_panel,
    get_value_by_id,
    get_value_by_label
)

__all__ = [
    'solve_captcha',
    'get_robust_locator',
    'type_slowly',
    'wait_for_result_panel',
    'get_value_by_id',
    'get_value_by_label'
]
