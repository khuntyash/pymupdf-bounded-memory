"""Peak resident memory of THIS process, in MB (MiB), on Windows, Linux and macOS.

Peak (not current) memory is what an out-of-memory killer cares about, and it is a
process-lifetime value, which is why the benchmark runs each configuration in a fresh
subprocess.
"""
from __future__ import annotations

import sys


def peak_rss_mb() -> float:
    if sys.platform == "win32":
        return _windows_peak_mb()
    if sys.platform.startswith("linux"):
        # Not ru_maxrss: on Linux it is carried across exec(), so a child process would
        # report its PARENT's peak if that was higher. VmHWM belongs to this process only.
        with open("/proc/self/status") as status:
            for line in status:
                if line.startswith("VmHWM:"):
                    return int(line.split()[1]) / 1024  # the value is in kB
        raise OSError("VmHWM not found in /proc/self/status")

    import resource

    # macOS reports ru_maxrss in bytes. The benchmark keeps its parent process small, so
    # the child's value is its own peak.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20


def _windows_peak_mb() -> float:
    import ctypes
    from ctypes import wintypes

    class _Counters(ctypes.Structure):  # PROCESS_MEMORY_COUNTERS
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.K32GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(_Counters), wintypes.DWORD,
    ]
    kernel32.K32GetProcessMemoryInfo.restype = wintypes.BOOL
    counters = _Counters()
    counters.cb = ctypes.sizeof(counters)
    if not kernel32.K32GetProcessMemoryInfo(
        kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
    ):
        raise OSError(ctypes.get_last_error(), "K32GetProcessMemoryInfo failed")
    return counters.PeakWorkingSetSize / 2**20
