#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""现场 HTTP 接口最小检查工具。

用途：
1. 验证设备或厂家网关 HTTP/HTTPS 接口是否可访问。
2. 保存 GET 状态接口响应样例，并按简单 JSONPath 标出关键字段。
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


def redact_headers(headers):
    output = {}
    for key, value in headers.items():
        if key.lower() in {"authorization", "cookie", "x-api-key"}:
            output[key] = "***"
        else:
            output[key] = value
    return output


def build_headers(args):
    headers = {}
    for item in args.header or []:
        name, value = parse_header(item)
        headers[name] = value

    auth = args.auth or "none"
    if auth == "none":
        return headers
    if auth.startswith("bearer:"):
        headers["Authorization"] = "Bearer " + auth.split(":", 1)[1]
        return headers
    if auth.startswith("basic:"):
        _, rest = auth.split(":", 1)
        if ":" not in rest:
            raise ValueError("--auth basic:user:password 缺少密码部分")
        user, password = rest.split(":", 1)
        token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = "Basic " + token
        return headers
    raise ValueError("--auth 仅支持 none、bearer:TOKEN、basic:user:password")


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
    if not base_url:
        raise ValueError("使用相对路径时必须提供 --base-url")
    return urljoin(base_url.rstrip("/") + "/", path_or_url.lstrip("/"))


def parse_json_maybe(text):
    try:
        return json.loads(text)
    except Exception:
        return None


def simple_json_path(data, path):
    """支持 $.a.b.0.c 这种最小 JSONPath，现场够用即可。"""
    if data is None or not path or not path.startswith("$."):
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
        raise ValueError("--field 格式应为 name=$.path，例如 --field power=$.data.power")
    name, path = text.split("=", 1)
    name = name.strip()
    path = path.strip()
    if not name or not path:
        raise ValueError("--field 的 name 和 path 不能为空")
    return name, path


def send_request(url, method, headers, body_text, timeout, insecure=False):
    request_headers = dict(headers)
    data = None
    if body_text is not None:
        data = body_text.encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    request = Request(url, data=data, headers=request_headers, method=method.upper())

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
    except Exception as exc:
        return {
            "success": False,
            "status": None,
            "reason": None,
            "headers": {},
            "body": "",
            "json": None,
            "error": str(exc),
        }


def extract_fields(responses, field_hints):
    if not field_hints:
        return {}
    first_json = None
    for item in responses:
        data = item.get("result", {}).get("json")
        if data is not None:
            first_json = data
            break
    return {
        name: {"path": path, "value": simple_json_path(first_json, path)}
        for name, path in field_hints.items()
    }


def build_parser():
    parser = argparse.ArgumentParser(description="现场 HTTP/JSON 接口最小检查。")
    parser.add_argument("--base-url", default="", help="接口根地址，例如 http://192.168.1.20")
    parser.add_argument("--get", help="状态接口路径或完整 URL，例如 /api/status")
    parser.add_argument("--post", help="控制接口路径或完整 URL，例如 /api/control")
    parser.add_argument("--body", help="POST body 文本，通常为 JSON")
    parser.add_argument("--body-file", help="从文件读取 POST body")
    parser.add_argument("--auth", default="none", help="none、bearer:TOKEN、basic:user:password")
    parser.add_argument("--header", action="append", help="额外 header，可重复，例如 'X-Token: xxx'")
    parser.add_argument("--field", action="append", help="字段路径，可重复，例如 power=$.data.power")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--insecure", action="store_true", help="HTTPS 测试时忽略证书校验")
    parser.add_argument("--confirm-write", action="store_true", help="确认真正执行 POST 控制请求")
    parser.add_argument("--json-report", help="保存 JSON 报告")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.get and not args.post:
        parser.error("--get 或 --post 至少提供一个")
        return 2

    try:
        headers = build_headers(args)
        body_text = read_body(args)
        field_hints = dict(parse_field_hint(item) for item in (args.field or []))
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    report = {
        "tool": "field_http_check.py",
        "timestamp": now_iso(),
        "protocol": "http",
        "base_url": args.base_url,
        "request_headers": redact_headers(headers),
        "requests": [],
        "field_values": {},
        "success": False,
    }

    if args.get:
        url = make_url(args.base_url, args.get)
        result = send_request(url, "GET", headers, None, args.timeout, args.insecure)
        report["requests"].append({"method": "GET", "url": url, "result": result})

    if args.post:
        url = make_url(args.base_url, args.post)
        planned = {
            "method": "POST",
            "url": url,
            "body": body_text,
            "confirmed": bool(args.confirm_write),
        }
        if not args.confirm_write:
            report["requests"].append({**planned, "dry_run": True, "result": {"success": True, "note": "未加 --confirm-write，未真正下发"}})
        else:
            result = send_request(url, "POST", headers, body_text, args.timeout, args.insecure)
            report["requests"].append({**planned, "dry_run": False, "result": result})

    report["field_values"] = extract_fields(report["requests"], field_hints)
    report["success"] = any(item["result"].get("success") for item in report["requests"])

    print("HTTP 现场检查结果")
    for item in report["requests"]:
        result = item["result"]
        status = result.get("status", "-")
        detail = result.get("error") or result.get("note") or result.get("reason") or ""
        print(f"  {item['method']:<4} {item['url']} -> success={result.get('success')} status={status} {detail}")
    if report["field_values"]:
        print("字段提取")
        for name, item in report["field_values"].items():
            print(f"  {name}: {item['path']} = {item['value']}")

    if args.json_report:
        with open(args.json_report, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        print(f"已保存 JSON 报告：{args.json_report}")

    return 0 if report["success"] else 2


if __name__ == "__main__":
    sys.exit(main())
