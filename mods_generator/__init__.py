import csv
import datetime
import os
import re

import xlrd
from eulxml.xmlmap import load_xmlobject_from_file
from bdrxml import mods, darwincore


class XmlRecord(object):

    def __init__(self, group_id, xml_id, field_data, data_files):
        self.group_id = group_id #this is what ties parent records to children
        self.xml_id = xml_id
        if not field_data:
            raise Exception('no field_data for %s: %s' % (group_id, xml_id))
        if u'<dc' in field_data[0]['xml_path'] or u'<dwc' in field_data[0]['xml_path']:
            self.record_type = 'dwc'
        else:
            self.record_type = 'mods'
        self._field_data = field_data
        self.data_files = data_files

    def field_data(self):
        #return list of {'xml_path': xxx, 'data': xxx}
        return self._field_data


class DataHandler(object):
    '''Handle interacting with the data.
    
    Use 1-based values for sheets or rows in public functions.
    There should be no data in byte objects - they should all be str,
    which is what xlrd uses, and we convert all CSV data to str objects
    as well.
    '''
    def __init__(self, filename, input_encoding='utf-8', sheet=1, ctrl_row=2, force_dates=False, obj_type='parent'):
        '''Open file and get data from correct sheet.
        
        First, try opening the file as an excel spreadsheet.
        If that fails, try opening it as a CSV file.
        Exit with error if CSV doesn't work.
        '''
        self.obj_type = obj_type
        self._force_dates = force_dates
        self._input_encoding = input_encoding
        self._ctrl_row_number = ctrl_row
        try:
            self.book = xlrd.open_workbook(filename)
            self.dataset = self.book.sheet_by_index(int(sheet)-1)
            self.data_type = 'xlrd'
        except xlrd.XLRDError as xerr:
            #if it's not excel, try csv
            try:
                with open(filename, 'rt', encoding=self._input_encoding) as csvFile:
                    #read some test data to pass to sniffer for checking the dialect
                    data = csvFile.read(4096)
                    csvFile.seek(0)
                    dialect = csv.Sniffer().sniff(data)
                    #set doublequote to true because that's the default and the Sniffer doesn't
                    #   seem to pick it up right
                    dialect.doublequote = True
                    self.data_type = 'csv'
                    csvReader = csv.reader(csvFile, dialect)
                    self.csvData = []
                    for row in csvReader:
                        if len(row) > 0:
                            self.csvData.append(row)
            except Exception as e:
                raise Exception('Could not recognize file format.')

    def get_xml_records(self):
        '''skips rows without a group id or xml id'''
        group_id_col = self._get_group_id_col()
        xml_id_col = self._get_xml_id_col()
        if group_id_col is None and xml_id_col is None:
            msg = 'no group id column (called "id", or "group id")'
            msg = msg + ' or xml id column (called "mods id" or with the xml id mapping)'
            raise Exception(msg)
        index = self._ctrl_row_number
        xml_records = []
        xml_ids = {}
        data_file_col = self._get_filename_col()
        cols_to_map = self.get_cols_to_map()
        if not cols_to_map:
            raise Exception('found no mapping information')
        genus_col = self._get_col_from_id_names(['<dwc:genus>'])
        for data_row in self._get_data_rows():
            index += 1
            group_id = None
            xml_id = None
            if group_id_col is not None:
                group_id = data_row[group_id_col].strip()
            if xml_id_col is not None:
                xml_id = data_row[xml_id_col].strip()
            if not (group_id or xml_id):
                continue
            #if we don't have xml_id, generate it from group_id
            if xml_id is None:
                if group_id in xml_ids:
                    xml_id = u'%s_%s' % (group_id, xml_ids[group_id])
                    xml_ids[group_id] = xml_ids[group_id] + 1
                else:
                    if self.obj_type == 'parent':
                        xml_id = group_id
                        xml_ids[group_id] = 1
                    else:
                        xml_id = u'%s_1' % group_id
                        xml_ids[group_id] = 2
            #if we don't have group_id, generate it from xml_id
            if group_id is None:
                group_id = xml_id.split(u'_')[0]
            field_data = []
            for i, val in enumerate(data_row):
                if i in cols_to_map and len(val) > 0:
                    field_data.append({'xml_path': cols_to_map[i], 'data': val})
            if genus_col:
                field_data = self._dwc_dynamic_fields(genus_col, data_row, field_data)
            data_files = []
            if data_file_col is not None:
                data_files = [df.strip() for df in data_row[data_file_col].split(u',')]
            xml_records.append(XmlRecord(group_id, xml_id, field_data, data_files))
        return xml_records

    def _dwc_dynamic_fields(self, genus_col, data_row, field_data):
        #sets scientificNameAuthorship, acceptedNameUsage, infraspecificEpithet, and taxonRank
        species_col = self._get_col_from_id_names(['<dwc:specificEpithet>'])
        species_author_col = self._get_col_from_id_names(['dwc_species_author'])
        accepted_name_usage = u'%s %s' % (data_row[genus_col], data_row[species_col])
        infraspecific_epithet = ''
        taxon_rank = ''
        scientific_name_authorship = data_row[species_author_col] or ''
        variety_col = self._get_col_from_id_names(['dwc_variety'])
        variety_author_col = self._get_col_from_id_names(['dwc_variety_author'])
        if data_row[variety_col]:
            infraspecific_epithet = data_row[variety_col]
            taxon_rank = 'variety'
            taxon_rank_abbr = 'var.'
            if data_row[variety_author_col]:
                scientific_name_authorship = data_row[variety_author_col]
        else:
            subspecies_col = self._get_col_from_id_names(['dwc_subspecies'])
            subspecies_author_col = self._get_col_from_id_names(['dwc_subspecies_author'])
            if data_row[subspecies_col]:
                infraspecific_epithet = data_row[subspecies_col]
                taxon_rank = 'subspecies'
                taxon_rank_abbr = 'subsp.'
                if data_row[subspecies_author_col]:
                    scientific_name_authorship = data_row[subspecies_author_col]
        if infraspecific_epithet:
            accepted_name_usage = u'%s %s %s' % (accepted_name_usage, taxon_rank_abbr, infraspecific_epithet)
            field_data.append({'xml_path': '<dwc:infraspecificEpithet>', 'data': infraspecific_epithet})
            field_data.append({'xml_path': '<dwc:taxonRank>', 'data': taxon_rank})
        accepted_name_usage = u'%s %s' % (accepted_name_usage, scientific_name_authorship)
        if scientific_name_authorship.strip():
            field_data.append({'xml_path': '<dwc:scientificNameAuthorship>', 'data': scientific_name_authorship.strip()})
        if accepted_name_usage.strip():
            field_data.append({'xml_path': '<dwc:acceptedNameUsage>', 'data': accepted_name_usage.strip()})
        return field_data

    def _get_data_rows(self):
        '''data rows will be all the rows after the control row'''
        for i in range(self._ctrl_row_number+1, self._get_total_rows()+1):
            yield self.get_row(i)

    def _get_control_row(self):
        '''Retrieve the row that controls XML mapping locations.'''
        return self.get_row(self._ctrl_row_number)

    def _get_col_from_id_names(self, id_names):
        id_names_lower = [n.lower() for n in id_names]
        #try control row first
        for i, val in enumerate(self._get_control_row()):
            if val.lower() in id_names_lower:
                return i
        #try first row if needed
        for i, val in enumerate(self.get_row(1)):
            if val.lower() in id_names_lower:
                return i
        #we didn't find the column
        return None

    def _get_xml_id_col(self):
        '''column that contains the xml id for this record'''
        ID_NAMES = [u'mods id', u'<mods:mods id="">']
        return self._get_col_from_id_names(ID_NAMES)

    def _get_group_id_col(self):
        '''Get index of column that contains id for tying children to parents'''
        ID_NAMES = [u'id', u'group id']
        return self._get_col_from_id_names(ID_NAMES)

    def _get_filename_col(self):
        '''Get index of column that contains data file name(s).'''
        ID_NAMES = [u'file name', u'filename']
        return self._get_col_from_id_names(ID_NAMES)

    def get_cols_to_map(self):
        '''Get a dict of columns & values in dataset that should be mapped to XML
        (some will just be ignored).
        '''
        cols = {}
        ctrl_row = self._get_control_row()
        for i, val in enumerate(ctrl_row):
            val = val.strip()
            #we'll assume it's to be mapped if we see the start of an XML  tag
            if val.startswith(u'<'):
                cols[i] = val
        return cols

    def get_row(self, index):
        '''Retrieve a list of str values (index is 1-based like excel)'''
        #subtract 1 from index so that it's 0-based like xlrd and csvData list
        index = index - 1
        if self.data_type == 'xlrd':
            row = self.dataset.row_values(index)
            #In a data column that's mapped to a date field, we could find a text
            #   string that looks like a date - we might want to reformat 
            #   that as well.
            if index > (self._ctrl_row_number-1):
                for i, v in enumerate(self._get_control_row()):
                    if 'date' in v.lower() and 'verbatim' not in v.lower():
                        if isinstance(row[i], str):
                            #we may have a text date, so see if we can understand it
                            # *process_text_date will return a text value of the
                            #   reformatted date if possible, else the original value
                            row[i] = process_text_date(row[i], self._force_dates)
            for i, v in enumerate(row):
                if isinstance(v, float):
                    #there are some interesting things that happen
                    # with numbers in Excel. Eg. what looks like an int in Excel
                    # is actually stored as a float (and xlrd handles as a float).
                    #http://stackoverflow.com/questions/2739989/reading-numeric-excel-data-as-text-using-xlrd-in-python
                    #if cell is XL_CELL_NUMBER
                    if self.dataset.cell_type(index, i) == 2 and int(v) == v:
                        #convert data into int & then str
                        #Note: if a number was displayed as xxxx.0 in Excel, we
                        #   would lose the .0 here
                        row[i] = str(int(v))
                    #Dates are also stored as floats in Excel, so we have to do
                    #   some extra processing to get a datetime object
                    #if we have an XL_CELL_DATE
                    elif self.dataset.cell_type(index, i) == 3:
                        #try to get an actual date out of it, instead of a float
                        #Note: we are losing Excel formatting information here,
                        #   and formatting the date as yyyy-mm-dd.
                        tup = xlrd.xldate_as_tuple(v, self.book.datemode)
                        d = datetime.datetime(*tup)
                        if tup[0] == 0 and tup[1] == 0 and tup[2] == 0:
                            #just time, no date
                            row[i] = '{0:%H:%M:%S}'.format(d)
                        elif tup[3] == 0 and tup[4] == 0 and tup[5] == 0:
                            #just date, no time
                            row[i] = '{0:%Y-%m-%d}'.format(d)
                        else:
                            #assume full date/time
                            row[i] = '{0:%Y-%m-%d %H:%M:%S}'.format(d)
        elif self.data_type == 'csv':
            row = self.csvData[index]
            if index > (self._ctrl_row_number-1):
                for i, v in enumerate(self._get_control_row()):
                    if 'date' in v.lower() and 'verbatim' not in v.lower():
                        if isinstance(row[i], str):
                            #we may have a text date, so see if we can understand it
                            # *process_text_date will return a text value of the
                            #   reformatted date if possible, else the original value
                            row[i] = process_text_date(row[i], self._force_dates)
        #this final loop should be unnecessary, but it's a final check to
        #   make sure everything is str.
        for i, v in enumerate(row):
            if not isinstance(v, str):
                try:
                    row[i] = v.decode(self._input_encoding)
                #if v isn't a string, we might get this error, so try without
                #   the encoding
                except TypeError:
                    row[i] = str(v)
        #finally return the row
        return row

    def _get_total_rows(self):
        '''Get total number of rows in the dataset.'''
        total_rows = 0
        if self.data_type == 'xlrd':
            total_rows = self.dataset.nrows
        elif self.data_type == 'csv':
            total_rows = len(self.csvData)
        return total_rows


