#!/usr/bin/env python3
# Copyright (c) 2024, Arm Limited or its affiliates. All rights reserved.
# SPDX-License-Identifier : Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#!/usr/bin/env python3
import json
import sys
import re
import argparse
import os
import xml.etree.ElementTree as ET


def clean_description(desc):
    desc = desc.strip().lower()
    desc = re.sub(r'\s+', ' ', desc)  # Replace multiple spaces with a single space
    desc = re.sub(r'[^\w\s-]', '', desc)  # Remove special characters except hyphens
    return desc

### WAIVER LOADING (unchanged) ###
def load_waivers(waiver_data, suite_name):
    suite_level_waivers = []
    testsuite_level_waivers = []
    subsuite_level_waivers = []
    testcase_level_waivers = []
    subtest_level_waivers = []

    for suite in waiver_data.get('Suites', []):
        if suite.get('Suite') == suite_name:
            # Check for suite-level waiver
            if 'Reason' in suite and suite['Reason']:
                suite_level_waivers.append({'Reason': suite['Reason']})

            # Iterate through TestSuites
            for test_suite in suite.get('TestSuites', []):
                # Attempt to extract TestSuite name
                test_suite_name = test_suite.get('TestSuite')
                if not test_suite_name:
                    # If TestSuite is missing a name, fallback to looking for 'TestCase' or 'SubSuite'
                    test_case = test_suite.get('TestCase') or test_suite.get('SubSuite', {}).get('TestCase')
                    if isinstance(test_case, str):
                        test_suite_name = test_case
                    elif isinstance(test_case, dict):
                        test_suite_name = None

                # TestSuite-level
                if test_suite_name and 'Reason' in test_suite and test_suite['Reason']:
                    testsuite_level_waivers.append({'TestSuite': test_suite_name,
                                                    'Reason': test_suite['Reason']})

                # For SCT, standalone, BBSR-SCT, BBSR-FWTS
                if suite_name.upper() in ['SCT', 'STANDALONE', 'BBSR-SCT', 'BBSR-FWTS']:
                    # SubSuite-level
                    if 'SubSuite' in test_suite:
                        subsuite = test_suite['SubSuite']
                        if isinstance(subsuite, dict):
                            subsuite_name = subsuite.get('SubSuite')
                            reason = subsuite.get('Reason')
                            if subsuite_name and reason:
                                subsuite_level_waivers.append({'SubSuite': subsuite_name,
                                                               'Reason': reason})

                    # Test_case-level
                    if 'TestCase' in test_suite:
                        testcase = test_suite['TestCase']
                        if isinstance(testcase, dict):
                            testcase_name = testcase.get('Test_case')
                            reason = testcase.get('Reason')
                            if testcase_name and reason:
                                testcase_level_waivers.append({'Test_case': testcase_name,
                                                               'Reason': reason})

                # SubTest-level waivers
                subtests = test_suite.get('TestCase', {}).get('SubTests', []) \
                           or test_suite.get('SubSuite', {}).get('TestCase', {}).get('SubTests', [])
                for subtest in subtests:
                    if 'Reason' in subtest and subtest['Reason']:
                        subtest_level_waivers.append(subtest)
            break

    return (suite_level_waivers,
            testsuite_level_waivers,
            subsuite_level_waivers,
            testcase_level_waivers,
            subtest_level_waivers)

### JSON apply code (untouched) ###
def apply_suite_level_waivers(test_suite_entry, suite_waivers):
    for waiver in suite_waivers:
        reason = waiver['Reason']
        for subtest in test_suite_entry.get('subtests', []):
            sub_test_result = subtest.get('sub_test_result')
            if isinstance(sub_test_result, dict):
                if sub_test_result.get('FAILED', 0) > 0:
                    sub_test_result['FAILED'] -= 1
                    sub_test_result['FAILED_WITH_WAIVER'] = sub_test_result.get('FAILED_WITH_WAIVER', 0) + 1
                    sub_test_result['waiver_reason'] = reason
                    existing_fail_reasons = sub_test_result.get('fail_reasons', [])
                    updated_fail_reasons = [fr + ' (WITH WAIVER)' for fr in existing_fail_reasons]
                    sub_test_result['fail_reasons'] = updated_fail_reasons
            elif isinstance(sub_test_result, str):
                if 'FAILED' in sub_test_result.upper() or 'FAILURE' in sub_test_result.upper():
                    if '(WITH WAIVER)' not in sub_test_result.upper():
                        subtest['sub_test_result'] += ' (WITH WAIVER)'
                        subtest['waiver_reason'] = reason

