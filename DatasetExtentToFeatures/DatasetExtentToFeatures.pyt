import arcpy
import os
import json

class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "Dataset Extent To Features"
        self.alias = "ext"

        # List of tool classes associated with this toolbox
        self.tools = [DatasetExtentToFeatures]

class DatasetExtentToFeatures(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Dataset Extent To Features"
        self.description = ""

    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(
            displayName="Input Datasets",
            name="in_datasets",
            datatype=["DEGeodatasetType", "GPFeatureLayer"],
            parameterType="Required",
            direction="Input",
            multiValue=True)

        param1 = arcpy.Parameter(
            displayName="Output Featureclass",
            name="out_featureclass",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Output",)

        return [param0, param1]

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        import datasetExtentToFeatures

        # execute is external so can call it directly from other modules
        datasetExtentToFeatures.execute(parameters[0].valueAsText, parameters[1].valueAsText)
