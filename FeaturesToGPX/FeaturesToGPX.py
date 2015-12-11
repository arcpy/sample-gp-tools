'''
Tool Name:  Features to GPX
Source Name: FeaturesToGPX.py
Version: ArcGIS 10.1+ or ArcGIS Pro 1.0+
Author: Esri
Contributors: Matt Wilkie
   (https://github.com/maphew/arcgiscom_tools/blob/master/Features_to_GPX/FeaturesToGPX.py)

Required Arguments:
    Input Features (features): path to layer or featureclass on disk
    Output Feature Class (file): path to GPX which will be created
Optional Arguements:
    Zero date (boolean): If no date exists, use this option to force dates to epcoh
        start, 1970-Jan-01. This will allow GPX files to open in Garmin Basecamp
    Pretty (boolean): Output gpx file will be "pretty", or easier to read.

Description:
    This tool takes input features (layers or featureclass) with either point or
    line geometry and converts into a .GPX file. Points and multipoint features
    are converted in to WPTs, lines are converted into TRKS. If the features conform
    to a known schema, the output GPX file will honor those fields.
'''

try:
    from xml.etree import cElementTree as ET
except:
    from xml.etree import ElementTree as ET
import arcpy
import time
import datetime
unicode = str

gpx = ET.Element("gpx", xmlns="http://www.topografix.com/GPX/1/1",
                 xalan="http://xml.apache.org/xalan",
                 xsi="http://www.w3.org/2001/XMLSchema-instance",
                 creator="Esri",
                 version="1.1")


def prettify(elem):
    """Return a pretty-printed XML string for the Element.
    """
    from xml.dom import minidom
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")



def featuresToGPX(inputFC, outGPX, zerodate, pretty):
    ''' This is called by the __main__ if run from a tool or at the command line
    '''

    descInput = arcpy.Describe(inputFC)
    if descInput.spatialReference.factoryCode != 4326:
        arcpy.AddWarning("Input data is not projected in WGS84,"
                         " features were reprojected on the fly to create the GPX.")

    generatePointsFromFeatures(inputFC , descInput, zerodate)

    # Write the output GPX file
    try:
        if pretty:
            gpxFile = open(outGPX, "w")
            gpxFile.write(prettify(gpx))
        else:
            gpxFile = open(outGPX, "wb")
            ET.ElementTree(gpx).write(gpxFile, encoding="UTF-8", xml_declaration=True)
    except TypeError as e:
        arcpy.AddError("Error serializing GPX into the file.")
    finally:
        gpxFile.close()



def generatePointsFromFeatures(inputFC, descInput, zerodate=False):

    def attHelper(row):
        # helper function to get/set field attributes for output gpx file

        pnt = row[1].getPart()
        valuesDict["PNTX"] = str(pnt.X)
        valuesDict["PNTY"] = str(pnt.Y)

        Z = pnt.Z if descInput.hasZ else None
        if Z or ("ELEVATION" in cursorFields):
            valuesDict["ELEVATION"] = str(Z) if Z else str(row[fieldNameDict["ELEVATION"]])
        else:
            valuesDict["ELEVATION"] = str(0)

        valuesDict["NAME"] = row[fieldNameDict["NAME"]] if "NAME" in fields else " "
        valuesDict["DESCRIPT"] = row[fieldNameDict["DESCRIPT"]] if "DESCRIPT" in fields else " "


        if "DATETIMES" in fields:
            row_time = row[fieldNameDict["DATETIMES"]]
            formatted_time = row_time if row_time else " "
        elif zerodate and "DATETIMES" not in fields:
            formatted_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(0))
        else:
            formatted_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(0)) if zerodate else " "

        valuesDict["DATETIMES"] = formatted_time

        return
    #-------------end helper function-----------------


    def getValuesFromFC(inputFC, cursorFields ):

        previousPartNum = 0
        startTrack = True

        # Loop through all features and parts
        with arcpy.da.SearchCursor(inputFC, cursorFields, spatial_reference="4326", explode_to_points=True) as searchCur:
            for row in searchCur:
                if descInput.shapeType == "Polyline":
                    for part in row:
                        newPart = False
                        if not row[0] == previousPartNum or startTrack is True:
                            startTrack = False
                            newPart = True
                        previousPartNum = row[0]

                        attHelper(row)
                        yield "trk", newPart

                elif descInput.shapeType == "Multipoint" or descInput.shapeType == "Point":
                    # check to see if data was original GPX with "Type" of "TRKPT" or "WPT"
                    trkType = row[fieldNameDict["TYPE"]].upper() if "TYPE" in fields else None

                    attHelper(row)

                    if trkType == "TRKPT":
                        newPart = False
                        if previousPartNum == 0:
                            newPart = True
                            previousPartNum = 1

                        yield "trk", newPart

                    else:
                        yield "wpt", None

    # ---------end get values function-------------


    # Get list of available fields
    fields = [f.name.upper() for f in arcpy.ListFields(inputFC)]
    valuesDict = {"ELEVATION": 0, "NAME": "", "DESCRIPT": "", "DATETIMES": "", "TYPE": "", "PNTX": 0, "PNTY": 0}
    fieldNameDict = {"ELEVATION": 0, "NAME": 1, "DESCRIPT": 2, "DATETIMES": 3, "TYPE": 4, "PNTX": 5, "PNTY": 6}

    cursorFields = ["OID@", "SHAPE@"]

    for key, item in valuesDict.items():
        if key in fields:
            fieldNameDict[key] = len(cursorFields)  # assign current index
            cursorFields.append(key)   # build up list of fields for cursor
        else:
            fieldNameDict[key] = None

    for index, gpxValues in enumerate(getValuesFromFC(inputFC, cursorFields)):

        if gpxValues[0] == "wpt":
            wpt = ET.SubElement(gpx, 'wpt', {'lon':valuesDict["PNTX"], 'lat':valuesDict["PNTY"]})
            wptEle = ET.SubElement(wpt, "ele")
            wptEle.text = valuesDict["ELEVATION"]
            wptTime = ET.SubElement(wpt, "time")
            wptTime.text = valuesDict["DATETIMES"]
            wptName = ET.SubElement(wpt, "name")
            wptName.text = valuesDict["NAME"]
            wptDesc = ET.SubElement(wpt, "desc")
            wptDesc.text = valuesDict["DESCRIPT"]

        else:  #TRKS
            if gpxValues[1]:
                # Elements for the start of a new track
                trk = ET.SubElement(gpx, "trk")
                trkName = ET.SubElement(trk, "name")
                trkName.text = valuesDict["NAME"]
                trkDesc = ET.SubElement(trk, "desc")
                trkDesc.text = valuesDict["DESCRIPT"]
                trkSeg = ET.SubElement(trk, "trkseg")

            trkPt = ET.SubElement(trkSeg, "trkpt", {'lon':valuesDict["PNTX"], 'lat':valuesDict["PNTY"]})
            trkPtEle = ET.SubElement(trkPt, "ele")
            trkPtEle.text = valuesDict["ELEVATION"]
            trkPtTime = ET.SubElement(trkPt, "time")
            trkPtTime.text = valuesDict["DATETIMES"]



if __name__ == "__main__":
    ''' Gather tool inputs and pass them to featuresToGPX
    '''

    inputFC = arcpy.GetParameterAsText(0)
    outGPX = arcpy.GetParameterAsText(1)
    zerodate = arcpy.GetParameter(2)
    pretty = arcpy.GetParameter(3)
    featuresToGPX(inputFC, outGPX, zerodate, pretty)
