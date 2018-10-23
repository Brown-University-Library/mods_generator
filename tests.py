#!/usr/bin/env python
import io
import os
import tempfile
import unittest

from bdrxml.mods import Mods
from bdrxml.darwincore import SimpleDarwinRecord
from mods_generator import ControlRowError, LocationParser, DataHandler, Mapper, process_text_date, process


class TestLocationParser(unittest.TestCase):

    def setUp(self):
        pass

    def test_single_tag(self):
        loc = '<mods:identifier type="local" displayLabel="PN_DB_id">'
        locParser = LocationParser(loc)
        base_element = locParser.get_base_element()
        self.assertEqual(base_element['element'], 'mods:identifier')
        self.assertEqual(base_element['attributes'], {'type': 'local', 'displayLabel': 'PN_DB_id'})
        self.assertFalse(base_element['data'])
        sections = locParser.get_sections()
        self.assertFalse(sections)

    def test_multi_tag(self):
        loc = '<mods:titleInfo><mods:title>'
        locParser = LocationParser(loc)
        base_element = locParser.get_base_element()
        self.assertEqual(base_element['element'], 'mods:titleInfo')
        self.assertEqual(base_element['attributes'], {})
        self.assertFalse(base_element['data'])
        sections = locParser.get_sections()
        self.assertEqual(len(sections), 1)
        first_section = sections[0]
        self.assertEqual(len(first_section), 1)
        self.assertEqual(first_section[0]['element'], 'mods:title')
        self.assertEqual(first_section[0]['attributes'], {})
        self.assertFalse(first_section[0]['data'])

    def test_name_tag(self):
        loc = '<mods:name type="personal"><mods:namePart>#<mods:role><mods:roleTerm type="text">winner'
        locParser = LocationParser(loc)
        base_element = locParser.get_base_element()
        self.assertEqual(base_element['element'], 'mods:name')
        self.assertEqual(base_element['attributes'], {'type': 'personal'})
        self.assertFalse(base_element['data'])
        sections = locParser.get_sections()
        self.assertEqual(len(sections), 2)
        first_section = sections[0]
        self.assertEqual(len(first_section), 1)
        self.assertEqual(first_section[0]['element'], 'mods:namePart')
        self.assertEqual(first_section[0]['attributes'], {})
        self.assertFalse(first_section[0]['data'])
        second_section = sections[1]
        self.assertEqual(len(second_section), 2)
        self.assertEqual(second_section[0]['element'], 'mods:role')
        self.assertEqual(second_section[0]['attributes'], {})
        self.assertFalse(second_section[0]['data'], {})
        self.assertEqual(second_section[1]['element'], 'mods:roleTerm')
        self.assertEqual(second_section[1]['attributes'], {'type': 'text'})
        self.assertEqual(second_section[1]['data'], 'winner')

    def test_another_tag(self):
        loc = '<mods:subject><mods:hierarchicalGeographic><mods:country>United States</mods:country><mods:state>'
        locParser = LocationParser(loc)
        base_element = locParser.get_base_element()
        self.assertEqual(base_element['element'], 'mods:subject')
        self.assertEqual(base_element['attributes'], {})
        self.assertFalse(base_element['data'])
        sections = locParser.get_sections()
        self.assertEqual(len(sections), 1)
        first_section = sections[0]
        self.assertEqual(len(first_section), 3)
        self.assertEqual(first_section[0]['element'], 'mods:hierarchicalGeographic')
        self.assertEqual(first_section[1]['element'], 'mods:country')
        self.assertEqual(first_section[1]['data'], 'United States')
        self.assertEqual(first_section[2]['element'], 'mods:state')

    def test_invalid_loc(self):
        loc = 'asdf1234'
        try:
            locParser = LocationParser(loc)
        except Exception:
            #return successfully if Exception was raised
            return
        #if we got here, no Exception was raised, so fail the test
        self.fail('Did not raise Exception on bad input!')


