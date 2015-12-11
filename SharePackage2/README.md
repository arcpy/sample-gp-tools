##Share Package 2

Uploads a package to ArcGIS.com or your portal.
This tool, an enhancement to the original [Share Package](http://desktop.arcgis.com/en/desktop/latest/tools/data-management-toolbox/share-package.htm) tool works both inside the app (ArcMap/ArcGIS Pro) as well as command line. If you are inside the application and signed in, it will use that account. Else you can provide a username and password.


### Parameters

**Input Package** | *file* | required input
* Input package. Can be any of layer (.lpk, .lpkx), map (.mpk, .mpkx), geoprocessing (.gpk, .gpkx), map tile (.tpk), address locator (.gcpk) or project (.ppkx, .aptx) package file.

**Username** | *string* | required input
* Username for the portal. If using the tool inside ArcMap or ArcGIS Pro and signed in, this option will be unavailable.

**Password** | *hidden string* | required input
* Password for the portal. If using the tool inside ArcMap or ArcGIS Pro and signed in, this option will be unavailable.

**Summary** | *string* | required input
* Summary of the package

**Tags** | *string* | required input
* Tags to help make the package searchable

**Credits** | *string* | optional input
* Package credits

**Everybody** | *boolean* | optional input
* Share with 'everybody' in the portal.

**Groups** | *string* | optional input
* Share with specific groups in the portal

**Organization** | *boolean* | optional input
* Share within your organization.

**output** | *boolean* | derived output
* Boolean flag set to True if upload succeeded.

### General Usage

Requires 10.3.1+ (uses the [arcpy.GetActivePortalURL](http://desktop.arcgis.com/en/desktop/latest/analyze/arcpy-functions/getactiveportalurl.htm) to obtain the active portal)

