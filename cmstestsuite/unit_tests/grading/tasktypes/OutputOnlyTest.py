#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Stefano Maggiolo <s.maggiolo@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Tests for the OutputOnly task type."""

import io
import unittest
from unittest.mock import MagicMock

from cms.db import File
from cms.grading.Job import EvaluationJob
from cms.grading.tasktypes.OutputOnly import OutputOnly
from cms.service.esoperations import ESOperation
from cmstestsuite.unit_tests.grading.tasktypes.tasktypetestutils import \
    OUTCOME, TEXT, TaskTypeTestMixin


FILE_001 = File(digest="digest of 001", filename="out_001.txt")
FILE_023 = File(digest="digest of 023", filename="out_023.txt")
NEWLINES = [b"\n", b"\r\n"]


class TestEvaluate(TaskTypeTestMixin, unittest.TestCase):
    """Tests for evaluate().

    prepare() creates a task type and a job with the given arguments, and in
    addition sets up successful return values for eval_output.

    """

    def setUp(self):
        super().setUp()
        self.setUpMocks("OutputOnly")
        self.file_cacher = MagicMock()
        self.file_cacher.get_file_content.return_value = b"output\r\n"
        self.file_cacher.get_file.side_effect = lambda digest: io.BytesIO(
            self.file_cacher.get_file_content.return_value)

    @staticmethod
    def job(files):
        operation = ESOperation(ESOperation.EVALUATION, 1, 1, "023")
        return EvaluationJob(input="digest of input",
                             output="digest of correct output",
                             files=files,
                             operation=operation,
                             multithreaded_sandbox=True)

    def prepare(self, parameters, files):
        tt = OutputOnly(parameters)
        job = self.job(files)
        self.eval_output.return_value = (True, OUTCOME, TEXT, None)
        return tt, job

    def assertResultsInJob(self, job, success, outcome, text, stats):
        self.assertEqual(job.success, success)
        self.assertEqual(job.outcome, outcome)
        self.assertEqual(job.text, text)
        self.assertEqual(job.plus, stats)

    def test_diff_success(self):
        tt, job = self.prepare(["diff"], {
            "out_001.txt": FILE_001,
            "out_023.txt": FILE_023
        })

        tt.evaluate(job, self.file_cacher)

        self.eval_output.assert_called_once_with(
            self.file_cacher, job, None, user_output_digest="digest of 023")
        self.assertResultsInJob(job, True, str(OUTCOME), TEXT, {})

    def test_diff_missing_file(self):
        tt, job = self.prepare(["diff"], {
            "out_001.txt": FILE_001,
        })

        tt.evaluate(job, self.file_cacher)

        self.eval_output.assert_not_called()
        self.assertResultsInJob(job,
                                True, str(0.0), ["File not submitted"], {})

    def test_diff_failure(self):
        tt, job = self.prepare(["diff"], {
            "out_001.txt": FILE_001,
            "out_023.txt": FILE_023
        })
        self.eval_output.return_value = False, None, None, None

        tt.evaluate(job, self.file_cacher)

        self.eval_output.assert_called_once_with(
            self.file_cacher, job, None, user_output_digest="digest of 023")
        self.assertResultsInJob(job, False, None, None, None)

    def test_comparator_success(self):
        tt, job = self.prepare(["comparator"], {
            "out_001.txt": FILE_001,
            "out_023.txt": FILE_023
        })

        tt.evaluate(job, self.file_cacher)

        self.eval_output.assert_called_once_with(
            self.file_cacher, job, "checker",
            user_output_digest="digest of 023")
        self.assertResultsInJob(job, True, str(OUTCOME), TEXT, {})

    def evaluate(self, content):
        """Evaluate a user output, recording what eval_output was given."""
        self.file_cacher.reset_mock()
        self.eval_output.reset_mock()
        tt, job = self.prepare(["comparator"], {"out_023.txt": FILE_023})
        self.file_cacher.get_file_content.return_value = content
        evaluated = {}

        def eval_output(file_cacher, job, checker, user_output_digest=None,
                        user_output_path=None):
            evaluated["digest"] = user_output_digest
            if user_output_path is not None:
                with open(user_output_path, "rb") as f:
                    evaluated["content"] = f.read()
            return True, OUTCOME, TEXT, None

        self.eval_output.side_effect = eval_output
        tt.evaluate(job, self.file_cacher)

        self.file_cacher.get_file.assert_called_once_with("digest of 023")
        self.assertResultsInJob(job, True, str(OUTCOME), TEXT, {})
        return evaluated

    def test_no_bom_is_evaluated_as_is(self):
        for newline in NEWLINES:
            with self.subTest(newline=newline):
                self.assertEqual(self.evaluate(b"output" + newline),
                                 {"digest": "digest of 023"})
                self.file_cacher.get_file_content.assert_not_called()

    def assertConvertedForEachNewline(self, encode):
        for newline in NEWLINES:
            with self.subTest(newline=newline):
                text = "output" + newline.decode()
                self.assertEqual(
                    self.evaluate(encode("\ufeff" + text)),
                    {"digest": None, "content": text.encode()})
                self.file_cacher.get_file_content.assert_called_once_with(
                    "digest of 023")

    def test_utf16_le_bom_is_evaluated_as_utf8(self):
        self.assertConvertedForEachNewline(lambda s: s.encode("utf-16-le"))

    def test_utf16_be_bom_is_evaluated_as_utf8(self):
        self.assertConvertedForEachNewline(lambda s: s.encode("utf-16-be"))

    def test_utf32_le_bom_is_evaluated_as_utf8(self):
        self.assertConvertedForEachNewline(lambda s: s.encode("utf-32-le"))

    def test_utf32_be_bom_is_evaluated_as_utf8(self):
        self.assertConvertedForEachNewline(lambda s: s.encode("utf-32-be"))

    def test_utf8_bom_is_stripped(self):
        self.assertConvertedForEachNewline(lambda s: s.encode("utf-8"))

    def test_undecodable_is_evaluated_as_is(self):
        for content in [b"\xff\xfe1", b"\xff\xfe\x00\x001"]:
            with self.subTest(content=content):
                self.assertEqual(self.evaluate(content),
                                 {"digest": "digest of 023"})

    def test_nothing_is_stored(self):
        self.evaluate("\ufeffoutput\r\n".encode("utf-16-le"))
        self.file_cacher.put_file_content.assert_not_called()
        self.file_cacher.put_file.assert_not_called()


if __name__ == "__main__":
    unittest.main()
