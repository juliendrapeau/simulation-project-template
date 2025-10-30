#!/usr/bin/env sh

# Build and run the Docker image in a flexible way.
# Usage: ./run.sh [script.py [args...]]
# Default: runs main.py

# Determine interactive mode
if [ -t 1 ]; then
    INTERACTIVE="-it"
    echo "[INFO] Interactive terminal detected, using -it"
else
    INTERACTIVE=""
    echo "[INFO] Non-interactive terminal"
fi

# Build the Docker image and save the image ID to a file
IID_FILE=".docker_image_id"
PACKAGE_NAME=$(grep -m1 '^name *= *' pyproject.toml | sed 's/name *= *["'\'']\([^"\'']*\)["'\'']/\1/')
echo "[INFO] Building Docker image..."
docker build -t "$PACKAGE_NAME":latest --iidfile "$IID_FILE" .
IMAGE_ID=$(cat "$IID_FILE")
echo "[INFO] Image built with ID: $IMAGE_ID"

# Verify IMAGE_ID is not empty
if [ -z "$IMAGE_ID" ]; then
    echo "[ERROR] Failed to build Docker image."
    exit 1
fi

# Print what will be run
echo "[INFO] Running container with command: docker run --rm $INTERACTIVE --volume $(pwd):/app --volume /app/.venv $IMAGE_ID $*"

# Run the container
docker run \
    --rm \
    --volume "$(pwd)":/app \
    --volume /app/.venv \
    $INTERACTIVE \
    "$IMAGE_ID" \
    "$@"
