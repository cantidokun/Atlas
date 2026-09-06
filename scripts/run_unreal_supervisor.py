"""Atlas Windows Process Supervisor for Unreal Engine Job Object containment.

Authoritative specification: docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md §9.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional, Tuple


# Windows API constants
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK = 0x00001000
JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x00000800
JobObjectBasicAccountingInformation = 1
JobObjectExtendedLimitInformation = 9


class JOBOBJECT_BASIC_ACCOUNTING_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("TotalUserTime", ctypes.c_int64),
        ("TotalKernelTime", ctypes.c_int64),
        ("ThisPeriodTotalUserTime", ctypes.c_int64),
        ("ThisPeriodTotalKernelTime", ctypes.c_int64),
        ("TotalPageFaultCount", ctypes.c_uint32),
        ("TotalProcesses", ctypes.c_uint32),
        ("ActiveProcesses", ctypes.c_uint32),
        ("TotalTerminatedProcesses", ctypes.c_uint32),
    ]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


@dataclass(frozen=True)
class ProcessQuiescenceResult:
    is_quiescent: bool
    active_process_count: int
    deployment_mode: str
    reason: str


class AtlasProcessSupervisor:
    """Windows Job Object supervisor for Unreal Engine rendering instances."""

    def __init__(self, job_name: Optional[str] = None):
        self.job_name = job_name
        self.job_handle: Optional[int] = None
        self._kernel32 = ctypes.windll.kernel32 if os.name == "nt" else None

    def create_contained_job(self) -> int:
        """Create a Windows Job Object configured with KILL_ON_JOB_CLOSE and no breakaway."""
        if os.name != "nt":
            raise NotImplementedError("Job Objects are only supported on Windows")

        name = self.job_name if self.job_name else None
        h_job = self._kernel32.CreateJobObjectW(None, name)
        if not h_job:
            err = self._kernel32.GetLastError()
            raise RuntimeError(f"Failed to CreateJobObjectW: WinError {err}")

        # Configure extended limits: KILL_ON_JOB_CLOSE, NO breakaway
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

        success = self._kernel32.SetInformationJobObject(
            h_job,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not success:
            err = self._kernel32.GetLastError()
            self._kernel32.CloseHandle(h_job)
            raise RuntimeError(f"Failed to SetInformationJobObject: WinError {err}")

        self.job_handle = h_job
        return h_job

    def assign_process(self, process_handle: int) -> None:
        """Assign an active process to the Job Object."""
        if not self.job_handle:
            raise RuntimeError("Job Object has not been created")
        success = self._kernel32.AssignProcessToJobObject(self.job_handle, process_handle)
        if not success:
            err = self._kernel32.GetLastError()
            raise RuntimeError(f"Failed to AssignProcessToJobObject: WinError {err}")

    def query_active_processes(self) -> int:
        """Query the kernel for the exact number of active processes in the Job Object."""
        if not self.job_handle:
            raise RuntimeError("Job Object has not been created")
        info = JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
        success = self._kernel32.QueryInformationJobObject(
            self.job_handle,
            JobObjectBasicAccountingInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
            None,
        )
        if not success:
            err = self._kernel32.GetLastError()
            raise RuntimeError(f"Failed to QueryInformationJobObject: WinError {err}")
        return int(info.ActiveProcesses)

    def close(self) -> None:
        """Close Job Object handle, terminating contained processes if configured."""
        if self.job_handle and self._kernel32:
            self._kernel32.CloseHandle(self.job_handle)
            self.job_handle = None


def evaluate_process_quiescence(
    supervisor: Optional[AtlasProcessSupervisor],
    deployment_mode: str,
) -> ProcessQuiescenceResult:
    """Evaluate Contract V1 §9 process quiescence predicate."""
    normalized_mode = deployment_mode.upper().strip()
    if normalized_mode == "UNCONTAINED_ATTACHED":
        return ProcessQuiescenceResult(
            is_quiescent=False,
            active_process_count=-1,
            deployment_mode="UNCONTAINED_ATTACHED",
            reason="Uncontained attached mode fails closed: zero surviving descendants cannot be proven",
        )

    if normalized_mode == "CONTAINED_JOB_OBJECT":
        if supervisor is None or supervisor.job_handle is None:
            return ProcessQuiescenceResult(
                is_quiescent=False,
                active_process_count=-1,
                deployment_mode="CONTAINED_JOB_OBJECT",
                reason="Supervisor or Job Object handle is missing/invalid",
            )
        try:
            active_count = supervisor.query_active_processes()
            if active_count == 0:
                return ProcessQuiescenceResult(
                    is_quiescent=True,
                    active_process_count=0,
                    deployment_mode="CONTAINED_JOB_OBJECT",
                    reason="Job Object contains exactly 0 active processes",
                )
            return ProcessQuiescenceResult(
                is_quiescent=False,
                active_process_count=active_count,
                deployment_mode="CONTAINED_JOB_OBJECT",
                reason=f"Job Object still has {active_count} active processes",
            )
        except Exception as exc:
            return ProcessQuiescenceResult(
                is_quiescent=False,
                active_process_count=-1,
                deployment_mode="CONTAINED_JOB_OBJECT",
                reason=f"Failed to query Job Object accounting: {exc}",
            )

    return ProcessQuiescenceResult(
        is_quiescent=False,
        active_process_count=-1,
        deployment_mode=deployment_mode,
        reason=f"Unknown deployment mode: {deployment_mode!r}",
    )
