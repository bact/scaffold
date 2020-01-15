# Copyright The Linux Foundation
# SPDX-License-Identifier: Apache-2.0

import json
import os

from jinja2 import Template

from datatypes import FindingsInstance, Priority, Status

# Helper for calculating findings instances and review categories
# Call with spName == "COMBINED" for combined report (should only
#   be used in print statements anyway)
# Returns lists of instances and review tuples
# Returns [], [] if no findings templates, or None, None if error
def analyzeFindingsInstances(cfg, prj, spName, slmJsonFilename):
    instances = []
    needReview = []

    # confirm whether this project has any findings templates
    if prj._findings == []:
        print(f'{prj._name}/{spName}: No findings template, skipping analysis')
        return [], []

    # get SLM JSON analysis details
    catLicFiles = loadSLMJSON(slmJsonFilename)
    if catLicFiles == []:
        print(f'{prj._name}/{spName}: Could not get any SLM category/license/file results; bailing')
        return None, None

    # walk through each finding template, and determine whether it has any instances
    # for this subproject
    for fi in prj._findings:
        inst = FindingsInstance()
        foundAny = False

        # for now, skip over subproject-only findings
        if fi._matches_subproject != [] and fi._matches_path == [] and fi._matches_license == []:
            continue

        # for this finding template, walk through each cat/lic/file tuple and see whether it applies
        for catName, licName, fileName in catLicFiles:
            matchesSubproject = False
            matchesPath = False
            matchesLic = False
            failedMatch = False

            # if the finding requires a subproject match, does it (contains) match any?
            if fi._matches_subproject != []:
                # requires subproject match, so check each one
                for p in fi._matches_subproject:
                    if p in fileName:
                        matchesSubproject = True
                if not matchesSubproject:
                    # failed the subproject match, so go on to the next lic/file pair
                    failedMatch = True

            # if the finding requires a path match, does it (contains) match any?
            if fi._matches_path != []:
                # requires path match, so check each one
                for p in fi._matches_path:
                    if p in fileName:
                        matchesPath = True
                if not matchesPath:
                    # failed the path match, so go on to the next lic/file pair
                    failedMatch = True

            # if the finding requires a license match, does it (exactly) match any?
            if fi._matches_license != []:
                # requires license match, so check each one
                for l in fi._matches_license:
                    if l == licName:
                        matchesLic = True
                if not matchesLic:
                    # failed the license match, so go on to the next lic/file pair
                    failedMatch = True

            # check whether it's a match
            if not failedMatch:
                # it's a match!
                if foundAny:
                    # this is a repeat finding, so just add our file to the existing one
                    inst._files.append(fileName)
                else:
                    # this is the first one for this instance, so initialize it
                    inst._finding = fi
                    inst._files = [fileName]
                    foundAny = True

        # done with lic/file pairs, so add this instance if we found any files
        if foundAny:
            instances.append(inst)

    # now, walk back through the category / license / files list again. for the
    # flagged categories, if a file is listed and is NOT in any instance, add it to
    # the review list
    for catName, licName, fileName in catLicFiles:
        found = False
        if catName in prj._flag_categories:
            # check if this file is in any instance
            for inst in instances:
                if fileName in inst._files:
                    found = True
            if not found:
                # it wasn't, so add it to the review list
                clfTuple = (catName, licName, fileName)
                needReview.append(clfTuple)
    
    # also, if there are any matches which list a subproject and NEITHER paths
    # nor licenses, then make sure we add that one for the subproject, if
    # applies to this subproject
    for fi in prj._findings:
        if fi._matches_subproject != [] and fi._matches_path == [] and fi._matches_license == [] and (spName == "COMBINED" or spName in fi._matches_subproject):
            inst = FindingsInstance()
            inst._finding = fi
            if spName == "COMBINED":
                inst._subprojects = fi._matches_subproject
            instances.append(inst)

    # finally, sort instances by finding priority
    instances.sort(key=lambda inst: inst._finding._priority.value, reverse=True)

    return instances, needReview

