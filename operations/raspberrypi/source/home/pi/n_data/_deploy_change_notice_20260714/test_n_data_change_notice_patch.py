#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""생성된 변경공고 패처의 독립 자체 테스트."""

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATCHER = HERE / "apply_n_data_change_notice_patch.py"

spec = importlib.util.spec_from_file_location("change_notice_patcher", str(PATCHER))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

raise SystemExit(module.self_test())
