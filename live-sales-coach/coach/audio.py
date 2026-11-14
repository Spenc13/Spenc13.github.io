"""Audio capture: microphone (Rep) and system-audio loopback (Prospect).

Windows: PyAudioWPatch gives WASAPI loopback of any output device, so the
         prospect's voice from Google Meet or a softphone is captured directly.
macOS:   install BlackHole and route call audio through a Multi-Output Device,
         then capture "BlackHole 2ch" with sounddevice (see README).

Both sources are delivered as 16-bit mono PCM at the device's native rate;
Deepgram is told the rate, so there's no resampling.
"""
from __future__ import annotations

import logging
import sys
import threading
from dataclasses import dataclass
from typing import Callable

import numpy as np

log = logging.getLogger(__name__)

ChunkCallback = Callable[[bytes], None]

# One PortAudio instance for the whole app. Starting PortAudio scans every audio
# device, which can take seconds (Bluetooth headsets especially) and blocks the
# window, so it's done once in the background (warm_up) instead of on every Start.
_PA = None
_PA_LOCK = threading.RLock()
_WASAPI_DEVICES: list | None = None


def _shared_pa(refresh: bool = False):
    global _PA, _WASAPI_DEVICES
    with _PA_LOCK:
        if refresh and _PA is not None:
            try:
                _PA.terminate()
            except Exception:
                pass
            _PA, _WASAPI_DEVICES = None, None
        if _PA is None:
            import pyaudiowpatch as pyaudio

            _PA = pyaudio.PyAudio()
        return _PA


def warm_up(cfg_backend: str = "auto", refresh: bool = False) -> None:
    """Start the audio system and read the device list ahead of time.
    refresh=True rescans (new headset plugged in, default device changed)."""
    if _backend(cfg_backend) == "wasapi":
        with _PA_LOCK:
            _shared_pa(refresh)
            list_devices("wasapi")
    else:
        import sounddevice  # noqa: F401  (loads PortAudio)


def shutdown() -> None:
    global _PA, _WASAPI_DEVICES
    with _PA_LOCK:
        if _PA is not None:
            try:
                _PA.terminate()
            except Exception:
                pass
        _PA, _WASAPI_DEVICES = None, None


@dataclass
class DeviceInfo:
    index: int
    name: str
    in_channels: int
    out_channels: int
    rate: int
    host_api: str
    is_loopback: bool = False


def _match(devices: list[DeviceInfo], want, pred) -> DeviceInfo | None:
    cands = [d for d in devices if pred(d)]
    if want in (None, ""):
        return None
    if isinstance(want, int) or (isinstance(want, str) and want.isdigit()):
        idx = int(want)
        return next((d for d in cands if d.index == idx), None)
    w = str(want).lower()
    return next((d for d in cands if w in d.name.lower()), None)


def to_mono_int16(data: bytes, channels: int, dtype=np.int16) -> bytes:
    arr = np.frombuffer(data, dtype=dtype)
    if dtype != np.int16:
        arr = np.clip(arr, -1.0, 1.0)
        arr = (arr * 32767).astype(np.int16)
    if channels > 1:
        arr = arr.reshape(-1, channels).mean(axis=1).astype(np.int16)
    return arr.tobytes()


class Capture:
    """A running capture for one source. Call start(), then stop()."""

    def __init__(self, label: str, on_chunk: ChunkCallback) -> None:
        self.label = label
        self.on_chunk = on_chunk
        self.rate = 16000
        self.device_name = ""

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------- sounddevice
class SoundDeviceCapture(Capture):
    def __init__(self, label: str, on_chunk: ChunkCallback, device, chunk_ms: int) -> None:
        super().__init__(label, on_chunk)
        import sounddevice as sd

        self.sd = sd
        info = sd.query_devices(device, "input") if device is not None else sd.query_devices(kind="input")
        self.device = device
        self.device_name = info["name"]
        self.rate = int(info["default_samplerate"])
        self.channels = 1 if info["max_input_channels"] >= 1 else 0
        if self.channels == 0:
            raise RuntimeError(f"{self.device_name} has no input channels")
        self.blocksize = int(self.rate * chunk_ms / 1000)
        self.stream = None

    def start(self) -> None:
        def cb(indata, frames, time_info, status):  # audio thread
            self.on_chunk(bytes(indata))

        self.stream = self.sd.RawInputStream(
            device=self.device, samplerate=self.rate, channels=1, dtype="int16",
            blocksize=self.blocksize, callback=cb,
        )
        self.stream.start()

    def stop(self) -> None:
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None


