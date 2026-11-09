"""Standalone MORK supervisor profile; same parent/descendant cleanup as inference.

MORK reserves large virtual buffers, so its AS bound is the original 16 GiB
native adapter bound. The existing 5 GiB aggregate RSS and 4 GiB host reserve
remain. This profile is selected by trusted source, never a chat request.
"""
import resource
import fresh_supervise


def memory_limit():
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_AS,(16*1024**3,16*1024**3))


if __name__ == '__main__':
    fresh_supervise.memory_limit = memory_limit
    raise SystemExit(fresh_supervise.main())
