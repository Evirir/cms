# Contest Management System - http://cms-dev.github.io/
# Copyright © 2026 Evirir <gojunxing@gmail.com>
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

"""Loaders for Polygon full packages with subtasks and OutputOnly tests.

The conversion follows polyconv (https://github.com/Evirir/polyconv):

* The Batch task contains every Polygon test, with codenames such as
  ``07_s3`` (test number and group), and GroupMin score parameters that
  capture Polygon groups, their points policies and their dependencies.
* Tests whose group name contains the OutputOnly substring (``OO`` by
  default) also form a separate OutputOnly task, renumbered from ``00``,
  with one GroupMin subtask per test and an ``attachment.zip`` holding the
  inputs as ``input_XX.txt``.
* Tests of the samples group (``samples`` by default) are attached to the
  Batch task as ``samples.zip``.

``PolygonPackageContestLoader`` creates a contest with both tasks (or only
one of them when all the non-sample tests are OutputOnly, or none are).
``PolygonPackageMultiContestLoader`` does the same for every problem of a
Polygon contest package (``contest.xml`` and ``problems/*``).
The task loaders can also be used on their own with ``cmsImportTask``.

An optional ``files/cms_conf.py`` in the package may define:

* ``general``: a dict of extra Task arguments, applied to both tasks;
* ``OUTPUT_ONLY_GROUP_SUBSTRING``: the OutputOnly group substring;
* ``SAMPLES_GROUP``: the exact name of the samples group.

"""

import importlib.resources
import importlib.util
import io
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import ModuleType

from cms.db import (
    Attachment,
    Contest,
    Dataset,
    Group,
    Manager,
    Statement,
    Task,
    Testcase,
)
from cms.db.filecacher import FileCacher
from cmscommon.crypto import build_password

from .base_loader import LANGUAGE_MAP, ContestLoader, TaskLoader

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_ONLY_GROUP_SUBSTRING = "OO"
DEFAULT_SAMPLES_GROUP = "samples"
OUTPUT_ONLY_TASK_SUFFIX = "-oo"
OUTPUT_ONLY_TITLE_SUFFIX = " (Output Only)"
OUTPUT_ONLY_ATTACHMENT_NAME = "attachment.zip"
SAMPLES_ATTACHMENT_NAME = "samples.zip"
CMS_CONF_PATH = os.path.join("files", "cms_conf.py")


@dataclass
class PolygonTest:
    """A test of the main Polygon testset.

    Attributes:
        index: One-based Polygon test number.
        group: Polygon group name.
        points: Points of the test (used by the ``each-test`` policy).
        input_path: Path to the input file.
        answer_path: Path to the answer file.
    """

    index: int
    group: str
    points: float
    input_path: str
    answer_path: str


@dataclass
class PolygonGroup:
    """A group of the main Polygon testset.

    Attributes:
        name: Group name.
        points: Points of the group (used by the ``complete-group`` policy).
        points_policy: Either ``complete-group`` or ``each-test``.
        dependencies: Names of the groups this group depends on.
    """

    name: str
    points: float
    points_policy: str
    dependencies: list[str]


