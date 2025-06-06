#!/usr/bin/env python3
# Copyright (c) 2025, Arm Limited or its affiliates. All rights reserved.
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

import sys
import re
import json

def parse_post_script_log(log_path):
    """
    Parse lines from post-script.log, storing them as subtests.
    We also attempt to detect a final summary line of the form:
        INFO <module>:
        create a single Test Suite for the entire log.
    """

    with open(log_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Define a single test suite container (similar structure to FWTS parser)
    test_suite = {
        "Test_suite": "post scripts checks",
        "Test_suite_Description": "Post script checks from post-script.log",
        "subtests": [],
        "test_suite_summary": {
            "total_PASSED": 0,
            "total_FAILED": 0,
            "total_ABORTED": 0,
            "total_SKIPPED": 0,
            "total_WARNINGS": 0
        }
    }

    # We'll keep a running index for sub_Test_Number
    subtest_counter = 0

    # We can also keep track of whether we found a final summary line
    final_summary_found = False
    final_summary_passed = 0
    final_summary_failed = 0
    final_summary_warnings = 0
    # (We have no direct 'aborted' or 'skipped' from the final summary line, so those remain zero.)

    # Regex to detect the final summary line, e.g.:
    # INFO <module>:
    summary_regex = re.compile(
        r"INFO\s+<module>:\s+(\d+)\s+checks,\s+(\d+)\s+pass,\s+(\d+)\s+warnings?,\s+(\d+)\s+errors?"
    )

    # Helper function to create a subtest entry
    def make_subtest(line_num, severity, text_line):
        """
        Convert a single log line into a subtest entry with
        fields: sub_Test_Number, sub_Test_Description, sub_test_result, etc.
        """
        subtest = {
            "sub_Test_Number": str(line_num),
            "sub_Test_Description": text_line.strip(),
            "sub_test_result": {
                "PASSED": 0,
                "FAILED": 0,
                "ABORTED": 0,
                "SKIPPED": 0,
                "WARNINGS": 0
            }
        }
        # Attach reasons arrays only if needed
        if severity == "ERROR":
            subtest["sub_test_result"]["FAILED"] = 1
            subtest["sub_test_result"]["fail_reasons"] = ["N/A"]
        elif severity == "WARNING":
            subtest["sub_test_result"]["WARNINGS"] = 1
            subtest["sub_test_result"]["warning_reasons"] = ["N/A"]
        elif severity == "INFO":
            return None
        return subtest

    # Parse line by line
    for line in lines:
        line_stripped = line.strip()

        # Check for final summary line
        m = summary_regex.search(line)
        if m:
            final_summary_found = True
            total_checks = int(m.group(1))
            final_summary_passed = int(m.group(2))
            final_summary_warnings = int(m.group(3))
            final_summary_failed = int(m.group(4))
            # We do *not* store it as a subtest. It's purely a summary.
            continue

        # Identify severity based on prefix: "ERROR ", "WARNING ", "INFO "
        # We'll do a quick search. If no match, we skip or treat as INFO
        # Variation: you could also treat lines with no recognized prefix as "INFO"
        if line.startswith("ERROR"):
            subtest_counter += 1
            st = make_subtest(subtest_counter, "ERROR", line)
            if st is not None:
                test_suite["subtests"].append(st)
        elif line.startswith("WARNING"):
            subtest_counter += 1
            st = make_subtest(subtest_counter, "WARNING", line)
            if st is not None:
                test_suite["subtests"].append(st)
        elif line.startswith("INFO"):
            subtest = make_subtest(subtest_counter+1, "INFO", line)  # calls make_subtest
            # we do not increment subtest_counter or append if it returns None
        else:
            # parse lines that do not start with these tokens,skip them to keep the subtests clean
            pass

    # If found a final summary, override the suite's summary from that
    if final_summary_found:
        test_suite["test_suite_summary"]["total_PASSED"] = final_summary_passed
        test_suite["test_suite_summary"]["total_FAILED"] = final_summary_failed
        test_suite["test_suite_summary"]["total_WARNINGS"] = final_summary_warnings
        # ABORTED and SKIPPED remain 0 as we don't have them in the summary line

    # If we did NOT find a final summary, we can fallback to summing from subtests:
    else:
        # Summation approach in case there's no final summary line
        for sub in test_suite["subtests"]:
            r = sub["sub_test_result"]
            test_suite["test_suite_summary"]["total_PASSED"] += r["PASSED"]
            test_suite["test_suite_summary"]["total_FAILED"] += r["FAILED"]
            test_suite["test_suite_summary"]["total_ABORTED"] += r["ABORTED"]
            test_suite["test_suite_summary"]["total_SKIPPED"] += r["SKIPPED"]
            test_suite["test_suite_summary"]["total_WARNINGS"] += r["WARNINGS"]

    # Next, build the top-level "suite_summary" from this single test suite
    suite_summary = {
        "total_passed": test_suite["test_suite_summary"]["total_PASSED"],
        "total_failed": test_suite["test_suite_summary"]["total_FAILED"],
        "total_failed_with_waiver": 0,  # no logic for waivers here
        "total_aborted": test_suite["test_suite_summary"]["total_ABORTED"],
        "total_skipped": test_suite["test_suite_summary"]["total_SKIPPED"],
        "total_warnings": test_suite["test_suite_summary"]["total_WARNINGS"]
    }

    # Finally, return the final dictionary in the same style as FWTS parser
    return {
        "test_results": [test_suite],
        "suite_summary": suite_summary
    }

def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <path to post-script.log> <output JSON file path>")
        sys.exit(1)

    log_file_path = sys.argv[1]
    output_file_path = sys.argv[2]

    output_json = parse_post_script_log(log_file_path)
    with open(output_file_path, "w", encoding="utf-8") as outfile:
        json.dump(output_json, outfile, indent=4)

if __name__ == "__main__":
    main()
