##Print Service Templates

This script tool is designed to work with ExportWebMap geoprocessing tool in order to facilitate printing from web applications.

This tool takes a folder location of map documents (.mxd files). The map files are layout templates and will be return as JSON (JavaScript object notation).

For more information about using this tool with the Printing Service, see the following help topics:
* [Get Layout Template tool](http://desktop.arcgis.com/en/arcmap/latest/tools/server-toolbox/get-layout-templates-info.htm)
* [Printing service tutorial](http://server.arcgis.com/en/server/latest/create-web-apps/windows/tutorial-publishing-additional-services-for-printing.htm)
  Note: step #8 in 'Preparing and publishing the service' section, use this tool instead of the system toolset.


### Parameters

**Layout Templates Folder** | *folder* | optional input
* The directory of map documents (mxd) to be used as layouts. If no input folder is given, the tool will use the ExportWebMapTemplates folder in the ArcGIS installation directory.

**Output JSON** | *string* | derived output
* The output JSON representing the map document (mxd).

### General Usage

Requires ArcMap/ArcGIS Server 10.1+ 

