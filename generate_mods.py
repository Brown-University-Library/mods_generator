#!/usr/bin/env python
'''Pass the name of the spreadsheet to this script and
it will generate individual mods files for each record
in the mods_files directory, logging the output to dataset_mods.log.
Run './generate_mods.py --help' to see various options.

Notes: 
1. The spreadsheet can be any version of Excel, or a CSV file.
2. See the test files for the format of the spreadsheet/csv file.
3. Unicode - all text strings from xlrd (for Excel files) are Unicode. For xlrd
    numbers, we convert those into Unicode, since we're just writing text out
    to files. The encoding of CSV files can be specified as an argument (if 
    it's not a valid encoding for Python, a LookupError will be raised). The
    encoding of the output files can also be specified as an argument (if
    there's an input character that can't be encoded in the output encoding, a
    UnicodeEncodeError will be raised).

'''
import sys
import os
from optparse import OptionParser
from mods_generator import DataHandler, process


if __name__ == '__main__':
    XML_FILES_DIR = "xml_files"
    parser = OptionParser()
    parser.add_option('-t', '--type',
                    action='store', dest='type', default='parent',
                    help='type of records (parent or child, default is parent)')
    parser.add_option('--force-dates',
                    action='store_true', dest='force_dates', default=False,
                    help='force date conversion even if ambiguous')
    parser.add_option('--copy-parent-to-children',
                    action='store_true', dest='copy_parent_to_children', default=False,
                    help='copy parent data into children')
    parser.add_option('-s', '--sheet',
                    action='store', dest='sheet', default=1,
                    help='specify the sheet number (starting at 1) in an Excel spreadsheet')
    parser.add_option('-r', '--ctrl_row',
                    action='store', dest='row', default=2,
                    help='specify the control row number (starting at 1) in an Excel spreadsheet')
    parser.add_option('-i', '--input-encoding',
                    action='store', dest='in_enc', default='utf-8',
                    help='specify the input encoding for CSV files (default is UTF-8)')
    (options, args) = parser.parse_args()
    #make sure we have a directory to put the mods files in
    try:
        os.makedirs(XML_FILES_DIR)
    except OSError as err:
        if os.path.isdir(XML_FILES_DIR):
            pass
        else:
            #dir creation error - re-raise it
            raise
    #set up data handler & process data
    dataHandler = DataHandler(args[0], options.in_enc, int(options.sheet), int(options.row), options.force_dates, options.type)
    process(dataHandler, xml_files_dir=XML_FILES_DIR, copy_parent_to_children=options.copy_parent_to_children)
    sys.exit()

