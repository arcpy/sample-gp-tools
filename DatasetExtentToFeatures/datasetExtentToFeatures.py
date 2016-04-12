import arcpy
import os

def execute(in_datasets, out_fc):
    # use gcs as output sr since all extents will fit in it
    out_sr = arcpy.SpatialReference("WGS 1984")

    in_datasets = in_datasets.split(";")

    arcpy.CreateFeatureclass_management(os.path.dirname(out_fc),
                                        os.path.basename(out_fc),
                                        "POLYGON",
                                        spatial_reference=out_sr)

    arcpy.AddField_management(out_fc, "dataset", "TEXT", 400)

    # add each dataset's extent & the dataset's name to the output
    with arcpy.da.InsertCursor(out_fc, ("SHAPE@", "dataset")) as cur:

        for i in in_datasets:
            d = arcpy.Describe(i)
            ex = d.Extent
            pts = arcpy.Array([arcpy.Point(ex.XMin, ex.YMin),
                              arcpy.Point(ex.XMin, ex.YMax),
                              arcpy.Point(ex.XMax, ex.YMax),
                              arcpy.Point(ex.XMax, ex.YMin),
                              arcpy.Point(ex.XMin, ex.YMin),])

            geom = arcpy.Polygon(pts,  d.SpatialReference)

            if d.SpatialReference != out_sr:
                geom = geom.projectAs(out_sr)
            cur.insertRow([geom, d.CatalogPath])


if __name__ == "__main__":
    execute(arcpy.GetParameterAsText(0), arcpy.GetParameterAsText(1))
