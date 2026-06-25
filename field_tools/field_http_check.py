#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""现场 HTTP 接口最小检查工具。

用途：
1. 验证设备或厂家网关 HTTP/HTTPS 接口是否可访问。
2. 保存 GET 状态接口响应样例。
3. 可选 dry-run / 确认执行 POST 控制接口，形成 JSON 证据。

只依赖 Python 标准库，不依赖 EdgeFusion 项目代码。
"""

import argparse
import base64
import json
import ssl
import sys
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def parse_header(text):
    if ":" not in text:
        raise ValueError(f"header 格式应为 Name: Value，实际为: {text}")
    name, value = text.split(":", 1)
    return name.strip(), value.strip()


def build_headers(args):
    headers = {}
    for item in args.header or []:
        name, value = parse_header(item)
        headers[name] = value

    auth = args.auth or ""
    if auth.startswith("bearer:"):
        headers["Authorization"] = "Bearer " + auth.split(":", 1)[1]
    elif auth.startswith("basic:"):
        _, rest = auth.split(":", 1)
        if ":" not in rest:
            raise ValueError("--auth basic:user:password 缺少密码部分")
        user, password = rest.split(":", 1)
        token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = "Basic " + token
    elif auth and auth != "none":
        raise ValueError("--auth 仅支持 none、bearer:TOKEN、basic:user:password")

    return headers


def read_body(args):
    if args.body and args.body_file:
        raise ValueError("--body 和 --body-file 只能提供一个")
    if args.body_file:
        with open(args.body_file, "r", encoding="utf-8") as handle:
            return handle.read()
    return args.body


def make_url(base_url, path_or_url):
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    return urljoin(base_url.rstrip("/") + "/", path_or_url.lstrip("/"))


def parse_json_maybe(text):
    try:
        return json.loads(text)
    except Exception:
        return None


def simple_json_path(data, path):
    if not path or not path.startswith("$."):
        return None
    current = data
    for part in path[2:].split("."):
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except Exception:
                return None
        else:
            return None
    return current


def parse_field_hint(text):
    if "=" not in text:
        raise ValueError("--field 格式应为 name=$.path")
    name, path = text.split("=", 1)
    return name.strip(), path.strip()


def send_request(url, method, headers, body_text, timeout, insecure=False):
    data = None
    if body_text is not None:
        data = body_text.encode("utf-8")
        headers = dict(headers)
        headers.setdefault("Content-Type", "application/json")

    request = Request(url, data=data, headers=headers, method=method.upper())

    context = None
    if insecure and url.startswith("https://"):
        context = ssl._create_unverified_context()

    try:
        with urlopen(request, timeout=timeout, context=context) as response:
            body = response.read()
            text = body.decode("utf-8", errors="replace")
            return {
                "success": 200 <= response.status < 300,
                "status": response.status,
                "reason": response.reason,
                "headers": dict(response.headers.items()),
                "body": text,
                "json": parse_json_maybe(text),
                "error": None,
            }
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {
            "success": False,
            "status": exc.code,
            "reason": exc.reason,
            "headers": dict(exc.headers.items()) if exc.headers else {},
            "body": body,
            "json": parse_json_maybe(body),
            "error": str(exc),
        }
    except URLError as exc:
        return {
            "success": False,
            "status": None,
            "reason": None,
            "headers": {},
            "body": "",
            "json": None,
            "error": str(exc.reason),
        }


def build_parser():
    parser = argparse.ArgumentParser(description="现场 HTTP/JSON 接口最小检查。")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--get")
    parser.add_argument("--post")
    parser.add_argument("--body")
    parser.add_argument("--body-file")
    parser.add_argument("--auth", default="none")
    parser.add_argument("--header", action="append")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--insecure", action="store_true")
    parser.add_argument("--field", action="append")
    parser.add_argument("--confirm-write", action="store_true")
    parser.add_argument("--json-report")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.get and not args.post:
        parser.error("--get 或 --post 至少提供一个")
        return 2

    headers = build_headers(args)
    body_text = read_body(args)
    field_hints = dict(parse_field_hint(item) for item in (args.field or []))

    report = {"tool": "field_http_check.py", "requests": [], "success": False}

    if args.get:
        url = make_url(args.base_url, args.get)
        result = send_request(url, "GET", headers, None, args.timeout, args.insecure)
        report["requests"].append({"method": "GET", "url": url, "result": result})

    if args.post:
        url = make_url(args.base_url, args.post)
        if not args.confirm_write:
            print("DRY-RUN")
        else:
            result = send_request(url, "POST", headers, body_text, args.timeout, args.insecure)
            report["requests"].append({"method": "POST", "url": url, "result": result})

    report["success"] = any(r["result"].get("success") for r in report["requests"])

    print("HTTP check done", report["success"])

    if args.json_report:
        with open(args.json_report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    return 0 if report["success"] else 2


if __name__ == "__main__":
    sys.exit(main())
