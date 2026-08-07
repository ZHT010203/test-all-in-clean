"""
并发执行器 - ConcurrentRunner类
用线程池并发跑多个任务，支持超时、异常兜底、结果统计、进度回调。

对应函数方法：
run() - 并发执行任务列表，返回结果列表（按行号排序）
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class ConcurrentRunner:
    """
    并发执行器

    用 ThreadPoolExecutor 并发执行任务，支持4个进阶能力：
    - 超时控制：整体超时秒数，超时后取消剩余任务
    - 异常兜底：func 忘了 try 也不会崩，自动转成 ERROR 结果
    - 结果统计：执行完打印 PASS/FAIL/ERROR 数量
    - 进度回调：每完成一条打印 [已完成/总数]

    示例:
        runner = ConcurrentRunner(max_workers=5)
        results = runner.run(tasks, run_one, timeout=60)
        # results 按 row 升序排序
    """

    def __init__(self, max_workers=5):
        """
        初始化并发执行器

        Args:
            max_workers: 线程池最大并发数，默认5
        """
        self.max_workers = max_workers

    def run(self, tasks, func, timeout=None):
        """
        并发执行任务列表

        用 as_completed 谁完成谁先返回（不保证顺序），最后按 row 排序。
        支持4个进阶能力：超时、异常兜底、结果统计、进度回调。

        Args:
            tasks: 任务列表，每个元素会作为参数传给 func
            func: 处理单个任务的函数，接收一个 task，返回结果元组 (row, actual, status, err)
            timeout: 整体超时秒数，None 表示不限制。超时后剩余任务标记 ERROR 并取消

        Returns:
            结果列表，按 row 升序排序

        用法:
            runner = ConcurrentRunner(max_workers=5)
            results = runner.run(tasks, run_one, timeout=60)
        """
        total = len(tasks)
        results = []
        stats = {"PASS": 0, "FAIL": 0, "ERROR": 0}

        timeout_msg = f"，超时={timeout}秒" if timeout else ""
        logger.info(f"开始并发执行，共{total}个任务，最大并发={self.max_workers}{timeout_msg}")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # submit 提交所有任务，建立 future → task 映射
            future_to_task = {executor.submit(func, t): t for t in tasks}
            done_count = 0

            try:
                # as_completed 谁完成谁先返回，timeout 是整体超时
                for future in as_completed(future_to_task, timeout=timeout):
                    task = future_to_task[future]
                    i, _ = task
                    row = i + 2
                    done_count += 1

                    try:
                        # func 正常返回结果元组
                        result = future.result()
                    except Exception as e:
                        # 异常兜底：func 忘了 try 或任务异常，这里接住
                        result = (row, "", "ERROR", f"任务异常: {e}")

                    results.append(result)
                    stats[result[2]] = stats.get(result[2], 0) + 1
                    logger.info(f"进度: [{done_count}/{total}] 第{row}行 {result[2]}")

            except TimeoutError:
                # 整体超时，取消剩余未完成的任务，标记为 ERROR
                logger.warning(f"整体超时{timeout}秒，已完成{done_count}/{total}，剩余取消")
                for future, task in future_to_task.items():
                    if not future.done():
                        future.cancel()
                        i, _ = task
                        row = i + 2
                        results.append((row, "", "ERROR", "执行超时"))
                        stats["ERROR"] += 1

        # 按 row 升序排序（as_completed 不保证顺序）
        results.sort(key=lambda r: r[0])

        logger.info(f"执行完成: 通过{stats['PASS']} 失败{stats['FAIL']} 异常{stats['ERROR']}")
        return results
