#! -*- coding: utf-8; mode: python -*-
"""
ago.py: interact with an ArcGIS Portal instance
"""
import arcpy
import json
import hashlib
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


# messages
UNPACKING_RASTER_MSG = "Unpacking raster on"
NO_PORTAL_URL_MSG = "Expected portal URL. None given."
NO_TOKEN_MSG = "Unable to get signin token."
EMPTY_ITEM_MSG = "Empty item detected, unable to move."
MISSING_TPK_MSG = "Failed to find Tile Package."
MISSING_USERNAME_MSG = "Expected user name. None given."
TPK_PUBLISHING_FAILED = "Publishing Tile Package failed."
NO_PORTAL_MSG = "Unable to create item for undefined portal."
NO_EDIT_RESPONSE_MSG = "No response when setting up edit service."
NO_UPDATE_RESPONSE_MSG = "No response when setting up update service."
NO_FILES_MULTIPART_MSG = "Multipart request made, but no files provided."
INVALID_SHARING_OPTIONS_MSG = "Invalid sharing options set."
JSON_OBJECT_ERROR_MSG = "JSON object returned an error."

# Valid package types on portal
itemTypes = {".LPK": "Layer Package",
             ".MPK": "Map Package",
             ".BPK": "Mobile Basemap Package",
             ".TPK": "Tile Package",             
             ".GPK": "Geoprocessing Package",             
             ".RPK": "Rule Package",
             ".GCPK": "Locator Package",             
             ".PPKX": "Project Package",
             ".APTX": "Project Template",
             ".SD": "Service Definition",
             ".TPK": "Tile Package"
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
        self.protocol = 'http'
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
        self.base_layers = {
            'WORLD_IMAGERY_WITH_LABELS': [
                'World_Imagery',
                'Reference/World_Boundaries_and_Places'
            ],
            'WORLD_IMAGERY': ['World_Imagery'],
            'WORLD_STREET_MAP': ['World_Street_Map'],
            'WORLD_TOPO_MAP': ['World_Topo_Map'],
            'WORLD_SHADED_RELIEF': ['World_Shaded_Relief'],
            'WORLD_PHYSICAL_MAP': ['World_Physical_Map'],
            'WORLD_TERRAIN_BASE': [
                'World_Terrain_Base',
                'Reference/World_Reference_Overlay'
            ],
            'USA_TOPO_MAPS': ['USA_Topo_Maps'],
            'OCEAN_BASEMAP': [
                'Ocean/World_Ocean_Base',
                'Ocean/World_Ocean_Reference'
            ],
            'LIGHT_GRAY_CANVAS': [
                'Canvas/World_Light_Gray_Base',
                'Canvas/World_Light_Gray_Reference'
            ],
            'NAT_GEO_WORLD_MAP': ['NatGeo_World_Map'],
            'OPENSTREETMAP': None
        }
        # nice mappings for the label names, matching what ArcGIS Online shows
        self.base_layer_names = {
            'WORLD_IMAGERY_WITH_LABELS': 'Imagery with Labels',
            'WORLD_IMAGERY': 'Imagery',
            'WORLD_STREET_MAP': 'Streets',
            'WORLD_TOPO_MAP': 'Topography',
            'WORLD_SHADED_RELIEF': 'Shaded Relief',
            'WORLD_PHYSICAL_MAP': 'Physical',
            'WORLD_TERRAIN_BASE': 'Terrain',
            'USA_TOPO_MAPS': 'USA Topographic',
            'OCEAN_BASEMAP': 'Oceans',
            'LIGHT_GRAY_CANVAS': 'Light Gray Canvas',
            'NAT_GEO_WORLD_MAP': 'National Geographic',
            'OPENSTREETMAP': 'OpenStreetMap'
        }
        # pulled this from an existing services; also see http://goo.gl/By8WRx
        # zoom level, resolution [meters], scale [1:x])
        self.scales = [
            (0, 156543.03392800014, 591657527.591555),
            (1, 78271.51696399994, 295828763.795777),
            (2, 39135.75848200009, 147914381.897889),
            (3, 19567.87924099992, 73957190.948944),
            (4, 9783.93962049996, 36978595.474472),
            (5, 4891.96981024998, 18489297.737236),
            (6, 2445.98490512499, 9244648.868618),
            (7, 1222.992452562495, 4622324.434309),
            (8, 611.4962262813797, 2311162.217155),
            (9, 305.74811314055756, 1155581.108577),
            (10, 152.87405657041106, 577790.554289),
            (11, 76.43702828507324, 288895.277144),
            (12, 38.21851414253662, 144447.638572),
            (13, 19.10925707126831, 72223.819286),
            (14, 9.554628535634155, 36111.909643),
            (15, 4.77731426794937, 18055.954822),
            (16, 2.388657133974685, 9027.977411),
            (17, 1.1943285668550503, 4513.988705),
            (18, 0.5971642835598172, 2256.994353),
            (19, 0.29858214164761665, 1128.497176)
        ]
        self.parameters = None
        self.portal_name = None
        self.portal_info = {}
        self.working_folder = None
        self.wkt = arcpy.SpatialReference(3857).exportToString()
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
            arcpy.AddError(MISSING_USERNAME_MSG)
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
            if hasattr(token_response, 'ssl') and token_response['ssl'] is True:
                self.protocol = 'https'
            else:
                self.protocol = 'http'

            # update base information with token
            self.information()
            self.login_method = 'password'
        else:
            arcpy.AddError(NO_TOKEN_MSG)
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
            arcpy.AddError(NO_TOKEN_MSG)
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

    def list_basemaps(self):
        """
        Query the service for available basemaps.

        Arguments:
            None

        Returns:
            A dictionary of basemap titles to ids.

        """
        basemaps = {}
        if self.portal_info and 'basemapGalleryGroupQuery' in self.portal_info:
            url = '{}/community/groups'.format(self.base_url)
            parameters = {
                'token': self.token,
                'f': 'json',
                'q': self.portal_info['basemapGalleryGroupQuery']
            }

            group_results = self.url_request(url, parameters)

            if group_results and 'results' in group_results and \
                    len(group_results['results']) > 0:
                # 'This group features a variety of basemaps that can be accessed
                # from ArcGIS Online.'
                group_id = group_results['results'][0]['id']
                basemap_results = self.search(group=group_id, num=50, id_only=False)
                for result in basemap_results:
                    basemaps[result['title']] = result['id']

        return basemaps

    def get_basemap(self, basemap_id):
        """
        Get JSON 'baseMap' response for specified id.

        Arguments:
            basemap_id -- item id for a valid basemap layer

        Returns:
            basemap dictionary suitable for using in the 'baseMap' list
            of a web map JSON document.
        """
        basemap_result = None
        response = self.item_data(basemap_id)
        if response and 'baseMap' in response:
            basemap_result = response['baseMap']
        return basemap_result

    def item_data(self, item_id):
        """
        Get JSON data response for specified id.

        Arguments:
            item_id -- item id that contains a webmap document

        Returns:
            Web map JSON document.
        """
        result = None
        url = '{}/content/items/{}/data'.format(self.base_url, item_id)

        parameters = {
            'token': self.token,
            'f': 'json'
        }
        response = self.url_request(url, parameters)
        if response:
            result = response
        return result

    def default_basemap(self):
        """
        Portal-defined 'default basemap'.

        Arguments: None

        Returns:
            Title of basemap.
        """
        default_title = None
        if 'defaultBasemap' in list(self.portal_info.keys()) and \
                self.portal_info['defaultBasemap']:
            # contains 'baseMapLayers' and 'title'. The layers howeer are
            # different than the gallery response -- take the tile and look
            # up the basemap instead.
            default_details = self.portal_info['defaultBasemap']
            if 'title' in default_details:
                basemaps = self.list_basemaps()
                if basemaps and default_details['title'] in list(basemaps.keys()):
                    default_title = default_details['title']

        return default_title

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

        Arguments:
            name -- folder name to create

        Returns:
            folder item id.
        """
        # TODO: side-effects
        url = '{}/content/users/{}/createFolder'.format(
            self.base_url, self.username)

        parameters = {
            'token': self.token,
            'f': 'json',
            'title': name
        }

        response = self.url_request(url, parameters, 'POST')
        if self.debug:
            arcpy.AddMessage("Creating folder, got response: {}".format(response))

        if response is None:
            return
        else:
            self.working_folder = response['folder']['id']

        return self.working_folder

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
            'token': self.token,
            'f': 'json',
            'folder': target_folder_id,
            'items': ','.join(map(str, items))
        }

        move_response = self.url_request(url, parameters, 'POST')
        if self.debug:
            msg = "Moving items, using {} with parameters {}, got {}".format(
                url, parameters, move_response)
            arcpy.AddMessage(msg)

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
                arcpy.AddWarning(INVALID_SHARING_OPTIONS_MSG)
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

    def publish_item(self, item_name, file_type):
        """
        Publish a tile package into a Service.

        Arguments:
            item_name -- name of item to be published.
            file_type -- type of item to be published: Service Definition (serviceDefinition), Tile Package (tilePackage)

        Returns:
            A tuple containing two elements: the raster creation
            response, and an 'is operational' layer boolean.
        """

        results = self.search(
            title=item_name, item_type=file_type,
            owner=self.username, repeat=5)

        if not results:
            arcpy.AddError("{} {}".format(MISSING_TPK_MSG, item_name))
            return

        published_Item_ID = results[0]
        if file_type == "Service Definition":
            pfileType = "serviceDefinition"
        else: pfileType = "tilePackage"

        url = '{}/content/users/{}/publish'.format(self.base_url, self.username)
        parameters = {
            'f': 'json',
            'token': self.token,
            'itemId': published_Item_ID,
            'filetype': pfileType}

        response_info = self.url_request(url, parameters, 'POST', repeat=5)
        if file_type == "Service Definition":
            return response_info
            # Everything below this is Tile specific, thats why we can go back.

        tile_service_url = None
        tile_service_item_id = None
        if 'services' in response_info:
            if len(response_info['services']) > 0:
                service_result = response_info['services'][0]
                if 'serviceurl' in service_result:
                    tile_service_url = service_result['serviceurl']
                if 'serviceItemId' in service_result:
                    tile_service_item_id = service_result['serviceItemId']

        if tile_service_item_id is None:
            arcpy.AddError("{} {}\n  {}".format(
                TPK_PUBLISHING_FAILED, item_name, service_result))
            return

        # A unique identifying string for the layer; i.e. for the DOM
        raster_id = "{}_{}".format(item_name, str(random.randint(1, 1000)))

        raster_info = {
            'itemId': tile_service_item_id,
            'url': tile_service_url,
            'visibility': 'true',
            'id': raster_id,
            'opacity': 1,
            'title': item_name
        }

        # get service attributes
        service_response = self.url_request(
            tile_service_url, self.parameters, repeat=5)
        is_operational = True

        if ('tileInfo' in service_response and
                'spatialReference' in service_response['tileInfo'] and
                'wkid' in service_response['tileInfo']['spatialReference']):
            ts_wkid = service_response['tileInfo']['spatialReference']['wkid']
            if ts_wkid not in [3857, 102100, 102113]:
                is_operational = False

            if self.debug:
                arcpy.AddMessage("Tile package {} has wkid of `{}`.".format(
                    item_name, ts_wkid))

        # self.wkt = service_response['spatialReference']
        # assemble the level of details contained in the tile package
        tile_lods = service_response['tileInfo']['lods']
        tile_levels = ','.join(map(str, [lod['level'] for lod in tile_lods]))

        # determine the extent of the tile package content
        f_extent = service_response['fullExtent']
        f_bbox = (f_extent['xmin'], f_extent['ymin'],
                  f_extent['xmax'], f_extent['ymax'])

        tiles_full_extent = ','.join(map(str, f_bbox))

        tile_service_url = tile_service_url.replace('rest', 'admin')
        tile_service_url = tile_service_url.replace('/MapServer', '.MapServer')

        ref = {
            'Referer': 'http://maps.esri.com',
            'Origin': 'http://maps.esri.com',
            'Host': 'tiles.arcgis.com'
        }

        arcpy.AddMessage("  {} {}".format(UNPACKING_RASTER_MSG, self.portal_name))
        # TODO further attemps at checking the tile service status
        # before looking for the edit service, see issue #158.
        edit_service_url = tile_service_url + '/edit'
        edit_service_parameters = {
            'f': 'json',
            'token': self.token,
            'sourceItemId': published_Item_ID,
            'minScale': service_response['minScale'],
            'maxScale': service_response['maxScale']
        }

        edit_response = self.url_request(
            edit_service_url, edit_service_parameters, 'POST', ref, repeat=5)

        if edit_response is None:
            arcpy.AddWarning(NO_EDIT_RESPONSE_MSG)
            return

        update_service_url = tile_service_url + '/updateTiles'
        update_service_parameters = {
            'f': 'json',
            'token': self.token,
            'levels': tile_levels,
            'extent': tiles_full_extent
        }

        update_response = self.url_request(
            update_service_url, update_service_parameters, 'POST', ref, repeat=5)
        if update_response is None:
            arcpy.AddWarning(NO_UPDATE_RESPONSE_MSG)
            return

        # return the item id and url for the generated map service
        return [raster_info, is_operational, published_Item_ID]

    def delete(self, title=None, item_type=None, item_id=None,
               owner_folder_id=None, repeat=None):
        """
        Delete items, a partial implementation of the
        delete operation of the ArcGIS REST API. Requires one of:
          title, item_type or item_id.

        Arguments:
            title -- item title
            item_type -- item type
            item_id -- item id
            owner_folder_id -- username of item owner
            repeat -- retry the search, up to this number of times.

        Returns:
            None
        """

        def create_delete_url(item_id=None, owner_folder_id=None):
            """ Create a formated delete url."""
            url = '{}/content/users/{}'.format(self.base_url, self.username)
            if owner_folder_id:
                url += '/{}'.format(owner_folder_id)
            url += '/items/{}/delete'.format(item_id)
            return url

        parameters = {
            'f': 'json',
            'token': self.token
        }

        if title and item_type:
            if self.debug:
                arcpy.AddMessage("Deleting {} of type {}.".format(
                    title, item_type))

            search_results = self.search(
                title=title, item_type=item_type,
                owner=self.username, repeat=repeat)

            if search_results:
                if len(search_results) > 0:
                    item_id = search_results[0]

                    # one more request to determine the location of the item
                    details_url = '{}/content/items/{}'.format(
                        self.base_url, item_id)

                    if self.debug:
                        arcpy.AddMessage("details URL: {}".format(details_url))

                    details_response = self.url_request(details_url, parameters)

                    if 'ownerFolder' in details_response:
                        owner_folder_id = details_response['ownerFolder']

            elif self.debug:
                arcpy.AddMessage("Unable to locate item.")

        if item_id:
            delete_url = create_delete_url(item_id, owner_folder_id)
            delete_response = self.url_request(delete_url, parameters, 'POST')

            if self.debug:
                arcpy.AddMessage(
                    "Got a url of {}, deleting item.".format(delete_url))
            arcpy.AddMessage("Deletion response: {}".format(delete_response))

        return

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
                arcpy.AddWarning(NO_FILES_MULTIPART_MSG)
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
                    arcpy.AddError(NO_TOKEN_MSG)
                    return
                rerun = True

            if rerun:
                time.sleep(2)
                response_json = self.url_request(
                    in_url, request_parameters, request_type,
                    additional_headers, files, repeat)

        return response_json

    def create_webmap(self, map_info, operational_layers, base_layers=None,
                      bookmarks=None, folder_id=None):
        """
        Create a web map document from a collection of provided items.

        Arguments:
            map_info -- a dictionary of properties to configure the map:
              - title: map title
              - tags: desired default tags
              - thumbnail: path to image
              - description: item description
              - snippet: short item summary
              - accessInformation: credits
              - licenseInfo: licensing information
              - extent: xmin,ymin,xmax,ymax
            operational_layers -- A list of thematic layers, each one containing
                a valid web map JSON dictionary
            base_layers -- provide the backdrop for the web map, typically
                basemaps directly provided by the portal
            bookmarks -- JSON dictionary of bookmark items
            folder_id -- folder to create the web map within.

        Returns:
            Resulting web map item_id.
        """
        if not self.portal_name:
            arcpy.AddError(NO_PORTAL_MSG)
            return

        current_time = time.time()
        created = datetime.datetime.fromtimestamp(
            current_time).strftime('%Y-%m-%d %H:%M:%S')

        if 'title' in map_info:
            title = map_info['title']
            item = "{}_{}".format(
                map_info['title'].replace(' ', '_'), int(current_time))
        else:
            title = 'Untitled WebMap created {}'.format(created)
            item = 'untitled_webmap_{}'.format(int(current_time))

        if 'tags' in map_info:
            tags = map_info['tags']
        else:
            tags = 'webmap,mxd2webmap'

        # 'snippet' is used as a term for 'summary'
        if 'snippet' in map_info:
            snippet = map_info['snippet']
        else:
            snippet = 'Untitled WebMap created {}'.format(created)

        output_base_layers = []
        if not base_layers:
            # we weren't passed base layers, initialize a basemap.
            basemap_title = self.default_basemap()
            basemap_id = self.list_basemaps()[basemap_title]
            output_base_layers = self.get_basemap(basemap_id)['baseMapLayers']
        else:
            for (i, layer) in enumerate(base_layers):
                # function basemap_layer will build up the necessary JSON
                # for a specific layer...
                if (isinstance(layer, unicode) or isinstance(layer, str)) \
                        and layer in list(self.base_layer_names.keys()):
                    # we got a bare string that is a layer name, generate JSON
                    basemap_id = self.list_basemaps()[layer]
                    basemap_json = self.get_basemap(basemap_id)
                    output_base_layers += basemap_json['baseMapLayers']
                    if i == 0:
                        basemap_title = layer
                elif isinstance(layer, dict):
                    # assume fully formed JSON, put at the top of the layer list
                    output_base_layers = layer['baseMapLayers'] + output_base_layers
                    if i == 0:
                        basemap_title = layer['title']
                else:
                    if self.debug:
                        arcpy.AddWarning(
                            "Skipping invalid layer {}".format(layer))

        webmap = {
            'operationalLayers': operational_layers,
            'bookmarks': bookmarks,
            'baseMap': {
                'baseMapLayers': output_base_layers,
                'title': basemap_title
            },
            "spatialReference": {
                "wkid": 102100,
                "latestWkid": 3857
            },
            'version': '2.0'
        }

        webmap_parameters = {
            'f': 'json',
            'token': self.token,
            'type': 'Web Map',
            'typeKeywords': 'Web Map, Online Map, mxd2webmap',
            'overwrite': 'true',
            'text': json.dumps(webmap),
            'title': title,
            'item': item,
            'tags': tags,
            'snippet': snippet,
        }

        optional = ['thumbnailURL', 'extent', 'description',
                    'accessInformation', 'licenseInfo']

        for param in optional:
            if param in map_info:
                webmap_parameters[param] = map_info[param]

        if self.debug:
            arcpy.AddMessage("Generated webmap JSON: {}".format(
                webmap_parameters))

        add_webmap_url = '{}/content/users/{}'.format(self.base_url, self.username)
        if folder_id:
            add_webmap_url += '/{}'.format(folder_id)
        add_webmap_url += '/addItem'

        if 'thumbnail' in map_info:
            files = {'thumbnail': map_info['thumbnail']}
            webmap_response = self.url_request(
                add_webmap_url, webmap_parameters,
                'WEBMAP', None, files)
        else:
            webmap_response = self.url_request(
                add_webmap_url, webmap_parameters,
                'POST')

        if 'id' not in webmap_response:
            arcpy.WarningMessage("Creating webmap failed.")
            return

        return webmap_response['id']

    def assert_json_success(self, data):
        """A function that checks that the input JSON object
            is not an error object."""
        success = False
        obj = json.loads(data)
        if 'status' in obj and obj['status'] == "error":
            arcpy.AddWarning("{} {}".format(JSON_OBJECT_ERROR_MSG, str(obj)))
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

    def basemap_layer(self, name):
        """ Build a formatted dictionary for baseMapLayers. """
        services_url = 'http://services.arcgisonline.com/ArcGIS/rest/services'
        basemaps = []
        basemap_defaults = {
            'opacity': 1,
            'visibility': True
        }

        if name in self.base_layers:
            if self.base_layers[name] is None:
                basemap_res = basemap_defaults.copy()
                basemap_res['type'] = name
                basemap_res['id'] = name
                basemap_res['layerType'] = name
                basemaps.append(basemap_res)
            else:
                for layer in self.base_layers[name]:
                    shorthash = hashlib.sha1(layer).hexdigest()[:7]

                    basemap_res = basemap_defaults.copy()
                    basemap_res['id'] = "{}_{}".format(
                        layer.split("/")[-1], shorthash)
                    basemap_res['url'] = "{}/{}/MapServer".format(
                        services_url, layer)
                    basemaps.append(basemap_res)
        if self.debug:
            for basemap_label in basemaps:
                arcpy.AddMessage("Adding basemap {}".format(basemap_label))

        return basemaps

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
