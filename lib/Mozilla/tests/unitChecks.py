# -*- coding: utf-8 -*-

import unittest

from Mozilla.Checks import getChecks
from Mozilla.Parser import getParser, Entity
from Mozilla.Paths import File


class BaseHelper(unittest.TestCase):
    file = None
    refContent = None

    def setUp(self):
        p = getParser(self.file.file)
        p.readContents(self.refContent)
        self.refList, self.refMap = p.parse()

    def _test(self, content, refWarnOrErrors):
        p = getParser(self.file.file)
        p.readContents(content)
        l10n = [e for e in p]
        assert len(l10n) == 1
        l10n = l10n[0]
        checks = getChecks(self.file)
        ref = self.refList[self.refMap[l10n.key]]
        found = tuple(checks(ref, l10n))
        self.assertEqual(found, refWarnOrErrors)


class TestPlurals(BaseHelper):
    file = File('foo.properties', 'foo.properties')
    refContent = '''# LOCALIZATION NOTE (downloadsTitleFiles): Semi-colon list of plural forms.
# See: http://developer.mozilla.org/en/docs/Localization_and_Plurals
# #1 number of files
# example: 111 files - Downloads
downloadsTitleFiles=#1 file - Downloads;#1 files - #2
'''

    def testGood(self):
        self._test('''# LOCALIZATION NOTE (downloadsTitleFiles): Semi-colon list of plural forms.
# See: http://developer.mozilla.org/en/docs/Localization_and_Plurals
# #1 number of files
# example: 111 files - Downloads
downloadsTitleFiles=#1 file - Downloads;#1 files - #2;#1 filers
''',
                   tuple())

    def testNotUsed(self):
        self._test('''# LOCALIZATION NOTE (downloadsTitleFiles): Semi-colon list of plural forms.
# See: http://developer.mozilla.org/en/docs/Localization_and_Plurals
# #1 number of files
# example: 111 files - Downloads
downloadsTitleFiles=#1 file - Downloads;#1 files - Downloads;#1 filers
''',
                   (('warning', 0, 'not all variables used in l10n', 'plural'),))

    def testNotDefined(self):
        self._test('''# LOCALIZATION NOTE (downloadsTitleFiles): Semi-colon list of plural forms.
# See: http://developer.mozilla.org/en/docs/Localization_and_Plurals
# #1 number of files
# example: 111 files - Downloads
downloadsTitleFiles=#1 file - Downloads;#1 files - #2;#1 #3
''',
                   (('error', 0, 'unreplaced variables in l10n', 'plural'),))


class TestDTDs(BaseHelper):
    file = File('foo.dtd', 'foo.dtd')
    refContent = '''<!ENTITY foo "This is &apos;good&apos;">
<!ENTITY width "10ch">
<!ENTITY style "width: 20ch; height: 280px;">
<!ENTITY minStyle "min-height: 50em;">
<!ENTITY ftd "0">
'''
    def testWarning(self):
        self._test('''<!ENTITY foo "This is &not; good">
''',
                   (('warning',(0,0),'Referencing unknown entity `not`', 'xmlparse'),))
        # make sure we only handle translated entity references
        self._test(u'''<!ENTITY foo "This is &ƞǿŧ; good">
'''.encode('utf-8'),
                   (('warning',(0,0),u'Referencing unknown entity `ƞǿŧ`', 'xmlparse'),))
    def testErrorFirstLine(self):
        self._test('''<!ENTITY foo "This is </bad> stuff">
''',
                   (('error',(1,10),'mismatched tag', 'xmlparse'),))
    def testErrorSecondLine(self):
        self._test('''<!ENTITY foo "This is
  </bad>
stuff">
''',
                   (('error',(2,4),'mismatched tag', 'xmlparse'),))
    def testXMLEntity(self):
        self._test('''<!ENTITY foo "This is &quot;good&quot;">
''',
                   tuple())
    def testNoNumber(self):
        self._test('''<!ENTITY ftd "foo">''',
                   (('warning', 0, 'reference is a number', 'number'),))
    def testNoLength(self):
        self._test('''<!ENTITY width "15miles">''',
                   (('error', 0, 'reference is a CSS length', 'css'),))
    def testNoStyle(self):
        self._test('''<!ENTITY style "15ch">''',
                   (('error', 0, 'reference is a CSS spec', 'css'),))
        self._test('''<!ENTITY style "junk">''',
                   (('error', 0, 'reference is a CSS spec', 'css'),))
    def testStyleWarnings(self):
        self._test('''<!ENTITY style "width:15ch">''',
                   (('warning', 0, 'height only in reference', 'css'),))
        self._test('''<!ENTITY style "width:15em;height:200px;">''',
                   (('warning', 0, "units for width don't match (em != ch)", 'css'),))
    def testNoWarning(self):
        self._test('''<!ENTITY width "12em">''', tuple())
        self._test('''<!ENTITY style "width:12ch;height:200px;">''', tuple())
        self._test('''<!ENTITY ftd "0">''', tuple())


