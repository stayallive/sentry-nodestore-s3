from __future__ import annotations

from typing import Any, Mapping
from datetime import datetime, timedelta

import boto3
from botocore.config import Config

from sentry.utils.codecs import Codec, ZstdCodec
from sentry.nodestore.base import NodeStorage
from sentry.nodestore.django import DjangoNodeStorage


class S3PassthroughDjangoNodeStorage(DjangoNodeStorage, NodeStorage):
    compression_strategies: Mapping[str, Codec[bytes, bytes]] = {
        "zstd": ZstdCodec(),
    }

    def __init__(
            self,
            delete_through=False,
            write_through=False,
            read_through=False,
            compression=True,
            bucket_name=None,
            region_name=None,
            bucket_path=None,
            endpoint_url=None,
            retry_attempts=3,
            aws_access_key_id=None,
            aws_secret_access_key=None
    ):
        self.delete_through = delete_through
        self.write_through = write_through
        self.read_through = read_through

        if compression:
            self.compression = "zstd"
        else:
            self.compression = None

        self.bucket_name = bucket_name
        self.bucket_path = bucket_path
        self.client = boto3.client(
            config=Config(
                retries={
                    'mode': 'standard',
                    'max_attempts': retry_attempts,
                }
            ),
            region_name=region_name,
            service_name='s3',
            endpoint_url=endpoint_url,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

    def delete(self, id):
        if self.delete_through:
            super().delete(id)
        self.__delete_from_bucket(id)
        self._delete_cache_item(id)

    def _get_bytes(self, id: str) -> bytes | None:
        if self.read_through:
            return self.__read_from_bucket(id) or super()._get_bytes(id)
        return self.__read_from_bucket(id)

    def _get_bytes_multi(self, id_list: list[str]) -> dict[str, bytes | None]:
        return {id: self._get_bytes(id) for id in id_list}

    def delete_multi(self, id_list: list[str]) -> None:
        if self.delete_through:
            super().delete_multi(id_list)
        # TODO: Maybe we should use the bulk delete API of the S3 client instead
        for id in id_list:
            self.__delete_from_bucket(id)
        self._delete_cache_items(id_list)

    def _set_bytes(self, id: str, data: Any, ttl: timedelta | None = None) -> None:
        if self.write_through:
            super()._set_bytes(id, data, ttl)
        self.__write_to_bucket(id, data)

    def cleanup(self, cutoff_timestamp: datetime) -> None:
        if self.delete_through:
            super().cleanup(cutoff_timestamp)

    def __get_key_for_id(self, id: str) -> str:
        if self.bucket_path is None:
            return id
        return self.bucket_path + '/' + id

    def __read_from_bucket(self, id: str) -> bytes | None:
        try:
            obj = self.client.get_object(
                Key=self.__get_key_for_id(id),
                Bucket=self.bucket_name,
            )

            data = obj.get('Body').read()

            codec = self.compression_strategies.get(obj.get('ContentEncoding'))

            return codec.decode(data) if codec else data
        except self.client.exceptions.NoSuchKey:
            return None

    def __write_to_bucket(self, id: str, data: Any) -> None:
        content_encoding = ''

        if self.compression is not None:
            codec = self.compression_strategies[self.compression]
            compressed_data = codec.encode(data)

            # Check if compression is worth it, otherwise store the data uncompressed
            if len(compressed_data) <= len(data):
                data = compressed_data
                content_encoding = self.compression

        self.client.put_object(
            Key=self.__get_key_for_id(id),
            Body=data,
            Bucket=self.bucket_name,
            ContentEncoding=content_encoding,
        )

    def __delete_from_bucket(self, id: str) -> None:
        self.client.delete_object(
            Key=self.__get_key_for_id(id),
            Bucket=self.bucket_name,
        )
