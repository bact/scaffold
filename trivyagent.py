# Copyright The Linux Foundation
# SPDX-License-Identifier: Apache-2.0

import os
from subprocess import run, PIPE
import sys
import zipfile
import tempfile
import spdx.spdxutil
import spdx.xlsx
from uploadspdx import doUploadFileForSubproject
from spdx_tools.spdx.parser.error import SPDXParsingError
from pdb import set_trace

def runUnifiedAgent(cfg, prj, sp):
    # make sure that the code to upload actually exists!
    if not sp._code_path:
        print(f"{prj._name}/{sp._name}: No code path found; can not run Trivy")
        return False
    if not os.path.exists(sp._code_path):
        print(f"{prj._name}/{sp._name}: Nothing found at code path {sp._code_path}; can not run Trivy")
        return False
    if not os.path.isfile(sp._code_path):
        print(f"{prj._name}/{sp._name}: Code path {sp._code_path} exists but is not a file; can not run Trivy")
        return False
    with tempfile.TemporaryDirectory() as tempdir:
        # Unzip file to a temporary directory
        analysisdir = os.path.join(tempdir, "code")
        os.mkdir(analysisdir)
        with zipfile.ZipFile(sp._code_path, mode='r') as zip:
            zip.extractall(analysisdir)
        cmd = ["trivy", "fs", "--scanners", "license,vuln", "--format", "spdx-json", analysisdir]
        result = os.path.join(tempdir, f"{prj._name}-{sp._name}-trivy-spdx.json")
        with open(result, 'w') as outfile:
            cp = run(cmd, stdout=outfile, stderr=PIPE, universal_newlines=True, shell=True)
            if cp.returncode != 0:
                print(f"""{prj._name}/{sp._name}: Trivy failed with error code {cp.returncode}:
----------
output:
{cp.stdout}
----------
errors:
{cp.stderr}
----------
""")
                return False
        set_trace()
        try:
            spdxDocument = spdx.spdxutil.parseFile(result)
        except SPDXParsingError:
            print(f"{prj._name}/{sp._name}: unable to parse Trivy generated SPDX document")
            return False
        spdx.spdxutil.fixTrivyDocument(spdxDocument)
        uploadSpdxFileName = f"{prj._name}-{sp._name}-spdx.json"
        uploadSpdxFile = os.path.join(tempdir, uploadSpdxFileName)
        spdx.spdxutil.writeFile(spdxDocument, uploadSpdxFile)
        if not doUploadFileForSubproject(cfg, prj, sp, tempdir, uploadSpdxFileName):
            print(f"{prj._name}/{sp._name}: unable to upload SPDX dependencies file")
            return False
        workbook = spdx.xlsx.makeXlsx(spdxDocument)
        workbookFile = os.path.join(tempdir, f"{prj._name}-{sp._name}-dependencies.xlsx")
        spdx.xlsx.saveXlsx(workbook, workbookFile)
        _copyWorkbookToReportsFolder(workbookFile)
        print(f"{prj._name}/{sp._name}: Trivy successfully run")
        return True
        
    
def _copyWorkbookToReportsFolder(file):
    print("TODO: Implement copy workbook to reports folder")
    

