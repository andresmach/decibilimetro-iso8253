# Distributed under the OSI-approved BSD 3-Clause License.  See accompanying
# file Copyright.txt or https://cmake.org/licensing for details.

cmake_minimum_required(VERSION 3.5)

file(MAKE_DIRECTORY
  "/home/oem/esp/v5.4/esp-idf/components/bootloader/subproject"
  "/home/oem/Documents/DSP-ESP32-UNER/TrabajoUner_final_dsp/decibilimetro_ISO8253_UNER/decibilimetro_firmware/decibel/build/bootloader"
  "/home/oem/Documents/DSP-ESP32-UNER/TrabajoUner_final_dsp/decibilimetro_ISO8253_UNER/decibilimetro_firmware/decibel/build/bootloader-prefix"
  "/home/oem/Documents/DSP-ESP32-UNER/TrabajoUner_final_dsp/decibilimetro_ISO8253_UNER/decibilimetro_firmware/decibel/build/bootloader-prefix/tmp"
  "/home/oem/Documents/DSP-ESP32-UNER/TrabajoUner_final_dsp/decibilimetro_ISO8253_UNER/decibilimetro_firmware/decibel/build/bootloader-prefix/src/bootloader-stamp"
  "/home/oem/Documents/DSP-ESP32-UNER/TrabajoUner_final_dsp/decibilimetro_ISO8253_UNER/decibilimetro_firmware/decibel/build/bootloader-prefix/src"
  "/home/oem/Documents/DSP-ESP32-UNER/TrabajoUner_final_dsp/decibilimetro_ISO8253_UNER/decibilimetro_firmware/decibel/build/bootloader-prefix/src/bootloader-stamp"
)

set(configSubDirs )
foreach(subDir IN LISTS configSubDirs)
    file(MAKE_DIRECTORY "/home/oem/Documents/DSP-ESP32-UNER/TrabajoUner_final_dsp/decibilimetro_ISO8253_UNER/decibilimetro_firmware/decibel/build/bootloader-prefix/src/bootloader-stamp/${subDir}")
endforeach()
if(cfgdir)
  file(MAKE_DIRECTORY "/home/oem/Documents/DSP-ESP32-UNER/TrabajoUner_final_dsp/decibilimetro_ISO8253_UNER/decibilimetro_firmware/decibel/build/bootloader-prefix/src/bootloader-stamp${cfgdir}") # cfgdir has leading slash
endif()
