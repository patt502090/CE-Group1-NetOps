#!/usr/bin/env python3
"""
FTD Passive Identity — Push user-IP mapping via REST API
==========================================================
Called by FreeRADIUS post-auth to register user identity on FTD
so that Access Policy can use identity/group rules WITHOUT captive portal.

Flow:
  802.1X Auth → RADIUS Accept → this script → FTD REST API
  → FTD knows user↔IP mapping → group-based ACL works automatically

Usage (standalone test):
  python3 ftd_identity_push.py --user winnie.p --ip 10.1.20.11
  python3 ftd_identity_push.py --list
  python3 ftd_identity_push.py --delete --ip 10.1.20.11
  python3 ftd_identity_push.py --exec "show user-identity user all"
  python3 ftd_identity_push.py --test-ad winnie.p

Usage (from FreeRADIUS):
  Called automatically via post-auth exec module (see README)

============================================================
FTD 7.4.2 FDM REST API — Verified Endpoints
============================================================

Token (auth):
  POST   /api/fdm/v6/fdm/token             ← get/refresh/revoke OAuth2 token

Identity — Push user-IP (via CLI command):
  POST   /api/fdm/v6/action/command         ← send CLI commands to FTD
    body: { "commandInput": "...", "type": "Command" }
    CLI:  user-identity update user GROUP1\\winnie.p 10.1.20.11

Identity — Monitor/Delete sessions:
  GET    /api/fdm/v6/action/activeusersessions           ← list all sessions
  GET    /api/fdm/v6/action/activeusersessions/{objId}   ← get one session
  DELETE /api/fdm/v6/action/activeusersessions/{objId}   ← remove session

Identity Source — Test AD auth:
  POST   /api/fdm/v6/action/testidentitysource           ← test AD login
    body: { "identitySource": {"id":"...","type":"..."}, 
            "username":"...", "password":"...", "type":"TestIdentitySource" }

Realm — Get realm info:
  GET    /api/fdm/v6/object/realms                       ← list realms (get ID)

Traffic Users/Groups:
  GET    /api/fdm/v6/object/trafficusers                 ← list known users
  GET    /api/fdm/v6/object/realms/{realmId}/trafficusers ← users in realm
  GET    /api/fdm/v6/object/trafficusergroups            ← list groups (IT, HR)

Identity Policy:
  GET    /api/fdm/v6/policy/identitypolicies             ← view identity rules
  PUT    /api/fdm/v6/policy/identitypolicies/{id}        ← modify rules

Access Policy:
  GET    /api/fdm/v6/policy/accesspolicies               ← view ACL rules

Deploy (required after config changes):
  POST   /api/fdm/v6/operational/deploy                  ← deploy pending changes
"""

import requests
import json
import sys
import os
import logging
import argparse
from datetime import datetime

# Disable SSL warnings (FTD uses self-signed cert)
requests.packages.urllib3.disable_warnings(
    requests.packages.urllib3.exceptions.InsecureRequestWarning
)

# ─── Configuration ───────────────────────────────────────────────
# Override with environment variables or edit defaults below
FTD_HOST = os.environ.get("FTD_HOST", "10.1.1.2")
FTD_PORT = os.environ.get("FTD_PORT", "443")
FTD_USER = os.environ.get("FTD_USER", "admin")
FTD_PASS = os.environ.get("FTD_PASS", "Admin@gp1")  # Change this!
FTD_DOMAIN = os.environ.get("FTD_DOMAIN", "GROUP1")  # AD domain (NetBIOS name)
FTD_REALM = os.environ.get("FTD_REALM", "Samba_AD")  # Must match realm on FTD

LOG_FILE = os.environ.get(
    "FTD_IDENTITY_LOG", "/var/log/ftd_identity_push.log"
)
# ─────────────────────────────────────────────────────────────────

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="a"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("ftd-identity")


