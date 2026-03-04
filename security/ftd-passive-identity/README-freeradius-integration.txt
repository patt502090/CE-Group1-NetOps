# FTD Passive Identity — FreeRADIUS Integration
# ===============================================
# Add these configs to FreeRADIUS on the Raspberry Pi (10.1.10.10)
# to automatically push user-IP mappings to FTD after 802.1X auth.
#
# This eliminates the need for Active Auth (captive portal) on FTD.
# Users login ONCE via 802.1X → FTD gets identity automatically.

# ─── Option A: Accounting-based (Recommended) ──────────────
# More reliable because IP is known after DHCP completes.
# WLC/Switch sends Accounting-Start with Framed-IP-Address.

# 1. Enable accounting on WLC:
#    config radius acct network 1 enable
#    config radius acct interim-interval 600
#
# 2. Enable accounting on L2 switch:
#    aaa accounting dot1x default start-stop group radius
#    aaa accounting network default start-stop group radius

# 3. In /etc/freeradius/3.0/sites-enabled/default
#    Find the "accounting" section and add:
#
#    accounting {
#        # ... existing config ...
#
#        # Push identity to FTD on accounting Start/Interim
#        update request {
#            Exec-Program-Wait = "/usr/bin/python3 /opt/ftd-identity/ftd_identity_push.py --accounting"
#        }
#        exec
#    }

# ─── Option B: Post-auth exec (Simpler but less reliable) ──
# IP might not be known yet at post-auth time on WiFi.
# Works better for LAN 802.1X where IP is already assigned.

# In /etc/freeradius/3.0/sites-enabled/inner-tunnel
# Find the "post-auth" section and add at the end:
#
#    post-auth {
#        # ... existing dynamic VLAN assignment ...
#        
#        # Push identity to FTD (after VLAN assignment)
#        exec {
#            wait = no
#            program = "/usr/bin/python3 /opt/ftd-identity/ftd_identity_push.py --post-auth"
#        }
#    }

# ─── Setup Steps ───────────────────────────────────────────

# 1. Copy script to Raspberry Pi:
#    scp ftd_identity_push.py pi@10.1.10.10:/opt/ftd-identity/
#
# 2. Install dependency:
#    pip3 install requests
#
# 3. Set credentials (edit script or use env vars):
#    export FTD_HOST="10.1.1.2"
#    export FTD_USER="admin"
#    export FTD_PASS="Admin@123"
#    export FTD_REALM="Samba_AD"
#
# 4. Test manually:
#    python3 /opt/ftd-identity/ftd_identity_push.py --user winnie.p --ip 10.1.20.11
#    python3 /opt/ftd-identity/ftd_identity_push.py --list
#
# 5. FTD side — switch Identity Policy from Active Auth to Passive:
#    - FMC/FDM > Identity Policy > edit rule
#    - Change Action from "Active Auth" to "Passive Auth"
#    - OR remove the Identity Rule entirely (API handles it)
#    - Deploy
#
# 6. Verify:
#    - Connect via 802.1X
#    - Check FTD: show user-identity active-user-session
#    - User should appear without captive portal
