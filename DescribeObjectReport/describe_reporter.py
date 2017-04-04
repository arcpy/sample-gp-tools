""" describe_reporter.py
    Andrew Ortego
    8/24/2016    

    TODO
    * Alter output with pprint so that it's all aligned (see output formatting)
    * Web-scrape script which gathering all Desc. object properties
    * Handle properties that have no attributes (currently commented)

    DESCRIPTION
    Creates a report of all arcpy describe-object properties for an object.

    INPUT
    Command line arguments must include a verbose or terse flag (-v or -t) as
    the first arguement. The difference between the two is that verbose will
    show you the attributes that have no value, whereas terse will not.
    Subsequent arguements are each of the describe properties being asked for 
    in the report. These are optional, and all properties will be reported if 
    these arguements are not provided.

    CAVEATS
    * The output will be overwritten unless you change the output's path.
    
    SAMPLE USAGE
    > python describe_reporter.py -v
    > python describe_reporter.py -t
    > python describe_reporter.py -v "General Describe" "Layer" "Table"
    > python describe_reporter.py -t "General Describe" "Workspace"

    SAMPLE OUTPUT (in terse mode)
    {
        Filename 1: {
            Describe Object Class 1: {
                Property 1: output,
                Propetry 2: {},
            }
        }
        Filename 2: 'FILE NOT FOUND'
    }
"""

import arcpy
import pickle, os, sys, time
from pprint import pprint
from functools import wraps
from collections import OrderedDict as od
try:
    from file_list import user_files
except ImportError as e:
    print("ERROR: Could not find list of files to be scanned. Please verify")
    print("that file_list.py is in the same directory as this script, and")
    print("that it contains a list called user_files which holds each path")
    print("to your files.")
    print("EXAMPLE: user_files = [u'C:\\Users\\andr7495\\Desktop\\KML.kml']")
    raise SystemExit

