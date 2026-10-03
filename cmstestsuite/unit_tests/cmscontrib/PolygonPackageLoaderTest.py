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

"""Tests for the polyconv-style Polygon package loaders."""

import io
import re
import zipfile
from collections.abc import Sequence
from pathlib import Path

import pytest

from cmscontrib.loaders.polygon_package import (
    PolygonPackage,
    PolygonPackageBatchTaskLoader,
    PolygonPackageContestLoader,
    PolygonPackageOutputOnlyTaskLoader,
)

# (group, points) for each test, in Polygon order.
MIXED_TESTS = [
    ("samples", 0),
    ("s1-OO", 5),
    ("s2-OO", 5),
    ("s2-OO", 5),
    ("s3", 20),
    ("s3", 0),
    ("s4", 65),
]
MIXED_GROUPS = """
<group name="samples" points="0.0" points-policy="complete-group"/>
<group name="s1-OO" points-policy="each-test"/>
<group name="s2-OO" points-policy="each-test"/>
<group name="s3" points="20.0" points-policy="complete-group">
  <dependencies><dependency group="s1-OO"/></dependencies>
</group>
<group name="s4" points="65.0" points-policy="complete-group">
  <dependencies><dependency group="s3"/></dependencies>
</group>
"""


class FakeFileCacher:
    """In-memory replacement for FileCacher."""

    def __init__(self) -> None:
        """Create an empty store."""
        self.files: dict[str, bytes] = {}

    def put_file_content(self, content: bytes, desc: str = "") -> str:
        """Store content and return a fake digest."""
        digest = f"digest{len(self.files)}"
        self.files[digest] = content
        return digest

    def put_file_from_path(self, src_path: str, desc: str = "") -> str:
        """Store a file and return a fake digest."""
        return self.put_file_content(Path(src_path).read_bytes(), desc)


def write_package(
    path: Path, tests: Sequence[tuple[str, int]], groups_xml: str
) -> Path:
    """Write a minimal Polygon package without a checker.

    Args:
        path: Directory in which to create the package.
        tests: (group, points) of each test.
        groups_xml: The content of the ``<groups>`` element.

    Returns:
        The package root.
    """
    tests_xml = "".join(
        f'<test group="{group}" points="{points}"/>' for group, points in tests
    )
    (path / "problem.xml").write_text(
        f"""<?xml version="1.0" encoding="utf-8"?>
<problem short-name="sorting">
  <names><name language="english" value="Sorting"/></names>
  <judging input-file="" output-file="">
    <testset name="tests">
      <time-limit>1500</time-limit>
      <memory-limit>268435456</memory-limit>
      <test-count>{len(tests)}</test-count>
      <input-path-pattern>tests/%02d</input-path-pattern>
      <answer-path-pattern>tests/%02d.a</answer-path-pattern>
      <tests>{tests_xml}</tests>
      <groups>{groups_xml}</groups>
    </testset>
  </judging>
</problem>
""",
        encoding="utf-8",
    )
    (path / "tests").mkdir()
    for index in range(1, len(tests) + 1):
        (path / "tests" / f"{index:02d}").write_bytes(f"in{index}\r\n".encode())
        (path / "tests" / f"{index:02d}.a").write_bytes(f"out{index}\n".encode())
    return path


def matching(regex: str, codenames: Sequence[str]) -> list[str]:
    """Return the codenames matched like GroupMin does (re.match)."""
    return [c for c in codenames if re.match(regex, c)]


@pytest.fixture
def mixed_package(tmp_path: Path) -> Path:
    """Return a package with samples, OutputOnly and Batch groups."""
    return write_package(tmp_path, MIXED_TESTS, MIXED_GROUPS)


def test_batch_score_params_follow_groups_and_dependencies(
    mixed_package: Path,
) -> None:
    """Score parameters cover each group plus its transitive prerequisites."""
    package = PolygonPackage(str(mixed_package))
    codenames = [package.batch_codename(t) for t in package.tests]
    assert codenames == [
        "1_samples",
        "2_s1-OO",
        "3_s2-OO",
        "4_s2-OO",
        "5_s3",
        "6_s3",
        "7_s4",
    ]

    params = package.batch_score_params()
    assert [p[0] for p in params] == [0, 5, 5, 5, 20, 65]
    assert [matching(p[1], codenames) for p in params] == [
        ["1_samples"],
        ["2_s1-OO"],
        ["3_s2-OO"],
        ["4_s2-OO"],
        ["2_s1-OO", "5_s3", "6_s3"],
        ["2_s1-OO", "5_s3", "6_s3", "7_s4"],
    ]