def process_text_date(str_date, force_dates=False):
    '''Take a text-based date and try to reformat it to yyyy-mm-dd if needed.
        
    Note: in xx/xx/xx or xx-xx-xx, we assume that year is last, not first.'''
    #do some checking on str_date - if it's not what we're looking for,
    #   just return str_date without changing anything
    if not isinstance(str_date, str):
        return str_date
    if len(str_date) == 0:
        return str_date
    #Some date formats we could understand:
    #dd/dd/dddd, dd/dd/dd, d/d/dd, ...
    mmddyy = re.compile('^\d?\d/\d?\d/\d\d$')
    mmddyyyy = re.compile('^\d?\d/\d?\d/\d\d\d\d$')
    mmyyyy = re.compile('^\d?\d/\d\d\d\d$')
    #dd-dd-dddd, dd-dd-dd, d-d-dd, ...
    mmddyy2 = re.compile('^\d?\d-\d?\d-\d\d$')
    mmddyyyy2 = re.compile('^\d?\d-\d?\d-\d\d\d\d$')
    mmyyyy2 = re.compile('^\d?\d-\d\d\d\d$')
    format = '' #flag to remember which format we used
    if mmddyy.search(str_date):
        try:
            #try mm/dd/yy first, since that should be more common in the US
            newDate = datetime.datetime.strptime(str_date, '%m/%d/%y')
            format = 'mmddyy'
        except ValueError:
            try:
                newDate = datetime.datetime.strptime(str_date, '%d/%m/%y')
                format = 'ddmmyy'
            except ValueError:
                return str_date
    elif mmddyyyy.search(str_date):
        try:
            newDate = datetime.datetime.strptime(str_date, '%m/%d/%Y')
            format = 'mmddyyyy'
        except ValueError:
            try:
                newDate = datetime.datetime.strptime(str_date, '%d/%m/%Y')
                format = 'ddmmyyyy'
            except ValueError:
                return str_date
    elif mmyyyy.search(str_date):
        month, year = str_date.split(u'/')
        return u'%04d-%02d' % (int(year), int(month))
    elif mmyyyy2.search(str_date):
        month, year = str_date.split(u'-')
        return u'%04d-%02d' % (int(year), int(month))
    elif mmddyy2.search(str_date):
        try:
            #try mm-dd-yy first, since that should be more common
            newDate = datetime.datetime.strptime(str_date, '%m-%d-%y')
            format = 'mmddyy'
        except ValueError:
            try:
                newDate = datetime.datetime.strptime(str_date, '%d-%m-%y')
                format = 'ddmmyy'
            except ValueError:
                return str_date
    elif mmddyyyy2.search(str_date):
        try:
            newDate = datetime.datetime.strptime(str_date, '%m-%d-%Y')
            format = 'mmddyyyy'
        except ValueError:
            try:
                newDate = datetime.datetime.strptime(str_date, '%d-%m-%Y')
                format = 'ddmmyyyy'
            except ValueError:
                return str_date
    else:
        return str_date
    #at this point, we have newDate, but it could still have been ambiguous
    #day & month are both between 1 and 12 & not equal - ambiguous
    if newDate.day <= 12 and newDate.day != newDate.month: 
        if force_dates:
            return u'%04d-%02d-%02d' % (newDate.year, newDate.month, newDate.day)
        else:
            return str_date
    #year is only two digits - don't know the century, or if year was
    # interchanged with month or day
    elif format == 'mmddyy' or format == 'ddmmyy':
        if force_dates:
            return u'%04d-%02d-%02d' % (newDate.year, newDate.month, newDate.day)
        else:
            return str_date
    else:
        return u'%04d-%02d-%02d' % (newDate.year, newDate.month, newDate.day)


