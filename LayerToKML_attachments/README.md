##Layer to KML with attachments

Converts a layer featureclass into a KMZ file and insert images from attachments into the output KMZ popup.

Originally posted to [ArcGIS.com as a sample](http://www.arcgis.com/home/item.html?id=5d8704c938ea4715b59eebabcd96c1d9). Original idea from a [GIS.SE question](http://gis.stackexchange.com/questions/119341/error-exporting-arcmap-feature-to-kml-retain-attached-photo)

### Parameters

**Input Layer** | *feature layer* | required input
* Input feature layer (must be a layer, not featureclass reference from disk)

**Output KMZ** | *file* | required output
* Output GPX file to be created

**Output scale** | *long* | optional input
* The scale at which to export the layer. This parameter is used with any scale dependency, such as layer visibility or scale-dependent rendering. Any value, such as 0, can be used if there are no scale dependencies.

**Clamped to ground** |  *boolean* | optional input
* Checked — You can override the Z-values inside your features or force them to be clamped to the ground. You should use this setting if you are not working with 3D features or have features with Z-values that might not honor values relative to sea level. 

**Allow Unique ID Field** |  *boolean* | optional input
* Checked — Allows a new ID (ObjectID) field to be added to the input features. This field is only necessary if the input features do not maintain sequential IDs (OID = 1,2,3,4, etc). The field will be removed from your data when the tool completes. If your data has sequential IDs, this setting will not do anything. Unchecked (false) is the default.

**Height** |  *long* | optional input
* Any numeric value will be used to set the *IMG* height within the KML PopUp. Use this value to force all image attachments to be a certain size. 

**Width** |  *long* | optional input
* Any numeric value will be used to set the *IMG* height within the KML PopUp. Use this value to force all image attachments to be a certain size. 

### General Usage

This tool creates a KMZ file from input features and inserts any attachments found into the output KMZ file. The current implementation of the Layer to KML tool does not export attachments. This tool works by first creating the KML file, then modifying this new KML by adding references to the attachments. The exported attachments are saved into the KMZ file.


