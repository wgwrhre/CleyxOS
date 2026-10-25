"""Network diagnostics and explicitly confirmed HTTPS transfers."""

from __future__ import annotations

import os
import socket
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import dns.resolver
import psutil
import requests
from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn, TimeRemainingColumn
from rich.table import Table

from utils.terminal import console

MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024


def validate_url(url: str, *, https_only: bool = False) -> str:
    candidate = url.strip()
    if not candidate.startswith(("https://", "http://")):
        candidate = "https://" + candidate
    parsed = urlsplit(candidate)
    allowed = {"https"} if https_only else {"http", "https"}
    if parsed.scheme not in allowed or not parsed.hostname or any(char.isspace() for char in candidate):
        raise ValueError("Enter a valid HTTPS URL." if https_only else "Enter a valid HTTP or HTTPS URL.")
    if parsed.username or parsed.password:
        raise ValueError("Credentials in URLs are not allowed.")
    return candidate


def public_ip() -> str:
    response = requests.get("https://api.ipify.org", timeout=8)
    response.raise_for_status()
    result = response.text.strip()
    # Validate rather than echo arbitrary response content.
    socket.inet_pton(socket.AF_INET6 if ":" in result else socket.AF_INET, result)
    return result


def dns_records(domain: str, record_type: str) -> list[str]:
    domain = domain.rstrip(".")
    if not domain or len(domain) > 253 or any(not label or len(label) > 63 for label in domain.split(".")):
        raise ValueError("Enter a valid domain name.")
    if record_type not in {"A", "AAAA", "MX", "TXT", "CNAME"}:
        raise ValueError("Record type must be A, AAAA, MX, TXT, or CNAME.")
    try:
        answers = dns.resolver.resolve(domain, record_type, lifetime=5)
        return [answer.to_text() for answer in answers]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return []
    except dns.exception.DNSException as error:
        raise OSError(f"DNS lookup failed: {error}") from error


def http_info(url: str) -> tuple[int, float, str, str, str]:
    url = validate_url(url)
    started = time.perf_counter()
    with requests.get(url, timeout=(5, 10), stream=True, allow_redirects=True) as response:
        elapsed = time.perf_counter() - started
        return (response.status_code, elapsed, response.headers.get("Content-Type", "—"),
                response.headers.get("Server", "—"), response.url)


def download(url: str, destination: Path) -> int:
    url = validate_url(url, https_only=True)
    if destination.exists():
        raise FileExistsError(f"Destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    if partial.exists() or partial.is_symlink():
        raise FileExistsError(f"Partial download already exists: {partial}; inspect or remove it before retrying.")
    received = 0
    partial_created = False
    try:
        current_url = url
        response = None
        for _ in range(6):
            response = requests.get(current_url, stream=True, timeout=(8, 30), allow_redirects=False)
            if response.is_redirect or response.is_permanent_redirect:
                location = response.headers.get("Location")
                response.close()
                if not location:
                    raise OSError("Download redirect did not include a destination.")
                current_url = validate_url(urljoin(current_url, location), https_only=True)
                continue
            break
        else:
            raise OSError("Download exceeded the redirect limit.")
        assert response is not None
        with response:
            response.raise_for_status()
            length_header = response.headers.get("Content-Length")
            total = int(length_header) if length_header and length_header.isdigit() else 0
            if total > MAX_DOWNLOAD_BYTES:
                raise ValueError("Download exceeds the 512 MiB safety limit.")
            with Progress(TextColumn("[progress.description]{task.description}"), BarColumn(),
                          DownloadColumn(), TimeRemainingColumn(), console=console) as progress:
                task = progress.add_task("Downloading", total=total or None)
                with partial.open("xb") as output:
                    partial_created = True
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if not chunk:
                            continue
                        received += len(chunk)
                        if received > MAX_DOWNLOAD_BYTES:
                            raise ValueError("Download exceeded the 512 MiB safety limit.")
                        output.write(chunk)
                        progress.update(task, advance=len(chunk))
        # Hard-link commit is atomic and fails rather than replacing a racing destination.
        os.link(partial, destination)
        partial.unlink()
        return received
    except BaseException:
        if partial_created:
            partial.unlink(missing_ok=True)
        raise


def speed_test() -> tuple[float, float, float]:
    """Approximate latency, 5 MiB download, and 1 MiB upload using Cloudflare speed endpoints."""
    base = "https://speed.cloudflare.com"
    started = time.perf_counter()
    requests.get(f"{base}/__down?bytes=0", timeout=(6, 12)).raise_for_status()
    latency = (time.perf_counter() - started) * 1000
    download_bytes = 5 * 1024 * 1024
    started = time.perf_counter()
    with requests.get(f"{base}/__down?bytes={download_bytes}", stream=True, timeout=(6, 30)) as response:
        response.raise_for_status()
        received = sum(len(chunk) for chunk in response.iter_content(64 * 1024) if chunk)
    download_mbps = received * 8 / max(time.perf_counter() - started, 0.001) / 1_000_000
    upload_bytes = 1024 * 1024
    started = time.perf_counter()
    response = requests.post(f"{base}/__up", data=b"0" * upload_bytes,
                             headers={"Content-Type": "application/octet-stream"}, timeout=(6, 30))
    response.raise_for_status()
    upload_mbps = upload_bytes * 8 / max(time.perf_counter() - started, 0.001) / 1_000_000
    return latency, download_mbps, upload_mbps


def netstat_table() -> Table:
    table = Table(title="Network Connections", border_style="cyan", header_style="bold cyan")
    table.add_column("Local", style="cyan")
    table.add_column("Remote")
    table.add_column("State")
    table.add_column("PID", justify="right")
    try:
        connections = psutil.net_connections(kind="inet")
    except (psutil.AccessDenied, PermissionError):
        connections = []
    for conn in connections:
        local = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "—"
        remote = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "—"
        table.add_row(local, remote, conn.status or "—", str(conn.pid or "—"))
    return table