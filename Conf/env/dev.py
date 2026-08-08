"""
dev 开发环境配置（本地默认环境）
"""

# ============= URL配置 =============
ADMIN_BASE_URL = "http://localhost:8080"
PORTAL_BASE_URL = "http://localhost:8085"
SEARCH_BASE_URL = "http://localhost:8081"

# ============= 数据库配置 =============
MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "database": "mall",
    "charset": "utf8mb4"
}

# ============= 账号配置（密码从 .env 读取覆盖） =============
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "macro123"
MEMBER_USERNAME = "testuser01"
MEMBER_PASSWORD = "test123456"
MEMBER_TELEPHONE = "13800000001"
