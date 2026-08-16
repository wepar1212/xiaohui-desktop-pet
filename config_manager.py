# -*- coding: utf-8 -*-
"""
星绊桌宠 — 配置读写
"""

import os
import json

from path_helper import data_path

CONFIG_FILE = data_path("config.json")


def load_config():
    default_config = {
        "deepseek_api_key": "",
        "deepseek_model": "deepseek-chat",
        "deepseek_base_url": "https://api.deepseek.com/v1",
        "pomodoro_minutes": 25,
        "affection": 40,
        "auto_talk_level": 2
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                default_config.update(config)
        except Exception:
            pass
    return default_config


def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
