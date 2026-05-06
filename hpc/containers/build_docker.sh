#!/usr/bin/env sh

# Build and run the Docker image (run from the project root).
# Usage:
#   ./hpc/containers/build_docker.sh                         # default: spt --help
#   ./hpc/containers/build_docker.sh generate 100 -o out.json
#   ./hpc/containers/build_docker.sh --help
# Optional env:
#   IMAGE_TAG=myproject:latest ./hpc/containers/build_docker.sh ...
# Optional host mounts (enabled automatically when directories exist):
#   ./configs -> /configs (read-only)
#   ./results -> /results

IMAGE_TAG="${IMAGE_TAG:-simulation-project-template:latest}"

echo "[INFO] Building Docker image: $IMAGE_TAG"
if ! docker build -t "$IMAGE_TAG" .; then
  echo "[ERROR] Docker build failed."
  exit 1
fi

if [ "$#" -eq 0 ]; then
  set -- spt --help
fi

set -- "$IMAGE_TAG" "$@"

if [ -d "./results" ]; then
  set -- -v "$(pwd)/results:/results" "$@"
fi
if [ -d "./configs" ]; then
  set -- -v "$(pwd)/configs:/configs:ro" "$@"
fi

if [ -t 1 ]; then
  set -- -it "$@"
fi

echo "[INFO] Running container..."
set -- docker run --rm "$@"
"$@"
