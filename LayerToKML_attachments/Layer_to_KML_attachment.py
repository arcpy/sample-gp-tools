# Layer to KML - With Attachments (Layer_to_KML_attachment.py)
# Kevin Hibma, Esri
# As found on ArcGIS.com:  http://www.arcgis.com/home/item.html?id=5d8704c938ea4715b59eebabcd96c1d9
# Last updated: November 27, 2015
# Version: ArcGIS 10.1+ or ArcGIS Pro 1.0+
#
# Required Arguments:
#    Input layer (features layer): path to layer
#    Output KML (file): output path to KMZ file to be created
# Optional Arguments:
#    Output scale (long): scale to create output KMZ file
#    Clamped to ground (boolean): Clamp features to the ground (override their elevation)
#    Allow Unique ID Field (boolean): allow a temporary ID field to be added to the input data
#    Height (long): set the height to display image attachments in the KML popup
#    Width (long): set the width to display image attachments in the KML popup
# ==================================================================================================

import arcpy
import os
import sys
import zipfile
import shutil
try:
  from xml.etree import cElementTree as ElementTree
except:
  from xml.etree import ElementTree

# These "supported" items determine what HTML to put into the HTML popup.
# If this list is enhanced, the IFSTATEMENT writing HTML needs to be updated.
fileTypes = {'IMG' : ['.jpg', '.png', '.gif'],
             'PDF' : ['.pdf']
             }


def checks(inputFeatures):
  """ Pre checks to make sure we can run """

  def hasAttachments(inputFeatures):

    d = arcpy.Describe(inputFeatures)
    rc_names = d.relationshipClassNames

    if len(rc_names) > 0:
      for rc_name in rc_names:
        # relationship class is always beside the input features
        rc = os.path.join(d.path, rc_name)
        rcDesc = arcpy.Describe(rc)

        if rcDesc.isAttachmentRelationship:
          attachTables = rcDesc.destinationClassNames
          if len(attachTables) > 0:
            for att_tableName in attachTables:
              if arcpy.Exists(os.path.join(d.path, att_tableName)):
                # assume the attachment table resides beside the input feature
                return os.path.join(d.path, att_tableName)
              else:
                # if the attachment table is not found, walk through the workspace looking for it
                for dirpath, dirnames, filenames in arcpy.da.Walk(ws, datatype="Table"):
                  for f in filenames:
                    if f == att_tableName:
                      if arcpy.Exists(os.path.join(dirpath, att_tableName)):
                        return os.path.join(dirpath, att_tableName)

    return None

  ## find the attachment table
  attachTable = hasAttachments(inputFeatures)

  ## check for sequential OIDs
  seq = True
  if max([row[0] for row in arcpy.da.SearchCursor(inputFeatures,["OID@"])]) != \
     int(arcpy.GetCount_management(inputFeatures).getOutput(0)):
    seq = False

  return attachTable, seq


def attachments(KMLfiles, KMLdir, attachTable, seq=True, uniqueID=False, height=None, width=None):
  """ Take attachments, extract to disk, update the KML and put them into the KMZ """

  docKML = os.path.join(KMLdir, "doc.kml")
  ElementTree.register_namespace('', "http://www.opengis.net/kml/2.2")
  tree = ElementTree.parse(docKML)

  KML_NS = ".//{http://www.opengis.net/kml/2.2}"
  for node in tree.findall(KML_NS + 'Placemark'):
    idTxt = node.attrib['id']
    idVal = long(idTxt.replace('ID_', '')) + 1 # add 1 because its 0 indexed.
    for node in node.findall(KML_NS + 'description') :
      html = node.text

      # Special handling for the addition of the tempID field
      if not seq and uniqueID:
        gidTD = html.find("tempIDField")
        gidStart = html.find("<td>", gidTD)
        GID = html[gidStart+4 : gidStart+20]

        # Remove the GUID field from the HTML.
        html = html[:gidTD-4] + html[gidStart+25:]

        # Take guid and match it to find the OID to use in the attachment table
        expression = "tempIDField = '{0}'".format(GID)
        with arcpy.da.SearchCursor(inputFeatures, ['OID@','tempIDField'], expression) as cursor:
          for row in cursor:
            tableMatchOID = row[0]

      # Extract the images and add HTML into the KML
      try:
        string2Inject = ''
        if not seq and uniqueID: # Use the field that was inserted
          exp = "REL_OBJECTID = {0}".format(tableMatchOID)
        else: # Otherwise, use the ID value from KML to match
          exp = "REL_OBJECTID = {0}".format(idVal)

        with arcpy.da.SearchCursor(attachTable,['DATA', 'ATT_NAME', 'REL_OBJECTID'], exp) as cursor:
          for row in cursor:
            binaryRep = row[0]
            fileName = row[1]
            # save to disk
            open(os.path.join(KMLfiles, fileName), 'wb').write(binaryRep.tobytes())
            fname, ext = os.path.splitext(fileName)

            os.rename(os.path.join(KMLfiles, fileName), os.path.join(KMLfiles, fileName.lower()))
            fileName = fileName.lower()

            filetype = "unknown"
            for k, v in fileTypes.items():
              if ext.lower() in v:
                filetype = k

            # Add new items here if the 'fileTypes' dictionary has been updated.
            if filetype == 'IMG':
              if height or width:
                string2Inject += " <br> <img src=\"files\{0}\" height={1} width={2}> ".format( fileName, height, width )
              else:
                string2Inject += " <br> <img src=\"files\{0}\"> ".format( fileName )
            elif filetype == 'PDF':
              string2Inject += " <br> <a href =\"files\{0}\">PDF: {1} </a> ".format(fileName, fileName)
            else:  # unknown
              arcpy.AddWarning("Unknown or unsupported file type for OBJECTID: {}.".format(row[2]))
              arcpy.AddWarning("{}  will not be accessible in the popup.".format(fileName))

            string2Inject += '</td>'
            newHTML = html.replace("</td>", string2Inject, 1)
            node.text = newHTML

      except:
        arcpy.AddWarning("No attachment match for ID: {}".format(idVal))

  tree.write(docKML)
  del tree
  del docKML


