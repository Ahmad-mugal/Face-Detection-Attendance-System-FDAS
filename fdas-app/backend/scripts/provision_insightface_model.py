from __future__ import annotations

import hashlib
import shutil
import urllib.request
import zipfile
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent.parent
MODEL_ROOT = BACKEND_DIR / "models" / "insightface"
MODEL_DIRECTORY = MODEL_ROOT / "buffalo_l"
ARCHIVE_PATH = MODEL_ROOT / "buffalo_l.zip"
PARTIAL_PATH = MODEL_ROOT / "buffalo_l.zip.part"
EXTRACTING_DIRECTORY = MODEL_ROOT / ".buffalo_l.extracting"
MODEL_URL = "https://github.com/deepinsight/insightface/releases/download/model-zoo/buffalo_l.zip"
EXPECTED_ARCHIVE_BYTES = 288_621_354
EXPECTED_ARCHIVE_SHA256 = "80ffe37d8a5940d59a7384c201a2a38d4741f2f3c51eef46ebb28218a7b0ca2f"
EXPECTED_MODEL_FILES = {
    "1k3d68.onnx": "df5c06b8a0c12e422b2ed8947b8869faa4105387f199c477af038aa01f9a45cc",
    "2d106det.onnx": "f001b856447c413801ef5c42091ed0cd516fcd21f2d6b79635b1e733a7109dbf",
    "det_10g.onnx": "5838f7fe053675b1c7a08b633df49e7af5495cee0493c7dcf6697200b85b5b91",
    "genderage.onnx": "4fde69b1c810857b88c64a335084f1c3fe8f01246c9a191b48c7bb756d6652fb",
    "w600k_r50.onnx": "4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_model_directory(path: Path) -> None:
    for filename, expected_hash in EXPECTED_MODEL_FILES.items():
        model_file = path / filename
        if not model_file.is_file():
            raise RuntimeError(f"Required model file is missing: {model_file}")
        actual_hash = sha256(model_file)
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"Model hash mismatch for {filename}: expected {expected_hash}, found {actual_hash}"
            )


def verify_archive(path: Path) -> None:
    size = path.stat().st_size
    if size != EXPECTED_ARCHIVE_BYTES:
        raise RuntimeError(
            f"Archive size mismatch: expected {EXPECTED_ARCHIVE_BYTES}, found {size}"
        )
    actual_hash = sha256(path)
    if actual_hash != EXPECTED_ARCHIVE_SHA256:
        raise RuntimeError(
            f"Archive hash mismatch: expected {EXPECTED_ARCHIVE_SHA256}, found {actual_hash}"
        )


def safe_extract(archive: Path, destination: Path) -> None:
    destination_root = destination.resolve()
    with zipfile.ZipFile(archive) as package:
        for member in package.infolist():
            member_path = (destination / member.filename).resolve()
            try:
                member_path.relative_to(destination_root)
            except ValueError as exc:
                raise RuntimeError(f"Unsafe archive member: {member.filename}") from exc
        package.extractall(destination)


def main() -> None:
    MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    if MODEL_DIRECTORY.is_dir():
        verify_model_directory(MODEL_DIRECTORY)
        print(f"buffalo_l already provisioned and verified: {MODEL_DIRECTORY}")
        return
    if PARTIAL_PATH.exists() or EXTRACTING_DIRECTORY.exists():
        raise RuntimeError(
            "A previous partial provisioning artifact exists. Review and remove it before retrying."
        )
    if not ARCHIVE_PATH.is_file():
        print(f"Downloading {MODEL_URL}")
        urllib.request.urlretrieve(MODEL_URL, PARTIAL_PATH)
        verify_archive(PARTIAL_PATH)
        PARTIAL_PATH.replace(ARCHIVE_PATH)
    else:
        verify_archive(ARCHIVE_PATH)

    EXTRACTING_DIRECTORY.mkdir()
    safe_extract(ARCHIVE_PATH, EXTRACTING_DIRECTORY)
    verify_model_directory(EXTRACTING_DIRECTORY)
    shutil.move(str(EXTRACTING_DIRECTORY), str(MODEL_DIRECTORY))
    print(f"buffalo_l provisioned and verified: {MODEL_DIRECTORY}")


if __name__ == "__main__":
    main()
