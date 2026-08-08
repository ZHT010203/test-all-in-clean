"""
请求体配置（接口入参）
换项目只需改这里，框架代码不动

用途：配置各接口的请求体JSON
请求头不需要配，所有接口登录后都一样，conftest.py自动处理
"""

# ============= 后台登录请求体 =============
ADMIN_LOGIN_BODY = {
    "username": "admin",
    "password": "macro123"
}

# ============= 前台登录请求体（form-urlencoded，不是JSON） =============
# 前台登录用data参数，不用json参数
MEMBER_LOGIN_BODY = {
    "username": "testuser01",
    "password": "test123456"
}
