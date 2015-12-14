#! -*- coding: utf-8; mode: python -*-
"""
ago.py: interact with an ArcGIS Portal instance
"""
import arcpy
import json
import time
import datetime
import mimetypes
import gzip
import random
import string
import getpass
import sys
import os
from io import BytesIO
import codecs
import uuid

try:
    import http.client as client
    import urllib.parse as parse
    from urllib.request import urlopen as urlopen
    from urllib.request import Request as request
    from urllib.parse import urlencode as encode
# py2
except ImportError:
    import httplib as client
    from urllib2 import urlparse as parse
    from urllib2 import urlopen as urlopen
    from urllib2 import Request as request
    from urllib import urlencode as encode
    unicode = str

# Valid package types on portal
itemTypes = {".LPK": "Layer Package",
             ".MPK": "Map Package",
             ".TPK": "Tile Package",
             ".GPK": "Geoprocessing Package",
             ".RPK": "Rule Package",
             ".GCPK": "Locator Package",
             ".PPKX": "Project Package",
             ".APTX": "Project Template",
             ".MMPK": "Mobile Map Package"
             }

class MultipartFormdataEncoder(object):
    """
    USAGE:   request_headers, request_data = MultipartFormdataEncoder().encodeForm(params, files)
    Inputs:
       params = {"f": "json", "token": token, "type": item_type,
                 "title": title, "tags": tags, "description": description}
       files = {"file": {"filename": "some_file.sd", "content": content}}
           Note:  content = open(file_path, "rb").read()
    """

    def __init__(self):
        self.boundary = uuid.uuid4().hex
        self.content_type = {"Content-Type": "multipart/form-data; boundary={}".format(self.boundary)}

    @classmethod
    def u(cls, s):
        if sys.hexversion < 0x03000000 and isinstance(s, str):
            s = s.decode('utf-8')
        if sys.hexversion >= 0x03000000 and isinstance(s, bytes):
            s = s.decode('utf-8')
        return s

    def iter(self, fields, files):
        """
        Yield bytes for body. See class description for usage.
        """
        encoder = codecs.getencoder('utf-8')
        for key, value in fields.items():
            yield encoder('--{}\r\n'.format(self.boundary))
            yield encoder(self.u('Content-Disposition: form-data; name="{}"\r\n').format(key))
            yield encoder('\r\n')
            if isinstance(value, int) or isinstance(value, float):
                value = str(value)
            yield encoder(self.u(value))
            yield encoder('\r\n')

        for key, value in files.items():
            if "filename" in value:
                filename = value.get("filename")
                yield encoder('--{}\r\n'.format(self.boundary))
                yield encoder(self.u('Content-Disposition: form-data; name="{}"; filename="{}"\r\n').format(key, filename))
                yield encoder('Content-Type: {}\r\n'.format(mimetypes.guess_type(filename)[0] or 'application/octet-stream'))
            yield encoder('\r\n')
            if "content" in value:
                buff = value.get("content")
                yield (buff, len(buff))
            yield encoder('\r\n')

        yield encoder('--{}--\r\n'.format(self.boundary))

    def encodeForm(self, fields, files):
        body = BytesIO()
        for chunk, chunk_len in self.iter(fields, files):
            body.write(chunk)
        self.content_type["Content-Length"] = str(len(body.getvalue()))
        return self.content_type, body.getvalue()