def apply_testsuite_level_waivers(test_suite_entry, testsuite_waivers):
    test_suite_name = test_suite_entry.get('Test_suite') or test_suite_entry.get('Test_suite_name')
    for waiver in testsuite_waivers:
        target_testsuite = waiver['TestSuite']
        reason = waiver['Reason']
        if test_suite_name == target_testsuite:
            for subtest in test_suite_entry.get('subtests', []):
                sub_test_result = subtest.get('sub_test_result')
                if isinstance(sub_test_result, dict):
                    if sub_test_result.get('FAILED', 0) > 0:
                        sub_test_result['FAILED'] -= 1
                        sub_test_result['FAILED_WITH_WAIVER'] = sub_test_result.get('FAILED_WITH_WAIVER', 0) + 1
                        sub_test_result['waiver_reason'] = reason
                        existing_fail_reasons = sub_test_result.get('fail_reasons', [])
                        updated_fail_reasons = [fr + ' (WITH WAIVER)' for fr in existing_fail_reasons]
                        sub_test_result['fail_reasons'] = updated_fail_reasons
                elif isinstance(sub_test_result, str):
                    if 'FAILED' in sub_test_result.upper() or 'FAILURE' in sub_test_result.upper():
                        if '(WITH WAIVER)' not in sub_test_result.upper():
                            subtest['sub_test_result'] += ' (WITH WAIVER)'
                            subtest['waiver_reason'] = reason

def apply_subsuite_level_waivers(test_suite_entry, subsuite_waivers):
    for waiver in subsuite_waivers:
        target_subsuite = waiver['SubSuite']
        reason = waiver['Reason']
        if test_suite_entry.get('Sub_test_suite') == target_subsuite:
            for subtest in test_suite_entry.get('subtests', []):
                sub_test_result = subtest.get('sub_test_result')
                if isinstance(sub_test_result, dict):
                    if sub_test_result.get('FAILED', 0) > 0:
                        sub_test_result['FAILED'] -= 1
                        sub_test_result['FAILED_WITH_WAIVER'] = sub_test_result.get('FAILED_WITH_WAIVER', 0) + 1
                        sub_test_result['waiver_reason'] = reason
                        existing_fail_reasons = sub_test_result.get('fail_reasons', [])
                        updated_fail_reasons = [fr + ' (WITH WAIVER)' for fr in existing_fail_reasons]
                        sub_test_result['fail_reasons'] = updated_fail_reasons
                elif isinstance(sub_test_result, str):
                    if 'FAILED' in sub_test_result.upper() or 'FAILURE' in sub_test_result.upper():
                        if '(WITH WAIVER)' not in sub_test_result.upper():
                            subtest['sub_test_result'] += ' (WITH WAIVER)'
                            subtest['waiver_reason'] = reason

def apply_testcase_level_waivers(test_suite_entry, testcase_waivers):
    for waiver in testcase_waivers:
        target_testcase = waiver['Test_case']
        reason = waiver['Reason']
        if test_suite_entry.get('Test_case') == target_testcase:
            for subtest in test_suite_entry.get('subtests', []):
                sub_test_result = subtest.get('sub_test_result')
                if isinstance(sub_test_result, dict):
                    if sub_test_result.get('FAILED', 0) > 0:
                        sub_test_result['FAILED'] -= 1
                        sub_test_result['FAILED_WITH_WAIVER'] = sub_test_result.get('FAILED_WITH_WAIVER', 0) + 1
                        sub_test_result['waiver_reason'] = reason
                        existing_fail_reasons = sub_test_result.get('fail_reasons', [])
                        updated_fail_reasons = [fr + ' (WITH WAIVER)' for fr in existing_fail_reasons]
                        sub_test_result['fail_reasons'] = updated_fail_reasons
                elif isinstance(sub_test_result, str):
                    if 'FAILED' in sub_test_result.upper() or 'FAILURE' in sub_test_result.upper():
                        if '(WITH WAIVER)' not in sub_test_result.upper():
                            subtest['sub_test_result'] += ' (WITH WAIVER)'
                            subtest['waiver_reason'] = reason

