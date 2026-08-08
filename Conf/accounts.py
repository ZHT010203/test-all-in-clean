"""
账号密码配置
换项目只需改这里，框架代码不动

说明：账号与密码统一由 Conf/config.py 按当前环境（APP_ENV）动态加载，
敏感密码可由项目根目录的 .env 覆盖，本文件仅做 re-export，
保持 conftest 的 `from Conf.accounts import ADMIN_USERNAME, ADMIN_PASSWORD` 可用。
"""
from Conf.config import (
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
    MEMBER_USERNAME,
    MEMBER_PASSWORD,
    MEMBER_TELEPHONE,
)

__all__ = [
    "ADMIN_USERNAME",
    "ADMIN_PASSWORD",
    "MEMBER_USERNAME",
    "MEMBER_PASSWORD",
    "MEMBER_TELEPHONE",
]