class TestAndroid(unittest.TestCase):
    """Test Android checker

    Make sure we're hitting our extra rules only if
    we're passing in a DTD file in the embedding/android module.
    """
    apos_msg = u"Apostrophes in Android DTDs need escaping with \\' or \\u0027, " + \
               u"or use \u2019, or put string in quotes."
    quot_msg = u"Quotes in Android DTDs need escaping with \\\" or \\u0022, " + \
               u"or put string in apostrophes."
    def getEntity(self, v):
        return Entity(v, lambda s: s, (0, len(v)), (), (0, 0), (), (), (0, len(v)), ())
    def test_android_dtd(self):
        """Testing the actual android checks. The logic is involved, so this is a lot
        of nitty gritty detail tests.
        """
        f = File("embedding/android/strings.dtd", "strings.dtd", "embedding/android")
        checks = getChecks(f)
        # good string
        ref = self.getEntity("plain string")
        l10n = self.getEntity("plain localized string")
        self.assertEqual(tuple(checks(ref, l10n)),
                         ())
        # dtd warning
        l10n = self.getEntity("plain localized string &ref;")
        self.assertEqual(tuple(checks(ref, l10n)),
                         (('warning', (0, 0), 'Referencing unknown entity `ref`', 'xmlparse'),))
        # no report on stray ampersand or quote, if not completely quoted
        for i in xrange(3):
            # make sure we're catching unescaped apostrophes, try 0..5 backticks
            l10n = self.getEntity("\\"*(2*i) + "'")
            self.assertEqual(tuple(checks(ref, l10n)),
                             (('error', 2*i, self.apos_msg, 'android'),))
            l10n = self.getEntity("\\"*(2*i + 1) + "'")
            self.assertEqual(tuple(checks(ref, l10n)),
                             ())
            # make sure we don't report if apos string is quoted
            l10n = self.getEntity('"' + "\\"*(2*i) + "'\"")
            tpl = tuple(checks(ref, l10n))
            self.assertEqual(tpl, (), "`%s` shouldn't fail but got %s" % (l10n.val, str(tpl)))
            l10n = self.getEntity('"' + "\\"*(2*i+1) + "'\"")
            tpl = tuple(checks(ref, l10n))
            self.assertEqual(tpl, (), "`%s` shouldn't fail but got %s" % (l10n.val, str(tpl)))
            # make sure we're catching unescaped quotes, try 0..5 backticks
            l10n = self.getEntity("\\"*(2*i) + "\"")
            self.assertEqual(tuple(checks(ref, l10n)),
                             (('error', 2*i, self.quot_msg, 'android'),))
            l10n = self.getEntity("\\"*(2*i + 1) + "'")
            self.assertEqual(tuple(checks(ref, l10n)),
                             ())
            # make sure we don't report if quote string is single quoted
            l10n = self.getEntity("'" + "\\"*(2*i) + "\"'")
            tpl = tuple(checks(ref, l10n))
            self.assertEqual(tpl, (), "`%s` shouldn't fail but got %s" % (l10n.val, str(tpl)))
            l10n = self.getEntity('"' + "\\"*(2*i+1) + "'\"")
            tpl = tuple(checks(ref, l10n))
            self.assertEqual(tpl, (), "`%s` shouldn't fail but got %s" % (l10n.val, str(tpl)))
        # check for mixed quotes and ampersands
        l10n = self.getEntity("'\"")
        self.assertEqual(tuple(checks(ref, l10n)),
                         (('error', 0, self.apos_msg, 'android'),
                          ('error', 1, self.quot_msg, 'android')))
        l10n = self.getEntity("''\"'")
        self.assertEqual(tuple(checks(ref, l10n)),
                         (('error', 1, self.apos_msg, 'android'),))
        l10n = self.getEntity('"\'""')
        self.assertEqual(tuple(checks(ref, l10n)),
                         (('error', 2, self.quot_msg, 'android'),))
        
        # broken unicode escape
        l10n = self.getEntity("Some broken \u098 unicode")
        self.assertEqual(tuple(checks(ref, l10n)),
                         (('error', 12, 'truncated \\uXXXX escape', 'android'),))
        # broken unicode escape, try to set the error off
        l10n = self.getEntity(u"\u9690"*14+"\u006"+"  "+"\u0064")
        self.assertEqual(tuple(checks(ref, l10n)),
                         (('error', 14, 'truncated \\uXXXX escape', 'android'),))
    def test_android_prop(self):
        f = File("embedding/android/strings.properties", "strings.properties", "embedding/android")
        checks = getChecks(f)
        # good plain string
        ref = self.getEntity("plain string")
        l10n = self.getEntity("plain localized string")
        self.assertEqual(tuple(checks(ref, l10n)),
                         ())
        # no dtd warning
        ref = self.getEntity("plain string")
        l10n = self.getEntity("plain localized string &ref;")
        self.assertEqual(tuple(checks(ref, l10n)),
                         ())
        # no report on stray ampersand
        ref = self.getEntity("plain string")
        l10n = self.getEntity("plain localized string with apos: '")
        self.assertEqual(tuple(checks(ref, l10n)),
                         ())
        # report on bad printf
        ref = self.getEntity("string with %s")
        l10n = self.getEntity("string with %S")
        self.assertEqual(tuple(checks(ref, l10n)),
                         (('error', 0, 'argument 1 `S` should be `s`', 'printf'),))
    def test_non_android_dtd(self):
        f = File("browser/strings.dtd", "strings.dtd", "browser")
        checks = getChecks(f)
        # good string
        ref = self.getEntity("plain string")
        l10n = self.getEntity("plain localized string")
        self.assertEqual(tuple(checks(ref, l10n)),
                         ())
        # dtd warning
        ref = self.getEntity("plain string")
        l10n = self.getEntity("plain localized string &ref;")
        self.assertEqual(tuple(checks(ref, l10n)),
                         (('warning', (0, 0), 'Referencing unknown entity `ref`', 'xmlparse'),))
        # no report on stray ampersand
        ref = self.getEntity("plain string")
        l10n = self.getEntity("plain localized string with apos: '")
        self.assertEqual(tuple(checks(ref, l10n)),
                         ())


if __name__ == '__main__':
    unittest.main()
