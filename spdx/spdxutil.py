# Copyright The Linux Foundation
# SPDX-License-Identifier: Apache-2.0

# Utility class to support merging / fixing up SPDX documents

from license_expression import get_spdx_licensing
from spdx_tools.spdx.model.document import Document
from spdx_tools.spdx.model.package import Package
from spdx_tools.spdx.model.package import ExternalPackageRef
from spdx_tools.spdx.model.package import ExternalPackageRefCategory
from spdx_tools.spdx.model.package import PackagePurpose
from spdx_tools.spdx.model.actor import Actor
from spdx_tools.spdx.model.actor import ActorType
from spdx_tools.spdx.model.relationship import Relationship
from spdx_tools.spdx.model.relationship import RelationshipType
from spdx_tools.spdx.model import SpdxNoAssertion
from spdx_tools.spdx.parser.error import SPDXParsingError
from spdx_tools.spdx.parser.parse_anything import parse_file
from spdx_tools.spdx.writer.write_anything import write_file
import spdx_tools.spdx.document_utils as document_utils
import spdx_tools.spdx.spdx_element_utils as spdx_element_utils
from datatypes import ProjectRepoType
import re

import pdb

'''
Parses an SPDX file with a supported file extension
Raises SPDXParsingError on parsing errors
'''
def parseFile(file):
    return parse_file(file)

'''
wrties an SPDX document to a file in the format dictated by the file extension
'''
def writeFile(spdx_document, file):
    write_file(spdx_document, file, validate=False)
    print("SPDX sucessfully written")
    
def augmentTrivyDocument(spdx_document, cfg, prj, sp):
    licensing = get_spdx_licensing()
    # find the root of the document
    describes = None
    for relationship in spdx_document.relationships:
        if relationship.relationship_type == RelationshipType.DESCRIBES and relationship.spdx_element_id == 'SPDXRef-DOCUMENT' and \
                spdx_element_utils.get_element_type_from_spdx_id(relationship.related_spdx_element_id, spdx_document) == Package:
            describes = document_utils.get_element_from_spdx_id(spdx_document, relationship.related_spdx_element_id)
    if describes == None:
        print("No document describes, trivy document not augumented")
        return False
    # Set the name to the "project.subproject"
    describes.name = prj._name + "." + sp._name
    # set the version to the date the analysis was run
    describes.version = cfg._month
    # Collect the project licenses and set the project license to the AND of all project licenses
    project_licenses = []
    for policy in prj._slm_policies.values():
        for category in policy._category_configs:
            if category._name == "Project Licenses":
                for licenseconfig in category._license_configs: 
                    project_licenses.append(licenseconfig._name)
    project_license = licenseIdsToExpression(project_licenses, licensing)
    describes.license_declared = project_license
    describes.license_concluded = project_license
    # Add a level under root for each of the repos
    repo_packages = {}
    for repo in sp._repos:
        repo_licenses = []
        if sp._slm_policy_name in prj._slm_policies:
            for category in prj._slm_policies[sp._slm_policy_name]._category_configs:
                if category._name == "Project Licenses":
                    for licenseconfig in category._license_configs: 
                        repo_licenses.append(licenseconfig._name)
        repo_license = licenseIdsToExpression(repo_licenses, licensing)
        
        name = repo
        fileAnalyzed = False
        if sp._repotype == ProjectRepoType.GITHUB:
            locator = 'pkg:github/' + sp._github_org + '/' + repo + '@' + sp._code_repos[repo]
            purl = ExternalPackageRef(category=ExternalPackageRefCategory.PACKAGE_MANAGER, reference_type='purl', locator=locator)
            # https://github.com/lfscanning/scaffold/archive/7ef25b63f44cb3a68cd60a3c26532e13853917a2.zip
            download_location = 'https://github.com/' + sp._github_org + '/' + repo + '/archive/' + sp._code_repos[repo] + '.zip'
            external_references = [purl]
        elif sp._repotype == ProjectRepoType.GITHUB_SHARED:
            locator = 'pkg:github/' + prj._github_shared_org + '/' + repo + '@' + sp._code_repos[repo]
            purl = ExternalPackageRef(category=ExternalPackageRefCategory.PACKAGE_MANAGER, reference_type='purl', locator=locator)
            # https://github.com/lfscanning/scaffold/archive/7ef25b63f44cb3a68cd60a3c26532e13853917a2.zip
            download_location = 'https://github.com/' + prj._github_shared_org + '/' + repo + '/archive/' + sp._code_repos[repo] + '.zip'
            external_references = [purl]
        # else if sp._repotype == ProjectRepoType.GERRIT:
            # https://gerrit.onap.org/r/aai/aai-common
            # git clone "https://gerrit.onap.org/r/aai"
        else:
            download_location = NoAssertion
            external_references = []
        version = sp._code_repos[repo]
        spdx_id = toSpdxRef(prj._name + "-" + sp._name + '-' + repo)
        supplier = Actor(actor_type = ActorType.ORGANIZATION, name = 'Linux Foundation Project ' + prj._name)
        source_info = 'The source this package was part of the LF Scanning configuration for the project ' + prj._name
        comment = 'This package was added to the Trivy analysis for the ' + name + ' by the Scaffold tool SBOM augmentation'
        repo_packages[repo] = Package(spdx_id = spdx_id, name = repo, download_location = download_location, version = version, supplier = supplier, \
                                        files_analyzed = False, source_info = source_info, license_concluded = licensing.parse('NOASSERTION'), \
                                        license_declared = repo_license, comment = comment, external_references = external_references, \
                                        primary_package_purpose = PackagePurpose.SOURCE)
        spdx_document.packages.append(repo_packages[repo])
        # add a contains relationship from the root to this package
        spdx_document.relationships.append(Relationship(spdx_element_id=describes.spdx_id, relationship_type=RelationshipType.CONTAINS, related_spdx_element_id=spdx_id))
    # move all the existing described relationships to their appropriate described fields
    for relationship in spdx_document.relationships:
        if relationship.spdx_element_id == describes.spdx_id:
            related_element = document_utils.get_element_from_spdx_id(spdx_document, relationship.related_spdx_element_id)
            repo = findRepoName(related_element, sp._repos)
            if repo:
                relationship.spdx_element_id = repo_packages[repo].spdx_id

    #
    # Fix up the creation info to add scaffold as a tool and Linux Foundation as an organization
    # Change the NONES to NOASSERTION for licenses and download locations
    # Change any license IDs in expressions to LicenseRef's
    # Change attribution text to annotations
    
    print("Trivy document augmented")
    return True
    
def toSpdxRef(identifier):
    return 'SPDXRef-' + re.sub(r'[^0-9a-zA-Z\.\-\+]+', '-', identifier)
    
def findRepoName(element, repos):
    if element == None:
        pdb.set_trace()
        return None
    for repo in repos:
        if element.name.startswith(repo + "/"):
            return repo
        if hasattr(element, 'source_info') and hasattr(element.source_info, 'startswith') and element.source_info.startswith("package found in: "+repo+"/"):
            return repo
    return None

def licenseIdsToExpression(licenseIds, licensing):
    if licenseIds:
        licstr = licenseIds[0]
        for i in range(1, len(licenseIds)-1):
            licstr = licstr + " AND " + licenseIds[i]
        return licensing.parse(licstr)
    else:
        return licensing.parse('NOASSERTION')
        