class AGOLHelper(object):
    """
    Interact with an ArcGIS Portal instance, such as ArcGIS Online. Must be
    initialized with either the login() method, or by reusing an existing
    OAuth token via token_login(). Covers approximately 1/3 of the complete
    API, primarily focused on the common operations around uploading and
    managing services and web maps.
    """

    def __init__(self, portal_url=None, token=None, debug=False):
        if portal_url is None:
            self.portal_url = arcpy.GetActivePortalURL()
        else:
            self.portal_url = portal_url
        # in the absence of information, default to HTTP
        self.protocol = 'https'
        self.is_arcgis_online = False
        url_parts = self._parse_url(self.portal_url)
        if url_parts:
            if url_parts.scheme:
                self.protocol = url_parts.scheme
            self.host = self._normalize_host_url(url_parts)
            if url_parts.netloc == 'www.arcgis.com':
                self.is_arcgis_online = True

        else:
            arcpy.AddError(NO_PORTAL_URL_MSG)
            sys.exit()
        self.base_url = '{}://{}/sharing/rest'.format(self.protocol, self.host)
        self.secure_url = 'https://{}/sharing/rest'.format(self.host)

        self.token = token
        self.debug = debug

        self.headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'User-Agent': ('ago.py -- ArcGIS portal module 0.1')
        }
        self.parameters = None
        self.portal_name = None
        self.portal_info = {}
        self.username = None
        self.login_method = None

    def login(self, username=None, password=None, repeat=None):
        """
        Get a sign-in token from provided credentials.

        Arguments:
            username -- user to sign in with
            password -- password for user (default: use getpass)

        Returns:
            None
        """

        if username:
            self.username = username
        else:
            arcpy.AddError("Expected user name. None given.")
            return
        if password is None:
            self._password = getpass.getpass()
        else:
            self._password = password

        token_url = '{}/generateToken?'.format(self.secure_url)
        token_parameters = {
            'username': username,
            'password': self._password,
            'referer': "http://maps.esri.com",
            'expiration': 600,
            'f': 'json'
        }
        token_response = self.url_request(
            token_url, token_parameters, 'POST', repeat=repeat)

        if token_response and 'token' in token_response:
            self.token = token_response['token']
            self.expiration = datetime.datetime.fromtimestamp(
                token_response['expires'] / 1000) - datetime.timedelta(seconds=1)

            # should we use SSL for handling traffic?
            if 'ssl' in token_response:
                if token_response['ssl']:
                    self.protocol = 'https'
            else:
                self.protocol = 'http'

            # update base information with token
            self.information()
            self.login_method = 'password'
        else:
            arcpy.AddError("Unable to get signin token.")
        return

    def token_login(self):
        """
        Get a sign-in token generated from ArcPy.

        Arguments:
            None

        Returns:
            None
        """
        # NOTE side-effects
        token_response = arcpy.GetSigninToken()
        if token_response and 'token' in token_response:
            self.token = token_response['token']
            self.expiration = datetime.datetime.fromtimestamp(
                token_response['expires']) - datetime.timedelta(seconds=1)

            if self.debug:
                msg = 'Received token starting with ' + \
                      '"{}", valid for {} minutes.'.format(
                          self.token[0:10], self.valid_for)
                arcpy.AddMessage(msg)

            # update base information with token
            self.information()
            self.login_method = 'token'
        else:
            arcpy.AddError("Unable to get signin token.")
        return

    @property
    def valid_for(self):
        """
        Length the current token is valid for, in minutes.

        Returns:
            An integer of minutes token remains valid
        """
        valid = False
        if self.expiration and isinstance(self.expiration, datetime.datetime):
            valid = (self.expiration - datetime.datetime.now()).seconds / 60
        return valid

    def information(self):
        """
        Get portal 'self' information.

        Arguments:
            None

        Returns:
            A dictionary returned from portals/self.
        """

        # NOTE side-effects; do separately
        url = '{}/portals/self'.format(self.base_url)

        self.parameters = {
            'token': self.token,
            'f': 'json'
        }

        portal_info = self.url_request(url, self.parameters)
        self.portal_info = portal_info
        self.portal_name = portal_info['portalName']

        url = '{}/community/self'.format(self.base_url)
        user_info = self.url_request(url, self.parameters)
        self.username = user_info['username']

        return self.portal_info

    def random_string(self, length):
        """
        Generate a random string of ASCII letters.

        Arguments:
            length = number of characters

        Returns:
            random string
        """
        alpha = string.ascii_letters
        return ''.join(random.choice(alpha) for ii in range(length + 1))

    def encode_multipart_data(self, data, files):
        """
        Create multipart boundaries between file streams.

        Arguments:
            data -- input data
            files -- input files

        Returns:
            A tuple containing response -- (body, headers)
        """
        boundary = self.random_string(30)

        def get_content_type(filename):
            """ Try to determine content type based on file extension."""
            return mimetypes.guess_type(filename)[0] or 'application/octet-stream'

        def encode_field(field_name):
            """ Encode fields using multipart specification."""
            return('--' + boundary,
                   'Content-Disposition: form-data; name="%s"' % field_name,
                   '', str(data[field_name]))

        def encode_file(field_name):
            """ Encode file data using multipart specification."""
            filename = str(files[field_name])

            return('--' + boundary,
                   'Content-Disposition: form-data;'
                   'name="{}"; filename="{}"'.format(field_name, filename),
                   'Content-Type: %s' % get_content_type(filename),
                   '', open(filename, 'rb').read())

        lines = []
        for name in data:
            lines.extend(encode_field(name))
        for name in files:
            lines.extend(encode_file(name))
        lines.extend(('--%s--' % boundary, ''))
        body = '\r\n'.join(lines)

        headers = {
            'content-type': 'multipart/form-data; boundary=' + boundary,
            'content-length': str(len(body))
        }

        return body, headers


    def item(self, item_id=None):
        """
        Get back information about a particular item. Must have read
        access to the item requested.

        Arguments:
            item_id: the portal id of the desired item.

        Returns:
            Dictionary from item response.
        """
        results = {}
        if item_id:
            url = '{}/content/items/{}'.format(self.base_url, item_id)
            parameters = {
                'token': self.token,
                'f': 'json'
            }
            results = self.url_request(url, parameters)
        return results


    def share_items(self, groups=None, everyone=False, org=False, items=None):
        """
        Shares one or more items with the specified groups. Can only share
        items with groups the user belongs to. Can also share with
        the users' current organization, and the public.

        Arguments:
            groups -- a list of group IDs to share items with
            everyone -- publicly share the item (default: False)
            org -- share with the users' organization (default: False)
            items -- a list of item IDs to update sharing properties on

        Returns:
            A dictionary of JSON objects, one per item containing the item,
            whether sharing was successful, any groups sharing failed with,
            and any errors.
        """
        if (groups is None and not everyone and not org) or not items:
            if self.debug:
                arcpy.AddWarning("Invalid sharing options set.")
            return

        # If shared with everyone, have to share with Org as well
        if everyone:
            org = True

        url = '{}/content/users/{}/shareItems'.format(
            self.base_url, self.username)

        parameters = {
            'token': self.token,
            'f': 'json',
            'everyone': everyone,
            'org': org,
            'items': ','.join(map(str, items))
        }
        # sharing with specific groups is optional
        if groups:
            parameters['groups'] = ','.join(map(str, groups))

        sharing_response = self.url_request(url, parameters, 'POST')
        if self.debug:
            msg = "Sharing items, using {} with parameters {}, got {}".format(
                url, parameters, sharing_response)
            arcpy.AddMessage(msg)

        return sharing_response

    def search(self, title=None, item_type=None, group=None,
               owner=None, item_id=None, repeat=None, num=10, id_only=True):
        """
        Search for items, a partial implementation of the
        search operation of the ArcGIS REST API. Requires one of:
          title, item_type, group, owner.

        Arguments:
            title -- item title
            item_type -- item type
            group -- item group
            owner -- username of item owner
            item_id -- item id
            repeat -- retry the search, up to this number of times (default: None)
            num -- number of results (default: 10)
            id_only -- return only IDs of results. If False, will return
                       full JSON results. (default: True)

        Returns:
            A list of search results item ids.

        """

        query_types = {
            'title': title,
            'type': item_type,
            'group': group,
            'owner': owner,
            'id': item_id
        }

        query_parts = []
        for (label, value) in list(query_types.items()):
            if value:
                query_parts.append('{}: "{}"'.format(label, value))

        if len(query_parts) == 0:
            return
        elif len(query_parts) == 1:
            query = query_parts[0]
        else:
            query = " AND ".join(query_parts)

        url = '{}/search'.format(self.base_url)
        parameters = {
            'token': self.token,
            'f': 'json',
            'num': num,
            'q': query
        }
        if self.debug:
            arcpy.AddMessage("Searching for '{}'".format(query))

        response_info = self.url_request(url, parameters)
        results = []

        if response_info and 'results' in response_info:
            if response_info['total'] > 0:
                for item in response_info['results']:
                    if 'id' in item:
                        if id_only:
                            results.append(item['id'])
                        else:
                            results.append(item)
        if self.debug:
            if results:
                arcpy.AddMessage("Got results! Found items: {}".format(results))
            else:
                arcpy.AddMessage("No results found.")

        # occasional timing conflicts are happening; repeat search until we
        # can continue -- the result should be empty since we just deleted it.
        if repeat and not results:
            repeat -= 1
            if repeat <= 0:
                return

            time.sleep(1)

            results = self.search(
                title=title, item_type=item_type, group=group, owner=owner,
                item_id=item_id, repeat=repeat, num=num, id_only=id_only)

        return results

    def user(self, username=None):
        """
        A user resource representing a registered user of the portal.

        Arguments:
            username -- user of interest

        Returns:
            A dictionary of the JSON response.

        """
        if username is None:
            username = self.username

        url = '{}/community/users/{}'.format(self.base_url, username)
        parameters = {
            'f': 'json',
            'token': self.token
        }
        return self.url_request(url, parameters)


    def list_groups(self, username=None):
        """
        List users' groups.

        Returns:
            A dictionary of group titles to ids.
        """
        groups = {}

        if username is None:
            username = self.username

        groups_request = self.user(username)['groups']
        for group in groups_request:
            groups[group['title']] = group['id']

        return groups

    def add_item(self, file2Upload, username=None, itemtype=None, params=None):
        """
        Adds an item to the portal.
        All items are added as multipart. Once the item is added, Add Part will be called.

        Returns:
            The response/itemID of the item added.
        """
        if username is None:
            username = self.username

        url = '{}/content/users/{}/addItem'.format(self.base_url, username)
        parameters = {'multipart': 'true',
                      'filename': file2Upload,
                      'token': self.token,
                      'f': 'json'}
        if params:
            parameters.update(params)

        if itemtype:
            parameters['type'] = itemtype
        else:
            try:
                itemtype = itemTypes[file2Upload.upper()]
            except KeyError:
                arcpy.AddError("Unable to uplaod file: {0}, unknown type".format(file2Upload))
                return

        addItemRes = self.url_request(url, parameters, "POST", "", {'filename': file2Upload})

        addPartRes = self._add_part(file2Upload, addItemRes['id'], itemtype)

        return addPartRes

    def _add_part(self, file2Upload, itemID, uploadType=None):

        def read_in_chunks(file_object, chunk_size=10000000):
            """Generate file chunks of 10mb"""
            while True:
                data = file_object.read(chunk_size)
                if not data:
                    break
                yield data

        url = '{}/content/users/{}/items/{}/addPart'.format(self.base_url, self.username, itemID)

        f = open(file2Upload, 'rb')

        for part_num, piece in enumerate(read_in_chunks(f), start=1):
            title = os.path.basename(file2Upload)
            files = {"file": {"filename": file2Upload, "content": piece}}
            params = {"f": "json",
                      "token": self.token,
                      'partNum': part_num,
                      'title': title,
                      'itemType': 'file',
                      'type': uploadType
                      }
            request_headers, request_data = MultipartFormdataEncoder().encodeForm(params, files)
            resp = self.url_request(url, request_data, "MULTIPART", request_headers)

        f.close()

        return resp

    def item_status(self, itemID, username=None):
        """
        Gets the status of an item.

        Returns:
            The item's status. (partial | processing | failed | completed)
        """
        if username is None:
            username = self.username

        url = '{}/content/users/{}/items/{}/status'.format(self.base_url, username, itemID)
        parameters = {'token': self.token,
                      'f': 'json'}

        return self.url_request(url, parameters)

    def commit(self, itemID, username=None):
        """
        Commits an item that was uploaded as multipart

        Returns:
            Result of calling commit. (success: true| false)
        """
        if username is None:
            username = self.username

        url = '{}/content/users/{}/items/{}/commit'.format(self.base_url, username, itemID)
        parameters = {'token': self.token,
                      'f': 'json'}

        return self.url_request(url, parameters)

    def update_item(self, itemID, metadata, username=None):
        """
        Updates metadata parts of an item.
        Metadata expected as a tuple

        Returns:
            Result of calling update. (success: true| false)
        """
        if username is None:
            username = self.username

        url = "{}/content/users/{}/items/{}/update".format(self.base_url, username, itemID)
        parameters = {'description' : metadata[0],
                      'snippet' : metadata[0],
                      'tags': metadata[1],
                      'accessInformation' : metadata[2],
                      'token' : self.token,
                      'f': 'json'}

        return self.url_request(url, parameters, 'POST')


    def url_request(self, in_url, request_parameters, request_type='GET',
                    additional_headers=None, files=None, repeat=None):
        """
        Make a request to the portal, provided a portal URL
        and request parameters, returns portal response.

        Arguments:
            in_url -- portal url
            request_parameters -- dictionary of request parameters.
            request_type -- HTTP verb (default: GET)
            additional_headers -- any headers to pass along with the request.
            files -- any files to send.
            repeat -- repeat the request up to this number of times.

        Returns:
            dictionary of response from portal instance.
        """

        if request_type == 'GET':
            req = request('?'.join((in_url, encode(request_parameters))))
        elif request_type == 'MULTIPART':
            req = request(in_url, request_parameters)
        elif request_type == "WEBMAP":
            if files:
                req = request(in_url,
                                      *self.encode_multipart_data(
                                          request_parameters, files))
            else:
                arcpy.AddWarning("Multipart request made, but no files provided.")
                return
        else:
            req = request(in_url, encode(request_parameters).encode('UTF-8'), self.headers)

        if additional_headers:
            for key, value in list(additional_headers.items()):
                req.add_header(key, value)
        req.add_header('Accept-encoding', 'gzip')
        response = urlopen(req)

        if response.info().get('Content-Encoding') == 'gzip':
            buf = BytesIO(response.read())
            with gzip.GzipFile(fileobj=buf) as gzip_file:
                response_bytes = gzip_file.read()
        else:
            response_bytes = response.read()

        response_text = response_bytes.decode('UTF-8')

        # Check that data returned is not an error object
        # if not self.assert_json_success(response_text):
        #     return

        # occasional timing conflicts; repeat until we get back a valid response.
        response_json = json.loads(response_text)

        if not response_json or "error" in response_json:
            rerun = False
            if repeat > 0:
                repeat -= 1
                rerun = True

            # token has expired. Revalidate, then rerun request
            if response_json['error']['code'] is 498:
                if self.debug:
                    arcpy.AddWarning("token invalid, retrying.")
                if self.login_method is 'token':
                    # regenerate the token if we're logged in via the application
                    self.token_login()
                else:
                    self.login(self.username, self._password, repeat=0)

                # after regenerating token, we should have something long-lived
                if not self.token or self.valid_for < 5:
                    arcpy.AddError("Unable to get signin token.")
                    return
                rerun = True

            if rerun:
                time.sleep(2)
                response_json = self.url_request(
                    in_url, request_parameters, request_type,
                    additional_headers, files, repeat)

        return response_json


    def assert_json_success(self, data):
        """A function that checks that the input JSON object
            is not an error object."""
        success = False
        obj = json.loads(data)
        if 'status' in obj and obj['status'] == "error":
            arcpy.AddWarning("{} {}".format("JSON object returned an error.", str(obj)))
        elif 'error' in obj:
            err = obj['error']
            # format the error message
            if 'messageCode' in err:
                code = err['messageCode']
            elif 'code' in err:
                code = err['code']
            else:
                code = "No code provided."

            msg = "Portal error: {}: {}".format(err['message'], code)
            if 'details' in err and err['details']:
                details = []
                for detail in err['details']:
                    # only use unique detail messages
                    if detail is not err['message']:
                        details.append(detail)
                if details:
                    msg += ". Details: {}".format("\n".join(details))
            arcpy.AddWarning(msg)
        else:
            success = True
        return success


    def _parse_url(self, url=None):
        """ Parse a url into components."""
        results = None
        if url:
            results = parse.urlparse(url)
        return results

    def _normalize_host_url(self, parse_result):
        """ Normalize a hostname to include just the validated
            location and path."""
        host_url = parse_result.netloc
        if parse_result.path:
            path = parse_result.path
            if path[-1] == '/':
                path = path[:-1]
            host_url += path
        return host_url
