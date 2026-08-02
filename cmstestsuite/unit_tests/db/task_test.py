#!/usr/bin/env python3

import unittest

from cms.db import Attachment, Testcase
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin


class TestParticipationScopedArtifacts(DatabaseMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.task = self.add_task()
        self.dataset = self.add_dataset(task=self.task)
        self.participation = self.add_participation()
        self.session.flush()

    def test_task_attachment_prefers_participation_specific_copy(self):
        shared_attachment = Attachment(
            task=self.task,
            filename="statement.txt",
            digest="shared-digest",
        )
        participant_attachment = Attachment(
            task=self.task,
            filename="statement.txt",
            digest="participant-digest",
            participation=self.participation,
        )
        self.session.add_all([shared_attachment, participant_attachment])
        self.session.flush()

        self.assertIs(
            self.task.get_attachment("statement.txt", self.participation),
            participant_attachment,
        )
        self.assertIs(
            self.task.get_attachment("statement.txt", None),
            shared_attachment,
        )

    def test_dataset_testcase_prefers_participation_specific_copy(self):
        shared_testcase = Testcase(
            dataset=self.dataset,
            codename="sample",
            input="shared-input",
            output="shared-output",
        )
        participant_testcase = Testcase(
            dataset=self.dataset,
            codename="sample",
            input="participant-input",
            output="participant-output",
            participation=self.participation,
        )
        self.session.add_all([shared_testcase, participant_testcase])
        self.session.flush()

        self.assertIs(
            self.dataset.get_testcase("sample", self.participation),
            participant_testcase,
        )
        self.assertIs(
            self.dataset.get_testcase("sample", None),
            shared_testcase,
        )
