"""

executor.py — 万能跑用例机器

- 原来你测一个接口要写一个 test_xxx.py （像 test_brand_create.py 那样一堆代码）。
- 有了它，以后加新接口测试 只加 Excel，不写 Python ： executor.run("xxx.xlsx") 一行搞定。
- 它把"读Excel→发请求→断言→回写"全自动串起来。
- 类比 ：像全自动洗衣机，你扔衣服进去按个按钮就行，不用自己搓。
通用接口测试执行器 - ApiExecutor类
读取Excel用例后自动执行任意接口，新增接口测试无需写Python代码。

把 ExcelReader（读用例）、HTTPClient（发请求）、AssertEngine（断言）、
ConcurrentRunner（并发）、ResultWriter（回写）串成一个完整流程：
    读Excel → 并发跑每条用例 → 收集结果 → 回写新Excel

对应函数方法：
run() - 执行一个Excel用例文件，自动并发、断言、回写

用法示例：
    from common.executor import ApiExecutor
    executor = ApiExecutor(admin_client)
    executor.run("添加品牌.xlsx")
"""
import os
import sys
import json
import logging

# 支持导入Conf模块（参考 result_writer.py 第14-16行）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Conf.config import TEST_CASE_DIR
from common.excel_reader import ExcelReader
from common.http_client import HTTPClient
from common.assertion import AssertEngine
from common.result_writer import ResultWriter
from common.runner import ConcurrentRunner
from common.context import TestContext

logger = logging.getLogger(__name__)


def _is_blank(val):
    """Excel单元格是否为空（None / NaN / 空字符串）"""
    if val is None:
        return True
    if isinstance(val, float) and val != val:  # NaN: 唯一不等于自身的值
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    return False


def _parse_extract_rules(extract_str):
    """
    解析"提取"列字符串，返回 [(变量名, jsonpath), ...]

    格式：变量名=jsonpath;变量名2=jsonpath2
    例：brand_id=$.data.id;brand_name=$.data.name
    """
    rules = []
    for item in str(extract_str).split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue
        name, path = item.split("=", 1)
        rules.append((name.strip(), path.strip()))
    return rules


