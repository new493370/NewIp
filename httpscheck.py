import asyncio
import ssl
import time
from typing import List, Tuple, Dict, Any
import aiohttp

TLS_PORTS = {443, 8443, 2053, 2083, 2087, 2096}
_SSL_CONTEXT_CACHE = {}
_ALPN_CACHE = {}
_CONNECTION_CACHE = {}

def scheme_for(port: int) -> str:
    return "https" if port in TLS_PORTS else "http"

def get_ssl_context():
    if "default" not in _SSL_CONTEXT_CACHE:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            ctx.set_alpn_protocols(["h2", "http/1.1"])
        except:
            pass
        _SSL_CONTEXT_CACHE["default"] = ctx
    return _SSL_CONTEXT_CACHE["default"]

async def tcp_connect_time(ip: str, port: int, timeout: float = 2) -> int | None:
    try:
        start = time.perf_counter()
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout
        )
        elapsed = int((time.perf_counter() - start) * 1000)
        writer.close()
        await writer.wait_closed()
        return elapsed
    except:
        return None

async def detect_alpn(ip: str, port: int, timeout: float = 2) -> str:
    if port not in TLS_PORTS:
        return ""

    cache_key = f"{ip}:{port}"
    if cache_key in _ALPN_CACHE:
        return _ALPN_CACHE[cache_key]

    ctx = get_ssl_context()

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port, ssl=ctx),
            timeout
        )

        ssl_obj = writer.get_extra_info("ssl_object")
        proto = ""

        if ssl_obj:
            proto = ssl_obj.selected_alpn_protocol()

        writer.close()
        await writer.wait_closed()

        proto = proto.lower() if proto else ""
        _ALPN_CACHE[cache_key] = proto
        return proto

    except:
        _ALPN_CACHE[cache_key] = ""
        return ""

async def https_check(
    session: aiohttp.ClientSession,
    ip: str,
    port: int,
    timeout: float = 3,
    retries: int = 3
) -> Tuple[bool, Dict[str, Any] | None]:

    scheme = scheme_for(port)
    url = f"{scheme}://{ip}:{port}"

    ok_count = 0
    ttfb_list = []
    status_codes = []

    final_status = 0
    final_headers = {}

    ssl_ctx = get_ssl_context()
    headers = {"User-Agent": "ARISTA"}

    for attempt in range(retries):
        try:
            start = time.perf_counter()

            async with session.get(
                url,
                headers=headers,
                allow_redirects=False,
                ssl=ssl_ctx
            ) as resp:

                await resp.release()

                ttfb = (time.perf_counter() - start) * 1000

                if attempt == 0:
                    final_status = resp.status
                    final_headers = {}

                status_codes.append(resp.status)
                ttfb_list.append(ttfb)
                ok_count += 1

                if ok_count >= 2 and all(c in {200, 204, 206, 301, 302} for c in status_codes):
                    break

        except:
            continue

    if ok_count == 0:
        return False, None

    avg_ttfb = sum(ttfb_list) / len(ttfb_list)
    reliability = ok_count / retries

    alpn = ""

    if port in TLS_PORTS:
        cache_key = f"{ip}:{port}"
        if cache_key in _ALPN_CACHE:
            alpn = _ALPN_CACHE[cache_key]
        elif reliability >= 0.8 and port == 443:
            alpn = await detect_alpn(ip, port, timeout)

    if port in TLS_PORTS:
        final_proto = alpn if alpn else "http/1.1"
    else:
        final_proto = "http"

    score = 0

    if avg_ttfb <= 100:
        score += 40
    elif avg_ttfb <= 200:
        score += 35
    elif avg_ttfb <= 300:
        score += 30
    elif avg_ttfb <= 500:
        score += 20
    elif avg_ttfb <= 800:
        score += 10

    score += int(reliability * 40)

    good_status = {200, 204, 206, 301, 302}

    if status_codes:
        good_responses = sum(1 for code in status_codes if code in good_status)
        score += int((good_responses / len(status_codes)) * 20)

    if final_proto == "h2":
        score += 10

    score = max(0, min(score, 100))

    return True, {
        "status": final_status,
        "ttfb": int(avg_ttfb),
        "proto": final_proto,
        "reliability": reliability,
        "score": score,
        "ws": False,
        "headers": final_headers
    }

async def check_multiple_ips(
    ip_port_list: List[Tuple[str, int]],
    concurrency: int = 500,
    timeout: float = 3,
    retries: int = 3
) -> Dict[Tuple[str, int], Tuple[bool, Dict[str, Any] | None]]:

    sem = asyncio.Semaphore(concurrency)

    timeout_cfg = aiohttp.ClientTimeout(
        total=timeout,
        connect=timeout,
        sock_read=timeout
    )

    connector = aiohttp.TCPConnector(
        limit=concurrency,
        limit_per_host=concurrency,
        ttl_dns_cache=300,
        ssl=False,
        enable_cleanup_closed=True,
        keepalive_timeout=10
    )

    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout_cfg
    ) as session:

        async def worker(ip: str, port: int):
            async with sem:
                try:
                    return await https_check(
                        session,
                        ip,
                        port,
                        timeout,
                        retries
                    )
                except:
                    return False, None

        tasks = [
            asyncio.create_task(worker(ip, port))
            for ip, port in ip_port_list
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = {}

        for (ip, port), result in zip(ip_port_list, results):
            if isinstance(result, Exception):
                output[(ip, port)] = (False, None)
            else:
                output[(ip, port)] = result

        return output


if __name__ == "__main__":
    ip_list = [
        ("1.1.1.1", 443),
        ("8.8.8.8", 443),
        ("9.9.9.9", 8443)
    ]

    res = asyncio.run(
        check_multiple_ips(
            ip_list,
            concurrency=500
        )
    )

    for (ip, port), (ok, data) in res.items():
        print(ip, port, ok, data)
