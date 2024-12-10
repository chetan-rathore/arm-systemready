3.4.1 DT Kernel self-test

DT kernel self-test is integarted with ACS live image and is used for validating the devices described in the device tree have an associated drivers in OS. <br />
The ACS performs this test automatically.This section describes how to perform the test manually.

1. Move to /usr/kernel-selftest directory <br />
` cd /usr/kernel-selftest `

2. Run the kselftest script <br />
`./run_kselftest.sh -t dt:test_unprobed_devices.sh &> log`

