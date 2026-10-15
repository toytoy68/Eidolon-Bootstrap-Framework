# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : identity_runtime.py
# Description : Enrôlement privé explicite lié au profil appairé, sans droit biométrique
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Own-profile enrolment and similarity checks, never authentication or switching.

Raw captures are not persisted; templates remain private data in the profile
services database. Deletion removes active templates, not old backups/SSD blocks.
Incomplete sessions expire after ten minutes and are invalidated on restart.
"""
import base64
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import threading
import uuid

from .contracts import digest, encode
from .identity_proposal import Calibration, EngineInfo, Observation, Registry, propose, _unit
from .identity_runners import FACE_PREPROCESSING, VOICE_PREPROCESSING
from .runtime_json import read_json_snapshot, _open_directory

MAX_CAPTURE = 512 * 1024


class IdentityError(ValueError):
    pass


def _require(ok, code):
    if not ok:
        raise IdentityError(code)


def engine(config, modality):
    return EngineInfo("wespeaker" if modality == "voice" else "yunet-sface", config["model"]["sha256"],
                      VOICE_PREPROCESSING if modality == "voice" else FACE_PREPROCESSING)


def validate(raw):
    _require(type(raw) is dict and set(raw) == {"schema", "modalities"}
             and raw["schema"] == "eidolon-identity-runtime/1" and type(raw["modalities"]) is dict
             and 1 <= len(raw["modalities"]) <= 2, "IDENTITY_CONFIG_INVALID")
    for modality, cfg in raw["modalities"].items():
        fields = {"samples", "model", "calibration"} | ({"min_speech_s", "max_duration_s", "speech_rms"} if modality == "voice" else {"detector"})
        _require(modality in ("voice", "face") and type(cfg) is dict and set(cfg) == fields
                 and type(cfg["samples"]) is int and 1 <= cfg["samples"] <= 16, "IDENTITY_CONFIG_INVALID")
        for role in ("model", "detector") if modality == "face" else ("model",):
            model = cfg[role]
            _require(type(model) is dict and set(model) == {"path", "sha256"}
                     and type(model["path"]) is str and Path(model["path"]).is_absolute()
                     and ".." not in Path(model["path"]).parts and "\0" not in model["path"]
                     and type(model["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", model["sha256"]), "IDENTITY_MODEL_INVALID")
        if modality == "voice":
            _require(all(type(cfg[k]) in (int, float) and math.isfinite(cfg[k]) for k in ("min_speech_s", "max_duration_s", "speech_rms"))
                     and 0 < cfg["min_speech_s"] <= cfg["max_duration_s"] <= 10
                     and 0 < cfg["speech_rms"] <= 32768, "IDENTITY_CAPTURE_POLICY_INVALID")
        if cfg["calibration"] is not None:
            _require(type(cfg["calibration"]) is dict and set(cfg["calibration"]) == set(Calibration.__dataclass_fields__), "IDENTITY_CALIBRATION_INVALID")
            c = Calibration(**dict(cfg["calibration"], score_bounds=tuple(cfg["calibration"]["score_bounds"])))
            e = engine(cfg, modality)
            _require(c.modality == modality and c.engine == e.name and c.model_sha256 == e.model_sha256
                     and c.preprocessing == e.preprocessing, "IDENTITY_CALIBRATION_MISMATCH")
    return json.loads(encode(raw))


def load(filename):
    path = Path(filename).absolute()
    fd = _open_directory(str(path.parent))
    try:
        info = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
        _require(stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o600,
                 "IDENTITY_CONFIG_PRIVATE_REQUIRED")
    finally:
        os.close(fd)
    return validate(read_json_snapshot(str(path.parent), path.name, max_bytes=65536, max_depth=6))


def observe_isolated(config, modality, data):
    """One disposable CPU inference process, pinned model bytes; no download."""
    package = str(Path(__file__).resolve().parents[1])
    bootstrap = "import sys; sys.path.insert(0,sys.argv[1]); from eidolon_core.identity_runtime import worker; worker()"
    child = subprocess.Popen([sys.executable, "-I", "-B", "-c", bootstrap, package],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             cwd="/", env={"PATH":"/usr/bin:/bin", "LANG":"C.UTF-8", "OMP_NUM_THREADS":"1", "OPENBLAS_NUM_THREADS":"1"},
                             start_new_session=True)
    payload = encode({"config": config, "modality": modality, "capture": base64.b64encode(data).decode()}).encode()
    try:
        out, _ = child.communicate(payload, timeout=30)
    except BaseException:
        try: os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        child.communicate()
        raise IdentityError("IDENTITY_ENGINE_UNAVAILABLE") from None
    _require(child.returncode == 0 and len(out) <= 262144, "IDENTITY_ENGINE_UNAVAILABLE")
    value = json.loads(out)
    _require("error_code" not in value, "IDENTITY_ENGINE_UNAVAILABLE")
    value["observed_at"] = datetime.fromisoformat(value["observed_at"])
    value["engine"] = EngineInfo(**value["engine"])
    if value["embedding"] is not None: value["embedding"] = tuple(value["embedding"])
    return Observation(**value)


def worker():
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (25, 25))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3,) * 2)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    try:
        value = json.loads(sys.stdin.buffer.read(800001))
        modality, cfg = value["modality"], value["config"]
        validate({"schema":"eidolon-identity-runtime/1", "modalities":{modality:cfg}})
        from .identity_engines import verify_model, VoiceAdapter, FaceAdapter
        from .identity_runners import WeSpeakerRunner, YuNetSFace
        e = engine(cfg, modality)
        model = verify_model(cfg["model"]["path"], cfg["model"]["sha256"], name=e.name, preprocessing=e.preprocessing)
        if modality == "voice":
            adapter = VoiceAdapter(WeSpeakerRunner(model), e, speech_rms=cfg["speech_rms"])
        else:
            detector = verify_model(cfg["detector"]["path"], cfg["detector"]["sha256"], name="yunet", preprocessing=e.preprocessing)
            runner = YuNetSFace(detector, model)
            adapter = FaceAdapter(runner.detector, runner.embedder, e)
        data = bytearray(base64.b64decode(value["capture"], validate=True))
        _require(0 < len(data) <= MAX_CAPTURE, "IDENTITY_CAPTURE_INVALID")
        observed = adapter.observe(data)
        result = asdict(observed); result["observed_at"] = observed.observed_at.isoformat()
    except Exception:
        result = {"error_code":"IDENTITY_ENGINE_UNAVAILABLE"}
    print(json.dumps(result, allow_nan=False))


class IdentityRuntime:
    def __init__(self, config, db, profile, *, clock=None, observer=None):
        self.config, self.db, self.profile = validate(config), db, profile
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.observer = observer or observe_isolated
        self.inference = threading.Lock()
        with db() as c:
            c.execute("CREATE TABLE IF NOT EXISTS identity_templates (profile TEXT, modality TEXT, revision INTEGER, engine TEXT, templates TEXT, updated_at TEXT, delete_digest TEXT, PRIMARY KEY(profile,modality))")
            c.execute("CREATE TABLE IF NOT EXISTS identity_sessions (id TEXT PRIMARY KEY, client TEXT, request_key TEXT, profile TEXT, modality TEXT, engine TEXT, created_at TEXT, expires_at TEXT, status TEXT, samples TEXT, revision INTEGER, UNIQUE(client,request_key))")
            c.execute("PRAGMA secure_delete=ON")
            c.execute("UPDATE identity_sessions SET status='EXPIRED',samples='[]' WHERE status='COLLECTING'")

    def _cfg(self, modality):
        _require(type(modality) is str and modality in self.config["modalities"], "IDENTITY_MODALITY_UNAVAILABLE")
        return self.config["modalities"][modality]

    def _expire(self, db):
        now = self.clock().isoformat()
        db.execute("PRAGMA secure_delete=ON")
        db.execute("UPDATE identity_sessions SET status='EXPIRED',samples='[]' WHERE status='COLLECTING' AND (expires_at<? OR created_at>?)", (now, now))

    def _session(self, db, client, identity):
        self._expire(db)
        row = db.execute("SELECT * FROM identity_sessions WHERE id=? AND client=?", (identity, client)).fetchone()
        _require(row is not None, "IDENTITY_SESSION_UNKNOWN")
        return row

    def _view(self, row):
        count = len(json.loads(row["samples"]))
        required = self.config["modalities"].get(row["modality"], {}).get("samples", 0)
        value = {"session_id":row["id"], "modality":row["modality"], "state":row["status"],
                 "samples":count, "required":required, "expires_at":row["expires_at"], "revision":row["revision"],
                 "grants":[], "authorizes_execution":False}
        value["approval_sha256"] = digest(dict(row)) if count == required and row["status"] == "COLLECTING" else None
        return value

    def status(self, client):
        profile, _ = self.profile(client)
        with self.db() as db:
            self._expire(db)
            values = []
            for modality, cfg in self.config["modalities"].items():
                row = db.execute("SELECT * FROM identity_templates WHERE profile=? AND modality=?", (profile, modality)).fetchone()
                enrolled = row is not None and bool(json.loads(row["templates"]))
                values.append({"modality":modality, "samples_required":cfg["samples"], "enrolled":enrolled,
                    "engine_matches":not enrolled or row["engine"] == digest(cfg), "calibrated":cfg["calibration"] is not None,
                    "max_duration_s":cfg.get("max_duration_s"), "min_speech_s":cfg.get("min_speech_s"),
                    "delete_sha256":digest(dict(row)) if enrolled else None})
            sessions = db.execute("SELECT * FROM identity_sessions WHERE client=? ORDER BY rowid DESC LIMIT 4", (client,)).fetchall()
        return {"profile_id":profile, "modalities":values, "sessions":[self._view(r) for r in sessions],
                "scope":"connected_profile_only", "grants":[], "authorizes_execution":False}

    def begin(self, client, modality, request_key, present, consent):
        profile, _ = self.profile(client); cfg = self._cfg(modality)
        _require(present is True and consent is True, "IDENTITY_CONSENT_REQUIRED")
        _require(type(request_key) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", request_key), "IDENTITY_KEY_INVALID")
        with self.db() as db:
            self._expire(db)
            old = db.execute("SELECT * FROM identity_sessions WHERE client=? AND request_key=?", (client,request_key)).fetchone()
            if old is not None:
                _require(old["modality"] == modality, "IDENTITY_KEY_REUSED")
                return self._view(old)
            existing = db.execute("SELECT templates FROM identity_templates WHERE profile=? AND modality=?", (profile,modality)).fetchone()
            _require(existing is None or not json.loads(existing[0]), "IDENTITY_DELETE_FIRST")
            active = db.execute("SELECT 1 FROM identity_sessions WHERE profile=? AND modality=? AND status='COLLECTING'", (profile,modality)).fetchone()
            _require(active is None, "IDENTITY_SESSION_BUSY")
            now = self.clock(); identity = uuid.uuid4().hex
            db.execute("INSERT INTO identity_sessions VALUES (?,?,?,?,?,?,?,?,?,'[]',NULL)",
                (identity,client,request_key,profile,modality,digest(cfg),now.isoformat(),(now+timedelta(minutes=10)).isoformat(),"COLLECTING"))
            return self._view(self._session(db,client,identity))

    @staticmethod
    def _capture(encoded):
        _require(type(encoded) is str and len(encoded) <= 4*((MAX_CAPTURE+2)//3), "IDENTITY_CAPTURE_INVALID")
        try: raw = bytearray(base64.b64decode(encoded, validate=True))
        except ValueError: raise IdentityError("IDENTITY_CAPTURE_INVALID") from None
        _require(0 < len(raw) <= MAX_CAPTURE, "IDENTITY_CAPTURE_INVALID")
        return raw

    def _observe(self, cfg, modality, raw):
        _require(self.inference.acquire(blocking=False), "IDENTITY_ENGINE_BUSY")
        try:
            result = self.observer(cfg, modality, raw)
            _require(isinstance(result, Observation) and result.modality == modality and result.engine == engine(cfg,modality)
                     and result.error is None, "IDENTITY_ENGINE_UNAVAILABLE")
            return result
        finally:
            raw[:] = bytes(len(raw))
            self.inference.release()

    def sample(self, client, identity, sample_key, encoded):
        self.profile(client)
        _require(type(sample_key) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", sample_key), "IDENTITY_KEY_INVALID")
        with self.db() as db:
            row = self._session(db,client,identity)
            _require(row["status"] == "COLLECTING", "IDENTITY_SESSION_CLOSED")
            cfg = self._cfg(row["modality"])
            _require(row["engine"] == digest(cfg), "IDENTITY_ENGINE_CHANGED")
        raw = self._capture(encoded); fingerprint = hashlib.sha256(raw).hexdigest()
        try:
            previous = next((s for s in json.loads(row["samples"]) if s["key"] == sample_key), None)
            if previous is not None:
                _require(previous["sha"] == fingerprint, "IDENTITY_KEY_REUSED")
                return self._view(row)
            _require(len(json.loads(row["samples"])) < cfg["samples"], "IDENTITY_SAMPLES_COMPLETE")
            observed = self._observe(cfg,row["modality"],raw)
            if row["modality"] == "face":
                _require(observed.faces == 1, "IDENTITY_ONE_FACE_REQUIRED")
            else:
                _require(not observed.silence and observed.overlap is not True
                         and observed.speech_s is not None and cfg["min_speech_s"] <= observed.speech_s
                         and observed.duration_s <= cfg["max_duration_s"], "IDENTITY_VOICE_QUALITY_REFUSED")
            vector = list(_unit(observed.embedding))
            with self.db() as db:
                row = self._session(db,client,identity)
                _require(row["status"] == "COLLECTING", "IDENTITY_SESSION_CLOSED")
                samples = json.loads(row["samples"])
                previous = next((s for s in samples if s["key"] == sample_key), None)
                if previous is not None:
                    _require(previous["sha"] == fingerprint, "IDENTITY_KEY_REUSED")
                    return self._view(row)
                _require(len(samples) < cfg["samples"] and all(s["sha"] != fingerprint for s in samples), "IDENTITY_SAMPLE_DUPLICATE_OR_FULL")
                samples.append({"key":sample_key,"sha":fingerprint,"vector":vector})
                db.execute("UPDATE identity_sessions SET samples=? WHERE id=?", (encode(samples),identity))
                return self._view(self._session(db,client,identity))
        finally:
            raw[:] = bytes(len(raw))

    def confirm(self, client, identity, approved):
        self.profile(client)
        with self.db() as db:
            row = self._session(db,client,identity)
            if row["status"] == "ENROLLED":
                _require(approved == row["engine"], "IDENTITY_APPROVAL_MISMATCH")
                return self._view(row)
            view = self._view(row)
            _require(row["status"] == "COLLECTING" and view["approval_sha256"] is not None
                     and approved == view["approval_sha256"], "IDENTITY_APPROVAL_MISMATCH")
            cfg = self._cfg(row["modality"])
            _require(row["engine"] == digest(cfg), "IDENTITY_ENGINE_CHANGED")
            old = db.execute("SELECT * FROM identity_templates WHERE profile=? AND modality=?", (row["profile"],row["modality"])).fetchone()
            _require(old is None or not json.loads(old["templates"]), "IDENTITY_DELETE_FIRST")
            revision = 1 if old is None else old["revision"]+1
            templates = [s["vector"] for s in json.loads(row["samples"])]
            Registry(row["modality"],{row["profile"]:templates},engine=engine(cfg,row["modality"]))
            db.execute("INSERT OR REPLACE INTO identity_templates VALUES (?,?,?,?,?,?,NULL)",
                       (row["profile"],row["modality"],revision,digest(cfg),encode(templates),self.clock().isoformat()))
            # Retain only the approval digest for idempotent confirmation, no duplicate templates.
            db.execute("UPDATE identity_sessions SET status='ENROLLED',samples='[]',revision=?,engine=? WHERE id=?",(revision,approved,identity))
            return self._view(self._session(db,client,identity))

    def cancel(self, client, identity):
        self.profile(client)
        with self.db() as db:
            row = self._session(db,client,identity)
            _require(row["status"] != "ENROLLED", "IDENTITY_USE_DELETE")
            db.execute("UPDATE identity_sessions SET status='CANCELLED',samples='[]' WHERE id=?",(identity,))
            return self._view(self._session(db,client,identity))

    def delete(self, client, modality, approved):
        profile, _ = self.profile(client); self._cfg(modality)
        with self.db() as db:
            self._expire(db)
            row = db.execute("SELECT * FROM identity_templates WHERE profile=? AND modality=?",(profile,modality)).fetchone()
            _require(row is not None, "IDENTITY_NOT_ENROLLED")
            if not json.loads(row["templates"]):
                _require(approved == row["delete_digest"], "IDENTITY_APPROVAL_MISMATCH")
            else:
                _require(approved == digest(dict(row)), "IDENTITY_APPROVAL_MISMATCH")
                db.execute("UPDATE identity_templates SET templates='[]',revision=revision+1,updated_at=?,delete_digest=? WHERE profile=? AND modality=?",(self.clock().isoformat(),approved,profile,modality))
                db.execute("UPDATE identity_sessions SET samples='[]',status='DELETED' WHERE profile=? AND modality=?",(profile,modality))
        return {"state":"REMOVED_FROM_ACTIVE_REGISTRY", "modality":modality, "backups_erased":False, "authorizes_execution":False}

    def probe(self, client, modality, encoded):
        profile, _ = self.profile(client); cfg = self._cfg(modality)
        with self.db() as db:
            row = db.execute("SELECT * FROM identity_templates WHERE profile=? AND modality=?",(profile,modality)).fetchone()
        _require(row is not None and json.loads(row["templates"]), "IDENTITY_NOT_ENROLLED")
        _require(row["engine"] == digest(cfg), "IDENTITY_ENGINE_CHANGED")
        raw = self._capture(encoded)
        try: observed = self._observe(cfg,modality,raw)
        finally: raw[:] = bytes(len(raw))
        with self.db() as db:
            current = db.execute("SELECT revision,templates FROM identity_templates WHERE profile=? AND modality=?",(profile,modality)).fetchone()
            _require(current is not None and current["revision"] == row["revision"] and current["templates"] == row["templates"], "IDENTITY_REGISTRY_CHANGED")
        calibration = None if cfg["calibration"] is None else Calibration(**dict(cfg["calibration"],score_bounds=tuple(cfg["calibration"]["score_bounds"])))
        value = propose(observed,Registry(modality,{profile:json.loads(row["templates"])},engine=engine(cfg,modality)),calibration,now=self.clock())
        value["candidates"] = []
        value["scope"] = "connected_profile_only"
        return value
