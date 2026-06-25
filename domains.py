import socket
import ssl
import requests
import re
import json
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

requests.packages.urllib3.disable_warnings()

TLS_INPUT_FILE = "output/tls_live.txt"
RESULTS_INPUT_FILE = "output/results.txt"
RAW_FILE = "output/domains_raw.txt"
IPS_FILE = "output/domains_ips.txt"

DOMAIN_RE = re.compile(
    r"(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}"
)

TLS_PORTS = {
    443,
    8443,
    2053,
    2083,
    2087,
    2096
}

HEADERS_TO_CHECK = [
    "Location",
    "Alt-Svc",
    "Server",
    "Via",
    "Origin",
    "Host",
    "X-Forwarded-Host"
]


def load_config():
    try:
        with open(
            "config.json",
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)
    except:
        return {}


def normalize_domain(domain):
    domain = str(domain).strip().lower()

    if not domain:
        return ""

    if "://" in domain:
        domain = urlparse(domain).netloc

    if ":" in domain:
        domain = domain.split(":")[0]

    domain = domain.strip("/")

    if domain.startswith("*."):
        domain = domain[2:]

    return domain


def resolve_domain_ip(domain):
    try:
        return socket.gethostbyname(domain)
    except:
        return None


def cert_domains(
    ip,
    port,
    timeout=2
):
    domains = set()

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with socket.create_connection(
            (ip, port),
            timeout=timeout
        ) as sock:

            with ctx.wrap_socket(
                sock,
                server_hostname=ip
            ) as ssock:

                cert = ssock.getpeercert()

                for item in cert.get(
                    "subject",
                    []
                ):
                    for k, v in item:
                        if k == "commonName":
                            d = normalize_domain(v)
                            if d:
                                domains.add(d)

                for typ, val in cert.get(
                    "subjectAltName",
                    []
                ):
                    if typ == "DNS":
                        d = normalize_domain(val)
                        if d:
                            domains.add(d)

    except:
        pass

    return domains


def redirect_domains(
    ip,
    port,
    timeout=2
):
    domains = set()

    scheme = (
        "https"
        if port in TLS_PORTS
        else "http"
    )

    try:
        r = requests.get(
            f"{scheme}://{ip}",
            timeout=timeout,
            verify=False,
            allow_redirects=True,
            stream=True
        )

        for resp in r.history:
            location = resp.headers.get(
                "Location"
            )

            if location:
                d = normalize_domain(
                    location
                )
                if d:
                    domains.add(d)

        d = normalize_domain(r.url)
        if d:
            domains.add(d)

    except:
        pass

    return domains


def header_domains(response):
    domains = set()

    for header in HEADERS_TO_CHECK:
        value = response.headers.get(
            header
        )

        if not value:
            continue

        found = DOMAIN_RE.findall(value)

        for d in found:
            d = normalize_domain(d)
            if d:
                domains.add(d)

    return domains


def html_domains(text):
    domains = set()

    found = DOMAIN_RE.findall(text)

    for d in found:
        d = normalize_domain(d)
        if d:
            domains.add(d)

    return domains


def http_domains(
    ip,
    port,
    timeout=2
):
    domains = set()

    scheme = (
        "https"
        if port in TLS_PORTS
        else "http"
    )

    try:
        r = requests.get(
            f"{scheme}://{ip}",
            timeout=timeout,
            verify=False,
            allow_redirects=True,
            stream=True
        )

        domains.update(
            header_domains(r)
        )

        ctype = r.headers.get(
            "Content-Type",
            ""
        ).lower()

        if "html" in ctype:
            text = r.text[:20000]
            domains.update(
                html_domains(text)
            )

    except:
        pass

    return domains


def ptr_domain(
    ip
):
    try:
        host = socket.gethostbyaddr(ip)[0]
        host = normalize_domain(host)

        if host:
            return {host}

    except:
        pass

    return set()


def read_tls_cache():
    items = []

    try:
        with open(
            TLS_INPUT_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            for line in f:
                line = line.strip()

                if not line:
                    continue

                parts = line.split(":")

                if len(parts) < 2:
                    continue

                try:
                    ip = parts[0]
                    port = int(parts[1])
                except:
                    continue

                items.append(
                    (ip, port)
                )

    except:
        pass

    return items


def read_results():
    items = []

    try:
        with open(
            RESULTS_INPUT_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            for line in f:
                line = line.strip()

                if not line:
                    continue

                parts = line.split("|")

                if len(parts) < 2:
                    continue

                try:
                    ip = parts[0]
                    port = int(parts[1])
                except:
                    continue

                items.append(
                    (ip, port)
                )

    except:
        pass

    return items


def extract_worker(item):
    ip, port = item

    result = set()

    result.update(
        cert_domains(ip, port)
    )

    result.update(
        redirect_domains(ip, port)
    )

    result.update(
        http_domains(ip, port)
    )

    result.update(
        ptr_domain(ip)
    )

    domain_ips = set()
    for domain in list(result):
        resolved_ip = resolve_domain_ip(domain)
        if resolved_ip:
            domain_ips.add(resolved_ip)

    for resolved_ip in domain_ips:
        result.add(resolved_ip)

    return result


def extract_domains():
    cfg = load_config()

    threads = min(
        cfg.get(
            "threads",
            300
        ),
        100
    )

    live_items = read_tls_cache()

    print(
        f"TLS INPUT={len(live_items)} "
        f"THREADS={threads}"
    )

    domains = set()
    domain_ips = set()

    with ThreadPoolExecutor(
        max_workers=threads
    ) as ex:

        futures = [
            ex.submit(
                extract_worker,
                item
            )
            for item in live_items
        ]

        for fut in as_completed(
            futures
        ):
            try:
                res = fut.result()

                if res:
                    for item in res:
                        if re.match(r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$', item):
                            domain_ips.add(item)
                        elif "." in item:
                            domains.add(item)

            except:
                continue

    domains = sorted(
        {
            d
            for d in domains
            if d and "." in d
        }
    )

    domain_ips = sorted(domain_ips)

    with open(
        RAW_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(
            "\n".join(domains)
        )

    with open(
        IPS_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(
            "\n".join(domain_ips)
        )

    print(
        f"DOMAINS={len(domains)} "
        f"DOMAIN_IPS={len(domain_ips)}"
    )


def extract_domains_from_results():
    cfg = load_config()

    threads = min(
        cfg.get(
            "threads",
            300
        ),
        100
    )

    live_items = read_results()

    print(
        f"RESULTS INPUT={len(live_items)} "
        f"THREADS={threads}"
    )

    domains = set()
    domain_ips = set()

    with ThreadPoolExecutor(
        max_workers=threads
    ) as ex:

        futures = [
            ex.submit(
                extract_worker,
                item
            )
            for item in live_items
        ]

        for fut in as_completed(
            futures
        ):
            try:
                res = fut.result()

                if res:
                    for item in res:
                        if re.match(r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$', item):
                            domain_ips.add(item)
                        elif "." in item:
                            domains.add(item)

            except:
                continue

    domains = sorted(
        {
            d
            for d in domains
            if d and "." in d
        }
    )

    domain_ips = sorted(domain_ips)

    with open(
        RAW_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(
            "\n".join(domains)
        )

    with open(
        IPS_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(
            "\n".join(domain_ips)
        )

    print(
        f"DOMAINS={len(domains)} "
        f"DOMAIN_IPS={len(domain_ips)}"
    )


if __name__ == "__main__":
    extract_domains()
