"""
断言引擎 - AssertEngine类

基于 jsonpath_ng 取值，用 pytest 的 assert 做断言。
实例化时传入接口返回的字典 result，之后所有方法不用再传 result。

用法:
    from common.assertion import AssertEngine

    result = response.json()
    ae = AssertEngine(result)

    # 核心方法：从Excel预期结果字符串解析断言（支持6种格式）
    ae.assert_result("$.code=200;$.message=操作成功", "登录测试")
    ae.assert_result("$.code=200;not_empty=$.data.name", "添加品牌")
    ae.assert_result("$.code=200;contains=$.message,成功", "查询品牌")
    ae.assert_result("$.code=200;type=$.code,int", "类型校验")
    ae.assert_result("$.code=200;length=$.data.list,>=1", "列表校验")

    # 单独调用
    ae.assert_not_empty("$.data.name", "品牌名")
    ae.assert_contains("$.message", "成功", "提示信息")
    brand = ae.find_in_list("$.data.list", "name", "万和")

数据库断言（校验写接口后数据是否落库）:
    from common.db_client import DBClient
    db = DBClient(db_config)

    # 方式1：初始化时传入 db_client
    ae = AssertEngine(result, db_client=db)

    # 方式2：调用时单独传 db（优先级高于初始化传入的）
    ae.assert_db_record(
        sql="SELECT id, name FROM pms_brand WHERE name = %s",
        params=("万和",),
        expected_dict={"name": "万和"},
        测试点="新增品牌落库"
    )

    # 断言记录不存在（删除/取消后校验）
    ae.assert_db_not_exists(
        sql="SELECT id FROM pms_brand WHERE id = %s",
        params=(999,),
        测试点="删除品牌后记录不存在"
    )
"""
import logging

from jsonpath_ng.ext import parse

logger = logging.getLogger(__name__)