# Helper for calculating category/license summary file counts.
# Returns (cats, totalCount, noLicThird, noLicEmpty, noLicExt) tuple
#   cats = (name, list of (lics, catTotalCount) tuples)
#     lics = list of (license, licCount) tuples
#   totalCount = total number of files overall
#   noLicThird = total "No license found" files in third-party dirs
#   noLicEmpty = total "No license found" empty files (prefers noLicThird)
#   noLicExt   = total "No license found" files with "ignore" extensions
#                  (prefers noLicExt)
#   noLicRest  = total "No license found" not falling into other categories
# Zero count lics / cats are ignored and not returned.
def getLicenseSummaryDetails(cfg, slmJsonFilename):
    cats = []
    totalCount = 0
    noLicThird = 0
    noLicEmpty = 0
    noLicExt = 0
    noLicRest = 0

    # walk through SLM JSON file and prepare summary count details
    try:
        with open(slmJsonFilename, "r") as f:
            # not using "get" below b/c we want it to crash if JSON is malformed
            # should be array of category objects
            cat_arr = json.load(f)
            for cat_dict in cat_arr:
                cat_numFiles = cat_dict["numFiles"]
                # ignore categories with no files
                if cat_numFiles == 0:
                    continue
                totalCount += cat_numFiles
                cat_name = cat_dict["name"]
                # get licenses and file counts
                lics = []
                for lic_dict in cat_dict["licenses"]:
                    lic_numFiles = lic_dict["numFiles"]
                    # ignore licenses with no files
                    if lic_numFiles == 0:
                        continue
                    lic = (lic_dict["name"], lic_numFiles)
                    lics.append(lic)
                    # also do further processing if this is "No license found"
                    if lic_dict["name"] == "No license found":
                        for file_dict in lic_dict["files"]:
                            findings_dict = file_dict.get("findings", {})
                            if findings_dict.get("thirdparty", "no") == "yes":
                                noLicThird += 1
                                continue
                            if findings_dict.get("emptyfile", "no") == "yes":
                                noLicEmpty += 1
                                continue
                            if findings_dict.get("extension", "no") == "yes":
                                noLicExt += 1
                                continue
                            noLicRest += 1
                # add these licenses to the cats array
                cat = (cat_name, lics, cat_numFiles)
                cats.append(cat)

        return (cats, totalCount, noLicThird, noLicEmpty, noLicExt, noLicRest)

    except json.decoder.JSONDecodeError as e:
        print(f'Error loading or parsing {slmJsonFilename}: {str(e)}')
        return []

# Helper to load SLM JSON document, and return a list of (category, license, filename) tuples
def loadSLMJSON(slmJsonFilename):
    catLicFiles = []
    try:
        with open(slmJsonFilename, "r") as f:
            # not using "get" below b/c we want it to crash if JSON is malformed
            # should be array of category objects
            cat_arr = json.load(f)
            for cat_dict in cat_arr:
                cat_name = cat_dict["name"]
                # contains array of license objects
                lic_arr = cat_dict["licenses"]
                for lic_dict in lic_arr:
                    # contains license name and array of file objects
                    lic_name = lic_dict["name"]
                    file_arr = lic_dict["files"]
                    for file_dict in file_arr:
                        # contains file path in path key
                        file_name = file_dict["path"]
                        cfl_tup = (cat_name, lic_name, file_name)
                        catLicFiles.append(cfl_tup)
        catLicFiles.sort(key=lambda tup: (tup[0], tup[1], tup[2]))
        return catLicFiles
    except json.decoder.JSONDecodeError as e:
        print(f'Error loading or parsing {slmJsonFilename}: {str(e)}')
        return []

def getShortPriorityString(p):
    if p == Priority.VERYHIGH:
        return "veryhigh"
    elif p == Priority.HIGH:
        return "high"
    elif p == Priority.MEDIUM:
        return "medium"
    elif p == Priority.LOW:
        return "low"
    else:
        return "unknown"
    
