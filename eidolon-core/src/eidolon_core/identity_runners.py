# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : identity_runners.py
# Description : Exécuteurs réels facultatifs (G170-C/D, C156-Q1) : WeSpeaker ONNX, YuNet + SFace OpenCV, sur octets vérifiés
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Real engine runners for identity_engines, behind OPTIONAL dependencies (numpy, onnxruntime, OpenCV).

Nothing is imported at module load and nothing is downloaded: each runner is built from an
``identity_engines.VerifiedModel`` (the hashed bytes) and loads THOSE bytes, never a path. Nothing here opens
a sensor, a route or a log, and a runner grants nothing. Decision parameters (thresholds) do not live here.

Preprocessing identifiers name exactly what the code does; parity with the reference implementations
(torchaudio Kaldi fbank for WeSpeaker, OpenCV's own alignment for SFace) is a measured claim, see
docs/G170-CD-RUNNERS.md, not an assumption.
"""
import math

VOICE_PREPROCESSING = "kaldi-fbank80-hamming-25ms-10ms-cmn/1"
FACE_PREPROCESSING = "yunet-2023mar+sface-align5/1"
MAX_PIXELS = 4096 * 4096
MAX_FRAMES = 3000                                    # 30 s at 10 ms


def _numpy():
    import numpy                                     # optional dependency, imported on use only
    return numpy


def _mel(freq):
    return 1127.0 * math.log(1.0 + freq / 700.0)


def mel_banks(num_bins=80, sample_rate=16000, n_fft=512, low_freq=20.0, high_freq=0.0):
    """Kaldi triangular mel filters on the FFT bins 0..n_fft/2 (the Nyquist column stays zero, as in Kaldi)."""
    np = _numpy()
    nyquist = sample_rate / 2.0
    high = high_freq if high_freq > 0 else nyquist + high_freq
    mel_low, mel_high = _mel(low_freq), _mel(high)
    delta = (mel_high - mel_low) / (num_bins + 1)
    half = n_fft // 2
    fft_mel = 1127.0 * np.log1p(np.arange(half) * (sample_rate / n_fft) / 700.0)
    banks = np.zeros((num_bins, half + 1), dtype=np.float64)
    for b in range(num_bins):
        left, center, right = mel_low + b * delta, mel_low + (b + 1) * delta, mel_low + (b + 2) * delta
        up = (fft_mel - left) / (center - left)
        down = (right - fft_mel) / (right - center)
        banks[b, :half] = np.maximum(0.0, np.minimum(up, down))
    return banks


def fbank(samples, sample_rate=16000, *, num_mel_bins=80, frame_length_ms=25, frame_shift_ms=10,
          preemphasis=0.97):
    """Kaldi-style log mel filterbank (dither 0, DC removal, pre-emphasis, Hamming, snip_edges, power, no
    energy) followed by CMN, as WeSpeaker's runtime does. ``samples`` are PCM16 values, not normalised."""
    np = _numpy()
    wave = np.asarray(samples, dtype=np.float64)
    frame, shift = sample_rate * frame_length_ms // 1000, sample_rate * frame_shift_ms // 1000
    if wave.ndim != 1 or len(wave) < frame:
        raise ValueError("audio shorter than one frame")
    count = min(1 + (len(wave) - frame) // shift, MAX_FRAMES)
    index = np.arange(frame)[None, :] + shift * np.arange(count)[:, None]
    frames = wave[index]
    frames = frames - frames.mean(axis=1, keepdims=True)
    previous = np.concatenate([frames[:, :1], frames[:, :-1]], axis=1)
    frames = frames - preemphasis * previous
    n = np.arange(frame)
    frames = frames * (0.54 - 0.46 * np.cos(2 * math.pi * n / (frame - 1)))
    n_fft = 1 << (frame - 1).bit_length()
    power = np.abs(np.fft.rfft(frames, n=n_fft, axis=1)) ** 2
    energies = power @ mel_banks(num_mel_bins, sample_rate, n_fft).T
    feats = np.log(np.maximum(energies, np.finfo(np.float32).eps))
    feats = feats - feats.mean(axis=0, keepdims=True)
    return feats.astype(np.float32)


def _cpu_session(verified):
    import onnxruntime                               # optional dependency
    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    options.log_severity_level = 3
    return onnxruntime.InferenceSession(verified.data, sess_options=options, providers=["CPUExecutionProvider"])


class WeSpeakerRunner:
    """``runner(samples, rate) -> vector`` for identity_engines.VoiceAdapter (input ``feats`` [1, T, 80])."""

    def __init__(self, verified):
        if verified.engine.preprocessing != VOICE_PREPROCESSING:
            raise ValueError("verified model was declared for another preprocessing")
        self._session = _cpu_session(verified)
        inputs, outputs = self._session.get_inputs(), self._session.get_outputs()
        if len(inputs) != 1 or inputs[0].shape[-1] != 80 or not outputs:
            raise ValueError("unexpected speaker model signature")
        self._input, self._output = inputs[0].name, outputs[0].name

    def __call__(self, samples, rate):
        if rate != 16000:
            raise ValueError("16 kHz audio expected")
        feats = fbank(samples, rate)[None, :, :]
        try:
            vector = self._session.run([self._output], {self._input: feats})[0].reshape(-1)
        finally:
            feats.fill(0)                            # our copy of the features; ONNX internals are not covered
        return tuple(float(v) for v in vector)


class Face:
    """One detection: opaque to identity_engines. Holds the decoded image until wiped."""

    def __init__(self, row, image):
        self.row, self._image = row, image

    def wipe(self):
        if self._image is not None:
            self._image.fill(0)
            self._image = None


class YuNetSFace:
    """YuNet detector + SFace encoder from verified bytes: ``detector(view) -> [Face]``, ``embedder(view, face)``."""

    def __init__(self, detector_model, encoder_model, *, score_threshold=0.9, nms_threshold=0.3, top_k=50):
        import cv2                                   # optional dependency
        np = _numpy()
        for verified in (detector_model, encoder_model):
            if verified.engine.preprocessing != FACE_PREPROCESSING:
                raise ValueError("verified model was declared for another preprocessing")
        self._cv2, self._np = cv2, np
        self._detector = cv2.FaceDetectorYN.create("onnx", np.frombuffer(detector_model.data, np.uint8),
                                                   np.zeros(0, np.uint8), (320, 320), score_threshold,
                                                   nms_threshold, top_k)
        self._encoder = cv2.FaceRecognizerSF.create("onnx", np.frombuffer(encoder_model.data, np.uint8),
                                                    np.zeros(0, np.uint8))

    def decode(self, view):
        image = self._cv2.imdecode(self._np.frombuffer(view, self._np.uint8), self._cv2.IMREAD_COLOR)
        if image is None or image.ndim != 3 or image.shape[0] * image.shape[1] > MAX_PIXELS:
            raise ValueError("unreadable or oversized image")
        return image

    def detector(self, view):
        image = self.decode(view)
        self._detector.setInputSize((image.shape[1], image.shape[0]))
        _, rows = self._detector.detect(image)
        faces = [] if rows is None else [Face(row.copy(), image) for row in rows]
        if not faces:
            image.fill(0)
        return faces

    def embedder(self, view, face):
        aligned = self._encoder.alignCrop(face._image, face.row)
        try:
            vector = self._encoder.feature(aligned).reshape(-1)
        finally:
            aligned.fill(0)
        return tuple(float(v) for v in vector)
