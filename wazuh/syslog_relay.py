#!/usr/bin/env python3
"""
Syslog UDP Relay for macOS + Docker
Receives syslog on port 514, preserves real source IP by embedding it
in the message, then forwards to Wazuh container.

Usage: sudo python3 syslog_relay.py
"""

import socket
import re

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 514
WAZUH_HOST  = "127.0.0.1"
WAZUH_PORT  = 5140   # Wazuh listens on this internal port

def relay():
    # Receive socket (UDP 514)
    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    recv_sock.bind((LISTEN_HOST, LISTEN_PORT))

    # Send socket
    send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print(f"[Syslog Relay] Listening on {LISTEN_HOST}:{LISTEN_PORT}")
    print(f"[Syslog Relay] Forwarding to {WAZUH_HOST}:{WAZUH_PORT}")
    print("[Syslog Relay] Real source IPs will be embedded in messages")
    print("-" * 60)

    while True:
        try:
            data, addr = recv_sock.recvfrom(65535)
            src_ip = addr[0]
            message = data.decode("utf-8", errors="replace").strip()

            # Embed real source IP into the syslog message
            # Format: prepend SRCIP=<ip> after the PRI+header if present
            # e.g. "<14>Feb 26 ... message" → "<14>Feb 26 ... SRCIP=10.1.50.2 message"
            pri_match = re.match(r'^(<\d+>)', message)
            if pri_match:
                pri = pri_match.group(1)
                rest = message[len(pri):]
                modified = f"{pri}SRCIP={src_ip} {rest}"
            else:
                modified = f"SRCIP={src_ip} {message}"

            print(f"[{src_ip}] → {message[:80]}...")
            send_sock.sendto(modified.encode("utf-8"), (WAZUH_HOST, WAZUH_PORT))

        except Exception as e:
            print(f"[ERROR] {e}")

if __name__ == "__main__":
    relay()