def getFullPriorityString(p):
    if p == Priority.VERYHIGH:
        return "Very High"
    elif p == Priority.HIGH:
        return "High"
    elif p == Priority.MEDIUM:
        return "Medium"
    elif p == Priority.LOW:
        return "Low"
    else:
        return "Unspecified"


# Helper for creating subproject findings document, whether draft or final
# Returns path to findings report (or "" if not written) and path to
# review report (or "" if not written)
def makeFindingsForSubproject(cfg, prj, sp, isDraft, includeReview=True):
    reviewReportWrittenPath = ""

    # load template
    tmplstr = ""
    with open("templates/findings.html", "r") as tmpl_f:
        tmplstr = tmpl_f.read()

    # calculate paths; report folder would have been created in doCreateReport stage
    reportFolder = os.path.join(cfg._storepath, cfg._month, "report", prj._name)
    slmJsonFilename = f"{sp._name}-{sp._code_pulled}.json"
    slmJsonPath = os.path.join(reportFolder, slmJsonFilename)
    reviewFilename = f"{sp._name}-{sp._code_pulled}-REVIEW.txt"
    if isDraft:
        htmlFilename = f"{sp._name}-{sp._code_pulled}-DRAFT.html"
    else:
        htmlFilename = f"{sp._name}-{sp._code_pulled}.html"
    htmlPath = os.path.join(reportFolder, htmlFilename)

    # if there's already a file at the location, needs to be deleted before we will proceed
    if os.path.exists(htmlPath):
        # print(f"{prj._name}/{sp._name}: run 'approve' action to finalize or delete existing report to re-run")
        return "", ""

    # get analysis results
    instances, needReview = analyzeFindingsInstances(cfg, prj, sp._name, slmJsonPath)

    # build review doc if needed
    reviewFilePath = os.path.join(reportFolder, reviewFilename)
    if needReview != [] and includeReview:
        with open(reviewFilePath, "w") as review_f:
            for catName, licName, fileName in needReview:
                review_f.write(f"{catName}: {licName}: {fileName}\n")
        print(f"{prj._name}/{sp._name}: REVIEW file written to {reviewFilename}")
        reviewReportWrittenPath = reviewFilePath
    else:
        # delete review doc if there's an old one there
        if os.path.exists(reviewFilePath):
            os.remove(reviewFilePath)

    # if no instances, that's fine, we'll still want to create the report

    # get license summary data
    cats, totalCount, noLicThird, noLicEmpty, noLicExt, noLicRest = getLicenseSummaryDetails(cfg, slmJsonPath)

    # build template data fillers
    repoData = []
    for repoName, commit in sp._code_repos.items():
        rdTup = (repoName, commit[0:8])
        repoData.append(rdTup)
    repoData.sort(key=lambda tup: tup[0])

    findingData = []
    for inst in instances:
        fd = {
            "priorityShort": getShortPriorityString(inst._finding._priority),
            "priorityFull": getFullPriorityString(inst._finding._priority),
            "description": inst._finding._text,
            "numFiles": len(inst._files),
            "files": inst._files,
            "subprojects": inst._subprojects,
        }
        findingData.append(fd)

    renderData = {
        "prjName": prj._name,
        "spName": sp._name,
        "codeDate": sp._code_pulled,
        "repoData": repoData,
        "findingData": findingData,
        "licenseSummary": {
            "cats": cats,
            "totalCount": totalCount,
            "noLicThird": noLicThird,
            "noLicEmpty": noLicEmpty,
            "noLicExt": noLicExt,
            "noLicRest": noLicRest,
        },
    }

    # and render it!
    tmpl = Template(tmplstr)
    renderedHtml = tmpl.render(renderData)

    # and write the results to disk
    with open(htmlPath, "w") as report_f:
        report_f.write(renderedHtml)
    
    if isDraft:
        print(f"{prj._name}/{sp._name}: DRAFT findings written to {htmlFilename}")
    else:
        print(f"{prj._name}/{sp._name}: FINAL findings written to {htmlFilename}")

    return htmlPath, reviewReportWrittenPath