class TestDataHandler(unittest.TestCase):
    '''added some non-ascii characters to the files to make sure
    they're handled properly (é is u00e9, ă is u0103)'''

    def setUp(self):
        pass

    def test_xls(self):
        dh = DataHandler(os.path.join('test_files', 'data.xls'))
        mods_records = dh.get_xml_records()
        self.assertEqual(len(mods_records), 2)
        self.assertTrue(isinstance(mods_records[0].field_data()[0]['xml_path'], str))
        self.assertTrue(isinstance(mods_records[0].field_data()[0]['data'], str))
        self.assertEqual(mods_records[0].field_data()[0]['xml_path'], '<mods:identifier type="local" displayLabel="Originăl noé.">')
        self.assertEqual(mods_records[0].field_data()[0]['data'], '123')
        self.assertEqual(mods_records[0].field_data()[2]['xml_path'], '<mods:titleInfo><mods:title>')
        self.assertEqual(mods_records[0].field_data()[2]['data'], 'Test 1')
        self.assertEqual(mods_records[0].group_id, 'test1')
        self.assertEqual(mods_records[1].group_id, 'test2')
        self.assertEqual(mods_records[0].xml_id, 'test1')
        self.assertEqual(mods_records[1].xml_id, 'test2')
        #test that process_text_date is working right
        self.assertEqual(mods_records[0].field_data()[4]['data'], '2005-10-21')
        #test that we can get the second sheet correctly
        dh = DataHandler(os.path.join('test_files', 'data.xls'), sheet=2)
        mods_records = dh.get_xml_records()
        self.assertEqual(len(mods_records), 1)
        self.assertEqual(mods_records[0].xml_id, 'mods0001')
        self.assertEqual(mods_records[0].field_data()[5]['data'], '2008-10-21')

    def test_xlsx(self):
        dh = DataHandler(os.path.join('test_files', 'data.xlsx'), object_type='child')
        mods_records = dh.get_xml_records()
        self.assertEqual(mods_records[0].group_id, 'test1')
        self.assertEqual(len(mods_records), 2)
        self.assertTrue(isinstance(mods_records[0].field_data()[0]['xml_path'], str))
        self.assertTrue(isinstance(mods_records[0].field_data()[0]['data'], str))
        self.assertEqual(mods_records[0].field_data()[0]['xml_path'], '<mods:identifier type="local" displayLabel="Originăl noé.">')
        self.assertEqual(mods_records[0].field_data()[0]['data'], '123')
        self.assertEqual(mods_records[0].field_data()[2]['xml_path'], '<mods:titleInfo><mods:title>')
        self.assertEqual(mods_records[0].field_data()[2]['data'], 'Test 1')
        self.assertEqual(mods_records[0].field_data()[4]['data'], '2005-10-21')
        self.assertEqual(mods_records[0].group_id, 'test1')
        self.assertEqual(mods_records[0].xml_id, 'test1_1') #_1 because it's a child
        self.assertEqual(mods_records[1].group_id, 'test1')
        self.assertEqual(mods_records[1].xml_id, 'test1_2')

    def test_csv(self):
        dh = DataHandler(os.path.join('test_files', 'data.csv'))
        mods_records = dh.get_xml_records()
        self.assertEqual(mods_records[0].group_id, 'test1')
        self.assertEqual(len(mods_records), 2)
        self.assertTrue(isinstance(mods_records[0].field_data()[0]['xml_path'], str))
        self.assertTrue(isinstance(mods_records[0].field_data()[0]['data'], str))
        self.assertEqual(mods_records[0].field_data()[0]['xml_path'], '<mods:identifier type="local" displayLabel="Originăl noé.">')
        self.assertEqual(mods_records[0].field_data()[0]['data'], '123')
        self.assertEqual(mods_records[0].field_data()[2]['xml_path'], '<mods:titleInfo><mods:title>')
        self.assertEqual(mods_records[0].field_data()[2]['data'], 'Test 1')
        self.assertEqual(mods_records[0].group_id, 'test1')
        self.assertEqual(mods_records[0].xml_id, 'test1')
        self.assertEqual(mods_records[1].group_id, 'test2')
        self.assertEqual(mods_records[0].field_data()[4]['data'], '2005-10-21')

    def test_csv_dwc(self):
        dh = DataHandler(os.path.join('test_files', 'data_dwc.csv'))
        xml_records = dh.get_xml_records()
        self.assertEqual(xml_records[0].group_id, 'test1')
        self.assertTrue(isinstance(xml_records[0].field_data()[0]['xml_path'], str))
        self.assertTrue(isinstance(xml_records[0].field_data()[0]['data'], str))
        self.assertEqual(xml_records[0].group_id, 'test1')
        self.assertEqual(xml_records[0].xml_id, 'test1')
        self.assertEqual(xml_records[0].field_data()[0]['xml_path'], '<dwc:higherClassification>')
        self.assertEqual(xml_records[0].field_data()[0]['data'], 'higher classification')
        self.assertEqual(xml_records[0].field_data()[1]['xml_path'], '<dwc:genus>')
        self.assertEqual(xml_records[0].field_data()[1]['data'], 'Genus')
        self.assertEqual(xml_records[0].field_data()[2]['xml_path'], '<dwc:specificEpithet>')
        self.assertEqual(xml_records[0].field_data()[2]['data'], 'species')
        self.assertEqual(xml_records[0].field_data()[3]['xml_path'], '<dwc:infraspecificEpithet>')
        self.assertEqual(xml_records[0].field_data()[3]['data'], 'variety')
        self.assertEqual(xml_records[0].field_data()[4]['xml_path'], '<dwc:taxonRank>')
        self.assertEqual(xml_records[0].field_data()[4]['data'], 'variety')
        self.assertEqual(xml_records[0].field_data()[5]['xml_path'], '<dwc:scientificNameAuthorship>')
        self.assertEqual(xml_records[0].field_data()[5]['data'], 'Variety Author')
        self.assertEqual(xml_records[0].field_data()[6]['xml_path'], '<dwc:acceptedNameUsage>')
        self.assertEqual(xml_records[0].field_data()[6]['data'], 'Genus species var. variety Variety Author')
        self.assertEqual(xml_records[1].field_data()[2]['xml_path'], '<dwc:specificEpithet>')
        self.assertEqual(xml_records[1].field_data()[2]['data'], 'species2')
        self.assertEqual(xml_records[1].field_data()[3]['xml_path'], '<dwc:infraspecificEpithet>')
        self.assertEqual(xml_records[1].field_data()[3]['data'], 'subspecies')
        self.assertEqual(xml_records[1].field_data()[4]['xml_path'], '<dwc:taxonRank>')
        self.assertEqual(xml_records[1].field_data()[4]['data'], 'subspecies')
        self.assertEqual(xml_records[1].field_data()[6]['xml_path'], '<dwc:acceptedNameUsage>')
        self.assertEqual(xml_records[1].field_data()[6]['data'], 'Genus2 species2 subsp. subspecies Subspecies Author')
        self.assertEqual(xml_records[2].field_data()[2]['xml_path'], '<dwc:specificEpithet>')
        self.assertEqual(xml_records[2].field_data()[2]['data'], 'species3')
        self.assertEqual(xml_records[2].field_data()[3]['xml_path'], '<dwc:scientificNameAuthorship>')
        self.assertEqual(xml_records[2].field_data()[3]['data'], 'Species3 Author')
        self.assertEqual(xml_records[2].field_data()[4]['xml_path'], '<dwc:acceptedNameUsage>')
        self.assertEqual(xml_records[2].field_data()[4]['data'], 'Genus3 species3 Species3 Author')

    def test_csv_small(self):
        dh = DataHandler(os.path.join('test_files', 'data-small.csv'))
        mods_records = dh.get_xml_records()
        self.assertEqual(mods_records[0].group_id, 'test1')
        self.assertEqual(len(mods_records), 1)
        self.assertTrue(isinstance(mods_records[0].field_data()[0]['xml_path'], str))
        self.assertTrue(isinstance(mods_records[0].field_data()[0]['data'], str))
        self.assertEqual(mods_records[0].field_data()[0]['xml_path'], '<mods:identifier type="local" displayLabel="Originăl noé.">')
        self.assertEqual(mods_records[0].field_data()[0]['data'], '123')
        self.assertEqual(mods_records[0].field_data()[2]['xml_path'], '<mods:titleInfo><mods:title>')
        self.assertEqual(mods_records[0].field_data()[2]['data'], 'Test 1')
        self.assertEqual(mods_records[0].group_id, 'test1')
        self.assertEqual(mods_records[0].field_data()[4]['data'], '2005-10-21')


