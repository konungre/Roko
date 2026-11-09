# Opt-in diagnostic only. Never starts the AI worker or gates COSMIC readiness.
{ pkgs, program }:
{
  description = "Roko COSMIC session input diagnostics (unqualified)";
  wantedBy = [ "cosmic-session.target" ];
  after = [ "cosmic-session.target" ];
  partOf = [ "cosmic-session.target" ];
  # Avoid the target's automatic After= ordering on its wanted diagnostic.
  unitConfig.DefaultDependencies = false;
  serviceConfig = {
    Type = "oneshot";
    RemainAfterExit = true;
    ExecStart = "${pkgs.python3}/bin/python3 ${program}/cosmic_session_report.py --output %t/roko-cosmic-diagnostic/status.json";
    RuntimeDirectory = "roko-cosmic-diagnostic";
    RuntimeDirectoryMode = "0700";
    RuntimeDirectoryPreserve = "yes";
    UMask = "0077";
    TimeoutStartSec = "10s";
    Restart = "no";
    StandardOutput = "journal";
    StandardError = "journal";
    SyslogIdentifier = "roko-cosmic-diagnostic";
    KillMode = "control-group";
    NoNewPrivileges = true;
    PrivateNetwork = true;
    ProtectSystem = "strict";
    ProtectHome = "read-only";
    RestrictAddressFamilies = [ "AF_UNIX" ];
    MemoryAccounting = true;
    MemoryHigh = "64M";
    MemoryMax = "96M";
    OOMPolicy = "stop";
  };
}
