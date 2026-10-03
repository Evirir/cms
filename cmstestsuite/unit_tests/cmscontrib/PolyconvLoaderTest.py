"""Tests for the polyconv Polygon task loaders."""

import subprocess
import tempfile
import unittest
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from cmscontrib.loaders import LOADERS
from cmscontrib.loaders.polyconv import (
    PolyconvBatchTaskLoader,
    PolyconvOutputOnlyTaskLoader,
)


class FakeFileCacher:
    """Store cached file contents in memory by digest."""

    def __init__(self):
        self.files = {}

    def put_file_from_path(self, path, _description):
        """Cache one file and return its content digest."""
        content = Path(path).read_bytes()
        digest = sha256(content).hexdigest()
        self.files[digest] = content
        return digest


class TestPolyconvLoaders(unittest.TestCase):
    """Exercise Batch and OutputOnly imports from one Polygon package."""

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.package_path = Path(self.temporary_directory.name) / "polygon-task"
        self.package_path.mkdir()
        self.file_cacher = FakeFileCacher()
        self.compiled_checker_directories = []
        self._write_package()

        patcher = patch(
            "cmscontrib.loaders.polyconv.subprocess.run",
            side_effect=self._compile_checker,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _write_package(self):
        tests_path = self.package_path / "tests"
        tests_path.mkdir()
        test_data = [
            ("samples", "0"),
            ("samples", "0"),
            ("s1-OO", "5"),
            ("s1", "0"),
        ]
        for test_id in range(1, len(test_data) + 1):
            (tests_path / f"{test_id:02}").write_text(
                f"input {test_id}", encoding="utf-8"
            )
            (tests_path / f"{test_id:02}.a").write_text(
                f"output {test_id}", encoding="utf-8"
            )

        files_path = self.package_path / "files"
        files_path.mkdir()
        (files_path / "check.cpp").write_text(
            '#include "testlib.h"\n#include "global.h"\nint main() { return VALUE; }\n',
            encoding="utf-8",
        )
        (files_path / "global.h").write_text("#define VALUE 0\n", encoding="utf-8")
        (files_path / "testlib.h").write_text("polygon testlib", encoding="utf-8")

        tests_xml = "\n".join(
            f'<test group="{group}" points="{points}"/>' for group, points in test_data
        )
        problem_xml = f"""<problem>
  <names><name language="english" value="Test task"/></names>
  <judging input-file="" output-file="">
    <testset name="tests">
      <time-limit>1000</time-limit>
      <memory-limit>268435456</memory-limit>
      <test-count>{len(test_data)}</test-count>
      <input-path-pattern>tests/%02d</input-path-pattern>
      <answer-path-pattern>tests/%02d.a</answer-path-pattern>
      <tests>{tests_xml}</tests>
      <groups>
        <group name="samples" points="0" points-policy="complete-group"/>
        <group name="s1-OO" points-policy="each-test"/>
        <group name="s1" points="20" points-policy="complete-group">
          <dependencies><dependency group="s1-OO"/></dependencies>
        </group>
      </groups>
    </testset>
  </judging>
  <assets><checker><source path="files/check.cpp"/></checker></assets>
</problem>"""
        (self.package_path / "problem.xml").write_text(problem_xml, encoding="utf-8")

    def _compile_checker(self, command, check):
        self.assertFalse(check)
        source_path = Path(command[-1])
        self.assertTrue((source_path.parent / "global.h").is_file())
        self.assertNotEqual(
            (source_path.parent / "testlib.h").read_text(encoding="utf-8"),
            "polygon testlib",
        )
        output_path = Path(command[command.index("-o") + 1])
        output_path.write_bytes(b"compiled checker")
        self.compiled_checker_directories.append(source_path.parent)
        return subprocess.CompletedProcess(command, 0)

    def _archive_names(self, attachment):
        content = self.file_cacher.files[attachment.digest]
        with ZipFile(BytesIO(content)) as archive:
            return set(archive.namelist())

    def test_batch_loader_imports_group_scoring_and_samples(self):
        loader = PolyconvBatchTaskLoader(self.package_path.as_posix(), self.file_cacher)

        task = loader.get_task(get_statement=False)

        self.assertEqual(task.name, "polygon-task")
        self.assertEqual(task.submission_format, ["polygon-task.%l"])
        dataset = task.active_dataset
        self.assertEqual(dataset.task_type, "Batch")
        self.assertEqual(
            dataset.task_type_parameters, ["alone", ["", ""], "comparator"]
        )
        self.assertEqual(dataset.score_type, "GroupMin")
        self.assertEqual(
            dataset.score_type_parameters,
            [
                [0, ".*_(samples)"],
                [5, ".*3_s1-OO"],
                [20, ".*_(s1|s1-OO)"],
            ],
        )
        self.assertEqual(
            set(dataset.testcases),
            {
                "1_samples.txt",
                "2_samples.txt",
                "3_s1-OO.txt",
                "4_s1.txt",
            },
        )
        self.assertIn("checker", dataset.managers)
        self.assertEqual(
            self._archive_names(task.attachments["samples.zip"]),
            {
                "input.01.txt",
                "output.01.txt",
                "input.02.txt",
                "output.02.txt",
            },
        )
        self.assertEqual(len(self.compiled_checker_directories), 1)

    def test_output_only_loader_selects_and_renumbers_tests(self):
        loader = PolyconvOutputOnlyTaskLoader(
            self.package_path.as_posix(), self.file_cacher
        )

        task = loader.get_task(get_statement=False)

        self.assertEqual(task.name, "polygon-task-output-only")
        self.assertEqual(task.title, "Test task (Output Only)")
        self.assertEqual(task.submission_format, ["output_00.txt"])
        dataset = task.active_dataset
        self.assertEqual(dataset.description, "output_only")
        self.assertEqual(dataset.task_type, "OutputOnly")
        self.assertEqual(dataset.task_type_parameters, ["comparator"])
        self.assertEqual(dataset.score_type, "GroupMin")
        self.assertEqual(dataset.score_type_parameters, [[5, 1]])
        self.assertEqual(set(dataset.testcases), {"00"})
        self.assertTrue(dataset.testcases["00"].public)
        self.assertEqual(
            self._archive_names(task.attachments["attachment.zip"]),
            {"input_00.txt"},
        )
        self.assertEqual(
            self._archive_names(task.attachments["samples.zip"]),
            {
                "input.01.txt",
                "output.01.txt",
                "input.02.txt",
                "output.02.txt",
            },
        )
        self.assertIn("checker", dataset.managers)
        self.assertEqual(len(self.compiled_checker_directories), 1)

    def test_loaders_are_registered_for_explicit_selection(self):
        self.assertIs(LOADERS["polyconv_batch"], PolyconvBatchTaskLoader)
        self.assertIs(LOADERS["polyconv_output_only"], PolyconvOutputOnlyTaskLoader)
        self.assertFalse(PolyconvBatchTaskLoader.detect(self.package_path))
        self.assertFalse(PolyconvOutputOnlyTaskLoader.detect(self.package_path))


if __name__ == "__main__":
    unittest.main()
