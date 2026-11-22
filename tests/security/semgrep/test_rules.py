import logging
import os
import subprocess
import sys
from pathlib import Path


def shell_cases() -> None:
    command = input("command: ")
    # ruleid: omniagent.python.shell-command-from-user-input
    subprocess.run(command, shell=True, check=False)

    # ok: omniagent.python.shell-command-from-user-input
    subprocess.run(["git", "status", "--short"], check=False)


def path_cases(root: Path) -> None:
    name = input("file: ")
    # ruleid: omniagent.python.user-input-path-join
    open(os.path.join(root, name), encoding="utf-8")

    # ok: omniagent.python.user-input-path-join
    open(root.resolve(), encoding="utf-8")


def logging_cases() -> None:
    token = os.getenv("OMNIAGENT_API_KEY")
    # ruleid: omniagent.python.secret-environment-value-logged
    logging.info("provider token: %s", token)

    # ok: omniagent.python.secret-environment-value-logged
    logging.info("provider configured: %s", token is not None)


def tls_cases(url: str) -> None:
    # ruleid: omniagent.python.tls-verification-disabled
    import requests

    requests.get(url, verify=False, timeout=1)

    # ok: omniagent.python.tls-verification-disabled
    requests.get(url, timeout=1)
