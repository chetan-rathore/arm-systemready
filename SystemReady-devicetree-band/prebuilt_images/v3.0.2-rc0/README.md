
Due to github size constraint, the image is splitted into two parts.
After download use below command to join the image.

> cat systemready-dt_acs_live_image.wic.xz_a* > systemready-dt_acs_live_image.wic.xz 

Then extract using

> xz -d systemready-dt_acs_live_image.wic.xz 



Changes on top of 3.0.1 in current image

BSA
	- build process of linux acs updated to remove patch dependency
        - Skip disabled SMMU from parsing for DT system

SystemReady
	- ethttol test fixes
		- mismatch of string
		- wget command correction
		- add failed checks in log parser for ping checks
	- KV260 usb config added
	- capturing dmesg and syslog dump
	- secureboot fixes
		- Signed efi binaries which were missing signing
	- Sort all keys of result summary in merged json
	- Changes for HIIConfigRouting protocol
	- added sct device path in json/html
