#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""现场 MQTT 接口最小检查工具。

用途：
1. 验证 broker 地址、认证和 topic 权限。
2. 订阅遥测 topic，保存 N 条 payload 样例。
3. 可选 dry-run / 确认发布控制 payload，形成 JSON 证据。

依赖 paho-mqtt。现场机器可执行：pip install paho-mqtt==1.6.1
"""

import argparse
import json
import sys
import time
from datetime import datetime


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def read_payload(args):
    if args.payload and args.payload_file:
        raise ValueError("--payload 和 --payload-file 只能提供一个")
    if args.payload_file:
        with open(args.payload_file, "r", encoding="utf-8") as handle:
            return handle.read()
    return args.payload


def import_mqtt():
    try:
        import paho.mqtt.client as mqtt
    except ImportError as exc:
        raise RuntimeError("缺少依赖：请先安装 paho-mqtt，例如 pip install paho-mqtt==1.6.1") from exc
    return mqtt


def make_client(args, messages, events):
    mqtt = import_mqtt()

    userdata = {
        "connected": False,
        "connect_rc": None,
        "subscribe_topics": [topic for topic in [args.topic, args.ack_topic] if topic],
    }

    client = mqtt.Client(client_id=args.client_id or "", userdata=userdata)

    if args.username:
        client.username_pw_set(args.username, args.password)

    if args.tls:
        client.tls_set()
        if args.insecure:
            client.tls_insecure_set(True)

    def on_connect(client, userdata, flags, rc, *extra):
        userdata["connect_rc"] = rc
        userdata["connected"] = rc == 0
        events.append({"timestamp": now_iso(), "event": "connect", "rc": rc})
        if rc == 0:
            for topic in userdata["subscribe_topics"]:
                client.subscribe(topic, qos=args.qos)
                events.append({"timestamp": now_iso(), "event": "subscribe", "topic": topic, "qos": args.qos})

    def on_disconnect(client, userdata, rc, *extra):
        events.append({"timestamp": now_iso(), "event": "disconnect", "rc": rc})

    def on_message(client, userdata, msg):
        payload = msg.payload.decode("utf-8", errors="replace")
        messages.append({
            "timestamp": now_iso(),
            "topic": msg.topic,
            "qos": msg.qos,
            "retain": msg.retain,
            "payload": payload,
            "json": parse_json_maybe(payload),
        })

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    return client, userdata


def parse_json_maybe(text):
    try:
        return json.loads(text)
    except Exception:
        return None


def wait_for_messages(messages, count, wait_seconds):
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if count and len(messages) >= count:
            return
        time.sleep(0.2)


def build_parser():
    parser = argparse.ArgumentParser(description="现场 MQTT 接口最小检查。")
    parser.add_argument("--host", required=True, help="broker 地址")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--tls", action="store_true")
    parser.add_argument("--insecure", action="store_true", help="TLS 测试时忽略证书校验")
    parser.add_argument("--client-id", default="")
    parser.add_argument("--topic", help="订阅遥测 topic，例如 device/+/telemetry")
    parser.add_argument("--ack-topic", help="订阅控制 ack topic")
    parser.add_argument("--count", type=int, default=3, help="期望采集 payload 数量，默认 3")
    parser.add_argument("--wait-seconds", type=float, default=10.0)
    parser.add_argument("--qos", type=int, default=0, choices=[0, 1, 2])
    parser.add_argument("--pub-topic", help="控制发布 topic")
    parser.add_argument("--payload", help="控制 payload")
    parser.add_argument("--payload-file", help="从文件读取控制 payload")
    parser.add_argument("--confirm-publish", action="store_true", help="确认真正 publish 控制 payload")
    parser.add_argument("--json-report", help="保存 JSON 报告")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.topic and not args.pub_topic:
        parser.error("--topic 或 --pub-topic 至少提供一个")
        return 2

    try:
        payload = read_payload(args)
        client_messages = []
        events = []
        client, userdata = make_client(args, client_messages, events)
    except (RuntimeError, ValueError) as exc:
        print(str(exc))
        return 2

    report = {
        "tool": "field_mqtt_check.py",
        "timestamp": now_iso(),
        "protocol": "mqtt",
        "broker": f"{args.host}:{args.port}",
        "topic": args.topic,
        "ack_topic": args.ack_topic,
        "publish": None,
        "events": events,
        "messages": client_messages,
        "success": False,
    }

    try:
        client.connect(args.host, args.port, keepalive=30)
        client.loop_start()

        time.sleep(1.0)

        if args.pub_topic:
            publish_item = {
                "topic": args.pub_topic,
                "payload": payload,
                "qos": args.qos,
                "confirmed": bool(args.confirm_publish),
                "dry_run": not args.confirm_publish,
                "success": True,
            }
            if not args.confirm_publish:
                publish_item["note"] = "未加 --confirm-publish，未真正发布控制 payload"
            else:
                result = client.publish(args.pub_topic, payload or "", qos=args.qos)
                while not result.is_published() and time.time() < time.time() + args.wait_seconds:
                    time.sleep(0.1)
                publish_item["success"] = result.rc == 0
                publish_item["rc"] = result.rc
            report["publish"] = publish_item

        wait_for_messages(client_messages, args.count if args.topic else 0, args.wait_seconds)
    except Exception as exc:
        events.append({"timestamp": now_iso(), "event": "exception", "error": str(exc)})
    finally:
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass

    connected = bool(userdata.get("connected"))
    subscribe_ok = bool(args.topic and client_messages) or not args.topic
    publish_ok = not report["publish"] or bool(report["publish"].get("success"))
    report["success"] = connected and subscribe_ok and publish_ok

    print("MQTT 现场检查结果")
    print(f"  broker   : {report['broker']}")
    print(f"  connected: {connected}, rc={userdata.get('connect_rc')}")
    if args.topic:
        print(f"  subscribe: {args.topic}, messages={len(client_messages)}")
    if report["publish"]:
        print(f"  publish  : {report['publish']['topic']}, dry_run={report['publish']['dry_run']}, success={report['publish']['success']}")

    if args.json_report:
        with open(args.json_report, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        print(f"已保存 JSON 报告：{args.json_report}")

    return 0 if report["success"] else 2


if __name__ == "__main__":
    sys.exit(main())
