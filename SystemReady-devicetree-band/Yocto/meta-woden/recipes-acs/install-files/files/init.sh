#!/bin/sh

# Copyright (c) 2023-2024, Arm Limited or its affiliates. All rights reserved.
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

echo "init.sh"

echo "Mounting efivarfs ..."
mount -t efivarfs efivarfs /sys/firmware/efi/efivars

sleep 5

#Skip running of ACS Tests if the grub option is added
ADDITIONAL_CMD_OPTION="";
ADDITIONAL_CMD_OPTION=`cat /proc/cmdline | awk '{ print $NF}'`

if [ $ADDITIONAL_CMD_OPTION != "noacs" ]; then
  echo "Attempting to mount the results partition ..." 
  #mount result partition
  BLOCK_DEVICE_NAME=$(blkid | grep "BOOT_ACS" | awk -F: '{print $1}')

  if [ ! -z "$BLOCK_DEVICE_NAME" ]; then
    mount $BLOCK_DEVICE_NAME /mnt
    echo "Mounted the results partition on device $BLOCK_DEVICE_NAME"
  else
    echo "Warning: the results partition could not be mounted. Logs may not be saved correctly"
  fi
  sleep 3
 
  SECURE_BOOT="";
  SECURE_BOOT=`cat /proc/cmdline | awk '{ print $NF}'`
 
  if [ $SECURE_BOOT = "secureboot" ]; then
    echo "Call BBSR ACS in Linux"
    /usr/bin/secure_init.sh
    echo "BBSR ACS run is completed\n"
    echo "Please press <Enter> to continue ..."
    echo -e -n "\n"
    exit 0
  fi

  if [ -f /mnt/yocto_image.flag ] && [ ! -f /mnt/acs_tests/app/capsule_update_check.flag ]; then
    check_flag=0
    if [ -f /mnt/acs_tests/app/capsule_update_done.flag ] || [ -f /mnt/acs_tests/app/capsule_update_ignore.flag ] || [ -f /mnt/acs_tests/app/capsule_update_unsupport.flag ]; then
      check_flag=1
    fi

    if [ $check_flag -eq 0 ]; then
      touch /mnt/acs_tests/app/capsule_update_check.flag

      #linux debug dump

      LINUX_DUMP_DIR="/mnt/acs_results/linux_dump"
      mkdir -p $LINUX_DUMP_DIR
      lspci -vvv &> $LINUX_DUMP_DIR/lspci.log
      lsusb    > $LINUX_DUMP_DIR/lsusb.log
      uname -a > $LINUX_DUMP_DIR/uname.log
      cat /proc/interrupts > $LINUX_DUMP_DIR/interrupts.log
      cat /proc/cpuinfo    > $LINUX_DUMP_DIR/cpuinfo.log
      cat /proc/meminfo    > $LINUX_DUMP_DIR/meminfo.log
      cat /proc/iomem      > $LINUX_DUMP_DIR/iomem.log
      ls -lR /sys/firmware > $LINUX_DUMP_DIR/firmware.log
      cp -r /sys/firmware $LINUX_DUMP_DIR/
      dmidecode  > $LINUX_DUMP_DIR/dmidecode.log
      efibootmgr > $LINUX_DUMP_DIR/efibootmgr.log
      fwupdmgr get-devices          &> $LINUX_DUMP_DIR/fwupd_getdevices.log
      echo "0" | fwupdtool esp-list &> $LINUX_DUMP_DIR/fwupd_esplist.log
      fwupdmgr get-bios-settings    &> $LINUX_DUMP_DIR/fwupd_bios_setting.log
      fwupdmgr get-history          &> $LINUX_DUMP_DIR/fwupd_get_history.log
      sync /mnt

      mkdir -p /mnt/acs_results/fwts
      echo "Executing FWTS for EBBR"
      test_list=`cat /usr/bin/ir_bbr_fwts_tests.ini | grep -v "^#" | awk '{print $1}' | xargs`
      echo "Test Executed are $test_list"
      echo "SystemReady devicetree band ACS v3.0.0" > /mnt/acs_results/fwts/FWTSResults.log
      /usr/bin/fwts --ebbr `echo $test_list` -r stdout >> /mnt/acs_results/fwts/FWTSResults.log
      echo -e -n "\n"
 
      #run linux bsa app
      mkdir -p /mnt/acs_results/linux_acs/bsa_acs_app
      echo "Loading BSA ACS Linux Driver"
      insmod /lib/modules/*/kernel/bsa_acs/bsa_acs.ko
      echo "Executing BSA ACS Application "
      echo "SystemReady devicetree band ACS v3.0.0" > /mnt/acs_results/linux_acs/bsa_acs_app/BSALinuxResults.log
      bsa >> /mnt/acs_results/linux_acs/bsa_acs_app/BSALinuxResults.log
      dmesg | sed -n 'H; /PE_INFO/h; ${g;p;}' > /mnt/acs_results/linux_acs/bsa_acs_app/BsaResultsKernel.log
      sync /mnt 
      sleep 3
 
      mkdir -p /home/root/fdt
      mkdir -p /mnt/acs_results/linux_tools
      # Device Driver Info script 
      pushd /usr/bin
      echo "running device_driver_info.sh device and driver info created"
      ./device_driver_info.sh
      cp device_driver_info.log /mnt/acs_results/linux_tools
      echo "device driver script run completed"
      popd
      sync /mnt

      # Generate the .dts file and move it to /mnt/acs_results/linux_tools
      dtc -I fs -O dts -o /mnt/acs_results/linux_tools/device_tree.dts /sys/firmware/devicetree/base 2>/dev/null

      # Generate tree format of sys hierarchy and saving it into logs.
      tree -d /sys > /mnt/acs_results/linux_dump/sys_hierarchy.log

      if [ -f /sys/firmware/fdt ]; then
        echo "copying fdt "
        cp /sys/firmware/fdt /home/root/fdt
        sync /mnt

        # Device Tree Validate script
        if [ -f /results/acs_results/linux_tools/dt-validate.log ]; then
          mv /results/acs_results/linux_tools/dt-validate.log /results/acs_results/linux_tools/dt-validate.log.old
        fi
 
        echo "Running dt-validate tool "
        dt-validate -s /usr/bin/processed_schema.json -m /home/root/fdt/fdt 2>> /mnt/acs_results/linux_tools/dt-validate.log
        sed -i '1s/^/DeviceTree bindings of Linux kernel version: 6.5 \ndtschema version: 2024.2 \n\n/' /mnt/acs_results/linux_tools/dt-validate.log
        if [ ! -s /mnt/acs_results/linux_tools/dt-validate.log ]; then
          echo "The FDT is compliant according to schema " >> /mnt/acs_results/linux_tools/dt-validate.log
        fi
      else
        echo  "Error: The FDT devicetree file, fdt, does not exist at /sys/firmware/fdt. Cannot run dt-schema tool" | tee /mnt/acs_results/linux_tools/dt-validate.log
      fi
      sync /mnt

      # Capturing System PSCI command output
      mkdir -p /mnt/acs_results/linux_tools/psci
      mount -t debugfs none /sys/kernel/debug
      cat /sys/kernel/debug/psci > /mnt/acs_results/linux_tools/psci/psci.log
      dmesg | grep psci > /mnt/acs_results/linux_tools/psci/psci_kernel.log

      # Compatible Devices driver association check script
      echo "Running DT Kernel Self Test"
      pushd /usr/kernel-selftest
      chmod +x dt/test_unprobed_devices.sh
      chmod +x dt/ktap_helpers.sh
      ./run_kselftest.sh -t dt:test_unprobed_devices.sh > /mnt/acs_results/linux_tools/dt_kselftest.log
      popd
      sync /mnt

      # Ethtool test run
      echo "Running Ethtool"
      # update resolv.conf with 8.8.8.8 DNS server
      echo "nameserver 8.8.8.8" >> /etc/resolv.conf

      # run ethtool-test.py, dump ethernet information, run self-tests if supported, and ping
      python3 /bin/ethtool-test.py | tee ethtool-test.log
      # remove color characters from log and save
      awk '{gsub(/\x1B\[[0-9;]*[JKmsu]/, "")}1' ethtool-test.log > /mnt/acs_results/linux_tools/ethtool-test.log
      sync /mnt

      # RUN read_write_check_blk_devices.py, parse block devices, and perform read if partition doesn't belond in precious partitions
      echo "Running BLK devices read and write check"
      python3 /bin/read_write_check_blk_devices.py | tee /mnt/acs_results/linux_tools/read_write_check_blk_devices.log
      sync /mnt

      # EDK2 Parser Tool run
      if [ -d "/mnt/acs_results/sct_results" ]; then
        echo "Running edk2-test-parser tool "
        mkdir -p /mnt/acs_results/edk2-test-parser
        cd /usr/bin/edk2-test-parser
        ./parser.py --md /mnt/acs_results/edk2-test-parser/edk2-test-parser.log /mnt/acs_results/sct_results/Overall/Summary.ekl /mnt/acs_results/sct_results/Sequence/EBBR.seq > /dev/null 2>&1
        echo "edk2-test-parser run completed"
      else
        echo "SCT result does not exist, cannot run edk2-test-parser tool cannot run"
      fi
      sync /mnt

      echo "System is rebooting for Capsule update"
      reboot
    else
      if [ -f /mnt/acs_tests/app/capsule_update_done.flag ]; then
        echo "Capsule update has done successfully..."
        rm /mnt/acs_tests/app/capsule_update_done.flag
      elif [ -f /mnt/acs_tests/app/capsule_update_unsupport.flag ]; then
        echo "Capsule update has failed ..."
        rm /mnt/acs_tests/app/capsule_update_unsupport.flag
      else
        echo "Capsule update has ignored..."
        rm /mnt/acs_tests/app/capsule_update_ignore.flag
      fi
    fi
  fi

  echo "Running acs log parser tool "
  if [ -d "/mnt/acs_results" ]; then
    /usr/bin/log_parser/main_log_parser.sh /mnt/acs_results /mnt/acs_tests/config/acs_config.txt /mnt/acs_tests/config/system_config.txt
  fi
  sleep 3
  sync /mnt
  echo "ACS run is completed"
else
  echo ""
  echo "Additional option set to not run ACS Tests. Skipping ACS tests on Linux"
  echo ""
fi

sync /mnt
echo "Please press <Enter> to continue ..."
echo -e -n "\n"
exit 0