properties = {
    'General Describe': {
        'baseName', 
        'catalogPath', 
        'children', 
        'childrenExpanded', 
        'dataElementType', 
        'dataType', 
        'extension', 
        'file', 
        'fullPropsRetrieved', 
        'metadataRetrieved', 
        'name',
        'path',
    },

    'ArcInfo Workstation Item': {
        'alternateName',
        'isIndexed',
        'isPseudo',
        'isRedefined',
        'itemType',
        'numberDecimals',
        'outputWidth',
        'startPosition',
        'width',
    },

    'ArcInfo Workstation Table': {
        'itemSet',
    },

    'CAD Drawing Dataset': {
        'is2D',
        'is3D',
        'isAutoCAD',
        'isDGN',
        },

    #'CAD FeatureClass': {},

    'Cadastral Fabric': {
        'bufferDistanceForAdjustment',
        'compiledAccuracyCategory',
        'defaultAccuracyCategory',
        'maximumShiftThreshold',
        'multiGenerationEditing',
        'multiLevelReconcile',
        'pinAdjustmentBoundary',
        'pinAdjustmentPointsWithinBoundary',
        'surrogateVersion',
        'type',
        'version',
        'writeAdjustmentVectors',
        },

    'Coverage FeatureClass': {
        'featureClassType',
        'hasFAT',
        'topology',
        },

    'Coverage': {
        'tolerances',
        },

    'Dataset': {
        'canVersion',
        'changeTracked',
        'datasetType',
        'DSID',
        'extent',
        'isArchived',
        'isVersioned',
        'MExtent',
        'spatialReference',
        'ZExtent',
        },

    #'dBase': {},

    'FeatureClass': {
        'featureType',
        'hasM',
        'hasZ',
        'hasSpatialIndex',
        'shapeFieldName',
        'shapeType',
        },

    'GDB FeatureClass': {
        'areaFieldName',
        'geometryStorage',
        'lengthFieldName',
        'representations',
        },

    'GDB Table': {
        'aliasName',
        'defaultSubtypeCode',
        'extensionProperties',
        'globalIDFieldName',
        'hasGlobalID',
        'modelName',
        'rasterFieldName',
        'relationshipClassNames',
        'subtypeFieldName',
        'versionedView',
        },

    'Geometric Network': {
        'featureClassNames',
        'networkType',
        'orphanJunctionFeatureClassName',
        },

    'LAS Dataset': {
        'constraintCount',
        'fileCount',
        'hasStatistics',
        'needsUpdateStatistics',
        'pointCount',
        'usesRelativePath',
        },

    'Layer': {
        'dataElement',
        'featureClass',
        'FIDSet',
        'fieldInfo',
        'layer',
        'nameString',
        'table',
        'whereClause',
        },

    #'Map Document': {},

    'Moscaic Dataset': {
        'allowedCompressionMethods',
        'allowedFields',
        'allowedMensurationCapabilities',
        'allowedMosaicMethods',
        'applyColorCorrection',
        'blendWidth',
        'blendWidthUnits',
        'cellSizeToleranceFactor',
        'childrenNames',
        'clipToBoundary',
        'clipToFootprint',
        'defaultCompressionMethod',
        'defaultMensurationCapability',
        'defaultMosaicMethod',
        'MosaicOperator',
        'defaultResamplingMethod',
        'SortAscending',
        'endTimeField',
        'footprintMayContainNoData',
        'GCSTransforms',
        'JPEGQuality',
        'LERCTolerance',
        'maxDownloadImageCount',
        'maxDownloadSizeLimit',
        'maxRastersPerMosaic',
        'maxRecordsReturned',
        'maxRequestSizeX',
        'maxRequestSizeY',
        'minimumPixelContribution',
        'orderBaseValue',
        'orderField',
        'rasterMetadataLevel',
        'referenced',
        'startTimeField',
        'timeValueFormat',
        'useTime',
        'viewpointSpacingX',
        'viewpointSpacingY',
        },

    'Network Analyst Layer': {
        'network',
        'nameString',
        'solverName',
        'impedance',
        'accumulators',
        'restrictions',
        'ignoreInvalidLocations',
        'uTurns',
        'useHierarchy',
        'hierarchyAttribute',
        'hierarchyLevelCount',
        'maxValueForHierarchyX',
        'locatorCount',
        'locators',
        'findClosest',
        'searchTolerance',
        'excludeRestrictedElements',
        'solverProperties',
        'children',
        'parameterCount',
        'parameters',
        },

    'Prj File': {
        'spatialReference',
        },


    'Raster Band': {
        'height',
        'isInteger',
        'meanCellHeight',
        'meanCellWidth',
        'noDataValue',
        'pixelType',
        'primaryField',
        'tableType',
        'width',
        },


    'Raster Catalog': {
        'rasterFieldName',
        },

    'Raster Dataset': {
        'bandCount',
        'compressionType',
        'format',
        'permanent',
        'sensorType',
        },

    'RecordSet and FeatureSet': {
        'json',
        'pjson',
        },

    'RelationshipClass': {
        'backwardPathLabel',
        'cardinality',
        'classKey',
        'destinationClassKeys',
        'destinationClassNames',
        'forwardPathLabel',
        'isAttachmentRelationship',
        'isAttributed',
        'isComposite',
        'isReflexive',
        'keyType',
        'notification',
        'originClassNames',
        'originClassKeys',
        'relationshipRules',
        },

    'RepresentationClass': {
        'backwardPathLabel',
        'cardinality',
        'classKey',
        'destinationClassKeys',
        'destinationClassNames',
        'forwardPathLabel',
        'isAttachmentRelationship',
        'isAttributed',
        'isComposite',
        'isReflexive',
        'keyType',
        'notification',
        'originClassNames',
        'originClassKeys',
        'relationshipRules',
        },

    #'Schematic Dataset': {},

    'Schematic Diagram': {
        'diagramClassName',
        },

    #'Schematic Folder': {},

    #'SDC FeatureClass': {},

    #'Shapefile FeatureClass': {},

    'Table': {
        'hasOID',
        'OIDFieldName',
        'fields',
        'indexes',
        },

    'TableView': {
        'table',
        'FIDSet',
        'fieldInfo',
        'whereClause',
        'nameString',
        },

    #'Text File': {},

    'Tin': {
        'fields',
        'hasEdgeTagValues',
        'hasNodeTagValues',
        'hasTriangleTagValues',
        'isDelaunay',
        'ZFactor',
        },

    #'Tool': {},

    #'Toolbox': {},

    'Topology': {
        'clusterTolerance',
        'featureClassNames',
        'maximumGeneratedErrorCount',
        'ZClusterTolerance',
        },

    #'VPF Coverage': {},

    #'VPF FeatureClass': {},

    #VPF Table': {},

    'Workspace': {
        'connectionProperties',
        'connectionString',
        'currentRelease',
        'domains',
        'release',
        'workspaceFactoryProgID',
        'workspaceType',
        },
}