def test_group_regex_does_not_match_longer_group_names(tmp_path: Path) -> None:
    """A group named s3 must not match the tests of group s3-OO."""
    package = PolygonPackage(
        str(
            write_package(
                tmp_path,
                [("s3-OO", 10), ("s3", 90)],
                '<group name="s3-OO" points-policy="each-test"/>'
                '<group name="s3" points="90" points-policy="complete-group"/>',
            )
        )
    )
    codenames = [package.batch_codename(t) for t in package.tests]
    assert [matching(p[1], codenames) for p in package.batch_score_params()] == [
        ["1_s3-OO"],
        ["2_s3"],
    ]


def test_contest_loader_creates_batch_and_output_only_tasks(
    mixed_package: Path,
) -> None:
    """A package with both kinds of tests yields two tasks."""
    loader = PolygonPackageContestLoader(str(mixed_package), FakeFileCacher())
    contest, tasks, participations = loader.get_contest()
    assert contest.name == "sorting"
    assert tasks == ["sorting", "sorting-oo"]
    assert participations == []
    assert isinstance(loader.get_task_loader("sorting"), PolygonPackageBatchTaskLoader)
    assert isinstance(
        loader.get_task_loader("sorting-oo"), PolygonPackageOutputOnlyTaskLoader
    )


@pytest.mark.parametrize(
    ("tests", "groups_xml", "expected"),
    [
        (
            [("samples", 0), ("s1-OO", 50), ("s2-OO", 50)],
            (
                '<group name="samples" points-policy="complete-group"/>'
                '<group name="s1-OO" points-policy="each-test"/>'
                '<group name="s2-OO" points-policy="each-test"/>'
            ),
            ["sorting-oo"],
        ),
        (
            [("samples", 0), ("s1", 100)],
            (
                '<group name="samples" points-policy="complete-group"/>'
                '<group name="s1" points="100" points-policy="complete-group"/>'
            ),
            ["sorting"],
        ),
    ],
)
def test_contest_loader_creates_one_task(
    tmp_path: Path,
    tests: Sequence[tuple[str, int]],
    groups_xml: str,
    expected: list[str],
) -> None:
    """All-OutputOnly or all-Batch packages yield a single task."""
    path = write_package(tmp_path, tests, groups_xml)
    _, tasks, _ = PolygonPackageContestLoader(str(path), FakeFileCacher()).get_contest()
    assert tasks == expected


def test_batch_task(mixed_package: Path) -> None:
    """The Batch task has every test, the samples and GroupMin parameters."""
    cacher = FakeFileCacher()
    task = PolygonPackageBatchTaskLoader(str(mixed_package), cacher).get_task(
        get_statement=False
    )
    assert task is not None
    assert task.name == "sorting"
    assert task.submission_format == ["sorting.%l"]
    dataset = task.active_dataset
    assert dataset.task_type == "Batch"
    assert dataset.task_type_parameters == ["alone", ["", ""], "diff"]
    assert dataset.score_type == "GroupMin"
    assert dataset.time_limit == 1.5
    assert dataset.memory_limit == 268435456
    assert len(dataset.testcases) == len(MIXED_TESTS)
    assert cacher.files[dataset.testcases["5_s3"].input] == b"in5\n"

    samples = zipfile.ZipFile(
        io.BytesIO(cacher.files[task.attachments["samples.zip"].digest])
    )
    assert sorted(samples.namelist()) == ["input.01.txt", "output.01.txt"]
    assert samples.read("output.01.txt") == b"out1\n"


def test_output_only_task(mixed_package: Path) -> None:
    """The OutputOnly task renumbers OO tests and attaches their inputs."""
    cacher = FakeFileCacher()
    task = PolygonPackageOutputOnlyTaskLoader(str(mixed_package), cacher).get_task(
        get_statement=False
    )
    assert task is not None
    assert task.name == "sorting-oo"
    assert task.title == "Sorting (Output Only)"
    assert task.submission_format == [
        "output_00.txt",
        "output_01.txt",
        "output_02.txt",
    ]
    dataset = task.active_dataset
    assert dataset.task_type == "OutputOnly"
    assert dataset.task_type_parameters == ["diff"]
    assert dataset.score_type_parameters == [[5, 1], [5, 1], [5, 1]]
    assert sorted(dataset.testcases) == ["00", "01", "02"]
    assert cacher.files[dataset.testcases["00"].output] == b"out2\n"

    attachment = zipfile.ZipFile(
        io.BytesIO(cacher.files[task.attachments["attachment.zip"].digest])
    )
    assert sorted(attachment.namelist()) == [
        "input_00.txt",
        "input_01.txt",
        "input_02.txt",
    ]
    assert attachment.read("input_02.txt") == b"in4\n"


def test_cms_conf_overrides_output_only_substring(mixed_package: Path) -> None:
    """files/cms_conf.py can change the OutputOnly group substring."""
    (mixed_package / "files").mkdir()
    (mixed_package / "files" / "cms_conf.py").write_text(
        'OUTPUT_ONLY_GROUP_SUBSTRING = "s2"\n', encoding="utf-8"
    )
    package = PolygonPackage(str(mixed_package))
    assert [t.index for t in package.output_only_tests] == [3, 4]
