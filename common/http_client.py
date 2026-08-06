"""
封装requests
1.统一请求头注入：Token、App-Code 自动拼接
2.异常重试：网络抖动时自动重试，最多3次，间隔递增
3.超时设置：统一超时30秒，避免某个接口卡死拖垮整个测试
4.日志记录：每个请求的入参、响应、耗时都记录到日志
5.状态码检查：自动检查 HTTP 状态码，非 200 的直接抛异常


对应函数方法：
更新请求头：set_headers()
合并请求头：merge_headers()
request() - 统一请求方法
url是get请求：get()
url是post请求：post()
url是put请求：put()
url是delete请求：delete()
关闭session：close()
"""
import time
import logging
import functools
from typing import Optional, Dict, Any
from urllib.parse import urljoin
import requests
from requests.exceptions import RequestException, HTTPError


def retry_on_network_error(max_retries: int = 3):
    """
    重试装饰器：仅对网络异常进行重试，不对业务异常重试

    Args:
        max_retries: 最大重试次数，默认3次

    Returns:
        装饰后的函数
    """
    def decorator(func):
        # @functools.wraps(func)
        # 保留原函数的元信息（如函数名、文档字符串等）
        #固定写法
        @functools.wraps(func)
        # 接收任意参数
        # *args, **kwargs这个两个参数实现
        def wrapper(self, *args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):  # 总共尝试 max_retries + 1 次
                try:
                    return func(self, *args, **kwargs)
                except HTTPError as e:
                    # HTTPError是业务异常（401/404/500等），不重试，直接抛出
                    logging.error(f"❌ 业务异常，不重试: status_code={e.response.status_code if e.response else 'N/A'}")
                    raise e
                except RequestException as e:
                    last_exception = e

                    # 如果是最后一次尝试，不再重试，直接抛出异常
                    if attempt == max_retries:
                        logging.error(f"❌ 请求失败，已达到最大重试次数 {max_retries} 次: {e}")
                        raise e

                    # 指数退避策略：第1次等1秒，第2次等2秒，第3次等4秒
                    #为什么不用info，而是用warning,其实两个都行，
                    #只不过warning更符合重试的场景。
                    wait_time = 2 ** attempt
                    logging.warning(
                        f"⚠️ 请求失败（第 {attempt + 1} 次尝试），"
                        f"{wait_time}秒后重试: {e}"
                    )
                    time.sleep(wait_time)

            # 理论上不会执行到这里，但为了代码完整性
            raise last_exception
        return wrapper
    return decorator


