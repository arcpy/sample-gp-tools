## GPX to Features

Converts features (layers and feature classes of schema; point, multipoint and polyline) into GPX files.

Originally posted to [ArcGIS.com as a sample](http://www.arcgis.com/home/item.html?id=067d6ab392b24497b8466eb8447ea7eb), this tool is the sibiling to the [GPX to Features](https://pro.arcgis.com/en/pro-app/tool-reference/conversion/gpx-to-features.htm) tool available in both ArcGIS Pro and ArcMap.

### Parameters

**Input Features** | *feature layer* | required input
* Input featureclass or feature layer

**Output GPX** | *file* | required output
* Output GPX file to be created

**Zero dates (support Garmin Basecamp)** | *boolean* | optional input
* Create 0 date (JAN-1-1970). If a string field named 'DateTimeS' exists, the values from this field will be used to populate the output GPX file. If this field does not exist, an empty string is used for the date. Garmin Basecamp software requires a valid date. Select this option to insert the JAN-1-1970 (epoch) date into your output GPX file if your features do not have a date field.

**Pretty output** |  *boolean* | optional input
*Format the output GPX file to be formatted in a nicer way. ie. human readable. This does not impact hardware and software devices ability to read the output file.

### General Usage

The tool takes both points and line feature classes as input.

Line features will be turned into Tracks (TRKS)

Point features will be turned into WayPoints (WPT)

**Note**: GPX uses the WGS84 coordinate system. If the input data is not in WGS84, the conversion to GPX will reproject the data. If a transformation is required the best match possible is used. For complete reprojection control you should run the Project tool, converting your data into WGS84 and choosing the correct transformation prior to creating a GPX file.

Note: Features with the following fields will be used in creating output GPX. Output from the GPX to Features tool (v. 10.1+) creates features with these fields. 

* Name

* Descript

* Type

* Elevation

* DateTimeS (of type String)

Point features with the field "Type" and a value of "TRKPT" will be turned into Tracks (TRKS)


