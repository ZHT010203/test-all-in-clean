"""
test 测试环境配置（占位值，按实际测试环境替换）
"""

# ============= URL配置 =============
ADMIN_BASE_URL = "http://test-mall-admin:8080"
PORTAL_BASE_URL = "http://test-mall-portal:8085"
SEARCH_BASE_URL = "http://test-mall-search:8081"

# ============= 数据库配置 =============
MYSQL_CONFIG = {
    "host": "test-mysql",
    "port": 3306,
    "user": "root",
    "password": "changeme",
    "database": "mall",
    "charset": "utf8mb4"
}

# ============= 账号配置（密码从 .env 读取覆盖） =============
ADMIN_USERNAME = "test_admin"
ADMIN_PASSWORD = "test_pwd"
MEMBER_USERNAME = "test_member"
MEMBER_PASSWORD = "test_member_pwd"
MEMBER_TELEPHONE = "13900000001"
