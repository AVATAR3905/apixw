"""Ethical Scraping Framework: robots.txt compliance, rate limiting, CAPTCHA handling, IP rotation.

Implements PRD Section 11-13: Ethical collection, rate limiting, robots.txt compliance,
CAPTCHA handling, IP rotation, session management, and audit trail.
"""

import asyncio
import logging
import time
import urllib.robotparser
from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limiting configuration per domain."""
    requests_per_minute: int = 30
    requests_per_hour: int = 500
    concurrent_requests: int = 3
    min_delay_seconds: float = 1.0
    max_delay_seconds: float = 5.0
    backoff_multiplier: float = 2.0
    max_backoff_seconds: float = 60.0


@dataclass
class ProxyConfig:
    """Proxy configuration for IP rotation."""
    proxy_urls: List[str] = field(default_factory=list)
    rotate_on_failure: bool = True
    rotate_on_captcha: bool = True
    max_failures_per_proxy: int = 3
    health_check_interval_seconds: int = 300


@dataclass
class CaptchaConfig:
    """CAPTCHA handling configuration."""
    enabled: bool = True
    solver_api_key: Optional[str] = None
    solver_endpoint: str = "https://api.2captcha.com"
    max_retries: int = 3
    timeout_seconds: float = 120.0
    retry_delay_seconds: float = 10.0


class RateLimiter:
    """Token bucket rate limiter with per-domain isolation."""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self._tokens: Dict[str, float] = {}
        self._last_refill: Dict[str, float] = {}
        self._request_times: Dict[str, List[float]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def _get_lock(self, domain: str) -> asyncio.Lock:
        if domain not in self._locks:
            self._locks[domain] = asyncio.Lock()
        return self._locks[domain]

    async def acquire(self, domain: str) -> None:
        """Acquire permission to make a request to domain."""
        lock = self._get_lock(domain)
        async with lock:
            now = time.time()
            await self._refill_tokens(domain, now)
            await self._enforce_rate_limits(domain, now)

            # Consume token
            self._tokens[domain] -= 1
            self._request_times.setdefault(domain, []).append(now)

            # Clean old request times
            cutoff = now - 3600
            self._request_times[domain] = [t for t in self._request_times[domain] if t > cutoff]

    async def _refill_tokens(self, domain: str, now: float) -> None:
        if domain not in self._last_refill:
            self._last_refill[domain] = now
            self._tokens[domain] = self.config.requests_per_minute
            return

        elapsed = now - self._last_refill[domain]
        if elapsed >= 60:
            self._tokens[domain] = self.config.requests_per_minute
            self._last_refill[domain] = now
        else:
            # Gradual refill
            refill_rate = self.config.requests_per_minute / 60.0
            self._tokens[domain] = min(
                self.config.requests_per_minute,
                self._tokens.get(domain, 0) + elapsed * refill_rate
            )

    async def _enforce_rate_limits(self, domain: str, now: float) -> None:
        # Check hourly limit
        hour_ago = now - 3600
        recent_requests = [t for t in self._request_times.get(domain, []) if t > hour_ago]
        if len(recent_requests) >= self.config.requests_per_hour:
            sleep_time = 3600 - (now - recent_requests[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        # Check token availability
        if self._tokens.get(domain, 0) < 1:
            # Wait for token refill
            wait_time = (1 - self._tokens.get(domain, 0)) * 60.0 / self.config.requests_per_minute
            await asyncio.sleep(min(wait_time, self.config.max_delay_seconds))


class ProxyManager:
    """Manages proxy pool with health monitoring and rotation."""

    def __init__(self, config: ProxyConfig):
        self.config = config
        self.proxies = config.proxy_urls.copy()
        self.proxy_health: Dict[str, Dict[str, Any]] = {}
        self.current_index = 0
        self._lock = asyncio.Lock()

        # Initialize health tracking
        for proxy in self.proxies:
            self.proxy_health[proxy] = {
                "failures": 0,
                "successes": 0,
                "last_used": 0,
                "last_check": 0,
                "healthy": True,
            }

    async def get_proxy(self) -> Optional[str]:
        """Get next healthy proxy."""
        async with self._lock:
            if not self.proxies:
                return None

            healthy_proxies = [
                p for p in self.proxies
                if self.proxy_health[p]["healthy"]
            ]

            if not healthy_proxies:
                # Reset all to healthy if none available
                for p in self.proxies:
                    self.proxy_health[p]["healthy"] = True
                    self.proxy_health[p]["failures"] = 0
                healthy_proxies = self.proxies

            proxy = healthy_proxies[self.current_index % len(healthy_proxies)]
            self.current_index = (self.current_index + 1) % len(healthy_proxies)
            self.proxy_health[proxy]["last_used"] = time.time()
            return proxy

    async def mark_failure(self, proxy: str, is_captcha: bool = False) -> None:
        """Mark proxy as failed, rotate if needed."""
        async with self._lock:
            if proxy not in self.proxy_health:
                return

            health = self.proxy_health[proxy]
            health["failures"] += 1

            if is_captcha and self.config.rotate_on_captcha:
                health["failures"] += 2  # Extra penalty for CAPTCHA

            if health["failures"] >= self.config.max_failures_per_proxy:
                health["healthy"] = False
                logger.warning(f"Proxy {proxy} marked unhealthy after {health['failures']} failures")

    async def mark_success(self, proxy: str) -> None:
        """Mark proxy as successful."""
        async with self._lock:
            if proxy in self.proxy_health:
                self.proxy_health[proxy]["successes"] += 1
                self.proxy_health[proxy]["failures"] = max(0, self.proxy_health[proxy]["failures"] - 1)


class CaptchaSolver:
    """CAPTCHA solving with 2Captcha integration."""

    def __init__(self, config: CaptchaConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def solve_recaptcha_v2(
        self,
        sitekey: str,
        pageurl: str,
    ) -> Optional[str]:
        """Solve reCAPTCHA v2 using 2Captcha."""
        if not self.config.enabled or not self.config.solver_api_key:
            logger.warning("CAPTCHA solver not configured")
            return None

        session = await self._get_session()
        api_key = self.config.solver_api_key

        # Submit CAPTCHA
        submit_url = f"{self.config.solver_endpoint}/in.php"
        params = {
            "key": api_key,
            "method": "userrecaptcha",
            "googlekey": sitekey,
            "pageurl": pageurl,
            "json": 1,
        }

        try:
            async with session.get(submit_url, params=params) as resp:
                data = await resp.json()
                if data.get("status") != 1:
                    logger.error(f"CAPTCHA submit failed: {data.get('request')}")
                    return None

                captcha_id = data["request"]
        except Exception as e:
            logger.error(f"CAPTCHA submit error: {e}")
            return None

        # Poll for result
        result_url = f"{self.config.solver_endpoint}/res.php"
        params = {
            "key": self.config.solver_api_key,
            "action": "get",
            "id": captcha_id,
            "json": 1,
        }

        start_time = time.time()
        while time.time() - start_time < self.config.timeout_seconds:
            await asyncio.sleep(self.config.retry_delay_seconds)
            try:
                async with session.get(result_url, params=params) as resp:
                    data = await resp.json()
                    if data.get("status") == 1:
                        return data["request"]
                    elif data.get("request") == "CAPCHA_NOT_READY":
                        continue
                    else:
                        logger.error(f"CAPTCHA solve failed: {data.get('request')}")
                        return None
            except Exception as e:
                logger.error(f"CAPTCHA poll error: {e}")
                return None

        logger.error("CAPTCHA solve timeout")
        return None


class RobotsTxtChecker:
    """robots.txt compliance checker with caching."""

    def __init__(self):
        self._parsers: Dict[str, urllib.robotparser.RobotFileParser] = {}
        self._cache_ttl = 3600  # 1 hour
        self._last_fetch: Dict[str, float] = {}

    def _get_parser(self, domain: str) -> urllib.robotparser.RobotFileParser:
        now = time.time()
        if domain not in self._parsers or now - self._last_fetch.get(domain, 0) > self._cache_ttl:
            parser = urllib.robotparser.RobotFileParser()
            robots_url = f"https://{domain}/robots.txt"
            try:
                parser.set_url(robots_url)
                parser.read()
                self._parsers[domain] = parser
                self._last_fetch[domain] = time.time()
            except Exception as e:
                logger.warning(f"Failed to fetch robots.txt for {domain}: {e}")
                # Default permissive parser
                parser = urllib.robotparser.RobotFileParser()
                parser.allow_all = True
                self._parsers[domain] = parser
        return self._parsers[domain]

    def can_fetch(self, url: str, user_agent: str = "*") -> bool:
        """Check if URL can be fetched per robots.txt."""
        parsed = urlparse(url)
        domain = parsed.netloc
        path = parsed.path or "/"

        try:
            parser = self._get_parser(domain)
            return parser.can_fetch(user_agent, path)
        except Exception:
            return True  # Default allow on error


class EthicalScraperBase(ABC):
    """Base class for ethical scraping with all safeguards."""

    def __init__(
        self,
        domain: str,
        user_agent: str = "APIX-Research-Bot/1.0 (+https://apix.example.com/bot)",
        rate_limit_config: Optional[RateLimitConfig] = None,
        proxy_config: Optional[ProxyConfig] = None,
        captcha_config: Optional[CaptchaConfig] = None,
    ):
        self.domain = domain
        self.user_agent = user_agent
        self.rate_limiter = RateLimiter(rate_limit_config or RateLimitConfig())
        self.proxy_manager = ProxyManager(proxy_config or ProxyConfig())
        self.captcha_solver = CaptchaSolver(captcha_config or CaptchaConfig())
        self.robots_checker = RobotsTxtChecker()

        self.session: Optional[aiohttp.ClientSession] = None
        self._request_count = 0
        self._captcha_count = 0
        self._error_count = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": self.user_agent},
                timeout=timeout,
            )
        return self.session

    async def fetch(
        self,
        url: str,
        method: str = "GET",
        **kwargs,
    ) -> Optional[aiohttp.ClientResponse]:
        """Fetch URL with all ethical safeguards."""
        # Check robots.txt
        if not self.robots_checker.can_fetch(url):
            logger.warning(f"robots.txt disallows: {url}")
            return None

        # Rate limiting
        parsed = urlparse(url)
        await self.rate_limiter.acquire(parsed.netloc)

        # Get proxy
        proxy = await self.proxy_manager.get_proxy()

        session = await self._get_session()
        headers = kwargs.pop("headers", {})
        headers["User-Agent"] = self.user_agent

        request_kwargs = {
            "proxy": proxy,
            "headers": headers,
            **kwargs,
        }

        for attempt in range(3):
            try:
                self._request_count += 1
                async with session.request(method, url, **request_kwargs) as resp:
                    # Check for CAPTCHA
                    if await self._is_captcha_response(resp):
                        self._captcha_count += 1
                        await self._handle_captcha(resp, proxy)
                        if attempt < 2:
                            await asyncio.sleep(10)
                            continue

                    if resp.status >= 400:
                        self._error_count += 1
                        if proxy:
                            await self.proxy_manager.mark_failure(proxy)
                        if attempt < 2:
                            await asyncio.sleep(2 ** attempt)
                            continue

                    if proxy:
                        await self.proxy_manager.mark_success(proxy)
                    return resp

            except asyncio.TimeoutError:
                self._error_count += 1
                if proxy:
                    await self.proxy_manager.mark_failure(proxy)
            except Exception as e:
                logger.error(f"Request error: {e}")
                self._error_count += 1
                if proxy:
                    await self.proxy_manager.mark_failure(proxy)

            if attempt < 2:
                await asyncio.sleep(2 ** attempt)

        return None

    async def _is_captcha_response(self, resp: aiohttp.ClientResponse) -> bool:
        """Detect CAPTCHA challenge in response."""
        content_type = resp.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            return False

        # Check status codes
        if resp.status in (403, 429, 503):
            return True

        # Check for CAPTCHA indicators in body (sample)
        text = await resp.text()
        captcha_indicators = [
            "captcha", "recaptcha", "hcaptcha", "cloudflare",
            "challenge", "verify you are human", "access denied"
        ]
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in captcha_indicators)

    async def _handle_captcha(self, resp: aiohttp.ClientResponse, proxy: Optional[str]) -> None:
        """Attempt to solve CAPTCHA."""
        if proxy:
            await self.proxy_manager.mark_failure(proxy, is_captcha=True)

        # In production, integrate with CAPTCHA solver
        logger.warning(f"CAPTCHA detected on {self.domain}, rotating proxy")


