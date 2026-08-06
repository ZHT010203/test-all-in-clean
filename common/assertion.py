"""
断言引擎 - AssertEngine类
基于pytest的assert扩展，不重复造轮子
只封装pytest做起来麻烦的场景

实例化一次，result只传一次，后面调用不用再传

用法:
    ae = AssertEngine(result)
    ae.assert_result("code=200;message=操作成功", "添加品牌")
    ae.assert_not_empty("data.name", "品牌名")
    ae.assert_contains("message", "成功", "提示信息")
    ae.assert_type("code", int, "状态码")
    ae.assert_length("data.list", min_len=1, 字段名="品牌列表")
    ae.find_in_list("data.list", "name", "测试品牌")
    ae.assert_field_exists("data.list", "name", "万和", "品牌列表")
"""
import logging

logger = logging.getLogger(__name__)


class AssertEngine:
    """
    断言引擎

    实例化时传入接口返回的字典，之后所有方法都不用再传result

    示例:
        result = resp.json()
        ae = AssertEngine(result)
        ae.assert_result("code=200")
        ae.assert_not_empty("data.name", "品牌名")
    """

    def __init__(self, result):
        """
        初始化断言引擎

        Args:
            result: 接口返回的字典
        """
        self.result = result

    def get_value(self, key):
        """
        从字典中取值，支持多级嵌套
        中间某层为None不会报错，返回None

        Args:
            key: 用.分隔的键路径
                 "code"              → result["code"]
                 "data.name"         → result["data"]["name"]
                 "data.list.0.id"    → result["data"]["list"][0]["id"]

        Returns:
            取到的值，取不到返回None
        """
        keys = key.split(".")
        value = self.result
        for k in keys:
            if value is None:
                return None
            if isinstance(value, dict) and k in value:
                value = value[k]
            elif isinstance(value, list):
                try:
                    index = int(k)
                    value = value[index]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return value

    def assert_result(self, expected_str, 测试点=""):
        """
        从Excel预期结果字符串断言（核心方法）

        支持格式（用分号分隔多个条件）:
            1. 精确匹配:   code=200
            2. 不等匹配:   code!=200
            3. 非空断言:   not_empty=data.name        → 字段不为空
            4. 包含断言:   contains=message,成功       → 字段包含某值
            5. 类型断言:   type=code,int               → 字段是指定类型
            6. 长度断言:   length=data.list,>=1        → 列表长度>=1

        组合示例:
            code=200;message=操作成功
            code=200;not_empty=data.name
            code=200;not_empty=data.list;contains=message,成功
            code=200;length=data.list,>=1

        Args:
            expected_str: 预期结果字符串（从Excel读取）
            测试点: 测试点名称（日志和报错提示用）

        用法:
            ae.assert_result("code=200;message=操作成功", "添加品牌")
            ae.assert_result("code=200;not_empty=data.name", "添加品牌")
            ae.assert_result("code=200;contains=message,成功", "添加品牌")
        """
        if not expected_str:
            logger.warning(f"[{测试点}] 预期结果为空，跳过断言")
            return
        # 按分号分隔多个断言条件。
        #原本是一个字符串，现在是一个列表
        #[["code=200", "message=操作成功"]
        conditions = str(expected_str).split(";")

        # 遍历每个断言条件
        for cond in conditions:
            # strip去掉首尾空格
            cond = cond.strip()
            if not cond:
                continue

            # 关键字断言: not_empty=data.name
            #startswith判断是否以指定前缀开头
            #split("=", 1)按等号分隔，最多分隔一次
            if cond.startswith("not_empty="):
                key = cond.split("=", 1)[1].strip()
                self.assert_not_empty(key, key)

            # 关键字断言: contains=message,成功
            elif cond.startswith("contains="):
                params = cond.split("=", 1)[1].strip()
                key, value = params.split(",", 1)
                self.assert_contains(key.strip(), value.strip(), key.strip())

            # 关键字断言: type=code,int
            elif cond.startswith("type="):
                params = cond.split("=", 1)[1].strip()
                key, type_name = params.split(",", 1)
                type_map = {"int": int, "str": str, "list": list, "dict": dict, "float": float, "bool": bool}
                expected_type = type_map.get(type_name.strip(), str)
                self.assert_type(key.strip(), expected_type, key.strip())

            # 关键字断言: length=data.list,>=1
            elif cond.startswith("length="):
                params = cond.split("=", 1)[1].strip()
                key, condition = params.split(",", 1)
                condition = condition.strip()
                value = self.get_value(key.strip())
                actual_len = len(value) if value is not None else 0
                if condition.startswith(">="):
                    min_len = int(condition[2:])
                    assert actual_len >= min_len, f"[{测试点}] {key}长度应>={min_len}, 实际={actual_len}"
                elif condition.startswith("<="):
                    max_len = int(condition[2:])
                    assert actual_len <= max_len, f"[{测试点}] {key}长度应<={max_len}, 实际={actual_len}"
                elif condition.startswith(">"):
                    min_len = int(condition[1:])
                    assert actual_len > min_len, f"[{测试点}] {key}长度应>{min_len}, 实际={actual_len}"
                elif condition.startswith("<"):
                    max_len = int(condition[1:])
                    assert actual_len < max_len, f"[{测试点}] {key}长度应<{max_len}, 实际={actual_len}"
                elif condition.startswith("==") or condition.startswith("="):
                    exp_len = int(condition.lstrip("= "))
                    assert actual_len == exp_len, f"[{测试点}] {key}长度应={exp_len}, 实际={actual_len}"
                logger.info(f"[{测试点}] 长度断言通过: {key}长度={actual_len}")

            # 普通不等断言: code!=200
            elif "!=" in cond:
                key, value = cond.split("!=", 1)
                actual = str(self.get_value(key.strip()))
                expected = value.strip()
                assert actual != expected, f"[{测试点}] {key}不应等于{expected}, 实际={actual}"

            # 普通等值断言: code=200
            elif "=" in cond:
                key, value = cond.split("=", 1)
                actual = str(self.get_value(key.strip()))
                expected = value.strip()
                assert actual == expected, f"[{测试点}] {key}应等于{expected}, 实际={actual}"

            # 兜底：直接包含
            else:
                assert cond in str(self.result), f"[{测试点}] 预期包含'{cond}', 实际={self.result}"

        logger.info(f"[{测试点}] 断言通过: {expected_str}")

    def assert_not_empty(self, key, 字段名=""):
        """
        断言字段非空
        None、空字符串、空列表、空字典都算空

        Args:
            key: 键路径，如 "data.name"
            字段名: 中文名，用于报错提示

        用法:
            ae.assert_not_empty("data.name", "品牌名")
            ae.assert_not_empty("data.list", "品牌列表")
        """
        value = self.get_value(key)
        label = 字段名 or key

        if value is None:
            assert False, f"[{label}] 字段为None"
        if isinstance(value, str) and value.strip() == "":
            assert False, f"[{label}] 字段为空字符串"
        if isinstance(value, list) and len(value) == 0:
            assert False, f"[{label}] 字段为空列表"
        if isinstance(value, dict) and len(value) == 0:
            assert False, f"[{label}] 字段为空字典"

        logger.info(f"[{label}] 断言非空通过, 值={value}")

    def assert_contains(self, key, expected, 字段名=""):
        """
        断言字段包含某个值

        Args:
            key: 键路径
            expected: 期望包含的值
            字段名: 中文名

        用法:
            ae.assert_contains("message", "成功", "提示信息")
        """
        value = self.get_value(key)
        label = 字段名 or key

        assert value is not None, f"[{label}] 字段不存在"
        assert expected in value, f"[{label}] 未包含'{expected}', 实际={value}"

        logger.info(f"[{label}] 断言包含通过, 包含'{expected}'")

    def assert_type(self, key, expected_type, 字段名=""):
        """
        断言字段类型

        Args:
            key: 键路径
            expected_type: 期望的类型，如 int、str、list、dict
            字段名: 中文名

        用法:
            ae.assert_type("code", int, "状态码")
            ae.assert_type("data", dict, "数据体")
        """
        value = self.get_value(key)
        label = 字段名 or key

        assert value is not None, f"[{label}] 字段不存在"
        assert isinstance(value, expected_type), f"[{label}] 类型应为{expected_type.__name__}, 实际={type(value).__name__}, 值={value}"

        logger.info(f"[{label}] 断言类型通过, 类型={expected_type.__name__}")

    def assert_length(self, key, min_len=None, max_len=None, 字段名=""):
        """
        断言列表/字典/字符串的长度

        Args:
            key: 键路径
            min_len: 最小长度（可选）
            max_len: 最大长度（可选）
            字段名: 中文名

        用法:
            ae.assert_length("data.list", min_len=1, 字段名="品牌列表")
        """
        value = self.get_value(key)
        label = 字段名 or key

        assert value is not None, f"[{label}] 字段不存在"
        actual_len = len(value)

        if min_len is not None:
            assert actual_len >= min_len, f"[{label}] 长度应>={min_len}, 实际={actual_len}"
        if max_len is not None:
            assert actual_len <= max_len, f"[{label}] 长度应<={max_len}, 实际={actual_len}"

        logger.info(f"[{label}] 断言长度通过, 长度={actual_len}")

    def find_in_list(self, key, search_field, search_value):
        """
        在列表中查找指定条件的数据，返回找到的字典

        面试经典问题：响应是一个大列表，怎么找到你要的那条数据？
        按字段名和值搜索，返回整条数据

        Args:
            key: 列表的键路径，如 "data.list"
            search_field: 要搜索的字段名，如 "name"
            search_value: 要搜索的值，如 "测试品牌"

        Returns:
            找到的字典，找不到返回None

        用法:
            brand = ae.find_in_list("data.list", "name", "测试品牌")
            if brand:
                assert brand["id"] == 60
        """
        value = self.get_value(key)

        if value is None:
            logger.warning(f"路径 '{key}' 不存在或为None")
            return None

        if not isinstance(value, list):
            logger.warning(f"路径 '{key}' 不是列表, 类型={type(value).__name__}")
            return None

        for item in value:
            if isinstance(item, dict) and item.get(search_field) == search_value:
                logger.info(f"在 '{key}' 中找到 {search_field}={search_value} 的数据")
                return item

        logger.warning(f"在 '{key}' 中未找到 {search_field}={search_value} 的数据")
        return None

    def assert_field_exists(self, key, search_field, search_value, 字段名=""):
        """
        断言列表中存在指定条件的数据
        比find_in_list多一步：找不到就报错（断言失败）

        Args:
            key: 列表的键路径
            search_field: 要搜索的字段名
            search_value: 要搜索的值
            字段名: 中文名

        用法:
            ae.assert_field_exists("data.list", "name", "万和", "品牌列表")
        """
        label = 字段名 or key
        found = self.find_in_list(key, search_field, search_value)
        assert found is not None, f"[{label}] 中未找到 {search_field}={search_value} 的数据"
        logger.info(f"[{label}] 断言存在通过: 找到 {search_field}={search_value}")
