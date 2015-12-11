##Raster Field, BLOB, Or Hyperlink To Attachment

Geoprocessing tool and script that converts the files stored or referenced in a dataset to geodatabase attachments. Files to be added as attachments can come from a Raster field, BLOB field, or text field containing a hyperlink or path.

Originally posted to [ArcGIS.com as a sample](http://www.arcgis.com/home/item.html?id=473c510504f445d5a6d593cf1a7f1133).

### Parameters

**Input Dataset** | *Table View* | required input
* The input dataset containing a raster field, blob field, or path or hyperlink to a file to add to the input dataset as a geodatabase attachment. This can be a geodatabase feature class or table.

**Field** | *Field* | required output
* The attribute field from the input dataset containing an image/raster (Raster field), file (Blob field), or file path or hyperlink to be added to the input dataset as a geodatabase attachment.

**File Type** | *String* | optional input
* The file type of the files contained in the BLOB field. When the input field is a Blob field this must be accurately specified for files to be written correctly as geodatabase attachments. For Raster or Text fields, this parameter is managed automatically and can be left blank.

Common file types include: JPG, TIF, PNG, BMP, PDF, XML, TXT, DOC, XLS.

**Output Dataset** | *Dataset* | derived output

### General Usage

Converts the files stored or referenced in a dataset to geodatabase attachments. Files to be added as attachments can come from a Raster field, BLOB field, or text field containing a hyperlink or path.