if __name__ == '__main__':

  inputFeatures = arcpy.GetParameterAsText(0)
  outputKML = arcpy.GetParameterAsText(1)
  outputScale = arcpy.GetParameterAsText(2)
  clamped = arcpy.GetParameterAsText(3)
  uniqueID = arcpy.GetParameterAsText(4)
  height = arcpy.GetParameterAsText(5)
  width = arcpy.GetParameterAsText(6)

  # Check the input and make sure
  # 1) the data has sequential OIDs
  # 2) an attachment table can be found
  attachTable, seq = checks(inputFeatures)

  if attachTable is None:
    arcpy.AddError("Could not find an attachment table. Ensure the attachment table is properly")
    arcpy.AddError("referenced through a relationship class in the same workspace as the input features.")
    sys.exit()

  if not seq:
    arcpy.AddWarning("It appears the OIDs for the input featureclass are NOT sequential.")
    arcpy.AddWarning("Attachment logic depends on sequential OIDs.")
    arcpy.AddWarning("A temporary ID field needs to be added to your data to attempt to reconcile this.")

    # Can only proceed if we're permitted to add a new field to the input data.
    if not uniqueID:
      arcpy.AddError("You need to check the Allow Unique ID parameter (re-run tool and set to True).")
      arcpy.AddError("Note: This will add a field to your data, calc, and eventually remove it.")
      arcpy.AddError("To maintain the integrity  of your data, make a copy of your data and provide this as input.")
      sys.exit()
    else: # Add the new ID field to the data
      import uuid
      arcpy.AddField_management(inputFeatures, "tempIDField", "TEXT")
      edit = arcpy.da.Editor(arcpy.Describe(inputFeatures).path)
      edit.startEditing(False, False)

      with arcpy.da.UpdateCursor(inputFeatures, ["tempIDField"]) as cursor:
        for row in cursor:
          row[0] = str(uuid.uuid4().get_hex().upper()[0:16])
          cursor.updateRow(row)
      edit.stopEditing(True)
      arcpy.AddMessage("A temporary field was added to your data and will be removed when tool completes.")

  # Create KML file
  arcpy.LayerToKML_conversion(inputFeatures, outputKML, outputScale, ignore_zvalue=clamped)

  # Make new files directory, copy all images inside
  KMLdir = os.path.join(os.path.dirname(outputKML), "kml_extracted")
  if not os.path.exists(KMLdir):
    os.mkdir(KMLdir)
  KMLfiles = os.path.join(KMLdir, "files")
  if not os.path.exists(KMLfiles):
    os.mkdir(KMLfiles)

  # Rename the KML to ZIP and extract it
  root, kmlext = os.path.splitext(outputKML)
  os.rename(outputKML, root + ".zip")

  with zipfile.ZipFile(root + ".zip", "r") as z:
    z.extractall(KMLdir)

  # Inject images into .kmz and save
  docKML = os.path.join(KMLdir, "doc.kml")

  # Place the attachments inside the KMZ
  attachments(KMLfiles, KMLdir, attachTable, seq, uniqueID, height, width)
  if uniqueID:
    arcpy.DeleteField_management(inputFeatures, "tempIDField")

  # Remove the original KMZ (zip) as it'll be made new again
  os.remove(root + ".zip")

  # zip everything back up
  zipf = zipfile.ZipFile(root + ".zip", 'w')
  for rootdir, dirs, files in os.walk(KMLdir):
    for f in files:
      zipf.write(os.path.join(rootdir, f), os.path.relpath(os.path.join(rootdir, f), KMLdir))
  zipf.close()

  # Rename ZIP back to KMZ
  os.rename(root + ".zip", outputKML)

  # Clean up the KML dir
  shutil.rmtree(KMLdir)
