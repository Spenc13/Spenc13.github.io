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
from dataclasses import dataclass
from typing import Callable

import numpy as np

log = logging.getLogger(__name__)

ChunkCallback = Callable[[bytes], None]


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
        self.pa = pyaudio.PyAudio()
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
        self.pa.terminate()


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
    backend = _backend(cfg_backend)
    out: list[DeviceInfo] = []
    if backend == "wasapi":
        import pyaudiowpatch as pyaudio

        pa = pyaudio.PyAudio()
        try:
            for i in range(pa.get_device_count()):
                d = pa.get_device_info_by_index(i)
                host = pa.get_host_api_info_by_index(d["hostApi"])["name"]
                out.append(DeviceInfo(
                    index=i, name=d["name"], in_channels=int(d["maxInputChannels"]),
                    out_channels=int(d["maxOutputChannels"]), rate=int(d["defaultSampleRate"]),
                    host_api=host, is_loopback=bool(d.get("isLoopbackDevice", False)),
                ))
        finally:
            pa.terminate()
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

        devices = list_devices("wasapi")
        dev = _match(devices, want, lambda d: d.in_channels > 0 and not d.is_loopback)
        if dev is None:
            pa = pyaudio.PyAudio()
            try:
                wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
                d = pa.get_device_info_by_index(wasapi["defaultInputDevice"])
            finally:
                pa.terminate()
            dev = next(x for x in devices if x.index == d["index"])
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
        import pyaudiowpatch as pyaudio

        devices = list_devices("wasapi")
        dev = _match(devices, want, lambda d: d.is_loopback)
        if dev is None and want:
            # User named the speakers/headset; find its loopback twin.
            out = _match(devices, want, lambda d: d.out_channels > 0 and not d.is_loopback)
            if out:
                dev = next((d for d in devices if d.is_loopback and out.name in d.name), None)
        if dev is None:
            pa = pyaudio.PyAudio()
            try:
                lb = pa.get_default_wasapi_loopback()
            finally:
                pa.terminate()
            dev = next(x for x in devices if x.index == lb["index"])
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

