
import arcpy
import os
import sys
import time
import ago

ago.client.HTTPConnection._http_vsn= 10
ago.client.HTTPConnection._http_vsn_str='HTTP/1.0'

# Valid package types on portal
pkgTypes = {".LPK": "Layer Package",
            ".MPK": "Map Package",
            ".TPK": "Tile Package",
            ".GPK": "Geoprocessing Package",
            ".RPK": "Rule Package",
            ".GCPK": "Locator Package",
            ".PPKX": "Project Package",
            ".APTX": "Project Template",
            ".MMPK": "Mobile Map Package"
            }

def sharePackage2(in_package, username, password, summary, tags, credits, everyone, groups, org):


    active_url = arcpy.GetActivePortalURL()
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

    pkgMetadata = (summary, tags, credits, everyone, groups)

    # Make sure file exists
    try:
        uploadSize = os.stat(in_package).st_size
    except FileNotFoundError:
        arcpy.AddError("The file {0} was not found".format(in_package))
        sys.exit()

    fileName, fileExt = os.path.splitext(os.path.basename(in_package))
    try:
        uploadType = pkgTypes[fileExt.upper()]
    except KeyError:
        arcpy.AddError("Unknown package type extension: {0}".format(fileExt))
        sys.exit()

    # Create the place holder item on the portal
    newItemIDres = agol_helper.add_item(in_package, agol_helper.username, uploadType)
    if 'success' in newItemIDres:
        if newItemIDres['success']:
            newItemID = newItemIDres['id']
    else:
        try:
            if "Item already exists" in newItemIDres['error']['message']:
                arcpy.AddError("An item with this name already exists")
        except:
            print("Cannot upload, no good error message returned. Try again.")

        sys.exit()

    # Commit the file
    resCom = agol_helper.commit(newItemID, agol_helper.username)

    status = 'processing'  # partial | processing | failed | completed
    while status == 'processing' or status == 'partial':
        status = agol_helper.item_status(newItemID, agol_helper.username)['status']
        time.sleep(1)
        if status == 'failed':
            arcpy.AddError("Failed in processing the file on the portal")
            sys.exit()

    # Update the file info on the portal with values from the tool
    if summary or tags or credits:
        uresp = agol_helper.update_item(newItemID, pkgMetadata)
        try:
            if not uresp['success']:
                arcpy.AddWarning("Could not set sharing properties")
        except:
            arcpy.AddWarning("Problem setting metadata values:")
            arcpy.AddError("  {0}".format(uresp['error']))

    if everyone or groups or org:
        if groups:
            userGroups = agol_helper.list_groups(agol_helper.username)
            groupIDs = []
            for group in userGroups:
                for selectedgroup in groups.split(';'):
                    if group == selectedgroup:
                        groupIDs.append(userGroups[group])
        else:
            groupIDs = None

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
        sharePackage2(arcpy.GetParameterAsText(0),
                      arcpy.GetParameterAsText(1),
                      arcpy.GetParameterAsText(2),
                      arcpy.GetParameterAsText(3),
                      arcpy.GetParameterAsText(4),
                      arcpy.GetParameterAsText(5),
                      arcpy.GetParameterAsText(6),
                      arcpy.GetParameterAsText(7),
                      arcpy.GetParameterAsText(8))
        arcpy.SetParameter(9, True)
    except Exception as e:
        arcpy.AddError("Failed to upload: {}".format(e))
        arcpy.SetParameter(9, False)

