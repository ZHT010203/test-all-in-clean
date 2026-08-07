"""
基础配置
换项目只需改这里，框架代码不动
"""

# ============= URL配置 =============
# 后台管理系统
ADMIN_BASE_URL = "http://localhost:8080"
# 前台商城系统
PORTAL_BASE_URL = "http://localhost:8085"
# 搜索系统
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

MONGODB_CONFIG = {
    "host": "localhost",
    "port": 27017,
    "database": "mall-port"
}

# ============= 测试用例路径 =============
import os

# 项目根目录（-01目录）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 测试用例Excel目录
TEST_CASE_DIR = os.path.join(PROJECT_ROOT, "Data", "Test_case")
# 测试报告目录（回写结果输出到这里）
TEST_REPORT_DIR = os.path.join(PROJECT_ROOT, "Data", "Test_report")
# 日志目录
LOG_DIR = os.path.join(PROJECT_ROOT, "Logs")
