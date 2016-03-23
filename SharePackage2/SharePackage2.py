
import arcpy
import os
import time
import ago

ago.client.HTTPConnection._http_vsn= 10
ago.client.HTTPConnection._http_vsn_str='HTTP/1.0'

# Valid package types on portal
pkgTypes = {".LPK": "Layer Package",
            ".LPKX": "Layer Package",
            ".MPK": "Map Package",
            ".MPKX": "Map Package",
            ".TPK": "Tile Package",
            ".GPK": "Geoprocessing Package",
            ".GPKX": "Geoprocessing Package",
            ".RPK": "Rule Package",
            ".GCPK": "Locator Package",
            ".PPKX": "Project Package",
            ".APTX": "Project Template",
            ".MMPK": "Mobile Map Package",
            ".VTPK": "Vector Tile Package"
            }


def sharePackage2(in_package, folder, username, password, maintain, summary, tags, credits, everyone, org, groups):

    try:
        active_url = arcpy.GetActivePortalURL()
    except:
        active_url = 'https://www.arcgis.com/'
    agol_helper = ago.AGOLHelper(portal_url=active_url)

    # If not app-signed in, and have user/pass, sign in the old manual way
    if username and password and "Signed in through app" not in username:
        agol_helper.login(username, password)
    elif arcpy.GetSigninToken() is not None:
        # Sign in using info from the app
        agol_helper.token_login()
    else:
        arcpy.AddIDMessage("Error", 1561)
        return

    # Make sure file exists
    try:
        uploadSize = os.stat(in_package).st_size
    except FileNotFoundError:
        raise Exception("The file {0} was not found".format(in_package))

    fileName, fileExt = os.path.splitext(os.path.basename(in_package))
    try:
        uploadType = pkgTypes[fileExt.upper()]
    except KeyError:
        raise Exception("Unknown/unsupported package type extension: {0}".format(fileExt))


    portalFolders = agol_helper.list_folders()
    if folder == "<root>" or None: folder = ''
    folderID = ""
    moveFolder = False

    if folder:
        if folder not in portalFolders.keys():
            # Create a new folder
            folderID = agol_helper.create_folder(folder)
            arcpy.AddMessage("Created: {}".format(folderID))
            #refresh the folder list
            portalFolders = agol_helper.list_folders()

    #previousPkgId = agol_helper.search(fileName, uploadType)
    previousPkgId = agol_helper.search(item_type=uploadType, name=fileName)

    if len(previousPkgId) == 0:
        # Pkg does not exist
        if maintain:
            # No pkg + maintain meta  == quit
            raise Exception("Existing package not found. Check to make sure it exists or disable maintain metadata.")

        if folder:
            if folder in portalFolders.keys():
                folderID = portalFolders[folder]
            moveFolder = True

    else:
        # Pkg exists
        newItemID = previousPkgId[0]
        itemInfo = agol_helper.item(newItemID)

        # original pkg lives here.
        pkgFolderID = itemInfo['ownerFolder'] if itemInfo['ownerFolder'] else ""

        if folder:
            if folder in portalFolders.keys():
                if maintain and portalFolders[folder] != pkgFolderID:
                    raise Exception("Existing package to update not found in folder {}. Check the folder or disable maintain metadata.".format(folder))
                else:
                    # Existing pkg lives in supplied folder. It'll be updated.
                    folderID = portalFolders[folder]
                    if folderID != pkgFolderID:
                        # Package of same name exists but uploading to a different folder
                        moveFolder = True

            # no else here - this is case where folder needs to be created, covered previously

        else:
            if maintain and pkgFolderID:
                # pkg lives in folder, but root was specified:
                raise Exception("Did not find package to update in <root> Does it exist in a folder?")

            # no else here - covered previously with folderID variable initialize


    # Set metadata by getting original metadata or adding new
    if not maintain:
        try:
            # Only available in Pro 1.2 or 10.4
            metaFromPkg = arcpy.GetPackageInfo(in_package)
            description = metaFromPkg['description']
            if not summary: summary = metaFromPkg['summary']
            if not tags: tags = metaFromPkg['tags']
            if not credits: credits = metaFromPkg['credits']
        except AttributeError:
            description = ''
        pkgMetadata = (summary, description, tags, credits, '')

    else:
        metadataURL = "{}/content/users/{}/{}/items/{}".format(
            agol_helper.base_url, agol_helper.username, folderID, newItemID)
        metadata = agol_helper.url_request(metadataURL, {'token': agol_helper.token, 'f':'json'} )

        #re-set everyone if necessary from original share options
        everyone = True if metadata['sharing']['access'] == 'public' else everyone
        org = True if everyone else True if metadata['sharing']['access'] == 'org' else org
        groups = metadata['sharing']['groups'] if metadata['sharing']['groups'] else groups
        snippet = metadata['item']['snippet'] if metadata['item']['snippet'] else ''
        description = metadata['item']['description'] if metadata['item']['description'] else ''
        tags = ','.join(metadata['item']['tags'])
        accessInfo = metadata['item']['accessInformation'] if metadata['item']['accessInformation'] else ''
        licenseInfo = metadata['item']['licenseInfo'] if metadata['item']['licenseInfo'] else ''
        pkgMetadata = (snippet, description, tags, accessInfo, licenseInfo)

        # Save original thumbnail to update with metadata
        try:
            thumbnailURL = "{}/content/items/{}/info/{}".format(
                        agol_helper.base_url, newItemID, metadata['item']['thumbnail'])
            saveThumb = os.path.join(arcpy.env.scratchFolder, "thumbnail.png")
            agol_helper.save_file(thumbnailURL, saveThumb)
            pkgMetadata += (saveThumb,)
        except:
            arcpy.AddWarning("Problem getting thumbnail")

        arcpy.AddMessage("Using existing metadata")


    # Behavior is to always overwrite a package if it exists
    extraParams = {'overwrite':'true'}

    # Upload the package
    arcpy.AddMessage("Beginning file upload")
    newItemIDres = agol_helper.add_item(in_package, agol_helper.username, folderID, uploadType, params=extraParams)

    if 'success' in newItemIDres:
        if newItemIDres['success']:
            newItemID = newItemIDres['id']
    else:
        raise Exception("(returned msg) {}".format(newItemIDres))

    # Commit the file
    arcpy.AddMessage("Committing the file on the portal")
    resCom = agol_helper.commit(newItemID, agol_helper.username)

    status = 'processing'  # partial | processing | failed | completed
    while status == 'processing' or status == 'partial':
        status = agol_helper.item_status(newItemID, agol_helper.username)['status']
        time.sleep(1)
        if status == 'failed':
            raise Exception("Failed in processing the file on the portal")

    if moveFolder:
        #move new package into folder
        moveResp = agol_helper.move_items(folderID, [newItemID])
        if not moveResp['results'][0]['success']:
            arcpy.AddMessage("Failed to move item to folder: '{}'. Item will be created in root".format(folder))
            folderID = ""

    # Set or Update the metadata
    arcpy.AddMessage("Setting metadata and sharing settings")
    uresp = agol_helper.update_item(newItemID, pkgMetadata, folder_id=folderID, title=fileName)
    try:
        if not uresp['success']:
            arcpy.AddWarning("Could not set sharing properties")
    except:
        arcpy.AddWarning("Problem setting metadata values:")
        arcpy.AddError("  {0}".format(uresp['error']))

    # Clean up thumbnail
    try:
        os.remove(saveThumb)
    except (NameError, IOError):
        pass


    # Set Sharing options
    if not maintain:
        if everyone or groups or org:
            groupIDs = []
            if groups:
                userGroups = agol_helper.list_groups(agol_helper.username)
                for group in userGroups.keys():
                    arcpy.AddMessage(group)
                    for selectedgroup in groups:
                        if group == selectedgroup:
                            groupIDs.append(userGroups[group])

            gresp = agol_helper.share_items(groupIDs, everyone, org, [newItemID])
            try:
                if not gresp['results'][0]['success']:
                    arcpy.AddWarning("Could not set sharing properties")
                    arcpy.AddError("  {0}".format(gresp['results'][0]['error']['message']))
            except:
                arcpy.AddWarning("Problem sharing item:")
                arcpy.AddError("  {0}".format(gresp))



if __name__ == '__main__':

    try:
        sharePackage2(arcpy.GetParameterAsText(0), #input pkg
                      arcpy.GetParameterAsText(1), #folder
                      arcpy.GetParameterAsText(2), #username
                      arcpy.GetParameterAsText(3), #password
                      arcpy.GetParameter(4), #maintain
                      arcpy.GetParameterAsText(5), #summary
                      arcpy.GetParameterAsText(6), #tags
                      arcpy.GetParameterAsText(7), #credits
                      arcpy.GetParameter(8), #everybody
                      arcpy.GetParameter(9), #org
                      arcpy.GetParameterAsText(10)) #groups

        arcpy.SetParameter(11, True)
        arcpy.AddMessage("done!")

    except Exception as e:
        arcpy.AddError("Failed to upload, error: {}".format(e))
        arcpy.SetParameter(11, False)
