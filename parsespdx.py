# Copyright The Linux Foundation
# SPDX-License-Identifier: Apache-2.0

import os

from datatypes import SLMCategory, SLMFile, SLMLicense, Status
from slmjson import saveSLMCategories
from slm.tvReader import TVReader
from slm.tvParser import TVParser

MD5_EMPTY_FILE = "d41d8cd98f00b204e9800998ecf8427e"

def doParseSPDXForSubproject(cfg, prj, sp):
    # make sure we're at the right stage
    if sp._status != Status.GOTSPDX:
        print(f"{prj._name}/{sp._name}: status is {sp._status}, won't parse SPDX now")
        return False

    # find the SPDX file we want to parse
    spdxFolder = os.path.join(cfg._storepath, cfg._month, "spdx", prj._name)
    spdxFilename = f"{sp._name}-{sp._code_pulled}.spdx"
    spdxFilePath = os.path.join(spdxFolder, spdxFilename)

    tvList = []
    try:
        with open(spdxFilePath, 'r') as f:
            # read in the tag-value pairs line-by-line
            reader = TVReader()
            for line in f:
                reader.readNextLine(line)
            tvList = reader.finalize()
            # check for errors
            if reader.isError():
                print(f"{prj._name}/{sp._name}: error reading SPDX file: {reader.errorMessage}")

    except FileNotFoundError:
        print(f"{prj._name}/{sp._name}: SPDX tag-value file not found at {spdxFilePath}")
        return False

    # parse the tag-value pairs
    parser = TVParser()
    for tag, value in tvList:
        parser.parseNextPair(tag, value)
    fdList = parser.finalize()
    # check for errors
    if parser.isError():
        print(f"{prj._name}/{sp._name}: error parsing SPDX file: {parser.errorMessage}")
        return False
    # empty list means no file data found
    if fdList == []:
        print(f"{prj._name}/{sp._name}: error parsing SPDX file: no file data found")
        return False

    # apply adjustments
    applyAliases(cfg, prj, fdList)
    applyNoLicenseFoundFindings(cfg, prj, fdList)

    # create one category for each SLMCategoryConfig, so they're in
    # the correct order; same for licenses in each category
    # we'll later drop any that don't have files
    cats = buildCategories(cfg, prj)

    # reformulate into category/license/file structure, and/or error out
    # if any are missing
    missing_lics = []
    for fd in fdList:
        cat_name = getCategoryForLicense(cfg, prj, fd.license)
        if cat_name:
            retval = addToLicense(cats, cat_name, fd)
            if not retval:
                print(f"{prj._name}/{sp._name}: error adding file path {fd.path} for license {fd.license}")
                return False
        else:
            # license isn't categorized
            if fd.license not in missing_lics:
                missing_lics.append(fd.license)

    # check for missing licenses
    if len(missing_lics) > 0:
        sp._slm_pending_lics = missing_lics
        print(f"{prj._name}/{sp._name}: need to add licenses to categories, see licenses-pending")
        return False
    else:
        sp._slm_pending_lics = []

    # and prune out any categories / licenses with zero files
    cats = pruneCategories(cats)

    # finally, save categories out to JSON
    # create report directory for project if it doesn't already exist
    reportFolder = os.path.join(cfg._storepath, cfg._month, "report", prj._name)
    if not os.path.exists(reportFolder):
        os.makedirs(reportFolder)
    slmJsonFilename = f"{sp._name}-{sp._code_pulled}.json"
    slmJsonPath = os.path.join(reportFolder, slmJsonFilename)
    saveSLMCategories(cats, slmJsonPath)

    # once we get here, the SPDX file has been parsed into JSON
    sp._status = Status.PARSEDSPDX

    # and when we return, the runner framework should update the project's
    # status to reflect the min of its subprojects
    return True

def applyAliases(cfg, prj, fdList):
    # build lookup of all configured aliases, with orig name => translated name
    aliases = {}
    for cat in prj._slm_category_configs:
        for lic in cat._license_configs:
            for a in lic._aliases:
                aliases[a] = lic._name

    # now, walk through fdList and apply aliases
    for fd in fdList:
        newLicense = aliases.get(fd.license, "")
        if newLicense != "":
            fd.license = newLicense

def applyNoLicenseFoundFindings(cfg, prj, fdList):
    # prepare extension search lists
    # split out those extensions ending in asterisks => anywhere in file path, not just at end
    # split out those extensions ending in equal sign => exact filename match
    anyList = []
    exactList = []
    extRevisedList = []
    for ext in prj._slm_extensions_skip:
        if ext.endswith("*"):
            anyList.append(str.lower(ext.rstrip("*")))
        elif ext.endswith("="):
            exactList.append(str.lower(ext.rstrip("=")))
        else:
            extRevisedList.append(str.lower(ext))

    for fd in fdList:
        if fd.license == "No license found":
            # check file extensions
            ext = os.path.splitext(fd.path)[1].lstrip(".")
            if str.lower(ext) in extRevisedList:
                fd.finding_extensions = "yes"
            # also check list of those with asterisks, for pattern anywhere in filename
            for pattern in anyList:
                if pattern in str.lower(fd.path):
                    fd.finding_extensions = "yes"
            # also check whether the filename is exactly the same as the "extension"
            for exactPattern in exactList:
                if exactPattern == str.lower(os.path.split(fd.path)[1]):
                    fd.finding_extensions = "yes"

            # also check third party dirs
            for directory in prj._slm_thirdparty_dirs:
                if directory in fd.path:
                    fd.finding_thirdparty = "yes"

            # also check empty files
            if fd.md5 == MD5_EMPTY_FILE:
                fd.finding_emptyfile = "yes"

def getCategoryForLicense(cfg, prj, lic):
    for cat_cfg in prj._slm_category_configs:
        for lic_cfg in cat_cfg._license_configs:
            if lic_cfg._name == lic:
                return cat_cfg._name

    return None

def buildCategories(cfg, prj):
    cats = []
    for cc in prj._slm_category_configs:
        cat = SLMCategory()
        cat._name = cc._name
        for lc in cc._license_configs:
            lic = SLMLicense()
            lic._name = lc._name
            cat._licenses.append(lic)
        cats.append(cat)
    return cats

def pruneCategories(cats):
    cats = [cat for cat in cats if cat._numfiles > 0]
    for cat in cats:
        cat._licenses = [lic for lic in cat._licenses if lic._numfiles > 0]
    return cats

def addToLicense(cats, cat_name, fd):
    # find the category
    for cat in cats:
        if cat._name == cat_name:
            # find the license
            for lic in cat._licenses:
                if lic._name == fd.license:
                    # add it
                    f = SLMFile()
                    f._path = fd.path
                    if fd.finding_extensions != "":
                        f._findings["extension"] = fd.finding_extensions
                    if fd.finding_thirdparty != "":
                        f._findings["thirdparty"] = fd.finding_thirdparty
                    if fd.finding_emptyfile != "":
                        f._findings["emptyfile"] = fd.finding_emptyfile
                    lic._numfiles += 1
                    cat._numfiles += 1
                    lic._files.append(f)
                    return True
    return False
