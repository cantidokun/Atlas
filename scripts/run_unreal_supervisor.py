"""Atlas Windows Process Supervisor for Unreal Engine Job Object containment.

Authoritative specification: docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md §9.
"""

from __future__ import annotations

import ctypes
import datetime
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

# Process creation flags used by the containment launch boundary.
CREATE_SUSPENDED = 0x00000004
CREATE_NEW_CONSOLE = 0x00000010
CREATE_NO_WINDOW = 0x08000000
CREATE_BREAKAWAY_FROM_JOB = 0x01000000

# OpenJobObjectW desired access (query only: the transport/lookup primitive).
JOB_OBJECT_QUERY = 0x0004

# OpenProcess desired access for read-only process queries.
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


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


class STARTUPINFOW(ctypes.Structure):
    """Windows STARTUPINFOW (CreateProcessW)."""

    _fields_ = [
        ("cb", ctypes.c_uint32),
        ("lpReserved", ctypes.c_wchar_p),
        ("lpDesktop", ctypes.c_wchar_p),
        ("lpTitle", ctypes.c_wchar_p),
        ("dwX", ctypes.c_uint32),
        ("dwY", ctypes.c_uint32),
        ("dwXSize", ctypes.c_uint32),
        ("dwYSize", ctypes.c_uint32),
        ("dwXCountChars", ctypes.c_uint32),
        ("dwYCountChars", ctypes.c_uint32),
        ("dwFillAttribute", ctypes.c_uint32),
        ("dwFlags", ctypes.c_uint32),
        ("wShowWindow", ctypes.c_uint16),
        ("cbReserved2", ctypes.c_uint16),
        ("lpReserved2", ctypes.c_void_p),
        ("hStdInput", ctypes.c_void_p),
        ("hStdOutput", ctypes.c_void_p),
        ("hStdError", ctypes.c_void_p),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    """Windows PROCESS_INFORMATION (CreateProcessW)."""

    _fields_ = [
        ("hProcess", ctypes.c_void_p),
        ("hThread", ctypes.c_void_p),
        ("dwProcessId", ctypes.c_uint32),
        ("dwThreadId", ctypes.c_uint32),
    ]


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]


def _configure_kernel32_prototypes(kernel32) -> None:
    """Declare Win32 prototypes BEFORE any handle is created.

    The ctypes default ``c_int`` return type truncates 64-bit HANDLEs, which
    produces spurious ``WinError 5`` (ACCESS_DENIED) from
    ``AssignProcessToJobObject``/``SetInformationJobObject``. Declaring the
    prototypes on the cached ``kernel32`` instance removes that whole failure class.
    """
    kernel32.CreateJobObjectW.restype = ctypes.c_void_p
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    kernel32.OpenJobObjectW.restype = ctypes.c_void_p
    kernel32.OpenJobObjectW.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.SetInformationJobObject.restype = ctypes.c_bool
    kernel32.SetInformationJobObject.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32
    ]
    kernel32.QueryInformationJobObject.restype = ctypes.c_bool
    kernel32.QueryInformationJobObject.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p
    ]
    kernel32.AssignProcessToJobObject.restype = ctypes.c_bool
    kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel32.CreateProcessW.restype = ctypes.c_bool
    kernel32.CreateProcessW.argtypes = [
        ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_bool, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_wchar_p,
        ctypes.c_void_p, ctypes.c_void_p,
    ]
    kernel32.ResumeThread.restype = ctypes.c_uint32
    kernel32.ResumeThread.argtypes = [ctypes.c_void_p]
    kernel32.TerminateProcess.restype = ctypes.c_bool
    kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel32.CloseHandle.restype = ctypes.c_bool
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.GetProcessTimes.restype = ctypes.c_bool
    kernel32.GetProcessTimes.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
    ]
    kernel32.GetLastError.restype = ctypes.c_uint32


def filetime_to_iso8601_utc(filetime: FILETIME) -> str:
    """Convert a Win32 FILETIME (100 ns ticks since 1601-01-01Z) to ISO-8601 UTC."""
    ticks = (int(filetime.dwHighDateTime) << 32) | int(filetime.dwLowDateTime)
    # 116444736000000000 == seconds between 1601-01-01 and 1970-01-01, in 100ns ticks.
    unix_100ns = ticks - 116444736000000000
    seconds, remainder = divmod(unix_100ns, 10000000)
    microseconds = remainder // 10
    moment = datetime.datetime.fromtimestamp(seconds, tz=datetime.timezone.utc).replace(
        microsecond=microseconds
    )
    return moment.isoformat()


@dataclass(frozen=True)
class JobObjectContainmentState:
    """Kernel-reported state of one Job Object (Contract V1 §9 conjuncts 3 and 4)."""

    active_processes: int
    total_processes: int
    total_terminated_processes: int
    limit_flags: int
    kill_on_job_close: bool
    silent_breakaway_ok: bool
    breakaway_ok: bool
    reason: str = ""

    @property
    def breakaway_disabled(self) -> bool:
        return not (self.silent_breakaway_ok or self.breakaway_ok)


