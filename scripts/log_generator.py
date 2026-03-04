#!/usr/bin/env python3
"""
Dummy Log Generator - Simulates various attack patterns and normal traffic
"""
import json
import random
import time
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
import hashlib
import math

# Attack simulation parameters
NORMAL_IPS = [f"192.168.1.{i}" for i in range(1, 100)]
SUSPICIOUS_IPS = [f"10.0.0.{i}" for i in range(1, 20)]
ATTACKER_IPS = [f"45.33.32.{i}" for i in range(1, 10)]
TOR_EXIT_NODES = ["185.220.101.1", "185.220.101.2", "185.220.101.3"]

NORMAL_PATHS = ["/api/users", "/api/products", "/api/orders", "/health", "/api/search"]
SENSITIVE_PATHS = ["/api/admin", "/api/config", "/api/users/delete", "/api/export"]
RECON_PATHS = [
    "/.git/config", "/.env", "/wp-admin", "/phpmyadmin",
    "/admin", "/backup.sql", "/.aws/credentials", "/api/debug",
    "/server-status", "/actuator/health", "/.svn/entries"
]
INJECTION_PATHS = [
    "/api/search?q='; DROP TABLE users;--",
    "/api/users?id=1 OR 1=1",
    "/api/login?user=admin'--",
    "/api/data?file=../../../etc/passwd"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "curl/7.68.0",
    "python-requests/2.28.0",
]

SCANNER_USER_AGENTS = [
    "Nikto/2.1.6",
    "sqlmap/1.5",
    "Nmap Scripting Engine",
    "Wget/1.21",
    "masscan/1.0"
]

COUNTRIES = ["US", "CA", "UK", "DE", "FR", "JP", "CN", "RU", "BR", "IN"]
SUSPICIOUS_COUNTRIES = ["CN", "RU", "KP", "IR"]