def apply_subtest_level_waivers(test_suite_entry, subtest_waivers, suite_name):
    for subtest in test_suite_entry.get('subtests', []):
        sub_test_result = subtest.get('sub_test_result')

        if isinstance(sub_test_result, dict):
            # For FWTSResults.json, SCTResults.json, standalone JSON, etc.
            subtest_description = subtest.get('sub_Test_Description')
            for waiver in subtest_waivers:
                waiver_desc = waiver.get('sub_Test_Description')
                if waiver_desc:
                    if suite_name.upper() == 'STANDALONE':
                        if clean_description(waiver_desc) in clean_description(subtest_description):
                            failed = sub_test_result.get('FAILED', 0)
                            failed_with_waiver = sub_test_result.get('FAILED_WITH_WAIVER', 0)
                            if failed > 0:
                                sub_test_result['FAILED'] = failed - 1
                                sub_test_result['FAILED_WITH_WAIVER'] = failed_with_waiver + 1
                            else:
                                sub_test_result['FAILED_WITH_WAIVER'] = failed_with_waiver + 1
                            reason = waiver.get('Reason', '')
                            if reason:
                                sub_test_result['waiver_reason'] = reason
                                existing_fail_reasons = sub_test_result.get('fail_reasons', [])
                                updated_fail_reasons = [fr + ' (WITH WAIVER)' for fr in existing_fail_reasons]
                                sub_test_result['fail_reasons'] = updated_fail_reasons
                            break
                    else:
                        if clean_description(waiver_desc) == clean_description(subtest_description):
                            if 'FAILED (WITH WAIVER)' not in sub_test_result.get('fail_reasons', []):
                                failed = sub_test_result.get('FAILED', 0)
                                failed_with_waiver = sub_test_result.get('FAILED_WITH_WAIVER', 0)
                                if failed > 0:
                                    sub_test_result['FAILED'] = failed - 1
                                    sub_test_result['FAILED_WITH_WAIVER'] = failed_with_waiver + 1
                                reason = waiver.get('Reason', '')
                                if reason:
                                    sub_test_result['waiver_reason'] = reason
                                    existing_fail_reasons = sub_test_result.get('fail_reasons', [])
                                    updated_fail_reasons = [fr + ' (WITH WAIVER)' for fr in existing_fail_reasons]
                                    sub_test_result['fail_reasons'] = updated_fail_reasons
                            break

        elif isinstance(sub_test_result, str):
            # Possibly BSA/SBSA style
            if 'FAILED' not in sub_test_result.upper() and 'FAILURE' not in sub_test_result.upper():
                continue
            subtest_description = subtest.get('sub_Test_Description')
            subtest_number = subtest.get('sub_Test_Number')
            for waiver in subtest_waivers:
                waiver_desc = waiver.get('sub_Test_Description')
                waiver_id = waiver.get('SubTestID')
                if suite_name.upper() in ['FWTS', 'STANDALONE', 'BBSR-FWTS']:
                    if waiver_desc:
                        if clean_description(waiver_desc) in clean_description(subtest_description):
                            if '(WITH WAIVER)' not in sub_test_result.upper():
                                subtest['sub_test_result'] += ' (WITH WAIVER)'
                            reason = waiver.get('Reason', '')
                            if reason:
                                subtest['waiver_reason'] = reason
                            break
                else:
                    if waiver_id and waiver_id == subtest_number:
                        if '(WITH WAIVER)' not in sub_test_result.upper():
                            subtest['sub_test_result'] += ' (WITH WAIVER)'
                        reason = waiver.get('Reason', '')
                        if reason:
                            subtest['waiver_reason'] = reason
                        break
                    elif waiver_desc:
                        if clean_description(waiver_desc) == clean_description(subtest_description):
                            if '(WITH WAIVER)' not in sub_test_result.upper():
                                subtest['sub_test_result'] += ' (WITH WAIVER)'
                            reason = waiver.get('Reason', '')
                            if reason:
                                subtest['waiver_reason'] = reason
                            break

### NEW or CHANGED for XML SUPPORT ###