@dataclass(frozen=True)
class SuspendedProcess:
    """A process created with CREATE_SUSPENDED, before any thread is resumed."""

    process_handle: int
    thread_handle: int
    process_id: int
    thread_id: int
    process_creation_time_utc: str
    command_line: str


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
        if self._kernel32 is not None:
            # Declare Win32 prototypes before ANY handle is created: the ctypes
            # default c_int return type truncates 64-bit HANDLEs.
            _configure_kernel32_prototypes(self._kernel32)

    def create_contained_job(self) -> int:
        """Create a Windows Job Object configured with KILL_ON_JOB_CLOSE and no breakaway."""
        if os.name != "nt":
            raise NotImplementedError("Job Objects are only supported on Windows")
        _configure_kernel32_prototypes(self._kernel32)

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

    def assign_suspended_process(self, process_handle: int) -> None:
        """Assign a CREATE_SUSPENDED process to the Job Object.

        This MUST be the assignment path for a contained launch: assigning an
        already-running process is refused by Windows (``WinError 5``), and the
        suspended window is what makes the containment race-free (no descendant can
        be spawned before the tree is inside the object).
        """
        self.assign_process(process_handle)

    def query_containment_state(self) -> JobObjectContainmentState:
        """Read the object's kernel accounting AND configured containment limits.

        Returns Contract V1 §9's kernel evidence in one call: ``ActiveProcesses``,
        ``TotalProcesses`` (cumulative; ``0`` for a never-used object -- the
        F-DG-1 discriminator), ``TotalTerminatedProcesses`` (diagnostic only, NOT a
        quiescence signal) and the read-back limit flags proving
        ``KILL_ON_JOB_CLOSE`` with breakaway disabled.
        """
        if not self.job_handle:
            raise RuntimeError("Job Object has not been created")

        accounting = JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
        success = self._kernel32.QueryInformationJobObject(
            self.job_handle,
            JobObjectBasicAccountingInformation,
            ctypes.byref(accounting),
            ctypes.sizeof(accounting),
            None,
        )
        if not success:
            err = self._kernel32.GetLastError()
            raise RuntimeError(f"Failed to QueryInformationJobObject(accounting): WinError {err}")

        limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        success = self._kernel32.QueryInformationJobObject(
            self.job_handle,
            JobObjectExtendedLimitInformation,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
            None,
        )
        if not success:
            err = self._kernel32.GetLastError()
            raise RuntimeError(f"Failed to QueryInformationJobObject(limits): WinError {err}")

        flags = int(limits.BasicLimitInformation.LimitFlags)
        return JobObjectContainmentState(
            active_processes=int(accounting.ActiveProcesses),
            total_processes=int(accounting.TotalProcesses),
            total_terminated_processes=int(accounting.TotalTerminatedProcesses),
            limit_flags=flags,
            kill_on_job_close=bool(flags & JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE),
            silent_breakaway_ok=bool(flags & JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK),
            breakaway_ok=bool(flags & JOB_OBJECT_LIMIT_BREAKAWAY_OK),
        )

    @classmethod
    def open_existing_job(cls, job_name: str) -> "AtlasProcessSupervisor":
        """Open an EXISTING Job Object by name (transport/lookup primitive only).

        A Job Object name is metadata, never proof of identity: this object may be
        queried, but it is NOT attempt-attributable on its own and MUST NOT be
        accepted as a §9 quiescence source without the attempt's authenticated launch
        record. Opening can only succeed while another process still holds a handle
        (last-handle close destroys the object under ``KILL_ON_JOB_CLOSE``).
        """
        if not isinstance(job_name, str) or not job_name.strip():
            raise ValueError("job_name must be a non-empty string")
        if os.name != "nt":
            raise NotImplementedError("Job Objects are only supported on Windows")
        kernel32 = ctypes.windll.kernel32
        _configure_kernel32_prototypes(kernel32)
        handle = kernel32.OpenJobObjectW(JOB_OBJECT_QUERY, False, job_name.strip())
        if not handle:
            err = kernel32.GetLastError()
            raise RuntimeError(f"Failed to OpenJobObjectW({job_name!r}): WinError {err}")
        supervisor = cls(job_name=job_name.strip())
        supervisor._kernel32 = kernel32
        supervisor.job_handle = handle
        return supervisor

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
        """Close Job Object handle, terminating contained processes if configured.

        Under ``KILL_ON_JOB_CLOSE`` this is the containment's fail-closed reap: when
        the last handle closes, the contained tree is terminated and the object (its
        counters and its name) is destroyed. A lost handle is therefore a lost
        provenance, never a recoverable one.
        """
        if self.job_handle and self._kernel32:
            self._kernel32.CloseHandle(self.job_handle)
            self.job_handle = None