def timethis(func):
    """ Decorator that reports the execution time.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print("Created {0} in {1}s".format(
            os.path.join(os.getcwd(), u'Describe Report.txt'), 
            round(end-start)))
        return result
    return wrapper

def set_mode(user_input):
    """ Check whether the user has select verbose or terse mode. This is set
        with the -v or -t flags, respectively.
    """
    try:
        if user_input[1] not in ["-v", "-t"]:
            print("ERROR   : Report mode not selected.")
            print("SOLUTION: Use -v or -t (verbose or terse) as first arguement.")
            print("EXAMPLE : > python describe_reporter.py -v Layer Table Workspace")
            raise SystemExit
    except IndexError:
        print("ERROR   : Report mode not selected.")
        print("SOLUTION: Use -v or -t (verbose or terse) as first arguement.")
        print("EXAMPLE : > python describe_reporter.py -v Layer Table Workspace")
        raise SystemExit
    return user_input[1] == "-v"


def check_prop_list(user_types):
    """ Verify that the user has entered valid Describe Object types/classes and
        print a warning message for any invalid choices. If no arguments are 
        provided, the report will print all Describe properties.Returns a list 
        of Describe properties whose attributes will be included in the report.
    """
    if not user_types:
        queried_types = [p for p in properties]
    else:
        invalid_types = list()
        queried_types = list()
        [queried_types.append(k) if k in properties else invalid_types.append(k) for k in user_types]
        if invalid_types:
            print("WARNING! Describe Types will not be included in report:")
            for t in invalid_types:
                print(t)
    return queried_types


@timethis
def generate_report(verbose_mode, property_list, user_files):
    """ Generates the report containing each file and its associated 
        Describe-object attributes. Report is a dictionary and can be useful
        for other scripts.
    """
    report_results = {}
    report_path = open(os.path.join(os.getcwd(), u'Describe Report.txt'), 'wt')
    for f in user_files:
        if arcpy.Exists(f):
            desc_dict = od()
            for d_class in sorted(property_list):
                desc_dict[d_class] = {}
                for p in properties[d_class]:
                    try:
                        desc_dict[d_class][p] = eval("arcpy.Describe(f).{0}".format(p))
                    except AttributeError:
                        if verbose_mode:
                            desc_dict[d_class][p] = 'ATTRIBUTE ERROR: Method not found'
                        else:
                            pass
            report_results[f] = desc_dict
        else:
            report_results[f] = 'FILE NOT FOUND'
    pprint(report_results, report_path, width=400)


if __name__ == "__main__":
    """ Collect user input, check report mode, clean list of properties to be
        reported, and generate the report.
    """
    user_input = [arg for arg in sys.argv]
    verbose_mode = set_mode(user_input)
    cleaned_user_types = check_prop_list(user_input[2:])
    generate_report(verbose_mode, cleaned_user_types, user_files)
    print('\nfin.')

