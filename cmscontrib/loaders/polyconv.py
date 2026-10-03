"""Load Polygon packages using polyconv naming and scoring conventions."""

import importlib.resources
import logging
import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from cms.db import Attachment, Dataset, Manager, Statement, Task, Testcase

from .base_loader import LANGUAGE_MAP, TaskLoader

logger = logging.getLogger(__name__)


@dataclass
class _CachedTest:
    polygon_id: str
    element: ET.Element
    input_path: Path
    output_path: Path
    input_digest: str
    output_digest: str


class _PolyconvTaskLoader(TaskLoader):
    output_only_group_substring = "OO"
    samples_group_name = "samples"

    @staticmethod
    def detect(_path: str) -> bool:
        """Require callers to select a polyconv loader explicitly."""
        return False

    def task_has_changed(self) -> bool:
        """Always re-read the Polygon package when updating a task."""
        return True

    @abstractmethod
    def get_task(self, get_statement: bool = True) -> Task:
        """Build the CMS task represented by the Polygon package."""
        raise NotImplementedError

    def _package_path(self, relative_path: str | Path) -> Path:
        package_path = Path(self.path).resolve()
        path = (package_path / relative_path).resolve()
        if not path.is_relative_to(package_path):
            raise ValueError(f"Path is outside the Polygon package: {relative_path}")
        return path

    @staticmethod
    def _required_element(parent: ET.Element, path: str) -> ET.Element:
        element = parent.find(path)
        if element is None:
            raise ValueError(f"Polygon package is missing {path}.")
        return element

    @staticmethod
    def _required_text(parent: ET.Element, path: str) -> str:
        element = _PolyconvTaskLoader._required_element(parent, path)
        if element.text is None:
            raise ValueError(f"Polygon package has no value for {path}.")
        return element.text

    def _load_statements(
        self, task_name: str
    ) -> tuple[dict[str, Statement], list[str]]:
        statements = {}
        primary_statements = []
        for language, cms_language in LANGUAGE_MAP.items():
            path = self._package_path(
                Path("statements") / ".pdf" / language / "problem.pdf"
            )
            if not path.exists():
                continue
            digest = self.file_cacher.put_file_from_path(
                path.as_posix(),
                f"Statement for task {task_name} (lang: {language})",
            )
            statements[cms_language] = Statement(cms_language, digest)
            primary_statements.append(cms_language)
        return statements, primary_statements

    def _checker_source(self, root: ET.Element) -> Path | None:
        source = root.find("assets/checker/source")
        if source is not None and source.get("path"):
            path = self._package_path(source.get("path"))
            if path.exists():
                return path

        for relative_path in (Path("files/check.cpp"), Path("check.cpp")):
            path = self._package_path(relative_path)
            if path.exists():
                return path
        return None

    def _compile_checker(self, root: ET.Element, task_name: str) -> str | None:
        checker_source = self._checker_source(root)
        if checker_source is None:
            return None

        package_path = Path(self.path).resolve()
        relative_source = checker_source.relative_to(package_path)
        with tempfile.TemporaryDirectory() as temporary_directory:
            build_root = Path(temporary_directory) / "package"
            build_source_directory = build_root / relative_source.parent
            shutil.copytree(checker_source.parent, build_source_directory)

            testlib_resource = importlib.resources.files("cmscontrib.loaders").joinpath(
                "polygon/testlib.h"
            )
            with testlib_resource.open("rb") as source:
                with (build_source_directory / "testlib.h").open("wb") as destination:
                    shutil.copyfileobj(source, destination)

            build_source = build_root / relative_source
            checker_binary = Path(temporary_directory) / "checker"
            result = subprocess.run(
                [
                    "g++",
                    "-x",
                    "c++",
                    "-O2",
                    "-static",
                    "-DCMS",
                    "-o",
                    checker_binary.as_posix(),
                    build_source.as_posix(),
                ],
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError("Could not compile Polygon checker.")

            return self.file_cacher.put_file_from_path(
                checker_binary.as_posix(), f"Manager for task {task_name}"
            )

    def _cache_tests(self, testset: ET.Element, task_name: str) -> list[_CachedTest]:
        tests = self._required_element(testset, "tests")
        test_elements = tests.findall("test")
        test_count = int(self._required_text(testset, "test-count"))
        if len(test_elements) != test_count:
            raise ValueError(
                "Polygon test-count does not match the number of test elements."
            )

        input_pattern = self._required_text(testset, "input-path-pattern")
        output_pattern = self._required_text(testset, "answer-path-pattern")
        width = len(str(test_count))
        cached_tests = []
        for index, test in enumerate(test_elements, start=1):
            polygon_id = str(index).zfill(width)
            input_path = self._package_path(input_pattern % index)
            output_path = self._package_path(output_pattern % index)
            input_digest = self.file_cacher.put_file_from_path(
                input_path.as_posix(), f"Input {index} for task {task_name}"
            )
            output_digest = self.file_cacher.put_file_from_path(
                output_path.as_posix(), f"Output {index} for task {task_name}"
            )
            cached_tests.append(
                _CachedTest(
                    polygon_id,
                    test,
                    input_path,
                    output_path,
                    input_digest,
                    output_digest,
                )
            )
        return cached_tests

    @staticmethod
    def _parse_dependencies(groups: list[ET.Element]) -> dict[str, list[str]]:
        dependencies = {}
        for group in groups:
            name = group.get("name")
            if name is None:
                raise ValueError("Polygon group has no name.")
            dependencies[name] = {
                dependency.get("group")
                for dependency in group.findall("dependencies/dependency")
            }
            if None in dependencies[name]:
                raise ValueError(f"Polygon group {name} has an unnamed dependency.")

        visited = set()
        visiting = set()

        def visit(group_name: str) -> None:
            if group_name in visited:
                return
            if group_name in visiting:
                raise ValueError("Polygon group dependencies contain a cycle.")
            if group_name not in dependencies:
                raise ValueError(f"Unknown Polygon group dependency: {group_name}")
            visiting.add(group_name)
            direct_dependencies = dependencies[group_name].copy()
            for dependency in direct_dependencies:
                visit(dependency)
                dependencies[group_name] |= dependencies[dependency]
            dependencies[group_name].add(group_name)
            visiting.remove(group_name)
            visited.add(group_name)

        for group_name in dependencies:
            visit(group_name)
        return {
            group_name: sorted(group_dependencies)
            for group_name, group_dependencies in dependencies.items()
        }

    @classmethod
    def _batch_score_parameters(
        cls, groups: list[ET.Element], tests: list[_CachedTest]
    ) -> list[list[int | str]]:
        dependencies = cls._parse_dependencies(groups)
        tests_by_group = {}
        for test in tests:
            group_name = test.element.get("group")
            if group_name is None:
                raise ValueError(f"Polygon test {test.polygon_id} has no group.")
            tests_by_group.setdefault(group_name, []).append(test)

        parameters = []
        for group in groups:
            name = group.get("name")
            if name is None:
                raise ValueError("Polygon group has no name.")
            points_policy = group.get("points-policy", "complete-group")
            if points_policy == "complete-group":
                points = int(float(group.get("points", 0)))
                group_names = "|".join(dependencies[name])
                parameters.append([points, f".*_({group_names})"])
                continue
            if points_policy != "each-test":
                raise ValueError(
                    f"Polygon group {name} uses unsupported points policy "
                    f"{points_policy}."
                )

            prerequisite_groups = [
                dependency for dependency in dependencies[name] if dependency != name
            ]
            for test in tests_by_group.get(name, []):
                points = int(float(test.element.get("points", 0)))
                testcase_pattern = f".*{test.polygon_id}_{name}"
                if prerequisite_groups:
                    prerequisites = "|".join(prerequisite_groups)
                    testcase_pattern = f"{testcase_pattern}|.*_({prerequisites})"
                parameters.append([points, testcase_pattern])
        return parameters

    @staticmethod
    def _managers(checker_digest: str | None) -> dict[str, Manager]:
        if checker_digest is None:
            return {}
        return {"checker": Manager("checker", checker_digest)}

    def _zip_attachment(
        self,
        task_name: str,
        filename: str,
        members: list[tuple[Path, str]],
    ) -> Attachment | None:
        if not members:
            return None
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / filename
            with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
                for source_path, archive_name in members:
                    archive.write(source_path, archive_name)
            digest = self.file_cacher.put_file_from_path(
                archive_path.as_posix(), f"Attachment {filename} for task {task_name}"
            )
        return Attachment(filename, digest)

    def _sample_attachment(
        self, task_name: str, tests: list[_CachedTest]
    ) -> Attachment | None:
        samples = [
            test
            for test in tests
            if test.element.get("group") == self.samples_group_name
        ]
        width = max(2, len(str(len(samples))))
        members = []
        for sample_id, test in enumerate(samples, start=1):
            sample_id_string = str(sample_id).zfill(width)
            members.extend(
                [
                    (test.input_path, f"input.{sample_id_string}.txt"),
                    (test.output_path, f"output.{sample_id_string}.txt"),
                ]
            )
        return self._zip_attachment(task_name, "samples.zip", members)

    def _base_task(
        self,
        root: ET.Element,
        task_name: str,
        submission_format: list[str],
        get_statement: bool,
    ) -> Task:
        name = self._required_element(root, "names/name").get("value")
        if name is None:
            raise ValueError("Polygon problem name has no value.")
        args = {
            "name": task_name,
            "title": name,
            "submission_format": submission_format,
            "attachments": {},
        }
        if get_statement:
            statements, primary_statements = self._load_statements(task_name)
            args["statements"] = statements
            args["primary_statements"] = primary_statements
        return Task(**args)

    def _package_data(
        self, get_statement: bool, output_only: bool
    ) -> tuple[
        Task,
        ET.Element,
        ET.Element,
        list[ET.Element],
        list[_CachedTest],
        str | None,
    ]:
        root = ET.parse(self._package_path("problem.xml")).getroot()
        testset = root.find("judging/testset[@name='tests']")
        if testset is None:
            testset = self._required_element(root, "judging/testset")
        groups = self._required_element(testset, "groups").findall("group")
        package_name = os.path.basename(os.path.abspath(self.path))
        task_name = f"{package_name}-output-only" if output_only else package_name
        if output_only:
            submission_format = []
        else:
            submission_format = [f"{task_name}.%l"]
        task = self._base_task(root, task_name, submission_format, get_statement)
        if output_only:
            task.title = f"{task.title} (Output Only)"
        tests = self._cache_tests(testset, task_name)
        checker_digest = self._compile_checker(root, task_name)
        return task, root, testset, groups, tests, checker_digest


class PolyconvBatchTaskLoader(_PolyconvTaskLoader):
    """Import a Polygon package as a group-aware CMS Batch task."""

    short_name = "polyconv_batch"
    description = "Polygon Batch task with polyconv scoring"

    def get_task(self, get_statement: bool = True) -> Task:
        """Build a Batch task using Polygon groups and dependencies."""
        task, root, testset, groups, tests, checker_digest = self._package_data(
            get_statement, output_only=False
        )
        judging = self._required_element(root, "judging")
        input_filename = judging.get("input-file", "")
        output_filename = judging.get("output-file", "")
        evaluation = "comparator" if checker_digest is not None else "diff"

        testcases = {}
        for test in tests:
            group = test.element.get("group")
            if group is None:
                raise ValueError(f"Polygon test {test.polygon_id} has no group.")
            codename = f"{test.polygon_id}_{group}.txt"
            testcase = Testcase(codename, True, test.input_digest, test.output_digest)
            testcases[codename] = testcase

        sample_attachment = self._sample_attachment(task.name, tests)
        if sample_attachment is not None:
            task.attachments[sample_attachment.filename] = sample_attachment

        dataset = Dataset(
            task=task,
            description="tests",
            autojudge=False,
            time_limit=float(self._required_text(testset, "time-limit")) * 0.001,
            memory_limit=int(self._required_text(testset, "memory-limit")),
            task_type="Batch",
            task_type_parameters=[
                "alone",
                [input_filename, output_filename],
                evaluation,
            ],
            score_type="GroupMin",
            score_type_parameters=self._batch_score_parameters(groups, tests),
            managers=self._managers(checker_digest),
            testcases=testcases,
        )
        task.active_dataset = dataset
        return task


class PolyconvOutputOnlyTaskLoader(_PolyconvTaskLoader):
    """Import selected Polygon groups as a CMS OutputOnly task."""

    short_name = "polyconv_output_only"
    description = "Polygon OutputOnly task with polyconv selection"

    def get_task(self, get_statement: bool = True) -> Task:
        """Build an OutputOnly task from groups containing ``OO``."""
        task, _, testset, _, tests, checker_digest = self._package_data(
            get_statement, output_only=True
        )
        selected_tests = [
            test
            for test in tests
            if self.output_only_group_substring in (test.element.get("group") or "")
        ]
        if not selected_tests:
            raise ValueError(
                "No Polygon test groups contain the OutputOnly substring "
                f"{self.output_only_group_substring}."
            )

        width = max(2, len(str(len(selected_tests))))
        testcases = {}
        score_parameters = []
        attachment_members = []
        submission_format = []
        for output_id, test in enumerate(selected_tests):
            codename = str(output_id).zfill(width)
            testcases[codename] = Testcase(
                codename, True, test.input_digest, test.output_digest
            )
            score_parameters.append([int(float(test.element.get("points", 0))), 1])
            input_filename = f"input_{codename}.txt"
            attachment_members.append((test.input_path, input_filename))
            submission_format.append(f"output_{codename}.txt")
        task.submission_format = submission_format

        input_attachment = self._zip_attachment(
            task.name, "attachment.zip", attachment_members
        )
        if input_attachment is not None:
            task.attachments[input_attachment.filename] = input_attachment
        sample_attachment = self._sample_attachment(task.name, tests)
        if sample_attachment is not None:
            task.attachments[sample_attachment.filename] = sample_attachment

        evaluation = "comparator" if checker_digest is not None else "diff"
        dataset = Dataset(
            task=task,
            description="output_only",
            autojudge=False,
            time_limit=float(self._required_text(testset, "time-limit")) * 0.001,
            memory_limit=int(self._required_text(testset, "memory-limit")),
            task_type="OutputOnly",
            task_type_parameters=[evaluation],
            score_type="GroupMin",
            score_type_parameters=score_parameters,
            managers=self._managers(checker_digest),
            testcases=testcases,
        )
        task.active_dataset = dataset
        return task
