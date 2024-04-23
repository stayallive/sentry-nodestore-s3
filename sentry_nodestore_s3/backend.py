from __future__ import absolute_import

import boto3
from time import sleep
from datetime import datetime, timedelta
from typing import Any

from sentry.nodestore.base import NodeStorage
from sentry.nodestore.django import DjangoNodeStorage


def retry(tries=3, delay=0.1, max_delay=None, backoff=1, exceptions=Exception):
    """Retry Decorator with arguments
    Args:
        tries (int): The maximum number of attempts. Defaults to -1 (infinite)
        delay (int, optional): Delay between attempts (seconds). Defaults to 0
        max_delay (int, optional): The maximum value of delay (seconds). Defaults to None (Unlimited)
        backoff (int, optional): Multiplier applied to delay between attempts (seconds). Defaults to 1 (No backoff)
        exceptions (tuple, optional): Types of exceptions to catch. Defaults to Exception (all)
    """

    def retry_decorator(func):
        def retry_wrapper(*args, **kwargs):
            nonlocal tries, delay, max_delay, backoff, exceptions
            while tries:
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    tries -= 1

                    # Reached to maximum tries
                    if not tries:
                        raise

                    # Apply delay between requests
                    sleep(delay)

                    # Adjust the next delay according to backoff
                    delay *= backoff

                    # Adjust maximum delay duration
                    if max_delay is not None:
                        delay = min(delay, max_delay)

        return retry_wrapper

    return retry_decorator


class S3PassthroughDjangoNodeStorage(DjangoNodeStorage, NodeStorage):
    def __init__(
            self,
            bucket_name=None,
            endpoint_url=None,
            aws_access_key_id=None,
            aws_secret_access_key=None
    ):
        self.bucket_name = bucket_name
        self.client = boto3.client(
            service_name='s3',
            region_name='auto',
            endpoint_url=endpoint_url,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )

    def delete(self, id):
        super().delete(id)
        self.__delete_from_bucket(id)

    def _get_bytes(self, id: str) -> bytes | None:
        return self.__read_from_bucket(id) or super()._get_bytes(id)

    def _get_bytes_multi(self, id_list: list[str]) -> dict[str, bytes | None]:
        return {id: self._get_bytes(id) for id in id_list}

    def delete_multi(self, id_list: list[str]) -> None:
        super().delete_multi(id_list)
        for id in id_list:
            self.__delete_from_bucket(id)

    def _set_bytes(self, id: str, data: Any, ttl: timedelta | None = None) -> None:
        super()._set_bytes(id, data, ttl)
        self.__write_to_bucket(id, data)

    def cleanup(self, cutoff_timestamp: datetime) -> None:
        super().cleanup(cutoff_timestamp)
        # TODO: Setup cleanup on the bucket itself to automatically delete old objects

    def bootstrap(self) -> None:
        super().bootstrap()
        # TODO: Update the bucket policy to automatically delete old objects based on the retention of the instance

    @retry()
    def __read_from_bucket(self, id: str):
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=id)
            return response['Body'].read()
        except self.client.exceptions.NoSuchKey:
            return None

    @retry()
    def __write_to_bucket(self, id: str, data: Any):
        self.client.put_object(Bucket=self.bucket_name, Key=id, Body=data)

    @retry()
    def __delete_from_bucket(self, id: str):
        self.client.delete_object(Bucket=self.bucket_name, Key=id)
