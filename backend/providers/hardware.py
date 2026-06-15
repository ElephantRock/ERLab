"""GPU hardware detection for model-to-hardware fitting.

Detects available GPU VRAM so ModelManager can skip models that
don't fit. Works with nvidia-smi, pynvml, or torch.cuda.
Gracefully returns None on CPU-only systems.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GPUInfo:
    """Detected GPU hardware information."""

    name: str  # e.g. "NVIDIA RTX 3080 Ti"
    vram_total_bytes: int  # total VRAM in bytes
    vram_available_bytes: int  # currently free VRAM
    compute_capability: str  # e.g. "8.6"
    driver_version: str  # e.g. "535.104.05"

    @property
    def vram_total_gb(self) -> float:
        return self.vram_total_bytes / (1024**3)

    @property
    def vram_available_gb(self) -> float:
        return self.vram_available_bytes / (1024**3)


class HardwareDetector:
    """Detect GPU hardware via multiple backends."""

    def detect_gpu(self) -> GPUInfo | None:
        """Detect available GPU. Returns None on CPU-only systems.

        Tries backends in order: nvidia-smi → pynvml → torch.cuda.
        """
        for detector in (
            self._detect_nvidia_smi,
            self._detect_pynvml,
            self._detect_torch,
            self._detect_wmi,
        ):
            try:
                result = detector()
                if result is not None:
                    logger.info(
                        "GPU detected: %s (%.1f GB VRAM, %.1f GB available)",
                        result.name,
                        result.vram_total_gb,
                        result.vram_available_gb,
                    )
                    return result
            except Exception as exc:
                logger.debug("GPU detection method %s failed: %s", detector.__name__, exc)

        logger.info("No GPU detected — running in CPU-only mode")
        return None

    def model_fits(self, model_size_bytes: int, gpu: GPUInfo | None) -> bool:
        """Check if a model can run on available hardware.

        Uses a 1.2x multiplier for KV cache + overhead.
        """
        if gpu is None:
            return True  # CPU-only: let the inference server decide

        # Model needs: weights + KV cache + overhead (~20%)
        estimated = int(model_size_bytes * 1.2)
        return estimated <= gpu.vram_total_bytes

    def models_fit_simultaneously(
        self, model_sizes: list[int], gpu: GPUInfo | None
    ) -> bool:
        """Check if multiple models can coexist in VRAM."""
        if gpu is None:
            return True
        total = sum(model_sizes)
        # Leave 15% for KV cache overhead
        return int(total * 1.15) <= gpu.vram_total_bytes

    @staticmethod
    def _detect_nvidia_smi() -> GPUInfo | None:
        """Detect via nvidia-smi CLI (works without Python GPU libraries)."""
        nvidia_smi = shutil.which("nvidia-smi")
        if nvidia_smi is None:
            return None

        # Query: name, memory.total, memory.free, compute_cap, driver_version
        result = subprocess.run(
            [
                nvidia_smi,
                "--query-gpu=name,memory.total,memory.free,compute_cap,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None

        line = result.stdout.strip().split("\n")[0]
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            return None

        name = parts[0]
        vram_total_mib = int(float(parts[1]))
        vram_free_mib = int(float(parts[2]))
        compute_cap = parts[3]
        driver_version = parts[4]

        # MiB → bytes
        mib_to_bytes = 1024 * 1024
        return GPUInfo(
            name=name,
            vram_total_bytes=vram_total_mib * mib_to_bytes,
            vram_available_bytes=vram_free_mib * mib_to_bytes,
            compute_capability=compute_cap,
            driver_version=driver_version,
        )

    @staticmethod
    def _detect_pynvml() -> GPUInfo | None:
        """Detect via pynvml (NVIDIA management library)."""
        try:
            import pynvml
        except ImportError:
            return None

        pynvml.nvmlInit()
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")

            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            cc_major = pynvml.nvmlDeviceGetCudaComputeCapability(handle)
            try:
                cc_minor = pynvml.nvmlDeviceGetCudaComputeCapabilityMinor(handle)
                compute_cap = f"{cc_major}.{cc_minor}"
            except Exception:
                compute_cap = f"{cc_major}.0"

            driver_version = pynvml.nvmlSystemGetDriverVersion()
            if isinstance(driver_version, bytes):
                driver_version = driver_version.decode("utf-8")

            return GPUInfo(
                name=name,
                vram_total_bytes=mem_info.total,
                vram_available_bytes=mem_info.free,
                compute_capability=compute_cap,
                driver_version=driver_version,
            )
        finally:
            pynvml.nvmlShutdown()

    @staticmethod
    def _detect_torch() -> GPUInfo | None:
        """Detect via torch.cuda (requires PyTorch with CUDA)."""
        try:
            import torch
        except ImportError:
            return None

        if not torch.cuda.is_available():
            return None

        device = torch.cuda.current_device()
        name = torch.cuda.get_device_name(device)
        total = torch.cuda.get_device_properties(device).total_memory
        # Reserved = allocated + cached (unused but held by allocator)
        reserved = torch.cuda.memory_reserved(device)
        available = total - reserved
        cap = torch.cuda.get_device_capability(device)

        return GPUInfo(
            name=name,
            vram_total_bytes=total,
            vram_available_bytes=available,
            compute_capability=f"{cap[0]}.{cap[1]}",
            driver_version=str(torch.version.cuda or "unknown"),
        )

    @staticmethod
    def _detect_wmi() -> GPUInfo | None:
        """Detect via Windows WMI (works for AMD/NVIDIA/Intel GPUs)."""
        import sys
        if sys.platform != "win32":
            return None

        try:
            import subprocess
            result = subprocess.run(
                [
                    "powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_VideoController | "
                    "Select-Object Name, AdapterRAM, DriverVersion | "
                    "ConvertTo-Json",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return None

            import json
            data = json.loads(result.stdout)

            # Handle single GPU (returned as dict) vs multiple (list)
            if isinstance(data, dict):
                gpus = [data]
            elif isinstance(data, list):
                gpus = data
            else:
                return None

            # Find the most capable GPU (prefer NVIDIA, then by VRAM)
            best = None
            for gpu_data in gpus:
                name = gpu_data.get("Name", "Unknown")
                vram = gpu_data.get("AdapterRAM", 0) or 0
                driver = gpu_data.get("DriverVersion", "unknown")

                # Prefer discrete GPUs (NVIDIA/AMD with >2GB VRAM)
                is_discrete = vram > 2 * (1024**3)
                is_nvidia = "NVIDIA" in name.upper() or "GEFORCE" in name.upper() or "RTX" in name.upper()

                if best is None:
                    best = (name, vram, driver, is_nvidia, is_discrete)
                else:
                    _, best_vram, _, best_nvidia, best_discrete = best
                    # Prefer: NVIDIA > discrete > by VRAM
                    if (is_nvidia and not best_nvidia) or (is_discrete and not best_discrete) or vram > best_vram:
                        best = (name, vram, driver, is_nvidia, is_discrete)

            if best is None or best[1] == 0:
                return None

            name, vram, driver, _, _ = best
            return GPUInfo(
                name=name,
                vram_total_bytes=vram,
                vram_available_bytes=vram,  # WMI doesn't report free VRAM
                compute_capability="unknown",
                driver_version=driver,
            )
        except Exception:
            return None
