## Image Split and extract Instructions

Due to GitHub size constraints, the image is split into two parts.

After downloading, join the image using the following command:

```bash
cat systemready-dt_acs_live_image.wic.xz_a* > systemready-dt_acs_live_image.wic.xz
```

Then extract the full image using:

```bash
xz -d systemready-dt_acs_live_image.wic.xz
```

---

## Changes on Top of v3.0.1 in Current Image

###  BSA ACS

* Updated build process of Linux ACS to remove patch dependency.
* Skipped disabled SMMUs during parsing for DT systems.
* Source code moved to sysarch-acs from old repo bsa-acs

###  SystemReady ACS

* **`ethtool` Test Fixes**:

  * Fixed mismatch of expected strings.
  * Corrected `wget` command usage.
  * Added failed checks to log parser for ping test failures.
* Added USB configuration for **KV260** board.
* Capturing **`dmesg`** and **`syslog`** dumps during test runs.
* **Secure Boot Fixes**:

  * Signed EFI binaries that were previously missing signatures.
* Sorted all keys in the **result summary JSON**.
* Fixed for failure of **`HIIConfigRouting` protocol**.
* Added **SCT device path** in both JSON and HTML result outputs.