class PolygonPackage:
    """Parsed content of a Polygon full package.

    Attributes:
        path: Root directory of the package (containing ``problem.xml``).
        name: Problem short name.
        title: Problem title.
        time_limit: Time limit in seconds.
        memory_limit: Memory limit in bytes.
        input_file: Input file name, empty for standard input.
        output_file: Output file name, empty for standard output.
        tests: Tests of the main testset, in Polygon order.
        groups: Groups of the main testset, in ``problem.xml`` order.
        checker_path: Path to the checker source, if any.
        resource_paths: Paths to resource files (headers etc.).
        conf: The optional ``files/cms_conf.py`` module.
        output_only_substring: Group substring selecting OutputOnly tests.
        samples_group: Exact name of the samples group.
    """

    def __init__(self, path: str):
        """Parse ``problem.xml`` and the optional ``files/cms_conf.py``.

        Args:
            path: Root directory of the Polygon full package.

        Raises:
            ValueError: If ``problem.xml`` lacks required information.
        """
        self.path = path
        root = ET.parse(os.path.join(path, "problem.xml")).getroot()

        self.name = root.get("short-name") or os.path.basename(os.path.normpath(path))
        name_element = root.find("names/name")
        self.title = (
            name_element.get("value", self.name)
            if name_element is not None
            else self.name
        )

        judging = root.find("judging")
        if judging is None:
            raise ValueError("problem.xml has no judging section.")
        self.input_file = judging.get("input-file", "")
        self.output_file = judging.get("output-file", "")
        testset = judging.find("testset[@name='tests']")
        if testset is None:
            testset = judging.find("testset")
        if testset is None:
            raise ValueError("problem.xml has no testset.")

        self.time_limit = int(_required_text(testset, "time-limit")) / 1000
        self.memory_limit = int(_required_text(testset, "memory-limit"))
        input_pattern = _required_text(testset, "input-path-pattern")
        answer_pattern = _required_text(testset, "answer-path-pattern")

        self.tests: list[PolygonTest] = []
        for index, test in enumerate(testset.findall("tests/test"), start=1):
            group = test.get("group")
            if group is None:
                raise ValueError(f"Test {index} has no group.")
            self.tests.append(
                PolygonTest(
                    index=index,
                    group=group,
                    points=float(test.get("points", 0)),
                    input_path=os.path.join(path, input_pattern % index),
                    answer_path=os.path.join(path, answer_pattern % index),
                )
            )
        if not self.tests:
            raise ValueError("No tests found in problem.xml.")
        missing = [
            os.path.relpath(test_path, path)
            for test in self.tests
            for test_path in (test.input_path, test.answer_path)
            if not os.path.exists(test_path)
        ]
        if missing:
            raise ValueError(
                f"Package {self.name} lacks test files ({', '.join(missing[:3])}"
                f"{', ...' if len(missing) > 3 else ''}); use a full package with "
                "generated tests (e.g. the Linux one) or run doall.sh first."
            )

        self.groups: list[PolygonGroup] = []
        for group in testset.findall("groups/group"):
            name = group.get("name")
            if name is None:
                raise ValueError("Group has no name.")
            dependencies = []
            for dependency in group.findall("dependencies/dependency"):
                dependency_group = dependency.get("group")
                if dependency_group is None:
                    raise ValueError(f'Dependency of group "{name}" has no group.')
                dependencies.append(dependency_group)
            self.groups.append(
                PolygonGroup(
                    name=name,
                    points=float(group.get("points", 0)),
                    points_policy=group.get("points-policy", "complete-group"),
                    dependencies=dependencies,
                )
            )

        self.checker_path: str | None = None
        checker_source = root.find("assets/checker/source")
        candidates = []
        if checker_source is not None and checker_source.get("path"):
            candidates.append(os.path.join(path, checker_source.get("path")))
        candidates += [
            os.path.join(path, "files", "check.cpp"),
            os.path.join(path, "check.cpp"),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                self.checker_path = candidate
                break

        self.resource_paths = [
            os.path.join(path, resource.get("path"))
            for resource in root.findall("files/resources/file")
            if resource.get("path")
        ]

        self.conf = _load_cms_conf(path)
        self.output_only_substring: str = getattr(
            self.conf,
            "OUTPUT_ONLY_GROUP_SUBSTRING",
            DEFAULT_OUTPUT_ONLY_GROUP_SUBSTRING,
        )
        if not self.output_only_substring:
            raise ValueError("The OutputOnly group substring cannot be empty.")
        self.samples_group: str = getattr(
            self.conf, "SAMPLES_GROUP", DEFAULT_SAMPLES_GROUP
        )

    @property
    def output_only_name(self) -> str:
        """Return the name of the OutputOnly task."""
        return self.name + OUTPUT_ONLY_TASK_SUFFIX

    @property
    def output_only_tests(self) -> list[PolygonTest]:
        """Return the tests whose group contains the OutputOnly substring."""
        return [t for t in self.tests if self.output_only_substring in t.group]

    @property
    def sample_tests(self) -> list[PolygonTest]:
        """Return the tests of the samples group."""
        return [t for t in self.tests if t.group == self.samples_group]

    @property
    def has_batch_tests(self) -> bool:
        """Return whether some non-sample test is not OutputOnly."""
        return any(
            self.output_only_substring not in t.group and t.group != self.samples_group
            for t in self.tests
        )

    def batch_codename(self, test: PolygonTest) -> str:
        """Return the Batch codename of a test, e.g. ``07_s3``.

        Args:
            test: The Polygon test.

        Returns:
            The test number, padded to the test count width, and the group.
        """
        width = len(str(len(self.tests)))
        return f"{str(test.index).zfill(width)}_{test.group}"

    def output_only_codenames(self) -> list[str]:
        """Return the OutputOnly codenames, aligned with output_only_tests.

        Returns:
            Codenames numbered from ``00``, padded to at least two digits.
        """
        count = len(self.output_only_tests)
        width = max(2, len(str(count)))
        return [str(i).zfill(width) for i in range(count)]

    def transitive_dependencies(self) -> dict[str, list[str]]:
        """Return each group with its transitive prerequisites, itself included.

        Raises:
            ValueError: If a dependency refers to an unknown group.
        """
        direct = {group.name: group.dependencies for group in self.groups}
        result: dict[str, list[str]] = {}
        for name in direct:
            seen = {name}
            stack = [name]
            while stack:
                for prereq in direct[stack.pop()]:
                    if prereq not in direct:
                        raise ValueError(f'Unknown dependency group "{prereq}".')
                    if prereq not in seen:
                        seen.add(prereq)
                        stack.append(prereq)
            result[name] = sorted(seen)
        return result

    def batch_score_params(self) -> list[list[float | str]]:
        """Return GroupMin parameters for the Batch task.

        Like polyconv, ``complete-group`` groups become one subtask covering
        the group and its prerequisites; ``each-test`` groups become one
        subtask per test, also covering the group's prerequisites.

        Raises:
            ValueError: If a group uses an unsupported points policy.
        """
        dependencies = self.transitive_dependencies()
        params: list[list[float | str]] = []
        for group in self.groups:
            if group.points_policy == "complete-group":
                params.append(
                    [_points(group.points), _groups_regex(dependencies[group.name])]
                )
                continue
            if group.points_policy != "each-test":
                raise ValueError(
                    f'Group "{group.name}" uses unsupported points policy '
                    f'"{group.points_policy}".'
                )
            prereqs = [g for g in dependencies[group.name] if g != group.name]
            for test in self.tests:
                if test.group != group.name:
                    continue
                regex = re.escape(self.batch_codename(test)) + "$"
                if prereqs:
                    regex += "|" + _groups_regex(prereqs)
                params.append([_points(test.points), regex])
        return params

    def output_only_score_params(self) -> list[list[float | int]]:
        """Return one GroupMin subtask per OutputOnly test."""
        return [[_points(t.points), 1] for t in self.output_only_tests]


def _required_text(element: ET.Element, tag: str) -> str:
    """Return the text of a required child element.

    Args:
        element: The parent element.
        tag: The child tag.

    Raises:
        ValueError: If the child is missing or empty.
    """
    text = element.findtext(tag)
    if not text:
        raise ValueError(f"problem.xml testset has no {tag}.")
    return text


def _points(points: float) -> float | int:
    """Return points as an int when they are integral."""
    return int(points) if points.is_integer() else points


def _groups_regex(groups: Sequence[str]) -> str:
    """Return a regex matching the codenames of any of the given groups."""
    return ".*_(" + "|".join(re.escape(g) for g in groups) + ")$"


def _load_cms_conf(path: str) -> ModuleType | None:
    """Load the optional ``files/cms_conf.py`` of a package.

    Args:
        path: Root directory of the Polygon package.

    Returns:
        The loaded module, or None if the file does not exist.
    """
    conf_path = os.path.join(path, CMS_CONF_PATH)
    if not os.path.exists(conf_path):
        return None
    logger.info("Found additional CMS options in %s.", conf_path)
    spec = importlib.util.spec_from_file_location("cms_conf", conf_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load {conf_path}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_test_file(path: str) -> bytes:
    """Read a test file, converting CRLF line endings to LF."""
    with open(path, "rb") as file:
        return file.read().replace(b"\r\n", b"\n")


def _zip_bytes(files: Mapping[str, bytes]) -> bytes:
    """Return a zip archive containing the given files.

    Args:
        files: Mapping from archive member names to contents.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


class _PolygonPackageTaskLoaderBase(TaskLoader):
    """Shared logic of the Batch and OutputOnly Polygon package loaders."""

    def __init__(self, path: str, file_cacher: FileCacher):
        """Initialize the loader.

        Args:
            path: Root directory of the Polygon full package.
            file_cacher: The file cacher used to store files.
        """
        super().__init__(path, file_cacher)
        self.package = PolygonPackage(path)

    @staticmethod
    def detect(path: str) -> bool:
        """Never autodetect, to avoid clashing with polygon_task."""
        return False

    def task_has_changed(self) -> bool:
        """See docstring in class TaskLoader."""
        return True

    def _put(self, content: bytes, description: str) -> str:
        """Store content in the file cacher and return its digest."""
        return self.file_cacher.put_file_content(content, description)

    def _task_args(self, name: str, title: str, get_statement: bool) -> dict:
        """Return the Task arguments shared by both task kinds.

        Args:
            name: Task name.
            title: Task title.
            get_statement: Whether to import the PDF statements.
        """
        args: dict = {"name": name, "title": title}
        if get_statement:
            args["statements"] = {}
            args["primary_statements"] = []
            for language, lang in LANGUAGE_MAP.items():
                path = os.path.join(
                    self.path, "statements", ".pdf", language, "problem.pdf"
                )
                if os.path.exists(path):
                    digest = self.file_cacher.put_file_from_path(
                        path, f"Statement for task {name} (lang: {lang})"
                    )
                    args["statements"][lang] = Statement(lang, digest)
                    args["primary_statements"].append(lang)
        return args

    def _apply_general_conf(self, args: dict) -> None:
        """Apply the ``general`` dict from ``files/cms_conf.py``, if any."""
        conf = self.package.conf
        if conf is not None and hasattr(conf, "general"):
            args.update(conf.general)

    def _checker_managers(self, name: str) -> tuple[dict[str, Manager], str]:
        """Compile the checker with CMS's patched testlib.h.

        Args:
            name: Task name, used in file descriptions.

        Returns:
            The managers dict and the evaluation parameter
            (``comparator`` or ``diff``).

        Raises:
            ValueError: If the checker does not compile.
        """
        checker_path = self.package.checker_path
        if checker_path is None:
            logger.info("Checker not found, using diff.")
            return {}, "diff"

        logger.info("Compiling checker %s.", checker_path)
        with tempfile.TemporaryDirectory() as tempdir:
            # Copy the package resources (e.g. headers included by the
            # checker), then replace testlib.h with CMS's patched version.
            for resource in self.package.resource_paths:
                if os.path.isfile(resource):
                    shutil.copy(resource, tempdir)
            testlib = importlib.resources.files("cmscontrib.loaders").joinpath(
                "polygon/testlib.h"
            )
            with (
                testlib.open("rb") as src,
                open(os.path.join(tempdir, "testlib.h"), "wb") as dst,
            ):
                shutil.copyfileobj(src, dst)
            source = os.path.join(tempdir, "check.cpp")
            shutil.copyfile(checker_path, source)
            binary = os.path.join(tempdir, "checker")
            code = subprocess.call(
                ["g++", "-x", "c++", "-O2", "-static", "-DCMS", "-o", binary, source]
            )
            if code != 0:
                raise ValueError("Could not compile the checker.")
            digest = self.file_cacher.put_file_from_path(
                binary, f"Checker for task {name}"
            )
        return {"checker": Manager("checker", digest)}, "comparator"


class PolygonPackageBatchTaskLoader(_PolygonPackageTaskLoaderBase):
    """Load the Batch task of a Polygon full package (polyconv-style)."""

    short_name = "polygon_package_batch"
    description = "Polygon full package, Batch task with GroupMin subtasks"

    def get_task(self, get_statement: bool = True) -> Task | None:
        """See docstring in class TaskLoader."""
        package = self.package
        name = package.name
        logger.info("Loading Batch task %s.", name)

        args = self._task_args(name, package.title, get_statement)
        args["submission_format"] = [f"{name}.%l"]
        args["attachments"] = {}
        if package.sample_tests:
            width = max(2, len(str(len(package.sample_tests))))
            samples = {}
            for i, test in enumerate(package.sample_tests, start=1):
                sample_id = str(i).zfill(width)
                samples[f"input.{sample_id}.txt"] = _read_test_file(test.input_path)
                samples[f"output.{sample_id}.txt"] = _read_test_file(test.answer_path)
            digest = self._put(_zip_bytes(samples), f"Samples for task {name}")
            args["attachments"][SAMPLES_ATTACHMENT_NAME] = Attachment(
                SAMPLES_ATTACHMENT_NAME, digest
            )
        self._apply_general_conf(args)
        task = Task(**args)

        managers, evaluation = self._checker_managers(name)
        testcases = {}
        for test in package.tests:
            codename = package.batch_codename(test)
            input_digest = self._put(
                _read_test_file(test.input_path), f"Input {codename} for task {name}"
            )
            output_digest = self._put(
                _read_test_file(test.answer_path),
                f"Output {codename} for task {name}",
            )
            testcases[codename] = Testcase(codename, True, input_digest, output_digest)

        score_params = package.batch_score_params()
        logger.info("Batch score parameters: %s", json.dumps(score_params))
        task.active_dataset = Dataset(
            task=task,
            description="tests",
            autojudge=False,
            time_limit=package.time_limit,
            memory_limit=package.memory_limit,
            task_type="Batch",
            task_type_parameters=[
                "alone",
                [package.input_file, package.output_file],
                evaluation,
            ],
            score_type="GroupMin",
            score_type_parameters=score_params,
            managers=managers,
            testcases=testcases,
        )
        logger.info("Task parameters loaded.")
        return task


class PolygonPackageOutputOnlyTaskLoader(_PolygonPackageTaskLoaderBase):
    """Load the OutputOnly task of a Polygon full package (polyconv-style)."""

    short_name = "polygon_package_output_only"
    description = "Polygon full package, OutputOnly task from OO groups"

    def get_task(self, get_statement: bool = True) -> Task | None:
        """See docstring in class TaskLoader."""
        package = self.package
        name = package.output_only_name
        tests = package.output_only_tests
        if not tests:
            logger.critical(
                'No test groups contain the OutputOnly substring "%s".',
                package.output_only_substring,
            )
            return None
        logger.info("Loading OutputOnly task %s.", name)

        codenames = package.output_only_codenames()
        args = self._task_args(
            name, package.title + OUTPUT_ONLY_TITLE_SUFFIX, get_statement
        )
        args["submission_format"] = [f"output_{c}.txt" for c in codenames]
        inputs = {
            f"input_{c}.txt": _read_test_file(t.input_path)
            for c, t in zip(codenames, tests)
        }
        digest = self._put(_zip_bytes(inputs), f"OutputOnly inputs for task {name}")
        args["attachments"] = {
            OUTPUT_ONLY_ATTACHMENT_NAME: Attachment(OUTPUT_ONLY_ATTACHMENT_NAME, digest)
        }
        self._apply_general_conf(args)
        task = Task(**args)

        managers, evaluation = self._checker_managers(name)
        testcases = {}
        for codename, test in zip(codenames, tests):
            input_digest = self._put(
                _read_test_file(test.input_path), f"Input {codename} for task {name}"
            )
            output_digest = self._put(
                _read_test_file(test.answer_path),
                f"Output {codename} for task {name}",
            )
            testcases[codename] = Testcase(codename, True, input_digest, output_digest)

        score_params = package.output_only_score_params()
        logger.info("OutputOnly score parameters: %s", json.dumps(score_params))
        task.active_dataset = Dataset(
            task=task,
            description="tests",
            autojudge=False,
            task_type="OutputOnly",
            task_type_parameters=[evaluation],
            score_type="GroupMin",
            score_type_parameters=score_params,
            managers=managers,
            testcases=testcases,
        )
        logger.info("Task parameters loaded.")
        return task


def _package_task_names(package: PolygonPackage) -> list[str]:
    """Return the names of the tasks created from a package.

    Args:
        package: The parsed Polygon package.

    Returns:
        The Batch task name unless all the non-sample tests are OutputOnly,
        followed by the OutputOnly task name if there are OutputOnly tests.
    """
    names = []
    if package.has_batch_tests or not package.output_only_tests:
        names.append(package.name)
    if package.output_only_tests:
        names.append(package.output_only_name)
    return names


def _package_task_loader(
    package: PolygonPackage, taskname: str, file_cacher: FileCacher
) -> TaskLoader:
    """Return the task loader for one of the tasks of a package.

    Args:
        package: The parsed Polygon package.
        taskname: One of the names returned by ``_package_task_names``.
        file_cacher: The file cacher used to store files.

    Returns:
        The Batch or OutputOnly task loader for the package.

    Raises:
        ValueError: If the task name does not belong to the package.
    """
    if taskname == package.name:
        return PolygonPackageBatchTaskLoader(package.path, file_cacher)
    if taskname == package.output_only_name:
        return PolygonPackageOutputOnlyTaskLoader(package.path, file_cacher)
    raise ValueError(f'Unknown task "{taskname}".')


class PolygonPackageContestLoader(ContestLoader):
    """Load a single Polygon full package as a contest with one or two tasks.

    The Batch task is created unless all the non-sample tests are
    OutputOnly; the OutputOnly task is created if some group contains the
    OutputOnly substring.
    """

    short_name = "polygon_package"
    description = "Polygon full package as a contest (Batch + OutputOnly tasks)"

    def __init__(self, path: str, file_cacher: FileCacher):
        """Initialize the loader.

        Args:
            path: Root directory of the Polygon full package.
            file_cacher: The file cacher used to store files.
        """
        super().__init__(path, file_cacher)
        self.package = PolygonPackage(path)

    @staticmethod
    def detect(path: str) -> bool:
        """Never autodetect, to avoid clashing with polygon_task."""
        return False

    def contest_has_changed(self) -> bool:
        """See docstring in class ContestLoader."""
        return True

    def task_names(self) -> list[str]:
        """Return the names of the tasks created from the package."""
        return _package_task_names(self.package)

    def get_task_loader(self, taskname: str) -> TaskLoader:
        """See docstring in class ContestLoader.

        Raises:
            ValueError: If the task name does not belong to the package.
        """
        return _package_task_loader(self.package, taskname, self.file_cacher)

    def get_contest(self) -> tuple[Contest, list[str], list[dict]]:
        """See docstring in class ContestLoader."""
        group = Group(name="default")
        contest = Contest(
            name=self.package.name,
            description=self.package.title,
            groups=[group],
            main_group=group,
        )
        return contest, self.task_names(), []


class PolygonPackageMultiContestLoader(ContestLoader):
    """Load a Polygon contest package, converting each problem like polyconv.

    The package contains ``contest.xml`` and one full package per problem in
    ``problems/<short-name>``. Each problem becomes one or two tasks, as with
    ``PolygonPackageContestLoader``, in the order of ``contest.xml``.

    Like ``polygon_contest``, an optional ``contestants.txt`` holds one
    participation per line as ``username;password;first_name;last_name;hidden``
    (the users must already exist).
    """

    short_name = "polygon_package_contest"
    description = "Polygon contest package (polyconv-style tasks per problem)"

    def __init__(self, path: str, file_cacher: FileCacher):
        """Parse ``contest.xml`` and the package of every problem.

        Args:
            path: Root directory of the Polygon contest package.
            file_cacher: The file cacher used to store files.

        Raises:
            ValueError: If ``contest.xml`` has no problems, or two problems
                produce tasks with the same name.
        """
        super().__init__(path, file_cacher)
        self.root = ET.parse(os.path.join(path, "contest.xml")).getroot()

        self.packages: list[PolygonPackage] = []
        for problem in self.root.findall("problems/problem"):
            url = problem.get("url", "").rstrip("/")
            self.packages.append(
                PolygonPackage(os.path.join(path, "problems", os.path.basename(url)))
            )
        if not self.packages:
            raise ValueError("contest.xml lists no problems.")

        self.task_packages: dict[str, PolygonPackage] = {}
        for package in self.packages:
            for taskname in _package_task_names(package):
                if taskname in self.task_packages:
                    raise ValueError(f'Two problems produce the task "{taskname}".')
                self.task_packages[taskname] = package

    @staticmethod
    def detect(path: str) -> bool:
        """Never autodetect, to avoid clashing with polygon_contest."""
        return False

    def contest_has_changed(self) -> bool:
        """See docstring in class ContestLoader."""
        return True

    def get_task_loader(self, taskname: str) -> TaskLoader:
        """See docstring in class ContestLoader.

        Raises:
            ValueError: If no problem produces the task.
        """
        if taskname not in self.task_packages:
            raise ValueError(f'Unknown task "{taskname}".')
        return _package_task_loader(
            self.task_packages[taskname], taskname, self.file_cacher
        )

    def _participations(self) -> list[dict]:
        """Read the participations from the optional ``contestants.txt``."""
        users_path = os.path.join(self.path, "contestants.txt")
        if not os.path.exists(users_path):
            return []
        participations = []
        with open(users_path, encoding="utf-8") as users_file:
            for line in users_file:
                fields = [field.strip() for field in line.split(";")]
                if not fields[0]:
                    continue
                participation: dict = {"username": fields[0]}
                if len(fields) > 1 and fields[1]:
                    participation["password"] = build_password(fields[1])
                participation["hidden"] = len(fields) > 4 and fields[4] == "1"
                participations.append(participation)
        return participations

    def get_contest(self) -> tuple[Contest, list[str], list[dict]]:
        """See docstring in class ContestLoader."""
        name = os.path.basename(os.path.normpath(self.path))
        names = self.root.findall("names/name")
        main_names = [n for n in names if n.get("main") == "true"] or names
        description = main_names[0].get("value", name) if main_names else name

        group = Group(name="default")
        contest = Contest(
            name=name,
            description=description,
            groups=[group],
            main_group=group,
        )
        logger.info("Contest parameters loaded.")
        return contest, list(self.task_packages), self._participations()
