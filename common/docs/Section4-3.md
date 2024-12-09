
If you do not choose an option in the GRUB menu and do not skip any tests, the image runs the
ACS in the following order:

1. SCT tests
2. Debug dumps
3. BSA ACS
4. Linux boot
5. FWTS tests
6. BSA tests
7. DT validate tool
8. DT kernel Kselftest
9. Ethtool
10. block device check script
11. System will automatically reboots for capsule update testing
12. Capsule Update test
13. Linux boot

After these tests are executed, the control returns to a Linux prompt.
