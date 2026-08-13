import oss2

from app.core.config import get_settings


class OssService:
    AVATAR_PREFIX = "avatars/"

    def __init__(self):
        settings = get_settings()

        auth = oss2.Auth(
            settings.oss_access_key_id,
            settings.oss_access_key_secret,
        )

        self.bucket = oss2.Bucket(
            auth,
            settings.oss_endpoint,
            settings.oss_bucket_name,
        )

    def upload_avatar(
        self,
        object_key: str,
        file_data: bytes,
    ) -> str:
        if not object_key.startswith(self.AVATAR_PREFIX):
            raise ValueError("头像必须上传到 avatars/ 目录")

        result = self.bucket.put_object(
            object_key,
            file_data,
            headers={
                "Content-Type": "image/webp",
                "Cache-Control": "private, max-age=3600",
            },
        )

        if result.status != 200:
            raise RuntimeError(
                f"OSS 上传失败，状态码：{result.status}"
            )

        return object_key

    def get_signed_url(
        self,
        object_key: str,
        expires: int = 3600,
    ) -> str:
        if not object_key.startswith(self.AVATAR_PREFIX):
            raise ValueError("无效的头像路径")

        return self.bucket.sign_url(
            "GET",
            object_key,
            expires,
        )

    def delete_avatar(self, object_key: str) -> None:
        if not object_key.startswith(self.AVATAR_PREFIX):
            raise ValueError("不允许删除头像目录以外的文件")

        self.bucket.delete_object(object_key)


oss_service = OssService()