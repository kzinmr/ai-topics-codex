"""Subprocess lifecycle: deadlines cover descendants as well as the immediate child."""

import os
import signal
import subprocess


def stop(proc):
    # Reap an already-exited leader before signalling its group. On macOS a
    # zombie-only group can report EPERM. Still signal the group afterwards:
    # descendants may outlive their leader and must obey the same deadline.
    proc.poll()
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
    # The leader may have exited while a descendant ignores SIGTERM.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def execute(argv, *, cwd, env, timeout, input=None):
    proc = subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(input, timeout=timeout)
        if proc.returncode:
            raise RuntimeError(f"{argv[0]} exited {proc.returncode}: {stderr[-4000:]}")
        return stdout
    finally:
        stop(proc)
