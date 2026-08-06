"""
conftest.py - 依赖管理和fixture
01: 日志配置
02: 后台管理员登录fixture
03: 后台HTTP客户端fixture（自动注入Token）
04: 数据库客户端fixture
05: 读取Excel测试用例fixture
"""
import sys
import os
import logging
import pytest
import requests

# 支持导入Conf和common模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Conf.accounts import ADMIN_USERNAME, ADMIN_PASSWORD
from Conf.api_path import ADMIN_LOGIN
from Conf.config import ADMIN_BASE_URL, MYSQL_CONFIG, LOG_DIR
from common.http_client import HTTPClient
from common.db_client import DBClient
from common.excel_reader import ExcelReader


# ============= 全局请求头（所有接口通用） =============
def make_auth_headers(token):
    """
    根据Token生成认证请求头
    所有接口登录后请求头都一样：Bearer Token + JSON
    如果你的系统请求头不一样，改这里就行
    """
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


# ============= 日志配置 =============
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, "test_run.log")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)


# ============= 后台管理员登录 =============
@pytest.fixture(scope="session")
def admin_login():
    """
    后台管理员登录fixture
    用原生requests发登录请求，拿到token
    返回 {"token": "xxx", "headers": {...}}
    """
    url = ADMIN_BASE_URL + ADMIN_LOGIN
    body = {"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
    
    logger.info(f"后台登录: URL={url}, 账号={ADMIN_USERNAME}")
    
    try:
        resp = requests.post(url, json=body, timeout=10)
        result = resp.json()
        
        if result.get("code") == 200:
            data = result.get("data")
            if data:
                # data可能是字符串token，也可能是{"token":"xxx","tokenHead":"Bearer "}
                if isinstance(data, dict):
                    token = data.get("token", "")
                else:
                    token = str(data)
                headers = make_auth_headers(token)
                logger.info(f"后台登录成功, Token={token[:20]}...")
                return {"token": token, "headers": headers}
        
        logger.error(f"后台登录失败: 返回={result}")
        raise Exception(f"后台登录失败: {result}")
        
    except requests.RequestException as e:
        logger.error(f"后台登录请求异常: {e}")
        raise


# ============= 后台HTTP客户端 =============
@pytest.fixture(scope="session")
def admin_client(admin_login):
    """
    后台HTTP客户端，自动注入管理员Token
    调用http_client.py的HTTPClient类，把token塞进default_headers
    
    用法（在测试文件里）：
        def test_xxx(admin_client):
            resp = admin_client.get("/brand/list", params={"pageNum":1})
            assert resp.json().get("code") == 200
    """
    client = HTTPClient(
        base_url=ADMIN_BASE_URL,
        default_headers=admin_login["headers"],
        timeout=30,
        max_retries=3
    )
    logger.info("后台HTTPClient创建成功，已注入Token")
    yield client
    client.close()
    logger.info("后台HTTPClient已关闭")





# ============= 数据库客户端 =============
@pytest.fixture(scope="session")
def db_client():
    """
    MySQL数据库客户端，自动管理连接池
    
    用法（在测试文件里）：
        def test_xxx(db_client):
            result = db_client.fetchone("SELECT * FROM pms_brand WHERE id = %s", (1,))
    """
    client = DBClient(db_config=MYSQL_CONFIG, pool_size=5)
    logger.info("DBClient创建成功，连接池已初始化")
    yield client
    client.close()
    logger.info("DBClient连接池已关闭")


# ============= 读取Excel测试用例 =============
@pytest.fixture
def read_excel():
    """
    通用Excel测试用例读取fixture
    按列名匹配，不依赖列顺序，自动清洗空数据

    用法（在测试文件里）：
        def test_xxx(read_excel):
            cases = read_excel(
                file_name="品牌分页列表.xlsx",
                required_cols=["测试点", "ApiPath", "接口入参", "预期结果"]
            )
            for case in cases:
                print(case["测试点"], case["ApiPath"])
    """
    from Conf.config import TEST_CASE_DIR
    #实例化ExcelReader类
    reader = ExcelReader()

    def _read(file_name, required_cols=None):
        file_path = os.path.join(TEST_CASE_DIR, file_name)
        return reader.read(file_path=file_path, required_cols=required_cols)

    return _read
