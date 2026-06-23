import asyncio
import ssl
import time
from typing import List, Tuple, Dict, Any
import aiohttp

TLS_PORTS = {443, 8443, 2053, 2083, 2087, 2096}

def scheme_for(port: int) -> str:
    return "https" if port in TLS_PORTS else "http"

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

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        ctx.set_alpn_protocols(["h2", "http/1.1"])
    except:
        pass

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                ip,
                port,
                ssl=ctx
            ),
            timeout
        )

        ssl_obj = writer.get_extra_info("ssl_object")

        proto = ""
        if ssl_obj:
            proto = ssl_obj.selected_alpn_protocol()

        writer.close()
        await writer.wait_closed()

        return proto.lower() if proto else ""

    except:
        return ""

async def https_check(
    session: aiohttp.ClientSession,
    ip: str,
    port: int,
    timeout: float = 3,
    retries: int = 5
) -> Tuple[bool, Dict[str, Any] | None]:

    scheme = scheme_for(port)
    url = f"{scheme}://{ip}"

    ok_count = 0
    ttfb_list = []
    connect_times = []
    status_codes = []

    final_status = 0
    final_proto = ""
    final_headers = {}

    connect_probes = min(5, retries)

    for _ in range(connect_probes):
        ct = await tcp_connect_time(ip, port, timeout)
        if ct is not None:
            connect_times.append(ct)

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    headers = {"User-Agent": "ARISTA"}

    for _ in range(retries):
        try:
            start = time.perf_counter()

            async with session.get(
                url,
                headers=headers,
                allow_redirects=False,
                ssl=ssl_ctx
            ) as resp:

                await resp.content.read(1)

                ttfb = int(
                    (time.perf_counter() - start) * 1000
                )

                final_status = resp.status
                final_headers = dict(resp.headers)

                status_codes.append(resp.status)
                ttfb_list.append(ttfb)
                ok_count += 1

        except:
            continue

    if ok_count == 0:
        return False, None

    avg_ttfb = int(sum(ttfb_list) / len(ttfb_list))

    reliability = ok_count / retries

    jitter = (
        max(ttfb_list) - min(ttfb_list)
        if len(ttfb_list) > 1
        else 0
    )

    alpn = ""

    if reliability >= 0.8:
        alpn = await detect_alpn(
            ip,
            port,
            timeout
        )

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
        good_responses = sum(
            1
            for code in status_codes
            if code in good_status
        )

        score += int(
            (good_responses / len(status_codes))
            * 20
        )

    if jitter > 400:
        score -= 8
    elif jitter > 250:
        score -= 5
    elif jitter > 100:
        score -= 2

    if final_proto == "h2":
        score += 10

    if connect_times:
        avg_connect = int(
            sum(connect_times)
            / len(connect_times)
        )

        connect_jitter = (
            max(connect_times)
            - min(connect_times)
        )

        if avg_connect <= 50:
            score += 25
        elif avg_connect <= 100:
            score += 20
        elif avg_connect <= 150:
            score += 15
        elif avg_connect <= 250:
            score += 10
        elif avg_connect <= 400:
            score += 5
        elif avg_connect > 800:
            score -= 10
        elif avg_connect > 500:
            score -= 5
        elif avg_connect > 300:
            score -= 2

        if connect_jitter > 200:
            score -= 10
        elif connect_jitter > 100:
            score -= 5

    score = max(0, min(score, 100))

    return True, {
        "status": final_status,
        "ttfb": avg_ttfb,
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
    retries: int = 5
) -> Dict[Tuple[str, int], Tuple[bool, Dict[str, Any] | None]]:

    sem = asyncio.Semaphore(concurrency)

    timeout_cfg = aiohttp.ClientTimeout(
        total=timeout
    )

    connector = aiohttp.TCPConnector(
        limit=concurrency,
        limit_per_host=0,
        ssl=False,
        enable_cleanup_closed=True
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

        tasks = {
            asyncio.create_task(
                worker(ip, port)
            ): (ip, port)
            for ip, port in ip_port_list
        }

        output = {}

        for task in asyncio.as_completed(tasks):
            ip, port = tasks[task]
            output[(ip, port)] = await task

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