class Mapper(object):
    '''Map data into a Mods object.
    Each instance of this class can only handle 1 XML object.'''

    def __init__(self, record_type, field_data, parent_mods=None):
        self.dataSeparator = u'||'
        self._parent_mods = parent_mods
        #dict for keeping track of which fields we've cleared out the parent
        # info for. So we can have multiple columns in the spreadsheet w/ the same field.
        self._cleared_fields = {}
        self._record_type = record_type
        if record_type == 'dwc':
            self._xml_obj = darwincore.make_simple_darwin_record_set()
            self._xml_obj.create_simple_darwin_record()
        else:
            if parent_mods:
                self._xml_obj = parent_mods
            else:
                self._xml_obj = mods.make_mods()
        for field in field_data:
            self.add_data(field['xml_path'], field['data'])

    def get_xml(self):
        return self._xml_obj

    def add_data(self, mods_loc, data):
        '''Method to actually put the data in the correct place of XML obj.'''
        #parse location info into elements/attributes
        loc = LocationParser(mods_loc)
        base_element = loc.get_base_element()
        location_sections = loc.get_sections()
        #Darwin core can't have repeated fields like mods. Some fields are lists, so there can be multiple
        # elements separated by '|', but otherwise the text is just put into one field (unlike mods, where
        # multiple elements are separated into multiple fields).
        if self._record_type == 'dwc':
            self._process_dwc_element(
                    self._xml_obj.simple_darwin_record, base_element, location_sections, data.replace(u'||', u'|'))
        else:
            data_vals = [data.strip() for data in data.split(self.dataSeparator)]
            #strip any empty data sections so we don't have to worry about it below
            data_vals = [self._get_data_divs(data, loc.has_sectioned_data) for data in data_vals if data]
            self._process_mods_element(base_element, location_sections, data_vals)

    def _process_dwc_element(self, xml_obj, base_element, location_sections, data):
        if base_element['element'] == u'dc:type':
            xml_obj.type = data
        elif base_element['element'] == u'dc:modified':
            xml_obj.modified = data
        elif base_element['element'] == u'dwc:catalogNumber':
            xml_obj.catalog_number = data
        elif base_element['element'] == u'dwc:basisOfRecord':
            xml_obj.basis_of_record = data
        elif base_element['element'] == u'dwc:recordedBy':
            xml_obj.recorded_by = data
        elif base_element['element'] == u'dwc:recordNumber':
            xml_obj.record_number = data
        elif base_element['element'] == u'dwc:individualID': #deprecated in DWC
            xml_obj.individual_id = data
        elif base_element['element'] == u'dwc:eventDate':
            xml_obj.event_date = data
        elif base_element['element'] == u'dwc:verbatimEventDate':
            xml_obj.verbatim_event_date = data
        elif base_element['element'] == u'dwc:scientificName':
            xml_obj.scientific_name = data
        elif base_element['element'] == u'dwc:higherClassification':
            xml_obj.higher_classification = data
        elif base_element['element'] == u'dwc:kingdom':
            xml_obj.kingdom = data
        elif base_element['element'] == u'dwc:phylum':
            xml_obj.phylum = data
        elif base_element['element'] == u'dwc:class':
            xml_obj.class_ = data
        elif base_element['element'] == u'dwc:order':
            xml_obj.order = data
        elif base_element['element'] == u'dwc:family':
            xml_obj.family = data
        elif base_element['element'] == u'dwc:genus':
            xml_obj.genus = data
        elif base_element['element'] == u'dwc:specificEpithet':
            xml_obj.specific_epithet = data
        elif base_element['element'] == u'dwc:scientificNameAuthorship':
            xml_obj.scientific_name_authorship = data
        elif base_element['element'] == u'dwc:infraspecificEpithet':
            xml_obj.infraspecific_epithet = data
        elif base_element['element'] == u'dwc:taxonRank':
            xml_obj.taxon_rank = data
        elif base_element['element'] == u'dwc:acceptedNameUsage':
            xml_obj.accepted_name_usage = data
        elif base_element['element'] == u'dwc:locality':
            xml_obj.locality = data
        elif base_element['element'] == u'dwc:municipality':
            xml_obj.municipality = data
        elif base_element['element'] == u'dwc:county':
            xml_obj.county = data
        elif base_element['element'] == u'dwc:stateProvince':
            xml_obj.state_province = data
        elif base_element['element'] == u'dwc:country':
            xml_obj.country = data
        elif base_element['element'] == u'dwc:habitat':
            xml_obj.habitat = data
        elif base_element['element'] == u'dwc:identificationID':
            xml_obj.identification_id = data
        else:
            raise Exception('unhandled DarwinCore element: %s' % base_element['element'])

    def _process_mods_element(self, base_element, location_sections, data_vals):
        #handle various MODS elements
        if base_element['element'] == u'mods:mods':
            if 'ID' in base_element['attributes']:
                self._xml_obj.id = data_vals[0][0]
        elif base_element['element'] == u'mods:name':
            if not self._cleared_fields.get(u'names', None):
                self._xml_obj.names = []
                self._cleared_fields[u'names'] = True
            self._add_name_data(base_element, location_sections, data_vals)
        elif base_element['element'] == u'mods:namePart':
            #grab the last name that was added
            name = self._xml_obj.names[-1]
            np = mods.NamePart(text=data_vals[0][0])
            if u'type' in base_element[u'attributes']:
                np.type = base_element[u'attributes'][u'type']
            name.name_parts.append(np)
        elif base_element[u'element'] == u'mods:titleInfo':
            if not self._cleared_fields.get(u'title_info_list', None):
                self._xml_obj.title_info_list = []
                self._cleared_fields[u'title_info_list'] = True
            self._add_title_data(base_element, location_sections, data_vals)
        elif base_element[u'element'] == u'mods:language':
            if not self._cleared_fields.get(u'languages', None):
                self._xml_obj.languages = []
                self._cleared_fields[u'languages'] = True
            for data in data_vals:
                language = mods.Language()
                language_term = mods.LanguageTerm(text=data[0])
                if u'authority' in location_sections[0][0]['attributes']:
                    language_term.authority = location_sections[0][0]['attributes']['authority']
                if u'type' in location_sections[0][0]['attributes']:
                    language_term.type = location_sections[0][0][u'attributes'][u'type']
                language.terms.append(language_term)
                self._xml_obj.languages.append(language)
        elif base_element[u'element'] == u'mods:genre':
            if not self._cleared_fields.get(u'genres', None):
                self._xml_obj.genres = []
                self._cleared_fields[u'genres'] = True
            for data in data_vals:
                genre = mods.Genre(text=data[0])
                if 'authority' in base_element['attributes']:
                    genre.authority = base_element['attributes']['authority']
                self._xml_obj.genres.append(genre)
        elif base_element['element'] == 'mods:originInfo':
            if not self._cleared_fields.get(u'origin_info', None):
                self._xml_obj.origin_info = None
                self._cleared_fields[u'origin_info'] = True
                self._xml_obj.create_origin_info()
            self._add_origin_info_data(base_element, location_sections, data_vals)
        elif base_element['element'] == 'mods:physicalDescription':
            if not self._cleared_fields.get(u'physical_description', None):
                self._xml_obj.physical_description = None
                self._cleared_fields[u'physical_description'] = True
                #can only have one physical description currently
                self._xml_obj.create_physical_description()
            data_divs = data_vals[0]
            for index, section in enumerate(location_sections):
                if section[0][u'element'] == 'mods:extent':
                    self._xml_obj.physical_description.extent = data_divs[index]
                elif section[0][u'element'] == 'mods:digitalOrigin':
                    try:
                        self._xml_obj.physical_description.digital_origin = data_divs[index]
                    except:
                        self._xml_obj.physical_description.digital_origin = section[0][u'data']
                elif section[0][u'element'] == 'mods:note':
                    self._xml_obj.physical_description.note = data_divs[index]
        elif base_element['element'] == 'mods:typeOfResource':
            if not self._cleared_fields.get(u'typeOfResource', None):
                self._xml_obj.resource_type = None
                self._cleared_fields[u'typeOfResource'] = True
            self._xml_obj.resource_type = data_vals[0][0]
        elif base_element['element'] == 'mods:targetAudience':
            if not self._cleared_fields.get(u'targetAudience', None):
                self._xml_obj.resource_type = None
                self._cleared_fields[u'targetAudience'] = True
            ta = mods.TargetAudience(text=data_vals[0][0])
            self._xml_obj.target_audiences.append(ta)
        elif base_element['element'] == 'mods:abstract':
            if not self._cleared_fields.get(u'abstract', None):
                self._xml_obj.abstract = None
                self._cleared_fields[u'abstract'] = True
                #can only have one abstract currently
                self._xml_obj.create_abstract()
            self._xml_obj.abstract.text = data_vals[0][0]
        elif base_element['element'] == 'mods:note':
            if not self._cleared_fields.get(u'notes', None):
                self._xml_obj.notes = []
                self._cleared_fields[u'notes'] = True
            for data in data_vals:
                note = mods.Note(text=data[0])
                if 'type' in base_element['attributes']:
                    note.type = base_element['attributes']['type']
                if 'displayLabel' in base_element['attributes']:
                    note.label = base_element['attributes']['displayLabel']
                self._xml_obj.notes.append(note)
        elif base_element['element'] == 'mods:subject':
            if not self._cleared_fields.get(u'subjects', None):
                self._xml_obj.subjects = []
                self._cleared_fields[u'subjects'] = True
            for data in data_vals:
                subject = mods.Subject()
                if 'authority' in base_element['attributes']:
                    subject.authority = base_element['attributes']['authority']
                data_divs = data
                for section, div in zip(location_sections, data_divs):
                    if section[0]['element'] == 'mods:topic':
                        topic = mods.Topic(text=div)
                        subject.topic_list.append(topic)
                    elif section[0]['element'] == 'mods:temporal':
                        temporal = mods.Temporal(text=div)
                        subject.temporal_list.append(temporal)
                    elif section[0]['element'] == 'mods:geographic':
                        subject.geographic = div
                    elif section[0]['element'] == 'mods:hierarchicalGeographic':
                        hg = mods.HierarchicalGeographic()
                        if section[1]['element'] == 'mods:country':
                            if 'data' in section[1]:
                                hg.country = section[1]['data']
                                if section[2]['element'] == 'mods:state':
                                    hg.state = div
                            else:
                                hg.country = div
                        subject.hierarchical_geographic = hg
                self._xml_obj.subjects.append(subject)
        elif base_element['element'] == 'mods:identifier':
            if not self._cleared_fields.get(u'identifiers', None):
                self._xml_obj.identifiers = []
                self._cleared_fields[u'identifiers'] = True
            for data in data_vals:
                identifier = mods.Identifier(text=data[0])
                if 'type' in base_element['attributes']:
                    identifier.type = base_element['attributes']['type']
                if 'displayLabel' in base_element['attributes']:
                    identifier.label = base_element['attributes']['displayLabel']
                self._xml_obj.identifiers.append(identifier)
        elif base_element['element'] == u'mods:location':
            if not self._cleared_fields.get(u'locations', None):
                self._xml_obj.locations = []
                self._cleared_fields[u'locations'] = True
            for data in data_vals:
                loc = mods.Location()
                data_divs = data
                for section, div in zip(location_sections, data_divs):
                    if section[0]['element'] == u'mods:url':
                        if section[0]['data']:
                            loc.url = section[0]['data']
                        else:
                            loc.url = div
                    elif section[0]['element'] == u'mods:physicalLocation':
                        if section[0]['data']:
                            loc.physical = mods.PhysicalLocation(text=section[0]['data'])
                        else:
                            loc.physical = mods.PhysicalLocation(text=div)
                    elif section[0]['element'] == u'mods:holdingSimple':
                        hs = mods.HoldingSimple()
                        if section[1]['element'] == u'mods:copyInformation':
                            if section[2]['element'] == u'mods:note':
                                note = mods.Note(text=div)
                                ci = mods.CopyInformation()
                                ci.notes.append(note)
                                hs.copy_information.append(ci)
                                loc.holding_simple = hs
                self._xml_obj.locations.append(loc)
        elif base_element['element'] == u'mods:relatedItem':
            if not self._cleared_fields.get(u'related', None):
                self._xml_obj.related_items = []
                self._cleared_fields[u'related'] = True
            for data in data_vals:
                related_item = mods.RelatedItem()
                if u'type' in base_element[u'attributes']:
                    related_item.type = base_element[u'attributes'][u'type']
                if u'displayLabel' in base_element[u'attributes']:
                    related_item.label = base_element[u'attributes'][u'displayLabel']
                if location_sections[0][0][u'element'] == u'mods:titleInfo':
                    if location_sections[0][1][u'element'] == u'mods:title':
                        related_item.title = data[0]
                self._xml_obj.related_items.append(related_item)
        else:
            raise Exception('MODS element not handled! %s' % base_element)

    def _add_title_data(self, base_element, location_sections, data_vals):
        for data_divs in data_vals:
            title = mods.TitleInfo()
            if u'type' in base_element['attributes']:
                title.type = base_element['attributes']['type']
            if u'displayLabel' in base_element['attributes']:
                title.label = base_element['attributes']['displayLabel']
            for section, div in zip(location_sections, data_divs):
                for element in section:
                    if element[u'element'] == u'mods:title':
                        title.title = div
                    elif element[u'element'] == u'mods:partName':
                        title.part_name = div
                    elif element[u'element'] == u'mods:partNumber':
                        title.part_number = div
                    elif element[u'element'] == u'mods:nonSort':
                        title.non_sort = div
            self._xml_obj.title_info_list.append(title)

    def _get_data_divs(self, data, has_sectioned_data):
        data_divs = []
        if not has_sectioned_data:
            return [data]
        #split data into its divisions based on '#', but allow \ to escape the #
        while data:
            ind = data.find(u'#')
            if ind == -1:
                data_divs.append(data)
                data = ''
            else:
                while ind != -1 and data[ind-1] == u'\\':
                    #remove '\'
                    data = data[:ind-1] + data[ind:]
                    #find next '#' (being sure to advance past current '#')
                    ind = data.find(u'#', ind)
                if ind == -1:
                    data_divs.append(data)
                    data = u''
                else:
                    data_divs.append(data[:ind])
                    data = data[ind+1:]
        return data_divs


    def _add_name_data(self, base_element, location_sections, data_vals):
        '''Method to handle more complicated name data. '''
        for data in data_vals:
            name = mods.Name() #we're always going to be creating a name
            if u'type' in base_element[u'attributes']:
                name.type = base_element[u'attributes'][u'type']
            data_divs = data
            for index, section in enumerate(location_sections):
                try:
                    div = data_divs[index].strip()
                except:
                    div = None
                #make sure we have data for this section (except for mods:role, which could just have a constant)
                if not div and section[0][u'element'] != u'mods:role':
                    continue
                for element in section:
                    #handle base name
                    if element['element'] == u'mods:namePart' and u'type' not in element['attributes']:
                        np = mods.NamePart(text=div)
                        name.name_parts.append(np)
                    elif element[u'element'] == u'mods:namePart' and u'type' in element[u'attributes']:
                        np = mods.NamePart(text=div)
                        np.type = element[u'attributes'][u'type']
                        name.name_parts.append(np)
                    elif element['element'] == u'mods:roleTerm':
                        role_attrs = element['attributes']
                        if element[u'data']:
                            role = mods.Role(text=element['data'])
                        else:
                            if div:
                                role = mods.Role(text=div)
                            else:
                                continue
                        if u'type' in role_attrs:
                            role.type = role_attrs['type']
                        if u'authority' in role_attrs:
                            role.authority = role_attrs[u'authority']
                        name.roles.append(role)
            self._xml_obj.names.append(name)

    def _add_origin_info_data(self, base_element, location_sections, data_vals):
        if u'displayLabel' in base_element['attributes']:
            self._xml_obj.origin_info.label = base_element[u'attributes'][u'displayLabel']
        for data in data_vals:
            divs = data
            for index, section in enumerate(location_sections):
                if not divs[index]:
                    continue
                if section[0][u'element'] == u'mods:dateCreated':
                    date = mods.DateCreated(date=divs[index])
                    date = self._set_date_attributes(date, section[0][u'attributes'])
                    self._xml_obj.origin_info.created.append(date)
                elif section[0][u'element'] == u'mods:dateIssued':
                    date = mods.DateIssued(date=divs[index])
                    date = self._set_date_attributes(date, section[0][u'attributes'])
                    self._xml_obj.origin_info.issued.append(date)
                elif section[0][u'element'] == u'mods:dateCaptured':
                    date = mods.DateCaptured(date=divs[index])
                    date = self._set_date_attributes(date, section[0][u'attributes'])
                    self._xml_obj.origin_info.captured.append(date)
                elif section[0][u'element'] == u'mods:dateValid':
                    date = mods.DateValid(date=divs[index])
                    date = self._set_date_attributes(date, section[0][u'attributes'])
                    self._xml_obj.origin_info.valid.append(date)
                elif section[0][u'element'] == u'mods:dateModified':
                    date = mods.DateModified(date=divs[index])
                    date = self._set_date_attributes(date, section[0][u'attributes'])
                    self._xml_obj.origin_info.modified.append(date)
                elif section[0][u'element'] == u'mods:copyrightDate':
                    date = mods.CopyrightDate(date=divs[index])
                    date = self._set_date_attributes(date, section[0][u'attributes'])
                    self._xml_obj.origin_info.copyright.append(date)
                elif section[0][u'element'] == u'mods:dateOther':
                    date = mods.DateOther(date=divs[index])
                    date = self._set_date_attributes(date, section[0][u'attributes'])
                    self._xml_obj.origin_info.other.append(date)
                elif section[0][u'element'] == u'mods:place':
                    place = mods.Place()
                    placeTerm = mods.PlaceTerm(text=divs[index])
                    place.place_terms.append(placeTerm)
                    self._xml_obj.origin_info.places.append(place)
                elif section[0][u'element'] == u'mods:publisher':
                    self._xml_obj.origin_info.publisher = divs[index]
                else:
                    raise Exception('unhandled originInfo element: %s' % section)

    def _set_date_attributes(self, date, attributes):
        if u'encoding' in attributes:
            date.encoding = attributes[u'encoding']
        if u'point' in attributes:
            date.point = attributes[u'point']
        if u'keyDate' in attributes:
            date.key_date = attributes[u'keyDate']
        return date


