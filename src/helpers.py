import logging
import subprocess

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
logger.addHandler(ch)


def get_logger() -> logging.Logger:
    """Return the logger"""
    return logger


def cmd_log(cmd: list, cwd: str = None) -> None:
    """Log a command to stdout"""
    out = ""
    if cwd:
        out += "├─ 🖥️  $ cd " + cwd
    out += "├─ 🖥️  $ " + " ".join(map(str, cmd))
    logging.debug(out)


def run(cmd: list, cwd=None) -> subprocess.CompletedProcess:
    """Run a command"""
    cmd_log(cmd, cwd=cwd)
    out = subprocess.run(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
    )
    return out


def check_executable(cmd: str) -> bool:
    """Check if a command is available"""
    try:
        # Check if the command is available in the PATH
        subprocess.run(["which", cmd], check=True, stdout=subprocess.DEVNULL)
        return True
    except:
        return False
