"""
prod 生产环境配置（占位值，谨慎使用）
生产环境配置，谨慎使用
"""

# ============= URL配置 =============
ADMIN_BASE_URL = "http://prod-mall-admin:8080"
PORTAL_BASE_URL = "http://prod-mall-portal:8085"
SEARCH_BASE_URL = "http://prod-mall-search:8081"

# ============= 数据库配置 =============
MYSQL_CONFIG = {
    "host": "prod-mysql",
    "port": 3306,
    "user": "root",
    "password": "changeme",
    "database": "mall",
    "charset": "utf8mb4"
}

# ============= 账号配置（密码从 .env 读取覆盖） =============
ADMIN_USERNAME = "prod_admin"
ADMIN_PASSWORD = "prod_pwd"
MEMBER_USERNAME = "prod_member"
MEMBER_PASSWORD = "prod_member_pwd"
MEMBER_TELEPHONE = "13700000001"