# ------------------------------------------------------------ WASAPI (Windows)
class WasapiCapture(Capture):
    """Mic or loopback via PyAudioWPatch."""

    def __init__(self, label: str, on_chunk: ChunkCallback, device_index: int,
                 channels: int, rate: int, name: str, chunk_ms: int) -> None:
        super().__init__(label, on_chunk)
        import pyaudiowpatch as pyaudio

        self.pa_mod = pyaudio
        self.pa = _shared_pa()
        self.index = device_index
        self.channels = max(1, channels)
        self.rate = rate
        self.device_name = name
        self.frames = int(rate * chunk_ms / 1000)
        self.stream = None

    def start(self) -> None:
        def cb(in_data, frame_count, time_info, status):  # audio thread
            self.on_chunk(to_mono_int16(in_data, self.channels))
            return (None, self.pa_mod.paContinue)

        self.stream = self.pa.open(
            format=self.pa_mod.paInt16, channels=self.channels, rate=self.rate,
            input=True, input_device_index=self.index,
            frames_per_buffer=self.frames, stream_callback=cb,
        )
        self.stream.start_stream()

    def stop(self) -> None:
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        # The shared PortAudio instance stays up for the next call.


# ------------------------------------------------------------------- helpers
def _backend(cfg_backend: str) -> str:
    if cfg_backend and cfg_backend != "auto":
        return cfg_backend
    if sys.platform == "win32":
        try:
            import pyaudiowpatch  # noqa: F401
            return "wasapi"
        except ImportError:
            return "sounddevice"
    return "sounddevice"


def list_devices(cfg_backend: str = "auto") -> list[DeviceInfo]:
    global _WASAPI_DEVICES
    backend = _backend(cfg_backend)
    out: list[DeviceInfo] = []
    if backend == "wasapi":
        with _PA_LOCK:
            if _WASAPI_DEVICES is not None:
                return list(_WASAPI_DEVICES)
            pa = _shared_pa()
            for i in range(pa.get_device_count()):
                d = pa.get_device_info_by_index(i)
                host = pa.get_host_api_info_by_index(d["hostApi"])["name"]
                out.append(DeviceInfo(
                    index=i, name=d["name"], in_channels=int(d["maxInputChannels"]),
                    out_channels=int(d["maxOutputChannels"]), rate=int(d["defaultSampleRate"]),
                    host_api=host, is_loopback=bool(d.get("isLoopbackDevice", False)),
                ))
            _WASAPI_DEVICES = out
            return list(out)
    else:
        import sounddevice as sd

        apis = sd.query_hostapis()
        for i, d in enumerate(sd.query_devices()):
            out.append(DeviceInfo(
                index=i, name=d["name"], in_channels=int(d["max_input_channels"]),
                out_channels=int(d["max_output_channels"]), rate=int(d["default_samplerate"]),
                host_api=apis[d["hostapi"]]["name"],
            ))
    return out


def print_devices(cfg_backend: str = "auto") -> None:
    backend = _backend(cfg_backend)
    print(f"Audio backend: {backend}\n")
    for d in list_devices(cfg_backend):
        kind = "LOOPBACK" if d.is_loopback else ("in " if d.in_channels else "") + ("out" if d.out_channels else "")
        print(f"[{d.index:>3}] {d.name}  ({d.host_api}, {kind.strip()}, {d.rate} Hz)")
    if backend == "wasapi":
        print("\nSet audio.loopback_device to a LOOPBACK device name (or leave blank for your default output).")
    elif sys.platform == "darwin":
        print("\nSet audio.loopback_device to \"BlackHole 2ch\" after the BlackHole setup in README.")


