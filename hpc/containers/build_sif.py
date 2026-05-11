#!/usr/bin/env python3
"""Build OCI archives and convert them to Apptainer/Singularity SIF images.

Builds one Docker image per requested platform via `docker buildx`, saves it as
an OCI archive under `containers/`, then converts each archive to a `.sif` file.

If `apptainer` (or `singularity`) is available locally, conversion is done
directly from the Docker daemon — no intermediate archive needed. Otherwise
falls back to running apptainer inside Docker via the kaczmarj/apptainer image.

Requirements
------------
- Docker Engine with a buildx builder using the docker-container driver
  (required for --output type=oci and multi-platform builds):
    docker buildx create --use --name builder --driver docker-container
    docker buildx inspect --bootstrap
- apptainer or singularity (optional but recommended — enables the fast path
  that skips the intermediate OCI archive):
    # Ubuntu/Debian: https://apptainer.org/docs/admin/main/installation.html
    sudo apt install apptainer
- project package installed in the active Python environment (for version lookup):
    uv sync
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTAINERS_DIR = PROJECT_ROOT / "containers"

PLATFORM_SUFFIX: dict[str, str] = {
    "linux/amd64": "",
    "linux/arm64": "-arm64",
}
PLATFORM_ARCH: dict[str, str] = {
    "linux/amd64": "amd64",
    "linux/arm64": "arm64",
}
APPTAINER_IMAGE = "kaczmarj/apptainer:latest"

_HOST_PLATFORM = {"x86_64": "linux/amd64", "aarch64": "linux/arm64"}.get(
    platform.machine(), f"linux/{platform.machine()}"
)


def _check_clean_tree() -> None:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    if result.stdout.strip():
        print(
            "error: uncommitted changes would be baked into the image.\n"
            "Commit or stash all changes before building the SIF.\n\n" + result.stdout,
            file=sys.stderr,
        )
        raise SystemExit(1)


def _local_apptainer() -> str | None:
    return shutil.which("apptainer") or shutil.which("singularity")


def _ssh_flag() -> str:
    """Return '--ssh default' only if the SSH agent has loaded keys."""
    result = subprocess.run(["ssh-add", "-l"], capture_output=True)
    return "--ssh default" if result.returncode == 0 else ""


def _image_name(pkg: str, tag_suffix: str = "") -> str:
    suffix = f"-{tag_suffix}" if tag_suffix else ""
    return f"{pkg.lower()}:{version(pkg)}{suffix}"


def _oci_archive(image: str, plat: str) -> Path:
    suffix = PLATFORM_SUFFIX.get(plat, "")
    return CONTAINERS_DIR / (image.replace(":", "-") + suffix + ".tar.gz")


def _sif_file(image: str, plat: str) -> Path:
    suffix = PLATFORM_SUFFIX.get(plat, "")
    return CONTAINERS_DIR / (image.replace(":", "-") + suffix + ".sif")


def _run(label: str, cmd: str) -> None:
    print(f"  {label}...", flush=True)
    subprocess.run(cmd, shell=True, check=True, cwd=PROJECT_ROOT)


def build_platform(pkg: str, plat: str, dockerfile: Path, tag_suffix: str = "") -> Path:
    image = _image_name(pkg, tag_suffix)
    sif = _sif_file(image, plat)
    apptainer = _local_apptainer()

    print(f"[{plat}] {image}")

    ssh = _ssh_flag()

    if apptainer and plat == _HOST_PLATFORM:
        # Fast path: load into Docker daemon, convert directly — no archive needed.
        # Only works when the target platform matches the host; cross-platform
        # builds fall through to the OCI fallback below.
        _run(
            "docker build",
            f"docker buildx build --platform {plat} {ssh} --load"
            f" --file {dockerfile} -t {image} .",
        )
        _run(
            "apptainer convert",
            f"{apptainer} build --force {sif} docker-daemon://{image}",
        )
    else:
        # Fallback: write OCI archive, convert via apptainer-in-Docker.
        # Use a local BuildKit cache so unchanged layers are not rebuilt.
        archive = _oci_archive(image, plat)
        arch = PLATFORM_ARCH.get(plat, "")
        cache_dir = CONTAINERS_DIR / ".buildkit-cache"
        archive.unlink(missing_ok=True)
        _run(
            "docker build",
            f"docker buildx build --platform {plat} {ssh}"
            f" --cache-from type=local,src={cache_dir}"
            f" --cache-to type=local,dest={cache_dir},mode=max"
            f' --output "type=oci,dest={archive},tar=true"'
            f" --file {dockerfile} -t {image} .",
        )
        _run(
            "apptainer convert",
            f"docker run --rm --volume={CONTAINERS_DIR}:/data {APPTAINER_IMAGE}"
            f" build {'--arch ' + arch if arch else ''} --force"
            f" /data/{sif.name} docker-archive:/data/{archive.name}",
        )

    return sif


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build platform-specific OCI archives with Docker Buildx and convert "
            "them to Apptainer/Singularity SIF images in ./containers."
        )
    )
    parser.add_argument(
        "--pkg",
        default="simulation-project-template",
        help="Package name (used to read version from installed metadata).",
    )
    parser.add_argument(
        "--platforms",
        nargs="+",
        default=["linux/amd64"],
        help="Target platforms (linux/amd64, linux/arm64).",
    )
    parser.add_argument(
        "--suffix",
        default="",
        help="Image/Dockerfile suffix (e.g. 'gpu' uses Dockerfile-gpu and tags as <version>-gpu).",
    )
    parser.add_argument(
        "--dirty",
        action="store_true",
        help="Allow building with uncommitted changes in src/. For testing only.",
    )
    args = parser.parse_args()
    if not args.dirty:
        _check_clean_tree()

    suffix = args.suffix.strip("-")
    dockerfile = PROJECT_ROOT / (f"Dockerfile-{suffix}" if suffix else "Dockerfile")
    image = _image_name(args.pkg, suffix)
    apptainer = _local_apptainer()

    CONTAINERS_DIR.mkdir(parents=True, exist_ok=True)

    print(
        f"Starting SIF build\n"
        f"  image:      {image}\n"
        f"  dockerfile: {dockerfile}\n"
        f"  platforms:  {', '.join(args.platforms)}\n"
        f"  output:     {CONTAINERS_DIR}\n"
        f"  converter:  {apptainer or 'docker (kaczmarj/apptainer)'}"
    )

    sif_outputs = [
        build_platform(args.pkg, plat, dockerfile, tag_suffix=suffix)
        for plat in args.platforms
    ]

    print("\nGenerated SIF image(s):")
    for sif in sif_outputs:
        print(f"  - {sif}")
    print(
        f"\nSet in workflow.yaml:\n  container: {sif_outputs[0] if sif_outputs else '<path>'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
