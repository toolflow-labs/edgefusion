import argparse
import os

import werkzeug
from flask import Flask, jsonify, render_template, request

from .collector import CollectorLoop, collect_once
from .config import load_config
from .control import write_control
from .mode_engine import arbitrate_mode, build_site_state, plan_export_protect
from .state import LatestState


DEFAULT_CONFIG = os.path.join(os.path.dirname(__file__), "config.example.yaml")

# Flask 2.2.x test_client expects werkzeug.__version__. Newer Werkzeug removed it.
# Keep this local so the pilot runtime does not force dependency pin changes.
if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "unknown"


def create_app(config_path=DEFAULT_CONFIG, start_background=False, readers=None, writers=None):
    config = load_config(config_path)
    latest = LatestState(config.get("site", {}))
    collector_loop = CollectorLoop(config, latest, readers=readers)
    app = Flask(__name__)
    app.config["pilot_config"] = config
    app.config["latest_state"] = latest
    app.config["collector_loop"] = collector_loop
    app.config["readers"] = readers
    app.config["writers"] = writers

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/snapshot")
    def snapshot():
        return jsonify(latest.snapshot())

    @app.route("/api/collect", methods=["POST"])
    def collect_now():
        snapshots = collect_once(config, readers=app.config.get("readers"))
        latest.update(snapshots)
        return jsonify(latest.snapshot())

    @app.route("/api/mode")
    def mode():
        state = build_site_state(latest.all(), config.get("mode", {}))
        decision = arbitrate_mode(state, config.get("mode", {}))
        plan = plan_export_protect(state, config.get("mode", {})) if decision["mode"] == "export_protect" else None
        return jsonify({"mode": decision["mode"], "reason": decision["reason"], "state": {
            "grid_power_w": state["grid_power_w"],
            "pv_power_w": state["pv_power_w"],
            "trusted": state["trusted"],
            "trust_issues": state["trust_issues"],
        }, "plan": plan})

    @app.route("/api/control", methods=["POST"])
    def control():
        payload = request.get_json(force=True) or {}
        result = write_control(
            config,
            payload.get("device_id"),
            payload.get("field"),
            payload.get("value"),
            writers=app.config.get("writers"),
        )
        return jsonify(result), 200 if result["success"] else 400

    if start_background:
        collector_loop.start()

    return app


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run pilot EMS.")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5050)
    args = parser.parse_args(argv)

    app = create_app(args.config)
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    exit(main())