def open_mic(cfg_audio: dict, on_chunk: ChunkCallback) -> Capture:
    backend = _backend(cfg_audio.get("backend", "auto"))
    chunk_ms = int(cfg_audio.get("chunk_ms", 100))
    want = cfg_audio.get("mic_device") or None
    if backend == "wasapi":
        import pyaudiowpatch as pyaudio

        def find():
            devices = list_devices("wasapi")
            dev = _match(devices, want, lambda d: d.in_channels > 0 and not d.is_loopback)
            if dev is None and not want:
                wasapi = _shared_pa().get_host_api_info_by_type(pyaudio.paWASAPI)
                idx = wasapi["defaultInputDevice"]
                dev = next((x for x in devices if x.index == idx), None)
            return dev

        dev = find()
        if dev is None:                      # newly plugged in? rescan once
            warm_up("wasapi", refresh=True)
            dev = find()
        if dev is None:
            raise RuntimeError(f"Microphone '{want}' not found. Run: python main.py --list-devices")
        return WasapiCapture("rep", on_chunk, dev.index, min(dev.in_channels, 2), dev.rate, dev.name, chunk_ms)
    device = None
    if want not in (None, ""):
        dev = _match(list_devices("sounddevice"), want, lambda d: d.in_channels > 0)
        if dev is None:
            raise RuntimeError(f"Microphone '{want}' not found. Run: python main.py --list-devices")
        device = dev.index
    return SoundDeviceCapture("rep", on_chunk, device, chunk_ms)


def open_loopback(cfg_audio: dict, on_chunk: ChunkCallback) -> Capture:
    backend = _backend(cfg_audio.get("backend", "auto"))
    chunk_ms = int(cfg_audio.get("chunk_ms", 100))
    want = cfg_audio.get("loopback_device") or None
    if backend == "wasapi":
        def find():
            devices = list_devices("wasapi")
            dev = _match(devices, want, lambda d: d.is_loopback)
            if dev is None and want:
                # User named the speakers/headset; find its loopback twin.
                out = _match(devices, want, lambda d: d.out_channels > 0 and not d.is_loopback)
                if out:
                    dev = next((d for d in devices if d.is_loopback and out.name in d.name), None)
            if dev is None and not want:
                lb = _shared_pa().get_default_wasapi_loopback()
                dev = next((x for x in devices if x.index == lb["index"]), None)
            return dev

        dev = find()
        if dev is None:                      # newly plugged in? rescan once
            warm_up("wasapi", refresh=True)
            dev = find()
        if dev is None:
            raise RuntimeError(f"Speaker '{want}' not found for call audio. Run: python main.py --list-devices")
        return WasapiCapture("prospect", on_chunk, dev.index, max(1, dev.in_channels), dev.rate, dev.name, chunk_ms)
    if want in (None, ""):
        raise RuntimeError(
            "No loopback device set. On macOS install BlackHole and set audio.loopback_device "
            "to \"BlackHole 2ch\" in config.yaml (see README)."
        )
    dev = _match(list_devices("sounddevice"), want, lambda d: d.in_channels > 0)
    if dev is None:
        raise RuntimeError(f"Loopback device '{want}' not found. Run: python main.py --list-devices")
    return SoundDeviceCapture("prospect", on_chunk, dev.index, chunk_ms)



# ------------------------------------------------------- follow the call audio
def resample_int16(pcm: bytes, src_rate: int, dst_rate: int = 16000) -> bytes:
    """Linear resample of 16-bit mono PCM (plenty for speech-to-text)."""
    if src_rate == dst_rate or not pcm:
        return pcm
    a = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    n = max(1, int(round(a.size * dst_rate / src_rate)))
    x = np.linspace(0, a.size - 1, n)
    return np.interp(x, np.arange(a.size), a).astype(np.int16).tobytes()


def _rms(pcm: bytes) -> float:
    a = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(a * a))) / 32768.0 if a.size else 0.0


