#!/usr/bin/env python3
"""Build OCI archives and convert them to Apptainer/Singularity SIF images.

Builds one Docker image per requested platform via `docker buildx`, saves it as
an OCI archive under `containers/`, then converts each archive to a `.sif` file
using an Apptainer container.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import importlib_metadata
from tqdm import tqdm

PLATFORM_SUFFIX: dict[str, str] = {
    "linux/amd64": "",
    "linux/arm64": "-arm64",
}
PLATFORM_ARCH: dict[str, str] = {
    "linux/amd64": "amd64",
    "linux/arm64": "arm64",
}
APPTAINER_IMAGE = "kaczmarj/apptainer:latest"


def _check_clean_src() -> None:
    root = Path(__file__).resolve().parent.parent.parent
    result = subprocess.run(
        ["git", "status", "--porcelain", "src/"],
        capture_output=True,
        text=True,
        cwd=root,
    )
    if result.stdout.strip():
        print(
            "error: uncommitted changes in src/ would be baked into the image.\n"
            "Commit or stash them before building the SIF.\n\n" + result.stdout,
            file=sys.stderr,
        )
        raise SystemExit(1)


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _containers_dir() -> Path:
    d = _project_root() / "containers"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _image_name(pkg: str, tag_suffix: str = "") -> str:
    version = importlib_metadata.version(pkg)
    suffix = f"-{tag_suffix}" if tag_suffix else ""
    return f"{pkg.lower()}:{version}{suffix}"


def _oci_archive(image: str, platform: str) -> Path:
    suffix = PLATFORM_SUFFIX.get(platform, "")
    return _containers_dir() / (image.replace(":", "-") + suffix + ".tar.gz")


def _sif_file(image: str, platform: str) -> Path:
    suffix = PLATFORM_SUFFIX.get(platform, "")
    return _containers_dir() / (image.replace(":", "-") + suffix + ".sif")


def _run(cmd: str, pbar: tqdm) -> None:
    pbar.set_postfix_str(cmd[:72] + "..." if len(cmd) > 72 else cmd)
    subprocess.run(cmd, shell=True, check=True, cwd=_project_root())


def build_platform(
    pkg: str, platform: str, dockerfile: Path, tag_suffix: str = ""
) -> Path:
    image = _image_name(pkg, tag_suffix)
    archive = _oci_archive(image, platform)
    sif = _sif_file(image, platform)
    arch = PLATFORM_ARCH.get(platform, "")

    archive.unlink(missing_ok=True)

    pbar = tqdm(desc=f"[{platform}] {image}")
    _run(
        f"docker buildx build --platform {platform} --ssh default"
        f' --output "type=oci,dest={archive},tar=true"'
        f" --file {dockerfile} -t {image} .",
        pbar,
    )
    _run(
        f"docker run --rm --volume={_containers_dir()}:/data {APPTAINER_IMAGE}"
        f" build {'--arch ' + arch if arch else ''} --force"
        f" /data/{sif.name} docker-archive:/data/{archive.name}",
        pbar,
    )
    pbar.set_postfix_str("done")
    pbar.close()
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
        _check_clean_src()
    suffix = args.suffix.strip("-")
    dockerfile = _project_root() / (f"Dockerfile-{suffix}" if suffix else "Dockerfile")

    print(
        f"Starting SIF build\n"
        f"  image:      {_image_name(args.pkg, suffix)}\n"
        f"  dockerfile: {dockerfile}\n"
        f"  platforms:  {', '.join(args.platforms)}\n"
        f"  output:     {_containers_dir()}"
    )

    sif_outputs: list[Path] = []
    for platform in args.platforms:
        sif = build_platform(args.pkg, platform, dockerfile, tag_suffix=suffix)
        sif_outputs.append(sif)

    print("\nGenerated SIF image(s):")
    for sif in sif_outputs:
        print(f"  - {sif}")
    print(
        f"\nSet in workflow.yaml:\n  container: {sif_outputs[0] if sif_outputs else '<path>'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
