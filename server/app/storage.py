"""Where models, jobs and orders live.

A directory of JSON files and the uploads beside them.  It is the smallest
thing that survives a restart, and it keeps a real database decision for when
there are accounts to attach models to (phase 3).  ``Store`` is the only
thing that touches the disk, so swapping it for Postgres later is one class.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid

from .models import BrickModel
from .pipeline.orders import Order


class Store:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self._lock = threading.Lock()
        for sub in ("uploads", "models", "orders", "jobs", "previews"):
            os.makedirs(os.path.join(self.root, sub), exist_ok=True)

    # ---- paths -----------------------------------------------------------

    def _path(self, kind: str, ident: str) -> str:
        return os.path.join(self.root, kind, "%s.json" % ident)

    def preview_path(self, model_id: str) -> str:
        return os.path.join(self.root, "previews", "%s.png" % model_id)

    def upload_dir(self, job_id: str) -> str:
        d = os.path.join(self.root, "uploads", job_id)
        os.makedirs(d, exist_ok=True)
        return d

    # ---- jobs ------------------------------------------------------------

    def new_job(self) -> str:
        return uuid.uuid4().hex

    def save_job(self, job: dict) -> None:
        self._write("jobs", job["id"], job)

    def get_job(self, job_id: str) -> dict:
        return self._read("jobs", job_id)

    # ---- models ----------------------------------------------------------

    def save_model(self, model_id: str, payload: dict) -> None:
        payload = dict(payload)
        payload["id"] = model_id
        payload.setdefault("created_at", time.time())
        payload["updated_at"] = time.time()
        self._write("models", model_id, payload)

    def get_model(self, model_id: str) -> dict:
        return self._read("models", model_id)

    def load_brick_model(self, model_id: str) -> BrickModel:
        return BrickModel.from_dict(self.get_model(model_id)["model"])

    def list_models(self, limit: int = 50, examples: bool = False,
                    owner: str | None = None) -> list:
        """The saved models, newest first.

        The homepage examples live in this same store so they open as ordinary
        sets, but they are the shop's, not the customer's, and listing them
        under "My sets" alongside a set someone actually made is wrong. They
        are left out unless asked for.

        With an ``owner``, only that install's sets come back. Everything on
        one server would otherwise be listed to everybody.
        """
        out = []
        d = os.path.join(self.root, "models")
        for name in os.listdir(d):
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(d, name)) as fh:
                    m = json.load(fh)
            except (OSError, ValueError):
                continue
            if not examples and m.get("status") == "example":
                continue
            if owner is not None and m.get("owner") != owner:
                continue
            out.append({
                "id": m.get("id"),
                "name": m.get("model", {}).get("name", "Model"),
                "piece_count": m.get("model", {}).get("piece_count", 0),
                "created_at": m.get("created_at", 0),
                "updated_at": m.get("updated_at", 0),
                "status": m.get("status", "draft"),
                "thumbnail": m.get("thumbnail"),
                "dimensions_cm": m.get("model", {}).get("dimensions_cm"),
            })
        out.sort(key=lambda m: -m.get("updated_at", 0))
        return out[:limit]

    # ---- orders ----------------------------------------------------------

    def save_order(self, order: Order) -> None:
        self._write("orders", order.id, order.to_dict())

    def get_order(self, order_id: str) -> Order:
        d = self._read("orders", order_id)
        d.pop("status_label", None)
        d.pop("steps", None)
        return Order(**d)

    def list_orders(self) -> list:
        d = os.path.join(self.root, "orders")
        out = []
        for name in os.listdir(d):
            if name.endswith(".json"):
                try:
                    out.append(self._read("orders", name[:-5]))
                except (OSError, ValueError):
                    continue
        out.sort(key=lambda o: -o.get("created_at", 0))
        return out

    # ---- io --------------------------------------------------------------

    def _write(self, kind: str, ident: str, payload: dict) -> None:
        path = self._path(kind, ident)
        tmp = path + ".tmp"
        with self._lock:
            with open(tmp, "w") as fh:
                json.dump(payload, fh)
            os.replace(tmp, path)      # never leave a half-written file behind

    def _read(self, kind: str, ident: str) -> dict:
        path = self._path(kind, ident)
        if not os.path.exists(path):
            raise NotFound("%s %s" % (kind[:-1], ident))
        with open(path) as fh:
            return json.load(fh)


class NotFound(KeyError):
    def __str__(self) -> str:
        return "not found: %s" % self.args[0]
