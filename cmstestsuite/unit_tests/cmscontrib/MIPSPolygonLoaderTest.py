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
import shutil
import subprocess
import zipfile
from collections.abc import Sequence
from pathlib import Path

import pytest

from cmscontrib.loaders.mips_polygon import (
    MIPSPolygon,
    MIPSPolygonBatchTaskLoader,
    MIPSPolygonContestLoader,
    MIPSPolygonMultiContestLoader,
    MIPSPolygonOutputOnlyTaskLoader,
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
    path: Path,
    tests: Sequence[tuple[str, int]],
    groups_xml: str,
    short_name: str = "sorting",
) -> Path:
    """Write a minimal Polygon package without a checker.

    Args:
        path: Directory in which to create the package.
        tests: (group, points) of each test.
        groups_xml: The content of the ``<groups>`` element.
        short_name: The problem short name.

    Returns:
        The package root.
    """
    tests_xml = "".join(
        f'<test group="{group}" points="{points}"/>' for group, points in tests
    )
    path.mkdir(parents=True, exist_ok=True)
    (path / "problem.xml").write_text(
        f"""<?xml version="1.0" encoding="utf-8"?>
<problem short-name="{short_name}">
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
    package = MIPSPolygon(str(mixed_package))
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
    package = MIPSPolygon(
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
    loader = MIPSPolygonContestLoader(str(mixed_package), FakeFileCacher())
    contest, tasks, participations = loader.get_contest()
    assert contest.name == "sorting"
    assert tasks == ["sorting-output", "sorting-code"]
    assert participations == []
    assert isinstance(
        loader.get_task_loader("sorting-code"), MIPSPolygonBatchTaskLoader
    )
    assert isinstance(
        loader.get_task_loader("sorting-output"), MIPSPolygonOutputOnlyTaskLoader
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
            ["sorting-output"],
        ),
        (
            [("samples", 0), ("s1", 100)],
            (
                '<group name="samples" points-policy="complete-group"/>'
                '<group name="s1" points="100" points-policy="complete-group"/>'
            ),
            ["sorting-code"],
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
    _, tasks, _ = MIPSPolygonContestLoader(str(path), FakeFileCacher()).get_contest()
    assert tasks == expected


def test_batch_task(mixed_package: Path) -> None:
    """The Batch task has every test, the samples and GroupMin parameters."""
    cacher = FakeFileCacher()
    task = MIPSPolygonBatchTaskLoader(str(mixed_package), cacher).get_task(
        get_statement=False
    )
    assert task is not None
    assert task.name == "sorting-code"
    assert task.title == "Sorting (Code)"
    assert task.submission_format == ["sorting-code.%l"]
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
    task = MIPSPolygonOutputOnlyTaskLoader(str(mixed_package), cacher).get_task(
        get_statement=False
    )
    assert task is not None
    assert task.name == "sorting-output"
    assert task.title == "Sorting (Output)"
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
        "README.md",
        "code/solution.cpp",
        "code/solution.py",
        "inputs/input_00.txt",
        "inputs/input_01.txt",
        "inputs/input_02.txt",
        "run.bat",
        "run.sh",
    ]
    assert attachment.read("inputs/input_02.txt") == b"in4\n"
    assert (attachment.getinfo("run.sh").external_attr >> 16) & 0o111
    assert b"\r\n" in attachment.read("run.bat")
    assert b"\r\n" not in attachment.read("run.sh")
    samples = zipfile.ZipFile(
        io.BytesIO(cacher.files[task.attachments["samples.zip"].digest])
    )
    assert sorted(samples.namelist()) == ["input.01.txt", "output.01.txt"]


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
@pytest.mark.parametrize(
    ("args", "solution"),
    [
        (["cat"], None),
        (["py"], ("code/solution.py", "print(input())\n")),
        (
            ["cpp"],
            (
                "code/solution.cpp",
                (
                    "#include <iostream>\n#include <string>\n"
                    "int main()\n{\n    std::string s;\n    std::cin >> s;\n"
                    '    std::cout << s << "\\n";\n}\n'
                ),
            ),
        ),
    ],
)
def test_output_only_kit_makes_submission_zip(
    mixed_package: Path,
    tmp_path: Path,
    args: Sequence[str],
    solution: tuple[str, str] | None,
) -> None:
    if args == ["cpp"] and shutil.which("g++") is None:
        pytest.skip("needs g++")
    cacher = FakeFileCacher()
    task = MIPSPolygonOutputOnlyTaskLoader(str(mixed_package), cacher).get_task(
        get_statement=False
    )
    assert task is not None
    kit = tmp_path / "kit"
    with zipfile.ZipFile(
        io.BytesIO(cacher.files[task.attachments["attachment.zip"].digest])
    ) as attachment:
        attachment.extractall(kit)
    if solution is not None:
        (kit / solution[0]).write_text(solution[1])

    subprocess.run(["bash", str(kit / "run.sh"), *args], check=True, cwd=tmp_path)

    with zipfile.ZipFile(kit / "output.zip") as output:
        assert sorted(output.namelist()) == task.submission_format
        assert output.read("output_02.txt") == b"in4\n"


@pytest.mark.parametrize(
    ("group", "conf", "found"),
    [
        ("sample", None, True),
        ("examples", None, False),
        ("examples", 'SAMPLES_GROUP = "examples"\n', True),
        ("sample", 'SAMPLES_GROUP = "examples"\n', False),
    ],
)
def test_samples_group_names(
    tmp_path: Path, group: str, conf: str | None, found: bool
) -> None:
    """``samples`` and ``sample`` are found by default; SAMPLES_GROUP overrides."""
    groups = (
        f'<group name="{group}" points-policy="complete-group"/>'
        '<group name="s1-OO" points-policy="each-test"/>'
    )
    package = write_package(tmp_path, [(group, 0), ("s1-OO", 100)], groups)
    if conf is not None:
        (package / "files").mkdir()
        (package / "files" / "cms_conf.py").write_text(conf, encoding="utf-8")
    task = MIPSPolygonOutputOnlyTaskLoader(str(package), FakeFileCacher()).get_task(
        get_statement=False
    )
    assert task is not None
    assert ("samples.zip" in task.attachments) == found


def test_cms_conf_overrides_output_only_substring(mixed_package: Path) -> None:
    """files/cms_conf.py can change the OutputOnly group substring."""
    (mixed_package / "files").mkdir()
    (mixed_package / "files" / "cms_conf.py").write_text(
        'OUTPUT_ONLY_GROUP_SUBSTRING = "s2"\n', encoding="utf-8"
    )
    package = MIPSPolygon(str(mixed_package))
    assert [t.index for t in package.output_only_tests] == [3, 4]


BATCH_ONLY_TESTS = [("samples", 0), ("s1", 100)]
BATCH_ONLY_GROUPS = (
    '<group name="samples" points-policy="complete-group"/>'
    '<group name="s1" points="100" points-policy="complete-group"/>'
)


def write_contest(path: Path, problems: Sequence[str]) -> Path:
    """Write a Polygon contest package listing the given problems.

    Args:
        path: Directory in which to create the contest package.
        problems: Short names of the problems, in contest order.

    Returns:
        The contest package root.
    """
    problems_xml = "".join(
        f'<problem index="{chr(ord("A") + i)}" '
        f'url="https://polygon.codeforces.com/p/user/{name}"/>'
        for i, name in enumerate(problems)
    )
    path.mkdir(parents=True, exist_ok=True)
    (path / "contest.xml").write_text(
        f"""<?xml version="1.0" encoding="utf-8"?>
<contest url="https://polygon.codeforces.com/c/1/practice">
  <names>
    <name language="russian" value="Practice RU"/>
    <name language="english" main="true" value="Practice Contest"/>
  </names>
  <problems>{problems_xml}</problems>
</contest>
""",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def contest_package(tmp_path: Path) -> Path:
    """Return a contest with a mixed problem and a Batch-only problem."""
    path = write_contest(tmp_path / "practice", ["beta", "alpha"])
    write_package(path / "problems" / "beta", MIXED_TESTS, MIXED_GROUPS, "beta")
    write_package(
        path / "problems" / "alpha", BATCH_ONLY_TESTS, BATCH_ONLY_GROUPS, "alpha"
    )
    return path


def test_multi_contest_loader_creates_tasks_for_every_problem(
    contest_package: Path,
) -> None:
    """Every problem yields its tasks, in contest.xml order, Output first."""
    loader = MIPSPolygonMultiContestLoader(str(contest_package), FakeFileCacher())
    contest, tasks, participations = loader.get_contest()
    assert contest.name == "practice"
    assert contest.description == "Practice Contest"
    assert tasks == ["beta-output", "beta-code", "alpha-code"]
    assert participations == []
    assert isinstance(loader.get_task_loader("beta-code"), MIPSPolygonBatchTaskLoader)
    assert isinstance(
        loader.get_task_loader("beta-output"), MIPSPolygonOutputOnlyTaskLoader
    )
    alpha = loader.get_task_loader("alpha-code").get_task(get_statement=False)
    assert alpha is not None
    assert alpha.name == "alpha-code"
    assert sorted(alpha.active_dataset.testcases) == ["1_samples", "2_s1"]
    with pytest.raises(ValueError, match="Unknown task"):
        loader.get_task_loader("alpha-output")


def test_multi_contest_loader_reads_contestants(contest_package: Path) -> None:
    """contestants.txt lines become participations."""
    (contest_package / "contestants.txt").write_text(
        "alice;secret;Alice;A;0\nbob;;Bob;B;1\n\n", encoding="utf-8"
    )
    loader = MIPSPolygonMultiContestLoader(str(contest_package), FakeFileCacher())
    _, _, participations = loader.get_contest()
    assert [p["username"] for p in participations] == ["alice", "bob"]
    assert [p["hidden"] for p in participations] == [False, True]
    assert "password" in participations[0]
    assert "password" not in participations[1]


def test_multi_contest_loader_rejects_clashing_task_names(tmp_path: Path) -> None:
    """Two problems producing the same task name are an error."""
    path = write_contest(tmp_path / "practice", ["first", "second"])
    write_package(path / "problems" / "first", MIXED_TESTS, MIXED_GROUPS, "dup")
    write_package(
        path / "problems" / "second", BATCH_ONLY_TESTS, BATCH_ONLY_GROUPS, "dup"
    )
    with pytest.raises(ValueError, match='task "dup-code"'):
        MIPSPolygonMultiContestLoader(str(path), FakeFileCacher())


def test_package_without_generated_tests_is_rejected(mixed_package: Path) -> None:
    """A package whose tests were not generated gives a clear error."""
    (mixed_package / "tests" / "02").unlink()
    with pytest.raises(ValueError, match=r"lacks test files \(tests/02\)"):
        MIPSPolygon(str(mixed_package))


def test_title_prefers_english_name(mixed_package: Path) -> None:
    """The English name is used as title even when it is not listed first."""
    problem_xml = mixed_package / "problem.xml"
    problem_xml.write_text(
        problem_xml.read_text(encoding="utf-8").replace(
            '<names><name language="english" value="Sorting"/></names>',
            '<names><name language="chinese" value="排序"/>'
            '<name language="english" value="Sorting"/>'
            '<name language="malay" value="Isihan"/></names>',
        ),
        encoding="utf-8",
    )
    assert MIPSPolygon(str(mixed_package)).title == "Sorting"


def test_default_task_args(mixed_package: Path) -> None:
    """Tasks default to OI restricted feedback, IOI 2017- scoring, 60 submissions."""
    cacher = FakeFileCacher()
    batch = MIPSPolygonBatchTaskLoader(str(mixed_package), cacher).get_task(
        get_statement=False
    )
    output_only = MIPSPolygonOutputOnlyTaskLoader(str(mixed_package), cacher).get_task(
        get_statement=False
    )
    for task in (batch, output_only):
        assert task is not None
        assert task.feedback_level == "oi_restricted"
        assert task.score_mode == "max_subtask"
        assert task.max_submission_number == 60


def test_cms_conf_general_overrides_defaults(mixed_package: Path) -> None:
    """``general`` in files/cms_conf.py overrides the default task arguments."""
    (mixed_package / "files").mkdir()
    (mixed_package / "files" / "cms_conf.py").write_text(
        'general = {"feedback_level": "full", "max_submission_number": None}\n',
        encoding="utf-8",
    )
    task = MIPSPolygonBatchTaskLoader(str(mixed_package), FakeFileCacher()).get_task(
        get_statement=False
    )
    assert task is not None
    assert task.feedback_level == "full"
    assert task.max_submission_number is None
    assert task.score_mode == "max_subtask"
