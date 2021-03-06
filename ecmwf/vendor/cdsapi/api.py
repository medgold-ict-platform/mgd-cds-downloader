# (C) Copyright 2018 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation nor
# does it submit to any jurisdiction.

from __future__ import absolute_import, division, print_function, unicode_literals

import json
import time
import os
import logging

import requests


def bytes_to_string(n):
    u = ['', 'K', 'M', 'G', 'T', 'P']
    i = 0
    while n >= 1024:
        n /= 1024.0
        i += 1
    return '%g%s' % (int(n * 10 + 0.5) / 10.0, u[i])


def read_config(path):
    config = {}
    with open(path) as f:
        for l in f.readlines():
            if ':' in l:
                k, v = l.strip().split(':', 1)
                if k in ('url', 'key', 'verify'):
                    config[k] = v.strip()
    return config


class Result(object):

    def __init__(self, client, reply):

        self.reply = reply

        self._url = client.url

        self.session = client.session
        self.robust = client.robust
        self.verify = client.verify
        self.cleanup = client.delete

        self.debug = client.debug
        self.info = client.info
        self.warning = client.warning
        self.error = client.error

        self._deleted = False

    def _download(self, url, size, target):

        if target is None:
            target = url.split('/')[-1]

        self.info("Downloading %s to %s (%s)", url, target, bytes_to_string(size))
        start = time.time()

        r = self.robust(requests.get)(url, stream=True, verify=self.verify)
        try:
            r.raise_for_status()

            total = 0
            with open(target, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)
        finally:
            r.close()

        assert total == size

        elapsed = time.time() - start
        if elapsed:
            self.info("Download rate %s/s", bytes_to_string(size / elapsed))

        return target

    def download(self, target=None):
        return self._download(self.location,
                              self.content_length,
                              target)

    @property
    def content_length(self):
        return int(self.reply['content_length'])

    @property
    def location(self):
        return self.reply['location']

    @property
    def content_type(self):
        return self.reply['content_type']

    def __repr__(self):
        return "Result(content_length=%s,content_type=%s,location=%s)" % (self.content_length,
                                                                          self.content_type,
                                                                          self.location)

    def check(self):
        self.debug("HEAD %s", self.reply['location'])
        metadata = self.robust(self.session.head)(self.reply['location'],
                                                  verify=self.verify)
        metadata.raise_for_status()
        self.debug(metadata.headers)
        return metadata

    def delete(self):

        if self._deleted:
            return

        if 'request_id' in self.reply:
            rid = self.reply['request_id']

            task_url = '%s/tasks/%s' % (self._url, rid)
            self.debug("DELETE %s", task_url)

            delete = self.session.delete(task_url, verify=self.verify)
            self.debug("DELETE returns %s %s", delete.status_code, delete.reason)

            try:
                delete.raise_for_status()
            except Exception:
                self.warning("DELETE %s returns %s %s",
                             task_url, delete.status_code, delete.reason)

            self._deleted = True

    def __del__(self):
        try:
            if self.cleanup:
                self.delete()
        except Exception as e:
            print(e)


