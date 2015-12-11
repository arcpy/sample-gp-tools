'''----------------------------------------------------------------------------------
 Tool Name:   Raster Field, Blob, Or Hyperlink To Attachment
 Source Name: ToAttachments.py
 Version:     ArcGIS 10.1
 Author:      dlfater@esri.com - Esri, Inc.
 Required Arguments:
              Input Dataset (Feature Class or Table)
              Field (Raster, Blob, or Text field)
 Optional Arguments:
              File Type (String)
 Derived output:
              Output Dataset (Feature Class or Table)

 Description: Adds geodatabase attachments to input dataset, based on files stored
              in a raster or blob field, or hyperlinked to.
----------------------------------------------------------------------------------'''

# Import system modules
import arcpy
import re
import os
import csv
import urllib2
import datetime
try:
    from urllib.request import urlopen as urlopen
except:
    from urllib2 import urlopen as urlopen

arcpy.env.overwriteOutput = True

# Main function, all functions run in SpatialJoinOverlapsCrossings
def ToAttachments(in_dataset, field, ftype="", hyperlinkDir=""):
    try:
        # Error if sufficient license is not available
        if arcpy.ProductInfo().lower() not in ['arcinfo', 'arceditor']:
            arcpy.AddError("An ArcGIS for Desktop Standard or Advanced license is required.")
            sys.exit()

        arcpy.SetProgressor("default", "Setting up process")
        # Determine the type of the field being analyzed
        for fld in arcpy.Describe(in_dataset).fields:
            if fld.name.lower() == field.lower():
                type = fld.type.lower()
                break
        oidfield = arcpy.Describe(in_dataset).OIDFieldName
        count = int(arcpy.management.GetCount(in_dataset).getOutput(0))

        # Create a folder to store intermediate files on disk
        filedir = arcpy.management.CreateFolder("%scratchfolder%", "files_{0}".format(datetime.datetime.strftime(datetime.datetime.now(), "%d%m%Y%H%M%S")))
        # Write ObjectIDs to matching file
        matchtable = os.path.join(str(filedir), "match.txt")
        with open(matchtable, 'wb') as f:
            writer = csv.writer(f)
            writer.writerow(["OID", "FILE"])

            # If working with a blob field
            if type == "blob":
                arcpy.SetProgressor("step", "Processing BLOBs in field {0}".format(field), 0, count, 1)
                with arcpy.da.SearchCursor(in_dataset, ["OID@", field]) as scur:
                    # Read through the dataset, harvest files from blob, write to folder, then keep track of OIDs
                    for row in scur:
                        try:
                            path = os.path.join(str(filedir), "file_{0}.{1}".format(row[0], ftype))
                            open(path, "wb").write(row[1].tobytes())
                            writer.writerow([str(row[0]), path])
                        except:
                            arcpy.AddWarning("Cannot process BLOB for OID {0}.".format(row[0]))
                        finally:
                            arcpy.SetProgressorPosition()
                    # Enable geodatabase attachments and write intermediate files to gdb
                    f.close()
                    arcpy.management.EnableAttachments(in_dataset)
                    arcpy.management.AddAttachments(in_dataset, oidfield, matchtable, "OID", "FILE")

            # If working with a raster field
            elif type == "raster":
                with arcpy.da.SearchCursor(in_dataset, ["OID@"]) as scur:
                    i = 1
                    for row in scur:
                        try:
                            arcpy.SetProgressorLabel("Processing record {0}/{1}".format(i, count))
                            inraster = r'{0}\{1}.OBJECTID = {2}'.format(arcpy.Describe(in_dataset).catalogPath, field, row[0])
                            newname = os.path.join(str(filedir), "image_{0}.jpg".format(row[0]))
                            arcpy.management.CopyRaster(inraster, newname)
                            writer.writerow([str(row[0]), newname])
                        except:
                            arcpy.AddWarning("Cannot process raster field for OID {0}.".format(row[0]))
                        finally:
                            i+=1
                    f.close()
                    arcpy.management.EnableAttachments(in_dataset)
                    arcpy.management.AddAttachments(in_dataset, oidfield, matchtable, "OID", "FILE")

            # If working with a file path or hyperlink
            elif type == "string":
                arcpy.SetProgressor("step", "Processing files in field {0}".format(field), 0, count, 1)
                with arcpy.da.SearchCursor(in_dataset, ["OID@", field]) as scur:
                    # Need to read the first value of the input field to see if it is a full path, weblink, or path relative to the hyperlink base
                    for row in scur:
                        path = row[1]
                        scur.reset()
                        break
                    # If the path 'exists', it is a file on disk or network location
                    if os.path.exists(path):
                        arcpy.management.EnableAttachments(in_dataset)
                        arcpy.management.AddAttachments(in_dataset, oidfield, in_dataset, oidfield, field)
                        arcpy.AddWarning(arcpy.GetMessages(1))
                        arcpy.SetProgressorPosition(count)
                    # If the path doesn't exist, check if it is on the web or relative to the hyperlink base
                    else:
                        # On the web
                        if str(path).lower().find("http") > -1 or str(path).lower().find("www") > -1:
                            for row in scur:
                                path = row[1]
                                try:
                                    # Go through search cur, download file and write oid and new path
                                    u = urlopen(path)
                                    newname = os.path.join(str(filedir), os.path.basename(path))
                                    localFile = open(newname, "wb")
                                    localFile.write(u.read())
                                    localFile.close()
                                    writer.writerow([str(row[0]), newname])
                                except:
                                    arcpy.AddWarning("Cannot process file {0} for OID {1}".format(row[1], row[0]))
                                finally:
                                    arcpy.SetProgressorPosition()
                            # Enable geodatabase attachments and write intermediate files to gdb
                            f.close()
                            arcpy.management.EnableAttachments(in_dataset)
                            arcpy.management.AddAttachments(in_dataset, oidfield, matchtable, "OID", "FILE")
                        # Relative to hyperlink base?
                        else:
                            if hyperlinkDir:
                                # If the hyperlinked path exists it is a file on disk or network location
                                if os.path.exists(os.path.join(hyperlinkDir, path)):
                                    arcpy.management.EnableAttachments(in_dataset)
                                    arcpy.management.AddAttachments(in_dataset, oidfield, in_dataset, oidfield, field, hyperlinkDir)
                                    arcpy.AddWarning(arcpy.GetMessages(1))
                                    arcpy.SetProgressorPosition(count)
                                # Else, the hyperlink path might be to web
                                elif str(hyperlinkDir).lower().find("http") > -1 or str(hyperlinkDir).lower().find("www") > -1:
                                    for row in scur:
                                        path = str(hyperlinkDir) + "/" + str(row[1])
                                        try:
                                            # Go through search cur, download file and write oid and new path
                                            u = urlopen(path)
                                            newname = os.path.join(str(filedir), os.path.basename(path))
                                            localFile = open(newname, "wb")
                                            localFile.write(u.read())
                                            localFile.close()
                                            writer.writerow([str(row[0]), newname])
                                        except:
                                            arcpy.AddWarning("Cannot process file {0} for OID {1}".format(row[0], row[1]))
                                        finally:
                                            arcpy.SetProgressorPosition()
                                    # Enable geodatabase attachments and write intermediate files to gdb
                                    f.close()
                                    arcpy.management.EnableAttachments(in_dataset)
                                    arcpy.management.AddAttachments(in_dataset, oidfield, matchtable, "OID", "FILE")
                                else:
                                    arcpy.AddWarning("The first record in field '{0}' does not contain a valid path. Processing will not continue.".format(field))
                            else:
                                arcpy.AddWarning("The first record in field '{0}' does not contain a valid path. Processing will not continue.".format(field))

    except:
        raise
    finally:
        if filedir:
            # Delete the temporary folder
            arcpy.management.Delete(filedir)

# Run the script
if __name__ == '__main__':
    # Get Parameters
    in_dataset = arcpy.GetParameterAsText(0)
    field = arcpy.GetParameterAsText(1)
    ftype = re.sub(r'\W+', '', arcpy.GetParameterAsText(2).upper())
    try:
        hyperlinkDir = arcpy.mapping.MapDocument("current").hyperlinkBase
    except:
        hyperlinkDir = ""

    ToAttachments(in_dataset, field, ftype, hyperlinkDir)
    arcpy.SetParameterAsText(3, in_dataset)
    print ("finished")