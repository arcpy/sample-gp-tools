##Share Package 2

Uploads a package to ArcGIS.com or your portal.
This tool, an enhancement to the original [Share Package](http://desktop.arcgis.com/en/desktop/latest/tools/data-management-toolbox/share-package.htm) tool works both inside the app (ArcMap/ArcGIS Pro) as well as command line. If you are inside the application and signed in, it will use that account. Else you can provide a username and password.

March 2015 - This tool has been enhanced with additional parameters. The parameter order has changed since the original version. Existing scripts calling this tool may need to be updated.


### Parameters

**Input Package** | *file* | required input
* Input package. Can be any of layer (.lpk, .lpkx), map (.mpk, .mpkx), geoprocessing (.gpk, .gpkx), map tile (.tpk), address locator (.gcpk) project (.ppkx, .aptx) or other type of ArcGIS package file.

**Folder** | *string* | required input
* Name of the folder to upload package too. If the folder does not exist, it will be created. A value of <root> or blank will upload the package to the root directory.

**Username** | *string* | required input
* Username for the portal. If using the tool inside ArcMap or ArcGIS Pro and signed in, this option will be unavailable.

**Password** | *hidden string* | required input
* Password for the portal. If using the tool inside ArcMap or ArcGIS Pro and signed in, this option will be unavailable.

**Maintain item's metadata** | *boolean* | required input
* Use this option to maintain the metadata when overwriting an existing package. The tools behavior is to overwrite a package if it already exists on the portal. This option will save the original metadata (description, tags, credits, etc) and apply them to the updated package.

**Summary** | *string* | required input
* Summary of the package

**Tags** | *string* | required input
* Tags to help make the package searchable

**Credits** | *string* | optional input
* Package credits

**Everyone** | *boolean* | optional input
* Share with 'everybody' in the portal.

**Organization** | *boolean* | optional input
* Share within your organization.

**Groups** | *string* | optional input
* Share with specific groups in the portal

**output** | *boolean* | derived output
* Boolean flag set to True if upload succeeded.

### General Usage

Requires 10.3.1+ (uses the [arcpy.GetActivePortalURL](http://desktop.arcgis.com/en/desktop/latest/analyze/arcpy-functions/getactiveportalurl.htm) to obtain the active portal)