class AssertEngine:
    """
    断言引擎

    实例化时传入接口返回的字典，之后所有方法都不用再传 result。

    示例:
        result = resp.json()
        ae = AssertEngine(result)
        ae.assert_result("$.code=200;$.message=操作成功", "登录")
    """

    def __init__(self, result, db_client=None):
        """
        初始化断言引擎

        Args:
            result: 接口返回的字典
            db_client: 可选，DBClient 实例，用于数据库断言（assert_db_record / assert_db_not_exists）
                       不传时为 None，调用 db 断言方法时需单独传 db 参数，否则报错
        """
        self.result = result
        self.db_client = db_client

    def _extract(self, path):
        """
        用 jsonpath_ng 从 self.result 取值（内部方法）

        Args:
            path: jsonpath 表达式，如 "$.code"、"$.data.list[0].name"

        Returns:
            取到的值；取不到或解析失败返回 None（不报错）
        """
        try:
            expr = parse(path)
            matches = expr.find(self.result)
            if matches:
                return matches[0].value
            return None
        except Exception as e:
            logger.error(f"jsonpath解析失败: {path}, 错误: {e}")
            return None

    def assert_result(self, expected_str, 测试点=""):
        """
        从Excel预期结果字符串解析断言（核心方法）

        用分号分隔多个条件，支持6种格式：
            1. 等值:  $.code=200              → 取值转str比较
            2. 不等:  $.code!=500
            3. 非空:  not_empty=$.data.name    → 调用 assert_not_empty
            4. 包含:  contains=$.message,成功  → 调用 assert_contains
            5. 类型:  type=$.code,int          → isinstance判断
            6. 长度:  length=$.data.list,>=1   → len()判断，支持 >= <= > < == =

        Args:
            expected_str: 预期结果字符串（从Excel读取）
            测试点: 测试点名称（日志和报错提示用）

        用法:
            ae.assert_result("$.code=200;$.message=操作成功", "登录")
            ae.assert_result("$.code=200;not_empty=$.data.name;length=$.data.list,>=1", "查询")
        """
        if not expected_str:
            logger.warning(f"[{测试点}] 预期结果为空，跳过断言")
            return

        # 按分号分隔多个断言条件
        conditions = str(expected_str).split(";")

        for cond in conditions:
            cond = cond.strip()
            if not cond:
                continue

            logger.debug(f"[{测试点}] 开始断言: {cond}")

            # 非空断言: not_empty=$.data.name
            if cond.startswith("not_empty="):
                path = cond.split("=", 1)[1].strip()
                self.assert_not_empty(path, path)

            # 包含断言: contains=$.message,成功
            elif cond.startswith("contains="):
                params = cond.split("=", 1)[1].strip()
                path, value = params.split(",", 1)
                self.assert_contains(path.strip(), value.strip(), path.strip())

            # 类型断言: type=$.code,int
            elif cond.startswith("type="):
                params = cond.split("=", 1)[1].strip()
                path, type_name = params.split(",", 1)
                type_map = {"int": int, "str": str, "list": list,
                            "dict": dict, "float": float, "bool": bool}
                expected_type = type_map.get(type_name.strip(), str)
                value = self._extract(path.strip())
                logger.debug(f"[{测试点}] 类型断言: {path} 期望={type_name.strip()}, 实际={type(value).__name__}")
                if not isinstance(value, expected_type):
                    logger.error(f"[{测试点}] 类型断言失败: {path} 期望={type_name.strip()}, 实际={type(value).__name__}, 值={value}")
                    assert False, \
                        f"[{测试点}] {path}类型应为{type_name.strip()}, 实际={type(value).__name__}, 值={value}"

            # 长度断言: length=$.data.list,>=1
            elif cond.startswith("length="):
                params = cond.split("=", 1)[1].strip()
                path, condition = params.split(",", 1)
                path = path.strip()
                condition = condition.strip()
                value = self._extract(path)
                logger.debug(f"[{测试点}] 长度断言: {path} 条件={condition}, 实际值={value}")
                if value is None:
                    logger.error(f"[{测试点}] 长度断言失败: {path}字段不存在")
                    assert False, f"[{测试点}] {path}字段不存在"
                actual_len = len(value)
                # 按操作符顺序判断：>= <= == > < =
                if condition.startswith(">="):
                    num = int(condition[2:])
                    logger.debug(f"[{测试点}] 长度断言: {path} 期望>={num}, 实际={actual_len}")
                    if not actual_len >= num:
                        logger.error(f"[{测试点}] 长度断言失败: {path} 期望>={num}, 实际={actual_len}")
                        assert False, f"[{测试点}] {path}长度应>={num}, 实际={actual_len}"
                elif condition.startswith("<="):
                    num = int(condition[2:])
                    logger.debug(f"[{测试点}] 长度断言: {path} 期望<={num}, 实际={actual_len}")
                    if not actual_len <= num:
                        logger.error(f"[{测试点}] 长度断言失败: {path} 期望<={num}, 实际={actual_len}")
                        assert False, f"[{测试点}] {path}长度应<={num}, 实际={actual_len}"
                elif condition.startswith("=="):
                    num = int(condition[2:])
                    logger.debug(f"[{测试点}] 长度断言: {path} 期望={num}, 实际={actual_len}")
                    if not actual_len == num:
                        logger.error(f"[{测试点}] 长度断言失败: {path} 期望={num}, 实际={actual_len}")
                        assert False, f"[{测试点}] {path}长度应={num}, 实际={actual_len}"
                elif condition.startswith(">"):
                    num = int(condition[1:])
                    logger.debug(f"[{测试点}] 长度断言: {path} 期望>{num}, 实际={actual_len}")
                    if not actual_len > num:
                        logger.error(f"[{测试点}] 长度断言失败: {path} 期望>{num}, 实际={actual_len}")
                        assert False, f"[{测试点}] {path}长度应>{num}, 实际={actual_len}"
                elif condition.startswith("<"):
                    num = int(condition[1:])
                    logger.debug(f"[{测试点}] 长度断言: {path} 期望<{num}, 实际={actual_len}")
                    if not actual_len < num:
                        logger.error(f"[{测试点}] 长度断言失败: {path} 期望<{num}, 实际={actual_len}")
                        assert False, f"[{测试点}] {path}长度应<{num}, 实际={actual_len}"
                elif condition.startswith("="):
                    num = int(condition[1:])
                    logger.debug(f"[{测试点}] 长度断言: {path} 期望={num}, 实际={actual_len}")
                    if not actual_len == num:
                        logger.error(f"[{测试点}] 长度断言失败: {path} 期望={num}, 实际={actual_len}")
                        assert False, f"[{测试点}] {path}长度应={num}, 实际={actual_len}"

            # 不等断言: $.code!=500
            elif "!=" in cond:
                path, value = cond.split("!=", 1)
                actual = str(self._extract(path.strip()))
                expected = value.strip()
                logger.debug(f"[{测试点}] 不等断言: {path} 不应等于={expected}, 实际={actual}")
                if actual == expected:
                    logger.error(f"[{测试点}] 不等断言失败: {path} 不应等于={expected}, 实际={actual}")
                    assert False, \
                        f"[{测试点}] {path}不应等于{expected}, 实际={actual}"

            # 等值断言: $.code=200
            elif "=" in cond:
                path, value = cond.split("=", 1)
                actual = str(self._extract(path.strip()))
                expected = value.strip()
                logger.debug(f"[{测试点}] 等值断言: {path} 期望={expected}, 实际={actual}")
                if actual != expected:
                    logger.error(f"[{测试点}] 等值断言失败: {path} 期望={expected}, 实际={actual}")
                    assert False, \
                        f"[{测试点}] {path}应等于{expected}, 实际={actual}"

            else:
                logger.error(f"[{测试点}] 无法识别的断言条件: {cond}")
                assert False, f"[{测试点}] 无法识别的断言条件: {cond}"

        logger.info(f"[{测试点}] 断言通过: {expected_str}")

    def assert_not_empty(self, path, 字段名=""):
        """
        断言字段非空

        None、空字符串、空列表、空字典都算空。

        Args:
            path: jsonpath 路径，如 "$.data.name"
            字段名: 中文名，用于报错提示

        用法:
            ae.assert_not_empty("$.data.name", "品牌名")
            ae.assert_not_empty("$.data.list", "品牌列表")
        """
        value = self._extract(path)
        label = 字段名 or path

        logger.debug(f"[{label}] 开始非空断言, 值={value}")

        if value is None:
            logger.error(f"[{label}] 非空断言失败: 字段为None")
            assert False, f"[{label}] 字段为None"
        if isinstance(value, str) and value.strip() == "":
            logger.error(f"[{label}] 非空断言失败: 字段为空字符串")
            assert False, f"[{label}] 字段为空字符串"
        if isinstance(value, list) and len(value) == 0:
            logger.error(f"[{label}] 非空断言失败: 字段为空列表")
            assert False, f"[{label}] 字段为空列表"
        if isinstance(value, dict) and len(value) == 0:
            logger.error(f"[{label}] 非空断言失败: 字段为空字典")
            assert False, f"[{label}] 字段为空字典"

        logger.info(f"[{label}] 断言非空通过, 值={value}")

    def assert_contains(self, path, value, 字段名=""):
        """
        断言字段包含某个值

        Args:
            path: jsonpath 路径
            value: 期望包含的值
            字段名: 中文名

        用法:
            ae.assert_contains("$.message", "成功", "提示信息")
        """
        actual = self._extract(path)
        label = 字段名 or path

        logger.debug(f"[{label}] 开始包含断言, 期望包含='{value}', 实际={actual}")

        if actual is None:
            logger.error(f"[{label}] 包含断言失败: 字段不存在")
            assert False, f"[{label}] 字段不存在"
        if value not in actual:
            logger.error(f"[{label}] 包含断言失败: 未包含'{value}', 实际={actual}")
            assert False, f"[{label}] 未包含'{value}', 实际={actual}"

        logger.info(f"[{label}] 断言包含通过, 包含'{value}'")

    def find_in_list(self, path, field, value):
        """
        在列表中查找指定条件的数据，返回找到的字典

        面试经典场景：响应1000条数据，找到你要的那一条。
        遍历列表，找到 item.get(field) == value 的字典并返回。

        Args:
            path: 列表的 jsonpath 路径，如 "$.data.list"
            field: 要搜索的字段名，如 "name"
            value: 要搜索的值，如 "万和"

        Returns:
            找到的字典；找不到返回 None

        用法:
            brand = ae.find_in_list("$.data.list", "name", "万和")
            if brand:
                assert brand["id"] == 1
        """
        data = self._extract(path)

        logger.info(f"在 '{path}' 中查找 {field}={value}")

        if data is None:
            logger.warning(f"路径 '{path}' 不存在或为None")
            return None

        if not isinstance(data, list):
            logger.warning(f"路径 '{path}' 不是列表, 类型={type(data).__name__}")
            return None

        for item in data:
            logger.debug(f"遍历 '{path}': 检查 {field}={item.get(field) if isinstance(item, dict) else item}")
            if isinstance(item, dict) and item.get(field) == value:
                logger.info(f"在 '{path}' 中找到 {field}={value} 的数据")
                return item

        logger.warning(f"在 '{path}' 中未找到 {field}={value} 的数据")
        return None

    def assert_db_record(self, sql, params, expected_dict, db=None, 测试点=""):
        """
        断言数据库中存在指定记录，并校验字段值是否一致

        用 db.fetchone(sql, params) 查询，遍历 expected_dict 比对每个字段。
        - 查不到记录（返回 None）：断言失败（记录不存在）
        - 字段不存在于查询结果：断言失败
        - 字段值不一致：断言失败，记录期望值和实际值
        - 全部一致：通过

        Args:
            sql: SQL 查询语句（用 %s 占位）
            params: SQL 参数元组
            expected_dict: 期望字段值字典，如 {"name": "万和", "status": 1}
            db: 可选，DBClient 实例；不传则用初始化时的 self.db_client；两者都为 None 则报错
            测试点: 测试点名称（日志和报错提示用）

        用法:
            ae.assert_db_record(
                sql="SELECT id, name FROM pms_brand WHERE name = %s",
                params=("万和",),
                expected_dict={"name": "万和"},
                测试点="新增品牌落库"
            )
        """
        # 选定 db 客户端：优先用入参 db，其次用初始化时传入的 self.db_client
        db_client = db if db is not None else self.db_client
        if db_client is None:
            logger.error(f"[{测试点}] 数据库断言失败: 未提供 db_client")
            assert False, f"[{测试点}] 未提供 db_client，无法执行数据库断言"

        logger.debug(f"[{测试点}] 开始数据库记录断言, SQL={sql}, params={params}")

        # 查询单条记录
        record = db_client.fetchone(sql, params)

        # 查询结果为 None：记录不存在，断言失败
        if record is None:
            logger.error(
                f"[{测试点}] 数据库记录断言失败: 记录不存在, "
                f"SQL={sql}, params={params}"
            )
            assert False, \
                f"[{测试点}] 数据库记录不存在, SQL={sql}, params={params}, 期望={expected_dict}"

        logger.debug(f"[{测试点}] 查询到记录: {record}")

        # 遍历期望字段逐一比对
        for field, expected_value in expected_dict.items():
            # 字段不存在于查询结果
            if field not in record:
                logger.error(
                    f"[{测试点}] 数据库记录断言失败: 字段不存在, "
                    f"字段={field}, SQL={sql}, 实际记录={record}"
                )
                assert False, \
                    f"[{测试点}] 字段不存在: {field}, SQL={sql}, 期望={expected_dict}, 实际记录={record}"

            actual_value = record[field]
            logger.debug(
                f"[{测试点}] 字段比对: {field} 期望={expected_value}, 实际={actual_value}"
            )

            # 值不一致
            if actual_value != expected_value:
                logger.error(
                    f"[{测试点}] 数据库记录断言失败: 字段值不一致, "
                    f"字段={field}, 期望={expected_value}, 实际={actual_value}, "
                    f"SQL={sql}"
                )
                assert False, \
                    f"[{测试点}] 字段值不一致: 字段={field}, 期望={expected_value}, 实际={actual_value}, SQL={sql}"

        # 全部一致，断言通过
        logger.info(f"[{测试点}] 数据库记录断言通过, SQL={sql}, 期望={expected_dict}")

    def assert_db_not_exists(self, sql, params, db=None, 测试点=""):
        """
        断言数据库中不存在指定记录（删除/取消等场景校验）

        用 db.fetchone(sql, params) 查询：
        - 查询结果不为 None：记录已存在，断言失败（不应存在）
        - 查询结果为 None：记录不存在，符合预期，通过

        Args:
            sql: SQL 查询语句（用 %s 占位）
            params: SQL 参数元组
            db: 可选，DBClient 实例；不传则用初始化时的 self.db_client；两者都为 None 则报错
            测试点: 测试点名称（日志和报错提示用）

        用法:
            ae.assert_db_not_exists(
                sql="SELECT id FROM pms_brand WHERE id = %s",
                params=(999,),
                测试点="删除品牌后记录不存在"
            )
        """
        # 选定 db 客户端：优先用入参 db，其次用初始化时传入的 self.db_client
        db_client = db if db is not None else self.db_client
        if db_client is None:
            logger.error(f"[{测试点}] 数据库断言失败: 未提供 db_client")
            assert False, f"[{测试点}] 未提供 db_client，无法执行数据库断言"

        logger.debug(f"[{测试点}] 开始数据库记录不存在断言, SQL={sql}, params={params}")

        # 查询单条记录
        record = db_client.fetchone(sql, params)

        # 查询结果不为 None：记录已存在，断言失败（不应存在）
        if record is not None:
            logger.error(
                f"[{测试点}] 数据库记录不存在断言失败: 记录已存在(不应存在), "
                f"SQL={sql}, params={params}, 实际记录={record}"
            )
            assert False, \
                f"[{测试点}] 记录已存在(不应存在), SQL={sql}, params={params}, 实际记录={record}"

        # 查询结果为 None：记录不存在，符合预期，通过
        logger.info(f"[{测试点}] 数据库记录不存在断言通过, SQL={sql}, params={params}")
