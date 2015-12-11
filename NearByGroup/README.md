##Near By Group

Determines the distance from each feature in the Input Features to the nearest feature with the same attributes in the Near Features.

[Downloadable ArcGIS.com sample](http://www.arcgis.com/home/item.html?id=37dbbaa29baa467d9da8e27d87d8ad45)


### Parameters

**Input Features** | *feature layer* | required input
* The input layer or feature class.

**Group Field(s)** | *Fields* | required input
* The field(s) containing the key attributes for how groups are defined in the input and near features. This process finds for each input feature the nearest near feature with the attributes matching in these field(s). 
The group field(s) must exist in the input features and near features datasets.
One or more fields can be specified. 

**Near Features** | *Feature Layer* | required input
* The features that will be evaluated to find the nearest feature with attributes matching each input feature.
One or more layers or feature classes can be specified.
The near features can be the same layer or feature class as the input features.

**Search Radius** |  *Linear Unit* | optional input
* Specifies the maximum distance used to search for near features. If there is no matching near feature within this distance of an input feature, the NEAR_OID, etc. fields in the output will be NULL. 


### General Usage

Determines the distance from each feature in the Input Features to the nearest feature with the same attributes in the Near Features.

### Software Requirements:

* ArcGIS 10.0 or later

* ArcInfo (Advanced) license