class LocationParser(object):
    '''class for parsing dataset location instructions (for various XML formats).
    eg. <mods:name type="personal"><mods:namePart>#<mods:namePart type="date">#<mods:namePart type="termsOfAddress">'''

    def __init__(self, data):
        self.has_sectioned_data = False
        self._data = data #raw data we receive
        self._section_separator = u'#'
        self._base_element = None #in the example, this will be set to {'element': 'mods:name', 'attributes': {'type': 'personal'}}
        self._sections = [] #list of the sections, which are divided by '#' (in the example, there are 3 sections)
            #each section consists of a list of elements
            #each element is a dict containing the element name, its attributes, and any data in that element
        self._parse()

    def get_base_element(self):
        return self._base_element

    def get_sections(self):
        return self._sections

    def _parse_base_element(self, data):
        #grab the first tag (including namespace) & parse into self._base_element
        startTagPos = data.find(u'<')
        endTagPos = data.find(u'>')
        if endTagPos > startTagPos:
            tag = data[startTagPos:endTagPos+1]
            #remove first tag from data for the rest of the parsing
            data = data[endTagPos+1:]
            #parse tag into elements & attributes
            space = tag.find(u' ')
            if space > 0:
                name = tag[1:space]
                attributes = self._parse_attributes(tag[space:-1])
            else:
                name = tag[1:-1]
                attributes = {}
            return ({u'element': name, u'attributes': attributes, u'data': None}, data)
        else:
            raise Exception('Error parsing "%s"!' % data.encode('utf-8'))

    def _parse(self):
        '''Get the first Mods field we're looking at in this string.'''
        #first strip off leading & trailing whitespace
        data = self._data.strip()
        #very basic data checking
        if data[0] != u'<':
            raise Exception('location data must start with "<"')
        #grab base element (eg. mods:originInfo, mods:name, ...)
        self._base_element, data = self._parse_base_element(data)
        if not data:
            return #we're done - there was just one base element
        #now pull out elements/attributes in order, for each section
        location_sections = data.split(self._section_separator)
        if len(location_sections) > 1:
            self.has_sectioned_data = True
        for section in location_sections:
            new_section = []
            while len(section) > 0:
                #grab the first tag (including namespace)
                startTagPos = section.find(u'<')
                endTagPos = section.find(u'>')
                if endTagPos > startTagPos:
                    tag = section[startTagPos:endTagPos+1]
                    #remove first tag from section for the next loop
                    section = section[endTagPos+1:]
                    if tag[:2] == u'</':
                        continue
                else:
                    raise Exception('Error parsing "%s"!' % section)
                #get element name and attributes to put in list
                space = tag.find(u' ')
                if space > 0:
                    name = tag[1:space]
                    attributes = self._parse_attributes(tag[space:-1])
                else:
                    name = tag[1:-1]
                    attributes = {}
                #there could be some text before the next tag
                text = None
                if section:
                    next_tag_start = section.find(u'<')
                    if next_tag_start == 0:
                        pass
                    elif next_tag_start == -1:
                        text = section
                        section = ''
                    else:
                        text = section[:next_tag_start]
                        section = section[next_tag_start:]
                if text:
                    new_section.append({'element': name, 'attributes': attributes, 'data': text})
                else:
                    new_section.append({'element': name, 'attributes': attributes, u'data': None})
            if new_section:
                self._sections.append(new_section)


    def _parse_attributes(self, data):
        data = data.strip()
        attributes = {}
        while len(data) > 0:
            equal = data.find('=')
            attr = data[:equal].strip()
            valStart = data.find('"', equal+1)
            valEnd = data.find('"', valStart+1)
            if valEnd > valStart:
                val = data[valStart+1:valEnd]
                attributes[attr] = val
                data = data[valEnd+1:].strip()
            else:
                raise Exception('Error parsing attributes. data = "%s"' % data)
        return attributes


def process(dataHandler, xml_files_dir, copy_parent_to_children=False):
    '''Function to go through all the data and process it.'''
    #get dicts of columns that should be mapped & where they go in MODS
    index = 1
    for record in dataHandler.get_xml_records():
        filename = '%s.%s' % (record.xml_id, record.record_type)
        full_path = os.path.join(xml_files_dir, filename)
        if os.path.exists(full_path):
            raise Exception('%s already exists!' % filename)
        if copy_parent_to_children:
            #load parent mods object if desired (& it exists)
            parent_filename = os.path.join(xml_files_dir, u'%s.%s' % (record.group_id, record.record_type))
            parent_xml = None
            if os.path.exists(parent_filename):
                parent_xml = load_xmlobject_from_file(parent_filename, mods.Mods)
                mapper = Mapper(record.record_type, record.field_data(), parent_mods=parent_xml)
        else:
            mapper = Mapper(record.record_type, record.field_data())
        xml_obj = mapper.get_xml()
        xml_bytes = xml_obj.serializeDocument(pretty=True) #serializes as UTF-8
        with open(full_path, 'wb') as f:
            f.write(xml_bytes)
        index = index + 1

