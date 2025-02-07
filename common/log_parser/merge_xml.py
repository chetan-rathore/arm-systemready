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

import xml.etree.ElementTree as ET
import argparse
import os
import subprocess
import re
from datetime import datetime

#############################################
# SYSTEM INFO / CONFIG FUNCTIONS (unchanged)
#############################################

def get_system_info():
    system_info = {}
    # Vendor
    try:
        vendor_output = subprocess.check_output(
            ["dmidecode", "-t", "system"],
            universal_newlines=True,
            stderr=subprocess.DEVNULL
        )
        for line in vendor_output.split('\n'):
            if 'Manufacturer:' in line:
                system_info['Vendor'] = line.split('Manufacturer:')[1].strip()
                break
    except Exception:
        system_info['Vendor'] = 'Unknown'

    # System
    try:
        system_name_output = subprocess.check_output(
            ["dmidecode", "-t", "system"],
            universal_newlines=True,
            stderr=subprocess.DEVNULL
        )
        for line in system_name_output.split('\n'):
            if 'Product Name:' in line:
                system_info['System'] = line.split('Product Name:')[1].strip()
                break
    except Exception:
        system_info['System'] = 'Unknown'

    # SoC Family
    try:
        soc_output = subprocess.check_output(
            "sudo dmidecode -t system | grep -i 'Family'",
            shell=True,
            universal_newlines=True,
            stderr=subprocess.DEVNULL
        )
        if 'Family:' in soc_output:
            system_info['SoC Family'] = soc_output.split('Family:')[1].strip()
        else:
            system_info['SoC Family'] = 'Unknown'
    except Exception:
        system_info['SoC Family'] = 'Unknown'

    # Firmware Version
    try:
        fw_output = subprocess.check_output(
            ["dmidecode", "-t", "bios"],
            universal_newlines=True,
            stderr=subprocess.DEVNULL
        )
        for line in fw_output.split('\n'):
            if 'Version:' in line:
                system_info['Firmware Version'] = line.split('Version:')[1].strip()
                break
    except Exception:
        system_info['Firmware Version'] = 'Unknown'

    # Timestamp
    system_info['Summary Generated On'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # UEFI Version (if available)
    try:
        # Change encoding if necessary
        with open("dummy", "r"): pass  # placeholder if needed
    except Exception:
        pass
    return system_info

def parse_config(config_path):
    info = {}
    if config_path and os.path.isfile(config_path):
        try:
            with open(config_path, 'r') as cf:
                for line in cf:
                    if ':' in line:
                        k, v = line.strip().split(':', 1)
                        info[k.strip()] = v.strip()
        except Exception as e:
            print(f"Warning reading {config_path}: {e}")
    return info

def get_uefi_version(uefi_version_log):
    if uefi_version_log and os.path.isfile(uefi_version_log):
        try:
            with open(uefi_version_log, 'r', encoding='utf-16') as f:
                for line in f:
                    if 'UEFI v' in line:
                        return line.strip()
        except Exception as e:
            print(f"Warning: reading {uefi_version_log}: {e}")
    return 'Unknown'

#############################################
# XML MERGE HELPERS
#############################################

def create_text_element(parent, tag, text):
    el = ET.SubElement(parent, tag)
    el.text = text
    return el

def reformat_xml(xml_path):
    # No-op; you can add pretty-printing if desired.
    pass

#############################################
# Parsing JUnit Stats from a suite XML
#############################################

def parse_junit_stats(file_root):
    """
    Returns a dict with statistics from JUnit-style <testsuite> elements:
      {
        "total_passed": X,
        "total_failed": Y,
        "total_failed_with_waiver": Z,
        "total_errors": E,
        "total_skipped": S,
      }
    Note: "total_failed_with_waiver" is incremented when a <failure> element's
    message attribute contains "(WITH WAIVER)". (This logic is kept simple for now.)
    """
    testsuite_els = []
    if file_root.tag.lower() == "testsuites":
        testsuite_els = file_root.findall("testsuite")
    elif file_root.tag.lower() == "testsuite":
        testsuite_els = [file_root]
    else:
        testsuite_els = file_root.findall(".//testsuite")

    total_passed   = 0
    total_failed   = 0
    total_failed_waived = 0
    total_errors   = 0
    total_skipped  = 0

    for ts in testsuite_els:
        tests_str    = ts.get("tests", "0")
        fails_str    = ts.get("failures", "0")
        errors_str   = ts.get("errors", "0")
        skipped_str  = ts.get("skipped", "0")

        try:
            t_tests   = int(tests_str)
            t_fails   = int(fails_str)
            t_errors  = int(errors_str)
            t_skipped = int(skipped_str)
        except ValueError:
            t_tests = t_fails = t_errors = t_skipped = 0

        total_failed += t_fails
        total_errors += t_errors
        total_skipped += t_skipped

        passed_calc = t_tests - t_fails - t_errors - t_skipped
        if passed_calc < 0:
            passed_calc = 0
        total_passed += passed_calc

        for fe in ts.findall(".//failure"):
            msg = fe.get("message", "").upper()
            if "(WITH WAIVER)" in msg:
                total_failed_waived += 1

    return {
        "total_passed": total_passed,
        "total_failed": total_failed,
        "total_failed_with_waiver": total_failed_waived,
        "total_errors": total_errors,
        "total_skipped": total_skipped
    }

#############################################
# Compliance Determination Functions
#############################################

def determine_compliance_for_suite(stats):
    """
    Given stats for a single suite, return:
      "Compliant", "Compliant with Waivers", or "Not compliant".
    """
    f  = stats["total_failed"]
    fw = stats["total_failed_with_waiver"]

    if f == 0:
        return "Compliant"
    else:
        if f == fw:
            return "Compliant with Waivers"
        else:
            return "Not compliant"

def determine_overall_compliance(suite_stats_map):
    """
    Given a dictionary mapping suite names to their stats,
    determine overall compliance across all suites.
    """
    all_failed_zero = True
    any_waivers_used = False
    any_unwaived_fails = False

    for sname, stats in suite_stats_map.items():
        f  = stats["total_failed"]
        fw = stats["total_failed_with_waiver"]
        if f > 0:
            all_failed_zero = False
        if fw > 0:
            any_waivers_used = True
        if f != fw:
            any_unwaived_fails = True

    if all_failed_zero:
        return "Compliant"
    else:
        if not any_unwaived_fails and any_waivers_used:
            return "Compliant with Waivers"
        else:
            return "Not compliant"

#############################################
# Main Merge Function
#############################################

def merge_xml_files(xml_files, output_file, acs_config_path=None, system_config_path=None, uefi_version_log=None):
    """
    1) Gather system info and acs config info.
    2) Build <MergedResults> with:
         <SystemInfo> ... </SystemInfo>
         <ACSResultsSummary> containing:
             <Band>, <Date>, plus per-suite compliance lines and overall compliance.
    3) For each suite XML file:
         - Parse it.
         - Determine suite name.
         - Compute suite statistics using parse_junit_stats.
         - Append a <Suite name="..."> element (with original content) to <MergedResults>.
         - (Optionally, you may also add per-suite summary info inside each <Suite>.)
    4) Inside <ACSResultsSummary>, add per-suite compliance lines and overall compliance.
    """

    # Step 1: Gather system info and config info
    sys_info = get_system_info()
    acs_conf = parse_config(acs_config_path) if acs_config_path else {}
    sys_conf = parse_config(system_config_path) if system_config_path else {}
    for k, v in sys_conf.items():
        sys_info[k] = v
    uefi_ver = get_uefi_version(uefi_version_log)
    if uefi_ver != 'Unknown':
        sys_info['UEFI_Version'] = uefi_ver

    # Create root and add system info
    root = ET.Element("MergedResults")
    sys_el = ET.SubElement(root, "SystemInfo")
    for k, v in sys_info.items():
        tagname = k.replace(" ", "_").replace(":", "_")
        create_text_element(sys_el, tagname, str(v))

    # Create ACSResultsSummary block and add fixed info from acs config if available
    summary_el = ET.SubElement(root, "ACSResultsSummary")
    band = acs_conf.get("Band", "Unknown") if acs_conf else "Unknown"
    date_val = sys_info.get("Summary_Generated_On", "Unknown")
    create_text_element(summary_el, "Band", band)
    create_text_element(summary_el, "Date", date_val)
    # We'll add suite compliance lines and overall compliance below

    # Dictionary to collect stats for each suite
    suite_stats_map = {}

    # Process each suite XML file
    for xml_path in xml_files:
        if not os.path.isfile(xml_path):
            print(f"Warning: {xml_path} not found, skipping.")
            continue
        reformat_xml(xml_path)
        try:
            tree = ET.parse(xml_path)
            file_root = tree.getroot()
        except Exception as e:
            print(f"Warning: parse error in {xml_path}: {e}")
            continue

        # Derive suite name from filename
        fn = os.path.basename(xml_path).upper()
        if "BSA" in fn and "SBSA" not in fn:
            suite_name = "BSA"
        elif "SBSA" in fn:
            suite_name = "SBSA"
        elif "BBSR-FWTS" in fn:
            suite_name = "BBSR-FWTS"
        elif "BBSR-SCT" in fn:
            suite_name = "BBSR-SCT"
        elif "FWTS" in fn:
            suite_name = "FWTS"
        elif "SCT" in fn:
            suite_name = "SCT"
        elif "CAPSULE_UPDATE" in fn:
            suite_name = "CAPSULE_UPDATE"
        elif "DT_KSELFTEST" in fn:
            suite_name = "DT_KSELFTEST"
        elif "DT_VALIDATE" in fn:
            suite_name = "DT_VALIDATE"
        elif "ETHTOOL_TEST" in fn:
            suite_name = "ETHTOOL_TEST"
        elif "READ_WRITE_CHECK_BLK_DEVICES" in fn:
            suite_name = "READ_WRITE_CHECK_BLK_DEVICES"
        else:
            suite_name = "Unknown"

        # Parse statistics from the XML
        stats = parse_junit_stats(file_root)
        suite_stats_map[suite_name] = stats

        # Create a <Suite name="..."> element and append the file's children
        suite_el = ET.SubElement(root, "Suite")
        suite_el.set("name", suite_name)
        for child in file_root:
            suite_el.append(child)
        
        # (Optional: Append per-suite summary inside the suite)
        suite_summary_el = ET.SubElement(suite_el, "SuiteSummary")
        create_text_element(suite_summary_el, "total_passed", str(stats["total_passed"]))
        create_text_element(suite_summary_el, "total_failed", str(stats["total_failed"]))
        create_text_element(suite_summary_el, "total_failed_with_waiver", str(stats["total_failed_with_waiver"]))
        create_text_element(suite_summary_el, "total_errors", str(stats["total_errors"]))
        create_text_element(suite_summary_el, "total_skipped", str(stats["total_skipped"]))
        # Also add suite compliance inside the suite (if desired)
        comp_val = determine_compliance_for_suite(stats)
        comp_el = ET.SubElement(suite_el, "SuiteCompliance")
        comp_el.text = comp_val

    # Now add per-suite compliance lines inside ACSResultsSummary
    for suite_name, stats in suite_stats_map.items():
        comp_val = determine_compliance_for_suite(stats)
        comp_el = ET.SubElement(summary_el, "Suite_Compliance")
        # Use an attribute to indicate the suite (we avoid colons in tag names)
        comp_el.set("name", f"{suite_name}_compliance")
        comp_el.text = comp_val

    # Finally, overall compliance
    overall_val = determine_overall_compliance(suite_stats_map)
    overall_el = ET.SubElement(summary_el, "OverallComplianceResult")
    overall_el.text = overall_val

    # Write final merged XML to output_file
    ET.ElementTree(root).write(output_file, encoding='utf-8', xml_declaration=True)

def main():
    parser = argparse.ArgumentParser(
        description="Merge multiple JUnit-style XML suite files into one MergedResults file with system info, ACSResultsSummary, per-suite summary/compliance, and overall compliance."
    )
    parser.add_argument("output_file", help="Output merged XML file")
    parser.add_argument("xml_files", nargs='+', help="List of suite XML files to merge")
    parser.add_argument("--acs_config_path", help="Path to acs_config.txt (for Band)", default=None)
    parser.add_argument("--system_config_path", help="Path to system_config.txt", default=None)
    parser.add_argument("--uefi_version_log", help="Path to uefi_version.log", default=None)

    args = parser.parse_args()

    merge_xml_files(
        xml_files=args.xml_files,
        output_file=args.output_file,
        acs_config_path=args.acs_config_path,
        system_config_path=args.system_config_path,
        uefi_version_log=args.uefi_version_log
    )

if __name__ == "__main__":
    main()
