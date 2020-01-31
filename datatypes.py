# Copyright The Linux Foundation
# SPDX-License-Identifier: Apache-2.0

from enum import Enum

class ProjectRepoType(Enum):
    UNKNOWN = 0
    GERRIT = 1
    GITHUB = 2
    GITHUB_SHARED = 3

class Status(Enum):
    UNKNOWN = 0
    START = 1
    GOTLISTING = 2
    GOTCODE = 3
    ZIPPEDCODE = 4
    UPLOADEDCODE = 5
    RANAGENTS = 6
    CLEARED = 7
    GOTSPDX = 8
    IMPORTEDSCAN = 9
    CREATEDREPORTS = 10
    MADEDRAFTFINDINGS = 11
    APPROVEDFINDINGS = 12
    MADEFINALFINDINGS = 13
    UPLOADEDSPDX = 14
    UPLOADEDREPORTS = 15
    DELIVERED = 16
    STOPPED = 90
    MAX = 99

class Priority(Enum):
    UNKNOWN = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    VERYHIGH = 4

class MatchText:

    def __init__(self):
        super(MatchText, self).__init__()

        self._text = ""
        self._comment = ""
        self._actions = []

class Finding:

    def __init__(self):
        super(Finding, self).__init__()

        # loaded from findings file
        self._id = -1
        self._priority = Priority.UNKNOWN
        self._matches_path = []
        self._matches_license = []
        self._matches_subproject = []
        self._title = ""
        self._text = ""

class Instance:

    def __init__(self):
        super(Instance, self).__init__()

        # ID of parent Finding that this refers to
        self._finding_id = -1

        # Priority of finding
        # FIXME this is temporary, for purposes of sorting in findings.py
        # FIXME should find a different solution
        self._priority = Priority.UNKNOWN

        # determined based on analysis
        self._files = []

        # determined based on analysis, for subprojects w/out specific files
        self._subprojects = []

        # year-month where this instance was first reported for this project
        self._first = ""

        # is this a new instance (true) or a repeat instance (false)?
        self._isnew = True

        # if not new, did the list of files change? ignore if new
        self._files_changed = False

        # if using JIRA, what is the JIRA ticket ID?
        self._jira_id = ""


class InstanceSet:

    def __init__(self):
        super(InstanceSet, self).__init__()

        # list of instances that are flagged
        self._flagged = []

        # list of files that are unflagged
        self._unflagged = []


class Project:

    def __init__(self):
        super(Project, self).__init__()

        self._ok = False
        self._name = ""
        self._repotype = ProjectRepoType.UNKNOWN
        self._status = Status.UNKNOWN

        self._subprojects = {}

        self._matches = []
        self._findings = []
        self._flag_categories = []

        # only if Gerrit
        self._gerrit_apiurl = ""
        self._gerrit_subproject_config = "manual"
        self._gerrit_repos_ignore = []
        self._gerrit_repos_pending = []

        # only if GITHUB_SHARED
        self._github_shared_org = ""
        self._github_shared_repos_ignore = []
        self._github_shared_repos_pending = []

        # SLM vars
        self._slm_shared = True
        self._slm_prj = ""
        self._slm_combined_report = False

        # web upload vars, only for combined reports
        self._web_combined_uuid = ""
        self._web_combined_html_url = ""
        self._web_combined_xlsx_url = ""

    def resetNewMonth(self):
        self._status = Status.START

        # tell subprojects to reset
        for sp in self._subprojects.values():
            sp.resetNewMonth()


class Subproject:

    def __init__(self):
        super(Subproject, self).__init__()

        self._ok = False
        self._name = ""
        self._repotype = ProjectRepoType.UNKNOWN
        self._status = Status.UNKNOWN
        self._repos = []

        self._code_pulled = ""
        self._code_path = ""
        self._code_anyfiles = False
        # mapping of repo name to pulled commit hash
        self._code_repos = {}

        # only if GitHub
        self._github_org = ""
        self._github_ziporg = ""
        self._github_repos_ignore = []
        self._github_repos_pending = []

        # SLM vars
        self._slm_prj = ""  # only if project's _slm_shared == False
        self._slm_sp = ""
        self._slm_scan_id = -1
        self._slm_pending_lics = []

        # web upload vars
        self._web_uuid = ""
        self._web_html_url = ""
        self._web_xlsx_url = ""

    def resetNewMonth(self):
        self._status = Status.START

        # reset code retrieval vars
        self._code_pulled = ""
        self._code_path = ""
        self._code_anyfiles = False
        self._code_repos = {}

        # reset scan-dependent SLM vars
        self._slm_scan_id = -1
        self._slm_pending_lics = []

        # reset web upload vars
        self._web_uuid = ""
        self._web_html_url = ""
        self._web_xlsx_url = ""

class JiraSecret:

    def __init__(self):
        super(JiraSecret, self).__init__()

        self._project_name = ""
        self._jira_project = ""
        self._server = ""
        self._username = ""
        self._password = ""


class Secrets:

    def __init__(self):
        super(Secrets, self).__init__()

        # mapping of project name to jira server details
        self._jira = {}


class Config:

    def __init__(self):
        super(Config, self).__init__()

        self._ok = False
        self._storepath = ""
        self._projects = {}
        self._month = ""
        self._version = 0
        self._slm_home = ""
        self._spdx_github_org = ""
        self._spdx_github_signoff = ""
        self._web_server = ""
        self._web_reports_path = ""
        self._web_reports_url = ""
        # DO NOT OUTPUT THESE TO CONFIG.JSON
        self._gh_oauth_token = ""
        self._secrets = None

    def __repr__(self):
        is_ok = "OK"
        if self._ok == False:
            is_ok = "NOT OK"

        return f"Config ({is_ok}): {self._storepath}, PROJECTS: {self._projects}"
