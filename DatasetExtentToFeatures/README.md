
###DatasetExtentToFeatures
Geoprocessing tool that takes many geodataset as input, and creates a new polygon feature class of the extent of the input geodatasets. 

### Parameters

**Input datasets** | *Geodataset or Feature Layer* | required input
* The input geodataset. This can be a feature class, or raster.

**Output Featureclass** | *Feature Class* | required output
* The output feature class.  This feature class will contain one polygon for each of the input geodataset.  The output will be in WGS 1984 Geographic coordinate system.  This is to insure that datasets with disparate extents and coordinate systems can all be successfully stored in the output feature class.  


![DatasetExtentToFeatures Image](https://github.com/arcpy/sample-gp-tools/raw/master/src/DatasetExtentToFeatures.png "Inputs of various types, output rendered as hashed polygons")
