import os
import sys
from pathlib import Path

import nbformat
from jupyter_client import KernelManager
from nbclient import NotebookClient


def main():
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    path = root / "notebooks/benchmark_analysis.ipynb"
    notebook = nbformat.read(path, as_version=4)
    manager = KernelManager(kernel_name="python3")
    manager.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
    client = NotebookClient(notebook, km=manager, timeout=180, resources={"metadata": {"path": str(root)}})
    try:
        client.execute()
    finally:
        if manager.has_kernel:
            manager.shutdown_kernel(now=True)
    target = root / "notebooks/benchmark_analysis.executed.ipynb"
    nbformat.write(notebook, target)
    print(f"PASS: {target}")


if __name__ == "__main__":
    main()
