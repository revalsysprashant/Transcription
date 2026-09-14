# Local storage: copy originals to generated paths; temporary processing files stay separate.
import shutil
from pathlib import Path
from uuid import UUID

from app.core.config import settings


class StorageRepository:
    """Keep original audio on disk without exposing paths in API responses."""

    @staticmethod
    def save_original(source: str | Path, user_id: UUID, job_id: UUID) -> str:
        """Copy an original into permanent storage and return a relative storage key.

        Input: an existing temporary file and server-controlled user/job UUIDs.
        Processing: create a unique file and copy its bytes in bounded chunks.
        Output: relative key for the database. Partial files are removed on error.
        """
        storage_key = f"{user_id}/{job_id}.audio"
        destination = settings.audio_storage_dir / storage_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        created = False
        try:
            with destination.open("xb") as output:
                created = True
                with Path(source).open("rb") as original:
                    shutil.copyfileobj(original, output, length=64 * 1024)
        except BaseException:
            if created:
                destination.unlink(missing_ok=True)
            raise
        return storage_key

    @staticmethod
    def remove_original(storage_key: str) -> None:
        """Remove a file created by save_original when database persistence fails.

        The service supplies the generated key; never pass a client-supplied path.
        """
        (settings.audio_storage_dir / storage_key).unlink(missing_ok=True)

    @staticmethod
    def get_original_path(storage_key: str) -> Path | None:
        """Resolve a stored key to an existing file inside the configured storage root.

        Input: the key from an owned database record, not a request path.
        Output: a local file path, or None if missing or outside storage.
        Resolving the path also prevents symlinks from escaping the storage root.
        """
        root = settings.audio_storage_dir.resolve()
        destination = (root / storage_key).resolve()
        if not destination.is_relative_to(root) or not destination.is_file():
            return None
        return destination
