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
import shutil

try:
    import http.client as client
    import urllib.parse as parse
    from urllib.request import urlopen as urlopen
    from urllib.request import Request as request
    from urllib.request import HTTPError, URLError
    from urllib.parse import urlencode as encode
# py2
except ImportError:
    import httplib as client
    from urllib2 import urlparse as parse
    from urllib2 import urlopen as urlopen
    from urllib2 import Request as request
    from urllib2 import HTTPError, URLError
    from urllib import urlencode as encode
    unicode = str

# Valid package types on portal
ITEM_TYPES = {
    ".LPK": "Layer Package",
    ".LPKX": "Layer Package",
    ".MPK": "Map Package",
    ".MPKX": "Map Package",
    ".GPK": "Geoprocessing Package",
    ".GPKX": "Geoprocessing Package",
    ".RPK": "Rule Package",
    ".GCPK": "Locator Package",
    ".PPKX": "Project Package",
    ".APTX": "Project Template",
    ".TPK": "Tile Package",
    ".MMPK": "Mobile Map Package",
    ".VTPK": "Vector Tile Package"
}


class MultipartFormdataEncoder(object):
    """
    Usage:   request_headers, request_data =
                 MultipartFormdataEncoder().encodeForm(params, files)
    Inputs:
       params = {"f": "json", "token": token, "type": item_type,
                 "title": title, "tags": tags, "description": description}
       files = {"file": {"filename": "some_file.sd", "content": content}}
           Note:  content = open(file_path, "rb").read()
    """

    def __init__(self):
        self.boundary = uuid.uuid4().hex
        self.content_type = {
            "Content-Type": "multipart/form-data; boundary={}".format(self.boundary)
        }

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
            yield encoder(
                self.u('Content-Disposition: form-data; name="{}"\r\n').format(key))
            yield encoder('\r\n')
            if isinstance(value, int) or isinstance(value, float):
                value = str(value)
            yield encoder(self.u(value))
            yield encoder('\r\n')

        for key, value in files.items():
            if "filename" in value:
                filename = value.get("filename")
                content_disp = 'Content-Disposition: form-data;name=' + \
                               '"{}"; filename="{}"\r\n'.format(key, filename)
                content_type = 'Content-Type: {}\r\n'.format(
                    mimetypes.guess_type(filename)[0] or 'application/octet-stream')
                yield encoder('--{}\r\n'.format(self.boundary))
                yield encoder(content_disp)
                yield encoder(content_type)
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
                self.protocol = 'https'

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

        self.portal_name = None
        self.portal_info = {}
        self.username = None
        self.login_method = None
        self.expiration = None
        self._password = None

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
        }
        token_response = self.url_request(
            token_url, token_parameters, 'POST', repeat=repeat)

        if token_response and 'token' in token_response:
            self.token = token_response['token']
            self.expiration = datetime.datetime.fromtimestamp(
                token_response['expires'] / 1000) - datetime.timedelta(seconds=1)

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

        portal_info = self.url_request(url)
        self.portal_info = portal_info
        self.portal_name = portal_info['portalName']

        url = '{}/community/self'.format(self.base_url)
        user_info = self.url_request(url)
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

    def list_folders(self):
        """
        List available user folders.

        Returns:
            A dictionary of folder titles to ids.
        """

        folders = {}

        folder_request = self.user_content()['folders']
        for folder in folder_request:
            folders[folder['title']] = folder['id']

        return folders

    def create_folder(self, name):
        """
        Create a folder item.
        property to the created folder.
        Arguments:
            name -- folder name to create
        Returns:
            folder item id.
        """
        folder = None
        url = '{}/content/users/{}/createFolder'.format(
            self.base_url, self.username)

        parameters = {'title': name}
        response = self.url_request(url, parameters, 'POST')

        if response is not None and 'folder' in response:
            folder = response['folder']['id']

        return folder

    def item(self, item_id=None, repeat=None):
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
            results = self.url_request(url, repeat=repeat)
        return results

    def move_items(self, target_folder_id, items):
        """
        Move items to a target folder.

        Arguments:
            target_folder_id: folder id to move items to
            items: list of one or more item ids to move

        Returns:
            None
        """
        # Test if we have a None object somewhere
        # This could potentially be the case if one of the previous
        # portal responses was not successful.
        if None in items:
            arcpy.AddError(EMPTY_ITEM_MSG)
            return

        url = '{}/content/users/{}/moveItems'.format(
            self.base_url, self.username)

        parameters = {
            'folder': target_folder_id,
            'items': ','.join(map(str, items))
        }

        move_response = self.url_request(url, parameters, request_type='POST')
        if self.debug:
            msg = "Moving items, using {} with parameters {}, got {}".format(
                url, parameters, move_response)
            arcpy.AddMessage(msg)

        return move_response

    def move_items(self, target_folder_id, items):
        """
        Move items to a target folder.
        Arguments:
            target_folder_id: folder id to move items to
            items: list of one or more item ids to move
        Returns:
            None
        """
        # Test if we have a None object somewhere
        # This could potentially be the case if one of the previous
        # portal responses was not successful.

        url = '{}/content/users/{}/moveItems'.format(
            self.base_url, self.username)

        parameters = {
            'folder': target_folder_id,
            'items': ','.join(map(str, items))
        }

        move_response = self.url_request(url, parameters, request_type='POST')

        return move_response

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
               owner=None, item_id=None, repeat=None, num=10, id_only=True, name=None):
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
            'owner': self.username, #owner,
            'id': item_id,
            'name': name
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

        if self.debug:
            arcpy.AddMessage("Searching for '{}'".format(query))

        url = '{}/search'.format(self.base_url)
        parameters = {
            'num': num,
            'q': query
        }
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
        return self.url_request(url)

    def user_content(self, username=None):
        """
        User items and folders.

        Arguments:
            username -- user of interest

        Returns:
            A dictionary of user items and folders.
        """
        if username is None:
            username = self.username

        url = '{}/content/users/{}'.format(self.base_url, username)
        return self.url_request(url)

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

    def add_item(self, file_to_upload, username=None, folder_id=None, itemtype=None, params=None):
        """
        Adds an item to the portal.
        All items are added as multipart. Once the item is added,
        Add Part will be called.

        Returns:
            The response/item_id of the item added.
        """
        if username is None:
            username = self.username

        url = '{}/content/users/{}/{}/addItem'.format(self.base_url, username, folder_id)
        parameters = {
            'multipart': 'true',
            'filename': file_to_upload,
        }
        if params:
            parameters.update(params)

        if itemtype:
            parameters['type'] = itemtype
        else:
            try:
                file_name, file_ext = os.path.splitext(os.path.basename(file_to_upload))
                itemtype = ITEM_TYPES[file_ext.upper()]
            except KeyError:
                msg = "Unable to upload file: {}, unknown type".format(
                    file_to_upload)
                arcpy.AddError(msg)
                return

        details = {'filename': file_to_upload}
        add_item_res = self.url_request(
            url, parameters, request_type="POST", files=details)

        return self._add_part(file_to_upload, add_item_res['id'], itemtype)

    def _add_part(self, file_to_upload, item_id, upload_type=None):
        """ Add item part to an item being uploaded."""

        def read_in_chunks(file_object, chunk_size=10000000):
            """Generate file chunks (default: 10MB)"""
            while True:
                data = file_object.read(chunk_size)
                if not data:
                    break
                yield data

        url = '{}/content/users/{}/items/{}/addPart'.format(
            self.base_url, self.username, item_id)

        with open(file_to_upload, 'rb') as f:
            for part_num, piece in enumerate(read_in_chunks(f), start=1):
                title = os.path.splitext(os.path.basename(file_to_upload))[0]
                files = {"file": {"filename": file_to_upload, "content": piece}}
                params = {
                    'f': "json",
                    'token': self.token,
                    'partNum': part_num,
                    'title': title,
                    'itemType': 'file',
                    'type': upload_type
                }
                headers, data = MultipartFormdataEncoder().encodeForm(params, files)
                resp = self.url_request(url, data, "MULTIPART", headers, repeat=1)

        return resp

    def item_status(self, item_id, username=None):
        """
        Gets the status of an item.

        Returns:
            The item's status. (partial | processing | failed | completed)
        """
        if username is None:
            username = self.username

        url = '{}/content/users/{}/items/{}/status'.format(
            self.base_url, username, item_id)

        return self.url_request(url)

    def commit(self, item_id, username=None):
        """
        Commits an item that was uploaded as multipart

        Returns:
            Result of calling commit. (success: true| false)
        """
        if username is None:
            username = self.username

        url = '{}/content/users/{}/items/{}/commit'.format(
            self.base_url, username, item_id)

        return self.url_request(url)

    def update_item(self, item_id, metadata, username=None, folder_id=None, title=None):
        """
        Updates metadata parts of an item.
        Metadata expected as a tuple

        Returns:
            Result of calling update. (success: true | false)
        """
        if username is None:
            username = self.username

        url = "{}/content/users/{}/{}/items/{}/update".format(
            self.base_url, username, folder_id, item_id)

        parameters = {
            'snippet': metadata[0],
            'description': metadata[1],
            'tags': metadata[2],
            'accessInformation': metadata[3],
            'licenseInfo': metadata[4],
            'token': self.token,
            'f': 'json'
        }
        if title:
            parameters['title'] = title

        if len(metadata) > 5:
            parameters['thumbnail'] = metadata[5]

            with open(metadata[5], 'rb') as f:
                d = f.read()
                files = {"thumbnail": {"filename": metadata[5], "content": d }}
                headers, data = MultipartFormdataEncoder().encodeForm(parameters, files)
                resp = self.url_request(url, data, "MULTIPART", headers, repeat=1)

            return resp

        else:
            return self.url_request(url, parameters, 'POST')


    def url_request(self, in_url, request_parameters=None, request_type='GET',
                    additional_headers=None, files=None, repeat=0):
        """
        Make a request to the portal, provided a portal URL
        and request parameters, returns portal response. By default,
        returns a JSON response, and reuses the current token.

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

        # multipart requests pre-encode the parameters
        if request_type == 'MULTIPART':
            parameters = request_parameters
        else:
            parameters = {'f': 'json'}
            # if we haven't logged in yet, won't have a valid token
            if self.token:
                parameters['token'] = self.token
            if request_parameters:
                parameters.update(request_parameters)

        if request_type == 'GET':
            req = request('?'.join((in_url, encode(parameters))))
        elif request_type == 'MULTIPART':
            req = request(in_url, parameters)
        elif request_type == 'WEBMAP':
            if files:
                req = request(in_url, *self.encode_multipart_data(parameters, files))
            else:
                arcpy.AddWarning("Multipart request made, but no files provided.")
                return
        else:
            req = request(
                in_url, encode(parameters).encode('UTF-8'), self.headers)

        if additional_headers:
            for key, value in list(additional_headers.items()):
                req.add_header(key, value)
        req.add_header('Accept-encoding', 'gzip')
        try:
            response = urlopen(req)
        except HTTPError as e:
            arcpy.AddWarning("{} {} -- {}".format(
                HTTP_ERROR_MSG, in_url, e.code))
            return
        except URLError as e:
            arcpy.AddWarning("{} {} -- {}".format(
                URL_ERROR_MSG, in_url, e.reason))
            return

        if response.info().get('Content-Encoding') == 'gzip':
            buf = BytesIO(response.read())
            with gzip.GzipFile(fileobj=buf) as gzip_file:
                response_bytes = gzip_file.read()
        else:
            response_bytes = response.read()

        response_text = response_bytes.decode('UTF-8')

        # occasional timing conflicts; repeat until we get back a valid response.
        response_json = json.loads(response_text)

        # Check that data returned is not an error object
        if not response_json or "error" in response_json:
            rerun = False
            if repeat > 0:
                repeat -= 1
                rerun = True

            # token has expired. Revalidate, then rerun request
            if response_json['error']['code'] == 498:
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

    def save_file(self, url, saveFile):
        """Saves a file to a given location"""

        if self.token:
            url += "?token={}".format(self.token)

        data = urlopen(url).read()
        with open(saveFile, "wb") as out_file:
            out_file.write(data)

        return saveFile

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
