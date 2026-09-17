"""Private resume storage boundary with short-lived download URLs."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4


class ResumeStorage:
    def __init__(self, backend: str, root: str = ".local/resumes") -> None:
        self.backend = backend
        self.root = Path(root)
        if backend == "s3" and not os.getenv("RECRUITING_RESUME_BUCKET"):
            raise ValueError("RECRUITING_RESUME_BUCKET is required for private resume storage")

    def put(self, content: bytes, *, application_id: str) -> str:
        key = f"resumes/{application_id}/{uuid4().hex}"
        if self.backend == "local":
            target = (self.root / key).resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            return target.as_uri()
        import boto3

        client = boto3.client("s3", endpoint_url=os.getenv("RECRUITING_RESUME_ENDPOINT_URL") or None)
        client.put_object(Bucket=os.environ["RECRUITING_RESUME_BUCKET"], Key=key, Body=content)
        return f"s3://{os.environ['RECRUITING_RESUME_BUCKET']}/{key}"

    def signed_download(self, object_uri: str, *, expires: int = 300) -> str:
        if self.backend == "local":
            return object_uri
        import boto3

        bucket, _, key = object_uri.removeprefix("s3://").partition("/")
        client = boto3.client("s3", endpoint_url=os.getenv("RECRUITING_RESUME_ENDPOINT_URL") or None)
        return client.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires)

    def delete(self, object_uri: str) -> None:
        if self.backend == "local" and object_uri.startswith("file:"):
            Path(object_uri.removeprefix("file:///")).unlink(missing_ok=True)
        elif self.backend == "s3":
            import boto3

            bucket, _, key = object_uri.removeprefix("s3://").partition("/")
            boto3.client("s3", endpoint_url=os.getenv("RECRUITING_RESUME_ENDPOINT_URL") or None).delete_object(
                Bucket=bucket, Key=key
            )
