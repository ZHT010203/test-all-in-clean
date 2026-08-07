"""
测试结果回写器 - ResultWriter类
把测试结果（实际结果、断言结果、错误信息）写回Excel新文件。

对应函数方法：
collect()      - 收集单条测试结果
write_back()   - 回写所有结果到Excel新文件
"""
import os
import sys
import logging
import pandas as pd

# 支持导入Conf模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Conf.config import TEST_CASE_DIR, TEST_REPORT_DIR

logger = logging.getLogger(__name__)


class ResultWriter:
    """
    测试结果回写器

    收集每条用例的执行结果，最后一次性回写到Excel新文件。
    新增3列：实际结果、断言结果、错误信息

    示例:
        >>> writer = ResultWriter()
        >>> writer.collect(2, '{"code":200}', "PASS")
        >>> writer.collect(3, '{"code":404}', "FAIL", "$.code应等于200, 实际=404")
        >>> writer.write_back("添加品牌.xlsx")
    """

    def __init__(self):
        """初始化，创建空结果列表"""
        self.results = []

    def collect(self, row, actual_result, status, error_msg=""):
        """
        收集单条测试结果

        Args:
            row: Excel行号（从2开始，跳过表头）
            actual_result: 接口实际返回内容（字符串）
            status: "PASS" / "FAIL" / "ERROR"
            error_msg: 失败原因（PASS时为空字符串）

        用法:
            writer.collect(2, '{"code":200}', "PASS")
            writer.collect(3, '{"code":404}', "FAIL", "$.code应等于200, 实际=404")
        """
        self.results.append({
            "row": row,
            "实际结果": actual_result,
            "断言结果": status,
            "错误信息": error_msg
        })
        logger.info(f"收集第{row}行结果: {status} {error_msg}")

    def write_back(self, file_name):
        """
        回写测试结果到Excel新文件

        读取原Excel，追加3列（实际结果、断言结果、错误信息），
        按collect时的行号对应写入，保存为 原文件名_结果.xlsx

        Args:
            file_name: 原Excel文件名，如 "添加品牌.xlsx"

        用法:
            writer.write_back("添加品牌.xlsx")
            # 生成 添加品牌_结果.xlsx，保存到 Data/Test_report/ 目录
        """
        try:
            # 原文件路径
            src_path = os.path.join(TEST_CASE_DIR, file_name)
            # 新文件名：去掉.xlsx后缀加_结果.xlsx
            base_name = file_name.rsplit(".xlsx", 1)[0]
            new_file_name = f"{base_name}_结果.xlsx"

            # 报告目录：不存在则自动创建
            os.makedirs(TEST_REPORT_DIR, exist_ok=True)
            dst_path = os.path.join(TEST_REPORT_DIR, new_file_name)

            # 读取原Excel
            df = pd.read_excel(src_path)
            logger.info(f"读取原文件成功: {file_name}, 共{len(df)}行, 列: {list(df.columns)}")

            # 新增3列，默认空值
            df["实际结果"] = ""
            df["断言结果"] = ""
            df["错误信息"] = ""

            # 按行号写入结果（行号从2开始，对应DataFrame索引 = 行号 - 2）
            for item in self.results:
                idx = item["row"] - 2
                if 0 <= idx < len(df):
                    df.at[idx, "实际结果"] = item["实际结果"]
                    df.at[idx, "断言结果"] = item["断言结果"]
                    df.at[idx, "错误信息"] = item["错误信息"]

            # 保存到报告目录
            df.to_excel(dst_path, index=False)
            logger.info(f"结果回写完成: {dst_path}, 共写入{len(self.results)}条结果")

        except Exception as e:
            logger.error(f"回写Excel失败: {e}")
            raise
