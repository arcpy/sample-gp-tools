# Describe-Object-Report

**Demonstrates**

    * Use of decorator
    * Command-line argument processing
    * Use of arcpy's extensive collection of Describe objects

**Description:**

    Creates a report of all arcpy describe-object properties for an object.

**Usage:**

    Command line arguments must include a verbose or terse flag (-v or -t) as
    the first arguement. The difference between the two is that verbose will
    show you the attributes that have no value, whereas terse will not.
    Subsequent arguements are each of the describe properties being asked for 
    in the report. These are optional, and all properties will be reported if 
    these arguements are not provided.

**Input:**

    NOTE: Be sure to update file_list.py before running!
    > python describe_reporter.py -v
    > python describe_reporter.py -t
    > python describe_reporter.py -v "General Describe" "Layer" "Table"
    > python describe_reporter.py -t "General Describe" "Workspace"

**Caveats**

    * The output will be overwritten unless you change the output's path in the source code

**Output Format (in terse mode)**

    {
        Filename 1: {
            Describe Object Class 1: {
                Property 1: output,
                Propetry 2: {},
            }
        }
        Filename 2: 'FILE NOT FOUND'
    }
