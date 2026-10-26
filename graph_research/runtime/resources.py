"""Shared protocol ceilings and opt-in host resource profiles; no allocation."""
import os

MAX_WALL_SECONDS = 7 * 86400
MAX_CPU_SECONDS = 365 * 86400
MAX_MEMORY_MB = 1024 * 1024
MAX_TOOL_CALLS = 10000
MAX_EVALUATIONS = 1000000
MAX_ROUNDS = 100000
MAX_BATCH_SIZE = 4096
MAX_SEGMENT_EVALUATIONS = 4096
MAX_THREADS = 128
MAX_SESSION_BYTES = 256 * 1024 * 1024


def machine_resources():
    total = None
    if os.name == 'nt':
        import ctypes
        class Memory(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                        *[(name, ctypes.c_ulonglong) for name in
                          ('total', 'available', 'page_total', 'page_available', 'virtual_total', 'virtual_available', 'extended')]]
        value = Memory(); value.length = ctypes.sizeof(value)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
            total = int(value.total // (1024 * 1024))
    return {'logical_cpus': os.cpu_count() or 1, 'physical_memory_mb': total}


def host_profile(name):
    if name == 'standard':
        return {'max_tool_calls': 10, 'tool_seconds': 30, 'tool_cpu_seconds': 30,
                'tool_memory_mb': 1024, 'tool_threads': 1}
    if name != 'research':
        raise ValueError('Unknown resource profile')
    machine = machine_resources()
    threads = min(MAX_THREADS, max(1, machine['logical_cpus'] - 1))
    memory = min(65536, max(64, int((machine['physical_memory_mb'] or 8192) * .75)))
    return {'max_tool_calls': 1000, 'tool_seconds': 900,
            'tool_cpu_seconds': min(MAX_CPU_SECONDS, 900 * threads),
            'tool_memory_mb': memory, 'tool_threads': threads}
