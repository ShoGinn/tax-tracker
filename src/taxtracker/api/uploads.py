"""Upload safety helpers."""

from fastapi import HTTPException, UploadFile, status

from taxtracker.core.config import settings


async def read_limited_upload(file: UploadFile) -> bytes:
    """Read an upload while enforcing the configured maximum size."""
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        max_megabytes = settings.max_upload_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds the {max_megabytes} MB upload limit",
        )
    return content