# Helper for creating project findings document, whether draft or final
# Returns path to findings report (or "" if not written) and path to
# review report (or "" if not written)
def makeFindingsForProject(cfg, prj, isDraft, includeReview=True):
    reviewReportWrittenPath = ""

    # load template
    tmplstr = ""
    with open("templates/findings.html", "r") as tmpl_f:
        tmplstr = tmpl_f.read()

    # calculate paths; report folder would have been created in doCreateReport stage
    reportFolder = os.path.join(cfg._storepath, cfg._month, "report", prj._name)
    slmJsonFilename = f"{prj._name}-{cfg._month}.json"
    slmJsonPath = os.path.join(reportFolder, slmJsonFilename)
    reviewFilename = f"{prj._name}-{cfg._month}-REVIEW.txt"
    if isDraft:
        htmlFilename = f"{prj._name}-{cfg._month}-DRAFT.html"
    else:
        htmlFilename = f"{prj._name}-{cfg._month}.html"
    htmlPath = os.path.join(reportFolder, htmlFilename)

    # if there's already a file at the location, needs to be deleted before we will proceed
    if os.path.exists(htmlPath):
        # print(f"{prj._name}: run 'approve' action to finalize or delete existing report to re-run")
        return "", ""

    # get analysis results
    instances, needReview = analyzeFindingsInstances(cfg, prj, "COMBINED", slmJsonPath)

    # build review doc if needed
    reviewFilePath = os.path.join(reportFolder, reviewFilename)
    if needReview != [] and includeReview:
        with open(reviewFilePath, "w") as review_f:
            for catName, licName, fileName in needReview:
                review_f.write(f"{catName}: {licName}: {fileName}\n")
        print(f"{prj._name}: REVIEW file written to {reviewFilename}")
        reviewReportWrittenPath = reviewFilePath
    else:
        # delete review doc if there's an old one there
        if os.path.exists(reviewFilePath):
            os.remove(reviewFilePath)

    # if no instances, that's fine, we'll still want to create the report

    # get license summary data
    cats, totalCount, noLicThird, noLicEmpty, noLicExt, noLicRest = getLicenseSummaryDetails(cfg, slmJsonPath)

    # build template data fillers
    repoData = []
    for sp in prj._subprojects.values():
        for repoName, commit in sp._code_repos.items():
            rdTup = (repoName, commit[0:8])
            repoData.append(rdTup)
    repoData.sort(key=lambda tup: tup[0])

    findingData = []
    for inst in instances:
        fd = {
            "priorityShort": getShortPriorityString(inst._finding._priority),
            "priorityFull": getFullPriorityString(inst._finding._priority),
            "description": inst._finding._text,
            "numFiles": len(inst._files),
            "files": inst._files,
            "numSubprojects": len(inst._subprojects),
            "subprojects": inst._subprojects,
        }
        findingData.append(fd)

    renderData = {
        "prjName": prj._name,
        "spName": "(all subprojects)",
        "codeDate": cfg._month,
        "repoData": repoData,
        "findingData": findingData,
        "licenseSummary": {
            "cats": cats,
            "totalCount": totalCount,
            "noLicThird": noLicThird,
            "noLicEmpty": noLicEmpty,
            "noLicExt": noLicExt,
            "noLicRest": noLicRest,
        },
    }

    # and render it!
    tmpl = Template(tmplstr)
    renderedHtml = tmpl.render(renderData)

    # and write the results to disk
    with open(htmlPath, "w") as report_f:
        report_f.write(renderedHtml)

    if isDraft:
        print(f"{prj._name}: DRAFT findings written to {htmlFilename}")
    else:
        print(f"{prj._name}: FINAL findings written to {htmlFilename}")

    return htmlPath, reviewReportWrittenPath

