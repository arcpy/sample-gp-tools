# SampleTools

These tools are provided by Esri as samples to be used with ArcGIS Desktop (ArcMap, ArcCatalog, ArcGIS Pro, etc). No support is expressed or implied. Each tool has been documented with individual help in its given folder. Download an individual tool or clone the entire repository and use the **SampleTools.tbx**.

## Tools
* [Dataset Extent To Features](DatasetExtentToFeatures)
  * Creates a polygon for the extent of each input geodataset.
* [Features to GPX](FeaturesToGPX)
  * Convert features into a GPX file.
* [Layer To KML with Attachments](LayerToKML_attachments)
  * Converts a layer featureclass into a KMZ file and insert images from attachments into the output KMZ popup.
* [Near By Group](NearByGroup)
  * Determines the distance from each feature in the Input Features to the nearest feature with the same attributes in the Near Features.
* [Share Package 2](SharePackage2)
  * Uploads a package file to arcgis.com or your local portal.
* [To Attachments](ToAttachment)
  * Geoprocessing tool and script that converts the files stored or referenced in a dataset to geodatabase attachments. Files to be added as attachments can come from a Raster field, BLOB field, or text field containing a hyperlink or path.


### Contributing

Suggestions, fixes, and enhancements are welcome and encouraged. Use the ISSUES link to report problems. Please see our [guidelines for contributing](https://github.com/esri/contributing). Please use one branch per tool update.


### Requirements

* ArcGIS 10.0+, ArcGIS Pro 1.0+  (unless otherwise noted)

### Deployment

After downloading the entire repo, the _SampleTools.tbx_ can be deployed to your system toolbox for quick access by using the setup.py file. Run the following code from the directory the `setup.py` file exists at, using a proper reference to your _python.exe_

`C:\downloads\sample-gp-tools>c:\Python27\ArcGIS10.3\python.exe setup.py install `


### Licensing

Copyright 2015 Esri

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

A copy of the license is available in the repository's [license.txt](LICENSE) file.

[](Esri Tags: arcpy sample tool python script)
[](Esri Language: Python)​
