#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""现场 MQTT 接口最小检查工具。

用途：
1. 验证 broker 地址、认证和 topic 权限。
2. 订阅遥测 topic，保存 N 条 payload 样例。
3. 可选 dry-run / 确认发布控制 payload，形成 JSON 证据。
"""

import argparse
import json
import sys
import time
from datetime import datetime


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def make_client(args, messages):
    import paho.mqtt.client as mqtt

    userdata = {
        "connected": False,
        "connect_rc": None,
        "subscribe_topics": [t for t in [args.topic, args.ack_topic] if t],
    }

    client = mqtt.Client(client_id=args.client_id or "", userdata=userdata)

    if args.username:
        client.username_pw_set(args.username, args.password)

    if args.tls:
        client.tls_set()

    def on_connect(client, userdata, flags, rc):
        userdata["connect_rc"] = rc
        userdata["connected"] = rc == 0
        if rc == 0:
            for t in userdata["subscribe_topics"]:
                client.subscribe(t, qos=args.qos)

    def on_message(client, userdata, msg):
        messages.append({
            "timestamp": now_iso(),
            "topic": msg.topic,
            "payload": msg.payload.decode("utf-8", errors="replace"),
        })

    client.on_connect = on_connect
    client.on_message = on_message
    return client, userdata


def main(argv=None):
    parser = argparse.ArgumentParser(description="MQTT check")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--topic")
    parser.add_argument("--pub-topic")
    parser.add_argument("--payload")
    parser.add_argument("--confirm-publish", action="store_true")
    parser.add_argument("--json-report")

    args = parser.parse_args(argv)

    messages = []
    client, userdata = make_client(args, messages)

    report = {"tool": "field_mqtt_check.py", "messages": [], "success": False}

    client.connect(args.host, args.port, 30)
    client.loop_start()

    time.sleep(2)

    if args.pub_topic and args.confirm_publish:
        client.publish(args.pub_topic, args.payload)

    time.sleep(2)
    client.loop_stop()
    client.disconnect()

    report["messages"] = messages
    report["success"] = userdata.get("connected", False)

    print("MQTT done", report["success"])

    if args.json_report:
        with open(args.json_report, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

    return 0 if report["success"] else 2


if __name__ == "__main__":
    sys.exit(main())
