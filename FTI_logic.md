flowchart TD

%% ============= CLI AND FULL INSTALL =============

subgraph CLI [User and LMS command]
  A[User runs LMS update] --> B[Call full_tool_install]
end

subgraph FullInstall [Full tool install script]
  B --> FI1[Install system packages]
  FI1 --> FI2[Clone repo to temporary directory]
  FI2 --> FI3[Replace main install directory]
  FI3 --> FI4[Create or refresh Python virtual environment]
  FI4 --> FI5[Install Python dependencies]
  FI5 --> FI6[Run AP setup helpers and hostapd dnsmasq install]
  FI6 --> FI7[Install and enable lms systemd service]
  FI7 --> FI8[Install LMS command in usr local bin]
  FI8 --> FI9[Run configuration utility with whiptail]
  FI9 --> FI10[Write launch settings file]
  FI10 --> C[Invoke launch.sh for runtime]
end

%% ============= LAUNCH SCRIPT RUNTIME =============

subgraph Launch [launch.sh runtime]
  C --> L1[Check current directory]
  L1 --> L2{In expected tool directory}
  L2 -->|no| L3[Clone repo into expected directory]
  L3 --> L4[Reinvoke launch script with install flag and exit]
  L2 -->|yes| L5[Verify required files exist]

  L5 --> L6{Files missing}
  L6 -->|yes| L7[Run full install helper and exit]
  L6 -->|no| L8[Load config values and flags]

  L8 --> L9[Parse command line flags]
  L9 --> L10{Fast launch enabled}
  L10 -->|no| L11[Loop install dependencies]
  L10 -->|yes| L12[Skip dependency install]

  L11 --> L13
  L12 --> L13{Use local mode}

  L13 -->|no AP mode| L14[Run setupAP python script]
  L13 -->|yes local mode| L15[Skip AP setup]

  L14 --> L16[Ensure uap0 interface]
  L15 --> L18[Set uap0 ok flag false]

  L16 --> L17[Set uap0 ok flag true or false]
  L17 --> L19[Detect IP address with fallbacks]
  L18 --> L19

  L19 --> L20[Choose dnsmasq unit name]

  L20 --> L21[Ensure hostapd running]
  L21 --> L22{Use dnsmasq on uap0}

  L22 -->|yes and uap0 ok| L23[Ensure dnsmasq uap0 running]
  L22 -->|yes and no uap0| L24[Log skip dnsmasq uap0]
  L22 -->|no| L25[Ensure global dnsmasq running]

  L23 --> L26
  L24 --> L26
  L25 --> L26[Enable apache2 unit]

  L26 --> L27[Ensure apache2 running]
  L27 --> L28[Start monitor with retries]
  L28 --> L29[Print summary with IP and monitor port then exit]
end

%% ============= HELPER: ENSURE SERVICE =============

subgraph HelperEnsureService [ensure_service helper]
  ES1[Start ensure_service] --> ES2[Set attempt to 1]
  ES2 --> ES3{Attempt less or equal max retries}
  ES3 -->|no| ES8[Log error service failed after retries and return failure]
  ES3 -->|yes| ES4[Restart service using systemctl]
  ES4 --> ES5[Sleep retry delay]
  ES5 --> ES6{Service active}
  ES6 -->|yes| ES7[Log ok and return success]
  ES6 -->|no| ES9[Log warning and show status snippet]
  ES9 --> ES10[Increase attempt and loop]
  ES10 --> ES3
end

%% ============= HELPER: ENSURE UAP0 INTERFACE =============

subgraph HelperUAP0 [ensure_uap0_interface helper]
  U1[Start ensure uap0 interface] --> U2[Set attempt to 1]
  U2 --> U3{Attempt less or equal max tries}
  U3 -->|no| U10[Log error no uap0 after retries and return failure]

  U3 -->|yes| U4{Interface uap0 exists}
  U4 -->|yes| U5[Bring uap0 up and return success]
  U4 -->|no| U6{Interface wlan0 exists}
  U6 -->|no| U9[Sleep then increase attempt and loop]
  U6 -->|yes| U7[Try create uap0 from wlan0 with iw]
  U7 --> U8[Sleep short time for kernel]
  U8 --> U9[Increase attempt count]
  U9 --> U3
end

%% ============= HELPER: START MONITOR WITH RETRIES =============

subgraph HelperMonitor [start_monitor_with_retries helper]
  M1[Start monitor helper] --> M2[Set attempt to 1 and clear log and port file]
  M2 --> M3{Attempt less or equal max retries}
  M3 -->|no| M10[Log error monitor failed and show log path]

  M3 -->|yes| M4[Launch monitor with nohup python app]
  M4 --> M5[Wait for monitor port file until timeout]
  M5 --> M6{Port file found}
  M6 -->|yes| M7[Read port value log success and return]
  M6 -->|no| M8[Log warning and tail monitor log]
  M8 --> M9[Kill monitor process and increase attempt]
  M9 --> M3
end

%% ============= SETUPAP PYTHON FLOW =============

subgraph SetupAP [setupAP.py AP configuration]
  SA1[Start setupAP script] --> SA2[Stop hostapd dnsmasq apache and related]
  SA2 --> SA3[Remove existing uap0 interface]
  SA3 --> SA4[Check wlan0 connected with nmcli]
  SA4 --> SA5[Ping internet to confirm connectivity]

  SA5 --> SA6[Create uap0 from wlan0 with iw]
  SA6 --> SA7[Assign static IP to uap0]
  SA7 --> SA8[Loop wait for uap0 visible]

  SA8 --> SA9{uap0 visible before timeout}
  SA9 -->|no| SA10[Log error timed out waiting for uap0]
  SA9 -->|yes| SA11[Write hostapd configuration file]

  SA11 --> SA12[Write dnsmasq configuration and template]
  SA12 --> SA13[Update hosts file for portal and monitor names]
  SA13 --> SA14[Write apache captive portal site config]
  SA14 --> SA15[Enable rewrite and site then restart apache2]
  SA15 --> SA16[Enable and restart hostapd]
  SA16 --> SA17[Enable and start dnsmasq on uap0]
  SA17 --> SA18[Log access point up on static IP]
end

%% ============= CROSS LINKS (CALL RELATIONSHIPS) =============

%% Launch script calling helpers
L16 -. calls .-> U1
L21 -. calls .-> ES1
L23 -. calls .-> ES1
L25 -. calls .-> ES1
L27 -. calls .-> ES1
L28 -. calls .-> M1

%% Launch script running setupAP
L14 -. runs .-> SA1