def create_process_suspended(
    command_line: str,
    *,
    application_name: Optional[str] = None,
    working_directory: Optional[str] = None,
    create_new_console: bool = False,
    create_no_window: bool = False,
) -> SuspendedProcess:
    """``CreateProcessW`` with ``CREATE_SUSPENDED`` (no thread is resumed here).

    The caller MUST assign the returned process to the Job Object and durably record
    the launch identity BEFORE calling :func:`resume_process`. Explicit breakaway is
    never requested (Contract V1 §9.274), so a contained launch cannot leave the
    object.
    """
    if os.name != "nt":
        raise NotImplementedError("Process containment is only supported on Windows")
    if not isinstance(command_line, str) or not command_line.strip():
        raise ValueError("command_line must be a non-empty string")

    kernel32 = ctypes.windll.kernel32
    _configure_kernel32_prototypes(kernel32)

    flags = CREATE_SUSPENDED
    if create_new_console:
        flags |= CREATE_NEW_CONSOLE
    if create_no_window:
        flags |= CREATE_NO_WINDOW
    # Explicit breakaway is prohibited by Contract V1 §9.274 and is never set here.
    if flags & CREATE_BREAKAWAY_FROM_JOB:  # pragma: no cover - defensive
        raise RuntimeError("CREATE_BREAKAWAY_FROM_JOB is prohibited inside a contained launch")

    startup_info = STARTUPINFOW()
    startup_info.cb = ctypes.sizeof(STARTUPINFOW)
    process_info = PROCESS_INFORMATION()
    command_line_buffer = ctypes.create_unicode_buffer(command_line)

    success = kernel32.CreateProcessW(
        application_name,
        command_line_buffer,
        None,
        None,
        False,
        flags,
        None,
        str(working_directory) if working_directory else None,
        ctypes.byref(startup_info),
        ctypes.byref(process_info),
    )
    if not success:
        err = kernel32.GetLastError()
        raise RuntimeError(f"Failed to CreateProcessW({command_line!r}): WinError {err}")

    process_handle = process_info.hProcess
    thread_handle = process_info.hThread
    try:
        creation = FILETIME()
        exit_time = FILETIME()
        kernel_time = FILETIME()
        user_time = FILETIME()
        ok = kernel32.GetProcessTimes(
            process_handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        )
        if not ok:
            err = kernel32.GetLastError()
            raise RuntimeError(f"Failed to GetProcessTimes: WinError {err}")
        creation_time_utc = filetime_to_iso8601_utc(creation)
    except Exception:
        # Fail closed: never leave an uncontained/unnamed suspended process behind.
        kernel32.TerminateProcess(process_handle, 1)
        kernel32.CloseHandle(thread_handle)
        kernel32.CloseHandle(process_handle)
        raise

    return SuspendedProcess(
        process_handle=process_handle,
        thread_handle=thread_handle,
        process_id=int(process_info.dwProcessId),
        thread_id=int(process_info.dwThreadId),
        process_creation_time_utc=creation_time_utc,
        command_line=command_line,
    )


def resume_process(thread_handle: int) -> None:
    """Resume the primary thread of a suspended process (the last launch step)."""
    if os.name != "nt":
        raise NotImplementedError("Process containment is only supported on Windows")
    kernel32 = ctypes.windll.kernel32
    _configure_kernel32_prototypes(kernel32)
    previous_count = kernel32.ResumeThread(thread_handle)
    if previous_count == 0xFFFFFFFF:
        err = kernel32.GetLastError()
        raise RuntimeError(f"Failed to ResumeThread: WinError {err}")


def terminate_process(process_handle: int, exit_code: int = 1) -> None:
    """Terminate one process by handle (fail-closed cleanup path)."""
    if os.name != "nt":
        raise NotImplementedError("Process containment is only supported on Windows")
    kernel32 = ctypes.windll.kernel32
    _configure_kernel32_prototypes(kernel32)
    kernel32.TerminateProcess(process_handle, exit_code)


def close_handle(handle: int) -> None:
    """Close one Win32 handle."""
    if os.name != "nt" or not handle:
        return
    kernel32 = ctypes.windll.kernel32
    _configure_kernel32_prototypes(kernel32)
    kernel32.CloseHandle(handle)


def evaluate_process_quiescence(
    supervisor: Optional[AtlasProcessSupervisor],
    deployment_mode: str,
) -> ProcessQuiescenceResult:
    """Evaluate Contract V1 §9 process quiescence predicate.

    ATTEMPT-UNBOUND PREDICATE (legacy/compatibility surface). This function answers
    only "does this handle report ``ActiveProcesses == 0``"; it does NOT establish
    handle provenance, so a fresh/empty Job Object satisfies it (F-DG-1). The
    recovery coordinator therefore uses
    :func:`planning.unreal_containment_quiescence.evaluate_containment_quiescence`,
    which adds the §9 launch-record provenance, kernel configuration and kernel
    counter-consistency conjuncts. Kept for the harness/diagnostic callers and for
    the `UNCONTAINED_ATTACHED`/unknown-mode fail-closed branches, whose reasons are
    asserted to stay identical across both predicates.
    """
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
