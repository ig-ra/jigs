from pathlib import Path
import tempfile
import unittest

from stats.ticket_flow import csvio


class CsvTests(unittest.TestCase):
    def test_stable_order_precision_and_blanks(self):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'data.csv'
            rows=[{'a':'z','b':None},{'a':'a','b':1.0}]
            csvio.write(path,rows,('a','b'))
            expected=path.read_bytes()
            csvio.write(path,list(reversed(rows)),('a','b'))
            self.assertEqual(path.read_bytes(),expected)
            self.assertEqual(expected,b'a,b\na,1.000000\nz,\n')

    def test_empty_table_headers_and_failure_before_publication(self):
        with tempfile.TemporaryDirectory() as name:
            directory=Path(name)/'run'
            empty={key:[] for key in csvio.SCHEMAS}
            csvio.publish(directory,empty)
            before={p.name:p.read_bytes() for p in directory.iterdir()}
            with self.assertRaises(KeyError):
                csvio.publish(directory,{'calls':[]})
            self.assertEqual(before,{p.name:p.read_bytes() for p in directory.iterdir()})