def apply_waivers_xml(suite_name, xml_file, waiver_data, test_category_data):
    """
    Minimal XML logic to replicate the JSON approach.
    Now extended to handle BOTH:
      A) The old <Suite>/<SubTest> style
      B) JUnit-style <testsuite>/<testcase><failure> style
    """

    if not os.path.isfile(xml_file):
        if verbose:
            print(f"XML file not found: {xml_file}")
        return

    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
    except Exception as e:
        if verbose:
            print(f"Failed to parse XML {xml_file}: {e}")
        return

    # 1) Extract waivers for this suite
    (suite_level_waivers,
     testsuite_level_waivers,
     subsuite_level_waivers,
     testcase_level_waivers,
     subtest_level_waivers) = load_waivers(waiver_data, suite_name)

    if not (suite_level_waivers or testsuite_level_waivers or subsuite_level_waivers or testcase_level_waivers or subtest_level_waivers):
        if verbose:
            print(f"No applicable waivers found for suite {suite_name} (XML).")
        return

    # We'll define a small helper to check if a test suite name is waivable:
    def is_waivable(test_suite_name):
        if test_category_data is None:
            return True
        for catID, catData in test_category_data.items():
            for suiteID, suiteData in catData.items():
                for sname_key, sname_value in suiteData.items():
                    if sname_key.startswith('SName:') and sname_key == f'SName: {suite_name}':
                        for ts_entry in sname_value:
                            if ts_entry.get('TSName', '').lower() == test_suite_name.lower():
                                if ts_entry.get('Waivable', '').lower() == 'yes':
                                    return True
        return False

    ######################################
    #  A) Old logic for <Suite>/<SubTest>
    ######################################
    for suite_el in root.findall(".//Suite"):
        suite_name_attr = suite_el.get("name", "")
        if not is_waivable(suite_name_attr):
            continue

        for subtest_el in suite_el.findall(".//SubTest"):
            result = subtest_el.get("result", "").upper()
            if "FAIL" in result:
                # If there's ANY relevant waiver, let's mark it as waived
                waived = False
                reason = ""

                # suite-level waivers => always apply
                if suite_level_waivers:
                    waived = True
                    reason = suite_level_waivers[0]['Reason']

                # testSuite-level
                for ts_wv in testsuite_level_waivers:
                    target_ts = ts_wv['TestSuite']
                    if suite_name_attr == target_ts:
                        waived = True
                        reason = ts_wv['Reason']
                        break

                # subtest-level check:
                sub_desc = subtest_el.get("description", "")
                sub_id   = subtest_el.get("id", "")
                for stw in subtest_level_waivers:
                    w_desc = stw.get("sub_Test_Description", "")
                    w_id   = stw.get("SubTestID", "")
                    if w_id and w_id == sub_id:
                        waived = True
                        reason = stw.get("Reason", "")
                        break
                    elif w_desc:
                        if clean_description(w_desc) in clean_description(sub_desc):
                            waived = True
                            reason = stw.get("Reason", "")
                            break

                if waived:
                    # Mark as "FAILED_WITH_WAIVER"
                    if result != "FAILED_WITH_WAIVER":
                        subtest_el.set("result", "FAILED_WITH_WAIVER")
                    if reason:
                        subtest_el.set("waiver_reason", reason)

    ####################################################
    #  B) NEW LOGIC for JUnit-style <testsuite>/<testcase>/<failure>
    ####################################################
    # We'll apply the same concept: if there's a <failure> element, it means "FAILED."
    # We then match it against suite-level, subtest-level waivers, etc.

    # For each <testsuite> in the XML
    for junit_ts in root.findall(".//testsuite"):
        junit_ts_name = junit_ts.get("name", "")
        # Check if waivable:
        if not is_waivable(junit_ts_name):
            continue

        # We'll apply suite-level if we have them
        suite_waived = False
        suite_reason = ""
        if suite_level_waivers:
            suite_waived = True
            suite_reason = suite_level_waivers[0].get("Reason", "")

        # For each <testcase>
        for testcase_el in junit_ts.findall("testcase"):
            # If there's a <failure>, that's a fail
            failure_el = testcase_el.find("failure")
            if failure_el is not None:
                # Mark waived if we have suite-level or testSuite-level or subtest-level waivers
                waived = False
                reason = ""

                # (a) suite-level?
                if suite_waived:
                    waived = True
                    reason = suite_reason

                # (b) testSuite-level waivers?
                for ts_wv in testsuite_level_waivers:
                    target_ts = ts_wv['TestSuite']
                    if junit_ts_name == target_ts:
                        waived = True
                        reason = ts_wv['Reason']
                        break

                # (c) subtest-level logic => parse subTestNumber from the "name" attribute, e.g. "[251]"
                testcase_name = testcase_el.get("name", "")
                # Attempt to parse out something like: "[251]" or "251"
                # This is up to you to adapt if you have a certain pattern:
                match = re.match(r"\[(\d+)\]", testcase_name)
                sub_id = match.group(1) if match else ""

                # Also check partial substring for subTestDescription
                for stw in subtest_level_waivers:
                    w_desc = stw.get("sub_Test_Description", "")
                    w_id   = stw.get("SubTestID", "")
                    # If we have an ID match
                    if w_id and w_id == sub_id:
                        waived = True
                        reason = stw.get("Reason", "")
                        break
                    elif w_desc:
                        # If test name or partial matches
                        if clean_description(w_desc) in clean_description(testcase_name):
                            waived = True
                            reason = stw.get("Reason", "")
                            break

                if waived:
                    # We can mark the <failure> message as "FAILED (WITH WAIVER)"
                    old_msg = failure_el.get("message", "")
                    if "(WITH WAIVER)" not in old_msg:
                        failure_el.set("message", old_msg + " (WITH WAIVER)")
                    # Optionally store the waiver reason
                    if reason:
                        testcase_el.set("waiver_reason", reason)

    # Finally, write the updated tree
    tree.write(xml_file, encoding='utf-8', xml_declaration=True)
    if verbose:
        print(f"XML waivers applied to {xml_file} for suite {suite_name}.")

