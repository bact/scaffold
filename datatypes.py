# Copyright The Linux Foundation
# SPDX-License-Identifier: Apache-2.0

from enum import Enum

class ProjectRepoType(Enum):
    UNKNOWN = 0
    GERRIT = 1
    GITHUB = 2

class Status(Enum):
    UNKNOWN = 0
    START = 1
    GOTLISTING = 2
    GOTCODE = 3
    UPLOADEDCODE = 4
    RANAGENTS = 5
    CLEARED = 6
    GOTSPDX = 7
    IMPORTEDSCAN = 8
    CREATEDREPORTS = 9
    ADDEDCOMMENTS = 10
    DELIVERED = 11
    UPLOADEDSPDX = 12

class Project:

    def __init__(self):
        super(Project, self).__init__()

        self._ok = False
        self._name = ""
        self._repotype = ProjectRepoType.UNKNOWN
        self._status = Status.UNKNOWN

        self._subprojects = {}

        # only if Gerrit
        self._gerrit_apiurl = ""
        self._gerrit_repos_ignore = []
    
    def __repr__(self):
        is_ok = "OK"
        if self._ok == False:
            is_ok = "NOT OK"

        if self._repotype == ProjectRepoType.GERRIT:
            return f"{self._name} ({is_ok}): {self._repotype.name}, {self._gerrit_apiurl}, IGNORE: {self._gerrit_repos_ignore}, SUBPROJECTS: {self._subprojects}"
        else:
            return f"{self._name} ({is_ok}): {self._repotype.name}, SUBPROJECTS: {self._subprojects}"


class Subproject:

    def __init__(self):
        super(Subproject, self).__init__()

        self._ok = False
        self._name = ""
        self._repotype = ProjectRepoType.UNKNOWN
        self._status = Status.UNKNOWN
        self._repos = []

        # only if GitHub
        self._github_org = ""
        self._github_ziporg = ""
        self._github_repos_ignore = []

    def __repr__(self):
        is_ok = "OK"
        if self._ok == False:
            is_ok = "NOT OK"

        if self._repotype == ProjectRepoType.GITHUB:
            return f"{self._name} ({is_ok}): {self._repotype.name}, {self._github_org}, {self._github_ziporg}, {self._repos}, IGNORE: {self._github_repos_ignore}"
        else:
            return f"{self._name} ({is_ok}): {self._repotype.name}, {self._repos}"

class Config:

    def __init__(self):
        super(Config, self).__init__()

        self._ok = False
        self._storepath = ""
        self._projects = {}
    
    def __repr__(self):
        is_ok = "OK"
        if self._ok == False:
            is_ok = "NOT OK"

        return f"Config ({is_ok}): {self._storepath}, PROJECTS: {self._projects}"
