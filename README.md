# Sentry Node Store S3

This is a Sentry extension that allows you to use a S3 compatible API object store as a storage backend for the `nodestore` in self-hosted Sentry setups.

The ["Node Storage"](https://develop.sentry.dev/services/nodestore/) is a key/value store that is used to store data in Sentry. It's main usage is storing event data, but it can be used for other things as well.

This work is inspired by the [sentry-nodestore-s3](https://github.com/ewdurbin/sentry-s3-nodestore) extension by [ewdurbin](https://github.com/ewdurbin), but has been updated to work with the latest version of Sentry and has been extended with additional features.

## Features

- Store data in a S3 compatible API object store
- Allow read and/or write through to the Django (default) node storage for easy migration
- Support for zstd compression to save on bandwidth and storage costs

## Caveats

- This extension is not officially supported by Sentry
- The extension is tested up to Sentry 24.4.1 at this time
- This code is only tested with the [official self-hosted](https://github.com/getsentry/self-hosted) Sentry distribution and not with any third-party K8S or other flavors
- At this time the extension is actively used in production but _no guarantees are made_ about it's functionality or performance (performance is also highly dependent on your object storage provider)

## Object Storage Provider Considerations

- The usage pattern of the `nodestore` is very write heavy which if you are using S3 or other compatible object stores, you may incur additional costs if you pay per request. It is advised to use a object storage provider where you pay only for storage and/or bandwidth and not per request/operation
- You will have to setup lifecycle policies on your bucket to remove old data (older than `SENTRY_EVENT_RETENTION_DAYS`)
- Setup your bucket to not allow public access 

## Installation

First you will need to setup a bucket in your S3 compatible object store. How to do this is out of scope but make sure you setup a lifecycle rule to remove old data as mentioned in the considerations.

After that you will need to clone or copy the contents of this repo to where you cloned the Sentry self-hosted repo. Clone or copy the content inside the `sentry` directory (next to the `sentry.conf.py` file).

Your directory structure should similar to this:

```
self-hosted/
|-- sentry/
│   ├── sentry-nodestore-s3/ (this repo)
│   │   ├── sentry_nodestore_s3/
│   │   │   ├── __init__.py
│   │   │   ├── backend.py
│   │   ├── setup.py
│   ├── sentry.conf.py
├── install.sh
```

You will need to also create the `enhance-image.sh` file to install the extension, if you already have the file merge their contents.

```bash
#!/bin/bash

# this path is the path inside the Docker container, not in your local filesystem
pip install /usr/src/sentry/sentry-nodestore-s3
```

After that you will need to add the following to your `sentry.conf.py` file:

```python
###########
# Storage #
###########

SENTRY_NODESTORE = "sentry_nodestore_s3.S3PassthroughDjangoNodeStorage"
SENTRY_NODESTORE_OPTIONS = {
    "delete_through": False,     # delete through to the Django nodestore (delete object from S3 and Django)
    "write_through": False,      # write through to the Django nodestore (duplicate writes to S3 and Django)
    "read_through": False,       # read through to the Django nodestore (if object not found in S3)
    "compression": True,         # compress data with zstd (highly recommended to leave enabled)
    "region_name": "nl-ams",
    "bucket_path": "nodestore",  # path inside the bucket, recommended to leave as is (removing it will make most object store web UI's grind to a halt accessing the bucket
    "bucket_name": "nodestore",
    "endpoint_url": "https://s3.nl-ams.scw.cloud",
    "retry_attempts": 3,         # retry attempts for S3 operations
    "aws_access_key_id": "",
    "aws_secret_access_key": "",
}
```

In the example above I am using Scaleway's S3 compatible object store in their Amsterdam (`nl-ams`) region. You will need to replace the values with those valid for your own provider.

Take note of the `delete_through`, `write_through` and `read_through` options. If you are setting up a new instance keep them on `False` but if you are migrating to S3 you will want to enable `delete_through` and `read_through` for the duration of `SENTRY_EVENT_RETENTION_DAYS`. If you are just testing also enable `write_through` to duplicate writes to S3 and Django allowing you to revert to the Django nodestore at any time without losing data.

After this you will need to re-run `install.sh` as you normally would when installing/updating Sentry.

## Security Vulnerabilities

If you discover a security vulnerability within this repository, please send an e-mail to Alex Bouma at `alex+security@bouma.me`. All security vulnerabilities will be swiftly addressed.

## License

The Sentry Node Store S3 plugin is open-sourced software licensed under the [MIT license](http://opensource.org/licenses/MIT).