### MAIN function that dispatches for JSON or XML ###
def apply_waivers(suite_name, json_or_xml_file, waiver_file='waiver.json', output_json_file=None):
    """
    This is your existing function that used to only do JSON. Now we do:
    1) If file ends with .json => original JSON logic
    2) If file ends with .xml  => new XML logic
    """

    file_lower = json_or_xml_file.lower()
    is_json = file_lower.endswith(".json")
    is_xml = file_lower.endswith(".xml")

    if not (is_json or is_xml):
        if verbose:
            print(f"ERROR: File must be .json or .xml => {json_or_xml_file}")
        return

    # If JSON => original code
    if is_json:
        # --- Original JSON Approach ---
        try:
            with open(json_or_xml_file, 'r') as f:
                json_data = json.load(f)
        except Exception as e:
            if verbose:
                print(f"WARNING: Failed to read or parse {json_or_xml_file}: {e}")
            return

        # Load waiver.json
        try:
            with open(waiver_file, 'r') as f:
                waiver_data = json.load(f)
        except Exception as e:
            if verbose:
                print(f"INFO: Failed to read or parse {waiver_file}: {e}")
            return

        # Load test_category.json if provided
        if output_json_file:  # Here "output_json_file" was originally your test_category argument
            try:
                with open(output_json_file, 'r') as f:
                    output_json_data = json.load(f)
            except Exception as e:
                if verbose:
                    print(f"WARNING: Failed to read or parse {output_json_file}: {e}")
                output_json_data = None
        else:
            output_json_data = None

        (suite_level_waivers,
         testsuite_level_waivers,
         subsuite_level_waivers,
         testcase_level_waivers,
         subtest_level_waivers) = load_waivers(waiver_data, suite_name)

        if not (suite_level_waivers or testsuite_level_waivers or 
                (suite_name.upper() in ['SCT', 'STANDALONE', 'BBSR-SCT', 'BBSR-FWTS'] and (subsuite_level_waivers or testcase_level_waivers)) or
                subtest_level_waivers):
            if verbose:
                print(f"No valid waivers found for suite '{suite_name}'. No changes applied.")
            return

        if 'test_results' in json_data:
            test_suite_entries = json_data['test_results']
        elif isinstance(json_data, list):
            test_suite_entries = json_data
        elif isinstance(json_data, dict):
            test_suite_entries = [json_data]
        else:
            if verbose:
                print(f"ERROR: Unexpected JSON data structure in {json_or_xml_file}")
            return

        for test_suite_entry in test_suite_entries:
            ts_name = test_suite_entry.get('Test_suite') or test_suite_entry.get('Test_suite_name')
            if not ts_name:
                continue

            # Check if waivable
            if output_json_data is None:
                waivable = True
            else:
                waivable = False
                for catID, catData in output_json_data.items():
                    for sID, sData in catData.items():
                        for sname_key, sname_value in sData.items():
                            if sname_key.startswith('SName:') and sname_key == f'SName: {suite_name}':
                                ts_list = sname_value
                                for ts_entry in ts_list:
                                    if ts_entry.get('TSName','').lower() == ts_name.lower():
                                        if ts_entry.get('Waivable','').lower() == 'yes':
                                            waivable = True
                                            break
                                if waivable: break
                        if waivable: break
                    if waivable: break
            if not waivable:
                continue

            # Apply suite-level
            if suite_level_waivers:
                apply_suite_level_waivers(test_suite_entry, suite_level_waivers)
            # Apply testSuite-level
            if testsuite_level_waivers:
                apply_testsuite_level_waivers(test_suite_entry, testsuite_level_waivers)
            # If sct / standalone / bbsr
            if suite_name.upper() in ['SCT', 'STANDALONE', 'BBSR-SCT', 'BBSR-FWTS']:
                if subsuite_level_waivers:
                    apply_subsuite_level_waivers(test_suite_entry, subsuite_level_waivers)
                if testcase_level_waivers:
                    apply_testcase_level_waivers(test_suite_entry, testcase_level_waivers)
            # Subtest-level
            if subtest_level_waivers:
                apply_subtest_level_waivers(test_suite_entry, subtest_level_waivers, suite_name)

            # Re-calc summary
            if suite_name.upper() in ['SCT', 'BBSR-SCT']:
                summary_field = 'test_case_summary'
            elif suite_name.upper() == 'STANDALONE':
                summary_field = 'test_suite_summary'
            else:
                summary_field = 'test_suite_summary'

            if summary_field in test_suite_entry:
                total_passed = 0
                total_failed = 0
                total_failed_with_waiver = 0
                total_aborted = 0
                total_skipped = 0
                total_warnings = 0

                for subtest in test_suite_entry.get('subtests', []):
                    sub_test_result = subtest.get('sub_test_result')
                    if isinstance(sub_test_result, dict):
                        total_passed += sub_test_result.get('PASSED', 0)
                        f1 = sub_test_result.get('FAILED', 0)
                        f2 = sub_test_result.get('FAILED_WITH_WAIVER', 0)
                        total_failed += (f1 + f2)
                        total_failed_with_waiver += f2
                        total_aborted += sub_test_result.get('ABORTED', 0)
                        total_skipped += sub_test_result.get('SKIPPED', 0)
                        total_warnings += sub_test_result.get('WARNINGS', 0)
                    elif isinstance(sub_test_result, str):
                        if 'PASS' in sub_test_result.upper():
                            total_passed += 1
                        if 'FAILED' in sub_test_result.upper() or 'FAILURE' in sub_test_result.upper():
                            total_failed += 1
                            if '(WITH WAIVER)' in sub_test_result.upper():
                                total_failed_with_waiver += 1
                        if 'SKIPPED' in sub_test_result.upper():
                            total_skipped += 1
                        if 'WARNING' in sub_test_result.upper():
                            total_warnings += 1

                test_suite_entry[summary_field] = {
                    'total_passed': total_passed,
                    'total_failed': total_failed,
                    'total_failed_with_waiver': total_failed_with_waiver,
                    'total_aborted': total_aborted,
                    'total_skipped': total_skipped,
                    'total_warnings': total_warnings
                }

        try:
            with open(json_or_xml_file, 'w') as f:
                json.dump(json_data, f, indent=4)
            print(f"Waivers successfully applied and '{json_or_xml_file}' has been updated.")
        except Exception as e:
            if verbose:
                print(f"ERROR: Failed to write updated data to {json_or_xml_file}: {e}")
        return

    # If XML => new logic
    if is_xml:
        # Load waiver data
        waiver_data = {}
        if os.path.isfile(waiver_file):
            try:
                with open(waiver_file, 'r') as wf:
                    waiver_data = json.load(wf)
            except Exception as e:
                if verbose:
                    print(f"Failed to load waiver JSON {waiver_file}: {e}")
        else:
            if verbose:
                print(f"Waiver file not found: {waiver_file}")

        # Load test_category.json if provided (output_json_file param in your script)
        test_category_data = None
        if output_json_file and os.path.isfile(output_json_file):
            try:
                with open(output_json_file, 'r') as cf:
                    test_category_data = json.load(cf)
            except Exception as e:
                if verbose:
                    print(f"Failed to parse test_category file {output_json_file}: {e}")

        apply_waivers_xml(suite_name, json_or_xml_file, waiver_data, test_category_data)

def main():
    parser = argparse.ArgumentParser(description='Apply waivers to test suite JSON or XML results.')
    parser.add_argument('suite_name', help='Name of the test suite')
    parser.add_argument('json_file', help='Path to the JSON or XML file')
    parser.add_argument('waiver_file', nargs='?', default='waiver.json', help='Path to the waiver file (default: waiver.json)')
    parser.add_argument('output_json_file', nargs='?', default=None,
                        help='Path to the test category file (default: None) - for JSON or XML waivability checks')
    parser.add_argument('--quiet', action='store_true', help='Suppress detailed output')
    args = parser.parse_args()

    global verbose
    verbose = not args.quiet

    apply_waivers(args.suite_name, args.json_file, args.waiver_file, args.output_json_file)

if __name__ == '__main__':
    main()