class CallAudioFollower(Capture):
    """Listens to every speaker on the PC (WASAPI loopback) and feeds speech-to-text
    from the one actually carrying the other person's voice.

    Why: the call can play through a different speaker than the Windows default.
    Bluetooth headsets switch to a "Hands-Free" speaker during calls; Meet and the
    dialer each have their own speaker setting. A speaker that only carries the
    rep's own voice (sidetone, "Listen to this device") is ignored, because audio
    is only scored while the rep's mic is quiet.
    """

    MIC_QUIET = 0.012          # mic RMS below this = the rep isn't talking
    MIN_SCORE = 0.002          # a speaker needs at least this much "other side" audio
    SWITCH_RATIO = 2.0         # and must beat the current one by this much
    HOLD_S = 3.0               # don't flip-flop

    def __init__(self, on_chunk: ChunkCallback, chunk_ms: int = 100, out_rate: int = 16000) -> None:
        super().__init__("prospect", on_chunk)
        import time as _time

        self._time = _time
        self.rate = out_rate
        self._lock = threading.Lock()
        self._mic = 0.0
        self.levels: dict[int, float] = {}
        self.scores: dict[int, float] = {}
        self.names: dict[int, str] = {}
        self.caps: dict[int, "WasapiCapture"] = {}
        self.locked = False
        self._last_switch = 0.0
        loopbacks = [d for d in list_devices("wasapi") if d.is_loopback]
        try:
            default = _shared_pa().get_default_wasapi_loopback()["index"]
        except Exception:
            default = loopbacks[0].index if loopbacks else None
        for d in loopbacks:
            try:
                cap = WasapiCapture("prospect", self._make_cb(d.index, d.rate), d.index,
                                    max(1, d.in_channels), d.rate, d.name, chunk_ms)
            except Exception as e:
                log.info("skipping speaker %s: %s", d.name, type(e).__name__)
                continue
            self.caps[d.index] = cap
            self.names[d.index] = d.name
            self.levels[d.index] = 0.0
            self.scores[d.index] = 0.0
        if not self.caps:
            raise RuntimeError("No speakers found to record call audio from. Run: python main.py --list-devices")
        self.active = default if default in self.caps else next(iter(self.caps))

    @property
    def device_name(self) -> str:          # type: ignore[override]
        return self.names.get(self.active, "")

    @device_name.setter
    def device_name(self, _v) -> None:
        pass

    def note_mic(self, rms: float) -> None:
        """Called with the rep's mic level (audio thread)."""
        self._mic = max(rms, self._mic * 0.8)

    def _make_cb(self, idx: int, rate: int):
        def cb(pcm: bytes) -> None:           # audio thread, mono int16 at the device rate
            r = _rms(pcm)
            with self._lock:
                self.levels[idx] = max(r, self.levels[idx] * 0.7)
                heard = r if self._mic < self.MIC_QUIET else 0.0
                self.scores[idx] = self.scores[idx] * 0.97 + heard * 0.03
                forward = idx == self.active
            if forward:
                self.on_chunk(resample_int16(pcm, rate, self.rate))
        return cb

    def start(self) -> None:
        started = {}
        for idx, cap in self.caps.items():
            try:
                cap.start()
                started[idx] = cap
            except Exception as e:
                log.info("couldn't open speaker %s: %s", self.names[idx], type(e).__name__)
        if not started:
            raise RuntimeError("Couldn't open any speaker for call audio")
        self.caps = started
        if self.active not in self.caps:
            self.active = next(iter(self.caps))

    def stop(self) -> None:
        for cap in self.caps.values():
            try:
                cap.stop()
            except Exception:
                pass

    def pick(self) -> bool:
        """Switch to the speaker carrying the other side, if it's clearly a different one.
        Returns True when it switched."""
        now = self._time.monotonic()
        with self._lock:
            # Speakers that went quiet stop sending audio entirely, so age everything here.
            for i in self.scores:
                self.scores[i] *= 0.9
                self.levels[i] *= 0.5
        if self.locked:
            return False
        with self._lock:
            best = max(self.scores, key=self.scores.get)
            cur = self.scores.get(self.active, 0.0)
            if (best != self.active and self.scores[best] >= self.MIN_SCORE
                    and self.scores[best] >= self.SWITCH_RATIO * max(cur, 1e-6)
                    and now - self._last_switch >= self.HOLD_S):
                self.active = best
                self._last_switch = now
                return True
        return False

    def set_active(self, idx: int | None) -> None:
        """idx=None: automatic. Otherwise lock to that speaker."""
        with self._lock:
            if idx is None:
                self.locked = False
            elif idx in self.caps:
                self.active = idx
                self.locked = True
                self._last_switch = self._time.monotonic()

    def device_list(self) -> list[dict]:
        with self._lock:
            return [{"index": i, "name": self.names[i].replace(" [Loopback]", ""),
                     "level": round(min(1.0, (self.levels[i] * 6) ** 0.6), 2), "active": i == self.active}
                    for i in self.caps]