class HTTPClient:
    """
    专业的HTTP客户端封装类

    提供统一的HTTP请求处理，包括：
    - 请求头自动管理
    - 异常自动重试（指数退避）
    - 超时控制
    - 日志记录
    - 状态码检查

    示例：
        >>> client = HTTPClient(
        ...     base_url="https://api.example.com",
        ...     default_headers={"Authorization": "Bearer token"},
        ...     timeout=30,
        ...     max_retries=3
        ... )
        >>> response = client.get("/users/123")
        >>> print(response.json())
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        default_headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        初始化HTTPClient实例

        Args:
            base_url: 基础URL，用于自动拼接相对路径
            default_headers: 默认请求头，每个请求都会自动携带
            timeout: 默认超时时间（秒），默认30秒
            max_retries: 最大重试次数，默认3次
        """
        self.base_url = base_url.rstrip('/') if base_url else None
        self.default_headers = default_headers or {}
        self.timeout = timeout
        self.max_retries = max_retries

        # 使用Session复用连接，提高性能
        self.session = requests.Session()

        logging.info(
            f"🔧 HTTPClient初始化完成 - "
            f"base_url: {self.base_url}, "
            f"timeout: {self.timeout}s, "
            f"max_retries: {self.max_retries}"
        )

    def set_headers(self, headers: Dict[str, str]) -> None:
        """
        更新默认请求头

        Args:
            headers: 要添加或更新的请求头字典

        示例：
            >>> client.set_headers({"X-Custom-Header": "value"})
        """
        self.default_headers.update(headers)
        logging.info(f"✅ 更新默认请求头: {headers}")

    def _merge_headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        合并默认请求头和自定义请求头

        Args:
            custom_headers: 自定义请求头

        Returns:
            合并后的请求头字典

        说明：
            - 自定义请求头会覆盖默认请求头中的同名项
            - 如果没有自定义请求头，返回默认请求头的副本
        """
        merged = self.default_headers.copy()
        if custom_headers:
            merged.update(custom_headers)
        return merged

    def _build_url(self, url: str) -> str:
        """
        构建完整的请求URL

        Args:
            url: 请求路径或完整URL

        Returns:
            完整的请求URL

        说明：
            - 如果url已经是完整URL（以http://或https://开头），直接返回
            - 如果配置了base_url，将base_url和url拼接
            - 否则直接返回url
        """
        if url.startswith(('http://', 'https://')):
            return url

        if self.base_url:
            return urljoin(self.base_url + '/', url.lstrip('/'))

        return url

    @retry_on_network_error(max_retries=3)
    def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> requests.Response:
        """
        统一的请求方法，所有HTTP方法都通过此方法发送请求

        Args:
            method: HTTP方法（GET、POST、PUT、DELETE等）
            url: 请求路径或完整URL
            headers: 自定义请求头（可选，会与默认请求头合并）
            timeout: 超时时间（秒），可选，默认使用实例配置的超时时间
            **kwargs: 其他requests支持的参数（如json、data、params等）

        Returns:
            requests.Response对象

        Raises:
            RequestException: 网络请求失败（会自动重试）
            HTTPError: HTTP状态码非2xx时抛出

        说明：
            - 自动合并默认请求头
            - 自动记录请求和响应日志
            - 自动检查响应状态码
            - 支持自动重试（仅针对网络异常）
        """
        # 构建完整URL
        full_url = self._build_url(url)

        # 合并请求头
        merged_headers = self._merge_headers(headers)

        # 使用传入的超时时间，如果没有则使用默认值
        request_timeout = timeout if timeout is not None else self.timeout

        # 记录请求日志
        request_body = kwargs.get('json') or kwargs.get('data') or kwargs.get('params')
        logging.info(
            f"📤 发送请求 - "
            f"method: {method.upper()}, "
            f"URL: {full_url}, "
            f"headers: {merged_headers}, "
            f"body: {request_body}, "
            f"timeout: {request_timeout}s"
        )

        # 记录开始时间
        start_time = time.time()

        try:
            # 发送请求
            response = self.session.request(
                method=method,
                url=full_url,
                headers=merged_headers,
                timeout=request_timeout,
                **kwargs
            )

            # 计算耗时（毫秒）
            elapsed_ms = int((time.time() - start_time) * 1000)

            # 截断响应内容，避免日志过大（最多1000字符）
            response_text = response.text[:1000] if len(response.text) > 1000 else response.text

            # 记录响应日志
            logging.info(
                f"📥 收到响应 - "
                f"status_code: {response.status_code}, "
                f"headers: {dict(response.headers)}, "
                f"body: {response_text}, "
                f"耗时: {elapsed_ms}ms"
            )

            # 检查状态码，非2xx抛出异常
            if not (200 <= response.status_code < 300):
                error_msg = (
                    f"❌ HTTP状态码异常 - "
                    f"status_code: {response.status_code}, "
                    f"URL: {full_url}, "
                    f"response: {response_text}"
                )
                logging.error(error_msg)
                raise HTTPError(error_msg, response=response)

            return response

        except RequestException as e:
            # 计算耗时（毫秒）
            elapsed_ms = int((time.time() - start_time) * 1000)
            logging.error(
                f"❌ 请求异常 - "
                f"URL: {full_url}, "
                f"耗时: {elapsed_ms}ms, "
                f"error: {e}"
            )
            raise

    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> requests.Response:
        """
        发送GET请求

        Args:
            url: 请求路径或完整URL
            headers: 自定义请求头（可选）
            timeout: 超时时间（秒），可选
            **kwargs: 其他requests支持的参数（如params等）

        Returns:
            requests.Response对象

        示例：
            >>> response = client.get("/users", params={"page": 1})
        """
        return self.request('GET', url, headers=headers, timeout=timeout, **kwargs)

    def post(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> requests.Response:
        """
        发送POST请求

        Args:
            url: 请求路径或完整URL
            headers: 自定义请求头（可选）
            timeout: 超时时间（秒），可选
            **kwargs: 其他requests支持的参数（如json、data等）

        Returns:
            requests.Response对象

        示例：
            >>> response = client.post("/users", json={"name": "张三"})
        """
        return self.request('POST', url, headers=headers, timeout=timeout, **kwargs)

    def put(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> requests.Response:
        """
        发送PUT请求

        Args:
            url: 请求路径或完整URL
            headers: 自定义请求头（可选）
            timeout: 超时时间（秒），可选
            **kwargs: 其他requests支持的参数（如json、data等）

        Returns:
            requests.Response对象

        示例：
            >>> response = client.put("/users/123", json={"name": "李四"})
        """
        return self.request('PUT', url, headers=headers, timeout=timeout, **kwargs)

    def delete(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> requests.Response:
        """
        发送DELETE请求

        Args:
            url: 请求路径或完整URL
            headers: 自定义请求头（可选）
            timeout: 超时时间（秒），可选
            **kwargs: 其他requests支持的参数

        Returns:
            requests.Response对象

        示例：
            >>> response = client.delete("/users/123")
        """
        return self.request('DELETE', url, headers=headers, timeout=timeout, **kwargs)

    def close(self) -> None:
        """
        关闭Session，释放资源

        说明：
            在测试结束时调用，确保资源正确释放
        """
        self.session.close()
        logging.info("🔌 HTTPClient Session已关闭")

    def __enter__(self):
        """
        支持上下文管理器协议
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        退出上下文时自动关闭Session
        """
        self.close()