class TestOther(unittest.TestCase):
    '''Test non-class functions.'''

    def test_process_text_date(self):
        '''Tests to make sure we're handling dates properly.'''
        #dates with slashes
        self.assertEqual(process_text_date('5/14/2000'), '2000-05-14')
        self.assertEqual(process_text_date('14/5/0050'), '0050-05-14')
        #dates with dashes
        self.assertEqual(process_text_date('3-17-2013'), '2013-03-17')
        self.assertEqual(process_text_date('17-3-1813'), '1813-03-17')
        #ambiguous dates or invalid dates should stay as they are
        self.assertEqual(process_text_date('5/4/99'), '5/4/99') #4/5 or 5/4
        self.assertEqual(process_text_date('5/14/00'), '5/14/00')
        self.assertEqual(process_text_date('05/14/00'), '05/14/00')
        self.assertEqual(process_text_date('14/5/00'), '14/5/00')
        self.assertEqual(process_text_date('14/05/00'), '14/05/00')
        self.assertEqual(process_text_date('3-17-13'), '3-17-13')
        self.assertEqual(process_text_date('03-17-13'), '03-17-13')
        self.assertEqual(process_text_date('17-3-13'), '17-3-13')
        self.assertEqual(process_text_date('17-03-13'), '17-03-13')
        self.assertEqual(process_text_date('3-3-03'), '3-3-03')
        self.assertEqual(process_text_date('03-17-03'), '03-17-03')
        self.assertEqual(process_text_date('05/14/01'), '05/14/01')
        self.assertEqual(process_text_date('05-14-12'), '05-14-12')
        self.assertEqual(process_text_date(1), 1)
        self.assertEqual(process_text_date(''), '')
        self.assertEqual(process_text_date(None), None)

        #test override as well
        self.assertEqual(process_text_date('05/1812'), '1812-05')
        self.assertEqual(process_text_date('6/1912'), '1912-06')
        self.assertEqual(process_text_date('6-1912'), '1912-06')
        self.assertEqual(process_text_date('5/4/99', True), '1999-05-04')
        self.assertEqual(process_text_date('5/17/99', True), '1999-05-17')

    def test_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_path = os.path.join('test_files', 'data.xls')
            process(spreadsheet=file_path, xml_files_dir=tmp)
            self.assertTrue(os.path.exists(os.path.join(tmp, 'test1.mods.xml')))

    def test_process_no_xml_files_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_path = os.path.join('test_files', 'data.xls')
            xml_files_dir = os.path.join(tmp, 'xml_files')
            process(spreadsheet=file_path, xml_files_dir=xml_files_dir)
            self.assertTrue(os.path.exists(os.path.join(xml_files_dir, 'test1.mods.xml')))

    def test_process_spreadsheet_file_obj(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_path = os.path.join('test_files', 'data.xls')
            with open(file_path, 'rb') as f:
                process(spreadsheet=f, xml_files_dir=tmp)
            self.assertTrue(os.path.exists(os.path.join(tmp, 'test1.mods.xml')))
        with tempfile.TemporaryDirectory() as tmp:
            file_path = os.path.join('test_files', 'data.csv')
            with open(file_path, 'rb') as f:
                process(spreadsheet=f, xml_files_dir=tmp)
            self.assertTrue(os.path.exists(os.path.join(tmp, 'test1.mods.xml')))

    def test_process_minimal_spreadsheet(self):
        csv_info = 'mods id,<mods:note>\n1,asdf\n'
        with tempfile.TemporaryDirectory() as tmp:
            process(spreadsheet=io.BytesIO(csv_info.encode('utf8')), xml_files_dir=tmp, control_row=1)
            self.assertTrue(os.path.exists(os.path.join(tmp, '1.mods.xml')))


class TestControlRow(unittest.TestCase):

    def test_find_ctrl_row_first_row(self):
        csv_info = 'mods id,<mods:note>\n1,asdf\n'
        with tempfile.TemporaryDirectory() as tmp:
            process(spreadsheet=io.BytesIO(csv_info.encode('utf8')), xml_files_dir=tmp)
            self.assertTrue(os.path.exists(os.path.join(tmp, '1.mods.xml')))
            self.assertEqual(len(os.listdir(tmp)), 1)

    def test_find_ctrl_row_second_row(self):
        csv_info = 'MODS,Note\nmods id,<mods:note>\n1,asdf\n'
        with tempfile.TemporaryDirectory() as tmp:
            process(spreadsheet=io.BytesIO(csv_info.encode('utf8')), xml_files_dir=tmp)
            self.assertTrue(os.path.exists(os.path.join(tmp, '1.mods.xml')))
            self.assertEqual(len(os.listdir(tmp)), 1)

    def test_no_ctrl_row(self):
        csv_info = 'MODS,Note\n1,asdf\n2,jkl;'
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ControlRowError):
                process(spreadsheet=io.BytesIO(csv_info.encode('utf8')), xml_files_dir=tmp)


