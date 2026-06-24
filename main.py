import os
import argparse
import json

from downloader import download_sources
from cleaner import clean_ips
from splitter import split_file

from scanner import (
    tcp_scan,
    tls_scan,
    https_scan,
    fingerprint_scan,
    geo_scan
)

from domains import extract_domains
from validator import validate_domains
from ranker import rank_results

from cache import (
    optimize_stage_files,
    load_cache,
    cache_count
)

OUTPUT_DIR = "output"
CLEAN_IPS_FILE = "output/clean_ips.txt"
CACHE_FILE = "output/scanned_cache.txt"


def ensure_output():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)


def exists(path):
    return os.path.exists(path) and os.path.getsize(path) > 0


def count_new_ips():
    """شمارش IPهای جدید که هنوز اسکن نشده‌اند"""
    if not exists(CLEAN_IPS_FILE):
        return 0
    
    cache = load_cache()
    scanned_ips = set()
    
    # استخراج IPهای اسکن شده از کش
    for key in cache:
        ip = key.split(":")[0] if ":" in key else key
        scanned_ips.add(ip)
    
    total_new = 0
    try:
        with open(CLEAN_IPS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                ip = line.strip()
                if ip and ip not in scanned_ips:
                    total_new += 1
    except:
        pass
    
    return total_new


def prepare():
    """مرحله آماده‌سازی با چک کردن IPهای جدید"""
    ensure_output()
    
    # شمارش IPهای جدید قبل از دانلود
    old_new_count = count_new_ips()
    
    # همیشه دانلود جدید انجام بده
    print("DOWNLOAD START")
    download_sources()
    
    # همیشه پاکسازی انجام بده
    print("CLEAN START")
    clean_ips()
    
    # شمارش IPهای جدید بعد از دانلود
    new_new_count = count_new_ips()
    
    print(f"NEW IPS AVAILABLE: {new_new_count}")
    
    # اگر IP جدیدی وجود نداره، پیام بده
    if new_new_count == 0:
        print("⚠️ NO NEW IPS TO SCAN - ALL IPS ALREADY SCANNED")
        # ولی همچنان ادامه بده تا splitter تصمیم بگیره


def run_tcp():
    prepare()
    
    # بررسی اینکه آیا IP جدیدی برای اسکن وجود داره
    new_count = count_new_ips()
    if new_count == 0:
        print("✅ ALL IPS SCANNED - SKIPPING TCP SCAN")
        return
    
    print(f"🔄 STARTING TCP SCAN FOR {new_count} NEW IPS")
    
    input_file = split_file()
    
    if not exists(input_file):
        print("NO PART AVAILABLE")
        return
    
    print("TCP START")
    tcp_scan(input_file)
    print("TCP DONE")


def run_tls():
    prepare()
    
    if not exists("output/tcp_live.txt"):
        print("NO TCP CACHE")
        return
    
    # بررسی اینکه آیا TLS جدیدی برای اسکن وجود داره
    cache = load_cache()
    scanned_ips = set()
    for key in cache:
        ip = key.split(":")[0] if ":" in key else key
        scanned_ips.add(ip)
    
    tcp_ips = set()
    try:
        with open("output/tcp_live.txt", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    tcp_ips.add(line.split(":")[0])
    except:
        pass
    
    new_tcp_ips = tcp_ips - scanned_ips
    if not new_tcp_ips:
        print("✅ NO NEW TCP IPS TO SCAN")
        return
    
    print(f"🔄 STARTING TLS SCAN FOR {len(new_tcp_ips)} NEW IPS")
    
    print("TLS START")
    tls_scan()
    print("TLS DONE")


def run_https():
    prepare()
    
    if not exists("output/tls_live.txt"):
        print("NO TLS CACHE")
        return
    
    print("HTTPS START")
    https_scan()
    print("HTTPS DONE")


def run_fp():
    prepare()
    
    if not exists("output/https_live.txt"):
        print("NO HTTPS CACHE")
        return
    
    print("FP START")
    fingerprint_scan()
    print("FP DONE")


def run_geo():
    prepare()
    
    if not exists("output/fingerprint_results.txt"):
        print("NO FP CACHE")
        return
    
    print("GEO START")
    geo_scan()
    print("GEO DONE")


def run_finalize():
    prepare()
    
    if not exists("output/results.txt"):
        print("NO RESULTS")
        return
    
    print("OPTIMIZE CACHE")
    optimize_stage_files()
    
    if exists("output/tls_live.txt"):
        print("DOMAIN EXTRACT")
        extract_domains()
    
    if exists("output/domains_raw.txt"):
        print("DOMAIN VALIDATE")
        validate_domains()
    
    print("RANK START")
    rank_results()
    
    # نمایش آمار نهایی
    cache_size = cache_count()
    print(f"📊 TOTAL CACHED IPs: {cache_size}")
    print(f"📊 NEW IPS AVAILABLE: {count_new_ips()}")
    
    print("FINAL DONE")


def main():
    ensure_output()
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--tcp", action="store_true")
    parser.add_argument("--tls", action="store_true")
    parser.add_argument("--https", action="store_true")
    parser.add_argument("--fp", action="store_true")
    parser.add_argument("--geo", action="store_true")
    parser.add_argument("--finalize", action="store_true")
    
    args = parser.parse_args()
    
    load_config()
    
    print("ARISTA START")
    
    if args.tcp:
        run_tcp()
    elif args.tls:
        run_tls()
    elif args.https:
        run_https()
    elif args.fp:
        run_fp()
    elif args.geo:
        run_geo()
    elif args.finalize:
        run_finalize()
    else:
        run_tcp()
    
    print("ARISTA DONE")


if __name__ == "__main__":
    main()
