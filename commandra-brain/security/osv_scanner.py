"""
OSV Scanner -- dependency vulnerability scanning using Google's OSV database.

Wraps the `osv-scanner` CLI binary.
Install: https://github.com/google/osv-scanner/releases
Or: go install github.com/google/osv-scanner/cmd/osv-scanner@latest
"""
from __future__ import annotations
import json
import shutil
import subprocess
from dataclasses import dataclass, field


@dataclass
class Vulnerability:
    vuln_id: str
    package: str
    version: str
    ecosystem: str
    summary: str
    severity: str
    aliases: list[str] = field(default_factory=list)
    fixed_in: str = ""

    def as_dict(self) -> dict:
        return {
            "vulnId": self.vuln_id,
            "package": self.package,
            "version": self.version,
            "ecosystem": self.ecosystem,
            "summary": self.summary,
            "severity": self.severity,
            "aliases": self.aliases,
            "fixedIn": self.fixed_in,
        }


@dataclass
class OSVScanResult:
    root: str
    vulnerabilities: list[Vulnerability]
    available: bool
    error: str | None = None

    def as_dict(self) -> dict:
        critical = [v for v in self.vulnerabilities if v.severity in ("CRITICAL", "HIGH")]
        return {
            "root": self.root,
            "vulnerabilities": [v.as_dict() for v in self.vulnerabilities],
            "vulnCount": len(self.vulnerabilities),
            "criticalAndHigh": len(critical),
            "available": self.available,
            "error": self.error,
        }


class OSVScanner:
    """Scans project dependencies against the Google OSV database."""

    BINARY = "osv-scanner"

    @classmethod
    def available(cls) -> bool:
        return shutil.which(cls.BINARY) is not None

    def scan(self, root: str) -> OSVScanResult:
        if not self.available():
            return OSVScanResult(root=root, vulnerabilities=[], available=False,
                                 error="osv-scanner not installed. See: https://github.com/google/osv-scanner/releases")
        try:
            cmd = [self.BINARY, "--format", "json", "--recursive", root]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            try:
                data = json.loads(proc.stdout)
            except json.JSONDecodeError:
                return OSVScanResult(root=root, vulnerabilities=[], available=True,
                                     error=proc.stderr[:300] or "Empty output")

            vulns: list[Vulnerability] = []
            for result in data.get("results", []):
                for pkg in result.get("packages", []):
                    pkg_info = pkg.get("package", {})
                    for v in pkg.get("vulnerabilities", []):
                        severity = "UNKNOWN"
                        for sev in v.get("severity", []):
                            if sev.get("type") == "CVSS_V3":
                                score = float(sev.get("score", "0") or "0")
                                if score >= 9.0:
                                    severity = "CRITICAL"
                                elif score >= 7.0:
                                    severity = "HIGH"
                                elif score >= 4.0:
                                    severity = "MEDIUM"
                                else:
                                    severity = "LOW"
                                break
                        fixed_in = ""
                        for affected in v.get("affected", []):
                            for r in affected.get("ranges", []):
                                for ev in r.get("events", []):
                                    if "fixed" in ev:
                                        fixed_in = ev["fixed"]
                                        break

                        vulns.append(Vulnerability(
                            vuln_id=v.get("id", ""),
                            package=pkg_info.get("name", ""),
                            version=pkg_info.get("version", ""),
                            ecosystem=pkg_info.get("ecosystem", ""),
                            summary=v.get("summary", "")[:200],
                            severity=severity,
                            aliases=v.get("aliases", []),
                            fixed_in=fixed_in,
                        ))

            return OSVScanResult(root=root, vulnerabilities=vulns, available=True)
        except subprocess.TimeoutExpired:
            return OSVScanResult(root=root, vulnerabilities=[], available=True, error="OSV scan timed out")
        except Exception as exc:
            return OSVScanResult(root=root, vulnerabilities=[], available=True, error=str(exc))