# Runner for CREATEDREPORTS and MADEDRAFTFINDINGS for one subproject
def doMakeDraftFindingsIfNoneForSubproject(cfg, prj, sp):
    orig_status = sp._status
    # make sure we're at the right stage
    if sp._status != Status.CREATEDREPORTS and sp._status != Status.MADEDRAFTFINDINGS:
        print(f"{prj._name}/{sp._name}: status is {sp._status}, won't create draft findings now")
        return False

    # make findings report and the review file, if any
    findingsPath, _ = makeFindingsForSubproject(cfg, prj, sp, True, True)
    if findingsPath == "":
        # print(f"{prj._name}/{sp._name}: no draft findings report written")
        # only return false if it's the same as when we came in
        if orig_status == Status.MADEDRAFTFINDINGS:
            return False

    # once we get here, the draft findings report has been created, if there is one
    sp._status = Status.MADEDRAFTFINDINGS

    # and when we return, the runner framework should update the project's
    # status to reflect the min of its subprojects --
    # AFTER taking into account creating a combined report, if needed
    return True

# Runner for CREATEDREPORTS and MADEDRAFTFINDINGS for one project, overall
def doMakeDraftFindingsIfNoneForProject(cfg, prj):
    orig_status = prj._status
    # make sure we're at the right stage
    if prj._status != Status.CREATEDREPORTS and prj._status != Status.MADEDRAFTFINDINGS:
        print(f"{prj._name}: status is {prj._status}, won't create draft findings now")
        return False

    # make findings report and the review file, if any
    findingsPath, _ = makeFindingsForProject(cfg, prj, True, True)
    if findingsPath == "":
        # print(f"{prj._name}: no draft findings report written")
        # only return false if it's the same as when we came in
        if orig_status == Status.MADEDRAFTFINDINGS:
            return False

    # once we get here, the draft findings report has been created, if there is one
    prj._status = Status.MADEDRAFTFINDINGS

    # and when we return, the runner framework should update the project's
    # status to reflect the min of its subprojects --
    # AFTER taking into account creating a combined report, if needed
    return True

# Runner for APPROVEDFINDINGS for one subproject
def doMakeFinalFindingsForSubproject(cfg, prj, sp):
    orig_status = sp._status
    # make sure we're at the right stage
    if sp._status != Status.APPROVEDFINDINGS:
        print(f"{prj._name}/{sp._name}: status is {sp._status}, won't create final findings now")
        return False

    # make findings report and the review file, if any
    findingsPath, _ = makeFindingsForSubproject(cfg, prj, sp, False, True)
    if findingsPath == "":
        print(f"{prj._name}/{sp._name}: no final findings report written")
        # only return false if it's the same as when we came in
        # FIXME is this incorrect? since it needs to be APPROVEDFINDINGS
        # FIXME to get here?
        if orig_status == Status.MADEDRAFTFINDINGS:
            return False

    # once we get here, the final findings report has been created, if there is one
    sp._status = Status.MADEFINALFINDINGS

    # and when we return, the runner framework should update the project's
    # status to reflect the min of its subprojects --
    # AFTER taking into account creating a combined report, if needed
    return True

# Runner for APPROVEDFINDINGS for one project overall
def doMakeFinalFindingsForProject(cfg, prj):
    orig_status = prj._status
    # make sure we're at the right stage
    if prj._status != Status.APPROVEDFINDINGS:
        print(f"{prj._name}: status is {prj._status}, won't create final findings now")
        return False

    # make findings report and the review file, if any
    findingsPath, _ = makeFindingsForProject(cfg, prj, False, True)
    if findingsPath == "":
        print(f"{prj._name}: no final findings report written")
        # only return false if it's the same as when we came in
        # FIXME is this incorrect? since it needs to be APPROVEDFINDINGS
        # FIXME to get here?
        if orig_status == Status.MADEDRAFTFINDINGS:
            return False

    # once we get here, the final findings report has been created, if there is one
    prj._status = Status.MADEFINALFINDINGS

    # and when we return, the runner framework should update the project's
    # status to reflect the min of its subprojects --
    # AFTER taking into account creating a combined report, if needed
    return True
