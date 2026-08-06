"""
数据库客户端封装
1.连接池管理：自动复用连接，提高性能
2.自动资源管理：自动关闭游标和连接，无需手动管理
3.统一异常处理：捕获pymysql异常，记录详细日志
4.SQL日志记录：记录SQL语句、参数、执行时间、影响行数
5.便捷方法：提供insert、update、delete等便捷方法


对应函数方法：
查询：fetchone(单条)、fetchall（多条列表）
插入：insert
更新：update
删除：delete
关闭：close()
"""
import time
import logging
from typing import Optional, Dict, List, Any, Tuple
import pymysql
from pymysql.cursors import DictCursor
from pymysql import Error as PyMySQLError

# 尝试导入DBUtils连接池，如果失败则使用简单实现
try:
    from dbutils.pooled_db import PooledDB
    USE_POOL = True
except ImportError:
    USE_POOL = False
    import queue
    logging.warning("⚠️ DBUtils未安装，使用简单连接池实现")


class DatabaseError(Exception):
    """数据库操作异常基类"""
    pass


class DBClient:
    """
    专业的数据库客户端封装类

    提供统一的数据库操作处理，包括：
    - 连接池管理
    - 自动资源管理（上下文管理器）
    - 统一异常处理
    - SQL日志记录
    - 便捷方法（insert/update/delete）

    示例：
        >>> client = DBClient(
        ...     db_config={'host': 'localhost', 'user': 'root', ...},
        ...     pool_size=5
        ... )
        >>> result = client.fetchone("SELECT * FROM users WHERE id = %s", (1,))
        >>> print(result)
    """

    def __init__(
        self,
        db_config: Dict[str, Any],
        pool_size: int = 5
    ):
        """
        初始化DBClient实例

        Args:
            db_config: 数据库配置字典，包含host、user、password、database、port、charset等
            pool_size: 连接池大小，默认5个连接

        示例：
            >>> db_config = {
            ...     'host': 'localhost',
            ...     'user': 'root',
            ...     'password': '123456',
            ...     'database': 'test_db',
            ...     'port': 3306,
            ...     'charset': 'utf8mb4'
            ... }
            >>> client = DBClient(db_config, pool_size=5)
        """
        self.db_config = db_config
        self.pool_size = pool_size

        # 创建连接池
        if USE_POOL:
            # 使用DBUtils连接池
            self.pool = PooledDB(
                creator=pymysql,
                maxconnections=pool_size,
                cursorclass=DictCursor,
                **db_config
            )
            logging.info(
                f"🔧 DBClient初始化完成（DBUtils连接池） - "
                f"pool_size: {pool_size}"
            )
        else:
            # 使用简单的queue.Queue实现连接池
            self.pool = queue.Queue(maxsize=pool_size)
            # 预创建连接
            for _ in range(pool_size):
                conn = self._create_connection()
                self.pool.put(conn)
            logging.info(
                f"🔧 DBClient初始化完成（简单连接池） - "
                f"pool_size: {pool_size}"
            )

    def _create_connection(self):
        """
        创建新的数据库连接

        Returns:
            pymysql.Connection对象

        Raises:
            DatabaseError: 连接创建失败
        """
        try:
            conn = pymysql.connect(
                cursorclass=DictCursor,
                **self.db_config
            )
            return conn
        except PyMySQLError as e:
            error_msg = f"数据库连接创建失败: {e}"
            logging.error(f"❌ {error_msg}")
            raise DatabaseError(error_msg) from e

    def get_connection(self):
        """
        从连接池获取连接

        Returns:
            pymysql.Connection对象

        说明：
            - 如果使用DBUtils，直接从连接池获取
            - 如果使用简单连接池，从queue.Queue获取
        """
        if USE_POOL:
            return self.pool.connection()
        else:
            # 从queue获取连接，如果为空则等待
            try:
                conn = self.pool.get(timeout=30)
                # 检查连接是否有效
                conn.ping(reconnect=True)
                return conn
            except queue.Empty:
                error_msg = "连接池已耗尽，无法获取连接"
                logging.error(f"❌ {error_msg}")
                raise DatabaseError(error_msg)

    def execute(
        self,
        sql: str,
        params: Optional[Tuple] = None
    ) -> int:
        """
        执行SQL语句，返回影响行数

        Args:
            sql: SQL语句
            params: SQL参数（可选）

        Returns:
            影响的行数

        Raises:
            DatabaseError: SQL执行失败

        示例：
            >>> rowcount = client.execute("UPDATE users SET name = %s WHERE id = %s", ("张三", 1))
        """
        conn = None
        cursor = None
        try:
            # 从连接池获取连接
            conn = self.get_connection()
            cursor = conn.cursor()

            # 记录SQL执行日志
            start_time = time.time()
            cursor.execute(sql, params)
            elapsed_ms = (time.time() - start_time) * 1000

            # 提交事务
            conn.commit()

            # 记录成功日志
            logging.info(
                f"✅ SQL执行成功 - "
                f"SQL: {sql}, "
                f"参数: {params}, "
                f"耗时: {elapsed_ms:.2f}ms, "
                f"影响行数: {cursor.rowcount}"
            )

            return cursor.rowcount

        except PyMySQLError as e:
            # 回滚事务
            if conn:
                conn.rollback()

            # 记录错误日志
            error_msg = f"SQL执行失败 - SQL: {sql}, 参数: {params}, 错误: {e}"
            logging.error(f"❌ {error_msg}")
            raise DatabaseError(error_msg) from e

        finally:
            # 关闭游标
            if cursor:
                cursor.close()
            # 归还连接到连接池
            if conn:
                if USE_POOL:
                    conn.close()
                else:
                    self.pool.put(conn)
    def fetchone(
        self,
        sql: str,
        params: Optional[Tuple] = None
    ) -> Optional[Dict[str, Any]]:
        """
        查询单条记录

        Args:
            sql: SQL查询语句
            params: SQL参数（可选）

        Returns:
            查询结果（字典形式）或 None

        Raises:
            DatabaseError: 查询失败

        示例：
            >>> result = client.fetchone("SELECT * FROM users WHERE id = %s", (1,))
        """
        conn = None
        cursor = None
        try:
            # 从连接池获取连接
            conn = self.get_connection()
            cursor = conn.cursor()

            # 记录SQL执行日志
            start_time = time.time()
            cursor.execute(sql, params)
            elapsed_ms = (time.time() - start_time) * 1000

            # 获取结果
            result = cursor.fetchone()

            # 记录成功日志
            logging.info(
                f"✅ SQL查询成功（单条） - "
                f"SQL: {sql}, "
                f"参数: {params}, "
                f"耗时: {elapsed_ms:.2f}ms"
            )

            return result

        except PyMySQLError as e:
            # 记录错误日志
            error_msg = f"SQL查询失败 - SQL: {sql}, 参数: {params}, 错误: {e}"
            logging.error(f"❌ {error_msg}")
            raise DatabaseError(error_msg) from e

        finally:
            # 关闭游标
            if cursor:
                cursor.close()
            # 归还连接到连接池
            if conn:
                if USE_POOL:
                    conn.close()
                else:
                    self.pool.put(conn)

    def fetchall(
        self,
        sql: str,
        params: Optional[Tuple] = None
    ) -> List[Dict[str, Any]]:
        """
        查询多条记录

        Args:
            sql: SQL查询语句
            params: SQL参数（可选）

        Returns:
            查询结果列表（字典列表）

        Raises:
            DatabaseError: 查询失败

        示例：
            >>> results = client.fetchall("SELECT * FROM users WHERE age > %s", (18,))
        """
        conn = None
        cursor = None
        try:
            # 从连接池获取连接
            conn = self.get_connection()
            cursor = conn.cursor()

            # 记录SQL执行日志
            start_time = time.time()
            cursor.execute(sql, params)
            elapsed_ms = (time.time() - start_time) * 1000

            # 获取结果
            results = cursor.fetchall()

            # 记录成功日志
            logging.info(
                f"✅ SQL查询成功（多条） - "
                f"SQL: {sql}, "
                f"参数: {params}, "
                f"耗时: {elapsed_ms:.2f}ms, "
                f"结果数: {len(results)}"
            )

            return results

        except PyMySQLError as e:
            # 记录错误日志
            error_msg = f"SQL查询失败 - SQL: {sql}, 参数: {params}, 错误: {e}"
            logging.error(f"❌ {error_msg}")
            raise DatabaseError(error_msg) from e

        finally:
            # 关闭游标
            if cursor:
                cursor.close()
            # 归还连接到连接池
            if conn:
                if USE_POOL:
                    conn.close()
                else:
                    self.pool.put(conn)

    def insert(self, table: str, data: Dict[str, Any]) -> int:
        """
        插入单条记录

        Args:
            table: 表名
            data: 要插入的数据（字典形式）

        Returns:
            新插入记录的ID（lastrowid）

        Raises:
            DatabaseError: 插入失败

        示例：
            >>> last_id = client.insert("users", {"name": "张三", "age": 25})
        """
        # 自动生成INSERT SQL
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        params = tuple(data.values())

        conn = None
        cursor = None
        try:
            # 从连接池获取连接
            conn = self.get_connection()
            cursor = conn.cursor()

            # 记录SQL执行日志
            start_time = time.time()
            cursor.execute(sql, params)
            elapsed_ms = (time.time() - start_time) * 1000

            # 提交事务
            conn.commit()

            # 获取新插入记录的ID
            lastrowid = cursor.lastrowid

            # 记录成功日志
            logging.info(
                f"✅ SQL执行成功（INSERT） - "
                f"SQL: {sql}, "
                f"参数: {params}, "
                f"耗时: {elapsed_ms:.2f}ms, "
                f"新记录ID: {lastrowid}"
            )

            return lastrowid

        except PyMySQLError as e:
            # 回滚事务
            if conn:
                conn.rollback()

            # 记录错误日志
            error_msg = f"SQL执行失败 - SQL: {sql}, 参数: {params}, 错误: {e}"
            logging.error(f"❌ {error_msg}")
            raise DatabaseError(error_msg) from e

        finally:
            # 关闭游标
            if cursor:
                cursor.close()
            # 归还连接到连接池
            if conn:
                if USE_POOL:
                    conn.close()
                else:
                    self.pool.put(conn)

    def update(
        self,
        table: str,
        data: Dict[str, Any],
        where: str,
        where_params: Optional[Tuple] = None
    ) -> int:
        """
        更新记录

        Args:
            table: 表名
            data: 要更新的数据（字典形式）
            where: WHERE条件语句（不含WHERE关键字）
            where_params: WHERE条件参数（可选）

        Returns:
            影响的行数

        Raises:
            DatabaseError: 更新失败

        示例：
            >>> rowcount = client.update(
            ...     "users",
            ...     {"name": "李四"},
            ...     "id = %s",
            ...     (1,)
            ... )
        """
        # 自动生成UPDATE SQL
        set_clause = ', '.join([f"{k} = %s" for k in data.keys()])
        sql = f"UPDATE {table} SET {set_clause} WHERE {where}"

        # 合并参数
        params = tuple(data.values()) + (where_params if where_params else ())

        return self.execute(sql, params)

    def delete(
        self,
        table: str,
        where: str,
        where_params: Optional[Tuple] = None
    ) -> int:
        """
        删除记录

        Args:
            table: 表名
            where: WHERE条件语句（不含WHERE关键字）
            where_params: WHERE条件参数（可选）

        Returns:
            影响的行数

        Raises:
            DatabaseError: 删除失败

        示例：
            >>> rowcount = client.delete("users", "id = %s", (1,))
        """
        # 自动生成DELETE SQL
        sql = f"DELETE FROM {table} WHERE {where}"
        params = where_params

        return self.execute(sql, params)

    def query(
        self,
        sql: str,
        params: Optional[Tuple] = None
    ) -> List[Dict[str, Any]]:
        """
        查询记录（别名方法，与fetchall一致）

        Args:
            sql: SQL查询语句
            params: SQL参数（可选）

        Returns:
            查询结果列表（字典列表）

        Raises:
            DatabaseError: 查询失败

        示例：
            >>> results = client.query("SELECT * FROM users")
        """
        return self.fetchall(sql, params)

    def executemany(
        self,
        sql: str,
        params_list: List[Tuple]
    ) -> int:
        """
        批量执行SQL

        Args:
            sql: SQL语句
            params_list: 参数列表

        Returns:
            影响的行数

        Raises:
            DatabaseError: 执行失败

        示例：
            >>> sql = "INSERT INTO users (name, age) VALUES (%s, %s)"
            >>> params_list = [("张三", 25), ("李四", 30)]
            >>> rowcount = client.executemany(sql, params_list)
        """
        conn = None
        cursor = None
        try:
            # 从连接池获取连接
            conn = self.get_connection()
            cursor = conn.cursor()

            # 记录SQL执行日志
            start_time = time.time()
            cursor.executemany(sql, params_list)
            elapsed_ms = (time.time() - start_time) * 1000

            # 提交事务
            conn.commit()

            # 记录成功日志
            logging.info(
                f"✅ SQL批量执行成功 - "
                f"SQL: {sql}, "
                f"批次大小: {len(params_list)}, "
                f"耗时: {elapsed_ms:.2f}ms, "
                f"影响行数: {cursor.rowcount}"
            )

            return cursor.rowcount

        except PyMySQLError as e:
            # 回滚事务
            if conn:
                conn.rollback()

            # 记录错误日志
            error_msg = f"SQL批量执行失败 - SQL: {sql}, 错误: {e}"
            logging.error(f"❌ {error_msg}")
            raise DatabaseError(error_msg) from e

        finally:
            # 关闭游标
            if cursor:
                cursor.close()
            # 归还连接到连接池
            if conn:
                if USE_POOL:
                    conn.close()
                else:
                    self.pool.put(conn)

    def close(self) -> None:
        """
        关闭连接池，释放资源

        说明：
            在测试结束时调用，确保所有连接正确关闭
        """
        if USE_POOL:
            # DBUtils连接池无需手动关闭
            logging.info("🔌 DBClient连接池已关闭（DBUtils自动管理）")
        else:
            # 手动关闭简单连接池中的所有连接
            while not self.pool.empty():
                conn = self.pool.get()
                conn.close()
            logging.info("🔌 DBClient连接池已关闭（手动关闭所有连接）")

    def __enter__(self):
        """
        支持上下文管理器协议

        示例：
            >>> with DBClient(db_config) as client:
            ...     result = client.fetchone("SELECT * FROM users")
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        退出上下文时自动关闭连接池
        """
        self.close()