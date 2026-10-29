#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Java programming language definition, using the default JDK installed
in the system.

"""

import os
from shlex import quote as shell_quote

from cms.grading import Language


__all__ = ["JavaJDK"]


class JavaJDK(Language):
    """This defines the Java programming language, compiled and executed using
    the Java Development Kit available in the system.

    """

    USE_JAR = True

    # Without a grader, the solution is compiled as MAIN_CLASS.java and run as
    # MAIN_CLASS, since its file name may not be a valid Java class name.
    MAIN_CLASS = "Main"

    @property
    def name(self):
        """See Language.name."""
        return "Java / JDK"

    @property
    def source_extensions(self):
        """See Language.source_extensions."""
        return [".java"]

    @property
    def executable_extension(self):
        """See Language.executable_extension."""
        return ".jar" if JavaJDK.USE_JAR else ".zip"

    @property
    def requires_multithreading(self):
        """See Language.requires_multithreading."""
        return True

    def get_compilation_commands(self,
                                 source_filenames, executable_filename,
                                 for_evaluation=True):
        """See Language.get_compilation_commands."""
        commands = []
        main_source = JavaJDK.MAIN_CLASS + ".java"
        if len(source_filenames) == 1 and source_filenames[0] != main_source:
            commands.append(["/bin/cp", source_filenames[0], main_source])
            source_filenames = [main_source]
        compile_command = ["/usr/bin/javac"] + source_filenames
        # We need to let the shell expand *.class as javac create
        # a class file for each inner class.
        if JavaJDK.USE_JAR:
            jar_command = ["/bin/sh", "-c",
                           " ".join(["jar", "cf",
                                     shell_quote(executable_filename),
                                     "*.class"])]
            return commands + [compile_command, jar_command]
        else:
            zip_command = ["/bin/sh", "-c",
                           " ".join(["zip",
                                     shell_quote(executable_filename),
                                     "*.class"])]
            return commands + [compile_command, zip_command]

    def get_evaluation_commands(
            self, executable_filename, main=None, args=None):
        """See Language.get_evaluation_commands."""
        args = args if args is not None else []
        if main == os.path.splitext(executable_filename)[0]:
            main = JavaJDK.MAIN_CLASS
        if JavaJDK.USE_JAR:
            # executable_filename is a jar file, main is the name of
            # the main java class
            return [["/usr/bin/java", "-Deval=true", "-Xmx512M", "-Xss64M",
                     "-cp", executable_filename, main] + args]
        else:
            unzip_command = ["/usr/bin/unzip", executable_filename]
            command = ["/usr/bin/java", "-Deval=true", "-Xmx512M", "-Xss64M",
                       main] + args
            return [unzip_command, command]