class Client(object):

    logger = logging.getLogger('cdsapi')

    def __init__(self,
                 url=os.environ.get('CDSAPI_URL'),
                 key=os.environ.get('CDSAPI_KEY'),
                 quiet=False,
                 debug=False,
                 verify=None,
                 timeout=None,
                 full_stack=False,
                 delete=True,
                 retry_max=500,
                 sleep_max=120,
                 info_callback=None,
                 warning_callback=None,
                 error_callback=None,
                 debug_callback=None,
                 ):

        if not quiet:

            if debug:
                level = logging.DEBUG
            else:
                level = logging.INFO

            logging.basicConfig(level=level,
                                format='%(asctime)s %(levelname)s %(message)s')

        dotrc = os.environ.get('CDSAPI_RC', os.path.expanduser('/var/task/.cdsapirc'))

        if url is None or key is None:
            if os.path.exists(dotrc):
                config = read_config(dotrc)

                if key is None:
                    key = config.get('key')

                if url is None:
                    url = config.get('url')

                if verify is None:
                    verify = int(config.get('verify', 1))

        if url is None or key is None or key is None:
            raise Exception('Missing/incomplete configuration file: %s' % (dotrc))

        self.url = url
        self.key = key

        self.quiet = quiet
        self.verify = True if verify else False
        self.timeout = timeout
        self.sleep_max = sleep_max
        self.retry_max = retry_max
        self.full_stack = full_stack
        self.delete = delete
        self.last_state = None

        self.debug_callback = debug_callback
        self.warning_callback = warning_callback
        self.info_callback = info_callback
        self.error_callback = error_callback

        self.session = requests.Session()
        self.session.auth = tuple(self.key.split(':', 2))

        self.debug("CDSAPI %s", dict(url=self.url,
                                     key=self.key,
                                     quiet=self.quiet,
                                     verify=self.verify,
                                     timeout=self.timeout,
                                     sleep_max=self.sleep_max,
                                     retry_max=self.retry_max,
                                     full_stack=self.full_stack,
                                     delete=self.delete
                                     ))

    def retrieve(self, name, request, target=None):
        result = self._api('%s/resources/%s' % (self.url, name), request)
        if target is not None:
            result.download(target)
        return result

    def _api(self, url, request):

        session = self.session

        self.info("Sending request to %s", url)
        self.debug("POST %s %s", url, json.dumps(request))

        result = self.robust(session.post)(url, json=request, verify=self.verify)
        reply = None

        try:
            result.raise_for_status()
            reply = result.json()
        except Exception:

            if reply is None:
                try:
                    reply = result.json()
                except Exception:
                    reply = dict(message=result.text)

            self.debug(json.dumps(reply))

            if 'message' in reply:
                error = reply['message']

                if 'context' in reply and 'required_terms' in reply['context']:
                    e = [error]
                    for t in reply['context']['required_terms']:
                        e.append("To access this resource, you first need to accept the terms"
                                 "of '%s' at %s" % (t['title'], t['url']))
                    error = '. '.join(e)
                raise Exception(error)
            else:
                raise

        sleep = 1
        start = time.time()

        while True:

            self.debug("REPLY %s", reply)

            if reply['state'] != self.last_state:
                self.info("Request is %s" % (reply['state'],))
                self.last_state = reply['state']

            if reply['state'] == 'completed':
                self.debug("Done")
                return Result(self, reply)

            if reply['state'] in ('queued', 'running'):
                rid = reply['request_id']

                if self.timeout and (time.time() - start > self.timeout):
                    raise Exception('TIMEOUT')

                self.debug("Request ID is %s, sleep %s", rid, sleep)
                time.sleep(sleep)
                sleep *= 1.5
                if sleep > self.sleep_max:
                    sleep = self.sleep_max

                task_url = '%s/tasks/%s' % (self.url, rid)
                self.debug("GET %s", task_url)

                result = self.robust(session.get)(task_url, verify=self.verify)
                result.raise_for_status()
                reply = result.json()
                continue

            if reply['state'] in ('failed',):
                self.error("Message: %s", reply['error'].get('message'))
                self.error("Reason:  %s", reply['error'].get('reason'))
                for n in reply.get('error', {}).get('context', {}).get('traceback', '').split('\n'):
                    if n.strip() == '' and not self.full_stack:
                        break
                    self.error("  %s", n)
                raise Exception("%s. %s." % (reply['error'].get('message'), reply['error'].get('reason')))

            raise Exception('Unknown API state [%s]' % (reply['state'],))

    def info(self, *args, **kwargs):
        if self.info_callback:
            self.info_callback(*args, **kwargs)
        else:
            self.logger.info(*args, **kwargs)

    def warning(self, *args, **kwargs):
        if self.warning_callback:
            self.warning_callback(*args, **kwargs)
        else:
            self.logger.warning(*args, **kwargs)

    def error(self, *args, **kwargs):
        if self.error_callback:
            self.error_callback(*args, **kwargs)
        else:
            self.logger.error(*args, **kwargs)

    def debug(self, *args, **kwargs):
        if self.debug_callback:
            self.debug_callback(*args, **kwargs)
        else:
            self.logger.debug(*args, **kwargs)

    def robust(self, call):

        def retriable(code, reason):

            if code in [requests.codes.internal_server_error,
                        requests.codes.bad_gateway,
                        requests.codes.service_unavailable,
                        requests.codes.gateway_timeout,
                        requests.codes.too_many_requests,
                        requests.codes.request_timeout]:
                return True

            return False

        def wrapped(*args, **kwargs):
            tries = 0
            while tries < self.retry_max:
                try:
                    r = call(*args, **kwargs)
                except requests.exceptions.ConnectionError as e:
                    r = None
                    self.warning("Recovering from connection error [%s], attemx ps %s of %s",
                                 e, tries, self.retry_max)

                if r is not None:
                    if not retriable(r.status_code, r.reason):
                        return r
                    self.warning("Recovering from HTTP error [%s %s], attemps %s of %s",
                                 r.status_code, r.reason, tries, self.retry_max)

                tries += 1

                self.warning("Retrying in %s seconds", self.sleep_max)
                time.sleep(self.sleep_max)

        return wrapped
