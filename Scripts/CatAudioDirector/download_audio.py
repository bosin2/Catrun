"""Download a verified provider-returned HTTPS URL; never submits generation jobs."""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import socket
import time
import urllib.error
import urllib.parse
import urllib.request


def validate_url(url, hosts):
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or '').lower()
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError('Only credential-free HTTPS URLs on port 443 are allowed')
    if not host or host not in hosts:
        raise ValueError('Download host is not in the explicit provider host allowlist')
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Download hostname must resolve only to public addresses')
    return host


class Redirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, hosts):
        self.hosts = hosts

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        validate_url(newurl, self.hosts)
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def download(url, destination, hosts, max_bytes=256 * 1024 * 1024):
    host = validate_url(url, hosts)
    destination = Path(destination).resolve()
    receipt = destination.with_suffix(destination.suffix + '.receipt.json')
    part = destination.with_suffix(destination.suffix + '.part')
    if destination.exists() or receipt.exists() or part.exists():
        raise ValueError('Destination/receipt/partial already exists; choose a new name')
    destination.parent.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(Redirects(hosts))
    for attempt in range(1, 4):
        owns_part = False
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'CatAudioDirector/1.0'})
            with opener.open(request, timeout=30) as response, part.open('xb') as output:
                owns_part = True
                if response.headers.get_content_type() in ('text/html', 'application/json'):
                    raise ValueError('Provider returned a page/error instead of audio')
                digest, length = hashlib.sha256(), 0
                while block := response.read(1024 * 1024):
                    length += len(block)
                    if length > max_bytes:
                        raise ValueError('Audio exceeds download size limit')
                    output.write(block)
                    digest.update(block)
                if not length:
                    raise ValueError('Empty download')
            # Exclusive destination creation avoids replacing a file created concurrently.
            with destination.open('xb') as final, part.open('rb') as source:
                while block := source.read(1024 * 1024):
                    final.write(block)
            part.unlink()
            result = {'source_host': host, 'path': str(destination), 'bytes': length,
                      'sha256': digest.hexdigest(), 'attempts': attempt,
                      'verified_audio': False, 'next_step': 'local pipeline decode and QA'}
            with receipt.open('x', encoding='utf-8') as output:
                output.write(json.dumps(result, indent=2))
            return result
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            if owns_part:
                part.unlink(missing_ok=True)
            retryable = not isinstance(error, urllib.error.HTTPError) or error.code in (408, 429, 500, 502, 503, 504)
            if attempt == 3 or not retryable:
                raise RuntimeError('Download failed; verify provider status/URL without resubmitting generation') from None
            time.sleep(attempt)
        except Exception:
            if owns_part:
                part.unlink(missing_ok=True)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url-file', required=True, help='Private UTF-8 text file containing returned URL; not logged')
    parser.add_argument('--output', required=True)
    parser.add_argument('--allowed-host', action='append', required=True, help='Exact host observed in verified provider result; repeat for redirects')
    args = parser.parse_args()
    try:
        url = Path(args.url_file).read_text(encoding='utf-8-sig').strip()
        result = download(url, args.output, {host.lower() for host in args.allowed_host})
        print(json.dumps(result, indent=2))
        return 0
    except Exception as error:
        # Never include raw network exceptions or a signed URL in console/log output.
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__, 'message': 'Download rejected or failed; verify host, destination, and provider job.'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
