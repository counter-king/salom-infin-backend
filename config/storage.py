import datetime
import getpass
import os
import mimetypes

import paramiko
from minio import Minio
from storages.backends.sftpstorage import SFTPStorage


class CustomSFTPStorage(SFTPStorage):
    def __init__(self, **settings):
        super().__init__(**settings)
        self.host = os.getenv('STORAGE_HOST')
        self.username = os.getenv('SFTP_USER')
        self.password = os.getenv('SFTP_PASSWORD')
        self.params = {
            'username': self.username,
            'password': self.password
        }
        self._sftp = None  # Initialize _sftp

    def _connect(self):
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # Disables host key checking

        # Ensure that known_host_file is not used
        self.known_host_file = None

        try:
            self._ssh.connect(self.host, **self.params)
            self._sftp = self._ssh.open_sftp()  # Initialize _sftp here
        except paramiko.AuthenticationException as e:
            if self.interactive and "password" not in self.params:
                if "username" not in self.params:
                    self.params["username"] = getpass.getuser()
                self.params["password"] = getpass.getpass()
                self._connect()
            else:
                raise paramiko.AuthenticationException(e)
        except paramiko.SSHException as e:
            raise paramiko.SSHException(f"Failed to connect to {self.host}: {e}")
        except Exception as e:
            raise Exception(f"Unexpected error: {e}")

    def _get_sftp(self):
        if self._sftp is None:
            self._connect()
        return self._sftp

    def _get(self, name):
        sftp = self._get_sftp()
        return sftp.open(name)


client = Minio(
    endpoint=os.getenv('MINIO_ENDPOINT', 'localhost:9000'),
    access_key=os.getenv('MINIO_ACCESS_KEY'),
    secret_key=os.getenv('MINIO_SECRET_KEY'),
    secure=False
)


def upload_file(file, module, object_name):
    """
    Uploads a file to the storage service of Minio
    """
    bucket_name = os.getenv('MINIO_BUCKET_NAME')
    year = datetime.datetime.now().year

    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)

    object_name = f'{module}/{year}/{object_name}'

    # Get Content Type
    if hasattr(file, 'content_type'):
        content_type = file.content_type
    else:
        content_type = 'application/octet-stream'

    # upload the file
    client.put_object(
        bucket_name, object_name, file, length=file.size,
        content_type=content_type
    )

    return object_name


def get_file_url(object_name):
    """
    Returns the URL of the file in the storage service
    """
    bucket_name = os.getenv('MINIO_BUCKET_NAME')
    return client.presigned_get_object(bucket_name, object_name)
