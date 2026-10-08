"""Minimal MLflow tracking client over the REST API (standard library only).

The models job logs to the platform's ML tracker (ml-mlflow, MLflow 3.x with --serve-artifacts):
experiments/runs/params/metrics through /api/2.0/mlflow, artifacts through the artifact proxy
(/api/2.0/mlflow-artifacts/artifacts/...). No mlflow package is needed on the NAS host or in the
image.
"""
import json
import mimetypes
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

from shared.exceptions import ModelsError


class MlflowError(ModelsError):
    pass


class MlflowClient:
    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base = base_url.rstrip("/")
        self.timeout = timeout

    def _call(self, method: str, path: str, body: Optional[dict] = None,
              query: Optional[dict] = None) -> dict:
        url = "%s/api/2.0/mlflow/%s" % (self.base, path)
        if query:
            url += "?" + urllib.parse.urlencode(query)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            if exc.code == 404 and "RESOURCE_DOES_NOT_EXIST" in detail:
                return {"_missing": True}
            raise MlflowError("MLflow %s %s: HTTP %s %s" % (method, path, exc.code,
                                                            detail)) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise MlflowError("MLflow unreachable at %s: %s" % (self.base, exc)) from exc

    def experiment_id(self, name: str) -> str:
        got = self._call("GET", "experiments/get-by-name", query={"experiment_name": name})
        if not got.get("_missing"):
            return got["experiment"]["experiment_id"]
        return self._call("POST", "experiments/create", {"name": name})["experiment_id"]

    def start_run(self, experiment: str, run_name: str, tags: Dict[str, str]) -> Dict[str, str]:
        info = self._call("POST", "runs/create", {
            "experiment_id": self.experiment_id(experiment), "run_name": run_name,
            "start_time": int(time.time() * 1000),
            "tags": [{"key": k, "value": str(v)} for k, v in tags.items()]})["run"]["info"]
        return {"run_id": info["run_id"], "artifact_uri": info["artifact_uri"],
                "experiment_id": info["experiment_id"]}

    def log_batch(self, run_id: str, params: Optional[Dict[str, object]] = None,
                  metrics: Optional[Dict[str, float]] = None) -> None:
        now = int(time.time() * 1000)
        ps = [{"key": k, "value": str(v)[:6000]} for k, v in (params or {}).items()]
        ms = [{"key": k, "value": float(v), "timestamp": now, "step": 0}
              for k, v in (metrics or {}).items() if v == v]      # drop NaN
        for i in range(0, max(len(ps), len(ms), 1), 100):
            self._call("POST", "runs/log-batch", {"run_id": run_id, "params": ps[i:i + 100],
                                                   "metrics": ms[i:i + 100]})

    def log_artifact(self, run: Dict[str, str], local_path: str,
                     name: Optional[str] = None) -> None:
        uri = run["artifact_uri"]
        if not uri.startswith("mlflow-artifacts:/"):
            raise MlflowError("artifact store %r is not the mlflow-artifacts proxy" % uri)
        rel = uri[len("mlflow-artifacts:/"):].strip("/")
        name = name or os.path.basename(local_path)
        url = "%s/api/2.0/mlflow-artifacts/artifacts/%s/%s" % (
            self.base, urllib.parse.quote(rel), urllib.parse.quote(name))
        with open(local_path, "rb") as f:
            data = f.read()
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        req = urllib.request.Request(url, data=data, method="PUT",
                                     headers={"Content-Type": ctype})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout):
                pass
        except (urllib.error.URLError, OSError) as exc:
            raise MlflowError("artifact upload %s failed: %s" % (name, exc)) from exc

    def download_artifact(self, experiment_id: str, run_id: str, name: str) -> bytes:
        url = "%s/api/2.0/mlflow-artifacts/artifacts/%s/%s/artifacts/%s" % (
            self.base, experiment_id, run_id, urllib.parse.quote(name))
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, OSError) as exc:
            raise MlflowError("artifact download %s failed: %s" % (name, exc)) from exc

    def run_info(self, run_id: str) -> Dict[str, str]:
        info = self._call("GET", "runs/get", query={"run_id": run_id})["run"]["info"]
        return {"run_id": info["run_id"], "experiment_id": info["experiment_id"],
                "artifact_uri": info["artifact_uri"]}

    def end_run(self, run_id: str, status: str = "FINISHED") -> None:
        self._call("POST", "runs/update", {"run_id": run_id, "status": status,
                                           "end_time": int(time.time() * 1000)})

    # -- model registry (the "champion" alias is what the daily forecast uses) -------------------
    def ensure_registered_model(self, name: str, description: str = "") -> None:
        got = self._call("GET", "registered-models/get", query={"name": name})
        if got.get("_missing"):
            self._call("POST", "registered-models/create", {"name": name,
                                                             "description": description})

    def create_model_version(self, name: str, run: Dict[str, str], tags: Dict[str, str]) -> str:
        mv = self._call("POST", "model-versions/create", {
            "name": name, "source": run["artifact_uri"], "run_id": run["run_id"],
            "tags": [{"key": k, "value": str(v)} for k, v in tags.items()]})["model_version"]
        return str(mv["version"])

    def set_alias(self, name: str, alias: str, version: str) -> None:
        self._call("POST", "registered-models/alias", {"name": name, "alias": alias,
                                                        "version": version})

    def get_alias(self, name: str, alias: str) -> Optional[Dict[str, str]]:
        got = self._call("GET", "registered-models/alias", query={"name": name, "alias": alias})
        if got.get("_missing") or "model_version" not in got:
            return None
        mv = got["model_version"]
        return {"version": str(mv["version"]), "run_id": mv.get("run_id", "")}

    def run_params(self, run_id: str) -> Dict[str, str]:
        run = self._call("GET", "runs/get", query={"run_id": run_id})["run"]
        return {p["key"]: p["value"] for p in run.get("data", {}).get("params", [])}

    def run_metrics(self, run_id: str) -> Dict[str, float]:
        run = self._call("GET", "runs/get", query={"run_id": run_id})["run"]
        return {m["key"]: float(m["value"]) for m in run.get("data", {}).get("metrics", [])}

    def search_runs(self, experiment: str, filter_string: str = "", max_results: int = 20
                    ) -> List[dict]:
        got = self._call("POST", "runs/search", {
            "experiment_ids": [self.experiment_id(experiment)], "filter": filter_string,
            "max_results": max_results, "order_by": ["attributes.start_time DESC"]})
        return got.get("runs", [])
