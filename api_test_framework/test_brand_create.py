"""
商品品牌接口管理
01：新增品牌
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.assertion import AssertEngine
from common.result_writer import ResultWriter
from common.runner import ConcurrentRunner


def test_brand_create(read_excel, admin_client, db_client):
    """
    新增品牌
    """
    # 读取测试用例
    cases = read_excel(
        file_name="添加品牌.xlsx",
        required_cols=["ApiPath", "接口入参", "预期结果"]
    )

    # 实例化回写器、并发执行器
    writer = ResultWriter()
    runner = ConcurrentRunner(max_workers=5)

    # 处理单个用例：只返回结果元组，不碰共享状态（不调writer.collect）
    def run_one(task):
        i, case = task
        excel_row = i + 2  # Excel行号（跳过表头，从2开始）
        测试点 = case.get("测试点", "")

        try:
            # 解析入参
            case["接口入参"] = json.loads(case["接口入参"])

            # 调用接口
            resp = admin_client.post(
                url=case["ApiPath"],
                json=case["接口入参"]
            )

            # 拿到响应JSON
            result = resp.json()

            # 实例化断言引擎，断言
            ae = AssertEngine(result)
            ae.assert_result(case["预期结果"], 测试点)

            # 断言通过
            return (excel_row, str(result), "PASS", "")

        except AssertionError as e:
            # 断言失败
            return (excel_row, str(result) if 'result' in locals() else "", "FAIL", str(e))

        except Exception as e:
            # 接口异常
            return (excel_row, "", "ERROR", str(e))

    # 构造任务列表：[(0, case0), (1, case1), ...]
    tasks = list(enumerate(cases))

    # 并发执行（整体超时60秒，超时后剩余任务取消）
    results = runner.run(tasks, run_one, timeout=60)

    # 主线程串行收集结果
    for row, actual, status, err in results:
        writer.collect(row, actual, status, err)

    # 回写结果到新Excel文件
    writer.write_back("添加品牌.xlsx")