class TestMapper(unittest.TestCase):

    FULL_MODS = '''<?xml version='1.0' encoding='UTF-8'?>
<mods:mods xmlns:mods="http://www.loc.gov/mods/v3" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.loc.gov/mods/v3 http://www.loc.gov/standards/mods/v3/mods-3-7.xsd" ID="mods000">
  <mods:physicalDescription>
    <mods:extent>1 video file</mods:extent>
    <mods:digitalOrigin>reformatted digital</mods:digitalOrigin>
    <mods:note>note 1</mods:note>
  </mods:physicalDescription>
  <mods:titleInfo>
    <mods:title>é. 1 Test</mods:title>
    <mods:partName>part #1</mods:partName>
    <mods:partNumber>1</mods:partNumber>
  </mods:titleInfo>
  <mods:titleInfo type="alternative" displayLabel="display">
    <mods:title>Alt Title</mods:title>
    <mods:nonSort>The</mods:nonSort>
  </mods:titleInfo>
  <mods:identifier type="local" displayLabel="Original no.">1591</mods:identifier>
  <mods:identifier type="local" displayLabel="PN_DB_id">321</mods:identifier>
  <mods:genre authority="aat">Programming Tests</mods:genre>
  <mods:originInfo displayLabel="Date Ądded to Colléction">
    <mods:publisher>Publisher</mods:publisher>
    <mods:place>
      <mods:placeTerm>USA</mods:placeTerm>
    </mods:place>
    <mods:dateOther encoding="w3cdtf" keyDate="yes">2010-01-31</mods:dateOther>
    <mods:dateCreated encoding="w3cdtf" point="end">7/13/1899</mods:dateCreated>
    <mods:dateCreated encoding="w3cdtf">1972-10-1973-07-07</mods:dateCreated>
    <mods:dateCreated encoding="w3cdtf" point="start" keyDate="yes">1972-10</mods:dateCreated>
    <mods:dateCreated encoding="w3cdtf" point="end">1973-07-07</mods:dateCreated>
    <mods:dateIssued encoding="w3cdtf">1974-01-01</mods:dateIssued>
    <mods:dateCaptured encoding="w3cdtf">1975-01-01</mods:dateCaptured>
    <mods:dateValid encoding="w3cdtf">1976-01-01</mods:dateValid>
    <mods:dateModified encoding="w3cdtf">1977-01-01</mods:dateModified>
    <mods:copyrightDate>1978-01-##</mods:copyrightDate>
  </mods:originInfo>
  <mods:subject>
    <mods:topic>PROGRĄMMING</mods:topic>
  </mods:subject>
  <mods:subject>
    <mods:topic>Testing</mods:topic>
  </mods:subject>
  <mods:subject>
    <mods:topic>Software</mods:topic>
    <mods:topic>Testing</mods:topic>
  </mods:subject>
  <mods:subject authority="local">
    <mods:topic>Recursion</mods:topic>
  </mods:subject>
  <mods:subject authority="local">
    <mods:temporal>1990s</mods:temporal>
  </mods:subject>
  <mods:subject>
    <mods:geographic>United States</mods:geographic>
  </mods:subject>
  <mods:subject>
    <mods:hierarchicalGeographic>
      <mods:country>United States</mods:country>
      <mods:state>Pennsylvania</mods:state>
    </mods:hierarchicalGeographic>
  </mods:subject>
  <mods:name type="personal">
    <mods:namePart>Smith</mods:namePart>
    <mods:role>
      <mods:roleTerm>creator</mods:roleTerm>
    </mods:role>
  </mods:name>
  <mods:name type="personal">
    <mods:namePart>Jones, T.</mods:namePart>
    <mods:namePart type="date">1799-1889</mods:namePart>
  </mods:name>
  <mods:name type="personal">
    <mods:namePart>Bob</mods:namePart>
    <mods:role>
      <mods:roleTerm type="text">winner</mods:roleTerm>
    </mods:role>
  </mods:name>
  <mods:name type="personal">
    <mods:namePart>Fob, Bob</mods:namePart>
  </mods:name>
  <mods:name type="personal">
    <mods:namePart>Smith, Ted</mods:namePart>
    <mods:namePart type="date">1900-2013</mods:namePart>
    <mods:namePart type="termsOfAddress">Sir</mods:namePart>
  </mods:name>
  <mods:note displayLabel="note label">Note 1&amp;2</mods:note>
  <mods:note>3&lt;4</mods:note>
  <mods:note>another note</mods:note>
  <mods:location>
    <mods:physicalLocation>zzz</mods:physicalLocation>
    <mods:url>http://www.example.com</mods:url>
    <mods:holdingSimple>
      <mods:copyInformation>
        <mods:note>Note 1</mods:note>
      </mods:copyInformation>
    </mods:holdingSimple>
  </mods:location>
  <mods:typeOfResource>video</mods:typeOfResource>
  <mods:language>
    <mods:languageTerm authority="iso639-2b" type="code">eng</mods:languageTerm>
  </mods:language>
  <mods:relatedItem type="related item" displayLabel="display">
    <mods:titleInfo>
      <mods:title>Some related item display title</mods:title>
    </mods:titleInfo>
  </mods:relatedItem>
</mods:mods>
'''

    def test_mods_output(self):
        self.maxDiff = None
        m1 = Mapper('mods', [])
        mods = m1.get_xml()
        self.assertTrue(isinstance(mods, Mods))
        #put some data in here, so we can pass this as a parent_mods to the next test
        # these next two should be deleted and not displayed twice
        m1.add_data('<mods:identifier type="local" displayLabel="Original no.">', '1591')
        m1.add_data('<mods:subject><mods:topic>', 'Recursion')
        # this one isn't added again, and should still be in the output
        m1.add_data('<mods:physicalDescription><mods:extent>#<mods:digitalOrigin>#<mods:note>', '1 video file#reformatted digital#note 1')
        #add all data as str, not bytes, since that's how it should be coming from DataHandler
        m = Mapper('mods', [], parent_mods=m1.get_xml())
        m.add_data('<mods:mods ID="">', 'mods000')
        m.add_data('<mods:titleInfo><mods:title>#<mods:partName>#<mods:partNumber>', 'é. 1 Test#part \#1#1')
        m.add_data('<mods:titleInfo type="alternative" displayLabel="display"><mods:title>#<mods:nonSort>', 'Alt Title#The')
        m.add_data('<mods:identifier type="local" displayLabel="Original no.">', '1591')
        m.add_data('<mods:identifier type="local" displayLabel="PN_DB_id">', '321')
        m.add_data('<mods:genre authority="aat">', 'Programming Tests')
        m.add_data('<mods:originInfo><mods:publisher>', 'Publisher')
        m.add_data('<mods:originInfo><mods:place><mods:placeTerm>', 'USA')
        m.add_data('<mods:originInfo displayLabel="Date Ądded to Colléction"><mods:dateOther encoding="w3cdtf" keyDate="yes">', '2010-01-31')
        m.add_data('<mods:subject><mods:topic>', 'PROGRĄMMING || Testing')
        m.add_data('<mods:subject><mods:topic>#<mods:topic>', 'Software#Testing')
        m.add_data('<mods:subject authority="local"><mods:topic>', 'Recursion || ')
        m.add_data('<mods:subject authority="local"><mods:temporal>', '1990s')
        m.add_data('<mods:subject><mods:geographic>', 'United States')
        m.add_data('<mods:subject><mods:hierarchicalGeographic><mods:country>United States</mods:country><mods:state>', 'Pennsylvania')
        m.add_data('<mods:name type="personal"><mods:namePart>#<mods:role><mods:roleTerm>', 'Smith#creator || Jones, T.')
        m.add_data('<mods:namePart type="date">', '1799-1889')
        m.add_data('<mods:name type="personal"><mods:namePart>#<mods:role><mods:roleTerm type="text">winner', 'Bob')
        m.add_data('<mods:name type="personal"><mods:namePart>#<mods:namePart type="date">#<mods:namePart type="termsOfAddress">', 'Fob, Bob || Smith, Ted#1900-2013#Sir')
        m.add_data('<mods:originInfo><mods:dateCreated encoding="w3cdtf" point="end">', '7/13/1899')
        m.add_data('<mods:originInfo><mods:dateCreated encoding="w3cdtf">#<mods:dateCreated encoding="w3cdtf" point="start" keyDate="yes">#<mods:dateCreated encoding="w3cdtf" point="end">', '1972-10-1973-07-07#1972-10#1973-07-07')
        m.add_data('<mods:note displayLabel="note label">', 'Note 1&2')
        m.add_data('<mods:note>', '3<4')
        m.add_data('<mods:location><mods:physicalLocation>zzz#<mods:url>#<mods:holdingSimple><mods:copyInformation><mods:note>', '#http://www.example.com#Note 1')
        m.add_data('<mods:note>', 'another note')
        m.add_data('<mods:typeOfResource>', 'video')
        m.add_data('<mods:language><mods:languageTerm authority="iso639-2b" type="code">', 'eng')
        m.add_data('<mods:relatedItem type="related item" displayLabel="display"><mods:titleInfo><mods:title>', 'Some related item display title')
        m.add_data('<mods:originInfo><mods:dateIssued encoding="w3cdtf">', '1974-01-01')
        m.add_data('<mods:originInfo><mods:dateCaptured encoding="w3cdtf">', '1975-01-01')
        m.add_data('<mods:originInfo><mods:dateValid encoding="w3cdtf">', '1976-01-01')
        m.add_data('<mods:originInfo><mods:dateModified encoding="w3cdtf">', '1977-01-01')
        m.add_data('<mods:originInfo><mods:copyrightDate>', '1978-01-##')
        mods = m.get_xml()
        mods_data = mods.serializeDocument(pretty=True).decode('utf8')
        self.assertTrue(isinstance(mods, Mods))
        self.assertEqual(mods.title_info_list[0].title, 'é. 1 Test')
        self.assertEqual(mods.title_info_list[0].part_number, '1')
        self.assertEqual(mods.title_info_list[0].part_name, 'part #1')
        #this does assume that the attributes will always be written out in the same order
        self.assertEqual(mods_data, self.FULL_MODS)

    def test_get_data_divs(self):
        m = Mapper('mods', [])
        self.assertEqual(m._get_data_divs('part1#part2#part3', False), ['part1#part2#part3'])
        self.assertEqual(m._get_data_divs('part1#part2#part3', True), ['part1', 'part2', 'part3'])
        self.assertEqual(m._get_data_divs('part\#1#part2#part\#3', True), ['part#1', 'part2', 'part#3'])
        self.assertEqual(m._get_data_divs('part\#1 and \#1a#part2#part\#3', True), ['part#1 and #1a', 'part2', 'part#3'])

    def test_dwc(self):
        m = Mapper('dwc', [])
        m.add_data('<dwc:scientificName>', 'Scientific Name')
        m.add_data('<dwc:higherClassification>', 'Higher Classification')
        m.add_data('<dwc:kingdom>', 'Kingdom')
        m.add_data('<dwc:phylum>', 'Phylum')
        m.add_data('<dwc:class>', 'Class')
        m.add_data('<dwc:order>', 'Order')
        m.add_data('<dwc:family>', 'Family')
        m.add_data('<dwc:genus>', 'Genus')
        m.add_data('<dwc:infraspecificEpithet>', 'Subspecies')
        m.add_data('<dwc:recordedBy>', 'Sci Entist || Phy Sycist')
        m.add_data('<dwc:recordNumber>', '2')
        m.add_data('<dwc:municipality>', 'Muni')
        m.add_data('<dwc:locality>', 'locality')
        dwc_set = m.get_xml()
        dwc = dwc_set.simple_darwin_record
        self.assertTrue(isinstance(dwc, SimpleDarwinRecord))
        self.assertEqual(dwc.scientific_name, 'Scientific Name')
        self.assertEqual(dwc.higher_classification, 'Higher Classification')
        self.assertEqual(dwc.kingdom, 'Kingdom')
        self.assertEqual(dwc.phylum, 'Phylum')
        self.assertEqual(dwc.class_, 'Class')
        self.assertEqual(dwc.order, 'Order')
        self.assertEqual(dwc.family, 'Family')
        self.assertEqual(dwc.genus, 'Genus')
        self.assertEqual(dwc.infraspecific_epithet, 'Subspecies')
        self.assertEqual(dwc.recorded_by, 'Sci Entist | Phy Sycist')
        self.assertEqual(dwc.record_number, '2')
        self.assertEqual(dwc.municipality, 'Muni')


if __name__ == '__main__':
    runner = unittest.TextTestRunner(verbosity=2)
    unittest.main(testRunner=runner)

