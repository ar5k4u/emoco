#
# profile.py
#
# Copyright (c) 2026, Emoco
#
# ABOUT
# Uploads the saved roast profile (.alog file) of a roast to the Emoco Cloud
# so that the roast can be analysed per coffee on the web. The upload is
# queued in the regular plus upload queue to survive offline periods.
#
# LICENSE
# This program or module is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 2 of the License, or
# version 3 of the License, or (at your option) any later version. It is
# provided for educational purposes and is distributed in the hope that
# it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See
# the GNU General Public License for more details.

import os
import gzip
import time
import logging
from typing import Any, Final

import requests

from plus import config, connection, controller, util

_log: Final[logging.Logger] = logging.getLogger(__name__)


def profile_url(roast_id: str) -> str:
    return f'{config.roast_url}/{roast_id}/profile'


# True if the given queue item is a profile upload item
def is_profile_item(item: dict[str, Any]) -> bool:
    return 'file' in item and 'verb' in item and item['verb'] == 'PUT'


# queues the upload of the profile file at path for the roast with the given roast_id (roastUUID)
# called after a profile has been saved to disk; does nothing if plus is off, read-only or the queue is not running
def queue_profile_upload(path: str|None, roast_id: str|None) -> None:
    try:
        if path is None or roast_id is None or roast_id == '':
            return
        aw = config.app_window
        if aw is None or aw.plus_readonly or not controller.is_on():
            return
        if not os.path.isfile(path):
            _log.debug('-> profile file not found: %s', path)
            return
        import plus.queue # pylint: disable=import-outside-toplevel # avoid circular import
        import plus.sync # pylint: disable=import-outside-toplevel
        if plus.queue.queue is None:
            _log.debug('-> profile not queued as queue is not running')
            return
        # only profiles of roasts known to the server (under sync) or about to be uploaded are sent
        if plus.sync.getSync(roast_id) is None and not plus.queue.full_roast_in_queue(roast_id):
            _log.debug('-> profile not queued as roast %s is not registered for upload', roast_id)
            return
        plus.queue.queue.put({
            'url': profile_url(roast_id),
            'verb': 'PUT',
            'file': path,
            'data': {
                'roast_id': roast_id,
                'modified_at': util.epoch2ISO8601(time.time())
            }
        })
        _log.info('profile queued: %s', roast_id)
    except Exception as e:  # pylint: disable=broad-except
        _log.exception(e)


# uploads the profile file of the given queue item (gzip compressed) and returns the response
# raises on connection errors; HTTP errors are returned via the response status code
def upload(item: dict[str, Any]) -> requests.models.Response:
    path = item['file']
    with open(path, 'rb') as f:
        raw = f.read()
    if len(raw) > config.profile_upload_max_bytes:
        raise ValueError(f'profile file too large: {len(raw)} bytes')
    body = gzip.compress(raw)
    headers = connection.getHeaders(authorized=True, decompress=False)
    headers['Content-Type'] = 'application/octet-stream'
    headers['Content-Encoding'] = 'gzip'
    _log.debug('-> uploading profile %s (%s bytes gzipped)', path, len(body))
    r = requests.put(
        item['url'],
        headers=headers,
        data=body,
        verify=config.verify_ssl,
        timeout=(config.connect_timeout, config.read_timeout_max),
    )
    if r.status_code == 401 and connection.authentify():
        # token expired: re-authentified, we retry once
        headers = connection.getHeaders(authorized=True, decompress=False)
        headers['Content-Type'] = 'application/octet-stream'
        headers['Content-Encoding'] = 'gzip'
        r = requests.put(
            item['url'],
            headers=headers,
            data=body,
            verify=config.verify_ssl,
            timeout=(config.connect_timeout, config.read_timeout_max),
        )
    return r
