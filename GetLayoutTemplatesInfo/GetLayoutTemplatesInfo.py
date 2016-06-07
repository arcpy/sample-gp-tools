# Retrieve metadata for all .mxd available in the specified folder
#    each .mxd is considered as a layout template in a printing service.
#    


# Import required modules
#
import sys
import os
import arcpy
import json
import glob
import xml.dom.minidom as DOM

# default location
#
_defTmpltFolder = os.path.join(arcpy.GetInstallInfo()['InstallDir'], r"Templates\ExportWebMapTemplates")

# Defining a custom JSONEncoder for MapDocument object
#
class MxdEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, arcpy.mapping.MapDocument):
            d = {}

            # Layout_Template name
            d["layoutTemplate"] = os.path.splitext(os.path.basename(obj.filePath))[0]

            # Page size
            ps = obj.pageSize
            d["pageSize"] = [ps.width, ps.height]

            # Size of the active dataframe element on the layout
            adf = obj.activeDataFrame
            d["activeDataFrameSize"] = [adf.elementWidth, adf.elementHeight]

            # Layout options containing information about layout elements
            lo = {}
            d["layoutOptions"] = lo
            lo["hasTitleText"] = False
            lo["hasAuthorText"] = False
            lo["hasCopyrightText"] = False
            lo["hasLegend"] = False

            # Is a legend element available whose parent dataframe name is same as the active dataframe's name
            for l in arcpy.mapping.ListLayoutElements(obj, "LEGEND_ELEMENT"):
                if (l.parentDataFrameName == adf.name):
                    lo["hasLegend"] = True
                    break

            # Availability of text elements - both predefined and user-defined
            ct = []     #an array contains custom text elements - each as a separate dictionary
            lo["customTextElements"] = ct
            for t in arcpy.mapping.ListLayoutElements(obj, "TEXT_ELEMENT"):
                try:    #processing dynamic-text-elements with xml tags
                    x = DOM.parseString(t.text)
                    r = x.childNodes[0]
                    if (r.tagName == "dyn") and (r.getAttribute("type") == "document"): #predefined with specific dynamic-text (i.e. xml tag)
                        if (r.getAttribute("property") == "title"):
                            lo["hasTitleText"] = True
                        if (r.getAttribute("property") == "author"):
                            lo["hasAuthorText"] = True
                        if (r.getAttribute("property") == "credits"):
                            lo["hasCopyrightText"] = True
                except:    #processing other text elements that have 'names'
                    if (len(t.name.strip()) > 0):
                        ct.append({t.name: t.text})

            return d
        return json.JSONEncoder.default(self, obj)


# Main module
#
def main():
    # Get the value of the input parameter
    #
    tmpltFolder = arcpy.GetParameterAsText(0)

    # When empty, it falls back to the default template location like ExportWebMap tool does
    #
    if (len(tmpltFolder) == 0):
        tmpltFolder = _defTmpltFolder

    # Getting a list of all file paths with .mxd extensions
    #    createing MapDocument objects and putting them in an array
    #
    mxds    = []
    for f in glob.glob(os.path.join(tmpltFolder, "*.mxd")):
        try:    #throw exception when MapDocument is corrupted
            mxds.append(arcpy.mapping.MapDocument(f))
        except:
            arcpy.AddWarning("Unable to open map document named {0}".format(os.path.basename(f)))
            

    # Encoding the array of MapDocument to JSON using a custom JSONEncoder class
    #
    outJSON = json.dumps(mxds, cls=MxdEncoder, indent=2)
    
    # Set output parameter
    #
    arcpy.SetParameterAsText(1, outJSON)
    
    # Clean up
    #
    del mxds


if __name__ == "__main__":
    main()