class LogGenerator:
    def __init__(self, output_path: str = "logs/app.log"):
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_counter = 0
        self.user_sessions: Dict[str, Dict] = {}
        self.current_time = datetime.utcnow()  # Track current time for sequential logs

    def get_timestamp(self, offset_seconds: float = 0) -> str:
        """Get timestamp with optional offset from current time."""
        ts = self.current_time + timedelta(seconds=offset_seconds)
        return ts.isoformat() + "Z"

    def advance_time(self, seconds: float = 0.1):
        """Advance the internal clock by specified seconds."""
        self.current_time += timedelta(seconds=seconds)

    def generate_session_id(self) -> str:
        self.session_counter += 1
        return hashlib.md5(f"session_{self.session_counter}_{time.time()}".encode()).hexdigest()[:16]

    def generate_normal_log(self) -> Dict[str, Any]:
        """Generate a normal traffic log entry"""
        ip = random.choice(NORMAL_IPS)
        path = random.choice(NORMAL_PATHS)
        method = random.choice(["GET", "GET", "GET", "POST", "PUT"])
        status = random.choices([200, 201, 204, 400, 404, 500], weights=[70, 10, 5, 5, 8, 2])[0]

        self.advance_time(random.uniform(0.05, 0.2))  # 50-200ms between normal logs

        return {
            "@timestamp": self.get_timestamp(),
            "client_ip": ip,
            "method": method,
            "path": path,
            "status_code": status,
            "latency_ms": random.gauss(50, 20),
            "user_agent": random.choice(USER_AGENTS),
            "request_size_bytes": random.randint(100, 2000),
            "response_size_bytes": random.randint(500, 10000),
            "user_id": f"user_{random.randint(1, 1000)}" if random.random() > 0.3 else None,
            "session_id": self.generate_session_id(),
            "geo_country": random.choice(COUNTRIES[:5]),
            "geo_city": random.choice(["New York", "London", "Tokyo", "Berlin", "Paris"]),
            "is_authenticated": status not in [401, 403],
            "error_message": None if status < 400 else "Request failed"
        }

    def generate_auth_failure_log(self, attacker_ip: str = None) -> Dict[str, Any]:
        """Generate authentication failure log"""
        ip = attacker_ip or random.choice(SUSPICIOUS_IPS)

        self.advance_time(random.uniform(0.5, 2.0))  # 0.5-2s between auth attempts

        return {
            "@timestamp": self.get_timestamp(),
            "client_ip": ip,
            "method": "POST",
            "path": "/api/auth/login",
            "status_code": random.choice([401, 403]),
            "latency_ms": random.gauss(100, 30),
            "user_agent": random.choice(USER_AGENTS),
            "request_size_bytes": random.randint(200, 500),
            "response_size_bytes": random.randint(100, 300),
            "user_id": None,
            "session_id": self.generate_session_id(),
            "geo_country": random.choice(SUSPICIOUS_COUNTRIES),
            "geo_city": "Unknown",
            "is_authenticated": False,
            "error_message": "Invalid credentials"
        }

    def generate_brute_force_attack(self, count: int = 50) -> List[Dict[str, Any]]:
        """Generate brute force attack pattern - rapid auth failures from single IP"""
        attacker_ip = random.choice(ATTACKER_IPS)
        logs = []

        for i in range(count):
            log = self.generate_auth_failure_log(attacker_ip)
            log["latency_ms"] = random.gauss(20, 5)  # Fast requests
            log["user_id"] = f"admin" if random.random() > 0.5 else f"user_{random.randint(1, 10)}"
            logs.append(log)

        # Maybe one success at the end (compromised account)
        if random.random() > 0.7:
            success_log = logs[-1].copy()
            success_log["status_code"] = 200
            success_log["is_authenticated"] = True
            success_log["error_message"] = None
            logs.append(success_log)

        return logs

    def generate_traffic_burst(self, count: int = 200) -> List[Dict[str, Any]]:
        """Generate abnormal traffic burst (potential DDoS)"""
        burst_ips = [f"203.0.113.{random.randint(1, 255)}" for _ in range(20)]
        logs = []

        for _ in range(count):
            self.advance_time(random.uniform(0.01, 0.05))  # Very fast - 10-50ms (DDoS pattern)

            log = {
                "@timestamp": self.get_timestamp(),
                "client_ip": random.choice(burst_ips),
                "method": "GET",
                "path": random.choice(NORMAL_PATHS + ["/api/heavy-endpoint"]),
                "status_code": random.choices([200, 503, 504], weights=[30, 40, 30])[0],
                "latency_ms": random.gauss(2000, 500),  # High latency
                "user_agent": random.choice(USER_AGENTS[:2]),  # Similar user agents
                "request_size_bytes": random.randint(100, 500),
                "response_size_bytes": random.randint(100, 500),
                "user_id": None,
                "session_id": self.generate_session_id(),
                "geo_country": random.choice(SUSPICIOUS_COUNTRIES),
                "geo_city": "Unknown",
                "is_authenticated": False,
                "error_message": "Service unavailable" if random.random() > 0.5 else None
            }
            logs.append(log)

        return logs

    def generate_reconnaissance(self, count: int = 30) -> List[Dict[str, Any]]:
        """Generate reconnaissance/scanning pattern"""
        scanner_ip = random.choice(ATTACKER_IPS + TOR_EXIT_NODES)
        logs = []

        for path in random.sample(RECON_PATHS, min(count, len(RECON_PATHS))):
            self.advance_time(random.uniform(0.1, 0.5))  # Fast scanning - 100-500ms

            log = {
                "@timestamp": self.get_timestamp(),
                "client_ip": scanner_ip,
                "method": "GET",
                "path": path,
                "status_code": random.choice([404, 403, 500]),
                "latency_ms": random.gauss(30, 10),
                "user_agent": random.choice(SCANNER_USER_AGENTS),
                "request_size_bytes": random.randint(100, 300),
                "response_size_bytes": random.randint(100, 500),
                "user_id": None,
                "session_id": self.generate_session_id(),
                "geo_country": random.choice(SUSPICIOUS_COUNTRIES),
                "geo_city": "Unknown",
                "is_authenticated": False,
                "error_message": "Not found"
            }
            logs.append(log)

        return logs

    def generate_injection_attempt(self) -> List[Dict[str, Any]]:
        """Generate SQL injection / path traversal attempts"""
        attacker_ip = random.choice(ATTACKER_IPS)
        logs = []

        for path in INJECTION_PATHS:
            self.advance_time(random.uniform(1.0, 3.0))  # Manual testing - 1-3s between

            log = {
                "@timestamp": self.get_timestamp(),
                "client_ip": attacker_ip,
                "method": random.choice(["GET", "POST"]),
                "path": path,
                "status_code": random.choice([400, 403, 500]),
                "latency_ms": random.gauss(50, 15),
                "user_agent": random.choice(SCANNER_USER_AGENTS + USER_AGENTS[-2:]),
                "request_size_bytes": random.randint(200, 1000),
                "response_size_bytes": random.randint(100, 500),
                "user_id": None,
                "session_id": self.generate_session_id(),
                "geo_country": random.choice(SUSPICIOUS_COUNTRIES),
                "geo_city": "Unknown",
                "is_authenticated": False,
                "error_message": "Bad request"
            }
            logs.append(log)

        return logs

    def generate_suspicious_ip_behavior(self, count: int = 20) -> List[Dict[str, Any]]:
        """Generate suspicious IP behavior - accessing sensitive endpoints"""
        suspicious_ip = random.choice(TOR_EXIT_NODES + ATTACKER_IPS)
        logs = []

        for _ in range(count):
            self.advance_time(random.uniform(0.5, 2.0))  # Exploring - 0.5-2s between

            log = {
                "@timestamp": self.get_timestamp(),
                "client_ip": suspicious_ip,
                "method": random.choice(["GET", "POST", "DELETE"]),
                "path": random.choice(SENSITIVE_PATHS),
                "status_code": random.choice([200, 401, 403, 404]),
                "latency_ms": random.gauss(100, 30),
                "user_agent": random.choice(USER_AGENTS[-2:]),
                "request_size_bytes": random.randint(100, 500),
                "response_size_bytes": random.randint(100, 2000),
                "user_id": None,
                "session_id": self.generate_session_id(),
                "geo_country": random.choice(SUSPICIOUS_COUNTRIES),
                "geo_city": "Unknown",
                "is_authenticated": False,
                "error_message": "Access denied" if random.random() > 0.5 else None
            }
            logs.append(log)

        return logs

    def generate_http_anomalies(self, count: int = 15) -> List[Dict[str, Any]]:
        """Generate HTTP anomalies - unusual methods, headers"""
        logs = []
        anomalous_methods = ["TRACE", "OPTIONS", "CONNECT", "DEBUG"]

        for _ in range(count):
            self.advance_time(random.uniform(0.2, 1.0))  # Probing - 200ms-1s

            log = {
                "@timestamp": self.get_timestamp(),
                "client_ip": random.choice(SUSPICIOUS_IPS),
                "method": random.choice(anomalous_methods),
                "path": random.choice(NORMAL_PATHS + SENSITIVE_PATHS),
                "status_code": random.choice([400, 405, 501]),
                "latency_ms": random.gauss(30, 10),
                "user_agent": random.choice(SCANNER_USER_AGENTS),
                "request_size_bytes": random.randint(50, 200),
                "response_size_bytes": random.randint(100, 300),
                "user_id": None,
                "session_id": self.generate_session_id(),
                "geo_country": random.choice(COUNTRIES),
                "geo_city": "Unknown",
                "is_authenticated": False,
                "error_message": "Method not allowed"
            }
            logs.append(log)

        return logs

    def write_log(self, log: Dict[str, Any]):
        """Write a single log entry to file"""
        with open(self.output_path, 'a') as f:
            f.write(json.dumps(log) + '\n')

    def write_logs(self, logs: List[Dict[str, Any]]):
        """Write multiple log entries"""
        with open(self.output_path, 'a') as f:
            for log in logs:
                f.write(json.dumps(log) + '\n')

    def run_continuous(self, rate: int = 10, attack_probability: float = 0.1):
        """Run continuous log generation with real-time timestamps"""
        print(f"Starting log generator - Rate: {rate}/sec, Attack prob: {attack_probability}")
        print(f"Output: {self.output_path}")

        attack_types = [
            ("brute_force", self.generate_brute_force_attack),
            ("traffic_burst", self.generate_traffic_burst),
            ("reconnaissance", self.generate_reconnaissance),
            ("injection", self.generate_injection_attempt),
            ("suspicious_ip", self.generate_suspicious_ip_behavior),
            ("http_anomaly", self.generate_http_anomalies),
        ]

        log_count = 0
        attack_count = 0

        try:
            while True:
                # Sync internal clock with real time at start of each cycle
                self.current_time = datetime.utcnow()

                # Normal traffic - spread across the 1 second interval
                time_per_log = 1.0 / rate
                for i in range(rate):
                    self.current_time = datetime.utcnow() - timedelta(seconds=(rate - i) * time_per_log)
                    self.write_log(self.generate_normal_log())
                    log_count += 1

                # Random attack injection
                if random.random() < attack_probability:
                    attack_name, attack_func = random.choice(attack_types)
                    attack_logs = attack_func()
                    self.write_logs(attack_logs)
                    attack_count += 1
                    log_count += len(attack_logs)
                    print(f"[ATTACK] Generated {attack_name} attack ({len(attack_logs)} logs)")

                if log_count % 100 == 0:
                    print(f"Generated {log_count} logs, {attack_count} attacks")

                time.sleep(1)

        except KeyboardInterrupt:
            print(f"\nStopped. Total: {log_count} logs, {attack_count} attacks")

    def simulate_attack_scenario(self, scenario: str):
        """Simulate a specific attack scenario with real-time timestamps"""
        print(f"Simulating attack scenario: {scenario}")

        # Reset clock to current time
        self.current_time = datetime.utcnow()

        if scenario == "brute_force":
            logs = self.generate_brute_force_attack(100)
        elif scenario == "ddos":
            logs = self.generate_traffic_burst(500)
        elif scenario == "recon":
            logs = self.generate_reconnaissance(50)
        elif scenario == "injection":
            logs = self.generate_injection_attempt()
        elif scenario == "suspicious":
            logs = self.generate_suspicious_ip_behavior(30)
        elif scenario == "http_anomaly":
            logs = self.generate_http_anomalies(25)
        elif scenario == "mixed":
            logs = []
            logs.extend(self.generate_brute_force_attack(30))
            logs.extend(self.generate_reconnaissance(20))
            logs.extend(self.generate_injection_attempt())
            logs.extend(self.generate_suspicious_ip_behavior(15))
        else:
            print(f"Unknown scenario: {scenario}")
            return

        self.write_logs(logs)
        print(f"Generated {len(logs)} attack logs for scenario: {scenario}")


def main():
    parser = argparse.ArgumentParser(description="SOC Analyst Log Generator")
    parser.add_argument("--output", "-o", default="logs/app.log", help="Output log file path")
    parser.add_argument("--mode", "-m", choices=["continuous", "attack"], default="continuous",
                        help="Generation mode")
    parser.add_argument("--rate", "-r", type=int, default=10, help="Logs per second (continuous mode)")
    parser.add_argument("--attack-prob", "-p", type=float, default=0.1,
                        help="Attack probability (continuous mode)")
    parser.add_argument("--scenario", "-s",
                        choices=["brute_force", "ddos", "recon", "injection", "suspicious", "http_anomaly", "mixed"],
                        help="Attack scenario to simulate (attack mode)")

    args = parser.parse_args()
    generator = LogGenerator(args.output)

    if args.mode == "continuous":
        generator.run_continuous(rate=args.rate, attack_probability=args.attack_prob)
    elif args.mode == "attack" and args.scenario:
        generator.simulate_attack_scenario(args.scenario)
    else:
        print("For attack mode, please specify a scenario with --scenario")


if __name__ == "__main__":
    main()
