import json
import socket
import time
import os
import asyncio
from concurrent.futures import (
    ThreadPoolExecutor,
    wait,
    FIRST_COMPLETED
)

from tls import tls_check
from fingerprint import detect_cdn
from geo import geo_lookup
from httpscheck import https_check

from cache import (
    append_tcp_live,
    append_tls_live,
    append_https_live,
    append_fp,
    read_tcp_live,
    read_tls_live,
    read_https_live,
    read_fp,
    load_geo_cache,
    save_geo_cache,
    load_cache,
    save_cache,
    already_scanned,
    cache_result,
    https_meta_store,
    https_meta_get
)

from livebank import append_live

RESULT_FILE = "output/results.txt"


def ensure_output():
    os.makedirs(
        "output",
        exist_ok=True
    )


def load_config():
    with open(
        "config.json",
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f)


def adaptive_threads(
    cfg,
    cap=None
):
    threads = int(
        cfg.get(
            "threads",
            300
        )
    )

    if cap:
        threads = min(
            threads,
            cap
        )

    if threads < 1:
        threads = 1

    return threads


def config_timeout(
    cfg,
    port
):
    base = float(
        cfg.get(
            "timeout",
            3
        )
    )

    if port == 80:
        return min(
            base,
            0.7
        )

    if port == 443:
        return min(
            base,
            1.2
        )

    return min(
        base,
        1.0
    )


def read_batches(
    path,
    size
):
    batch = []

    try:
        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            for line in f:
                line = line.strip()

                if not line:
                    continue

                batch.append(line)

                if len(batch) >= size:
                    yield batch
                    batch = []

            if batch:
                yield batch

    except:
        return


def tcp_check(
    ip,
    port,
    retries,
    timeout
):
    for _ in range(
        retries
    ):
        start = time.time()

        try:
            sock = socket.create_connection(
                (
                    ip,
                    port
                ),
                timeout=timeout
            )

            sock.close()

            latency = int(
                (
                    time.time()
                    - start
                ) * 1000
            )

            return (
                "success",
                latency
            )

        except socket.timeout:
            return (
                "timeout",
                None
            )

        except:
            continue

    return (
        "failed",
        None
    )


def tcp_worker(
    ip,
    ports,
    retries,
    cfg,
    cache
):
    live = []

    limit = cfg.get(
        "latency_limit_ms",
        500
    )

    for port in ports:

        if already_scanned(
            cache,
            ip,
            port
        ):
            continue

        timeout = config_timeout(
            cfg,
            port
        )

        status, latency = tcp_check(
            ip,
            port,
            retries,
            timeout
        )

        cache_result(
            cache,
            ip,
            port,
            status
        )

        if (
            status == "success"
            and latency is not None
            and latency <= limit
        ):
            live.append(
                f"{ip}:{port}:{latency}"
            )

    return live


def tcp_scan(
    input_file
):
    ensure_output()

    cfg = load_config()

    ports = cfg.get(
        "ports",
        []
    )

    threads = adaptive_threads(
        cfg,
        300
    )

    batch_size = cfg.get(
        "batch_size",
        20000
    )

    retries = cfg.get(
        "retries",
        2
    )

    cache = load_cache()

    total_live = 0
    total_batch = 0

    for batch in read_batches(
        input_file,
        batch_size
    ):

        total_batch += 1
        stage_live = []

        print(
            f"BATCH={total_batch} "
            f"SIZE={len(batch)} "
            f"CACHE={len(cache)} "
            f"THREADS={threads}"
        )

        with ThreadPoolExecutor(
            max_workers=threads
        ) as ex:

            pending = set()
            iterator = iter(
                batch
            )

            while True:

                while len(
                    pending
                ) < (
                    threads * 2
                ):
                    try:
                        ip = next(
                            iterator
                        )
                    except StopIteration:
                        break

                    pending.add(
                        ex.submit(
                            tcp_worker,
                            ip,
                            ports,
                            retries,
                            cfg,
                            cache
                        )
                    )

                if not pending:
                    break

                done, pending = wait(
                    pending,
                    return_when=FIRST_COMPLETED
                )

                for fut in done:
                    try:
                        res = fut.result()

                        if res:
                            stage_live.extend(
                                res
                            )
                    except:
                        continue

        append_tcp_live(
            stage_live
        )

        append_live(
            stage_live
        )

        save_cache(
            cache
        )

        total_live += len(
            stage_live
        )

        print(
            f"TCP_BATCH={len(batch)} "
            f"LIVE={len(stage_live)} "
            f"TOTAL={total_live}"
        )

    print(
        f"TCP COMPLETE={total_live}"
    )


def tls_worker(
    item
):
    try:
        ip, port, latency = item.split(
            ":"
        )
        port = int(port)
    except:
        return None

    timeout = 1.5

    tls_ok, tls_data = tls_check(
        ip,
        port,
        timeout
    )

    if not tls_ok:
        return None

    alpn = ""
    sni = ""
    issuer = ""

    if tls_data:

        alpn = (
            tls_data.get(
                "alpn",
                ""
            ) or ""
        )

        sni = (
            tls_data.get(
                "sni",
                ""
            ) or ""
        )

        meta = (
            tls_data.get(
                "meta",
                {}
            ) or {}
        )

        issuer = (
            meta.get(
                "issuer",
                ""
            ) or ""
        )

    return (
        f"{ip}:{port}:{latency}:"
        f"{alpn}:{sni}:{issuer}"
    )