class ApiExecutor:
    """
    通用接口测试执行器

    接收一个已配置好的 HTTPClient 实例（含 token），读取 Excel 用例后
    自动执行任意接口，新增接口测试只需在 Excel 里加一行，无需写 Python。

    支持的 Excel 列：
        - ApiPath:   接口路径（必填）
        - 接口入参:   JSON字符串（必填），支持 ${变量名} 占位符
        - 预期结果:   断言条件字符串（必填）
        - Method:    HTTP方法，可选，默认 POST
        - 测试点:    测试点名称，可选，用于日志提示
        - 提取:      可选，链路用例变量提取，格式 变量名=jsonpath，
                     多个用分号分隔，如 brand_id=$.data.id;brand_name=$.data.name

    链路用例（含"提取"列或入参含 ${）自动走串行执行：前一条提取的变量
    给后一条用。普通用例仍并发执行。

    示例:
        >>> from common.executor import ApiExecutor
        >>> executor = ApiExecutor(admin_client)
        >>> executor.run("添加品牌.xlsx")
    """

    def __init__(self, http_client, max_workers=5):
        """
        初始化ApiExecutor

        Args:
            http_client: 已配置好的 HTTPClient 实例（含 token、base_url）
            max_workers: 并发线程数，默认5
        """
        self.http_client = http_client
        self.max_workers = max_workers
        self.reader = ExcelReader()
        logger.info(f"ApiExecutor初始化完成, max_workers={max_workers}")

    def _execute_case(self, case, context=None):
        """
        执行单条用例的核心逻辑：解析入参→发请求→断言→（串行时提取变量）

        串行分支传入context：执行前对入参/路径做 ${var} 变量替换，
        执行后按"提取"列把响应字段提取为变量给下一条用例用。
        并发分支不传context，保持原逻辑（不替换、不提取）。

        Args:
            case: 单条用例字典
            context: TestContext实例，None表示不做变量替换和提取

        Returns:
            (status, actual, err) 三元组，status为 PASS/FAIL/ERROR
        """
        测试点 = case.get("测试点", "")
        result = None
        try:
            # 入参字符串（串行分支先做 ${var} 变量替换，再 json.loads）
            payload_str = str(case["接口入参"])
            if context is not None:
                payload_str = context.resolve(payload_str)
            payload = json.loads(payload_str)

            # 请求方法和路径（串行分支路径也替换，支持 /brand/${brand_id}）
            method = str(case.get("Method", "POST")).upper()
            url = str(case["ApiPath"])
            if context is not None:
                url = context.resolve(url)

            # 按 method 调用对应的HTTP方法
            if method == "GET":
                resp = self.http_client.get(url, params=payload)
            elif method == "POST":
                resp = self.http_client.post(url, json=payload)
            elif method == "PUT":
                resp = self.http_client.put(url, json=payload)
            elif method == "DELETE":
                resp = self.http_client.delete(url, json=payload)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")

            # 拿到响应JSON
            result = resp.json()

            # 断言
            ae = AssertEngine(result)
            ae.assert_result(case["预期结果"], 测试点)

            # 串行分支：执行后按"提取"列提取变量，给下一条用例用
            if context is not None:
                extract_str = case.get("提取")
                if not _is_blank(extract_str):
                    for name, path in _parse_extract_rules(extract_str):
                        context.extract(name, path, result)

            # 断言通过
            return ("PASS", str(result), "")

        except AssertionError as e:
            # 断言失败
            return ("FAIL", str(result) if result is not None else "", str(e))

        except Exception as e:
            # 接口异常（json解析失败、请求失败、响应非JSON等）
            return ("ERROR", "", str(e))

    def _needs_serial(self, cases):
        """
        检测用例列表是否需要串行执行（链路用例）

        任一条用例满足以下之一即判定为链路用例，走串行分支：
            - 有非空"提取"列（要把响应字段提取给下一条）
            - 入参含 ${ 占位符（要引用上一条提取的变量）
        """
        for case in cases:
            if not _is_blank(case.get("提取")):
                return True
            入参 = str(case.get("接口入参", ""))
            if "${" in 入参:
                return True
        return False

    def run(self, file_name, required_cols=None, timeout=60):
        """
        执行一个Excel用例文件，自动断言、回写结果

        链路用例（含"提取"列或入参含 ${ 占位符）走串行执行：维护一个
        TestContext，前一条提取的变量给后一条用。普通用例保持并发执行。
        两种分支最终都回写到新Excel文件。

        流程：
            1. 拼接文件路径，用 ExcelReader 读取用例
            2. 检测是否链路用例：是→串行分支（TestContext传变量）；
               否→并发分支（ConcurrentRunner）
            3. 收集结果回写到新Excel文件

        Args:
            file_name: Excel文件名，如 "添加品牌.xlsx"
            required_cols: 必填列名列表，默认 ["ApiPath", "接口入参", "预期结果"]
            timeout: 并发分支整体超时秒数，默认60秒

        Returns:
            结果列表 [(row, actual, status, err), ...]，按行号升序
        """
        # 1. 拼接路径，读取用例
        file_path = os.path.join(TEST_CASE_DIR, file_name)
        if required_cols is None:
            required_cols = ["ApiPath", "接口入参", "预期结果"]

        cases = self.reader.read(file_path, required_cols=required_cols)
        logger.info(f"读取用例完成: {file_name}, 共{len(cases)}条")

        # 2. 检测链路用例，选择执行分支
        if self._needs_serial(cases):
            # ===== 串行分支：链路用例顺序执行，TestContext传变量 =====
            logger.info(f"检测到链路用例，走串行执行分支: {file_name}")
            context = TestContext()
            results = []
            total = len(cases)
            for i, case in enumerate(cases):
                excel_row = i + 2  # Excel行号（跳过表头，从2开始）
                status, actual, err = self._execute_case(case, context=context)
                results.append((excel_row, actual, status, err))
                logger.info(f"进度: [{i + 1}/{total}] 第{excel_row}行 {status}")
        else:
            # ===== 并发分支：普通用例保持原逻辑 =====
            tasks = list(enumerate(cases))

            def _run_one(task):
                i, case = task
                excel_row = i + 2  # Excel行号（跳过表头，从2开始）
                status, actual, err = self._execute_case(case)
                return (excel_row, actual, status, err)

            runner = ConcurrentRunner(max_workers=self.max_workers)
            results = runner.run(tasks, _run_one, timeout=timeout)

        # 3. 收集结果并回写
        writer = ResultWriter()
        for row, actual, status, err in results:
            writer.collect(row, actual, status, err)
        writer.write_back(file_name)

        return results
