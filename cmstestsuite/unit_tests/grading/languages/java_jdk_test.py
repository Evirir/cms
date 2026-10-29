#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
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

"""Tests for the Java main class naming of JavaJDK."""

from cms.grading.languages.java_jdk import JavaJDK


def test_single_source_compiles_as_main():
    """Test that a solution without a grader is copied to Main.java."""
    commands = JavaJDK().get_compilation_commands(
        ["task-code.java"], "task-code.jar")
    assert commands[0] == ["/bin/cp", "task-code.java", "Main.java"]
    assert commands[1] == ["/usr/bin/javac", "Main.java"]
    assert len(commands) == 3


def test_main_source_is_not_copied():
    """Test that a solution already named Main.java is compiled as is."""
    commands = JavaJDK().get_compilation_commands(["Main.java"], "Main.jar")
    assert commands[0] == ["/usr/bin/javac", "Main.java"]
    assert len(commands) == 2


def test_grader_sources_keep_their_names():
    """Test that sources compiled with a grader keep their names."""
    commands = JavaJDK().get_compilation_commands(
        ["grader.java", "task.java"], "task.jar")
    assert commands[0] == ["/usr/bin/javac", "grader.java", "task.java"]
    assert len(commands) == 2


def test_solution_runs_main_class():
    """Test that a solution run under the executable's name runs Main."""
    commands = JavaJDK().get_evaluation_commands(
        "task-code.jar", main="task-code")
    assert commands[-1][-1] == "Main"


def test_grader_main_class_is_kept():
    """Test that a grader main class is passed through unchanged."""
    commands = JavaJDK().get_evaluation_commands("task.jar", main="grader")
    assert commands[-1][-1] == "grader"
