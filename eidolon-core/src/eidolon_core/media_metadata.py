# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_metadata.py
# Description : Métadonnées techniques d'un artefact, sondage local borné avec FFprobe
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Inspect container/first visual stream metadata, never semantic content or all frames.

Only an explicit private artifact reference and operator-chosen FFprobe are used.
The bytes are rehashed by ArtifactStore and copied into a private temporary input.
Fixed demuxers and file/pipe protocols exclude playlists and remote inputs. FFprobe
has a wall deadline, CPU/address-space limits, bounded probing and bounded stdout.
The chosen executable is trusted operator configuration, not a sandboxed plugin.
"""
import math
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time

from .media_agents import MediaError, parse_json
from .media_artifacts import ArtifactStore
from .presentation import header, message, section

MAX_OUTPUT = 16_384
WALL_SECONDS = 10
CPU_SECONDS = 5
ADDRESS_SPACE = 512 * 1024 * 1024
MAX_ALLOCATION = 64 * 1024 * 1024
DEMUXERS = {"image/png": "png_pipe", "image/jpeg": "mjpeg", "image/webp": "webp_pipe",
            "video/mp4": "mov", "video/webm": "matroska"}
# A separate interpreter applies limits before exec; no preexec_fn in a threaded caller.
LIMITED_EXEC = f"""import os,resource,sys
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
resource.setrlimit(resource.RLIMIT_CPU,({CPU_SECONDS},{CPU_SECONDS}))
resource.setrlimit(resource.RLIMIT_AS,({ADDRESS_SPACE},{ADDRESS_SPACE}))
os.execv(sys.argv[1],sys.argv[1:])
"""


def _executable(path):
    if type(path) is not str or not Path(path).is_absolute():
        raise MediaError("FFPROBE_NOT_CONFIGURED")
    try:
        info = os.stat(path)
    except OSError:
        raise MediaError("FFPROBE_NOT_CONFIGURED") from None
    if not stat.S_ISREG(info.st_mode) or not os.access(path, os.X_OK):
        raise MediaError("FFPROBE_NOT_EXECUTABLE")
    return path


def _output(command, *, timeout=WALL_SECONDS):
    """Bound bytes while reading, not after communicate has allocated the response."""
    child = subprocess.Popen([sys.executable, "-I", "-c", LIMITED_EXEC, *command],
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, start_new_session=True)
    complete = False
    try:
        deadline = time.monotonic() + timeout
        body = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise MediaError("MEDIA_PROBE_TIMEOUT")
                if not selector.select(remaining):
                    raise MediaError("MEDIA_PROBE_TIMEOUT")
                block = os.read(child.stdout.fileno(), min(4096, MAX_OUTPUT + 1 - len(body)))
                if not block:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise MediaError("MEDIA_PROBE_TIMEOUT")
                    try:
                        status = child.wait(timeout=remaining)
                    except subprocess.TimeoutExpired:
                        raise MediaError("MEDIA_PROBE_TIMEOUT") from None
                    complete = True
                    if status:
                        raise MediaError("MEDIA_PROBE_FAILED")
                    return bytes(body)
                body.extend(block)
                if len(body) > MAX_OUTPUT:
                    raise MediaError("MEDIA_PROBE_OUTPUT_TOO_LARGE")
    finally:
        if not complete:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
        child.stdout.close()


def _label(value):
    if type(value) is not str or re.fullmatch(r"[A-Za-z0-9_,.-]{1,80}", value) is None:
        raise MediaError("INVALID_MEDIA_METADATA")
    return value


def _duration(value):
    if value is None or value == "N/A":
        return None
    if type(value) not in (str, int, float):
        raise MediaError("INVALID_MEDIA_METADATA")
    try:
        number = float(value)
    except (ValueError, OverflowError):
        raise MediaError("INVALID_MEDIA_METADATA") from None
    if not math.isfinite(number) or not 0 <= number <= 1_000_000_000:
        raise MediaError("INVALID_MEDIA_METADATA")
    return number


def _rate(value):
    if value in (None, "0/0", "N/A"):
        return None
    if type(value) is not str or re.fullmatch(r"[0-9]{1,9}/[0-9]{1,9}", value) is None:
        raise MediaError("INVALID_MEDIA_METADATA")
    numerator, denominator = map(int, value.split("/"))
    if not denominator or numerator / denominator > 100_000:
        raise MediaError("INVALID_MEDIA_METADATA")
    return {"numerator": numerator, "denominator": denominator}


def _metadata(raw, media_type):
    try:
        value = parse_json(raw)
        streams = value.get("streams") if type(value) is dict else None
        container = value.get("format") if type(value) is dict else None
        if type(streams) is not list or len(streams) != 1 or type(container) is not dict:
            raise MediaError("INVALID_MEDIA_METADATA")
        stream = streams[0]
        if (type(stream) is not dict or stream.get("codec_type") != "video"
                or any(type(stream.get(k)) is not int or not 1 <= stream[k] <= 65_536 for k in ("width", "height"))):
            raise MediaError("INVALID_MEDIA_METADATA")
        codec = _label(stream.get("codec_name"))
        expected = {"image/png": "png", "image/jpeg": "mjpeg", "image/webp": "webp"}.get(media_type)
        if expected is not None and codec != expected:
            raise MediaError("MEDIA_METADATA_TYPE_MISMATCH")
        duration = _duration(container.get("duration"))
        if duration is None:
            duration = _duration(stream.get("duration"))
        return {"codec": codec, "container": _label(container.get("format_name")),
                "width": stream["width"], "height": stream["height"],
                "duration_seconds": duration if expected is None else None,
                "frame_rate": _rate(stream.get("avg_frame_rate")) if expected is None else None}
    except MediaError:
        raise
    except (ValueError, TypeError, KeyError, RecursionError):
        raise MediaError("INVALID_MEDIA_METADATA") from None


def probe(root, store_id, reference, *, ffprobe):
    executable = _executable(ffprobe)
    body, manifest = ArtifactStore(root, expected_store_id=store_id).read(reference)
    media_type = manifest["media_type"]
    with tempfile.TemporaryDirectory(prefix="eidolon-media-probe-") as folder:
        source = Path(folder) / "source.bin"
        fd = os.open(source, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(body)
        command = [executable, "-v", "error", "-max_alloc", str(MAX_ALLOCATION),
                   "-protocol_whitelist", "file,pipe", "-probesize", "1000000",
                   "-analyzeduration", "3000000", "-threads", "1", "-f", DEMUXERS[media_type],
                   *(["-enable_drefs", "0", "-use_absolute_path", "0"] if media_type == "video/mp4" else []),
                   "-i", str(source), "-select_streams", "v:0", "-show_entries",
                   "stream=codec_name,codec_type,width,height,duration,avg_frame_rate:format=format_name,duration",
                   "-of", "json"]
        observed = _metadata(_output(command), media_type)
    return {"schema": "media-artifact-metadata/1", "state": "METADATA_OBSERVED",
            "reference": manifest["reference"], "media_type": media_type, "size_bytes": len(body),
            "observed": observed, "content_hash_checked": True, "first_visual_stream_only": True,
            "audio_inspected": False, "full_file_decoded": False, "semantic_content_verified": False,
            "engine_contacted": False, "artifact_modified": False, "execution_authorized": False,
            "limits": {"wall_seconds": WALL_SECONDS, "cpu_seconds": CPU_SECONDS,
                       "address_space_bytes": ADDRESS_SPACE, "max_stdout_bytes": MAX_OUTPUT,
                       "max_single_allocation_bytes": MAX_ALLOCATION}}


def render_metadata(report):
    data = report["observed"]
    lines = [header(title="Métadonnées d'un artefact média"),
             message("INFO", "FFprobe local sur une copie temporaire ; aucun moteur contacté."),
             section("Observation technique"), message("OK", "Empreinte de l'artefact comparée à sa référence."),
             message("INFO", "Dimensions rapportées : " + str(data["width"]) + " × " + str(data["height"]) + " pixels."),
             message("INFO", "Codec : " + data["codec"] + " ; conteneur : " + data["container"] + ".")]
    if report["media_type"].startswith("video/"):
        lines.append(message("INFO", "Durée rapportée : " + ("indisponible" if data["duration_seconds"] is None
                              else format(data["duration_seconds"], ".3f") + " secondes") + "."))
    lines.extend([section("Limites"),
                  message("ATTENTION", "Métadonnées du premier flux visuel uniquement ; le fichier n'a pas été décodé intégralement."),
                  message("INFO", "Audio et contenu sémantique non vérifiés. Aucune réussite de mission déduite."),
                  message("INFO", "Artefact inchangé ; ce rapport n'en modifie pas le statut.")])
    return "\n".join(lines)