class FTDClient:
    """FTD REST API client — uses verified FDM 7.4.2 endpoints."""

    def __init__(self, host=FTD_HOST, port=FTD_PORT, user=FTD_USER, password=FTD_PASS):
        self.base = f"https://{host}:{port}/api/fdm/v6"
        self.user = user
        self.password = password
        self.token = None
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    # ──────────────────────── Token ────────────────────────
    # POST /api/fdm/v6/fdm/token
    # Parameters:
    #   grant_type: "password" | "refresh_token" | "revoke_token"
    #   username:   FTD admin username (for password grant)
    #   password:   FTD admin password (for password grant)
    # Response:
    #   access_token, refresh_token, token_type, expires_in

    def authenticate(self) -> bool:
        """
        POST /api/fdm/v6/fdm/token
        Get OAuth2 access token. Required before all other API calls.
        """
        url = f"{self.base}/fdm/token"
        payload = {
            "grant_type": "password",
            "username": self.user,
            "password": self.password,
        }
        try:
            resp = self.session.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                self.session.headers["Authorization"] = f"Bearer {self.token}"
                log.info("FTD auth OK — token expires in %ss", data.get("expires_in"))
                return True
            else:
                log.error(f"FTD auth failed: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            log.error(f"FTD connection error: {e}")
            return False

    def revoke_token(self):
        """
        POST /api/fdm/v6/fdm/token (grant_type=revoke_token)
        Free the API session — FTD only allows limited concurrent sessions.
        """
        if not self.token:
            return
        url = f"{self.base}/fdm/token"
        payload = {
            "grant_type": "revoke_token",
            "access_token": self.token,
            "token_to_revoke": self.token,
        }
        try:
            self.session.post(url, json=payload, timeout=5)
            log.debug("Token revoked")
        except Exception:
            pass

    # ──────────────── Command API (THE KEY!) ──────────────
    # POST /api/fdm/v6/action/command
    # Parameters (body):
    #   commandInput: string — the CLI command to execute
    #   type:         "Command"
    # Response:
    #   commandOutput: string — CLI output text

    def exec_command(self, command: str) -> str:
        """
        POST /api/fdm/v6/action/command
        Execute a CLI command on FTD and return output.
        This is how we push user-IP identity mappings.
        """
        url = f"{self.base}/action/command"
        payload = {
            "commandInput": command,
            "type": "Command",
        }
        log.info(f"CLI> {command}")
        try:
            resp = self.session.post(url, json=payload, timeout=15)
            if resp.status_code in (200, 201):
                output = resp.json().get("commandOutput", "")
                log.info(f"CLI output: {output.strip()}")
                return output
            else:
                log.error(f"Command failed: {resp.status_code} {resp.text}")
                return f"ERROR: {resp.status_code}"
        except Exception as e:
            log.error(f"Command error: {e}")
            return f"ERROR: {e}"

    def push_user_identity(self, username: str, ip_address: str,
                           domain: str = FTD_DOMAIN) -> bool:
        """
        Push user-IP mapping via CLI command API.

        CLI command: user-identity update user DOMAIN\\username ip_address
        This tells FTD: "this IP belongs to this AD user"
        so Access Policy identity/group rules match without captive portal.
        """
        # Format: DOMAIN\username (double backslash in string)
        fqdn_user = f"{domain}\\\\{username}"
        command = f"user-identity update user {fqdn_user} {ip_address}"

        log.info(f"Pushing identity: {domain}\\{username} -> {ip_address}")
        output = self.exec_command(command)

        if "ERROR" in output.upper() and "error" not in command.lower():
            log.error(f"Push failed: {output}")
            return False

        log.info(f"SUCCESS: {domain}\\{username} ↔ {ip_address}")
        return True

    def remove_user_identity(self, username: str, ip_address: str,
                             domain: str = FTD_DOMAIN) -> bool:
        """
        Remove user-IP mapping via CLI command.
        CLI: user-identity remove user DOMAIN\\username ip_address
        """
        fqdn_user = f"{domain}\\\\{username}"
        command = f"user-identity remove user {fqdn_user} {ip_address}"

        log.info(f"Removing identity: {domain}\\{username} <- {ip_address}")
        output = self.exec_command(command)
        return "ERROR" not in output.upper()

    def show_user_identity(self) -> str:
        """
        Show all user-IP mappings via CLI.
        CLI: show user-identity user all
        """
        return self.exec_command("show user-identity user all")

    def show_user_memory(self) -> str:
        """Show user-identity memory/status."""
        return self.exec_command("show user-identity memory")

    # ──────────── ActiveUserSessions (Monitor/Delete) ─────
    # GET    /api/fdm/v6/action/activeusersessions
    # GET    /api/fdm/v6/action/activeusersessions/{objId}
    # DELETE /api/fdm/v6/action/activeusersessions/{objId}
    #
    # Response model (each session):
    #   id, userName, ipAddress, realmName, loginTime, type, links

    def list_active_sessions(self) -> list:
        """
        GET /api/fdm/v6/action/activeusersessions
        List all active user-IP mappings on FTD.
        Returns list of session objects.
        """
        url = f"{self.base}/action/activeusersessions"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("items", [])
            else:
                log.error(f"List sessions failed: {resp.status_code} {resp.text}")
                return []
        except Exception as e:
            log.error(f"List sessions error: {e}")
            return []

    def delete_session_by_id(self, obj_id: str) -> bool:
        """
        DELETE /api/fdm/v6/action/activeusersessions/{objId}
        Remove a specific user session by its FTD object ID.
        """
        url = f"{self.base}/action/activeusersessions/{obj_id}"
        try:
            resp = self.session.delete(url, timeout=10)
            if resp.status_code in (200, 204):
                log.info(f"Deleted session {obj_id}")
                return True
            else:
                log.error(f"Delete failed: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            log.error(f"Delete error: {e}")
            return False

    def delete_session_by_ip(self, ip_address: str) -> bool:
        """
        Find session by IP address, then DELETE it.
        Searches active sessions and deletes the matching one.
        """
        sessions = self.list_active_sessions()
        for s in sessions:
            if s.get("ipAddress") == ip_address:
                return self.delete_session_by_id(s["id"])

        log.warning(f"No active session found for IP {ip_address}")
        return False

    # ──────── TestIdentitySource (Test AD auth) ───────────
    # POST /api/fdm/v6/action/testidentitysource
    # Parameters (body):
    #   identitySource: { id, type, version, name } — reference to realm
    #   username: AD username to test
    #   password: AD password to test
    #   type:     "TestIdentitySource"
    # Response:
    #   statusCode: 0 = success
    #   statusMessage: result text

    def test_identity_source(self, username: str, password: str,
                             realm_id: str = None, realm_name: str = None) -> dict:
        """
        POST /api/fdm/v6/action/testidentitysource
        Test AD authentication for a user. Verifies FTD → AD connectivity.
        """
        # Get realm ID if not provided
        if not realm_id:
            realms = self.get_realms()
            for r in realms:
                if r.get("name") == (realm_name or FTD_REALM):
                    realm_id = r["id"]
                    realm_type = r.get("type", "activedirectoryrealm")
                    realm_version = r.get("version")
                    break
            if not realm_id:
                log.error(f"Realm '{realm_name or FTD_REALM}' not found")
                return {"statusCode": -1, "statusMessage": "Realm not found"}

        url = f"{self.base}/action/testidentitysource"
        payload = {
            "identitySource": {
                "id": realm_id,
                "type": realm_type,
                "version": realm_version,
                "name": realm_name or FTD_REALM,
            },
            "username": username,
            "password": password,
            "type": "TestIdentitySource",
        }
        try:
            resp = self.session.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                log.info(f"AD test: code={data.get('statusCode')} msg={data.get('statusMessage')}")
                return data
            else:
                log.error(f"AD test failed: {resp.status_code} {resp.text}")
                return {"statusCode": resp.status_code, "statusMessage": resp.text}
        except Exception as e:
            log.error(f"AD test error: {e}")
            return {"statusCode": -1, "statusMessage": str(e)}

    # ──────────── Realm (get realm config) ────────────────
    # GET /api/fdm/v6/object/realms
    # Response: items[] with id, name, type, directoryConfigurations, etc.

    def get_realms(self) -> list:
        """
        GET /api/fdm/v6/object/realms
        List all configured identity realms (AD domains).
        """
        url = f"{self.base}/object/realms"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("items", [])
            else:
                log.error(f"Get realms failed: {resp.status_code}")
                return []
        except Exception as e:
            log.error(f"Get realms error: {e}")
            return []

    # ──────── Traffic Users & Groups ──────────────────────
    # GET /api/fdm/v6/object/trafficusers
    # GET /api/fdm/v6/object/realms/{parentId}/trafficusers
    # GET /api/fdm/v6/object/trafficusergroups

    def get_traffic_users(self, realm_id: str = None) -> list:
        """
        GET /api/fdm/v6/object/trafficusers
        (or /object/realms/{realmId}/trafficusers for specific realm)
        List users known to FTD from AD.
        """
        if realm_id:
            url = f"{self.base}/object/realms/{realm_id}/trafficusers"
        else:
            url = f"{self.base}/object/trafficusers"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("items", [])
            else:
                return []
        except Exception:
            return []

    def get_traffic_user_groups(self) -> list:
        """
        GET /api/fdm/v6/object/trafficusergroups
        List AD groups known to FTD (IT, HR, Finance, etc.)
        """
        url = f"{self.base}/object/trafficusergroups"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("items", [])
            else:
                return []
        except Exception:
            return []

    # ──────────── Identity Policy ─────────────────────────
    # GET /api/fdm/v6/policy/identitypolicies

    def get_identity_policies(self) -> list:
        """
        GET /api/fdm/v6/policy/identitypolicies
        View configured identity policy rules.
        """
        url = f"{self.base}/policy/identitypolicies"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("items", [])
            else:
                return []
        except Exception:
            return []

    # ──────────── Access Policy ───────────────────────────
    # GET /api/fdm/v6/policy/accesspolicies

    def get_access_policies(self) -> list:
        """
        GET /api/fdm/v6/policy/accesspolicies
        View configured access control rules.
        """
        url = f"{self.base}/policy/accesspolicies"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("items", [])
            else:
                return []
        except Exception:
            return []

    # ──────────── Deploy ──────────────────────────────────
    # POST /api/fdm/v6/operational/deploy

    def deploy(self) -> bool:
        """
        POST /api/fdm/v6/operational/deploy
        Deploy pending configuration changes.
        Required after modifying policies via API.
        """
        url = f"{self.base}/operational/deploy"
        try:
            resp = self.session.post(url, json={}, timeout=30)
            if resp.status_code in (200, 201, 202):
                log.info("Deploy initiated successfully")
                return True
            else:
                log.error(f"Deploy failed: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            log.error(f"Deploy error: {e}")
            return False


# ════════════════════════════════════════════════════════════
# FreeRADIUS Integration Functions
# ════════════════════════════════════════════════════════════

def radius_post_auth():
    """
    Called by FreeRADIUS exec module after successful authentication.
    Reads RADIUS reply attributes from environment variables.
    """
    username = os.environ.get("USER_NAME", "")
    ip_address = os.environ.get("FRAMED_IP_ADDRESS", "")

    # FreeRADIUS also provides these via Calling-Station-Id or reply attrs
    if not username:
        username = os.environ.get("User-Name", "")

    # Strip domain prefix if present (DOMAIN\user → user)
    if "\\" in username:
        username = username.split("\\")[-1]

    # For WiFi: the IP might not be assigned yet at post-auth time.
    # In that case, use RADIUS Accounting (Interim-Update) instead.
    if not ip_address:
        log.warning(
            f"No IP for user {username} at post-auth time. "
            "Will rely on Accounting-Start/Interim-Update."
        )
        return

    ftd = FTDClient()
    if not ftd.authenticate():
        sys.exit(1)

    try:
        success = ftd.push_user_identity(username, ip_address)
        sys.exit(0 if success else 1)
    finally:
        ftd.revoke_token()


def accounting_update():
    """
    Called by FreeRADIUS accounting module.
    More reliable for WiFi because the IP is known
    after DHCP completes (Accounting-Start/Interim-Update).

    RADIUS Accounting env vars:
      Acct-Status-Type:  Start | Interim-Update | Stop
      User-Name:         winnie.p
      Framed-IP-Address: 10.1.20.11
    """
    acct_type = os.environ.get("Acct-Status-Type", "")
    username = os.environ.get("User-Name", "")
    ip_address = os.environ.get("Framed-IP-Address", "")

    if "\\" in username:
        username = username.split("\\")[-1]

    log.info(f"Accounting: type={acct_type} user={username} ip={ip_address}")

    if not username or not ip_address:
        log.warning("Missing username or IP in accounting request")
        return

    ftd = FTDClient()
    if not ftd.authenticate():
        return

    try:
        if acct_type in ("Start", "Interim-Update"):
            ftd.push_user_identity(username, ip_address)
        elif acct_type == "Stop":
            ftd.remove_user_identity(username, ip_address)
        else:
            log.debug(f"Ignoring accounting type: {acct_type}")
    finally:
        ftd.revoke_token()


# ════════════════════════════════════════════════════════════
# CLI Interface
# ════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="FTD Passive Identity — Push user-IP mapping via REST API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --user winnie.p --ip 10.1.20.11    Push user identity
  %(prog)s --delete --user winnie.p --ip 10.1.20.11  Remove mapping
  %(prog)s --list                               List active sessions
  %(prog)s --show                               CLI: show user-identity
  %(prog)s --exec "show conn"                   Run any CLI command
  %(prog)s --test-ad winnie.p                   Test AD authentication
  %(prog)s --realms                             List configured realms
  %(prog)s --users                              List known AD users
  %(prog)s --groups                             List known AD groups
  %(prog)s --policies                           Show identity policies
  %(prog)s --deploy                             Deploy pending changes
        """,
    )
    parser.add_argument("--user", "-u", help="Username (e.g. winnie.p)")
    parser.add_argument("--ip", "-i", help="IP address (e.g. 10.1.20.11)")
    parser.add_argument("--domain", default=FTD_DOMAIN, help=f"AD domain (default: {FTD_DOMAIN})")
    parser.add_argument("--delete", "-d", action="store_true", help="Remove user-IP mapping")
    parser.add_argument("--list", "-l", action="store_true", help="List active sessions (API)")
    parser.add_argument("--show", "-s", action="store_true", help="CLI: show user-identity")
    parser.add_argument("--exec", "-e", dest="cmd", help="Execute any FTD CLI command")
    parser.add_argument("--test-ad", metavar="USER", help="Test AD auth for user (prompts password)")
    parser.add_argument("--realms", action="store_true", help="List identity realms")
    parser.add_argument("--users", action="store_true", help="List known AD users")
    parser.add_argument("--groups", action="store_true", help="List known AD groups")
    parser.add_argument("--policies", action="store_true", help="Show identity policies")
    parser.add_argument("--deploy", action="store_true", help="Deploy pending changes")
    parser.add_argument("--accounting", action="store_true", help="RADIUS accounting mode")
    parser.add_argument("--post-auth", action="store_true", help="FreeRADIUS post-auth mode")
    args = parser.parse_args()

    # RADIUS integration modes (non-interactive)
    if args.post_auth:
        radius_post_auth()
        return
    if args.accounting:
        accounting_update()
        return

    # Interactive CLI mode — authenticate first
    ftd = FTDClient()
    if not ftd.authenticate():
        sys.exit(1)

    try:
        # ── Push user identity ──
        if args.user and args.ip and not args.delete:
            ftd.push_user_identity(args.user, args.ip, args.domain)

        # ── Remove user identity ──
        elif args.delete and args.user and args.ip:
            ftd.remove_user_identity(args.user, args.ip, args.domain)

        # ── Delete session by IP (API) ──
        elif args.delete and args.ip:
            ftd.delete_session_by_ip(args.ip)

        # ── List active sessions (API) ──
        elif args.list:
            sessions = ftd.list_active_sessions()
            print(f"\n{'User':<25} {'IP Address':<16} {'Login Time':<20} {'ID'}")
            print("-" * 80)
            for s in sessions:
                print(
                    f"{s.get('userName', '?'):<25} "
                    f"{s.get('ipAddress', '?'):<16} "
                    f"{s.get('loginTime', '?'):<20} "
                    f"{s.get('id', '?')}"
                )
            print(f"\nTotal: {len(sessions)} active sessions")

        # ── Show user-identity (CLI) ──
        elif args.show:
            print(ftd.show_user_identity())

        # ── Execute any CLI command ──
        elif args.cmd:
            print(ftd.exec_command(args.cmd))

        # ── Test AD authentication ──
        elif args.test_ad:
            import getpass
            pwd = getpass.getpass(f"AD password for {args.test_ad}: ")
            result = ftd.test_identity_source(args.test_ad, pwd)
            code = result.get("statusCode", "?")
            msg = result.get("statusMessage", "?")
            print(f"\nResult: {'✅ SUCCESS' if code == 0 else '❌ FAILED'}")
            print(f"Code:    {code}")
            print(f"Message: {msg}")

        # ── List realms ──
        elif args.realms:
            realms = ftd.get_realms()
            print(f"\n{'Name':<20} {'Type':<30} {'ID'}")
            print("-" * 70)
            for r in realms:
                print(f"{r.get('name', '?'):<20} {r.get('type', '?'):<30} {r.get('id', '?')}")

        # ── List users ──
        elif args.users:
            users = ftd.get_traffic_users()
            print(f"\n{'Name':<30} {'Realm':<15} {'ID'}")
            print("-" * 65)
            for u in users:
                print(f"{u.get('name', '?'):<30} {u.get('realmName', '?'):<15} {u.get('id', '?')}")

        # ── List groups ──
        elif args.groups:
            groups = ftd.get_traffic_user_groups()
            print(f"\n{'Name':<30} {'Realm':<15} {'ID'}")
            print("-" * 65)
            for g in groups:
                print(f"{g.get('name', '?'):<30} {g.get('realmName', '?'):<15} {g.get('id', '?')}")

        # ── Show identity policies ──
        elif args.policies:
            policies = ftd.get_identity_policies()
            print(json.dumps(policies, indent=2))

        # ── Deploy ──
        elif args.deploy:
            ftd.deploy()

        else:
            parser.print_help()

    finally:
        ftd.revoke_token()


if __name__ == "__main__":
    main()
