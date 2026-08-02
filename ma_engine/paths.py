"""Robust data-file resolution.

Reading data files via a plain relative path (``data/foo.csv``) depends on the
current working directory, which is not guaranteed on hosted platforms
(Streamlit Cloud, containers, etc.). This resolves a data file against, in order:
the configured ``data_dir`` (as given / relative to CWD), then the repository
root that ships with the package. That makes the engine location-independent.
"""
from __future__ import annotations

import os

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))   # .../ma_engine
_REPO_ROOT = os.path.dirname(_PACKAGE_DIR)                   # repo root (ships data/)


def resolve_data_file(data_dir: str, filename: str) -> str:
    """Return an existing path to ``filename``, trying data_dir then the repo's data/.

    Raises FileNotFoundError with both attempted locations if neither exists, so
    a missing/uncommitted data file produces a clear message.
    """
    candidates = [
        os.path.join(data_dir, filename),                   # as configured / CWD-relative
        os.path.join(_REPO_ROOT, "data", filename),         # bundled with the repo
        os.path.join(_REPO_ROOT, data_dir, filename),       # data_dir relative to repo root
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        f"Could not find data file {filename!r}. Looked in: "
        + "; ".join(candidates)
        + ". If deploying, make sure the data/*.csv files are committed to the repo."
    )
