"""
测试上下文 - TestContext类
多接口链路测试的变量传递核心：前一个接口的响应字段提取为变量，后一个接口的入参用 ${变量名} 引用。

典型链路场景（新增→查询→删除）：
    1. 新增品牌接口返回 {"data": {"id": 10086}}
    2. 提取列填 brand_id=$.data.id，存入 context.vars["brand_id"] = 10086
    3. 删除接口入参填 {"id": ${brand_id}}，执行前 resolve 替换为 {"id": 10086}

对应函数方法：
extract()   - 从接口响应里用jsonpath提取变量存入上下文
resolve()   - 把字符串里的 ${name} 占位符替换为变量值
clear()     - 清空所有变量

用法示例：
    from common.context import TestContext

    ctx = TestContext()
    # 从第1个接口的响应里提取变量
    ctx.extract('brand_id', '$.data.id', {'data': {'id': 10086}})
    print(ctx.vars)                       # {'brand_id': 10086}

    # 第2个接口的入参/路径引用变量
    print(ctx.resolve('/brand/${brand_id}'))            # /brand/10086
    print(ctx.resolve('{"id": ${brand_id}}'))            # {"id": 10086}

    ctx.clear()
    print(ctx.vars)                       # {}
"""
import re
import logging

from jsonpath_ng.ext import parse

logger = logging.getLogger(__name__)

# 匹配 ${变量名}，变量名只允许字母、数字、下划线
_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


class TestContext:
    """
    多接口链路测试上下文
    - 给你说的**第3阶段（多接口链路）**用的。
- 场景：先调"新增品牌"拿到 id=10086 → 再调"删除品牌"要用这个 id。context 就是存 id 的中转站。
- 两个方法： extract （把响应里的值存进来）、 resolve （把 ${brand_id} 替换成 10086）。
- 类比 ：像快递柜，A接口把东西存进去，B接口凭取件码来拿。

    维护一个 vars 字典，用于在串行执行的多个接口之间传递变量。
    - extract：把接口响应里的字段提取为变量
    - resolve：把字符串里的 ${变量名} 替换为变量值

    示例：
        >>> ctx = TestContext()
        >>> ctx.extract('brand_id', '$.data.id', {'data': {'id': 10086}})
        >>> ctx.resolve('/brand/${brand_id}')
        '/brand/10086'
    """

    def __init__(self):
        """初始化，创建空变量字典"""
        self.vars = {}

    def extract(self, name, jsonpath, result):
        """
        从接口响应里用jsonpath提取变量，存入上下文

        Args:
            name: 变量名，后续用 ${name} 引用
            jsonpath: jsonpath表达式，如 "$.data.id"
            result: 接口响应字典

        取不到值时打warning，不报错（链路可能仍想继续往下跑）

        用法：
            ctx.extract('brand_id', '$.data.id', resp.json())
        """
        try:
            expr = parse(jsonpath)
            matches = expr.find(result)
            if matches:
                value = matches[0].value
                self.vars[name] = value
                logger.info(f"提取变量: {name}={value} (path={jsonpath})")
            else:
                logger.warning(f"提取变量失败: {name} 未匹配到值 (path={jsonpath})")
        except Exception as e:
            logger.warning(f"提取变量异常: {name}, path={jsonpath}, 错误: {e}")

    def resolve(self, template):
        """
        把字符串里的 ${变量名} 替换为变量值

        支持一个字符串里多个 ${var}，如 "/brand/${brand_id}/item/${item_id}"。
        变量不存在则保留原 ${name} 并打warning（不报错，方便定位）。

        Args:
            template: 含 ${变量名} 占位符的字符串

        Returns:
            替换后的字符串

        用法：
            ctx.resolve('/brand/${brand_id}')           # /brand/10086
            ctx.resolve('{"id": ${brand_id}}')           # {"id": 10086}
        """
        def _replace(match):
            name = match.group(1)
            if name in self.vars:
                return str(self.vars[name])
            logger.warning(f"变量不存在，保留原占位符: ${{{name}}}")
            return match.group(0)

        return _VAR_PATTERN.sub(_replace, template)

    def clear(self):
        """清空所有变量"""
        self.vars = {}
        logger.info("上下文变量已清空")
