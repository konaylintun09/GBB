"""Media upload — issues a presigned URL so the client uploads directly to object storage.

The API never proxies the file bytes. Disabled with a clear message until S3/R2 is configured.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import get_settings
from app.deps import require_role
from app.models import User
from app.schemas import PresignIn, PresignOut

router = APIRouter(prefix="/media", tags=["media"])
settings = get_settings()


@router.post("/presign", response_model=PresignOut)
async def presign(body: PresignIn, _: User = Depends(require_role("admin", "engineer"))):
    if not settings.s3_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage is not configured. Set S3_* env vars to enable uploads.",
        )
    import boto3  # imported lazily so the app runs without boto3 in dev

    s3 = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )
    ext = body.filename.rsplit(".", 1)[-1] if "." in body.filename else "jpg"
    key = f"records/{uuid.uuid4().hex}.{ext}"
    url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.s3_bucket, "Key": key, "ContentType": body.content_type},
        ExpiresIn=900,
    )
    return PresignOut(upload_url=url, storage_key=key)
