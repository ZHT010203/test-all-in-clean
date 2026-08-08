"""
日志模块 - setup_logger()
统一配置 root logger，用 RotatingFileHandler 按大小切割日志文件，
同时输出到文件和控制台。防止重复添加 handler。
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler

# 支持导入Conf模块（参考 result_writer.py 的处理方式）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Conf.config import LOG_DIR


def setup_logger(level=logging.INFO):
    """
    配置 root logger：
    - 文件 handler：RotatingFileHandler，单文件 10MB，保留 5 个备份
    - 控制台 handler：StreamHandler
    - 格式：%(asctime)s - %(levelname)s - %(message)s
    - 防止重复添加 handler（root logger 已有 handler 时先清空再加）

    Args:
        level: 日志级别，默认 logging.INFO
    """
    # 确保日志目录存在
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, "test_run.log")

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # 文件 handler：按大小切割，单文件 10MB，保留 5 个备份
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    # 控制台 handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # 配置 root logger：先清空已有 handler，防止重复添加
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
