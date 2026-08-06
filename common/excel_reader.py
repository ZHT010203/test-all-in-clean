"""
Excel测试用例读取器
1.读取文件：校验文件存在、Sheet存在
2.校验必填列：检查用户需要的列是否存在
3.清洗数据：必填列为空的行跳过，记录日志
4.转换返回：DataFrame转 list[dict]


对应函数方法：
read()    - 读取Excel，返回 list[dict]
"""
import os
import logging
import pandas as pd


class ExcelReader:
    """
    通用Excel测试用例读取器
    按列名匹配，不依赖列顺序

    示例：
        >>> reader = ExcelReader()
        >>> cases = reader.read(
        ...     file_path="Data/Test_case/品牌分页列表.xlsx",
        ...     required_cols=["测试点", "ApiPath", "接口入参", "预期结果"]
        ... )
        >>> for case in cases:
        ...     print(case["测试点"])
    """

    def read(self, file_path, required_cols=None, sheet_name=0):
        """
        读取Excel测试用例

        Args:
            file_path: Excel文件的完整路径
            required_cols: 必填列名列表，为空的行会被跳过。列的顺序无所谓，按名字匹配
            sheet_name: Sheet名或索引，默认0（第一个Sheet）

        Returns:
            list[dict]: 测试用例列表，每条是一个字典

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: Sheet不存在 或 必填列缺失
        """
        # ------------------ 第一步：读取文件 ------------------
        # 校验文件是否存在，Sheet是否存在
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            logging.info(f"读取Excel成功: {os.path.basename(file_path)}, 共{len(df)}行, 列: {list(df.columns)}")
        except FileNotFoundError:
            logging.error(f"文件不存在: {file_path}")
            raise
        except ValueError as e:
            logging.error(f"Sheet不存在或文件异常: {e}")
            raise
        except Exception as e:
            logging.error(f"读取文件未知异常: {e}")
            raise

        # ------------------ 第二步：校验必填列 ------------------
        # 新建数组，for循环判断列名是否存在
        if required_cols:
            missing = [col for col in required_cols if col not in df.columns]
            if missing:
                logging.error(f"缺失必填列: {missing}")
                raise ValueError(f"缺失必填列: {missing}, 文件: {os.path.basename(file_path)}")

        # ------------------ 第三步：清洗前先记录脏数据 ------------------
        # 两层for循环，一层if判断
        # 外层for：读取数据 pd.iterrows()
        # 内层for：遍历必填列名
        # if判断：pd.isnull() 为空则记录日志
        if required_cols:
            #iterrows()：遍历DataFrame的每一行，返回是一个二维表格
            for index, row in df.iterrows():
                for col in required_cols:
                    if pd.isnull(row[col]):
                        # Excel行号 = index + 2（索引从0开始，加上表头占1行）
                        excel_row = index + 2
                        logging.warning(f"第{excel_row}行的'{col}'为空，该行将被跳过")

            # 清洗：某行中某个必填字段为空，则丢弃这一行
            # dropna = drop + NA（Not Available），丢弃缺失值
            # subset：指定检查哪些列
            # inplace=True：直接在原DataFrame上修改
            df.dropna(subset=required_cols, inplace=True)

        # ------------------ 第四步：转换并返回 ------------------
        # 每一行变成一个字典（列名→key，单元格值→value）
        # 所有字典装进一个列表：[{第1行}, {第2行}, {第3行}]
        # orient="records"：按记录行格式，一行一个字典
        test_cases = df.to_dict(orient="records")
        logging.info(f"加载完成: 成功读取{len(test_cases)}条测试用例")
        return test_cases
