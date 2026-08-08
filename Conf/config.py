"""
基础配置
换项目只需改这里，框架代码不动

环境切换机制：
  1. 通过环境变量 APP_ENV 指定当前环境（dev / test / prod），默认 dev
  2. 各环境的 URL / 账号 / DB 配置写在 Conf/env/{APP_ENV}.py
  3. 敏感信息（密码）放在项目根目录的 .env 文件中（不提交 git），
     .env 中的同名变量会覆盖 Conf/env/{APP_ENV}.py 里的密码
  4. 真实的系统环境变量优先级最高（.env 不会覆盖已存在的系统环境变量）
"""
import os
import importlib


# ============= 路径配置（与环境无关） =============
# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 测试用例Excel目录
TEST_CASE_DIR = os.path.join(PROJECT_ROOT, "Data", "Test_case")
# 测试报告目录（回写结果输出到这里）
TEST_REPORT_DIR = os.path.join(PROJECT_ROOT, "Data", "Test_report")
# 日志目录
LOG_DIR = os.path.join(PROJECT_ROOT, "Logs")


# ============= 加载 .env（手写简易版，不引入 python-dotenv） =============
def _load_dotenv():
    """
    读取项目根目录的 .env 文件，按行解析 KEY=VALUE 注入 os.environ。
    已存在的环境变量不会被覆盖（真实系统环境变量优先级最高）。
    """
    env_path = os.path.join(PROJECT_ROOT, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # 跳过空行和注释
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # 去掉两端引号
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            # 已存在则不覆盖
            if key not in os.environ:
                os.environ[key] = value


_load_dotenv()


# ============= 根据 APP_ENV 动态加载环境配置 =============
APP_ENV = os.environ.get("APP_ENV", "dev")
_env_module = importlib.import_module(f"Conf.env.{APP_ENV}")

# URL配置
ADMIN_BASE_URL = _env_module.ADMIN_BASE_URL
PORTAL_BASE_URL = _env_module.PORTAL_BASE_URL
SEARCH_BASE_URL = _env_module.SEARCH_BASE_URL

# 数据库配置
MYSQL_CONFIG = _env_module.MYSQL_CONFIG

# 账号配置
ADMIN_USERNAME = _env_module.ADMIN_USERNAME
MEMBER_USERNAME = _env_module.MEMBER_USERNAME
MEMBER_TELEPHONE = _env_module.MEMBER_TELEPHONE

# 敏感信息（密码）：优先用 .env / 系统环境变量中的值覆盖
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", _env_module.ADMIN_PASSWORD)
MEMBER_PASSWORD = os.environ.get("MEMBER_PASSWORD", _env_module.MEMBER_PASSWORD)


# ============= MongoDB 配置（与环境无关，保持静态） =============
MONGODB_CONFIG = {
    "host": "localhost",
    "port": 27017,
    "database": "mall-port"
}