def tls_scan():
    ensure_output()

    cfg = load_config()

    threads = adaptive_threads(
        cfg,
        250
    )

    tcp_items = read_tcp_live()

    print(
        f"TCP INPUT={len(tcp_items)} "
        f"THREADS={threads}"
    )

    tls_live = []

    with ThreadPoolExecutor(
        max_workers=threads
    ) as ex:

        for res in ex.map(
            tls_worker,
            tcp_items
        ):
            if res:
                tls_live.append(
                    res
                )

    append_tls_live(
        tls_live
    )

    append_live(
        tls_live
    )

    print(
        f"TLS LIVE={len(tls_live)}"
    )


async def https_worker_async(
    item,
    cfg,
    session
):
    try:
        parts = item.split(
            ":"
        )

        ip = parts[0]
        port = int(parts[1])

    except:
        return None

    timeout = min(
        cfg.get(
            "timeout",
            3
        ),
        2
    )

    ok, data = await https_check(
        session,
        ip,
        port,
        timeout=timeout,
        retries=2
    )

    if not ok:
        return None

    https_meta_store(
        ip,
        port,
        {
            "headers": data.get(
                "headers",
                {}
            ),
            "ws": data.get(
                "ws",
                False
            )
        }
    )

    ws = int(
        bool(
            data.get(
                "ws",
                False
            )
        )
    )

    return (
        f"{ip}|{port}|"
        f"{data['status']}|"
        f"{data['ttfb']}|"
        f"{data['proto']}|"
        f"{data['reliability']}|"
        f"{ws}"
    )


def https_scan():
    ensure_output()

    cfg = load_config()

    threads = adaptive_threads(
        cfg,
        200
    )

    tls_items = read_tls_live()

    print(
        f"TLS INPUT={len(tls_items)} "
        f"THREADS={threads}"
    )

    if not tls_items:
        print("NO TLS ITEMS TO SCAN")
        return

    https_live = []

    async def run_https_scan():
        nonlocal https_live
        
        batch_size = 50
        
        timeout_cfg = aiohttp.ClientTimeout(
            total=cfg.get("timeout", 3),
            connect=2,
            sock_read=2
        )

        connector = aiohttp.TCPConnector(
            limit=threads,
            limit_per_host=threads // 4,
            ssl=False,
            enable_cleanup_closed=True,
            force_close=True
        )

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout_cfg
        ) as session:
            
            for i in range(0, len(tls_items), batch_size):
                batch = tls_items[i:i + batch_size]
                
                tasks = [
                    https_worker_async(
                        item,
                        cfg,
                        session
                    )
                    for item in batch
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for res in results:
                    if res and not isinstance(res, Exception):
                        https_live.append(res)
                
                print(f"HTTPS PROGRESS: {min(i + batch_size, len(tls_items))}/{len(tls_items)}")
    
    import aiohttp
    
    try:
        asyncio.run(run_https_scan())
    except Exception as e:
        print(f"HTTPS SCAN ERROR: {e}")
        https_live = []

    append_https_live(
        https_live
    )

    print(
        f"HTTPS={len(https_live)}"
    )


def fp_worker(
    item
):
    try:
        parts = item.split("|")

        ip = parts[0]
        port = int(parts[1])
        status = parts[2]
        ttfb = parts[3]
        proto = parts[4]
        reliability = parts[5]
        ws = parts[6]

    except:
        return None

    meta = https_meta_get(
        ip,
        port
    ) or {}

    headers = meta.get(
        "headers",
        {}
    )

    cdn = detect_cdn(
        headers
    )

    return (
        f"{ip}|{port}|"
        f"{status}|{ttfb}|"
        f"{proto}|{reliability}|"
        f"{ws}|{cdn}"
    )


def fingerprint_scan():
    ensure_output()

    cfg = load_config()

    threads = adaptive_threads(
        cfg,
        200
    )

    https_items = read_https_live()

    print(
        f"HTTPS INPUT={len(https_items)} "
        f"THREADS={threads}"
    )

    fp_results = []

    with ThreadPoolExecutor(
        max_workers=threads
    ) as ex:

        for res in ex.map(
            fp_worker,
            https_items
        ):
            if res:
                fp_results.append(
                    res
                )

    append_fp(
        fp_results
    )

    print(
        f"FP DONE={len(fp_results)}"
    )


def geo_worker(
    item,
    geo_cache
):
    try:
        parts = item.split("|")

        ip = parts[0]
        port = parts[1]
        status = parts[2]
        ttfb = parts[3]
        proto = parts[4]
        reliability = parts[5]
        ws = parts[6]
        cdn = parts[7]

    except:
        return None

    geo = geo_cache.get(
        ip
    )

    if geo is None:
        geo = geo_lookup(
            ip
        )
        geo_cache[ip] = geo

    country = geo.get(
        "country",
        "?"
    )

    provider = geo.get(
        "provider",
        "?"
    )

    return (
        f"{ip}|{port}|"
        f"{status}|{ttfb}|"
        f"{proto}|{reliability}|"
        f"{ws}|{cdn}|"
        f"{country}|{provider}"
    )


def geo_scan():
    ensure_output()

    cfg = load_config()

    threads = adaptive_threads(
        cfg,
        100
    )

    fp_items = read_fp()

    print(
        f"FP INPUT={len(fp_items)} "
        f"THREADS={threads}"
    )

    geo_cache = load_geo_cache()
    final = []

    with ThreadPoolExecutor(
        max_workers=threads
    ) as ex:

        for res in ex.map(
            lambda x:
            geo_worker(
                x,
                geo_cache
            ),
            fp_items
        ):
            if res:
                final.append(
                    res
                )

    save_geo_cache(
        geo_cache
    )

    with open(
        RESULT_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(
            "\n".join(final)
        )

    print(
        f"GEO DONE={len(final)}"
    )
