"""
商品品牌接口管理
01：新增品牌
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.assertion import AssertEngine


def test_brand_create(read_excel, admin_client, db_client):
    """
    新增品牌
    """
    #================= 读取测试用例 ==================
    cases = read_excel(
        file_name="添加品牌.xlsx",
        required_cols=["ApiPath", "接口入参", "预期结果"]
    )

    #================= 逐条执行 ==================
    for case in cases:
        #解析入参
        case["接口入参"] = json.loads(case["接口入参"])

        #调用接口
        resp = admin_client.post(
            url=case["ApiPath"],
            json=case["接口入参"]
        )

        #拿到响应JSON
        result = resp.json()

        #实例化断言引擎，result只传一次
        ae = AssertEngine(result)

        #用预期结果列进行断言
        ae.assert_result(case["预期结果"], case.get("测试点", ""))
    


       