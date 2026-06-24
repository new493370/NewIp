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

    all_ips = []

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            for line in f:
                ip = line.strip()
                if not ip:
                    continue
                if not any(already_scanned(cache, ip, port) for port in ports):
                    all_ips.append(ip)
    except:
        pass

    if not all_ips:
        print("NO NEW IPS TO SCAN")
        return

    total_live = 0
    total_batch = 0

    for i in range(0, len(all_ips), batch_size):
        batch = all_ips[i:i+batch_size]
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
    cfg
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

    https_live = []

    async def run_batch(batch):
        tasks = [
            https_worker_async(
                item,
                cfg
            )
            for item in batch
        ]
        return await asyncio.gather(*tasks)

    batch_size = 100
    batches = [
        tls_items[i:i + batch_size]
        for i in range(0, len(tls_items), batch_size)
    ]

    for batch in batches:
        results = asyncio.run(run_batch(batch))
        for res in results:
            if res:
                https_live.append(res)

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

    tls_info = {}

    try:
        with open(
            "output/tls_live.txt",
            "r",
            encoding="utf-8"
        ) as f:

            for line in f:

                if line.startswith(
                    f"{ip}:{port}"
                ):

                    tls_parts = line.strip().split(
                        ":"
                    )

                    if len(tls_parts) >= 6:

                        tls_info = {
                            "alpn": tls_parts[3],
                            "sni": tls_parts[4],
                            "issuer": tls_parts[5]
                        }

                    break

    except:
        pass

    cdn = detect_cdn(
        ip=ip,
        port=port,
        headers=headers,
        issuer=tls_info.get(
            "issuer"
        ),
        sni=tls_info.get(
            "sni"
        ),
        alpn=tls_info.get(
            "alpn"
        )
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
```

---

فایل دوازدهم: cache.py

```python
import os
import json

CACHE_FILE = "output/scanned_cache.txt"
TCP_FILE = "output/tcp_live.txt"
TLS_FILE = "output/tls_live.txt"
HTTPS_FILE = "output/https_live.txt"
FP_FILE = "output/fingerprint_results.txt"
GEO_FILE = "output/geo_cache.json"
HTTPS_META_FILE = "output/https_meta.json"


def ensure_output():
    os.makedirs(
        "output",
        exist_ok=True
    )


def cache_key(
    ip,
    port
):
    return f"{ip}:{port}"


def cache_line(
    ip,
    port,
    status="success"
):
    return f"{ip}:{port}:{status}"


def load_cache():
    ensure_output()

    if not os.path.exists(
        CACHE_FILE
    ):
        return {}

    data = {}

    try:
        with open(
            CACHE_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            for line in f:
                line = line.strip()

                if not line:
                    continue

                parts = line.split(
                    ":"
                )

                if len(parts) < 2:
                    continue

                ip = parts[0]

                try:
                    port = int(
                        parts[1]
                    )
                except:
                    continue

                status = (
                    parts[2]
                    if len(parts) >= 3
                    else "success"
                )

                data[
                    cache_key(
                        ip,
                        port
                    )
                ] = status

    except:
        return {}

    return data


def save_cache(cache):
    ensure_output()

    tmp = (
        CACHE_FILE
        + ".tmp"
    )

    try:
        with open(
            tmp,
            "w",
            encoding="utf-8"
        ) as f:

            for key in sorted(
                cache
            ):
                status = cache[key]

                f.write(
                    f"{key}:{status}\n"
                )

        os.replace(
            tmp,
            CACHE_FILE
        )

    except:
        pass


def already_scanned(
    cache,
    ip,
    port
):
    return (
        cache_key(
            ip,
            port
        )
        in cache
    )


def cache_status(
    cache,
    ip,
    port
):
    return cache.get(
        cache_key(
            ip,
            port
        )
    )


def cache_result(
    cache,
    ip,
    port,
    status="success"
):
    cache[
        cache_key(
            ip,
            port
        )
    ] = status


def cache_count():
    return len(
        load_cache()
    )


def clear_cache():
    ensure_output()

    with open(
        CACHE_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        f.write("")


def read_stage(path):
    ensure_output()

    if not os.path.exists(
        path
    ):
        return []

    try:
        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            return [
                x.strip()
                for x in f
                if x.strip()
            ]

    except:
        return []


def append_stage(
    path,
    items
):
    ensure_output()

    if not items:
        return 0

    count = 0

    try:
        with open(
            path,
            "a",
            encoding="utf-8"
        ) as f:

            for item in items:
                item = str(
                    item
                ).strip()

                if not item:
                    continue

                f.write(
                    item
                    + "\n"
                )

                count += 1

    except:
        return 0

    return count


def dedupe_file(path):
    ensure_output()

    if not os.path.exists(
        path
    ):
        return 0

    tmp = (
        path
        + ".tmp"
    )

    try:
        seen = set()

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as src, open(
            tmp,
            "w",
            encoding="utf-8"
        ) as dst:

            for line in src:
                line = line.strip()

                if (
                    not line
                    or
                    line in seen
                ):
                    continue

                seen.add(
                    line
                )

                dst.write(
                    line
                    + "\n"
                )

        os.replace(
            tmp,
            path
        )

        return len(
            seen
        )

    except:
        return 0


def append_tcp_live(items):
    return append_stage(
        TCP_FILE,
        items
    )


def append_tls_live(items):
    return append_stage(
        TLS_FILE,
        items
    )


def append_https_live(items):
    return append_stage(
        HTTPS_FILE,
        items
    )


def append_fp(items):
    return append_stage(
        FP_FILE,
        items
    )


def optimize_stage_files():
    tcp = dedupe_file(
        TCP_FILE
    )

    tls = dedupe_file(
        TLS_FILE
    )

    https = dedupe_file(
        HTTPS_FILE
    )

    fp = dedupe_file(
        FP_FILE
    )

    return {
        "tcp": tcp,
        "tls": tls,
        "https": https,
        "fp": fp
    }


def read_tcp_live():
    return read_stage(
        TCP_FILE
    )


def read_tls_live():
    return read_stage(
        TLS_FILE
    )


def read_https_live():
    return read_stage(
        HTTPS_FILE
    )


def read_fp():
    return read_stage(
        FP_FILE
    )


def load_geo_cache():
    ensure_output()

    if not os.path.exists(
        GEO_FILE
    ):
        return {}

    try:
        with open(
            GEO_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(
                f
            )
    except:
        return {}


def save_geo_cache(data):
    ensure_output()

    tmp = (
        GEO_FILE
        + ".tmp"
    )

    try:
        with open(
            tmp,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                ensure_ascii=False
            )

        os.replace(
            tmp,
            GEO_FILE
        )

    except:
        pass


def load_https_meta():
    ensure_output()

    if not os.path.exists(
        HTTPS_META_FILE
    ):
        return {}

    try:
        with open(
            HTTPS_META_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(
                f
            )

    except:
        return {}


def save_https_meta(data):
    ensure_output()

    tmp = (
        HTTPS_META_FILE
        + ".tmp"
    )

    try:
        with open(
            tmp,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                ensure_ascii=False
            )

        os.replace(
            tmp,
            HTTPS_META_FILE
        )

    except:
        pass


def https_meta_get(
    ip,
    port
):
    data = load_https_meta()

    return data.get(
        cache_key(
            ip,
            port
        )
    )


def https_meta_store(
    ip,
    port,
    value
):
    data = load_https_meta()

    data[
        cache_key(
            ip,
            port
        )
    ] = value

    save_https_meta(
        data
    )


def geo_cached(ip):
    data = load_geo_cache()

    return data.get(
        ip
    )


def geo_store(
    ip,
    value
):
    data = load_geo_cache()

    data[ip] = value

    save_geo_cache(
        data
    )


if __name__ == "__main__":
    res = optimize_stage_files()

    print(
        f"TCP={res['tcp']} "
        f"TLS={res['tls']} "
        f"HTTPS={res['https']} "
        f"FP={res['fp']}"
    )
